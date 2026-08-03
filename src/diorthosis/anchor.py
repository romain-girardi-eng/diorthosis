"""Apparatus anchoring: link each apparatus entry to its place in the text.

The apparatus band cites the constituted text through one of two printed
conventions:

- **marker style** (footnote-like; e.g. Paradosis): a superscript number in
  the text (``σωθήσεται6``) matches the number opening the apparatus entry;
- **line style** (Teubner/OCT): marginal line numbers, cited by the entries
  (detected, not yet resolved — that is the location-referenced method).

Anchoring is evidence-driven and never guesses:

- marker numbers RESTART per printed page and may repeat within one page
  (five pages of the reference edition carry a duplicated number). A number
  with several in-text candidates is resolved by matching the entry's LEMMA
  against the text before each candidate; without a unique lemma-confirmed
  candidate the anchor stays unresolved and is counted as ``ambiguous``.
- markers separated from their word by a space ("detached": ``ἐδήλωσέ 4``)
  are indistinguishable from section numbers by shape alone; they are
  accepted ONLY when the lemma confirms them.
- entry numbers are monotone within a band; a would-be entry whose number
  does not increase is a locus reference inside the previous entry, not a
  new entry (this exact confusion fabricated phantom entries before).

Entries are split, never rewritten: raw text is preserved verbatim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .conspectus import Registry
from .grammar import parse_entry
from .match import lemma_matches_before
from .model import Anchor, ApparatusEntry, Block, Layer, Page

# Genuine capital letters only. The naive range Ἀ-ῼ (U+1F00-1FFC) contains
# the LOWERCASE Greek Extended letters as well — a bug that once split
# entries on lowercase words. Greek Extended capitals live in disjoint
# sub-ranges.
_LEMMA_CAPITAL = (
  "A-Z"
  "Ά-Ώ"            # accented capitals, U+0386-038F
  "Α-Ω"            # basic capitals, U+0391-03A9
  "Ἀ-ἏἘ-ἝἨ-ἯἸ-Ἷ"
  "Ὀ-ὍὙ-ὟὨ-Ὧ"
  "ᾈ-ᾏᾘ-ᾟᾨ-ᾯ"  # capitals with prosgegrammeni (ᾝρει, p196: unsplit without them)
  "Ᾰ-ᾼῈ-ῌῘ-ΊῨ-ῬῸ-ῼ"
)
_ENTRY_SPLIT = re.compile(
  r"(?:(?<=^)|(?<=\s\s))(\d{1,2})\s+(?=[" + _LEMMA_CAPITAL + "])"
)

# Characters that may legitimately close the word a marker is glued to:
# Greek letters, editorial brackets, closing punctuation, elision apostrophe
# (histogram over the full reference edition: ] 16×, ’ 10×, ) 2×, ; 1×).
_GLUE = "Ͱ-Ͽἀ-῿>\\]\\)’'·;.,"
_BOUNDARY = " \t\n.,·;:!»)\\]Ͱ-Ͽἀ-῿"
_MARKER = re.compile(
  r"(?<=[" + _GLUE + r"])(\d{1,2})(?=[" + _BOUNDARY + r"]|$)"
)
_DETACHED = re.compile(
  r"(?<=[Ͱ-Ͽἀ-῿\]’']) (\d{1,2})(?=[ \t\n.,·;:!»)\]]|$)"
)
_HAS_GREEK_NEAR = re.compile(r"[Ͱ-Ͽἀ-῿]")


@dataclass
class _Candidate:
  block_index: int
  offset: int
  detached: bool
  digit_start: int
  """Start of the printed digits; for a detached marker this includes the
  separating space, so consuming the span re-glues the marker to its word."""
  digit_end: int
  """End (exclusive) of the printed digits."""


def split_entries(apparatus_text: str) -> list[ApparatusEntry]:
  """Split an apparatus band into numbered entries, verbatim.

  Entry numbers must be strictly increasing within a band; a split point
  whose number does not increase is a locus reference inside the previous
  entry and is merged back.
  """
  flat = " ".join(apparatus_text.split("\n"))

  # candidate split positions, filtered by two structural rules:
  # - never inside parentheses (locus references live there: "(… Dial.
  #   136,  2  Marc.)" once fabricated a phantom entry 2);
  # - entry numbers are strictly increasing within a band.
  boundaries: list[tuple[int, int, str]] = []  # (start, body_start, num)
  depth = 0
  prev_num = 0
  scan = 0
  for m in _ENTRY_SPLIT.finditer(flat):
    depth += flat.count("(", scan, m.start()) - flat.count(")", scan, m.start())
    scan = m.start()
    num = int(m.group(1))
    if depth > 0 or num <= prev_num:
      continue
    prev_num = num
    boundaries.append((m.start(), m.end(), m.group(1)))

  entries: list[ApparatusEntry] = []
  head = flat[: boundaries[0][0]].strip() if boundaries else flat.strip()
  if head:
    entries.append(ApparatusEntry(raw=head))
  for i, (_, body_start, num) in enumerate(boundaries):
    end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(flat)
    body = flat[body_start: end].strip()
    if body:
      entries.append(ApparatusEntry(
        raw=body, anchor=Anchor(kind="marker", value=num),
      ))
  return entries


def find_markers(text: str) -> list[tuple[str, int]]:
  """(marker number, char offset) for every glued superscript marker.

  A candidate must have a Greek letter within the four preceding characters:
  punctuation alone (…"p. 45"…) never carries a marker.
  """
  out: list[tuple[str, int]] = []
  for m in _MARKER.finditer(text):
    if _HAS_GREEK_NEAR.search(text[max(0, m.start() - 4): m.start()]):
      out.append((m.group(1), m.start()))
  return out


def _find_detached(text: str) -> list[tuple[str, int]]:
  out: list[tuple[str, int]] = []
  for m in _DETACHED.finditer(text):
    if _HAS_GREEK_NEAR.search(text[max(0, m.start() - 4): m.start()]):
      out.append((m.group(1), m.start() + 1))
  return out


def _lemma_of(entry: ApparatusEntry, registry: Registry | None) -> str | None:
  if registry is None:
    return None
  parsed = parse_entry(entry.raw, registry)
  return parsed.lemma if parsed is not None else None


def _confirmed(lemma: str | None, page: Page, cand: _Candidate) -> bool:
  if lemma is None:
    return False
  text = page.blocks[cand.block_index].text
  return lemma_matches_before(lemma, text[: cand.offset])


def anchor_page(page: Page, registry: Registry | None = None) -> dict[str, int]:
  """Split and anchor the apparatus blocks of one page, in place.

  Returns honest counters — including ``ambiguous`` (several candidates,
  none or several lemma-confirmed) and ``duplicate_markers`` (numbers that
  occur more than once in the page text): coverage is part of the output.
  """
  candidates: dict[str, list[_Candidate]] = {}
  for bi, block in enumerate(page.blocks):
    if block.layer in (Layer.TEXT, Layer.HEADING):
      for num, off in find_markers(block.text):
        candidates.setdefault(num, []).append(
          _Candidate(bi, off, False, off, off + len(num)))
      for num, off in _find_detached(block.text):
        # off is the digit position; the span starts one earlier so the
        # separating space is consumed together with the digits
        candidates.setdefault(num, []).append(
          _Candidate(bi, off, True, off - 1, off + len(num)))

  stats = {"entries": 0, "anchored": 0, "unanchored": 0,
           "ambiguous": 0, "duplicate_markers": 0}
  stats["duplicate_markers"] = sum(
    1 for c in candidates.values() if len([x for x in c if not x.detached]) > 1
  )

  for block in page.blocks:
    if block.layer is not Layer.APPARATUS:
      continue
    block.entries = split_entries(block.text)
    for e in block.entries:
      stats["entries"] += 1
      if e.anchor is None:
        stats["unanchored"] += 1
        continue
      cands = candidates.get(e.anchor.value, [])
      glued = [c for c in cands if not c.detached]
      chosen: _Candidate | None = None
      if len(glued) == 1:
        chosen = glued[0]
      else:
        lemma = _lemma_of(e, registry)
        confirmed = [c for c in cands if _confirmed(lemma, page, c)]
        if len(confirmed) == 1:
          chosen = confirmed[0]
        elif glued or [c for c in cands if c.detached]:
          stats["ambiguous"] += 1
      if chosen is not None:
        e.anchor.block_index, e.anchor.char_offset = chosen.block_index, chosen.offset
        e.anchor.digit_start, e.anchor.digit_end = chosen.digit_start, chosen.digit_end
        stats["anchored"] += 1
      else:
        stats["unanchored"] += 1
  return stats


def detect_marginal_line_numbers(page: Page) -> bool:
  """Line-style detection only (P1): short digit runs in arithmetic
  progression by 5 anywhere in the text blocks' margins."""
  seq = re.findall(r"(?:^|\s)(5|10|15|20|25|30)(?:\s|$)",
                   "\n".join(b.text for b in page.blocks_of(Layer.TEXT)))
  return len(seq) >= 3


def anchor_block_text(block: Block) -> str:
  """The block's text with each superscript marker rewritten as ⟦n⟧ —
  the single, documented normalization diorthosis performs."""
  return _MARKER.sub(lambda m: f"⟦{m.group(1)}⟧", block.text)


def marker_positions(text: str) -> dict[int, int]:
  """start offset -> end offset of every glued marker (public accessor for
  emitters — do not re-implement marker traversal)."""
  return {
    off: off + len(num) for num, off in find_markers(text)
  }
