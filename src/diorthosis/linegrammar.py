"""Line-referenced apparatus grammar — the reledmac/Teubner-family
convention, as printed by the DLL editions::

    5 cotidie operibus USTV | cotidie M (cf. BC 3.112.9) | nouis cotidie
    operibus Castiglioni ∥ 7 aptantur MUSTV | temptantur Nipperdey ∥
    per foramina MU | foramina STV ∥ 19 ◊ ⟨et hanc⟩ et illam scripsimus |
    et illa in urbe MU | …

- entries are ``∥``-separated; an entry opens with the marginal LINE
  number of the constituted text (``5``, ``11–12``) or with none (same
  line as the previous entry — the number is inherited);
- ``|`` separates readings; the FIRST reading is the accepted text (the
  lemma), with its own attribution;
- witness sigla print GLUED (``MUSTV``, ``USTcV``): they are segmented
  against the registry, longest siglum first (``Tc`` before ``T``), and
  only when the whole token dissolves into declared sigla;
- ``◊`` marks an entry with an editorial intervention (kept as a
  qualifier); attribution latinity (``teste X``, ``coll.``, editorial
  brackets, ``(cf. …)`` commentary) is the shared grammar lexicon.

Contract as everywhere: parse only what the convention defines, refuse
verbatim, lose nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .conspectus import Registry
from .grammar import QUALIFIERS, Attribution, _split_attribution

_LINE_NUM = re.compile(
  r"^(\d{1,3}(?:\.\d{1,3})?(?:[-–]\d{1,3}(?:\.\d{1,3})?)?)$")

_RELATIVE = re.compile(
  r",?\s+(?:quos|qui|quae|quod|cuius|quibus|quem|quam|quas|qua|ubi|ut)"
  r"\b.*$")
"""A Latin relative clause after the reading is editorial narrative
(", quos secutus foramina seclusit Vielhaber ut glossema"): commentary."""

_REF_TAIL = re.compile(
  r"(?<=\s)(?:coll\.|testibus|teste|u\.|cf\.|ut\s+glossema|uoc(?:e|ibus)|"
  r"ex(?=\s+\d))(?:\s|$)")
"""From ``coll.``/``u.``/``teste``/``cf.``/``ut glossema``/``uoce`` to the
end of the segment is citation narrative ("coll. Plin. Nat. 10.93",
"teste Oudendorp fortasse recte", "uoce uictis infra seruata"):
commentary, never part of the reading or its attribution."""

_NARRATIVE_TAIL = re.compile(
  r",?\s+\S+\s+(?:infra|supra)\s+(?:sequens|secutus|sequitur|seruat\w*)"
  r"\b.*$")
"""``Manutium infra sequens``-style narrative after the attribution."""

_LACUNA_TAIL = re.compile(r",?\s+quam\s+lacunam\b.*$")
"""``quam lacunam e.g. ⟨…⟩ suppleuerimus`` — how the editor would fill
the lacuna: narrative, with or without the comma."""

_AN_TAIL = re.compile(r"\s+an\s+\S+ndum\b.*$")
"""``an secludendum ut glossema (…)?`` after the attribution — a
dubitative editorial action (gerundive), not a variant reading."""

_ALII_NARRATIVE = re.compile(r"\S+\s+ali[oa]s\s+alii$")
"""``numeros alios alii`` — the alii-alia family with an object: some
give other numbers. Whole-segment narrative."""

_NISI_MAUIS = re.compile(
  r"(\S+)\s*(\([^)]*\))?(?:\s+uel\s+(\S+)\s*(\([^)]*\))?)?")
"""``nisi mauis X (…) [uel Y (…)]`` — dubitative conjectures when X/Y are
bare forms; a whole-segment note when the tail is an action ("nisi mauis
casum secludere")."""

_FINAL_PAREN = re.compile(r"\((?:[^()])*\)[\s?.,;]*$")
"""A parenthesis closing the segment (after the attribution) is a note;
one BEFORE the attribution ("qui (sc. Alexandrini) Cellarius") qualifies
the reading itself and stays inline — the golden encodings draw exactly
this line, whatever the paren's content."""


@dataclass
class LineReading:
  text: str
  attribution: Attribution


@dataclass
class LineEntry:
  line: str
  """Marginal line number as printed ('5', '11–12'); '' when inherited."""
  raw: str
  """The printed entry, verbatim (without the leading number)."""
  lemma: str = ""
  lemma_attribution: Attribution | None = None
  readings: list[LineReading] = field(default_factory=list)
  comments: list[str] = field(default_factory=list)
  crux: bool = False
  parsed: bool = False
  resolved_lemma: str = ""


def looks_line_referenced(band_text: str) -> bool:
  """Signature of the convention: the ``∥`` entry separator with ``|``
  reading separators."""
  flat = " ".join(band_text.split())
  return "∥" in flat and " | " in flat


def burst_sigla(words: list[str], registry: Registry) -> list[str]:
  """Split glued sigla tokens (``MUSTV`` -> M U S T V; ``USTcV`` -> U S Tc
  V) against the registry, longest siglum first. A token is only burst
  when it dissolves COMPLETELY into declared sigla — anything else is
  text and stays whole."""
  sigla = sorted(registry.witnesses, key=len, reverse=True)
  if not sigla:
    return words
  out: list[str] = []
  for w in words:
    bare = w.rstrip(".,;:")
    if len(bare) < 2 or not re.fullmatch(r"[A-Za-zΑ-Ωα-ωϘ-ϡ*]+", bare):
      out.append(w)
      continue
    parts: list[str] = []
    rest = bare
    while rest:
      for s in sigla:
        if rest.startswith(s):
          parts.append(s)
          rest = rest[len(s):]
          break
      else:
        parts = []
        break
    if len(parts) >= 2:
      suffix = w[len(bare):]           # trailing punctuation, if any
      if suffix:
        parts[-1] += suffix
      out.extend(parts)
    else:
      out.append(w)
  return out


_UNSEPARATED = re.compile(
  r"(\d+\.\d+|[)?]\??)\s+(?=\d{1,3}(?:[-–]\d{1,3})?\s+\S)")
"""The one place this convention omits ``∥``: after an entry that ends
with a parenthesized note, a dubitative ``?`` or a bare locus reference
("sed cf. 57.6"), the closing sign itself separates and the next entry
opens directly with its line number."""


def _split_unseparated(chunk: str) -> list[str]:
  """Split a ``∥``-chunk at ``) NUM …`` boundaries — only at paren depth
  zero (line numbers inside parentheses are page references, not entries)."""
  parts: list[str] = []
  start = 0
  for m in _UNSEPARATED.finditer(chunk):
    depth = chunk[:m.end(1)].count("(") - chunk[:m.end(1)].count(")")
    if depth == 0:
      parts.append(chunk[start:m.end(1)])
      start = m.end()
  parts.append(chunk[start:])
  return parts


def split_line_entries(band_text: str) -> list[LineEntry]:
  """Split a line-referenced band into entries, verbatim."""
  flat = " ".join(band_text.split())
  entries: list[LineEntry] = []
  current_line = ""
  for chunk in (p for c in flat.split("∥") for p in _split_unseparated(c)):
    chunk = chunk.strip()
    if not chunk:
      continue
    words = chunk.split()
    line = ""
    if words and _LINE_NUM.match(words[0]):
      line = words[0]
      current_line = line
      words = words[1:]
    else:
      line = ""  # inherited: same text line as the previous entry
    crux = False
    if words and words[0] == "◊":
      crux = True
      words = words[1:]
    raw = " ".join(words)
    if raw:
      entries.append(LineEntry(
        line=line or current_line, raw=raw, crux=crux))
  return entries


def parse_line_entry(entry: LineEntry, registry: Registry) -> LineEntry:
  """Parse ``LEMMA ATTR | reading ATTR | …`` in place, verbatim-preserving.

  Refusal (``parsed`` stays False) when the first segment dissolves into
  attribution with no text, or a middle segment is empty."""
  comments: list[str] = []
  # split on SPACED pipes only: "in|directam" is a typographic division
  # mark inside a reading, not a separator
  segments = [s.strip()
              for s in re.split(r"(?<=\s)\|(?=\s)", " " + entry.raw + " ")]
  if not segments or not segments[0]:
    return entry
  spaced_editors = [n for n in registry.editors if " " in n]
  sides: list[tuple[str, Attribution]] = []
  for idx, seg in enumerate(segments):
    seg_c0 = len(comments)
    for name in spaced_editors:
      if name in seg:
        seg = seg.replace(name, name.replace(" ", ""))
    if idx > 0 and seg.startswith("lacunam "):
      comments.append(seg)
      continue
    if idx > 0 and seg.startswith("nisi mauis "):
      rest = seg[len("nisi mauis "):].strip()
      conj: list[tuple[str, list[str]]] = []
      narrative = False
      for part in re.split(r"\s+uel\s+(?![^(]*\))", rest):
        pcs: list[str] = []
        mt = next((c for c in _REF_TAIL.finditer(part)
                   if part[: c.start()].count("(")
                   == part[: c.start()].count(")")), None)
        if mt:
          pcs.append(part[mt.start():].strip())
          part = part[: mt.start()].rstrip()
        while (mp := _FINAL_PAREN.search(part)):
          pcs.append(mp.group(0).strip())
          part = part[: mp.start()].rstrip()
        if not part or part.split()[-1].endswith("re"):
          # an infinitive tail is an editorial ACTION ("casum
          # secludere"), not a proposed form
          narrative = True
          break
        conj.append((part, pcs))
      if narrative or not conj:
        comments.append(seg)
      else:
        for text, pcs in conj:
          attr = Attribution()
          attr.qualifiers.append("nisi mauis")
          sides.append((text, attr))
          comments.extend(pcs)
      continue
    if idx > 0 and _ALII_NARRATIVE.fullmatch(seg):
      comments.append(seg)
      continue
    if idx > 0 and any(
        seg[: m.start()].count("(") == seg[: m.start()].count(")")
        for m in re.finditer(r"\.\.\.|…", seg)):
      # an ellipsis at paren depth zero quotes a SPAN of the lemma
      # ("sed ... coniectura post dictitabat transposuit Landgraf 1889"):
      # transposition narrative — inside a citation paren it is quoted
      # source text and proves nothing
      comments.append(seg)
      continue
    if idx > 0 and seg.startswith(("transposu", "post ")) \
       and re.search(r"\btranspos", seg):
      # "post ortus transposuit Schiller 1889" — pure transposition
      # narrative; when a READING precedes ("… Klotz post facta
      # transposuerit") the editor-recovery below handles it instead
      comments.append(seg)
      continue
    m = _RELATIVE.search(seg)
    if m:
      # only when the clause follows the attribution — the word before
      # the comma is a witness, editor or editorial verb ("Cellarius, qui
      # Manutium infra sequitur"; "scripsimus, quam lacunam…"); a
      # comma-clause inside a sentence-length reading is the reading's
      # own text
      prev = seg[: m.start()].split()
      last = prev[-1].rstrip(".,;:") if prev else ""
      if registry.is_witness(last) or registry.is_editor(last) \
         or last in QUALIFIERS or last.endswith(")") \
         or len(burst_sigla([last], registry)) > 1:
        comments.append(m.group(0).lstrip(", "))
        seg = seg[: m.start()]
    m = _NARRATIVE_TAIL.search(seg)
    if m and not _NARRATIVE_TAIL.match(seg):
      comments.append(m.group(0).lstrip(", "))
      seg = seg[: m.start()]
    m = _LACUNA_TAIL.search(seg)
    if m:
      prev = seg[: m.start()].split()
      last = prev[-1].rstrip(".,;:") if prev else ""
      if registry.is_editor(last) or last in QUALIFIERS:
        comments.append(m.group(0).lstrip(", "))
        seg = seg[: m.start()]
    m = _AN_TAIL.search(seg)
    if m:
      comments.append(m.group(0).strip())
      seg = seg[: m.start()]
    m = re.search(r"\s+nisi\s+mauis\b.*$", seg)
    if m:
      comments.append(m.group(0).strip())
      seg = seg[: m.start()]
    # ablative-absolute narrative after the attribution: "compendiis
    # indicatis", "de compendio corrupto", "relicto inter palam et cum
    # spatio septem litterarum", "sensu repugnante"
    m = re.search(r",?\s+(?:de\s+)?(?:compendi(?:o|is)|relicto|sensu)\b.*$",
                  seg)
    if m:
      comments.append(m.group(0).strip(" ,"))
      seg = seg[: m.start()]
    # a page number glued to the editor with a comma ("Forchhammer,92")
    seg = re.sub(r"(?<=[A-Za-zà-öø-ÿ]),(?=\d)", " ", seg)
    # a paren BETWEEN words whose content is neither a scilicet/uel
    # gloss nor constituted text (capital opening) is a qualifier note:
    # "Marcus (per compendium) sibi usu S", "M (supra lineam) USTV"
    def _mid_paren(mm: re.Match) -> str:
      inner = mm.group(0)[1:-1].strip()
      if inner.startswith(("sc.", "uel", "per")) \
         or (inner and inner[0].isupper()):
        return mm.group(0)
      comments.append(mm.group(0))
      return " "
    seg = re.sub(r"(?<=\s)\((?:[^()])*\)(?=\s)", _mid_paren, seg)
    # the golden's own typos print an unbalanced citation tail
    # ("…MUSTV (u. App. … TLL 10.2.519.39–55)" with two closers): from
    # the first orphaned paren on, everything is citation narrative
    if seg.count("(") != seg.count(")") and "(" in seg:
      cut = seg.index("(")
      comments.append(seg[cut:].strip())
      seg = seg[:cut].rstrip()
    elif seg.count(")") > seg.count("("):
      # an orphaned closer left over from the golden's own typo: the
      # clause carrying it ("et, de notione …, TLL 10.2.519.39–55)")
      # is citation narrative
      m = re.search(r",?\s+(?:et,?\s+)?de\s+\S.*$", seg) \
          or re.search(r"\s*\).*$", seg)
      if m:
        comments.append(m.group(0).strip(" ,"))
        seg = seg[: m.start()]
    m = next((c for c in _REF_TAIL.finditer(seg)
              if seg[: c.start()].count("(") == seg[: c.start()].count(")")),
             None)
    if m:
      comments.append(seg[m.start():].strip())
      seg = seg[: m.start()]
    while (mp := _FINAL_PAREN.search(seg)):
      comments.append(mp.group(0).strip())
      seg = seg[: mp.start()].rstrip()
    words = burst_sigla(seg.split(), registry)
    i = next((k for k, w in enumerate(words)
              if w == "uel" and k > 0
              and words[k - 1].rstrip(".,;:") in registry.witnesses), None)
    if i is not None:
      comments.append(" ".join(words[i:]))
      words = words[:i]
    dubitative = False
    if words and words[0] == "an":
      if len(words) > 1 and words[1].rstrip("?").endswith("ndum"):
        # "an secludendum (ut glossema)?" — a dubitative editorial
        # ACTION (gerundive), not a proposed form: whole-segment note
        comments.append(seg)
        continue
      if any("u. supra" in c or "u. infra" in c or "u. et supra" in c
             for c in comments[seg_c0:]):
        # "an Medubrigenses (u. supra)?" — an internal cross-reference
        # to a proposal already made: a note, not a new conjecture
        comments.append(seg)
        continue
      dubitative = True
      words = words[1:]
      if words and words[-1] in ("?", "?."):
        words = words[:-1]
      elif words and words[-1].endswith("?"):
        words[-1] = words[-1].rstrip("?")
    text, attr = _split_attribution(" ".join(words), registry)
    if not attr.witnesses and not attr.editors and text:
      # end-anchored peeling fails when narrative follows the editor
      # ("…imprudentia Klotz post facta transposuerit"): recover by
      # splitting at the LAST known editor mid-segment
      w2 = text.split()
      idxs = [i for i, w in enumerate(w2)
              if 0 < i < len(w2) - 1
              and registry.is_editor(w.rstrip(".,;"))]
      if idxs:
        i = idxs[-1]
        text2, attr2 = _split_attribution(" ".join(w2[: i + 1]), registry)
        if not attr2.empty:
          comments.append(" ".join(w2[i + 1:]))
          text, attr = text2, attr2
    # a superscript occurrence number glued to its word ("eius1" = the
    # first of two eius on the line) marks WHICH occurrence, not text
    text = re.sub(r"(?<=[a-zA-Zà-öø-ÿ])[0-9](?=\s|$)", "", text)
    # a long lemma is closed by a reledmac "]" terminator — typography,
    # not text (balanced "[obiectis]" seclusion brackets stay)
    if text.endswith("]") and text.count("]") > text.count("["):
      text = text[:-1].rstrip()
    if dubitative:
      attr.qualifiers.insert(0, "an?")
    if "ed. pr." in attr.qualifiers:
      # the editio princeps is an attribution authority, not a manner
      attr.qualifiers.remove("ed. pr.")
      attr.editors.append("ed. pr.")
    sides.append((text, attr))
  lemma, lemma_attr = sides[0]
  if not lemma:
    return entry
  if entry.crux:
    lemma_attr.qualifiers.insert(0, "◊")
  entry.lemma = lemma
  entry.lemma_attribution = lemma_attr
  for t, a in sides[1:]:
    if not t and not a.witnesses and not a.editors:
      # a qualifier-only segment ("alii alia") is narrative, not a variant
      if a.qualifiers:
        comments.append(" ".join(a.qualifiers))
      continue
    entry.readings.append(LineReading(text=t, attribution=a))
  entry.comments = comments
  entry.parsed = True
  return entry
