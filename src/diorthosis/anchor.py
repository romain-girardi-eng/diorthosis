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

Entries retain both an exact immutable source slice and a normalized parsing
view; normalization never supplies citable verbatim output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import linegrammar, paragraphgrammar, versegrammar
from .conspectus import Registry
from .grammar import gate_marker_band, parse_entry
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
# an entry may open with an editorial bracket before its capitalized lemma:
# "3 <Ab> incendio", "2 {Fluminum}" — the bracket is part of the printed text
_LEMMA_OPEN = r"(?=[<{\[⟨]?[" + _LEMMA_CAPITAL + "])"
_ENTRY_SPLIT = re.compile(
  r"(?:(?<=^)|(?<=\s\s))(\d{1,2})\s+" + _LEMMA_OPEN
)
# the same shape, anchored at a former line start (one-entry-per-line bands);
# the leading space is the flattened line break itself
_ENTRY_AT = re.compile(
  r" ?(\d{1,2})\s+" + _LEMMA_OPEN
)

# The letters a constituted text may be written in: Greek, or Latin script
# with its accented ranges (a LATIN edition's markers glue to Latin words —
# ``arcessit1`` — a class the Greek-only ranges once made invisible).
_TEXT_LETTER = "A-Za-zÀ-ÖØ-öø-ÿĀ-ſͰ-Ͽἀ-῿"
# Characters that may legitimately close the word a marker is glued to:
# text letters, editorial brackets, closing punctuation, elision apostrophe
# (histogram over the full reference edition: ] 16×, ’ 10×, ) 2×, ; 1×).
_GLUE = _TEXT_LETTER + ">}\\]\\)’'·;.,"
_BOUNDARY = " \t\n.,·;:!»)\\]—–" + _TEXT_LETTER
_MARKER = re.compile(
  r"(?<=[" + _GLUE + r"])(\d{1,2})(?=[" + _BOUNDARY + r"]|$)"
)
_DETACHED = re.compile(
  r"(?<=[" + _TEXT_LETTER + r"\]’']) (\d{1,2})(?=[ \t\n.,·;:!»)\]—–]|$)"
)
_HAS_LETTER_NEAR = re.compile("[" + _TEXT_LETTER + "]")


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

  Two boundary idioms are accepted, both observed in print:
  wide in-line gaps (Paradosis: two-plus spaces survive extraction) and
  one-entry-per-line bands (SC and TeX-set editions: line breaks carry the
  boundary, and a wrapped continuation line never opens with
  number-then-capital).
  """
  lines = apparatus_text.split("\n")
  line_starts: list[int] = []
  off = 0
  for ln in lines:
    line_starts.append(off)
    off += len(ln) + 1

  # candidate split positions, filtered by two structural rules:
  # - never inside parentheses (locus references live there: "(… Dial.
  #   136,  2  Marc.)" once fabricated a phantom entry 2);
  # - entry numbers are strictly increasing within a band.
  candidates: dict[int, tuple[int, str]] = {}  # start -> (body_start, num)
  for m in _ENTRY_SPLIT.finditer(apparatus_text):
    candidates[m.start()] = (m.end(), m.group(1))
  for ls in line_starts:
    m = _ENTRY_AT.match(apparatus_text, ls)
    if m:
      candidates.setdefault(m.start(1), (m.end(), m.group(1)))

  boundaries: list[tuple[int, int, str]] = []  # (start, body_start, num)
  depth = 0
  prev_num = 0
  scan = 0
  for start in sorted(candidates):
    body_start, num_s = candidates[start]
    depth += (apparatus_text.count("(", scan, start)
              - apparatus_text.count(")", scan, start))
    scan = start
    num = int(num_s)
    if depth > 0 or num <= prev_num:
      continue
    prev_num = num
    boundaries.append((start, body_start, num_s))

  entries: list[ApparatusEntry] = []
  head = (apparatus_text[: boundaries[0][0]].strip()
          if boundaries else apparatus_text.strip())
  if head:
    entries.append(ApparatusEntry(raw=head.replace("\n", " "), source=head))
  for i, (_, body_start, num) in enumerate(boundaries):
    end = (boundaries[i + 1][0]
           if i + 1 < len(boundaries) else len(apparatus_text))
    source_slice = apparatus_text[body_start:end].strip()
    if source_slice:
      entries.append(ApparatusEntry(
        raw=source_slice.replace("\n", " "), source=source_slice,
        anchor=Anchor(kind="marker", value=num),
      ))
  return entries


def find_markers(text: str) -> list[tuple[str, int]]:
  """(marker number, char offset) for every glued superscript marker.

  A candidate must have a text letter (Greek or Latin script) within the
  four preceding characters: punctuation alone (…"p. 45"…) never carries a
  marker.
  """
  out: list[tuple[str, int]] = []
  for m in _MARKER.finditer(text):
    if _HAS_LETTER_NEAR.search(text[max(0, m.start() - 4): m.start()]):
      out.append((m.group(1), m.start()))
  return out


def _find_detached(text: str) -> list[tuple[str, int]]:
  out: list[tuple[str, int]] = []
  for m in _DETACHED.finditer(text):
    if _HAS_LETTER_NEAR.search(text[max(0, m.start() - 4): m.start()]):
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


# a verse number inside the constituted text: word-bounded digits
_VERSE_IN_TEXT = re.compile(r"(?:^|(?<=[\s(]))(\d{1,3})(?::(\d{1,3}))?(?=[\s.,])")


def _verse_windows(text: str, verse: str) -> list[tuple[int, int]]:
  """(start, end) windows of the given verse number's occurrences in a
  text block — from just after the number to the next verse-like number."""
  marks = [(m.start(1), m.end(), m.group(2) or m.group(1))
           for m in _VERSE_IN_TEXT.finditer(text)]
  out = []
  for i, (_, after, num) in enumerate(marks):
    if num == verse:
      end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
      out.append((after, end))
  return out


def _find_span_end(window: str, lemma: str) -> tuple[int, int] | None:
  """(start, end) of the lemma inside a verse window.

  Tolerates the elliptical printed form ('Βόες … Βόες' finds first…last)
  and the text's own typography between the lemma's words: NBSP/double
  spaces and the in-text anchor sigla (⸂Ἠλὶ ἠλὶ⸃ must match 'Ἠλὶ ἠλὶ')."""
  def rx(words: list[str]) -> re.Pattern:
    # tokens are matched punctuation-stripped, with the text's own
    # typography tolerated between them — anchor sigla AND punctuation
    # ("προφήτην ἰδεῖν;" must match "⸂προφήτην ἰδεῖν⸃;"). A char-level
    # candidate uses "§" between characters where whitespace MAY occur
    # (glued-doublet reconstruction: "ο§τ§ι" matches "ὅ τι" and "ὅτι").
    if len(words) == 1 and "§" in words[0]:
      chars = words[0].split("§")
      return re.compile(
        r"[\s⸀-⸏]*".join(re.escape(ch) for ch in chars if ch))
    ws = [w.strip(".,;·:!?»«") for w in words]
    return re.compile(
      r"[\s⸀-⸏.,;·:!?]+".join(re.escape(w) for w in ws if w))

  if "…" in lemma or "..." in lemma:
    # Elliptical lemmas may carry SEVERAL ellipses ("ἐν … καὶ ἓν … καὶ ἓν").
    # Chain the parts in order from EVERY possible start of the first part
    # and keep the SHORTEST span: a repeated opening phrase must not make
    # the span leap over intervening text (Lc 6:42: two "τὸ κάρφος").
    parts = [w for w in re.split(r"\s*(?:…|\.\.\.)\s*", lemma) if w]
    first_rx = rx(parts[0].split())
    best: tuple[int, int] | None = None
    for m0 in first_rx.finditer(window):
      pos_ = m0.end()
      last_end = m0.end()
      ok = True
      for part in parts[1:]:
        m = rx(part.split()).search(window, pos_)
        if m is None:
          ok = False
          break
        last_end = m.end()
        pos_ = m.end()
      if ok and (best is None or last_end - m0.start() < best[1] - best[0]):
        best = (m0.start(), last_end)
    return best
  m = rx(lemma.split()).search(window)
  if m is None:
    return None
  return m.start(), m.end()


def _anchor_verse_band(page: Page, block: Block, registry: Registry | None,
                       stats: dict[str, int]) -> None:
  """Split and anchor a verse-referenced band (NT convention) in place."""
  entries: list[ApparatusEntry] = []
  for ve in versegrammar.split_verse_entries(block.text):
    versegrammar.parse_verse_entry(ve)
    e = ApparatusEntry(
      raw=f"{ve.loc} {ve.raw}",
      source=ve.source_slice,
      anchor=Anchor(kind="verse", value=ve.loc),
      parsed_verse=ve if ve.parsed else None,
    )
    entries.append(e)
    stats["entries"] += 1
    resolved = False
    if ve.parsed:
      first_verse = re.split(r"[-–]", ve.loc.split(":")[-1])[0] \
        if ":" not in ve.loc else ve.loc.split(":")[1].split("-")[0]
      # the constituted text ARBITRATES between candidate lemma forms of a
      # noisy printed doublet: the first candidate found in the verse wins
      for cand in versegrammar.lemma_candidates(ve):
        for bi, tb in enumerate(page.blocks):
          if tb.layer not in (Layer.TEXT, Layer.HEADING):
            continue
          for wstart, wend in _verse_windows(tb.text, first_verse):
            span = _find_span_end(tb.text[wstart:wend], cand)
            if span is None:
              continue
            s, t = wstart + span[0], wstart + span[1]
            e.anchor.block_index, e.anchor.char_offset = bi, t
            e.anchor.digit_start = e.anchor.digit_end = t
            ve.resolved_lemma = tb.text[s:t]
            # a technical candidate form (char-level "§") never becomes
            # the lemma — the resolved text span is the lemma
            ve.lemma = ve.resolved_lemma if "§" in cand else cand
            resolved = True
            break
          if resolved:
            break
        if resolved:
          break
    if resolved:
      stats["anchored"] += 1
    else:
      stats["unanchored"] += 1
    if registry is not None and ve.parsed:
      sigla = {*ve.lemma_sigla, *(s for r in ve.readings for s in r.sigla)}
      for s in sigla:
        registry.witnesses.setdefault(
          s, versegrammar.EDITION_WITNESSES.get(s, s))
  block.entries = entries


def _refuse_verse_band(block: Block, stats: dict[str, int],
                       evidence: str) -> None:
  """Keep a verse-shaped foreign band split but wholly verbatim."""
  entries: list[ApparatusEntry] = []
  for ve in versegrammar.split_verse_entries(block.text):
    entries.append(ApparatusEntry(
      raw=f"{ve.loc} {ve.raw}",
      source=ve.source_slice,
      anchor=Anchor(kind="verse", value=ve.loc),
      refusal_evidence=evidence,
    ))
    stats["entries"] += 1
    stats["unanchored"] += 1
  block.entries = entries


def _hyphen_rx(words: list[str]) -> re.Pattern:
  """Word-sequence pattern tolerating printed LINE-BREAK HYPHENATION inside
  any word ("stipendi- umque" must match "stipendiumque"), MARGINAL LINE
  NUMBERS caught inside the text flow ("uacuas 15 in celeberrimis",
  "proficis- 10 ceretur" — the constituted text numbers its lines; Latin
  prose itself uses Roman numerals, so 1-3 arabic digits between words
  are layout, not content) and the usual inter-word typography."""
  def char_pat(ch: str) -> str:
    # an em-dash inside a lemma word may close its printed line
    # ("natura—⏎namque"): whitespace after it is layout
    return re.escape(ch) + (r"\s*" if ch in "—–" else "")

  def word_pat(w: str) -> str:
    return r"(?:-\s+(?:\d{1,3}\s+)?)?".join(char_pat(ch) for ch in w)
  ws = [w.strip(".,;·:!?»«") for w in words]
  # a section number may print GLUED to the next word ("6Pugnabatur")
  joiner = r"[\s.,;·:!?—–]+(?:\d{1,3}[\s.,;·:!?]*)*"
  return re.compile(joiner.join(word_pat(w) for w in ws if w))


def _search_line_lemma(lemma: str, text: str,
                       start_at: int) -> re.Match | None:
  """Locate a lemma in the constituted text, degrading gracefully when
  its tail is hyphenated onto the NEXT page ("dabatur uic-⏎"): drop
  trailing words, then shorten the first word to a prefix — a partial
  match must still cover at least five characters."""
  words = lemma.split()

  def hit(ws: list[str]) -> re.Match | None:
    rx = _hyphen_rx(ws)
    m = rx.search(text, start_at)
    if m is None and start_at:
      m = rx.search(text)
    if m is not None and m.end() - m.start() >= (5 if ws != words else 0):
      return m
    return None

  if (m := hit(words)) is not None:
    return m
  for cut in range(len(words) - 1, -1, -1):
    head = words[:cut]
    w = words[cut].strip(".,;·:!?»«⟨⟩[]†")
    for plen in range(len(w) - 1, 3, -1):
      if (m := hit([*head, w[:plen]])) is not None:
        return m
    if head and (m := hit(head)) is not None:
      return m
  return None


def _anchor_line_band(page: Page, block: Block, registry: Registry | None,
                      stats: dict[str, int]) -> None:
  """Split and anchor a line-referenced band (reledmac convention) in
  place. Anchors resolve by CONTENT: each entry's first reading (the
  accepted text) is located in the page's constituted text at a
  monotonically advancing position; the printed line number travels on
  the anchor value."""
  entries: list[ApparatusEntry] = []
  cursors: dict[int, int] = {}
  for le in linegrammar.split_line_entries(block.text):
    if registry is not None:
      linegrammar.parse_line_entry(le, registry)
    prefix = f"{le.line} " if le.line else ""
    e = ApparatusEntry(
      raw=f"{prefix}{'◊ ' if le.crux else ''}{le.raw}",
      source=le.source_slice,
      anchor=Anchor(kind="line", value=le.line),
      parsed_line=le if le.parsed else None,
    )
    entries.append(e)
    stats["entries"] += 1
    resolved = False
    if le.parsed and le.lemma:
      for bi, tb in enumerate(page.blocks):
        if tb.layer not in (Layer.TEXT, Layer.HEADING):
          continue
        start_at = cursors.get(bi, 0)
        m = _search_line_lemma(le.lemma, tb.text, start_at)
        if m is None:
          continue
        e.anchor.block_index, e.anchor.char_offset = bi, m.end()
        e.anchor.digit_start = e.anchor.digit_end = m.end()
        le.resolved_lemma = tb.text[m.start(): m.end()]
        cursors[bi] = m.start() + 1
        resolved = True
        break
    if resolved:
      stats["anchored"] += 1
    else:
      stats["unanchored"] += 1
  block.entries = entries


def _refuse_line_band(block: Block, stats: dict[str, int],
                      evidence: str) -> None:
  """Keep a line-shaped foreign band split but wholly verbatim."""
  entries: list[ApparatusEntry] = []
  for le in linegrammar.split_line_entries(block.text):
    prefix = f"{le.line} " if le.line else ""
    entries.append(ApparatusEntry(
      raw=f"{prefix}{'◊ ' if le.crux else ''}{le.raw}",
      source=le.source_slice,
      anchor=Anchor(kind="line", value=le.line),
      refusal_evidence=evidence,
    ))
    stats["entries"] += 1
    stats["unanchored"] += 1
  block.entries = entries


def _anchor_paragraph_band(page: Page, block: Block, registry: Registry,
                           stats: dict[str, int]) -> None:
  """Split and anchor a paragraphed-reledmac band (juxtaposed entries,
  ``NUM lemma] readings``) in place. On a DOUBLE apparatus the fontium
  tier precedes the first entry boundary and stays one verbatim note."""
  entries: list[ApparatusEntry] = []
  cursors: dict[int, int] = {}
  preamble, pentries = paragraphgrammar.split_paragraph_entries(block.text)
  if preamble:
    entries.append(ApparatusEntry(raw=" ".join(preamble.split()), source=preamble))
    stats["entries"] += 1
    stats["unanchored"] += 1
  for pe in pentries:
    paragraphgrammar.parse_paragraph_entry(pe, registry)
    e = ApparatusEntry(
      raw=pe.raw,
      source=pe.source_slice,
      anchor=Anchor(kind="line", value=pe.line),
      parsed_paragraph=pe if pe.parsed else None,
    )
    entries.append(e)
    stats["entries"] += 1
    resolved = False
    if pe.parsed and pe.lemma:
      for bi, tb in enumerate(page.blocks):
        if tb.layer not in (Layer.TEXT, Layer.HEADING):
          continue
        start_at = cursors.get(bi, 0)
        m = _search_line_lemma(pe.lemma, tb.text, start_at)
        if m is None:
          continue
        e.anchor.block_index, e.anchor.char_offset = bi, m.end()
        e.anchor.digit_start = e.anchor.digit_end = m.end()
        cursors[bi] = m.start() + 1
        resolved = True
        break
    if resolved:
      stats["anchored"] += 1
    else:
      stats["unanchored"] += 1
  block.entries = entries


def _refuse_paragraph_band(block: Block, stats: dict[str, int],
                           evidence: str) -> None:
  """Keep paragraph boundaries for review, without claiming structure."""
  entries: list[ApparatusEntry] = []
  preamble, pentries = paragraphgrammar.split_paragraph_entries(block.text)
  if preamble:
    entries.append(ApparatusEntry(
      raw=" ".join(preamble.split()), source=preamble,
      refusal_evidence=evidence,
    ))
    stats["entries"] += 1
    stats["unanchored"] += 1
  for pe in pentries:
    entries.append(ApparatusEntry(
      raw=pe.raw,
      source=pe.source_slice,
      anchor=Anchor(kind="line", value=pe.line),
      refusal_evidence=evidence,
    ))
    stats["entries"] += 1
    stats["unanchored"] += 1
  block.entries = entries


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
    if versegrammar.looks_verse_referenced(block.text):
      decision = versegrammar.gate_verse_band(block.text)
      if decision.accepted:
        _anchor_verse_band(page, block, registry, stats)
      else:
        _refuse_verse_band(block, stats, decision.evidence)
      continue
    if linegrammar.looks_line_referenced(block.text):
      if registry is None:
        _refuse_line_band(
          block, stats,
          "line convention gate refused band: no registry is available "
          "for a trial parse",
        )
      else:
        decision = linegrammar.gate_line_band(block.text, registry)
        if decision.accepted:
          _anchor_line_band(page, block, registry, stats)
        else:
          _refuse_line_band(block, stats, decision.evidence)
      continue
    if registry is not None and \
       paragraphgrammar.looks_paragraph_referenced(block.text):
      decision = paragraphgrammar.gate_paragraph_band(block.text, registry)
      if decision.accepted:
        _anchor_paragraph_band(page, block, registry, stats)
      else:
        _refuse_paragraph_band(block, stats, decision.evidence)
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
    resolved_markers = sum(
      entry.anchor is not None and entry.anchor.kind == "marker"
      and entry.anchor.block_index is not None
      for entry in block.entries
    )
    decision = gate_marker_band(block.entries, registry, resolved_markers)
    if decision.accepted:
      for entry in block.entries:
        if entry.anchor is not None and entry.anchor.kind == "marker":
          entry.marker_eligible = True
        else:
          entry.refusal_evidence = (
            "marker convention gate excluded entry: it was not produced by "
            "a numeric-marker boundary"
          )
    else:
      for entry in block.entries:
        entry.refusal_evidence = decision.evidence
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
