"""TEI P5 emission — the canonical output, aligned with the Guidelines.

Follows chapter 13 ("Critical Apparatus") of TEI P5 ≥ 4.12:

- apparatus links use the **double-end-point-attached** method with
  ``location="internal"``: the printed superscript marker gives the END
  anchor; the lemma's start anchor is computed by matching the lemma against
  the text (when that match is not confident, the ``<app>`` carries only its
  end anchor — honesty over guessing). The mandatory ``<variantEncoding>``
  declaration is emitted whenever an ``<app>`` is present.
- manuscripts from the conspectus go to ``@wit`` (declared in ``<listWit>``
  with their siglum as ``<abbr type="siglum">``); editors go to ``@source``
  (declared in a ``<listBibl>``) — per 13.1.2, ``@source`` "indicates the
  scholar responsible for asserting the existence of that reading", the
  correct category for ``coni. Otto`` (``@resp`` would claim the *encoder's*
  responsibility).
- an omission (``om.``) is an EMPTY ``<rdg>`` (13.4); ``ut vid.`` becomes
  ``@cert="low"``; placement notes (``sup. l.``, ``in marg.``…) become
  ``<witDetail>``; everything else stays in the verbatim note — the exact
  wording of the source apparatus is always preserved (13.1.2).
- unparsed entries remain ``<note type="apparatus">`` — a form that needs no
  ``variantEncoding`` and loses nothing.

Provenance survives everywhere: OCR-generated blocks carry
``subtype="generative"`` and the header says what that means.
"""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from . import __version__
from .conspectus import Registry, builtin_editors
from .grammar import Attribution, ParsedEntry, Reading, parse_entry
from .model import Block, Document, Layer, Page
from .witnesses import decompose

TEI_NS = "http://www.tei-c.org/ns/1.0"

# codepoints XML 1.0 forbids in content (controls except \t\n\r; the
# FFFE/FFFF non-characters; surrogates are unrepresentable in str already)
_XML_INVALID = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")

# qualifiers that place a reading in the witness (13.1.4.1 <witDetail>)
_PLACEMENT = {"sup. l.", "s.l.", "in marg.", "i.m.", "in ras.", "a. corr.",
              "p. corr.", "a.c.", "p.c.", "prima manu", "secunda manu"}
# qualifiers that weaken certainty (@cert)
_UNCERTAIN = {"ut vid.", "fort."}
# the omission operator: an empty <rdg> per 13.4
_OMISSION = {"om."}


def _lang(text: str) -> str | None:
  letters = [c for c in text if c.isalpha()]
  if not letters:
    return None
  greek = sum(1 for c in letters if "Ͱ" <= c <= "Ͽ" or "ἀ" <= c <= "῿")
  return "grc" if greek / len(letters) > 0.5 else None


@dataclass
class _AnchorPoint:
  offset: int
  xml_id: str
  n: str | None
  consume_to: int
  """End of the text span the anchor replaces: the printed marker digits
  (with a detached marker's separating space) for an end anchor; equal to
  ``offset`` for a start anchor, which is a pure insertion."""


def _witness_ids(attr: Attribution, registry: Registry) -> str:
  return " ".join(dict.fromkeys(
    f"#wit-{registry.xml_id(w)}" for w in attr.witnesses))


def _editor_ids(attr: Attribution, registry: Registry) -> str:
  return " ".join(dict.fromkeys(
    f"#ed-{registry.xml_id(e)}" for e in attr.editors))


def _emit_reading(app: ET.Element, tag: str, text: str, attr: Attribution,
                  registry: Registry) -> None:
  el = ET.SubElement(app, tag)
  quals = set(attr.qualifiers)
  if quals & _OMISSION and not text:
    pass  # an omission: the element stays empty (13.4)
  else:
    el.text = text
  wit = _witness_ids(attr, registry)
  if wit:
    el.set("wit", wit)
  src = _editor_ids(attr, registry)
  if src:
    el.set("source", src)
  if quals & _UNCERTAIN:
    el.set("cert", "low")
  if attr.sources or attr.references:
    cite = ET.SubElement(el, "note", {"type": "cited-source"})
    cite.text = " ".join([*attr.sources, *attr.references])
  # sorted: set iteration order varies per process (hash randomization)
  # and once broke byte-determinism between two identical builds
  for q in sorted(quals & _PLACEMENT):
    for w in attr.witnesses:
      wd = ET.SubElement(app, "witDetail",
                         {"wit": f"#wit-{registry.xml_id(w)}"})
      wd.text = q


def _emit_app(parent: ET.Element, raw: str, parsed: ParsedEntry,
              registry: Registry, n: str | None,
              start_id: str | None, end_id: str | None,
              resp: str | None = None) -> None:
  app = ET.SubElement(parent, "app")
  if n:
    app.set("n", n)
  if resp:
    app.set("resp", resp)
  if start_id:
    app.set("from", f"#{start_id}")
  if end_id:
    app.set("to", f"#{end_id}")
  _emit_reading(app, "lem", parsed.lemma, parsed.lemma_attribution, registry)
  for r in parsed.readings:
    _emit_reading(app, "rdg", r.text, r.attribution, registry)
  for c in parsed.comments:
    ET.SubElement(app, "note", {"type": "comment"}).text = c
  ET.SubElement(app, "note", {"type": "verbatim"}).text = raw


def _anchored_ab(parent: ET.Element, block: Block,
                 points: list[_AnchorPoint]) -> None:
  """Emit block text as <ab>, inserting the collected anchors in offset
  order. Each end anchor consumes its own printed digit span (carried by
  the anchor since resolution — the one normalization performed, declared
  in the header); start anchors are pure insertions."""
  ab = ET.SubElement(parent, "ab")
  lang = _lang(block.text)
  if lang:
    ab.set("xml:lang", lang)
  if block.generative:
    ab.set("subtype", "generative")

  last_node: ET.Element | None = None

  def append_text(chunk: str) -> None:
    nonlocal last_node
    if last_node is None:
      ab.text = (ab.text or "") + chunk
    else:
      last_node.tail = (last_node.tail or "") + chunk

  pos = 0
  for p in sorted(points, key=lambda x: x.offset):
    if p.offset < pos:
      continue
    append_text(block.text[pos: p.offset])
    last_node = ET.SubElement(ab, "anchor")
    last_node.set("xml:id", p.xml_id)
    if p.n:
      last_node.set("n", p.n)
    pos = p.consume_to
  append_text(block.text[pos:])


def _verse_to_parsed(ve) -> ParsedEntry:
  """A verse-referenced entry in the shared emission shape: edition sigla
  are witnesses (the scholarly TEI of the convention declares them so)."""
  return ParsedEntry(
    lemma=ve.resolved_lemma or ve.lemma,
    lemma_attribution=Attribution(witnesses=list(ve.lemma_sigla)),
    readings=[
      Reading(text=r.text, attribution=Attribution(witnesses=list(r.sigla)))
      for r in ve.readings
    ],
    comments=[],
  )


def resolve_parsed(e, registry: Registry | None) -> ParsedEntry | None:
  """One entry's structured reading, in priority order: human review
  wins over every grammar; a review 'verbatim' forces the honest
  refusal. Shared by the TEI emitter and the review UI so both always
  show the SAME structure."""
  if e.override_action == "verbatim":
    return None
  if e.parsed_override is not None:
    return e.parsed_override
  if e.refusal_evidence:
    return None
  if e.parsed_verse is not None and registry is not None:
    return _verse_to_parsed(e.parsed_verse)
  if e.parsed_line is not None and registry is not None:
    le = e.parsed_line
    # the apparatus' own printed lemma, NOT the span resolved in the
    # constituted text: the latter carries marginal line numbers and
    # hyphenation caught mid-span
    return ParsedEntry(
      lemma=le.lemma,
      lemma_attribution=le.lemma_attribution,
      readings=[Reading(text=r.text, attribution=r.attribution)
                for r in le.readings],
      comments=list(le.comments),
    )
  if e.parsed_paragraph is not None and registry is not None:
    pe = e.parsed_paragraph
    return ParsedEntry(
      lemma=pe.lemma,
      lemma_attribution=Attribution(),
      readings=[Reading(text=r.text, attribution=r.attribution)
                for r in pe.readings],
      comments=list(pe.comments)
               + [c for r in pe.readings for c in r.comments],
    )
  if e.marker_eligible and registry is not None:
    return parse_entry(e.raw, registry)
  return None


def _collect_page_apparatus(page: Page, registry: Registry | None):
  """First pass: parse apparatus entries and compute both anchor points.

  Returns (anchors per text-block index, emission plan for the apparatus).
  """
  from .match import locate_lemma_start

  anchors: dict[int, list[_AnchorPoint]] = {}
  plan: list[tuple[Block, list[tuple]]] = []

  for block in page.blocks:
    if block.layer is not Layer.APPARATUS:
      continue
    entries_plan: list[tuple] = []
    for ei, e in enumerate(block.entries or []):
      parsed = resolve_parsed(e, registry)
      start_id = end_id = None
      if (e.anchor is not None and e.anchor.block_index is not None
          and e.anchor.char_offset is not None):
        # ids are minted per ENTRY, not per marker number: marker numbers
        # restart each printed page and may even repeat within one
        end_id = f"a-p{page.index}-e{ei}"
        ds = (e.anchor.digit_start if e.anchor.digit_start is not None
              else e.anchor.char_offset)
        de = (e.anchor.digit_end if e.anchor.digit_end is not None
              else e.anchor.char_offset)
        anchors.setdefault(e.anchor.block_index, []).append(
          _AnchorPoint(ds, end_id, e.anchor.value, de))
        if parsed is not None:
          text = page.blocks[e.anchor.block_index].text
          start = locate_lemma_start(parsed.lemma, text, e.anchor.char_offset)
          if start is not None and start < ds:
            start_id = f"{end_id}-start"
            anchors.setdefault(e.anchor.block_index, []).append(
              _AnchorPoint(start, start_id, None, start))
      entries_plan.append((e, parsed, start_id, end_id))
    plan.append((block, entries_plan))
  return anchors, plan


def _header(tei: ET.Element, doc: Document, title: str | None,
            registry: Registry | None) -> ET.Element:
  header = ET.SubElement(tei, "teiHeader")
  fd = ET.SubElement(header, "fileDesc")
  ts = ET.SubElement(fd, "titleStmt")
  ET.SubElement(ts, "title").text = title or doc.source_name
  if any(e.override_action
         for page in doc.pages for b in page.blocks
         for e in (b.entries or [])):
    rs = ET.SubElement(ts, "respStmt")
    rs.set("xml:id", "human-review")
    ET.SubElement(rs, "resp").text = (
      "Entries marked resp='#human-review' were corrected or reclassified "
      "by a human reviewer through a diorthosis overrides file; their "
      "verbatim source wording is retained unchanged.")
    ET.SubElement(rs, "name").text = "human reviewer"
  pub = ET.SubElement(fd, "publicationStmt")
  ET.SubElement(pub, "p").text = (
    f"Structural conversion produced by diorthosis {__version__} from "
    f"'{doc.source_name}' (ingest: {doc.ingest}). The text mirrors the "
    "source page for page. The single normalization applied: in-text "
    "superscript apparatus markers are encoded as tei:anchor elements "
    "(the marker gives the end anchor; lemma start anchors are computed "
    "by matching and omitted when the match is not confident). Parsed "
    "apparatus entries always retain their exact source-band substring, "
    "including whitespace and line breaks, in a note[@type='verbatim']; "
    "the normalized parsing view is never emitted there. Blocks marked "
    "subtype='generative' were "
    "produced by OCR and are a recognition model's output, not a decoded "
    "text stream."
  )
  sd = ET.SubElement(fd, "sourceDesc")
  ET.SubElement(sd, "bibl").text = doc.source_name
  if registry is not None and registry.witnesses:
    lw = ET.SubElement(sd, "listWit")
    for siglum, desc in registry.witnesses.items():
      wit = ET.SubElement(lw, "witness")
      wit.set("xml:id", f"wit-{registry.xml_id(siglum)}")
      base, hand = decompose(siglum, registry)
      if hand and base in registry.witnesses:
        wit.set("corresp", f"#wit-{registry.xml_id(base)}")
      abbr = ET.SubElement(wit, "abbr", {"type": "siglum"})
      abbr.text = siglum
      abbr.tail = f" {desc}"
  return header


def _editors_bibl(header: ET.Element, registry: Registry,
                  used: set[str]) -> None:
  if not used:
    return
  sd = header.find("fileDesc/sourceDesc")
  lb = ET.SubElement(sd, "listBibl")
  canon = builtin_editors()
  for token in sorted(used):
    bibl = ET.SubElement(lb, "bibl")
    bibl.set("xml:id", f"ed-{registry.xml_id(token)}")
    full = registry.editors.get(token) or canon.get(token) or token
    # the printed token itself, machine-recoverable (the xml:id hex-escapes
    # non-ASCII and the description need not open with the name)
    abbr = ET.SubElement(bibl, "abbr")
    abbr.text = token
    if isinstance(full, str) and full != token:
      abbr.tail = " " + full


def to_tei(doc: Document, title: str | None = None,
           registry: Registry | None = None) -> str:
  tei = ET.Element("TEI", {"xmlns": TEI_NS})
  header = _header(tei, doc, title, registry)

  text_el = ET.SubElement(tei, "text")
  body = ET.SubElement(text_el, "body")
  edition = ET.SubElement(body, "div", {"type": "edition"})
  translations: list[tuple[str | None, Block]] = []
  used_editors: set[str] = set()
  any_app = False

  for page in doc.pages:
    anchors, plan = _collect_page_apparatus(page, registry)
    plan_iter = iter(plan)
    text_block_index = -1

    pb = ET.SubElement(edition, "pb")
    if page.printed_page:
      pb.set("n", page.printed_page)
    pb.set("xml:id", f"page-{page.index}")

    for bi, block in enumerate(page.blocks):
      if block.layer is Layer.TEXT:
        text_block_index = bi
        _anchored_ab(edition, block, anchors.get(bi, []))
        for ref in block.inline_refs:
          ET.SubElement(edition, "note", {"type": "witness-ref"}).text = ref
      elif block.layer is Layer.HEADING:
        # <head> is only legal in a div's opening sequence; we deliberately
        # refuse to infer nested <div> structure, so section titles become
        # <label>, which is legal anywhere
        ET.SubElement(edition, "label", {"type": "section-title"}).text = block.text
      elif block.layer is Layer.APPARATUS:
        entries_plan = next(plan_iter, (block, []))[1]
        for e, parsed, start_id, end_id in entries_plan:
          if parsed is not None:
            any_app = True
            for a in (parsed.lemma_attribution,
                      *(r.attribution for r in parsed.readings)):
              used_editors.update(a.editors)
            _emit_app(edition, e.source_slice, parsed, registry,
                      e.anchor.value if e.anchor else None, start_id, end_id,
                      resp=("#human-review" if e.override_action else None))
          else:
            note = ET.SubElement(edition, "note", {"type": "apparatus"})
            if e.anchor is not None:
              note.set("n", e.anchor.value)
            if end_id:
              note.set("target", f"#{end_id}")
            if e.override_action:
              note.set("resp", "#human-review")
            note.text = e.source_slice
        if not block.entries:
          ET.SubElement(edition, "note", {"type": "apparatus"}).text = block.text
      elif block.layer is Layer.TRANSLATION:
        translations.append((page.printed_page, block))
      elif block.layer is Layer.NOTES:
        ET.SubElement(edition, "note", {"type": "editorial"}).text = block.text
      elif block.layer is Layer.RUNNING_HEAD:
        ET.SubElement(edition, "fw", {"type": "running-head"}).text = block.text
      elif block.layer is Layer.PAGE_NUMBER:
        ET.SubElement(edition, "fw", {"type": "page-number"}).text = block.text
      else:
        unk = ET.SubElement(edition, "ab", {"type": "unclassified"})
        if block.generative:
          unk.set("subtype", "generative")
        unk.text = block.text
    del text_block_index

  if translations:
    tr = ET.SubElement(body, "div", {"type": "translation"})
    for printed, block in translations:
      p = ET.SubElement(tr, "p")
      if printed:
        p.set("n", printed)
      if block.generative:
        p.set("subtype", "generative")
      p.text = block.text

  if any_app:
    # ch. 13.2: any document containing <app> REQUIRES this declaration
    enc = ET.Element("encodingDesc")
    ET.SubElement(enc, "variantEncoding",
                  {"method": "double-end-point", "location": "internal"})
    header.insert(1, enc)
  if registry is not None:
    _editors_bibl(header, registry, used_editors)

  # ET.indent leaves mixed-content elements (those carrying text) untouched,
  # so <ab> stays byte-verbatim — minidom's pretty-printer corrupted it
  ET.indent(tei, space="  ")
  raw = ET.tostring(tei, encoding="unicode", xml_declaration=True)
  # A PDF text layer can carry XML-invalid codepoints (a degenerate
  # ToUnicode maps missing glyphs to U+FFFF — observed). They are replaced
  # with U+FFFD so the document stays well-formed; the replacement is
  # visible, never silent.
  raw = _XML_INVALID.sub("�", raw)
  return unicodedata.normalize("NFC", raw) + "\n"


__all__ = ["to_tei", "TEI_NS"]
