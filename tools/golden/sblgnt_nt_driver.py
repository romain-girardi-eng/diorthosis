#!/usr/bin/env python3
"""Source-complete whole-NT oracle over all 27 SBLGNT book PDFs.

The source manifest is built before any subprocess runs.  A successful run
accounts for every book as compared or as a named refusal; build failures,
stale output, malformed TEI, checker failures, and unparseable summaries are
fatal rather than changes to the denominator.
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
_STAT = re.compile(
  r"(\d+) source apps .*? (\d+) compared \| (\d+) uncovered apps in "
  r"(\d+) loci \| (\d+) ERRORS \| (\d+) gaps \| (\d+) documented")


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

  totals = {"compared": 0, "refused": 0, "uncovered": 0,
            "errors": 0, "gaps": 0, "divergences": 0}
  failures: list[dict] = []
  states: dict[str, str] = {}

  for book, expected in manifest.items():
    if book not in pdfs:
      failures.append({"book": book, "error": "missing book PDF"})
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
      print(f"{book} {name:18} FAILED build rc={build.returncode}")
      continue
    outputs = list(out.glob("*.tei.xml"))
    if len(outputs) != 1:
      failures.append({"book": book, "error":
                       f"expected one TEI output, found {len(outputs)}"})
      print(f"{book} {name:18} FAILED output count {len(outputs)}")
      continue
    tei = outputs[0]
    try:
      structured = emitted_app_count(tei)
    except (ET.ParseError, OSError, ValueError) as exc:
      failures.append({"book": book, "error": f"unparseable output: {exc}"})
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
      print(f"{book} {name:18} FAILED unparseable checker summary")
      continue
    source_apps, compared, uncovered, uncovered_loci, errors, gaps, divs = (
      map(int, stats.groups()))
    if source_apps != expected["source_apps"]:
      errors += 1
      failures.append({"book": book, "error":
                       f"manifest/checker source mismatch "
                       f"{expected['source_apps']} != {source_apps}"})
    totals["uncovered"] += uncovered
    totals["errors"] += errors
    totals["gaps"] += gaps
    totals["divergences"] += divs
    checker_failed = check.returncode != 0 or errors > 0
    if checker_failed:
      failures.append({"book": book, "error": "checker failed",
                       "detail": check.stdout[-2000:]})

    if structured == 0 and source_apps:
      if len(expected["chapters"]) == 1:
        reason = ("single-chapter book: band opens with bare verse numbers; "
                  "verse grammar requires C:V")
        states[book] = f"refused: {reason}"
        totals["refused"] += source_apps
        print(f"{book} {name:18} REFUSED {source_apps:4d} apps — {reason}")
      else:
        reason = "zero structured output without a declared convention reason"
        states[book] = f"refused: {reason}"
        totals["refused"] += source_apps
        failures.append({"book": book, "error": reason})
        print(f"{book} {name:18} REFUSED/FAIL {source_apps:4d} apps — {reason}")
      continue

    states[book] = f"compared: {compared}"
    totals["compared"] += compared
    status = "PASS" if not checker_failed else "FAIL"
    print(f"{book} {name:18} COMPARED {compared:4d}/{source_apps:4d} | "
          f"{uncovered:3d} uncovered in {uncovered_loci:3d} loci | {status}")

  missing_states = sorted(set(manifest) - set(states))
  if missing_states:
    failures.append({"book": ",".join(missing_states),
                     "error": "books have no compared/refused terminal state"})
  print(f"\nTOTAL: compared {totals['compared']} / refused-with-reason "
        f"{totals['refused']} / source {source_total} leaf apps | "
        f"uncovered {totals['uncovered']} | {totals['errors']} ERRORS | "
        f"{totals['gaps']} gaps | {totals['divergences']} typed divergences")
  ledger = {
    "source_total": source_total,
    "states": states,
    "failures": failures,
  }
  error_path = work / "nt_errors.json"
  error_path.write_text(
    json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
  print(f"wrote {error_path} with {len(failures)} fatal failures")
  return 1 if manifest_error or failures or totals["errors"] else 0


if __name__ == "__main__":
  raise SystemExit(main())
