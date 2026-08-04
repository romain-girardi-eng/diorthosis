#!/usr/bin/env python3
"""Whole-NT driver: build all 27 SBLGNT book PDFs and verse_check each
against the scholarly TEI. Usage:

  python3 sblgnt_nt_driver.py <dir-with-sblgnt_pdfs-and-sblgnt.xml> <workdir>

Expects <dir>/sblgnt_pdfs/NN-SBLGNT-Book.pdf and <dir>/sblgnt.xml
(fetch_sources.sh + https://sblgnt.com/download/SBLGNTpdf.zip). Writes a
per-book PASS/FAIL table and <workdir>/nt_errors.json.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KNOWN = Path(__file__).parent / "sblgnt_known_divergences.json"
_STAT = re.compile(
  r"(\d+) scholar apps.*?(\d+) ERRORS \| (\d+) gaps \| (\d+) documented")


def main() -> int:
  data = Path(sys.argv[1])
  work = Path(sys.argv[2])
  work.mkdir(parents=True, exist_ok=True)
  totals = [0, 0, 0, 0]
  failures: list[tuple[str, object]] = []

  for pdf in sorted(data.glob("sblgnt_pdfs/*-SBLGNT-*.pdf")):
    m = re.match(r"(\d+)-SBLGNT-(.+)\.pdf", pdf.name)
    if not m or m.group(2) == "Front":
      continue
    book = f"B{int(m.group(1)) - 60:02d}"
    out = work / m.group(2)
    subprocess.run(
      [sys.executable, "-m", "diorthosis.cli", "build", str(pdf),
       "-o", str(out)],
      capture_output=True, text=True, cwd=str(REPO / "src"))
    tei = next(out.glob("*.tei.xml"), None)
    if tei is None:
      failures.append((book, "no output"))
      continue
    r = subprocess.run(
      [sys.executable, "tools/golden/verse_check.py",
       str(data / "sblgnt.xml"), str(tei), "--book", book,
       "--known", str(KNOWN)],
      capture_output=True, text=True, cwd=str(REPO))
    stats = [ln for ln in r.stdout.splitlines() if "|" in ln]
    mm = _STAT.search(stats[0]) if stats else None
    if mm is None:
      print(f"{book} {m.group(2):18} UNPARSEABLE: {r.stdout[-120:]!r}")
      failures.append((book, r.stdout[-120:]))
      continue
    apps, errs, gaps, divs = map(int, mm.groups())
    for i, v in enumerate((apps, errs, gaps, divs)):
      totals[i] += v
    print(f"{book} {m.group(2):18} {apps:4d} apps  {errs:3d} err  "
          f"{gaps:3d} gaps  {'PASS' if errs == 0 else 'FAIL'}")
    if errs:
      failures.append(
        (book, [ln for ln in r.stdout.splitlines() if "ERROR" in ln]))

  print(f"\nTOTAL: {totals[0]} apps | {totals[1]} ERRORS | "
        f"{totals[2]} gaps | {totals[3]} documented divergences")
  errors = [
    {"book": b, "err": ln.strip()}
    for b, f in failures if isinstance(f, list)
    for ln in f if "ERROR " in ln and "|" not in ln
  ]
  (work / "nt_errors.json").write_text(
    json.dumps(errors, ensure_ascii=False, indent=1))
  print(f"wrote {work / 'nt_errors.json'} with {len(errors)} errors")
  return 1 if totals[1] else 0


if __name__ == "__main__":
  raise SystemExit(main())
