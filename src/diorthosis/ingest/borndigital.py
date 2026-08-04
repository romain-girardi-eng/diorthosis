"""Born-digital PDF ingestion, built on regreek.

regreek does the character-level work (legacy Greek font decoding with its
zero-fabrication contract) and the page-level work (layer separation,
printed-folio extraction). This adapter maps its output onto the diorthosis
model; nothing here is generative.
"""

from __future__ import annotations

import re
from collections import Counter
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


def _looks_apparatus(text: str) -> bool:
  """A line carrying an apparatus separator is apparatus, whatever its
  vertical position — never a colophon."""
  return " : " in text or " | " in text or "∥" in text or "]" in text


def _foot_colophon_split(lines: list) -> tuple[list, list]:
  """Trailing line(s) of a foot band separated from its body by a vertical
  gap FAR larger than a line's own height are a printer's or publisher's
  footer (license line, colophon), not apparatus — split them off. A
  sparse final apparatus entry can also sit low, so the split needs both
  the extreme gap and non-apparatus content."""
  if len(lines) < 2:
    return lines, []
  heights = sorted(ln.y1 - ln.y0 for ln in lines)
  h = heights[len(heights) // 2]
  if h <= 0:
    return lines, []
  ys = [ln.y0 for ln in lines]
  gaps = [ys[i] - ys[i + 1] for i in range(len(ys) - 1)]
  for cut in (len(lines) - 2, len(lines) - 1):
    if cut >= 1 and gaps[cut - 1] >= 5.0 * h and not any(
        _looks_apparatus(ln.decoded or ln.text) for ln in lines[cut:]):
      return lines[:cut], lines[cut:]
  return lines, []


def ingest_pdf(pdf_path: str | Path, pages: list[int] | None = None,
               text_lang: str = "grc") -> Document:
  doc = Document(source_name=Path(pdf_path).name, ingest="borndigital")
  layered = layer_pages(pdf_path, pages=pages)
  # a printer's/license footer repeats VERBATIM at the foot of many pages
  # (the mirror of a running head); the geometric split alone cannot
  # catch it under a deep apparatus, where the gap shrinks to normal pitch
  tails: Counter[str] = Counter()
  for lp in layered:
    for band in lp.bands:
      if band.layer in ("notes", "apparatus"):
        content = [ln for ln in band.lines
                   if (ln.decoded or ln.text).strip()]
        if content:
          tails[" ".join(
            (content[-1].decoded or content[-1].text).split())] += 1
  # a repeated SHORT tail is a wrapped apparatus fragment ("om. RP"
  # falling alone on the last line of many pages), not a footer — a
  # printer's footer is a sentence
  repeated = {t for t, n in tails.items()
              if n >= 3 and len(t) >= 25 and not _looks_apparatus(t)}
  for lp in layered:
    page = Page(index=lp.page, printed_page=lp.printed_page)
    for band in lp.bands:
      layer = _LAYER_MAP.get(band.layer, Layer.UNKNOWN)
      if text_lang == "la" and band.layer in _LATIN_REMAP:
        layer = _LATIN_REMAP[band.layer]
      body, colophon = band.lines, []
      if band.layer in ("notes", "apparatus"):
        content = [ln for ln in band.lines
                   if (ln.decoded or ln.text).strip()]
        while content and " ".join(
            (content[-1].decoded or content[-1].text).split()) in repeated:
          colophon.insert(0, content.pop())
        body, geom = _foot_colophon_split(content)
        colophon = geom + colophon
      page.blocks.append(Block(
        layer=layer,
        text="\n".join(ln.decoded or ln.text for ln in body),
        source=Source.BORN_DIGITAL,
        generative=False,
        confidence=band.confidence,
        evidence=band.evidence
                 + (f"; remapped for text-lang={text_lang}"
                    if text_lang == "la" and band.layer in _LATIN_REMAP else ""),
        inline_refs=list(band.inline_refs),
      ))
      if colophon:
        page.blocks.append(Block(
          layer=Layer.NOTES,
          text="\n".join(ln.decoded or ln.text for ln in colophon),
          source=Source.BORN_DIGITAL,
          generative=False,
          confidence=band.confidence,
          evidence="printer's footer split from the foot band "
                   "(vertical gap over 2.5x the band pitch)",
        ))
    _recover_folio(page, doc)
    _reclassify_degenerate(page)
    doc.pages.append(page)
  return doc


def _recover_folio(page: Page, doc: Document) -> None:
  """On a degenerate page the printed folio can end up GLUED to the tail
  of a content band ("… Px 61") and the layerer finds no page number.
  Folio continuity disambiguates: the number expected after the previous
  printed page, sitting alone at the end of a line, is the folio — adopt
  it and strip it from the band."""
  if page.printed_page is not None or not doc.pages \
     or not _is_degenerate(page):
    return
  prev = doc.pages[-1].printed_page
  if not (prev and prev.isdigit()):
    return
  want = str(int(prev) + 1)
  for b in page.blocks:
    lines = b.text.split("\n")
    for i, ln in enumerate(lines):
      m = re.search(rf"(?:^|\s){want}\s*$", ln)
      if m:
        lines[i] = ln[: m.start()].rstrip()
        b.text = "\n".join(lines)
        page.printed_page = want
        return


_APP_OPEN = re.compile(r"^\s*\d{1,2}\s+\S[^:]*\s:\s")
_MARKERS = re.compile(r"[a-zà-öø-ÿA-ZΑ-Ωα-ω][0-9]\b")


def _is_degenerate(page: Page) -> bool:
  """One or two lines of constituted text starve the geometric layerer.
  A page with a substantial TEXT block, an apparatus, or a long
  translation is a NORMAL page — never rewritten."""
  if any(b.layer is Layer.APPARATUS for b in page.blocks):
    return False
  if any(b.layer is Layer.TEXT and b.text.count("\n") >= 2
         and not _APP_OPEN.match(" ".join(b.text.split()))
         for b in page.blocks):
    # substantial constituted text that does NOT itself read like a
    # mislabeled apparatus band
    return False
  return not any(
    b.layer is Layer.TRANSLATION and b.text.count("\n") >= 6
    for b in page.blocks)


def _reclassify_degenerate(page: Page) -> None:
  """On a DEGENERATE page the short text reads as a running head and the
  foot band as the page body. The CONTENT disambiguates — an apparatus
  band opens with a marker number and a ``:`` separator; a running head
  never carries multiple superscript markers."""
  if not _is_degenerate(page):
    return
  for b in page.blocks:
    flat = " ".join(b.text.split())
    if b.layer in (Layer.TRANSLATION, Layer.TEXT) and _APP_OPEN.match(flat):
      b.layer = Layer.APPARATUS
      b.evidence += "; reclassified: opens like a marker apparatus band"
    elif b.layer is Layer.RUNNING_HEAD and len(_MARKERS.findall(flat)) >= 2:
      b.layer = Layer.TEXT
      b.evidence += "; reclassified: a running head never carries markers"
