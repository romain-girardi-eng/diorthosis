"""ALTO-XML ingestion — the OCR-agnostic path.

diorthosis never calls an OCR engine. It consumes the standard output formats
instead: Kraken, eScriptorium, Tesseract and Transkribus all export ALTO (or
hOCR/PAGE, see the sibling adapters). Whatever produced the file, its text is
**generative** — a recognition model's guess, not a decoding of a character
stream — and every block is permanently marked so.

Layer classification is not attempted here in P1: ALTO gives lines and word
confidences but no typographic registers comparable to a born-digital page.
Blocks arrive as ``UNKNOWN`` for a human or a later pass to label; honesty
over guesswork.

Two things this adapter refuses before reading a single ``String``: a file it
cannot parse (see :mod:`.errors` — a dependency's ``ParseError`` is not a
diagnosis), and a well-formed XML file that is simply not ALTO. The second
matters because the generic advice for a build that yielded nothing is "run an
OCR engine and pass its output with --alto/--hocr/--page-xml" — which, to
someone who has just done exactly that with the wrong file, says nothing.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from ..model import Block, Document, Layer, Page, Source
from .errors import SourceRefused, parse_xml


def _local(tag: str) -> str:
  return tag.rsplit("}", 1)[-1]


def ingest_alto(paths: list[str | Path]) -> Document:
  """Ingest one ALTO file per page, in order."""
  doc = Document(source_name=Path(paths[0]).stem if paths else "alto", ingest="alto")
  for i, p in enumerate(paths):
    root = parse_xml(p, "ALTO")
    if _local(root.tag) != "alto":
      raise SourceRefused(
        f"{p}: not ALTO — root is <{_local(root.tag)}>, expected <alto>")
    page = Page(index=i, printed_page=None)
    for tb in root.iter():
      if _local(tb.tag) != "TextBlock":
        continue
      lines: list[str] = []
      confs: list[float] = []
      for ln in tb:
        if _local(ln.tag) != "TextLine":
          continue
        words: list[str] = []
        for s in ln:
          if _local(s.tag) == "String":
            words.append(s.get("CONTENT", ""))
            wc = s.get("WC")
            if wc:
              with contextlib.suppress(ValueError):
                confs.append(float(wc))
          elif _local(s.tag) == "SP":
            words.append(" ")
        if words:
          lines.append("".join(words).strip())
      if not lines:
        continue
      page.blocks.append(Block(
        layer=Layer.UNKNOWN,
        text="\n".join(lines),
        source=Source.OCR,
        generative=True,
        confidence=(sum(confs) / len(confs)) if confs else 0.0,
        evidence="ALTO TextBlock; OCR output — text is generated, not decoded",
      ))
    doc.pages.append(page)
  return doc
