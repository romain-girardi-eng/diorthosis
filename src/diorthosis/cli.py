"""Command-line interface.

Usage::

  diorthosis build edition.pdf -o out/            # born-digital PDF
  diorthosis build --alto p1.xml p2.xml -o out/   # any OCR engine's ALTO
  diorthosis build edition.pdf --pages 290-320 -o out/
  diorthosis inspect edition.pdf --page 300
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .anchor import anchor_page
from .conspectus import Registry, find_conspectus_pages, parse_conspectus, with_builtin_editors
from .ingest import ingest_alto, ingest_pdf
from .md import to_markdown
from .tei import to_tei


def _parse_pages(spec: str | None) -> list[int] | None:
  if not spec:
    return None
  out: list[int] = []
  for part in spec.split(","):
    if "-" in part:
      a, b = part.split("-", 1)
      out.extend(range(int(a), int(b) + 1))
    else:
      out.append(int(part))
  return out


def main(argv: list[str] | None = None) -> int:
  ap = argparse.ArgumentParser(
    prog="diorthosis",
    description="Compile published critical editions into TEI P5 + AI-ready Markdown",
  )
  sub = ap.add_subparsers(dest="cmd", required=True)

  b = sub.add_parser("build", help="compile a source into TEI + Markdown")
  b.add_argument("pdf", nargs="?", default=None, help="born-digital PDF")
  b.add_argument("--alto", nargs="+", default=None, metavar="XML",
                 help="ALTO files, one per page (any OCR engine's export)")
  b.add_argument("--pages", default=None, help="0-based page spec: 290-320 or 1,5,9")
  b.add_argument("-o", "--out", required=True, help="output directory")
  b.add_argument("--title", default=None)
  b.add_argument("--conspectus-page", type=int, default=None,
                 help="0-based page of the sigla list (default: search the front matter)")

  i = sub.add_parser("inspect", help="show one page's anchored structure")
  i.add_argument("pdf")
  i.add_argument("--page", type=int, required=True)

  args = ap.parse_args(argv)

  if args.cmd == "inspect":
    doc = ingest_pdf(args.pdf, pages=[args.page])
    for page in doc.pages:
      stats = anchor_page(page)
      print(to_markdown(doc))
      print(f"[anchoring: {stats['anchored']}/{stats['entries']} entries anchored]",
            file=sys.stderr)
    return 0

  if bool(args.pdf) == bool(args.alto):
    ap.error("build needs exactly one source: a PDF, or --alto files")
  doc = ingest_alto(args.alto) if args.alto else ingest_pdf(args.pdf, _parse_pages(args.pages))

  registry = Registry()
  if args.pdf:
    rng = ([args.conspectus_page] if args.conspectus_page is not None
           else range(0, 200))
    conspectus_text = find_conspectus_pages(args.pdf, rng)
    if conspectus_text:
      registry = parse_conspectus(conspectus_text)
      print(f"conspectus: {len(registry.witnesses)} witnesses, "
            f"{len(registry.editors)} editors declared")
  registry = with_builtin_editors(registry)

  totals = {"entries": 0, "anchored": 0, "unanchored": 0}
  for page in doc.pages:
    st = anchor_page(page)
    for k in totals:
      totals[k] += st[k]

  outdir = Path(args.out)
  outdir.mkdir(parents=True, exist_ok=True)
  stem = Path(doc.source_name).stem[:60] or "edition"
  (outdir / f"{stem}.tei.xml").write_text(
    to_tei(doc, title=args.title, registry=registry), encoding="utf-8")
  (outdir / f"{stem}.md").write_text(to_markdown(doc, title=args.title), encoding="utf-8")
  print(f"wrote {outdir / (stem + '.tei.xml')}")
  print(f"wrote {outdir / (stem + '.md')}")
  print(f"apparatus anchoring: {totals['anchored']}/{totals['entries']} entries anchored"
        + (f", {totals['unanchored']} unanchored" if totals["unanchored"] else ""))
  if doc.any_generative:
    print("[!] this document contains OCR-generated blocks (marked generative) — "
          "their text is a recognition model's output, not a decoded stream",
          file=sys.stderr)
  return 0


def run() -> int:
  try:
    return main()
  except (ValueError, KeyError) as exc:
    print(f"error: {exc}", file=sys.stderr)
    return 2
  except FileNotFoundError as exc:
    print(f"error: file not found: {getattr(exc, 'filename', exc)}", file=sys.stderr)
    return 2


if __name__ == "__main__":
  raise SystemExit(run())
