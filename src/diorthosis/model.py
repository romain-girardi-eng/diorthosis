"""The common document model every ingest source compiles into.

Design rules, inherited from the regreek zero-fabrication contract:

- **Provenance is load-bearing.** Every block records where its text came
  from (``born_digital`` or ``ocr``) and whether it was *generated* by a
  recognition engine. Born-digital text is a faithful decoding of the file's
  own glyph stream; OCR text is a model's guess and is permanently marked as
  such — the distinction must survive into the TEI and Markdown outputs.
- **Nothing is reordered, merged, or corrected.** The model mirrors the page.
- **Citability.** A block knows its printed folio (the citable page number),
  never just the file's page index.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Source(str, Enum):
  BORN_DIGITAL = "born_digital"
  OCR = "ocr"


class Layer(str, Enum):
  TEXT = "text"                # the constituted text (any language/script)
  APPARATUS = "apparatus"      # apparatus criticus / fontium at the foot
  TRANSLATION = "translation"
  NOTES = "notes"              # translator's / editorial notes
  HEADING = "heading"
  RUNNING_HEAD = "running_head"
  PAGE_NUMBER = "page_number"
  UNKNOWN = "unknown"


@dataclass
class Anchor:
  """A link between an apparatus entry and its place in the text.

  ``kind`` records how the link was established:

  - ``marker``: a numeric superscript in the text matches the entry number
    (footnote-style apparatus, e.g. Paradosis);
  - ``line``: the entry cites a marginal line number (Teubner/OCT style).
  """

  kind: str
  value: str
  """The marker number or line number, as printed."""
  block_index: int | None = None
  """Index of the text block the anchor resolves into, when resolved."""
  char_offset: int | None = None
  """Offset within that block's text, when resolvable."""
  digit_start: int | None = None
  """Start of the printed marker digits in the block's text — includes the
  separating space of a detached marker, so consuming [digit_start,
  digit_end) removes the digits AND re-glues the marker to its word."""
  digit_end: int | None = None
  """End (exclusive) of the printed marker digits in the block's text."""


@dataclass
class ApparatusEntry:
  """One entry of the apparatus band, split but NOT interpreted.

  P1 deliberately stops at anchoring: the entry text is preserved verbatim
  (lemma, readings, sigla and editors unparsed). Interpreting it into
  <app>/<lem>/<rdg> is the phase-2 per-series grammar problem.
  """

  raw: str
  anchor: Anchor | None = None
  parsed_verse: object | None = None
  """A versegrammar.VerseEntry when the band follows the verse-referenced
  convention and this entry parsed; None otherwise."""
  parsed_line: object | None = None
  """A linegrammar.LineEntry when the band follows the line-referenced
  convention and this entry parsed; None otherwise."""
  parsed_override: object | None = None
  """A grammar.ParsedEntry supplied by HUMAN REVIEW (overrides file).
  Wins over every grammar; the TEI marks it resp="#human-review"."""
  override_action: str = ""
  """'' | 'parse' | 'verbatim' — how review touched this entry."""


@dataclass
class Block:
  layer: Layer
  text: str
  source: Source
  generative: bool
  """True when the text was produced by a recognition engine (OCR) rather
  than decoded from the file's own character stream."""
  confidence: float
  evidence: str = ""
  inline_refs: list[str] = field(default_factory=list)
  entries: list[ApparatusEntry] = field(default_factory=list)
  """Populated on APPARATUS blocks after anchoring."""


@dataclass
class Page:
  index: int
  """0-based index in the source file — a file coordinate, not a locus."""
  printed_page: str | None
  """The folio printed on the page: the citable page number."""
  blocks: list[Block] = field(default_factory=list)

  def blocks_of(self, layer: Layer) -> list[Block]:
    return [b for b in self.blocks if b.layer == layer]


@dataclass
class Document:
  source_name: str
  pages: list[Page] = field(default_factory=list)
  ingest: str = ""
  """Which adapter produced this document (borndigital, alto, hocr…)."""

  @property
  def any_generative(self) -> bool:
    return any(b.generative for p in self.pages for b in p.blocks)
