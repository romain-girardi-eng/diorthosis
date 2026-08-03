"""hOCR ingestion — the OCR-agnostic path, HTML flavour.

diorthosis never calls an OCR engine. It consumes the standard output formats
instead: Tesseract, kraken, OCRopus, Calamari and Transkribus all export hOCR
(or ALTO/PAGE, see the sibling adapters). Whatever produced the file, its text
is **generative** — a recognition model's guess, not a decoding of a character
stream — and every block is permanently marked so.

Three refusals, inherited from the ALTO adapter:

- **No layer classification.** hOCR does define logical classes
  (``ocr_header``, ``ocr_pageno``, ``ocr_caption``…), but engines in practice
  emit only the typesetting ones, and where a logical class *is* declared it
  remains a model's guess about a page whose registers (text / apparatus /
  translation) it has no vocabulary for. Blocks arrive as ``UNKNOWN``; the
  declared classes are copied verbatim into ``evidence`` so nothing is lost.
- **No invented separators.** Word text is read with the whitespace the file
  itself serializes between the word spans — ALTO's rule, where a space
  appears only where ``<SP/>`` appears.
- **No HTML repair beyond parsing.** ``xml.etree`` is not usable here:
  Tesseract's hOCR is well-formed XHTML, but engines that emit HTML5 void
  tags (``<meta charset="utf-8">``) or named entities (``&nbsp;``) make it
  raise ``ParseError``. ``html.parser`` (stdlib) accepts both flavours.

Confidence follows this format's own scale. The spec asks producers to give
``x_wconf`` "values between 0 and 100", so a block whose confidences exceed 1
is read as percentages and normalized; one whose values are all ≤ 1 is read as
already normalized. ``x_confs`` (per-character) is used only as a fallback,
when no ``x_wconf`` exists anywhere in the block. Absent both, the block
reports 0.0 — no confidence claimed, not high confidence.

Unlike ALTO, hOCR carries the citable folio: ``lpageno`` on the ``ocr_page``
title is the number *printed* on the page (``ppageno`` is the physical index
in the scan). It is used verbatim when present.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from ..model import Block, Document, Layer, Page, Source

_PAGE_CLASSES = frozenset({"ocr_page"})
_BLOCK_CLASSES = frozenset({"ocr_carea", "ocrx_block"})
_PAR_CLASSES = frozenset({"ocr_par"})
_LINE_CLASSES = frozenset({"ocr_line", "ocrx_line"})
_WORD_CLASSES = frozenset({"ocrx_word", "ocr_word"})

# Logical classes hOCR may declare on a block. Never acted on (see the module
# docstring); recorded in the block's evidence instead.
_LOGICAL_CLASSES = frozenset({
  "ocr_abstract", "ocr_author", "ocr_blockquote", "ocr_caption", "ocr_chapter",
  "ocr_display", "ocr_footer", "ocr_header", "ocr_pageno", "ocr_part",
  "ocr_section", "ocr_subsection", "ocr_subsubsection", "ocr_title",
})

# HTML void elements: they never open a scope, whether or not the producer
# closed them (``<meta charset="utf-8">`` vs ``<meta ... />``).
_VOID_TAGS = frozenset({
  "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
  "param", "source", "track", "wbr",
})

_WS = re.compile(r"\s+")


@dataclass
class _Node:
  """One element of the hOCR tree, keeping text and children interleaved."""

  tag: str
  classes: frozenset[str]
  props: dict[str, str]
  parts: list[str | _Node] = field(default_factory=list)

  @property
  def children(self) -> list[_Node]:
    return [p for p in self.parts if isinstance(p, _Node)]


class _HocrParser(HTMLParser):
  """Tolerant tree builder: accepts XHTML and HTML5 hOCR alike."""

  def __init__(self) -> None:
    super().__init__(convert_charrefs=True)
    self.root = _Node("", frozenset(), {})
    self._stack: list[_Node] = [self.root]

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    if tag in _VOID_TAGS:
      return
    attrib = {k: (v or "") for k, v in attrs}
    node = _Node(
      tag=tag,
      classes=frozenset(attrib.get("class", "").split()),
      props=_title_props(attrib.get("title")),
    )
    self._stack[-1].parts.append(node)
    self._stack.append(node)

  def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    return  # self-closing: no content to collect, no scope to open

  def handle_endtag(self, tag: str) -> None:
    # Close to the nearest matching open element; ignore a stray end tag
    # rather than unwinding the tree on it.
    for i in range(len(self._stack) - 1, 0, -1):
      if self._stack[i].tag == tag:
        del self._stack[i:]
        return

  def handle_data(self, data: str) -> None:
    self._stack[-1].parts.append(data)


def _title_props(title: str | None) -> dict[str, str]:
  """Parse an hOCR ``title`` attribute: ``"bbox 1 2 3 4; x_wconf 96"``."""
  props: dict[str, str] = {}
  for part in (title or "").split(";"):
    part = part.strip()
    if not part:
      continue
    key, _, value = part.partition(" ")
    props[key] = value.strip()
  return props


def _flat_text(node: _Node) -> str:
  """The element's text, in document order, with its own whitespace."""
  return "".join(p if isinstance(p, str) else _flat_text(p) for p in node.parts)


def _norm(text: str) -> str:
  return _WS.sub(" ", text).strip()


def _outermost(node: _Node, classes: frozenset[str]) -> list[_Node]:
  """Nodes carrying one of ``classes``, never descending into a match."""
  if node.classes & classes:
    return [node]
  found: list[_Node] = []
  for child in node.children:
    found.extend(_outermost(child, classes))
  return found


def _descendants(node: _Node, classes: frozenset[str]) -> list[_Node]:
  found: list[_Node] = []
  for child in node.children:
    if child.classes & classes:
      found.append(child)
    found.extend(_descendants(child, classes))
  return found


def _blocks_of(page: _Node) -> list[_Node]:
  """The page's block-level nodes, at the coarsest grouping it offers.

  Tesseract nests ``ocr_page > ocr_carea > ocr_par > ocr_line``; kraken emits
  ``ocr_page > ocr_line`` flat. The page itself is the last resort, so a flat
  file still yields one block rather than silently none.
  """
  for classes in (_BLOCK_CLASSES, _PAR_CLASSES):
    found = _outermost(page, classes)
    if found:
      return found
  return [page]


def _float(raw: str | None) -> float | None:
  if raw is None:
    return None
  try:
    return float(raw)
  except ValueError:
    return None


def _confidences(block: _Node) -> list[float]:
  words = _descendants(block, _WORD_CLASSES)
  values = [v for w in words if (v := _float(w.props.get("x_wconf"))) is not None]
  if values:
    return values
  for word in words:
    values.extend(
      v for raw in word.props.get("x_confs", "").split()
      if (v := _float(raw)) is not None
    )
  return values


def _aggregate(values: list[float]) -> float:
  """Mean confidence in [0, 1], normalizing the spec's 0-100 scale."""
  if not values:
    return 0.0
  scale = 100.0 if max(values) > 1.0 else 1.0
  mean = sum(values) / len(values) / scale
  return min(1.0, max(0.0, mean))


def _declared_logical(node: _Node) -> set[str]:
  """Logical classes declared anywhere in the block, engine-agnostically.

  Tesseract would carry them on the ``ocr_carea``; a flat producer carries
  them on the lines. Either way the label is reported, never obeyed.
  """
  found = set(node.classes & _LOGICAL_CLASSES)
  for child in node.children:
    found |= _declared_logical(child)
  return found


def _evidence(block: _Node) -> str:
  kind = " ".join(sorted(block.classes)) or block.tag or "block"
  evidence = f"hOCR {kind}; OCR output — text is generated, not decoded"
  declared = sorted(_declared_logical(block))
  if declared:
    evidence += f"; logical class declared ({' '.join(declared)}) — not acted on"
  return evidence


def ingest_hocr(paths: list[str | Path]) -> Document:
  """Ingest hOCR files; one file may carry several ``ocr_page`` divs."""
  doc = Document(source_name=Path(paths[0]).stem if paths else "hocr", ingest="hocr")
  index = 0
  for p in paths:
    parser = _HocrParser()
    parser.feed(Path(p).read_text(encoding="utf-8"))
    parser.close()
    pages = _outermost(parser.root, _PAGE_CLASSES)
    if not pages:
      raise ValueError(f"{p}: no ocr_page element — not hOCR output")
    for src in pages:
      page = Page(index=index, printed_page=src.props.get("lpageno") or None)
      index += 1
      for blk in _blocks_of(src):
        lines = [t for ln in _outermost(blk, _LINE_CLASSES) if (t := _norm(_flat_text(ln)))]
        if not lines:
          whole = _norm(_flat_text(blk))
          lines = [whole] if whole else []
        if not lines:
          continue
        page.blocks.append(Block(
          layer=Layer.UNKNOWN,
          text="\n".join(lines),
          source=Source.OCR,
          generative=True,
          confidence=_aggregate(_confidences(blk)),
          evidence=_evidence(blk),
        ))
      doc.pages.append(page)
  return doc
