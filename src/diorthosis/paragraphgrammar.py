"""Paragraphed line-referenced apparatus — the standard reledmac foot,
as printed by the LombardPress/scholastic editions::

    18 est] om. R 20 in] om. R SV S 20 Guillelmum] Guillelmi R
    25 super] supra V 15 considerabo] considera R SV considerata S
    79 contemptum] contentum V 79-80 erga se] ergo R erga S SV

- entries are JUXTAPOSED: no ``∥``, no ``|`` — a new entry opens with its
  marginal line number (or range) followed by a short lemma closed by
  ``]``; text before the first such boundary (the fontium tier of a
  double apparatus, "56-57 I Ad Corinthios 13:12") is not entry material
  and stays verbatim;
- readings inside an entry are ALSO juxtaposed: each one is
  ``TEXT? OPERATORS? WITNESSES`` and the next begins right after the
  witness run ends ("considera R SV considerata S" = two readings);
- operators follow the LombardPress print vocabulary: ``om.``,
  ``iterum``, ``in textu``, ``plus lectiones``, ``add.`` (+ ``interl.``
  / ``in marg.``), ``add. sed del.``, ``corr. ex`` (the pre-correction
  text after the operator belongs to the note, not the reading);
- a parenthesis right after a witness is a facsimile locus ("S (2r/21)")
  and is a note.

Contract as everywhere: parse only what the convention defines, refuse
verbatim, lose nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .conspectus import Registry
from .grammar import Attribution

_BOUNDARY = re.compile(
  r"(?:(?<=^)|(?<=\s))(\d{1,3}(?:[-–]\d{1,3})?)\s+([^\]]{1,120}?)\s*\]")
"""A line number (or range) + a short lemma + the closing ``]``."""

# operators, longest first so multi-word forms win
_OPERATORS = ("add. sed del.", "plus lectiones", "corr. ex", "in textu",
              "in marg.", "interl.", "add.", "om.", "iterum")

_FACS = re.compile(r"^\((?:[^()])*\)$")


@dataclass
class ParagraphReading:
  text: str
  attribution: Attribution
  comments: list[str] = field(default_factory=list)


@dataclass
class ParagraphEntry:
  line: str
  """Marginal line number as printed ('79', '79-80')."""
  raw: str
  """The printed entry, verbatim (number + lemma + ']' + readings)."""
  lemma: str = ""
  readings: list[ParagraphReading] = field(default_factory=list)
  comments: list[str] = field(default_factory=list)
  parsed: bool = False


def looks_paragraph_referenced(band_text: str) -> bool:
  """Signature of the convention: ``]``-closed lemmas after line numbers,
  WITHOUT the ``∥``/``|`` separators of the DLL family."""
  flat = " ".join(band_text.split())
  if "∥" in flat or " | " in flat or " : " in flat:
    return False
  return len(_BOUNDARY.findall(flat)) >= 2


_NOT_A_LEMMA = re.compile(r"\d+[:.]\d+|(?:^|\s)\d+(?:[-–]\d+)?(?:\s|$)")
"""A candidate lemma carrying a locus reference ("118:18") or a bare
number is fontium narrative, not an entry boundary."""


def split_paragraph_entries(band_text: str) -> tuple[str, list[ParagraphEntry]]:
  """(preamble, entries): the preamble is everything before the first
  entry boundary — on a double apparatus, the whole fontium tier."""
  flat = " ".join(band_text.split())
  # scan WITHOUT consumption: an invalid candidate ("15-16 Psalm 118:18
  # 1 Sententiarum ]" — fontium narrative swallowing a real boundary)
  # must not eat the genuine boundary hiding inside its span
  hits = []
  pos = 0
  while (m := _BOUNDARY.search(flat, pos)) is not None:
    # an ELLIPTIC lemma is always genuine, whatever its tail — the
    # ellipsis may swallow anything up to a closing locus reference
    # ("nam …52:1]"); the fontium guard only applies to full lemmas
    lemma_c = m.group(2)
    single_numeric = len(lemma_c.split()) == 1 and lemma_c.strip().isdigit()
    # an elliptic lemma may end with anything ("nam …52:1]") — but its
    # HEAD must still be clean, or fontium narrative rides in on the
    # ellipsis ("c. 1" + "139–141 Unde ….]")
    guard_zone = lemma_c.split("…")[0] if "…" in lemma_c else lemma_c
    if not single_numeric and _NOT_A_LEMMA.search(guard_zone):
      # a single numeric token IS a valid lemma (the constituted text
      # quotes a number: "20 ] vigesimo S") — the guard only screens
      # fontium narrative, which never carries the "]" closer
      pos = m.start() + len(m.group(1))
      continue
    hits.append(m)
    pos = m.end()
  if not hits:
    return flat, []
  preamble = flat[: hits[0].start()].strip()
  entries: list[ParagraphEntry] = []
  for i, m in enumerate(hits):
    end = hits[i + 1].start() if i + 1 < len(hits) else len(flat)
    entries.append(ParagraphEntry(
      line=m.group(1),
      raw=flat[m.start(): end].strip(),
    ))
  return preamble, entries


def _is_witness(tok: str, registry: Registry) -> bool:
  return registry.is_witness(tok.rstrip(".,;:"))


def _match_operator(words: list[str], i: int) -> str | None:
  for op in _OPERATORS:
    parts = op.split()
    if words[i: i + len(parts)] == parts:
      return op
  return None


def parse_paragraph_entry(entry: ParagraphEntry,
                          registry: Registry) -> ParagraphEntry:
  """Parse ``NUM LEMMA] reading reading …`` in place.

  Readings are recovered by scanning: text accumulates until an operator
  or a witness run; a reading CLOSES when its witness run ends and a
  non-witness token follows. Refusal (``parsed`` stays False) when no
  reading gets at least one witness — juxtaposition without witnesses is
  undecidable and stays verbatim."""
  m = _BOUNDARY.match(entry.raw)
  if m is None:
    return entry
  entry.lemma = m.group(2).strip()
  rest = entry.raw[m.end():].strip()
  words = rest.split()

  readings: list[ParagraphReading] = []
  cur_text: list[str] = []
  cur = ParagraphReading(text="", attribution=Attribution())
  in_wits = False
  post_op: str | None = None

  def close() -> None:
    nonlocal cur, cur_text, in_wits, post_op
    cur.text = " ".join(cur_text).strip()
    if cur.text or not cur.attribution.empty:
      readings.append(cur)
    cur = ParagraphReading(text="", attribution=Attribution())
    cur_text = []
    in_wits = False
    post_op = None

  i = 0
  while i < len(words):
    w = words[i]
    if in_wits and _FACS.match(w):
      # facsimile locus right after a witness ("S (2r/21)")
      cur.comments.append(w)
      i += 1
      continue
    if in_wits and not _is_witness(w, registry):
      close()
      continue          # re-examine w at the head of the next reading
    op = _match_operator(words, i)
    if op is not None:
      cur.attribution.qualifiers.append(op)
      i += len(op.split())
      if op == "corr. ex":
        # the pre-correction text up to the witness run is a note
        pre: list[str] = []
        while i < len(words) and not _is_witness(words[i], registry) \
              and _match_operator(words, i) is None:
          pre.append(words[i])
          i += 1
        if pre:
          cur.comments.append("corr. ex " + " ".join(pre))
      post_op = op
      continue
    if _is_witness(w, registry):
      bare = w.rstrip(".,;:")
      if bare in cur.attribution.witnesses:
        # a DUPLICATE siglum in one run: the earlier occurrence was
        # reading TEXT, not a witness (Roman numerals collide with
        # sigla). Which reading's text depends on where it sat:
        # - run-initial with nothing else on the reading ("I] V R SV
        #   S V") — it was THIS reading's text; fold it back in;
        # - otherwise ("VIII R SV S V V") — it opened the NEXT
        #   reading; close the current one without it.
        run_initial = (not cur_text and not cur.attribution.qualifiers
                       and cur.attribution.witnesses[0] == bare)
        cur.attribution.witnesses.remove(bare)
        if not run_initial:
          close()
        cur_text.append(bare)
      cur.attribution.witnesses.append(bare)
      in_wits = True
      i += 1
      continue
    if post_op is not None and post_op != "plus lectiones":
      # an operator closes its reading's text; any non-witness token
      # after it opens the NEXT reading (only "plus lectiones" takes
      # its variant list AFTER the operator)
      close()
      continue
    cur_text.append(w)
    i += 1
  close()

  # a trailing witness-less NUMERIC "reading" is the next entry's line
  # number, hyphen-split at a band line break and left behind by the
  # boundary scan — layout residue, not a variant
  while readings and not readings[-1].attribution.witnesses \
        and re.fullmatch(r"[\d\s–-]+", readings[-1].text or " "):
    readings.pop()

  if not any(r.attribution.witnesses or r.attribution.qualifiers
             for r in readings):
    # an operator alone still attests the structure (the source TEI
    # occasionally prints a witness-less "in textu" reading)
    return entry
  entry.readings = readings
  entry.parsed = True
  return entry
