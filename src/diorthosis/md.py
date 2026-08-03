"""The AI-ready Markdown view — md-ce/0.2, a normative, executable format.

This is a VIEW, never a second truth: derived from the same document model
as the TEI, block for block. The full grammar and the twelve invariants live
in SPEC.md at the repository root; the ones that shape this module:

- **I1** any body line that could impersonate structure (``#…``, the meta
  comment) is escaped with a backslash and counted in the header;
- **I3** markers are page-scoped ``⟦folio:n⟧``; an unresolved anchor renders
  ``⟦folio:n?⟧`` and never pretends to link;
- **I4** the marker delimiters may not occur in source text — if they do,
  emission REFUSES rather than produce an ambiguous file;
- **I6** every section header carries the block's 0-based ordinal within its
  page, counting furniture, so (folio, layer, block) is a stable address;
- **I9** lossiness is declared: page furniture, the conspectus and the parsed
  apparatus structure live in the TEI named by the header, nowhere else;
- **I11** the header's coverage numbers are recomputable from the file.
"""

from __future__ import annotations

import re

from . import __version__
from .anchor import find_markers
from .model import Document, Layer

MD_CE_VERSION = "0.2"

_LAYER_TITLES = {
  Layer.TEXT: "text",
  Layer.APPARATUS: "apparatus",
  Layer.TRANSLATION: "translation",
  Layer.NOTES: "notes",
  Layer.HEADING: "heading",
  Layer.UNKNOWN: "unclassified",
}
_FURNITURE = (Layer.RUNNING_HEAD, Layer.PAGE_NUMBER)
_STRUCTURAL = re.compile(r"^(#{1,6} |<!-- md-ce)")


class MarkerDelimiterError(ValueError):
  """Source text contains ⟦ or ⟧ (I4): the file would be ambiguous."""


def _escape_body(text: str, counter: list[int]) -> str:
  out: list[str] = []
  for line in text.split("\n"):
    if _STRUCTURAL.match(line):
      counter[0] += 1
      line = "\\" + line
    out.append(line)
  return "\n".join(out)


def _marker(folio: str, n: str, resolved: bool) -> str:
  return f"⟦{folio}:{n}⟧" if resolved else f"⟦{folio}:{n}?⟧"


def to_markdown(doc: Document, title: str | None = None,
                tei_name: str = "") -> str:
  pages_out: list[str] = []
  escaped = [0]
  generative_blocks = 0
  anchored_total = 0
  entries_total = 0
  first_index = doc.pages[0].index if doc.pages else 0
  last_index = doc.pages[-1].index if doc.pages else 0

  for page in doc.pages:
    folio = page.printed_page or "–"
    body_blocks = [b for b in page.blocks if b.layer not in _FURNITURE]
    n_markers = sum(
      len(find_markers(b.text)) for b in page.blocks
      if b.layer in (Layer.TEXT, Layer.HEADING)
    )
    entries = [e for b in body_blocks if b.layer is Layer.APPARATUS
               for e in (b.entries or [])]
    unresolved = sum(
      1 for e in entries
      if e.anchor is None or e.anchor.block_index is None
    )
    entries_total += len(entries)
    anchored_total += len(entries) - unresolved

    lines: list[str] = []
    lines.append("")
    lines.append(
      f"## page {folio} (file index {page.index})"
      f" [markers={n_markers} entries={len(entries)} unresolved={unresolved}]"
    )
    for bi, block in enumerate(page.blocks):
      if block.layer in _FURNITURE:
        continue
      if "⟦" in block.text or "⟧" in block.text:
        raise MarkerDelimiterError(
          f"page {page.index}: source text contains the marker delimiter "
          "⟦/⟧ — refusing to emit an ambiguous md-ce file (I4)"
        )
      if block.generative:
        generative_blocks += 1
      meta = (
        f"[source={block.source.value} generative={str(block.generative).lower()} "
        f"confidence={block.confidence:.2f} block={bi}]"
      )
      lines.append("")
      lines.append(f"### {_LAYER_TITLES[block.layer]} {meta}")
      if block.inline_refs:
        lines.append(f"*refs: {', '.join(block.inline_refs)}*")
      lines.append("")
      if block.layer is Layer.APPARATUS and block.entries:
        for e in block.entries:
          if e.anchor is not None:
            resolved = e.anchor.block_index is not None
            prefix = _marker(folio, e.anchor.value, resolved) + " "
          else:
            prefix = ""
          lines.append(prefix + _escape_body(e.raw, escaped))
      elif block.layer in (Layer.TEXT, Layer.HEADING):
        text = block.text
        # Rewrite markers from the page's RESOLVED anchors — the single
        # source of truth. Re-scanning find_markers here (the pre-v0.2.1
        # behaviour) saw only glued markers and missed lemma-confirmed
        # detached ones, so the apparatus showed a resolved ⟦f:n⟧ with no
        # counterpart in the text: a real I3 violation. Digits without a
        # resolved entry stay verbatim (I3: an unresolved entry has ZERO
        # ⟦f:n⟧ in the text).
        spans = sorted(
          (e.anchor.digit_start, e.anchor.digit_end, e.anchor.value)
          for e in entries
          if e.anchor is not None and e.anchor.block_index == bi
          and e.anchor.digit_start is not None and e.anchor.digit_end is not None
        )
        pos = 0
        parts: list[str] = []
        for ds, de, n in spans:
          if ds < pos:
            continue
          parts.append(text[pos:ds])
          parts.append(_marker(folio, n, True))
          pos = de
        parts.append(text[pos:])
        lines.append(_escape_body("".join(parts), escaped))
      else:
        lines.append(_escape_body(block.text, escaped))
    pages_out.append("\n".join(lines))

  header = f"# {title or doc.source_name}"
  meta = (
    f"<!-- md-ce/{MD_CE_VERSION} · diorthosis {__version__} · "
    f"ingest: {doc.ingest} · pages: {first_index}-{last_index} · "
    f"anchored: {anchored_total}/{entries_total} · "
    f"generative-blocks: {generative_blocks} · "
    f"escaped-lines: {escaped[0]} · tei: {tei_name} -->"
  )
  return "\n".join([header, "", meta, *pages_out]).rstrip() + "\n"
