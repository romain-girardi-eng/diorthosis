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
from .convention import GateDecision, token_count

# The technical lexicon of the apparatus latinity — series-independent core.
# Multi-word qualifiers must be matched before their prefixes.
# Core follows Maurer's list ("Commonest Abbreviations… Used in the
# Apparatus to a Classical Text", U. Dallas) and the LDLT witness-state
# vocabulary; series-local items (e.g. "prop.", Paradosis) are kept and
# marked in the series grammar docs. Multi-word entries match before their
# prefixes. First-person forms (scripsi, conieci…) denote the CURRENT
# editor — SC and Budé reserve them systematically for the edition's own
# interventions.
QUALIFIERS = (
  # placement / witness state
  "a. corr.", "p. corr.", "ex corr.", "a.c.", "p.c.", "in ras.", "a.r.",
  "p.r.", "in lit.", "sup. l.", "s.l.", "s.s.", "sscr.", "interl.",
  "in marg.", "i.m.", "mg.", "in textu", "in semicirculis", "ad calcem",
  "prima manu", "secunda manu", "m.1", "m.2", "ed. pr.",
  # editorial actions (third person)
  "add.", "coni.", "ci.", "cj.", "conj.", "corr.", "del.", "em.", "om.",
  "prop.", "secl.", "suppl.", "transp.", "transponendum", "iter.", "exp.",
  "dist.", "damn.", "susp.", "trai.", "praem.",
  # editorial actions (first person = the current editor); "ego"/"nos"
  # are NOT here — ordinary Latin pronouns a reading can consist of
  "scripsi", "scripsimus", "conieci", "coniecimus", "correxi", "correximus",
  "seclusi", "seclusimus", "addidi", "addidimus", "delevi", "delevimus",
  "deleui", "deleuimus", "supplevi", "supplevimus",
  # collectives and states
  "codd.", "cod.", "edd.", "ed.", "cett.", "rell.", "al.", "recc.", "dett.",
  "vett.", "vulg.", "lac.", "deest", "desunt", "v.l.", "vv.ll.",
  # citation latinity of the line-referenced series (Maurer/LDLT):
  # "teste Andrieu" (on X's testimony), "coll." (collato), "u." (uide),
  # "non male", "ut glossema", "alii alia", third-person verbs of the
  # editorial narrative
  # "alia", "recte", "male" as SINGLE tokens are ordinary Latin words a
  # reading can consist of — only the fixed editorial BIGRAMS qualify
  "teste", "coll.", "u.", "non male", "ut glossema", "glossema",
  "alii alia", "seclusit", "omisit", "secutus", "secuti",
  "indicavit", "indicavere", "addiderit", "defendit", "distinxit",
  "ut uidetur", "uidetur", "fortasse recte", "fortasse",
  "testibus", "dubitanter", "per compendia", "per compendium",
  "supra lineam", "supra linea", "feliciter", "ex compendio",
  # a witness leaving or rejoining the tradition ("hostes redit S":
  # S resumes after a lacuna)
  "redit", "desinit", "deficit", "incipit", "auctore",
  # discourse
  "sic", "vel", "et", "cf.", "Cf.", "ut vid.", "fort.", "vel sim.",
  "scripsit", "scripserunt", "legit",
)

# Discourse words are glue inside attributions but TEXT when nothing else
# would remain: an edition can perfectly well add the single word "et".
_DISCOURSE = frozenset({"sic", "vel", "et"})

# First-person editorial actions name the current editor as the authority for
# the constituted reading. They share the qualifier lexicon for recognition,
# but TEI must emit them through lemma/reading ``@source``, not silently retain
# them only in the verbatim note.
FIRST_PERSON_EDITORS = frozenset({
  "scripsi", "scripsimus", "conieci", "coniecimus", "correxi", "correximus",
  "seclusi", "seclusimus", "addidi", "addidimus", "delevi", "delevimus",
  "deleui", "deleuimus", "supplevi", "supplevimus",
})

# Latin connectors inside attribution runs ("edd. ab Otto", "coni. Marc. ex
# LXX"): consumable between known tokens, never meaningful alone.
CONNECTORS = frozenset({"ab", "a", "ex", "in", "cum", "apud", "ante", "post", "sine", "loco"})

# Source-text tokens attributions cite (versions, not witnesses or editors).
SOURCES = frozenset({"LXX", "MT", "Hebr.", "Vulg."})

# Trailing locus references ("I Apol. 50, 5", "Dial. 66, 2", "p. 106"):
# work abbreviations, Roman numerals, bare numbers with punctuation.
_REF_TOKEN = re.compile(
  r"^(?:[IVXL]+|\d+[,.:]?|\d{4}[a-z]|\d{4}[a-z]?[–-]\d{4}[a-z]?|"
  r"\d+(?:\.\d+)+|n\.\d+|p\.|Apol\.|Dial\.|Cor\.|"
  r"Gen\.|Ex\.|Ps\.|Is\.|Jer\.|Mt\.|Mc\.|Lc\.|Jn\.|Rom\.|Gal\.|Beitr\.,?|"
  r"BC|BG|BHisp|BAfr|BAlex|Hirt\.|Aen\.|Tac\.|Virg\.|Cic\.|Liv\.|Hist\.|"
  r"TLL)$"
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

  def known_attribution(token: str) -> bool:
    """Is this token itself attribution material? Used to decide whether a
    discourse word / trailing numeral is glue between attributions or the
    tail of the reading's own text."""
    if token in _STRAY_PUNCT:
      return True     # "Dial. 66, 3 ; 77, 2" — the ';' sits between loci
    bare = token.rstrip(",.;:")
    return bool(
      bare in CONNECTORS
      or any(v in QUALIFIERS or v in SOURCES for v in (token, bare, bare + "."))
      or registry.is_witness(bare) or registry.is_editor(bare)
      or registry.is_editor(bare + ".")
      or _REF_TOKEN.match(token.rstrip(",")) or _REF_TOKEN.match(bare)
    )

  def variants(token: str) -> tuple[str, ...]:
    """Matching forms of a raw token: as-is, stripped of trailing
    punctuation, and re-dotted (abbreviations keep their dot in the
    registry, but a sentence-final period may double as it). Re-dotting
    needs at least two letters: a bare "u" is a Latin word, not "u."."""
    bare = token.rstrip(",.;:")
    forms = (token, token.rstrip(","), bare)
    return forms + ((bare + ".",) if len(bare) > 1 else ())

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
    if tail in _STRAY_PUNCT and len(words) > 1:
      words.pop()  # detached punctuation left by parenthesis removal —
      # never the LAST word: a reading can BE a punctuation mark
    elif two in QUALIFIERS:
      attr.qualifiers.insert(0, two)
      del words[-2:]
      consumed_something()
    elif (q := lookup(tail, lambda v: v in QUALIFIERS)) is not None:
      # a discourse word is glue only BETWEEN attribution tokens; adjacent
      # to plain text it is the reading's own tail ("regnum et M U" reads
      # "regnum et", it is not qualified by "et")
      if q in _DISCOURSE and (
          len(words) == 1 or not known_attribution(words[-2])
          or words[-2].rstrip(",.;:") in _DISCOURSE
          or words[-2].rstrip(",.;:") in CONNECTORS):
        # a discourse word after another discourse word ("et sic") or a
        # bare connector ("a. et") is running Latin text, not glue
        break
      if q in FIRST_PERSON_EDITORS:
        attr.editors.insert(0, q)
      else:
        attr.qualifiers.insert(0, q)
      words.pop()
      consumed_something()
    elif (src := lookup(tail, lambda v: v in SOURCES)) is not None:
      attr.sources.insert(0, src)
      words.pop()
      consumed_something()
    elif _REF_TOKEN.match(tail_clean) and not registry.is_witness(tail_clean):
      # a PURE numeral after plain text is the reading's own tail
      # ("cohortibus XXX", "legioni XXXVIII" — the edition supplies the
      # number); after a work token it is a locus ("Dial. 66, 2"). Work
      # abbreviations themselves (letters) are always references.
      numeric_only = re.fullmatch(r"[IVXLCDM]+|\d+[,.:]?", tail_clean)
      if numeric_only and (len(words) == 1
                           or not known_attribution(words[-2])):
        break
      attr.references.insert(0, tail_clean)
      words.pop()
      consumed_something()
    elif (w := lookup(tail, registry.is_witness)) is not None:
      # a Roman-numeral siglum as the LAST remaining word is the text
      # itself, not a witness: in "V M U S T V" the head V is the numeral
      # the edition prints (five), attested by the five manuscripts
      if len(words) == 1 and re.fullmatch(r"[IVXLCDM]+", tail.rstrip(",.;:")):
        break
      attr.witnesses.insert(0, w.rstrip(",;"))
      words.pop()
      consumed_something()
    elif (ed := lookup(tail, registry.is_editor)) is not None:
      attr.editors.insert(0, ed.rstrip(",;"))
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


# Tokens that betray a FOREIGN apparatus convention (e.g. Göttingen
# Septuagint): an unbalanced "]" is another series' lemma separator; bare
# un-dotted operator keywords open its entries; numeric minuscule sigla and
# occurrence markers (78-569, 2°) are its witness system. Parsing such an
# entry with this grammar produced silent misattribution — refusal is the
# only honest output until a grammar for that series exists.
_FOREIGN_OPENER = re.compile(r"^(om|pr|tr|init|fin|hab)\s")
# Only the UNAMBIGUOUS foreign shapes: minuscule ranges (78-569) and
# occurrence markers (2°). Plain bare numerals stay legal in text —
# the home series quotes fragment and column numbers inline
# ("Fr. 102 Holl", "PG VI, 1580").
_FOREIGN_WITNESS = re.compile(r"^\d{1,4}-\d{1,4}°?$|^\d+°$")

# A marker band may contain one long narrative refusal among several short,
# resolved entries.  The token ceiling therefore combines with the 50%
# entry-consistency floor below.  Above 60%, the unconsumed material is the
# band, rather than an isolated honest miss, so the convention refuses it.
MARKER_MAX_UNCONSUMED_TOKEN_RATIO = 0.60


def _names_an_authority(attribution: Attribution) -> bool:
  """Does this attribution name WHO reads the segment?

  Witness sigla, editor abbreviations and cited text versions are the
  apparatus' evidence.  Qualifiers are deliberately excluded: "ed.", "cf.",
  "et", "sic" are ordinary prose words, and a footnote band full of them
  would otherwise look attributed.
  """
  return bool(attribution.witnesses or attribution.editors or attribution.sources)


def _looks_foreign(flat: str) -> bool:
  if flat.count("]") > flat.count("["):
    return True
  return bool(_FOREIGN_OPENER.match(flat))


def _residual_foreign_tokens(*texts: str) -> bool:
  for t in texts:
    for tok in t.split():
      if _FOREIGN_WITNESS.match(tok.strip(".,;:")):
        return True
  return False


def gate_marker_band(entries: list[object], registry: Registry | None,
                     resolved_markers: int) -> GateDecision:
  """Whole-band gate for the generic numeric-marker convention.

  ``entries`` are the output of ``anchor.split_entries``.  This function is
  intentionally unavailable as an entry-local shortcut: a numeric split and
  at least one resolved in-text marker are mandatory pipeline evidence.
  """
  grammar = "marker"
  marker_entries = [
    entry for entry in entries
    if entry.anchor is not None and entry.anchor.kind == "marker"
  ]
  if not marker_entries:
    return GateDecision.refuse(grammar, "numeric-marker entry splitting found no boundary")
  if resolved_markers < 1:
    return GateDecision.refuse(
      grammar, "0 numeric markers resolved against the text layer")
  band_text = " ".join(str(entry.source_slice) for entry in entries)
  if "||" in band_text:
    return GateDecision.refuse(grammar, "foreign separator '||' is not consumed")
  if "∥" in band_text:
    return GateDecision.refuse(grammar, "foreign separator '∥' is not consumed")
  unmatched_closers = max(0, band_text.count("]") - band_text.count("["))
  if unmatched_closers:
    return GateDecision.refuse(
      grammar,
      f"{unmatched_closers} unmatched ']' lemma separator(s) are not consumed",
    )
  if registry is None:
    return GateDecision.refuse(grammar, "no registry is available for a trial parse")
  trial = [parse_entry(str(entry.raw), registry) for entry in marker_entries]
  total_tokens = sum(token_count(str(entry.raw)) for entry in marker_entries)
  refused_tokens = sum(
    token_count(str(entry.raw))
    for entry, parsed in zip(marker_entries, trial, strict=True)
    if parsed is None
  )
  ratio = refused_tokens / max(total_tokens, 1)
  if ratio > MARKER_MAX_UNCONSUMED_TOKEN_RATIO:
    return GateDecision.refuse(
      grammar,
      f"trial parse left {ratio:.1%} of tokens unconsumed "
      f"(maximum {MARKER_MAX_UNCONSUMED_TOKEN_RATIO:.0%})",
    )
  parsed_count = sum(parsed is not None for parsed in trial)
  if parsed_count * 2 < len(marker_entries):
    return GateDecision.refuse(
      grammar,
      f"only {parsed_count}/{len(marker_entries)} marker entries parsed in trial "
      "(minimum 50%)",
    )
  # An apparatus criticus records WHO reads WHAT: somewhere in the band a
  # proposed variant must name a witness, an editor or a cited version.
  # Numbered prose — editorial footnotes, fontes paragraphs, translators'
  # notes — carries the same superscript numbering and the same ": " as the
  # convention, so shape alone cannot tell them apart; the printed sigla can.
  # This is a WHOLE-BAND floor on purpose.  A single entry may stay bare:
  # editions collated against one witness print their readings without a
  # siglum by design, and refusing them entry by entry cost the reference
  # edition 6 points of parse rate (99.0 -> 93.0, review adjudication).
  readings = [reading for parsed in trial if parsed is not None
              for reading in parsed.readings]
  if not any(_names_an_authority(reading.attribution) for reading in readings):
    return GateDecision.refuse(
      grammar,
      f"no witness, editor or source is named on any of the {len(readings)} "
      f"reading(s) proposed by {parsed_count}/{len(marker_entries)} trial-parsed "
      "entries — a numbered prose band, not a variant apparatus",
    )
  return GateDecision.accept(grammar)


def parse_entry(raw: str, registry: Registry) -> ParsedEntry | None:
  """Parse one apparatus entry, or return None when its shape is not ours.

  Refusal conditions are part of the design: no colon (prose entry), a
  segment that empties after attribution peeling, or any sign of a FOREIGN
  series' conventions — a wrong structure is worse than no structure.
  """
  # printed line-break hyphenation inside the band ("An- drieu") is a
  # typographic artifact, rejoined before parsing (the verbatim note keeps
  # the printed form untouched)
  raw = re.sub(r"(?<=\w)-\s+(?=[a-zà-öø-ÿα-ω])", "", raw)
  comments: list[str] = []

  def _classify_paren(m: re.Match) -> str:
    # A parenthetical is COMMENTARY when it carries technical apparatus
    # material — digits (loci), an equivalence ("= …"), a cited source, an
    # editor, an operator or placement qualifier, a leading Latin connector
    # ("ex …" = derivation), or a segment separator. A plain-prose
    # parenthetical ("(uel ex)", "(sc. Alexandrini)", "(t/c)") is part of
    # the reading and stays in the text.
    content = m.group(0)[1:-1].strip()
    if re.search(r"\d", content) or " : " in content or content.startswith("="):
      comments.append(m.group(0))
      return " "
    toks = content.split()
    if len(toks) >= 2 and toks[0].rstrip(".,;:·") in CONNECTORS:
      comments.append(m.group(0))
      return " "
    if any(q in content for q in QUALIFIERS
           if " " in q and not q.startswith("per ")):
      # "per compendium"-type manner glosses qualify the reading itself —
      # the golden encodings keep them inline
      comments.append(m.group(0))
      return " "
    for tok in (t.strip(".,;:·") for t in toks):
      if (tok in SOURCES or registry.is_editor(tok) or registry.is_editor(tok + ".")
          or (tok + ".") in QUALIFIERS or tok in ("om", "add", "del", "cf")):
        comments.append(m.group(0))
        return " "
    return m.group(0)

  flat = _PAREN.sub(_classify_paren, raw)
  # an unclosed parenthesis means the entry was cut at a page boundary:
  # everything from the dangling "(" is commentary, kept verbatim
  m_open = re.search(r"\([^)]*$", flat)
  if m_open:
    comments.append(m_open.group(0))
    flat = flat[: m_open.start()]
  flat = re.sub(r"\s+", " ", flat).strip()
  if _looks_foreign(flat):
    return None
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

  # bare numerals are locus references ONLY in the company of a work token
  # ("Dial. 66, 2"); alone they are another series' numeric sigla
  for attr in (lemma_attr, *(r.attribution for r in readings)):
    # bare numerals with a cross-reference qualifier ("cf. 62, 2") are a
    # locus in the home series; without any such context they are another
    # series' numeric sigla
    if (attr.references and "cf." not in attr.qualifiers and not any(
        re.search(r"[A-Za-z]", ref) for ref in attr.references)):
      return None
  if _residual_foreign_tokens(lemma, *(r.text for r in readings)):
    return None
  # NOTE (review adjudication): a bare "lemma : reading" without any
  # attribution is NOT refused here. In the marker-anchored convention
  # the structural evidence is the anchored superscript marker, and
  # single-witness editions print manuscript readings bare by design
  # (Bobichon's codex A: ~121 legitimate entries, parse 99.0->93.0 when
  # this refusal was tried). The attribution-based refusals live in the
  # verse/line/paragraph grammars, where sigla ARE the structure.
  return ParsedEntry(
    lemma=lemma, lemma_attribution=lemma_attr,
    readings=readings, comments=comments,
  )
