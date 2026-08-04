#!/usr/bin/env python3
"""Whole-NT driver: build all 27 SBLGNT book PDFs and verse_check each
against the scholarly TEI. Usage:

  python3 sblgnt_nt_driver.py <dir-with-sblgnt_pdfs-and-sblgnt.xml> <workdir>

Expects <dir>/sblgnt_pdfs/NN-SBLGNT-Book.pdf and <dir>/sblgnt.xml
(fetch_sources.sh + https://sblgnt.com/download/SBLGNTpdf.zip)."""
import re
import subprocess
import sys
from pathlib import Path

D = Path(sys.argv[1])
pdfs = sorted(D.glob("sblgnt_pdfs/6*-SBLGNT-*.pdf")) + sorted(D.glob("sblgnt_pdfs/[78]*-SBLGNT-*.pdf"))
tot_err = tot_gap = tot_div = tot_apps = 0
fails = []
for i, pdf in enumerate(sorted(D.glob("sblgnt_pdfs/*-SBLGNT-*.pdf"))):
    m = re.match(r"(\d+)-SBLGNT-(.+)\.pdf", pdf.name)
    if not m or m.group(2) == "Front":
        continue
    book = f"B{int(m.group(1)) - 60:02d}"
    out = Path(sys.argv[2]) / m.group(2)
    subprocess.run([sys.executable, "-m", "diorthosis.cli", "build", str(pdf),
                    "-o", str(out)], capture_output=True, text=True,
                   cwd=str(Path(__file__).resolve().parents[2] / "src"))
    tei = next(out.glob("*.tei.xml"), None)
    if tei is None:
        fails.append((book, "no output"))
        continue
    r = subprocess.run(
      [sys.executable, "tools/golden/verse_check.py", str(D / "sblgnt.xml"),
       str(tei), "--book", book,
       "--known", str(Path(__file__).parent / "sblgnt_known_divergences.json")],
      capture_output=True, text=True,
      cwd=str(Path(__file__).resolve().parents[2]))
    last = [ln for ln in r.stdout.splitlines() if "|" in ln]
    stat = last[0] if last else r.stdout[-200:]
    mm = re.search(r"(\d+) scholar apps.*?(\d+) ERRORS \| (\d+) gaps \| (\d+) documented", stat)
    if mm:
        apps, errs, gapn, divn = map(int, mm.groups())
        tot_apps += apps; tot_err += errs; tot_gap += gapn; tot_div += divn
        flag = "PASS" if errs == 0 else "FAIL"
        print(f"{book} {m.group(2):18} {apps:4d} apps  {errs:3d} err  {gapn:3d} gaps  {flag}")
        if errs:
            fails.append((book, [ln for ln in r.stdout.splitlines() if "ERROR" in ln]))
    else:
        print(f"{book} {m.group(2):18} UNPARSEABLE: {stat[:80]}")
        fails.append((book, stat[:120]))
print(f"\nTOTAL: {tot_apps} apps | {tot_err} ERRORS | {tot_gap} gaps | {tot_div} documented divergences")
import json

all_errors = []
for b, f in fails:
    if isinstance(f, list):
        for ln in f:
            if "ERROR " in ln and "|" not in ln:
                all_errors.append({"book": b, "err": ln.strip()})
Path(sys.argv[2]) / "nt_errors.json".write_text(json.dumps(all_errors, ensure_ascii=False, indent=1))
print(f"wrote /tmp/nt_errors.json with {len(all_errors)} errors")
