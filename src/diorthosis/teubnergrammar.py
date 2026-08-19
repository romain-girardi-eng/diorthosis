"""Teubner / OCT printed apparatus — line number, ``lemma]``, colon readings.

The shape as printed by the Bibliotheca Teubneriana and the Oxford Classical
Texts (and by the many series that imitate them)::

    12 λόγος] λέξις A : om. B
    15-16 καὶ εἶπεν] om. M
    20 εἰπεῖν] εἶπεν vulg. : λέγει A

- a new entry opens with its marginal LINE number (or range) and a short
  lemma closed by ``]`` — the same boundary the paragraphed-reledmac
  grammar uses, which is why a band WITHOUT spaced colons stays there
  (Plaoul, Segrave) and is not stolen;
- readings inside an entry are separated by a SPACED colon `` : ``, the
  signal this family carries and the paragraph grammar refuses on purpose;
- the lemma typically carries NO sigla: that is a *negative* apparatus.
  The constituted text is the reading of the silent witnesses. TEI records
  that as a ``<lem>`` without ``@wit`` — never by inventing ``cett.``
  unless the edition printed it;
- ``∥``, spaced ``|`` and ``||`` are foreign and refuse the whole band.

Contract as everywhere: parse only what the convention defines, refuse
verbatim, lose nothing. A grammar that cannot be told from Plaoul's
``lemma]`` juxtaposition is not this grammar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .conspectus import Registry
from .convention import GateDecision, unconsumed_token_ratio
from .grammar import QUALIFIERS, Attribution, _split_attribution
from .paragraphgrammar import _BOUNDARY

TEUBNER_MAX_UNCONSUMED_TOKEN_RATIO = 0.20


@dataclass
class TeubnerReading:
  text: str
  attribution: Attribution


@dataclass
class TeubnerEntry:
  line: str
  raw: str
  source_slice: str = ""
  lemma: str = ""
  lemma_attribution: Attribution | None = None
  readings: list[TeubnerReading] = field(default_factory=list)
  comments: list[str] = field(default_factory=list)
  parsed: bool = False
  resolved_lemma: str = ""


def looks_teubner(band_text: str) -> bool:
  """Line + ``lemma]`` AND a spaced colon; no reledmac / Budé separators.

  The colon is load-bearing: without it this band is the paragraph
  family's, and stealing Plaoul would re-open the v0.6 fabrication.
  """
  flat = " ".join(band_text.split())
  if "∥" in flat or " | " in flat or "||" in flat:
    return False
  if " : " not in flat:
    return False
  return bool(_BOUNDARY.search(flat))


def split_teubner_entries(band_text: str) -> list[TeubnerEntry]:
  """Split on ``LINE lemma]`` boundaries; keep each source slice verbatim."""
  hits = list(_BOUNDARY.finditer(band_text))
  entries: list[TeubnerEntry] = []
  for i, m in enumerate(hits):
    end = hits[i + 1].start() if i + 1 < len(hits) else len(band_text)
    source_slice = band_text[m.start():end].strip()
    if not source_slice:
      continue
    entries.append(TeubnerEntry(
      line=m.group(1),
      raw=" ".join(source_slice.split()),
      source_slice=source_slice,
    ))
  return entries


def gate_teubner_band(band_text: str, registry: Registry) -> GateDecision:
  grammar = "teubner"
  if not looks_teubner(band_text):
    return GateDecision.refuse(grammar, "band lacks the line-lemma] + ' : ' signature")
  trial = split_teubner_entries(band_text)
  if not trial:
    return GateDecision.refuse(grammar, "no LINE lemma] boundary was split")
  for entry in trial:
    parse_teubner_entry(entry, registry)
  ratio = unconsumed_token_ratio(trial)
  if ratio > TEUBNER_MAX_UNCONSUMED_TOKEN_RATIO:
    return GateDecision.refuse(
      grammar,
      f"trial parse left {ratio:.1%} of tokens unconsumed "
      f"(maximum {TEUBNER_MAX_UNCONSUMED_TOKEN_RATIO:.0%})",
    )
  parsed = [entry for entry in trial if entry.parsed]
  if not parsed:
    return GateDecision.refuse(grammar, "trial parse produced no structured entry")
  attributed = sum(
    1 for entry in parsed for reading in entry.readings
    if not reading.attribution.empty
  )
  if attributed < len(parsed):
    return GateDecision.refuse(
      grammar,
      f"only {attributed} attributed reading(s) across {len(parsed)} "
      "parsed entries — a negative apparatus still names who diverges",
    )
  return GateDecision.accept(grammar)


def parse_teubner_entry(entry: TeubnerEntry, registry: Registry) -> TeubnerEntry:
  """Parse ``NUM LEMMA] reading [: reading …]`` in place.

  Refusal when the lemma closer is missing, a side dissolves into
  attribution with no text and no operator, or no side carries an
  attribution (juxtaposed prose, not this convention).
  """
  m = _BOUNDARY.match(entry.raw)
  if m is None:
    return entry
  entry.lemma = m.group(2).strip()
  rest = entry.raw[m.end():].strip()
  if not rest:
    return entry
  sides = [side.strip() for side in re.split(r"\s+:\s+", rest) if side.strip()]
  if not sides:
    return entry
  readings: list[TeubnerReading] = []
  comments: list[str] = []
  for side in sides:
    text, attr = _split_attribution(side, registry)
    text = text.strip()
    if not text and attr.empty:
      return entry
    if not text and attr.qualifiers and set(attr.qualifiers) <= set(QUALIFIERS):
      # ``om. A`` — the reading is the empty string, the operator stays
      readings.append(TeubnerReading(text="", attribution=attr))
      continue
    if not text:
      return entry
    readings.append(TeubnerReading(text=text, attribution=attr))
  if not any(not r.attribution.empty for r in readings):
    return entry
  entry.lemma_attribution = Attribution()
  entry.readings = readings
  entry.comments = comments
  entry.parsed = True
  return entry
