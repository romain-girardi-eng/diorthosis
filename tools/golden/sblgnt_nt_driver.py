#!/usr/bin/env python3
"""Source-complete whole-NT oracle over all 27 SBLGNT book PDFs.

The source manifest is built before any subprocess runs.  A successful run
accounts for every book as compared or as a named refusal; build failures,
stale output, malformed TEI, checker failures, and unparseable summaries are
fatal rather than changes to the denominator.

Every source app lands in EXACTLY ONE bucket, and the partition is asserted
per book and on the corpus sum before the run may exit 0:

  compared     entry-by-entry against the scholars' TEI
  refused      whole book refused for a named convention reason
  uncovered    source loci the build never covered
  unaccounted  source app inside a covered locus with no counterpart —
               fatal, pending human adjudication
  adjudicated  an unaccounted app absorbed by a typed, evidence-checked
               divergence record
  unexamined   book whose run failed before comparison (already fatal, but
               it still owns its apps: a crash must not shrink the source
               denominator)

Buckets that overlap are the same lie as buckets that leak: an empty build
reports its whole book as "uncovered" through the checker's locus lens, and
counting that on top of "refused" is what made the printed totals exceed the
manifest by the size of the refused set.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from lxml import etree

REPO = Path(__file__).resolve().parents[2]
KNOWN = Path(__file__).parent / "sblgnt_known_divergences.json"
TEI = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
EXPECTED_SOURCE_TOTAL = 6921
BUCKETS = ("compared", "refused", "uncovered", "unaccounted", "adjudicated",
           "unexamined")
_STAT = re.compile(
  r"(\d+) source apps .*? (\d+) compared \| (\d+) unaccounted \| "
  r"(\d+) documented-unaccounted \| (\d+) uncovered apps in (\d+) loci \| "
  r"(\d+) ERRORS \| (\d+) gaps \| (\d+) documented")


def source_manifest(path: Path) -> dict[str, dict]:
  """Leaf-app counts and chapter sets, scoped by source milestones."""
  root = etree.parse(str(path)).getroot()
  counts: dict[str, int] = defaultdict(int)
  chapters: dict[str, set[int]] = defaultdict(set)
  current = ""
  for el in root.iter():
    if not isinstance(el.tag, str):
      continue
    xid = el.get(XML_ID) or ""
    milestone = re.match(r"(B\d+)K(\d+)(?:V\d+)?$", xid)
    if milestone:
      current = milestone.group(1)
      chapters[current].add(int(milestone.group(2)))
    if el.tag == f"{TEI}app" and not any(
        isinstance(d.tag, str) and d.tag == f"{TEI}app"
        for d in el.iterdescendants()):
      counts[current] += 1
  return {
    book: {"source_apps": counts[book], "chapters": sorted(chapters[book])}
    for book in sorted(counts)
  }


def identity_failures(assigned: dict[str, dict[str, int]],
                      manifest: dict[str, dict]) -> list[str]:
  """Where the outcome buckets stop partitioning the source manifest.

  Checked per book AND on the corpus sum: one book over-counting what
  another loses would leave the corpus total intact, and a total that only
  balances by coincidence is exactly the accounting this oracle must not
  print as healthy."""
  failures: list[str] = []
  for book, expected in sorted(manifest.items()):
    got = sum(assigned.get(book, {}).values())
    if got != expected["source_apps"]:
      failures.append(f"{book}: buckets sum to {got}, manifest has "
                      f"{expected['source_apps']} source apps "
                      f"({assigned.get(book, {})})")
  total_assigned = sum(sum(book.values()) for book in assigned.values())
  total_source = sum(item["source_apps"] for item in manifest.values())
  if total_assigned != total_source:
    failures.append(f"corpus: buckets sum to {total_assigned}, manifest has "
                    f"{total_source} source apps")
  return failures


def emitted_app_count(path: Path) -> int:
  root = ET.parse(path).getroot()
  edition = root.find(f".//{TEI}div[@type='edition']")
  if edition is None:
    raise ValueError("emitted TEI has no edition div")
  return sum(1 for _ in edition.iter(f"{TEI}app"))


def main() -> int:
  if len(sys.argv) != 3:
    print(__doc__, file=sys.stderr)
    return 2
  data = Path(sys.argv[1]).resolve()
  work = Path(sys.argv[2]).resolve()
  work.mkdir(parents=True, exist_ok=True)
  source = data / "sblgnt.xml"
  try:
    manifest = source_manifest(source)
  except (OSError, etree.XMLSyntaxError) as exc:
    print(f"FATAL source manifest: {exc}", file=sys.stderr)
    return 1
  source_total = sum(item["source_apps"] for item in manifest.values())
  manifest_error = source_total != EXPECTED_SOURCE_TOTAL or len(manifest) != 27
  print(f"SOURCE MANIFEST: {len(manifest)} books, {source_total} leaf apps")
  if manifest_error:
    print(f"FATAL expected 27 books/{EXPECTED_SOURCE_TOTAL} leaf apps, got "
          f"{len(manifest)}/{source_total}")

  pdfs: dict[str, tuple[Path, str]] = {}
  for pdf in sorted((data / "sblgnt_pdfs").glob("*-SBLGNT-*.pdf")):
    match = re.match(r"(\d+)-SBLGNT-(.+)\.pdf", pdf.name)
    if not match or not 61 <= int(match.group(1)) <= 87:
      continue
    pdfs[f"B{int(match.group(1)) - 60:02d}"] = (pdf, match.group(2))

  totals = dict.fromkeys(BUCKETS, 0)
  observed = {"errors": 0, "gaps": 0, "divergences": 0}
  failures: list[dict] = []
  states: dict[str, str] = {}
  assigned: dict[str, dict[str, int]] = {}
  unaccounted_loci: list[str] = []

  def assign(book: str, **buckets: int) -> None:
    assigned[book] = buckets
    for name, value in buckets.items():
      totals[name] += value

  for book, expected in manifest.items():
    if book not in pdfs:
      failures.append({"book": book, "error": "missing book PDF"})
      assign(book, unexamined=expected["source_apps"])
      print(f"{book} {'?':18} FAILED missing PDF")
      continue
    pdf, name = pdfs[book]
    out = work / name
    if out.exists():
      shutil.rmtree(out)
    build = subprocess.run(
      [sys.executable, "-m", "diorthosis.cli", "build", str(pdf),
       "-o", str(out)],
      capture_output=True, text=True, cwd=REPO)
    if build.returncode != 0:
      detail = (build.stderr or build.stdout)[-1000:]
      failures.append({"book": book, "error": "build failed", "detail": detail})
      assign(book, unexamined=expected["source_apps"])
      print(f"{book} {name:18} FAILED build rc={build.returncode}")
      continue
    outputs = list(out.glob("*.tei.xml"))
    if len(outputs) != 1:
      failures.append({"book": book, "error":
                       f"expected one TEI output, found {len(outputs)}"})
      assign(book, unexamined=expected["source_apps"])
      print(f"{book} {name:18} FAILED output count {len(outputs)}")
      continue
    tei = outputs[0]
    try:
      structured = emitted_app_count(tei)
    except (ET.ParseError, OSError, ValueError) as exc:
      failures.append({"book": book, "error": f"unparseable output: {exc}"})
      assign(book, unexamined=expected["source_apps"])
      print(f"{book} {name:18} FAILED unparseable TEI: {exc}")
      continue

    check = subprocess.run(
      [sys.executable, "tools/golden/verse_check.py", str(source), str(tei),
       "--book", book, "--known", str(KNOWN)],
      capture_output=True, text=True, cwd=REPO)
    summary = next((line for line in check.stdout.splitlines()
                    if " source apps | " in line), "")
    stats = _STAT.search(summary)
    if stats is None:
      failures.append({"book": book, "error": "unparseable checker output",
                       "detail": check.stdout[-1000:]})
      assign(book, unexamined=expected["source_apps"])
      print(f"{book} {name:18} FAILED unparseable checker summary")
      continue
    (source_apps, compared, unaccounted, adjudicated, uncovered,
     uncovered_loci, errors, gaps, divs) = map(int, stats.groups())
    if source_apps != expected["source_apps"]:
      errors += 1
      failures.append({"book": book, "error":
                       f"manifest/checker source mismatch "
                       f"{expected['source_apps']} != {source_apps}"})
    # the checker prints one band per unaccounted app; a counter that no
    # longer matches its own printed evidence is itself a fatal defect
    printed = [line.strip().removeprefix("UNACCOUNTED ")
               for line in check.stdout.splitlines()
               if line.strip().startswith("UNACCOUNTED ")]
    if len(printed) != unaccounted:
      failures.append({"book": book, "error":
                       f"checker printed {len(printed)} unaccounted bands for "
                       f"a count of {unaccounted}"})
    unaccounted_loci.extend(f"{book} {name} {line}" for line in printed)
    observed["errors"] += errors
    observed["gaps"] += gaps
    observed["divergences"] += divs
    checker_failed = check.returncode != 0 or errors > 0
    if checker_failed:
      failures.append({"book": book, "error": "checker failed",
                       "detail": check.stdout[-2000:]})

    if structured == 0 and source_apps:
      # An empty build covers no locus, so the checker reports the whole book
      # as "uncovered" too; the refusal is the book's single outcome and the
      # locus-lens view of the same apps must not be added on top.
      if len(expected["chapters"]) == 1:
        reason = ("single-chapter book: band opens with bare verse numbers; "
                  "verse grammar requires C:V")
        states[book] = f"refused: {reason}"
        assign(book, refused=expected["source_apps"])
        print(f"{book} {name:18} REFUSED {source_apps:4d} apps — {reason}")
      else:
        reason = "zero structured output without a declared convention reason"
        states[book] = f"refused: {reason}"
        assign(book, refused=expected["source_apps"])
        failures.append({"book": book, "error": reason})
        print(f"{book} {name:18} REFUSED/FAIL {source_apps:4d} apps — {reason}")
      continue

    states[book] = (f"compared: {compared}" if not unaccounted else
                    f"compared: {compared}, unaccounted: {unaccounted}")
    assign(book, compared=compared, uncovered=uncovered,
           unaccounted=unaccounted, adjudicated=adjudicated)
    # a FAIL names what failed: an unaccounted app is not an apparatus error
    flags = []
    if errors:
      flags.append(f"{errors} ERRORS")
    if unaccounted:
      flags.append(f"{unaccounted} unaccounted")
    if checker_failed and not flags:
      flags.append(f"checker rc={check.returncode}")
    status = "PASS" if not flags else "FAIL " + ", ".join(flags)
    print(f"{book} {name:18} COMPARED {compared:4d}/{source_apps:4d} | "
          f"{uncovered:3d} uncovered in {uncovered_loci:3d} loci | {status}")

  missing_states = sorted(set(manifest) - set(states))
  if missing_states:
    failures.append({"book": ",".join(missing_states),
                     "error": "books have no compared/refused terminal state"})
  identity = identity_failures(assigned, manifest)
  bucket_sum = sum(totals.values())
  print(f"\nTOTAL: {source_total} source leaf apps = "
        f"{totals['compared']} compared + {totals['refused']} "
        f"refused-with-reason + {totals['uncovered']} uncovered + "
        f"{totals['unaccounted']} unaccounted + {totals['adjudicated']} "
        f"adjudicated + {totals['unexamined']} unexamined | "
        f"{observed['errors']} ERRORS | {observed['gaps']} gaps | "
        f"{observed['divergences']} typed divergences")
  if identity:
    print(f"ACCOUNTING FAILURE: buckets sum to {bucket_sum}, manifest has "
          f"{source_total} source leaf apps")
    for failure in identity:
      print(f"   {failure}")
    failures.append({"book": "corpus", "error": "bucket identity violated",
                     "detail": identity})
  else:
    print(f"ACCOUNTING: identity holds — {bucket_sum} == {source_total} "
          f"source leaf apps, all {len(manifest)} books reconciled")
  if unaccounted_loci:
    print(f"UNACCOUNTED (fatal, pending human adjudication): "
          f"{totals['unaccounted']} source apps in no outcome bucket")
    for locus in unaccounted_loci:
      print(f"   {locus}")
    failures.append({"book": "corpus", "error":
                     f"{totals['unaccounted']} unaccounted source apps",
                     "detail": unaccounted_loci})
  ledger = {
    "source_total": source_total,
    "buckets": totals,
    "per_book_buckets": assigned,
    "identity_failures": identity,
    "unaccounted": unaccounted_loci,
    "states": states,
    "failures": failures,
  }
  error_path = work / "nt_errors.json"
  error_path.write_text(
    json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
  print(f"wrote {error_path} with {len(failures)} fatal failures")
  return 1 if manifest_error or failures or observed["errors"] else 0


if __name__ == "__main__":
  raise SystemExit(main())
