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
"""

from __future__ import annotations

import contextlib
import xml.etree.ElementTree as ET
from pathlib import Path

from ..model import Block, Document, Layer, Page, Source


def _local(tag: str) -> str:
  return tag.rsplit("}", 1)[-1]


def ingest_alto(paths: list[str | Path]) -> Document:
  """Ingest one ALTO file per page, in order."""
  doc = Document(source_name=Path(paths[0]).stem if paths else "alto", ingest="alto")
  for i, p in enumerate(paths):
    tree = ET.parse(str(p))
    root = tree.getroot()
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
