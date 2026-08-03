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

# A LATIN edition's constituted text is Latin-script: regreek (built on the
# Greek/translation opposition) labels it "translation" and its foot band
# "notes". When the user declares --text-lang la, those labels are remapped
# to what they are on a monolingual Latin page.
_LATIN_REMAP = {
  "translation": Layer.TEXT,
  "notes": Layer.APPARATUS,
}


def ingest_pdf(pdf_path: str | Path, pages: list[int] | None = None,
               text_lang: str = "grc") -> Document:
  doc = Document(source_name=Path(pdf_path).name, ingest="borndigital")
  for lp in layer_pages(pdf_path, pages=pages):
    page = Page(index=lp.page, printed_page=lp.printed_page)
    for band in lp.bands:
      layer = _LAYER_MAP.get(band.layer, Layer.UNKNOWN)
      if text_lang == "la" and band.layer in _LATIN_REMAP:
        layer = _LATIN_REMAP[band.layer]
      page.blocks.append(Block(
        layer=layer,
        text=band.text,
        source=Source.BORN_DIGITAL,
        generative=False,
        confidence=band.confidence,
        evidence=band.evidence
                 + (f"; remapped for text-lang={text_lang}"
                    if text_lang == "la" and band.layer in _LATIN_REMAP else ""),
        inline_refs=list(band.inline_refs),
      ))
    doc.pages.append(page)
  return doc
