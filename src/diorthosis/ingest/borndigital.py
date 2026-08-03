"""Born-digital PDF ingestion, built on regreek.

regreek does the character-level work (legacy Greek font decoding with its
zero-fabrication contract) and the page-level work (layer separation,
printed-folio extraction). This adapter maps its output onto the diorthosis
model; nothing here is generative.
"""

from __future__ import annotations

from pathlib import Path

from regreek.layers import layer_pages

from ..model import Block, Document, Layer, Page, Source

_LAYER_MAP = {
  "greek_text": Layer.TEXT,
  "translation": Layer.TRANSLATION,
  "apparatus": Layer.APPARATUS,
  "notes": Layer.NOTES,
  "heading": Layer.HEADING,
  "running_head": Layer.RUNNING_HEAD,
  "page_number": Layer.PAGE_NUMBER,
}


def ingest_pdf(pdf_path: str | Path, pages: list[int] | None = None) -> Document:
  doc = Document(source_name=Path(pdf_path).name, ingest="borndigital")
  for lp in layer_pages(pdf_path, pages=pages):
    page = Page(index=lp.page, printed_page=lp.printed_page)
    for band in lp.bands:
      page.blocks.append(Block(
        layer=_LAYER_MAP.get(band.layer, Layer.UNKNOWN),
        text=band.text,
        source=Source.BORN_DIGITAL,
        generative=False,
        confidence=band.confidence,
        evidence=band.evidence,
        inline_refs=list(band.inline_refs),
      ))
    doc.pages.append(page)
  return doc
