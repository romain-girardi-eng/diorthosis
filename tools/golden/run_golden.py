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


def sh(*cmd: str, cwd: Path | None = None) -> None:
  r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
  if r.returncode != 0:
    print(r.stdout[-2000:], file=sys.stderr)
    print(r.stderr[-2000:], file=sys.stderr)
    raise SystemExit(f"step failed: {' '.join(cmd[:3])}…")


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
     str(edition_json))
  edition = json.loads(edition_json.read_text(encoding="utf-8"))
  stem = re.sub(r"[^A-Za-z0-9_-]+", "_", edition["title"])[:40]

  sh(sys.executable, str(HERE / "typeset_golden.py"), str(edition_json),
     str(work))
  sh("tectonic", f"{stem}.tex", cwd=work)

  golden = json.loads((work / f"{stem}.golden.json").read_text(encoding="utf-8"))
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
