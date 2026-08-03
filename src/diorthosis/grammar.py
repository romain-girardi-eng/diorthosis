"""Apparatus entry parsing — per-series grammar, honest fallback.

An apparatus entry in the reference series (Paradosis) reads::

    Μωσέως : Μωϋσέως Mign., Otto, Goodsp. (hic et infra : 45, 3)

structure: ``LEMMA [attribution] : READING [attribution] [: READING …]``
where an attribution is a run of witness sigla (``A``, ``B1``), editor
abbreviations (``Mign.``, ``Otto``) and technical qualifiers (``prop.``,
``coni.``, ``ut vid.``, ``codd.``…). Parenthesized material is commentary
and stays attached to its segment verbatim.

The contract of this module:

- **parse only what the grammar recognizes** — an entry whose shape does not
  fit returns ``None`` and the caller keeps it as a verbatim note. A wrong
  structure is worse than no structure;
- **lose nothing** — the parsed form is emitted *alongside* the verbatim
  text, never instead of it;
- the vocabulary (witnesses, editors) comes from the edition's own
  conspectus siglorum, plus the series' technical lexicon below.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .conspectus import Registry

# The technical lexicon of the apparatus latinity — series-independent core.
# Multi-word qualifiers must be matched before their prefixes.
QUALIFIERS = (
  "a. corr.", "p. corr.", "ex corr.", "sup. l.", "in marg.", "in textu",
  "in semicirculis", "ut vid.", "ad calcem", "prima manu", "secunda manu",
  "add.", "coni.", "corr.", "del.", "om.", "prop.", "secl.", "transp.",
  "transponendum", "iter.", "codd.", "cod.", "edd.", "ed.", "cett.", "al.",
  "sic", "vel", "et", "ego", "scripsit", "scripserunt", "legit",
)

# Latin connectors inside attribution runs ("edd. ab Otto", "coni. Marc. ex
# LXX"): consumable between known tokens, never meaningful alone.
CONNECTORS = frozenset({"ab", "a", "ex", "in", "cum", "apud", "ante", "post", "sine", "loco"})

# Source-text tokens attributions cite (versions, not witnesses or editors).
SOURCES = frozenset({"LXX", "MT", "Hebr.", "Vulg."})

# Trailing locus references ("I Apol. 50, 5", "Dial. 66, 2", "p. 106"):
# work abbreviations, Roman numerals, bare numbers with punctuation.
_REF_TOKEN = re.compile(
  r"^(?:[IVXL]+|\d+[,.:]?|p\.|Apol\.|Dial\.|Cor\.|Gen\.|Ex\.|Ps\.|Is\.|Jer\.|"
  r"Mt\.|Mc\.|Lc\.|Jn\.|Rom\.|Gal\.|Beitr\.,?)$"
)
_STRAY_PUNCT = frozenset({",", ";", ":", ".", "·"})

_PAREN = re.compile(r"\([^)]*\)")


@dataclass
class Attribution:
  witnesses: list[str] = field(default_factory=list)
  editors: list[str] = field(default_factory=list)
  qualifiers: list[str] = field(default_factory=list)
  sources: list[str] = field(default_factory=list)
  """Cited text versions (LXX, MT…)."""
  references: list[str] = field(default_factory=list)
  """Trailing locus citations, verbatim tokens in original order."""

  @property
  def empty(self) -> bool:
    return not (self.witnesses or self.editors or self.qualifiers
                or self.sources or self.references)


@dataclass
class Reading:
  text: str
  attribution: Attribution


@dataclass
class ParsedEntry:
  lemma: str
  lemma_attribution: Attribution
  readings: list[Reading]
  comments: list[str]
  """Parenthesized commentary, verbatim, in order of appearance."""


def _split_attribution(segment: str, registry: Registry) -> tuple[str, Attribution]:
  """Peel witnesses / editors / qualifiers off the END of a segment.

  The reading text comes first, its attribution trails it; we consume known
  tokens from the right until an unknown token stops us. Whatever remains is
  the reading text — untouched.
  """
  attr = Attribution()
  words = segment.split()
  pending_connectors: list[str] = []

  def variants(token: str) -> tuple[str, ...]:
    """Matching forms of a raw token: as-is, stripped of trailing
    punctuation, and re-dotted (abbreviations keep their dot in the
    registry, but a sentence-final period may double as it)."""
    bare = token.rstrip(",.;:")
    return (token, token.rstrip(","), bare, bare + ".")

  def lookup(token: str, pred) -> str | None:
    for v in variants(token):
      if pred(v):
        return v
    return None

  def consumed_something() -> None:
    pending_connectors.clear()

  while words:
    tail = words[-1]
    tail_clean = tail.rstrip(",")
    two = " ".join(words[-2:]).rstrip(",") if len(words) >= 2 else ""
    if tail in _STRAY_PUNCT:
      words.pop()  # detached punctuation left by parenthesis removal
    elif two in QUALIFIERS:
      attr.qualifiers.insert(0, two)
      del words[-2:]
      consumed_something()
    elif (q := lookup(tail, lambda v: v in QUALIFIERS)) is not None:
      attr.qualifiers.insert(0, q)
      words.pop()
      consumed_something()
    elif (src := lookup(tail, lambda v: v in SOURCES)) is not None:
      attr.sources.insert(0, src)
      words.pop()
      consumed_something()
    elif _REF_TOKEN.match(tail_clean) and not registry.is_witness(tail_clean):
      attr.references.insert(0, tail_clean)
      words.pop()
      consumed_something()
    elif (w := lookup(tail, registry.is_witness)) is not None:
      attr.witnesses.insert(0, w)
      words.pop()
      consumed_something()
    elif (ed := lookup(tail, registry.is_editor)) is not None:
      attr.editors.insert(0, ed)
      words.pop()
      consumed_something()
    elif tail_clean in CONNECTORS:
      # only consumable if something known follows it (already peeled);
      # a connector adjacent to unknown text belongs to that text
      if attr.empty:
        break
      pending_connectors.append(tail_clean)
      words.pop()
    else:
      break
  # connectors peeled but never followed by a known token belong to the text
  if pending_connectors:
    words.extend(reversed(pending_connectors))
  return " ".join(words).strip(), attr


def parse_entry(raw: str, registry: Registry) -> ParsedEntry | None:
  """Parse one apparatus entry, or return None when its shape is not ours.

  Refusal conditions are part of the design: no colon (prose entry), or a
  lemma/reading segment that ends up empty after attribution peeling —
  both mean the entry does not follow the LEMMA : READING convention.
  """
  # mid-word parentheses hold editorial letters — Κατα(να)θεματίζοντας —
  # and belong to the word; only space-preceded parentheticals are commentary
  raw = re.sub(r"(?<=\S)\((\S+?)\)", r"\1", raw)
  comments = _PAREN.findall(raw)
  flat = _PAREN.sub(" ", raw)
  # an unclosed parenthesis means the entry was cut at a page boundary:
  # everything from the dangling "(" is commentary, kept verbatim
  m_open = re.search(r"\([^)]*$", flat)
  if m_open:
    comments.append(m_open.group(0))
    flat = flat[: m_open.start()]
  flat = re.sub(r"\s+", " ", flat).strip()
  # "corr. ex" introduces the pre-correction reading: a segment boundary,
  # with the operator recorded on the reading it introduces
  flat = flat.replace(" corr. ex ", " : corr. ex ")

  if " : " not in flat:
    # no variant: an editorial action on the lemma alone
    # ("Τοὺς add. sup. l. A1.", "Πάντοτε − Χριστοῦ in semicirculis Marc.").
    # Transpositions carry a target argument: "Κατὰ − βουλὴν post εἰς τὸν
    # transponendum Thirlb." — the operator and its Greek argument are a
    # qualifier, not part of the lemma.
    op = re.search(r"\s(post|ante)\s", flat)
    op_qualifier = None
    if op:
      head_part, arg_part = flat[: op.start()], flat[op.end():]
      arg, attr = _split_attribution(arg_part, registry)
      if not attr.empty:
        op_qualifier = f"{op.group(1)} {arg}".strip()
        lemma, lemma_attr = _split_attribution(head_part, registry)
        # merge: operator argument first, then the peeled technicals
        attr.qualifiers.insert(0, op_qualifier)
        attr.witnesses[:0] = lemma_attr.witnesses
        attr.editors[:0] = lemma_attr.editors
        attr.qualifiers[:0] = lemma_attr.qualifiers
        if lemma:
          return ParsedEntry(
            lemma=lemma, lemma_attribution=attr, readings=[], comments=comments,
          )
    lemma, attr = _split_attribution(flat, registry)
    if lemma and not attr.empty:
      return ParsedEntry(
        lemma=lemma, lemma_attribution=attr, readings=[], comments=comments,
      )
    return None

  head, *rest = [seg.strip() for seg in flat.split(" : ")]
  lemma, lemma_attr = _split_attribution(head, registry)
  if not lemma:
    return None

  readings: list[Reading] = []
  for seg in rest:
    text, attr = _split_attribution(seg, registry)
    if not text and attr.empty:
      return None
    readings.append(Reading(text=text, attribution=attr))
  return ParsedEntry(
    lemma=lemma, lemma_attribution=lemma_attr,
    readings=readings, comments=comments,
  )
