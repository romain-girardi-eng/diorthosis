"""Command-line interface.

Usage::

  diorthosis build edition.pdf -o out/            # born-digital PDF
  diorthosis build --alto p1.xml p2.xml -o out/   # any OCR engine's ALTO
  diorthosis build edition.pdf --pages 290-320 -o out/
  diorthosis inspect edition.pdf --page 300
  diorthosis validate out/edition.md              # md-ce invariants
  diorthosis roundtrip out/edition.md out/edition.tei.xml

Exit codes are part of the contract — a tool that reports success for a
build that produced nothing is worse than a tool that fails::

  0  success
  1  refused: the command ran and diorthosis does not certify its result
     (a degenerate build, md-ce that `diorthosis validate` rejects,
     invariant violations, a source too ambiguous to emit)
  2  user-actionable input error (bad flags, missing file, empty page set)
  3  internal fault — a diorthosis defect, not an input problem
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from .anchor import anchor_page
from .conspectus import Registry, bootstrap_registry, with_builtin_editors
from .ingest import (
  SourceRefused,
  ingest_alto,
  ingest_hocr,
  ingest_pagexml,
  ingest_pdf,
)
from .md import Coverage, MarkerDelimiterError, coverage, to_markdown
from .model import Document, Layer
from .tei import resolve_parsed, to_tei
from .witnesses import witness_table

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_INPUT = 2
EXIT_INTERNAL = 3

_EXIT_CODES = """exit codes:
  0  success
  1  refused: diorthosis does not certify the result it produced
  2  user-actionable input error
  3  internal fault (a diorthosis defect)
"""

_FURNITURE = (Layer.RUNNING_HEAD, Layer.PAGE_NUMBER)


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


def _output_dir(raw: str) -> Path:
  """Check ``-o`` as a directory path, BEFORE the build does its work.

  ``-o`` aimed at an existing file used to raise out of ``mkdir()`` and reach
  the generic handler, so a plain typo was reported as "a diorthosis defect …
  please report it" at exit 3. Choosing where the output goes is the user's
  job, and getting it wrong is a `2`.
  """
  out = Path(raw)
  if out.exists() and not out.is_dir():
    raise ValueError(
      f"-o {out}: exists and is not a directory — build writes several files "
      f"(.tei.xml, .md, .witnesses.json), so -o takes a directory path")
  return out


def _make_output_dir(out: Path) -> Path:
  """Create the output directory, or say why the path cannot be used."""
  try:
    out.mkdir(parents=True, exist_ok=True)
  except OSError as exc:
    raise ValueError(f"-o {out}: cannot create the output directory "
                     f"({exc.strerror or exc})") from None
  return out


def degeneracies(doc: Document, cov: Coverage) -> list[str]:
  """Ways a build can succeed mechanically while producing nothing usable.

  The documented one-liner on this project's own flagship edition used to
  exit 0 after emitting zero text blocks and zero apparatus entries, because
  a Latin-script constituted text is layered as a translation unless
  ``--text-lang la`` says otherwise. Every finding below therefore names the
  option that would have avoided it: an honest failure has to be actionable.
  """
  bodies = [b for p in doc.pages for b in p.blocks if b.layer not in _FURNITURE]
  if not any(b.text.strip() for b in bodies):
    return [
      f"the {len(doc.pages)} selected page(s) carry no decodable text at all. "
      "If this is a scanned edition, diorthosis never calls an OCR engine: "
      "run one and pass its output with --alto/--hocr/--page-xml."
    ]

  findings: list[str] = []
  histogram = Counter(b.layer.value for b in bodies)
  shape = ", ".join(f"{n} {layer}" for layer, n in sorted(histogram.items()))
  # OCR adapters deliberately assign no layer, so a layer census is
  # meaningless there; only a LAYERED document can be missing its text
  layered = any(b.layer is not Layer.UNKNOWN for b in bodies)
  if layered and not histogram.get(Layer.TEXT.value):
    findings.append(
      f"no constituted-text block across {len(doc.pages)} page(s): the "
      f"layerer classified {shape} and nothing as text. A Latin-script "
      "constituted text is read as a translation unless --text-lang la is "
      "given, and a page range covering front matter or a facing translation "
      "produces the same shape — select the edition's own pages with --pages."
    )
  if histogram.get(Layer.APPARATUS.value) and cov.entries == 0:
    findings.append(
      f"{histogram[Layer.APPARATUS.value]} apparatus band(s) were detected but "
      "no entry was split from any of them: the apparatus is present in the "
      "TEI as verbatim prose only, and nothing is anchored."
    )
  return findings


def _build_parser() -> argparse.ArgumentParser:
  ap = argparse.ArgumentParser(
    prog="diorthosis",
    description="Compile published critical editions into TEI P5 + AI-ready Markdown",
    epilog=_EXIT_CODES,
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )
  sub = ap.add_subparsers(dest="cmd", required=True)

  b = sub.add_parser("build", help="compile a source into TEI + Markdown",
                     epilog=_EXIT_CODES,
                     formatter_class=argparse.RawDescriptionHelpFormatter)
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
  b.add_argument("--ignore-self-check", action="store_true",
                 help="write the outputs and exit 0 even when the build's own "
                      "self-check refuses them (degenerate structure, or md-ce "
                      "that 'diorthosis validate' rejects). The findings are "
                      "still printed: use this only when you know why the "
                      "output looks like that")

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
  return ap


def main(argv: list[str] | None = None) -> int:
  ap = _build_parser()
  args = ap.parse_args(argv)

  if args.cmd == "validate":
    from .mdce_validate import MD_CE_SUPPORTED, validate_file

    violations = validate_file(args.file)
    for x in violations:
      print(f"{args.file}: {x}")
    if violations:
      print(f"{len(violations)} violation(s)", file=sys.stderr)
      return EXIT_REFUSED
    print(f"OK: md-ce/{MD_CE_SUPPORTED} invariants hold")
    return EXIT_OK

  if args.cmd == "roundtrip":
    from .roundtrip import check_roundtrip

    violations = check_roundtrip(args.md, args.tei)
    for violation in violations:
      print(f"{args.md} <> {args.tei}: {violation}")
    if violations:
      print(f"{len(violations)} violation(s)", file=sys.stderr)
      return EXIT_REFUSED
    print("OK: md-ce and TEI carry the same content")
    return EXIT_OK

  if args.cmd == "inspect":
    # ingested FIRST so that an unreadable PDF is refused by the adapter that
    # owns pdfminer, in its words and at exit 2 — the conspectus search reads
    # the same file and would meet the library's exception first
    doc = ingest_pdf(args.pdf, pages=[args.page])
    # same registry bootstrap as build: without it, anchoring cannot
    # discriminate duplicate markers by lemma and inspect would show a
    # DIFFERENT structure than the one build emits
    registry, note = bootstrap_registry(args.pdf, args.conspectus_page)
    if note:
      print(note, file=sys.stderr)
    for page in doc.pages:
      anchor_page(page, registry)
    cov = coverage(doc, registry)
    print(to_markdown(doc, cov=cov))
    for line in cov.lines:
      print(line, file=sys.stderr)
    return EXIT_OK

  if args.cmd == "review":
    try:
      import pypdfium2  # noqa: F401
    except ImportError:
      print("review needs the optional extra: pip install 'diorthosis[review]'",
            file=sys.stderr)
      return EXIT_INPUT
    from .review import render_review

    outdir = _output_dir(args.out)
    doc = ingest_pdf(args.pdf, _parse_pages(args.pages),
                     text_lang=args.text_lang)
    registry, note = bootstrap_registry(args.pdf, args.conspectus_page)
    if note:
      print(note)
    for page in doc.pages:
      anchor_page(page, registry)
    if args.overrides:
      from .overrides import apply_overrides, load_overrides

      apply_overrides(doc, load_overrides(args.overrides))
    stats = render_review(doc, args.pdf, outdir, registry)
    print(f"wrote {outdir / 'index.html'}")
    print(f"review: {stats['entries']} entries — {stats['parsed']} parsed, "
          f"{stats['refused']} refused, {stats['unanchored']} unanchored, "
          f"{stats['reviewed']} reviewed; {stats['snippets']} snippets")
    return EXIT_OK

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
  # checked before the source is read: an unusable -o is a typo, and learning
  # about it after several minutes of ingestion helps nobody
  outdir = _output_dir(args.out)
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
    added = []
    for siglum in args.sigla.split(","):
      siglum = siglum.strip()
      if siglum and siglum not in registry.witnesses:
        registry.witnesses[siglum] = "user-supplied siglum (--sigla)"
        added.append(siglum)
    # the conspectus line above reports what the EDITION declared; without
    # this, supplying seven sigla on an edition that prints no conspectus
    # still reads "0 witnesses" and the user cannot tell the flag took
    print(f"--sigla: {len(added)} witness(es) supplied by hand "
          f"({', '.join(added)}); registry now holds "
          f"{len(registry.witnesses)}")

  if not doc.pages:
    raise ValueError("no pages ingested: the requested pages do not exist "
                     "in this document")
  for page in doc.pages:
    anchor_page(page, registry)

  if getattr(args, "overrides", None):
    from .overrides import apply_overrides, load_overrides

    ov_stats = apply_overrides(doc, load_overrides(args.overrides))
    print(f"overrides: {ov_stats['applied']} parses replaced, "
          f"{ov_stats['verbatim']} forced verbatim")
    if ov_stats["unmatched"]:
      print(f"[!] {len(ov_stats['unmatched'])} override key(s) matched no "
            f"entry (stale file?): {', '.join(ov_stats['unmatched'][:8])}",
            file=sys.stderr)

  # measured ONCE: the console, the md-ce meta and every md-ce page line
  # render this same object, so a build can no longer announce two scores
  cov = coverage(doc, registry)

  _make_output_dir(outdir)
  stem = Path(doc.source_name).stem[:60] or "edition"
  md_path = outdir / f"{stem}.md"
  witness_path = outdir / f"{stem}.witnesses.json"
  (outdir / f"{stem}.tei.xml").write_text(
    to_tei(doc, title=args.title, registry=registry), encoding="utf-8")
  md_path.write_text(
    to_markdown(doc, title=args.title, tei_name=f"{stem}.tei.xml", cov=cov),
    encoding="utf-8")
  witness_path.write_text(
    json.dumps(
      witness_table(registry, _used_witness_sigla(doc, registry)),
      indent=1,
      ensure_ascii=False,
    ),
    encoding="utf-8",
  )
  print(f"wrote {outdir / (stem + '.tei.xml')}")
  print(f"wrote {md_path}")
  print(f"wrote {witness_path}")
  for line in cov.lines:
    print(line)
  if doc.any_generative:
    print("[!] this document contains OCR-generated blocks (marked generative) — "
          "their text is a recognition model's output, not a decoded stream",
          file=sys.stderr)

  return self_check(doc, cov, md_path, ignore=args.ignore_self_check)


def self_check(doc: Document, cov: Coverage, md_path: Path,
               ignore: bool) -> int:
  """Refuse to call a build a success until its own outputs pass.

  `diorthosis validate` is the executable spec; a build that hands a stranger
  an artifact its own validator rejects has reported success for a failure.
  """
  from .mdce_validate import validate_file

  findings = degeneracies(doc, cov)
  violations = validate_file(md_path)
  if not findings and not violations:
    return EXIT_OK

  print("self-check FAILED: this build is not certified", file=sys.stderr)
  for finding in findings:
    print(f"  degenerate: {finding}", file=sys.stderr)
  if violations:
    print(f"  md-ce: {len(violations)} violation(s) of SPEC.md — the file "
          f"'{md_path}' is not a valid md-ce document:", file=sys.stderr)
    for violation in violations[:5]:
      print(f"    {violation}", file=sys.stderr)
    if len(violations) > 5:
      print(f"    … {len(violations) - 5} more; run "
            f"'diorthosis validate {md_path}' for the full list",
            file=sys.stderr)
  if ignore:
    print("[!] --ignore-self-check: exiting 0 with an uncertified artifact",
          file=sys.stderr)
    return EXIT_OK
  print("the files above were written but are NOT certified; fix the command "
        "line, or pass --ignore-self-check to accept them as they are",
        file=sys.stderr)
  return EXIT_REFUSED


def run() -> int:
  try:
    return main()
  except MarkerDelimiterError as exc:
    # SPEC I4: an ambiguous file must never be emitted. Not an input error —
    # the source is legitimate, the format simply refuses to represent it.
    print(f"refused: {exc}", file=sys.stderr)
    return EXIT_REFUSED
  except SourceRefused as exc:
    # an ingest adapter could not read the file it was given, and says so in
    # diorthosis's own words, naming it. The user chose the file: exit 2,
    # never 3 — this is not a defect to report. (SourceRefused is a
    # ValueError, so the clause below would land it here anyway; it is
    # written out because the mapping is the contract, not a side effect.)
    print(f"error: {exc}", file=sys.stderr)
    return EXIT_INPUT
  except (ValueError, KeyError) as exc:
    print(f"error: {exc}", file=sys.stderr)
    return EXIT_INPUT
  except FileNotFoundError as exc:
    print(f"error: file not found: {getattr(exc, 'filename', exc)}", file=sys.stderr)
    return EXIT_INPUT
  except Exception as exc:  # noqa: BLE001 — user-facing CLI: never a traceback
    print(f"internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
    print("this is a diorthosis defect, not an input problem; please report it "
          "with the command line that produced it", file=sys.stderr)
    return EXIT_INTERNAL


if __name__ == "__main__":
  raise SystemExit(run())
