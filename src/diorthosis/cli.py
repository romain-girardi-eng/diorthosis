"""Command-line interface.

Usage::

  diorthosis build edition.pdf -o out/            # born-digital PDF
  diorthosis build --alto p1.xml p2.xml -o out/   # any OCR engine's ALTO
  diorthosis build edition.pdf --pages 290-320 -o out/
  diorthosis inspect edition.pdf --page 300
  diorthosis validate out/edition.md              # md-ce/0.2 invariants
  diorthosis roundtrip out/edition.md out/edition.tei.xml
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .anchor import anchor_page
from .conspectus import Registry, bootstrap_registry, with_builtin_editors
from .ingest import ingest_alto, ingest_hocr, ingest_pagexml, ingest_pdf
from .md import to_markdown
from .model import Document, Layer
from .tei import resolve_parsed, to_tei
from .witnesses import witness_table


def _used_witness_sigla(doc: Document, registry: Registry) -> set[str]:
  """Collect witnesses from the same resolved structures emitted as TEI."""
  used: set[str] = set()
  for page in doc.pages:
    for block in page.blocks:
      if block.layer is not Layer.APPARATUS:
        continue
      for entry in block.entries or []:
        parsed = resolve_parsed(entry, registry)
        if parsed is None:
          continue
        used.update(parsed.lemma_attribution.witnesses)
        for reading in parsed.readings:
          used.update(reading.attribution.witnesses)
  return used


def _parse_pages(spec: str | None) -> list[int] | None:
  if spec is None:
    return None
  if not spec.strip():
    raise ValueError("--pages given but empty; omit the flag to process all pages")
  out: set[int] = set()
  for part in spec.split(","):
    part = part.strip()
    m = re.fullmatch(r"(\d+)-(\d+)", part)
    if m:
      a, b = int(m.group(1)), int(m.group(2))
      if b < a:
        raise ValueError(f"--pages range {part!r} is reversed")
      out.update(range(a, b + 1))
    elif re.fullmatch(r"\d+", part):
      out.add(int(part))
    else:
      raise ValueError(
        f"--pages element {part!r} is not a 0-based page number or A-B range")
  # SORTED is load-bearing: pdfminer yields pages in document order
  # regardless of the requested order; an unsorted list would silently
  # cross-label pages (content of one page under another's index)
  return sorted(out)


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
  b.add_argument("--hocr", nargs="+", default=None, metavar="HTML",
                 help="hOCR files (any OCR engine's export; may be multi-page)")
  b.add_argument("--page-xml", nargs="+", default=None, metavar="XML",
                 help="PAGE-XML files, one per page (kraken/eScriptorium/Transkribus)")
  b.add_argument("--pages", default=None, help="0-based page spec: 290-320 or 1,5,9")
  b.add_argument("-o", "--out", required=True, help="output directory")
  b.add_argument("--title", default=None)
  b.add_argument("--conspectus-page", type=int, default=None,
                 help="0-based page of the sigla list (default: search the front matter)")
  b.add_argument("--text-lang", choices=("grc", "la"), default="grc",
                 help="language of the CONSTITUTED TEXT (PDF source only): "
                      "'la' treats the Latin-script main band as the text and "
                      "its foot band as the apparatus")
  b.add_argument("--overrides", default=None, metavar="JSON",
                 help="per-edition human-review overrides file; every "
                      "applied override is marked resp='#human-review' "
                      "in the TEI")
  b.add_argument("--sigla", default=None, metavar="S1,S2,…",
                 help="comma-separated witness sigla (e.g. 'R,V,S,SV') for "
                      "editions whose PDF prints no conspectus siglorum; "
                      "merged into whatever the front matter yields")

  i = sub.add_parser("inspect", help="show one page's anchored structure")
  i.add_argument("pdf")
  i.add_argument("--page", type=int, required=True)
  i.add_argument("--conspectus-page", type=int, default=None,
                 help="0-based page of the sigla list (default: search the front matter)")

  v = sub.add_parser("validate", help="check a md-ce file against SPEC.md's invariants")
  v.add_argument("file", help="a .md file produced by diorthosis build")

  rt = sub.add_parser(
    "roundtrip", help="check that md-ce and TEI carry the same content")
  rt.add_argument("md", help="a .md file produced by diorthosis build")
  rt.add_argument("tei", help="the matching .tei.xml file")

  r = sub.add_parser(
    "review",
    help="generate the human-review page: image snippet per apparatus "
         "entry, parse side by side, exportable overrides.json")
  r.add_argument("pdf", help="born-digital PDF (the review needs the page image)")
  r.add_argument("--pages", default=None, help="0-based page spec: 290-320 or 1,5,9")
  r.add_argument("-o", "--out", required=True, help="output directory")
  r.add_argument("--conspectus-page", type=int, default=None)
  r.add_argument("--text-lang", choices=("grc", "la"), default="grc")
  r.add_argument("--overrides", default=None, metavar="JSON",
                 help="existing overrides to apply before review "
                      "(reviewed entries show as such)")

  args = ap.parse_args(argv)

  if args.cmd == "validate":
    from .mdce_validate import validate_file

    violations = validate_file(args.file)
    for x in violations:
      print(f"{args.file}: {x}")
    if violations:
      print(f"{len(violations)} violation(s)", file=sys.stderr)
      return 1
    print("OK: md-ce/0.2 invariants hold")
    return 0

  if args.cmd == "roundtrip":
    from .roundtrip import check_roundtrip

    violations = check_roundtrip(args.md, args.tei)
    for violation in violations:
      print(f"{args.md} <> {args.tei}: {violation}")
    if violations:
      print(f"{len(violations)} violation(s)", file=sys.stderr)
      return 1
    print("OK: md-ce and TEI carry the same content")
    return 0

  if args.cmd == "inspect":
    # same registry bootstrap as build: without it, anchoring cannot
    # discriminate duplicate markers by lemma and inspect would show a
    # DIFFERENT structure than the one build emits
    registry, note = bootstrap_registry(args.pdf, args.conspectus_page)
    if note:
      print(note, file=sys.stderr)
    doc = ingest_pdf(args.pdf, pages=[args.page])
    for page in doc.pages:
      stats = anchor_page(page, registry)
      print(to_markdown(doc))
      print(f"[anchoring: {stats['anchored']}/{stats['entries']} entries anchored]",
            file=sys.stderr)
    return 0

  if args.cmd == "review":
    try:
      import pypdfium2  # noqa: F401
    except ImportError:
      print("review needs the optional extra: pip install 'diorthosis[review]'",
            file=sys.stderr)
      return 2
    from .review import render_review

    registry, note = bootstrap_registry(args.pdf, args.conspectus_page)
    if note:
      print(note)
    doc = ingest_pdf(args.pdf, _parse_pages(args.pages),
                     text_lang=args.text_lang)
    for page in doc.pages:
      anchor_page(page, registry)
    if args.overrides:
      from .overrides import apply_overrides, load_overrides

      apply_overrides(doc, load_overrides(args.overrides))
    stats = render_review(doc, args.pdf, Path(args.out), registry)
    print(f"wrote {Path(args.out) / 'index.html'}")
    print(f"review: {stats['entries']} entries — {stats['parsed']} parsed, "
          f"{stats['refused']} refused, {stats['unanchored']} unanchored, "
          f"{stats['reviewed']} reviewed; {stats['snippets']} snippets")
    return 0

  if sum(map(bool, (args.pdf, args.alto, args.hocr, args.page_xml))) != 1:
    ap.error("build needs exactly one source: a PDF, or --alto/--hocr/--page-xml files")
  if not args.pdf:
    # refuse silently ignored flags: both options only make sense for a PDF
    if args.pages is not None:
      ap.error("--pages selects pages of a PDF; with --alto/--hocr/--page-xml, "
               "pass only the page files you want built")
    if args.conspectus_page is not None:
      ap.error("--conspectus-page points into a PDF; OCR page files carry no "
               "front matter to search")
  if args.alto:
    doc = ingest_alto(args.alto)
  elif args.hocr:
    doc = ingest_hocr(args.hocr)
  elif args.page_xml:
    doc = ingest_pagexml(args.page_xml)
  else:
    doc = ingest_pdf(args.pdf, _parse_pages(args.pages), text_lang=args.text_lang)

  if args.pdf:
    registry, note = bootstrap_registry(args.pdf, args.conspectus_page)
    if note:
      print(note)
    else:
      where = (f"page {args.conspectus_page}" if args.conspectus_page is not None
               else "the front matter")
      print(f"[!] no conspectus siglorum found in {where}: witnesses will be "
            "missing from the TEI and manuscript sigla cannot be attributed",
            file=sys.stderr)
  else:
    registry = with_builtin_editors(Registry())

  if getattr(args, "sigla", None):
    for siglum in args.sigla.split(","):
      siglum = siglum.strip()
      if siglum and siglum not in registry.witnesses:
        registry.witnesses[siglum] = "user-supplied siglum (--sigla)"

  if not doc.pages:
    raise ValueError("no pages ingested: the requested pages do not exist "
                     "in this document")
  totals = {"entries": 0, "anchored": 0, "unanchored": 0, "ambiguous": 0}
  for page in doc.pages:
    st = anchor_page(page, registry)
    for k in totals:
      totals[k] += st.get(k, 0)

  if getattr(args, "overrides", None):
    from .overrides import apply_overrides, load_overrides

    ov_stats = apply_overrides(doc, load_overrides(args.overrides))
    print(f"overrides: {ov_stats['applied']} parses replaced, "
          f"{ov_stats['verbatim']} forced verbatim")
    if ov_stats["unmatched"]:
      print(f"[!] {len(ov_stats['unmatched'])} override key(s) matched no "
            f"entry (stale file?): {', '.join(ov_stats['unmatched'][:8])}",
            file=sys.stderr)

  outdir = Path(args.out)
  outdir.mkdir(parents=True, exist_ok=True)
  stem = Path(doc.source_name).stem[:60] or "edition"
  witness_path = outdir / f"{stem}.witnesses.json"
  (outdir / f"{stem}.tei.xml").write_text(
    to_tei(doc, title=args.title, registry=registry), encoding="utf-8")
  (outdir / f"{stem}.md").write_text(
    to_markdown(doc, title=args.title, tei_name=f"{stem}.tei.xml"), encoding="utf-8")
  witness_path.write_text(
    json.dumps(
      witness_table(registry, _used_witness_sigla(doc, registry)),
      indent=1,
      ensure_ascii=False,
    ),
    encoding="utf-8",
  )
  print(f"wrote {outdir / (stem + '.tei.xml')}")
  print(f"wrote {outdir / (stem + '.md')}")
  print(f"wrote {witness_path}")
  msg = f"apparatus anchoring: {totals['anchored']}/{totals['entries']} entries anchored"
  if totals["unanchored"]:
    msg += f", {totals['unanchored']} unanchored"
  if totals["ambiguous"]:
    msg += f", {totals['ambiguous']} ambiguous (duplicate markers, unresolved)"
  print(msg)
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
  except Exception as exc:  # noqa: BLE001 — user-facing CLI: never a traceback
    print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 2


if __name__ == "__main__":
  raise SystemExit(run())
