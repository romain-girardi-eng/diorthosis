"""Verse-referenced apparatus grammar — the NT-edition convention.

The SBLGNT (and the NA/UBS family it abbreviates) prints its apparatus as::

    1:18 Ἰησοῦ Ἰησοῦ WH NIV RP ] – Treg • γένεσις γένεσις WH Treg NIV ]
    γέννησις RP 19 δειγματίσαι … ] παραδειγματίσαι RP

- entries are referenced by CHAPTER:VERSE (``1:18``), later entries of the
  same chapter by the bare verse number (``19``); ``•`` separates entries
  within a verse, a new verse reference separates entries across verses;
- the lemma is printed twice (bold, then roman before its sigla) — the
  extracted stream shows the doublet, sometimes glued (``ὑπὸὑπὸ``);
- ``]`` separates the accepted side from the rejected readings, ``;``
  separates readings; ``–`` is an omission, ``+ X`` an addition (kept
  VERBATIM — the scholarly TEI encodes them exactly so);
- the attributing sigla are printed EDITIONS (WH, Treg, NIV, RP …), which
  the TEI declares as witnesses;
- in the TEXT, the variant's place is marked by in-text anchor sigla:
  ⸀ (following word) and ⸂…⸃ / ⸄…⸅ (spans) — the printed page itself gives
  both end points of the lemma.

The module follows grammar.py's contract: parse only what the convention
defines, refuse the rest verbatim, lose nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# The edition sigla of the NT critical tradition, as declared by the
# SBLGNT's own front matter and its TEI encoding. A registry fallback in
# the builtin_editors spirit: an edition's own conspectus always wins.
EDITION_WITNESSES: dict[str, str] = {
  "WH": "Westcott–Hort, The New Testament in the Original Greek (1881)",
  "Treg": "Tregelles, The Greek New Testament (1857–1879)",
  "NIV": "Goodrich–Lukaszewski, A Reader's Greek New Testament (2003)",
  "RP": "Robinson–Pierpont, The New Testament in the Original Greek: "
        "Byzantine Textform (2005)",
  "NA": "Nestle–Aland, Novum Testamentum Graece",
  "TR": "Textus Receptus",
  "SBL": "The Greek New Testament: SBL Edition (Holmes 2010)",
  "ECM": "Editio Critica Maior",
  "Holmes": "Michael W. Holmes, The Greek New Testament: SBL Edition (2010)",
  "Greeven": "Huck–Greeven, Synopse der drei ersten Evangelien (1981)",
  "JJM": "J. J. Griesbach (apud SBLGNT apparatus)",
}
_SIGLUM = re.compile(
  r"^(WH|Treg|NIV|RP|NA|TR|SBL|ECM|Holmes|Greeven|JJM)"
  r"(marg|app|txt|ed)?$"
)

_VERSE_REF = re.compile(r"^\d{1,3}:\d{1,3}(?:[-–]\d{1,3}(?::\d{1,3})?)?$")
_BARE_VERSE = re.compile(r"^\d{1,3}(?:[-–]\d{1,3})?$")
# in-text anchor sigla of the NT convention (U+2E00-2E0F)
ANCHOR_SIGLA = re.compile(r"[⸀-⸏]")


def is_edition_siglum(token: str) -> bool:
  return bool(_SIGLUM.match(token.strip(".,;·")))


@dataclass
class VerseReading:
  text: str
  """Verbatim as printed; '' for an omission ('–')."""
  sigla: list[str] = field(default_factory=list)


@dataclass
class VerseEntry:
  loc: str
  """Chapter:verse reference ('1:18', '1:7-8')."""
  raw: str
  """The printed entry, verbatim (without the leading reference)."""
  lemma: str = ""
  """The accepted form as printed (doublet reduced), possibly elliptical."""
  lemma_sigla: list[str] = field(default_factory=list)
  readings: list[VerseReading] = field(default_factory=list)
  parsed: bool = False
  resolved_lemma: str = ""
  """The full text of the lemma's span in the constituted text, once the
  anchor resolves — an elliptical printed lemma ('Βόες … Βόες') resolves to
  the actual span ('Βόες ἐκ τῆς Ῥαχάβ, Βόες')."""


def looks_verse_referenced(band_text: str) -> bool:
  """Signature of the convention: an opening C:V reference and the ']'
  lemma/readings separator."""
  flat = " ".join(band_text.split())
  return bool(re.match(r"^\d{1,3}:\d{1,3}\s", flat)) and " ] " in flat


def _wfold(w: str) -> str:
  """Word comparison form for doublet detection: punctuation-insensitive."""
  return w.strip(".,;·:!?»«()").lower()


def lemma_candidates(entry: VerseEntry) -> list[str]:
  """Candidate lemma forms for anchor resolution, printed form first.

  A residual spaced doublet ("ἐν ἐν") offers its half as a SECOND
  candidate; the constituted text arbitrates, and a genuine repetition
  ("Ἠλὶ ἠλὶ") resolves as candidate one before the half is ever tried."""
  out = [entry.lemma]
  words = entry.lemma.split()
  if len(words) >= 2 and len(words) % 2 == 0:
    half = len(words) // 2
    if [_wfold(w) for w in words[:half]] == [_wfold(w) for w in words[half:]]:
      out.append(" ".join(words[half:]))
  return [c for c in out if c]


_GLUED_SIGLUM = re.compile(
  r"^(.*?[Ͱ-Ͽἀ-῿])(WH|Treg|NIV|RP|NA|TR|SBL|ECM|Holmes|Greeven|JJM)"
  r"(marg|app|txt|ed)?$")


def _peel_sigla(words: list[str]) -> tuple[list[str], list[str]]:
  sigla: list[str] = []
  while words:
    if is_edition_siglum(words[-1]):
      sigla.insert(0, words.pop().strip(".,;·"))
      continue
    # a siglum glued to the Greek word it follows ("ἡμέραWH") splits
    m = _GLUED_SIGLUM.match(words[-1])
    if m:
      words[-1] = m.group(1)
      sigla.insert(0, m.group(2) + (m.group(3) or ""))
      continue
    break
  return words, sigla


def split_verse_entries(band_text: str) -> list[VerseEntry]:
  """Split a verse-referenced band into entries, verbatim.

  Boundaries: ``•`` always; a verse reference (C:V, or a bare number after
  a completed attribution) opens a new entry and updates the running
  chapter. The reference tokens are consumed into ``loc``; everything else
  is preserved verbatim in ``raw``.
  """
  flat = " ".join(band_text.replace("•", " • ").split())
  tokens = flat.split(" ")
  entries: list[VerseEntry] = []
  chapter = ""
  loc = ""
  cur: list[str] = []

  def flush() -> None:
    nonlocal cur
    raw = " ".join(cur).strip()
    if raw and loc:
      entries.append(VerseEntry(loc=loc, raw=raw))
    cur = []

  prev_was_siglum = False
  for tok in tokens:
    if _VERSE_REF.match(tok):
      flush()
      chapter = tok.split(":")[0]
      loc = tok
      prev_was_siglum = False
      continue
    if tok == "•":
      flush()
      prev_was_siglum = False
      continue
    # a bare verse number right after a completed attribution opens the
    # next verse's entry ("… γὰρ RP 19 δειγματίσαι …")
    if prev_was_siglum and _BARE_VERSE.match(tok) and chapter:
      flush()
      loc = f"{chapter}:{tok}"
      prev_was_siglum = False
      continue
    cur.append(tok)
    prev_was_siglum = is_edition_siglum(tok)
  flush()
  return entries


def parse_verse_entry(entry: VerseEntry) -> VerseEntry:
  """Parse ``LEMMA LEMMA SIGLA ] reading SIGLA ; reading SIGLA`` in place.

  Refusal (``parsed`` stays False) when the shape is not the convention's:
  no ``]``, an empty side, or a lemma side that dissolves entirely into
  sigla. The raw is preserved either way.
  """
  if "]" not in entry.raw:
    return entry
  left, _, right = entry.raw.partition("]")
  lwords, lsigla = _peel_sigla(left.split())
  # The bold lemma re-set in roman with zero kerning extracts as ONE glued
  # token ("δὲδὲ"): reduce a token whose halves agree to one half. Never
  # reduce ACROSS tokens — "Ἠλὶ ἠλὶ" is text, not a doublet (overlaid
  # copies are already deduplicated at glyph level in extraction).
  # occurrence numerals glued to the lemma ("1ἄλλῳ" = first occurrence of
  # ἄλλῳ in the verse) are locators, not text — the TEI lemma has none
  lwords = [re.sub(r"^\d(?=[Ͱ-Ͽἀ-῿])", "", w) for w in lwords]
  lwords = [
    w[: len(w) // 2]
    if len(w) >= 4 and len(w) % 2 == 0
    and _wfold(w[: len(w) // 2]) == _wfold(w[len(w) // 2:])
    else w
    for w in lwords
  ]
  if not lwords:
    return entry
  # ';' separates readings ONLY when the left part carries its sigla: a
  # bare ';' belongs to the text (punctuation variants are variants too —
  # "ἰδεῖν; προφήτην Treg NIV RP" is ONE reading)
  segments: list[str] = []
  for seg in right.split(";"):
    if segments:
      prev_words, prev_sigla = _peel_sigla(segments[-1].split())
      if not prev_sigla:
        segments[-1] = f"{segments[-1]};{seg}"
        continue
    segments.append(seg)
  readings: list[VerseReading] = []
  for seg in segments:
    words, sigla = _peel_sigla(seg.split())
    text = " ".join(words).strip()
    if text == "–" or text == "—" or text == "-":
      text = ""
    if not text and not sigla:
      continue
    readings.append(VerseReading(text=text, sigla=sigla))
  if not readings:
    return entry
  entry.lemma = " ".join(lwords)
  entry.lemma_sigla = lsigla
  entry.readings = readings
  entry.parsed = True
  return entry
