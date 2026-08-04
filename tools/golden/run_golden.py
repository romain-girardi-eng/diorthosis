#!/usr/bin/env python3
"""One command: scholar TEI -> typeset PDF -> diorthosis -> golden check.

Usage: run_golden.py scholar.xml workdir/ [--text-lang la] [--rng tei_all.rng]

Chains the whole golden pipeline and enforces the invariant the pieces
cannot see alone: the typeset PDF must have EXACTLY one page per golden
page (plus the conspectus page) — a TeX-broken overflow page would silently
desynchronize the comparison.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent.parent


def sh(*cmd: str, cwd: Path | None = None, show: bool = False) -> str:
  r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
  if r.returncode != 0:
    print(r.stdout[-2000:], file=sys.stderr)
    print(r.stderr[-2000:], file=sys.stderr)
    raise SystemExit(f"step failed: {' '.join(cmd[:3])}…")
  if show and r.stdout:
    print(r.stdout.rstrip())
  return r.stdout


def pdf_page_count(path: Path) -> int:
  from pdfminer.pdfdocument import PDFDocument
  from pdfminer.pdfpage import PDFPage
  from pdfminer.pdfparser import PDFParser
  with open(path, "rb") as f:
    return len(list(PDFPage.create_pages(PDFDocument(PDFParser(f)))))


def main() -> int:
  if len(sys.argv) < 3:
    print(__doc__, file=sys.stderr)
    return 2
  scholar = Path(sys.argv[1]).resolve()
  work = Path(sys.argv[2]).resolve()
  work.mkdir(parents=True, exist_ok=True)
  text_lang = sys.argv[sys.argv.index("--text-lang") + 1] \
    if "--text-lang" in sys.argv else "grc"
  rng = sys.argv[sys.argv.index("--rng") + 1] if "--rng" in sys.argv else None

  edition_json = work / (scholar.stem + ".edition.json")
  sh(sys.executable, str(HERE / "tei_to_edition.py"), str(scholar),
     str(edition_json), show=True)
  edition = json.loads(edition_json.read_text(encoding="utf-8"))
  stem = re.sub(r"[^A-Za-z0-9_-]+", "_", edition["title"])[:40]

  sh(sys.executable, str(HERE / "typeset_golden.py"), str(edition_json),
     str(work), show=True)
  sh("tectonic", f"{stem}.tex", cwd=work)

  golden = json.loads((work / f"{stem}.golden.json").read_text(encoding="utf-8"))
  ledger = golden.get("ledger", [])
  source_total = golden.get("source_total")
  emitted_entries = [entry for page in golden["pages"] for entry in page["entries"]]
  emitted_ids = {entry.get("source_id") for entry in emitted_entries}
  ledger_ids = [record.get("id") for record in ledger]
  excluded = [record for record in ledger if record.get("state") == "excluded"]
  ledger_emitted = {record.get("id") for record in ledger
                    if record.get("state") == "emitted"}
  bad = []
  if not isinstance(source_total, int) or source_total != len(ledger):
    bad.append(f"source_total={source_total!r} but ledger has {len(ledger)} records")
  if len(ledger_ids) != len(set(ledger_ids)):
    bad.append("ledger IDs are not unique")
  if any(record.get("state") not in ("emitted", "excluded") for record in ledger):
    bad.append("ledger contains a nonterminal state")
  if any(not record.get("reason") for record in excluded):
    bad.append("excluded ledger record has no reason")
  if ledger_emitted != emitted_ids or len(ledger_emitted) != len(emitted_entries):
    bad.append("ledger emitted IDs do not exactly equal typeset entry IDs")
  if len(emitted_entries) + len(excluded) != source_total:
    bad.append(f"{len(emitted_entries)} emitted + {len(excluded)} excluded "
               f"!= {source_total} source")
  reasons: dict[str, int] = {}
  for record in excluded:
    reason = record["reason"]
    reasons[reason] = reasons.get(reason, 0) + 1
  print(f"LEDGER: {len(emitted_entries)} compared of {source_total} source apps "
        f"({len(excluded)} excluded: {dict(sorted(reasons.items()))})")
  if bad:
    raise SystemExit("LEDGER FAILURE: " + "; ".join(bad))
  n_pdf = pdf_page_count(work / f"{stem}.pdf")
  expected = len(golden["pages"]) + golden.get("conspectus_pdf_pages", 1)
  if n_pdf != expected:
    raise SystemExit(
      f"OVERFLOW: typeset PDF has {n_pdf} pages, golden expects {expected} "
      "(conspectus + golden pages). Lower the pagination budget.")

  out = work / "out"
  sh(sys.executable, "-m", "diorthosis.cli", "build", str(work / f"{stem}.pdf"),
     "--conspectus-page", "0", "--text-lang", text_lang, "-o", str(out),
     cwd=REPO / "src")
  tei = out / f"{stem}.tei.xml"

  cmd = [sys.executable, str(HERE / "check_golden.py"),
         str(work / f"{stem}.golden.json"), str(tei)]
  if rng:
    cmd += ["--rng", rng]
  r = subprocess.run(cmd)
  return r.returncode


if __name__ == "__main__":
  raise SystemExit(main())
