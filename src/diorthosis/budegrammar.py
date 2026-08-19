"""Budé / Collection des Universités de France run-in apparatus.

The shape as printed by the Budé series and by theses that imitate it
(de Rivas 2022 on Herodian, measured on the born-digital PDF)::

    5 μυθῶδες ABVGF : ἀσθενές L || 6 ἐλεγχθήσεται VGFL : ἐλεχθήσεται AB

- ``||`` separates ENTRIES, not readings. That is the opposite of the
  textbook reconstruction, and it is why v0.6 collapsed a page into one
  ``<app>``: it treated ``||`` as a reading separator inside a single
  lemma. This grammar splits on ``||`` first;
- each entry is ``LOCUS? LEMMA WITS : READING WITS``. The lemma usually
  CARRIES sigla — a positive apparatus. Silence on the lemma is legal
  (negative) and emits ``<lem>`` without ``@wit``;
- the locus is a line, a range, or a section.line (``5``, ``6-7``,
  ``1.11``). It may be omitted: the next ``||`` chunk inherits the
  previous locus;
- ``||`` immediately before a ``LINE lemma]`` boundary is Segrave-style
  paragraph continuation, not this convention — the looker refuses it
  so the paragraph gate can refuse it too;
- a chunk that does not trial-parse stays a verbatim entry. The gate
  accepts the band only when enough chunks parse, so a page of narrative
  cannot become structure.

Contract as everywhere: parse only what the convention defines, refuse
verbatim, lose nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .conspectus import Registry
from .convention import GateDecision
from .grammar import QUALIFIERS, Attribution, _split_attribution
from .linegrammar import burst_sigla

# Segrave continuation is ``|| 31 album]`` — a lemma closer, no colon
# between the number and the ``]``. Editorial brackets (``[ὡς ἄν]``)
# after a Budé colon must not trip this.
_PARAGRAPH_CONTINUATION = re.compile(
  r"\|\|\s*\d{1,3}(?:[-–]\d{1,3})?\s+(?:(?!\s+:\s)[^:\]]){1,40}\]"
)

_NARRATIVE = re.compile(
  r"(euanid|difficile|legitur|uerbum|extra\s+marginem|primae?|primera|"
  r"littera|inscriptio|in\s+[A-Z]\b)",
  re.I,
)

_LOCUS = re.compile(
  r"^(\d+(?:\.\d+)?(?:[-–]\d+)?[¹²³]?)(?:\s+|$)"
)

BUDE_MIN_PARSED = 2
BUDE_MIN_PARSED_RATIO = 0.30


@dataclass
class BudeReading:
  text: str
  attribution: Attribution


@dataclass
class BudeEntry:
  line: str
  raw: str
  source_slice: str = ""
  lemma: str = ""
  lemma_attribution: Attribution | None = None
  readings: list[BudeReading] = field(default_factory=list)
  comments: list[str] = field(default_factory=list)
  parsed: bool = False
  resolved_lemma: str = ""


def looks_bude(band_text: str) -> bool:
  """``||`` as an entry separator, not as a paragraph-continuation mark."""
  flat = " ".join(band_text.split())
  if "||" not in flat:
    return False
  if _PARAGRAPH_CONTINUATION.search(flat):
    return False
  if "∥" in flat and " | " in flat:
    return False
  return " : " in flat


_INNER_SECTION = re.compile(r"(?<=\s)(\d+\.\d+)(?=\s)")


def split_bude_entries(band_text: str) -> list[BudeEntry]:
  """Split on ``||`` and on mid-chunk ``section.line`` loci."""
  parts: list[str] = []
  for chunk in re.split(r"\s*\|\|\s*", band_text):
    start = 0
    for m in _INNER_SECTION.finditer(chunk):
      if m.start() == 0:
        continue
      head = chunk[start:m.start()].strip()
      if head:
        parts.append(head)
      start = m.start()
    tail = chunk[start:].strip()
    if tail:
      parts.append(tail)
  entries: list[BudeEntry] = []
  current_line = ""
  for part in parts:
    source_slice = part.strip()
    if not source_slice:
      continue
    raw = " ".join(source_slice.split())
    line = ""
    m = _LOCUS.match(raw)
    if m:
      line = m.group(1)
      current_line = line
    entries.append(BudeEntry(
      line=line or current_line,
      raw=raw,
      source_slice=source_slice,
    ))
  return entries


def gate_bude_band(band_text: str, registry: Registry) -> GateDecision:
  grammar = "bude"
  if _PARAGRAPH_CONTINUATION.search(" ".join(band_text.split())):
    return GateDecision.refuse(
      grammar,
      "foreign separator '||' precedes a LINE lemma] boundary "
      "(paragraph continuation, not a Budé entry separator)",
    )
  if "||" not in band_text:
    return GateDecision.refuse(grammar, "band has no '||' entry separator")
  trial = split_bude_entries(band_text)
  if len(trial) < 2:
    return GateDecision.refuse(grammar, f"only {len(trial)} '||'-separated chunk(s)")
  for entry in trial:
    parse_bude_entry(entry, registry)
  parsed = [entry for entry in trial if entry.parsed]
  parsed_ratio = len(parsed) / max(len(trial), 1)
  if len(parsed) < BUDE_MIN_PARSED:
    return GateDecision.refuse(
      grammar,
      f"only {len(parsed)} '||'-chunk(s) trial-parsed "
      f"(minimum {BUDE_MIN_PARSED})",
    )
  if parsed_ratio < BUDE_MIN_PARSED_RATIO:
    return GateDecision.refuse(
      grammar,
      f"only {len(parsed)}/{len(trial)} '||'-chunks trial-parsed "
      f"({parsed_ratio:.1%}; minimum {BUDE_MIN_PARSED_RATIO:.0%})",
    )
  return GateDecision.accept(grammar)


def _parse_bude_omission(entry: BudeEntry, registry: Registry) -> BudeEntry:
  """``5 χρόνῳ om. L`` / ``δέ om. G`` — no colon, one operator."""
  raw = " ".join(burst_sigla(entry.raw.split(), registry))
  if "om." not in raw:
    return entry
  m = _LOCUS.match(raw)
  rest = raw
  if m:
    if not entry.line:
      entry.line = m.group(1)
    rest = raw[m.end():].strip()
  left, _, right = rest.partition("om.")
  lemma = left.strip()
  _, attr = _split_attribution(("om. " + right).strip(), registry)
  if not lemma or attr.empty:
    return entry
  if _NARRATIVE.search(lemma) or re.search(r"[A-ZΑ-Ω]{2,}", lemma):
    return entry
  if len(lemma.split()) > 8:
    return entry
  entry.lemma = lemma
  entry.lemma_attribution = Attribution()
  entry.readings = [BudeReading(text="", attribution=attr)]
  entry.parsed = True
  return entry


def parse_bude_entry(entry: BudeEntry, registry: Registry) -> BudeEntry:
  """Parse ``LOCUS? LEMMA ATTR : READING ATTR`` in place.

  One colon, two sides. Extra narrative after the reading's attribution
  is a refusal — that is how ``in G uerbum … difficile legitur`` stays
  verbatim instead of becoming a third witness.
  """
  if " : " not in entry.raw:
    return _parse_bude_omission(entry, registry)
  left, right = entry.raw.split(" : ", 1)
  left, right = left.strip(), right.strip()
  if not left or not right:
    return entry
  left = " ".join(burst_sigla(left.split(), registry))
  right = " ".join(burst_sigla(right.split(), registry))
  lemma_text, lemma_attr = _split_attribution(left, registry)
  lemma_text = lemma_text.strip()
  m = _LOCUS.match(lemma_text)
  if m:
    if not entry.line:
      entry.line = m.group(1)
    lemma_text = lemma_text[m.end():].strip()
  if not lemma_text:
    return entry
  reading_text, reading_attr = _split_attribution(right, registry)
  reading_text = reading_text.strip()
  if not reading_text and reading_attr.qualifiers \
     and set(reading_attr.qualifiers) <= set(QUALIFIERS):
    reading_text = ""
  elif not reading_text:
    return entry
  if reading_attr.empty:
    return entry
  if len(lemma_text.split()) > 8 or _NARRATIVE.search(lemma_text) \
     or _NARRATIVE.search(reading_text) or "om." in reading_text \
     or "]" in reading_text or re.search(r"[A-ZΑ-Ω]{2,}", lemma_text):
    # Inscriptio run-on, ``in G uerbum … difficile legitur``, a second
    # ``om.`` jammed into the reading, damaged ``ἀριθ]`` — not one reading.
    return entry
  entry.lemma = lemma_text
  entry.lemma_attribution = lemma_attr
  entry.readings = [BudeReading(text=reading_text, attribution=reading_attr)]
  entry.parsed = True
  return entry
