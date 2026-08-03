"""Apparatus anchoring: link each apparatus entry to its place in the text.

The apparatus band cites the constituted text through one of two printed
conventions:

- **marker style** (footnote-like; e.g. Paradosis): a superscript number in
  the text (``σωθήσεται6``) matches the number opening the apparatus entry
  (``6 Δικαιοσύνῃ … :``);
- **line style** (Teubner/OCT/SC): marginal line numbers every five lines,
  cited by the entries.

P1 resolves the marker style completely and detects the line style without
resolving it (honesty over guesswork: resolving line citations requires the
marginal numbers, which some layouts absorb into the text column).

Entries are split, never rewritten: the raw entry text is preserved verbatim.
"""

from __future__ import annotations

import re

from .model import Anchor, ApparatusEntry, Block, Layer, Page

# An entry opens with its number followed by the LEMMA, which the reference
# series capitalizes ("6 Δικαιοσύνῃ …"). Numbers inside cross-references
# ("cf. 62, 2 (ὅτι…)") are not followed by a capital and therefore never
# split. This is the P1 heuristic; per-series grammar files supersede it in
# phase 2. Capital classes: Latin, Greek accented capitals (U+0386-038F),
# basic Greek capitals (U+0391-03A9), Greek Extended capitals.
_LEMMA_CAPITAL = "A-ZΆ-ΏΑ-ΩἈ-ῼ"
_ENTRY_SPLIT = re.compile(r"(?:(?<=^)|(?<=\s\s))(\d{1,2})\s+(?=[" + _LEMMA_CAPITAL + "])")

# A marker is a small number glued to the end of a Greek word — or of an
# editorial bracket around one, as in Ὥς<τε>1.
_MARKER = re.compile(r"(?<=[Ͱ-Ͽἀ-῿>])(\d{1,2})(?=[\s.,·;:!»)\]]|$)")


def split_entries(apparatus_text: str) -> list[ApparatusEntry]:
  """Split an apparatus band into numbered entries, verbatim.

  Text before the first number (or an un-numbered band) stays a single
  anchor-less entry — some bands are prose (apparatus fontium) and must not
  be forced into the numeric mold.
  """
  flat = " ".join(apparatus_text.split("\n"))
  parts = _ENTRY_SPLIT.split(flat)
  entries: list[ApparatusEntry] = []
  if parts and parts[0].strip():
    entries.append(ApparatusEntry(raw=parts[0].strip()))
  for i in range(1, len(parts) - 1, 2):
    num, body = parts[i], parts[i + 1].strip()
    if body:
      entries.append(ApparatusEntry(
        raw=body, anchor=Anchor(kind="marker", value=num),
      ))
  return entries


def find_markers(text: str) -> list[tuple[str, int]]:
  """(marker number, char offset) for every superscript marker in the text."""
  return [(m.group(1), m.start()) for m in _MARKER.finditer(text)]


def anchor_page(page: Page) -> dict[str, int]:
  """Split and anchor the apparatus blocks of one page, in place.

  Returns counters: entries, anchored, unanchored — the coverage is part of
  the output's honesty, never silently perfect.
  """
  markers: dict[str, tuple[int, int]] = {}
  for bi, block in enumerate(page.blocks):
    if block.layer is Layer.TEXT:
      for num, off in find_markers(block.text):
        markers.setdefault(num, (bi, off))

  stats = {"entries": 0, "anchored": 0, "unanchored": 0}
  for block in page.blocks:
    if block.layer is not Layer.APPARATUS:
      continue
    block.entries = split_entries(block.text)
    for e in block.entries:
      stats["entries"] += 1
      if e.anchor is None:
        stats["unanchored"] += 1
        continue
      hit = markers.get(e.anchor.value)
      if hit is not None:
        e.anchor.block_index, e.anchor.char_offset = hit
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
