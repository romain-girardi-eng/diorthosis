"""The AI-ready Markdown view — a deterministic rendering of the model.

This is a VIEW, never a second truth: it is derived from the same document
model as the TEI, block for block, and it follows a tiny versioned contract
(``md-ce``) that retrieval pipelines can rely on:

- every section is a ``###`` header naming its layer, with bracketed
  provenance metadata (``[source=… generative=… confidence=…]``);
- a chunker that splits on headers can NEVER mix apparatus into text;
- apparatus markers appear as ``⟦n⟧`` in the text and at the start of the
  matching apparatus entry — the link is visible to humans and trivially
  parseable by machines;
- pages are introduced by their **printed folio** (the citable number),
  with the file index in parentheses;
- block order mirrors the page; nothing is reordered.
"""

from __future__ import annotations

from . import __version__
from .anchor import anchor_block_text
from .model import Document, Layer

MD_CE_VERSION = "0.1"

_LAYER_TITLES = {
  Layer.TEXT: "text",
  Layer.APPARATUS: "apparatus",
  Layer.TRANSLATION: "translation",
  Layer.NOTES: "notes",
  Layer.HEADING: "heading",
  Layer.RUNNING_HEAD: "running-head",
  Layer.PAGE_NUMBER: "page-number",
  Layer.UNKNOWN: "unclassified",
}


def to_markdown(doc: Document, title: str | None = None) -> str:
  out: list[str] = []
  out.append(f"# {title or doc.source_name}")
  out.append("")
  out.append(
    f"<!-- md-ce/{MD_CE_VERSION} · diorthosis {__version__} · ingest: {doc.ingest} · "
    "layers are fenced by ### headers; apparatus markers are ⟦n⟧; "
    "generative=true means OCR output, not decoded text -->"
  )
  for page in doc.pages:
    out.append("")
    printed = page.printed_page or "–"
    out.append(f"## page {printed} (file index {page.index})")
    for block in page.blocks:
      if block.layer in (Layer.RUNNING_HEAD, Layer.PAGE_NUMBER):
        continue  # page furniture: kept in TEI, noise for retrieval
      meta = (
        f"[source={block.source.value} generative={str(block.generative).lower()} "
        f"confidence={block.confidence:.2f}]"
      )
      out.append("")
      out.append(f"### {_LAYER_TITLES[block.layer]} {meta}")
      if block.inline_refs:
        out.append(f"*refs: {', '.join(block.inline_refs)}*")
      out.append("")
      if block.layer is Layer.APPARATUS and block.entries:
        for e in block.entries:
          mark = f"⟦{e.anchor.value}⟧ " if e.anchor is not None else ""
          out.append(f"{mark}{e.raw}")
      elif block.layer is Layer.TEXT:
        out.append(anchor_block_text(block))
      else:
        out.append(block.text)
  return "\n".join(out).rstrip() + "\n"
