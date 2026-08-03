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

import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from . import __version__
from .anchor import marker_positions
from .conspectus import Registry, builtin_editors
from .grammar import Attribution, ParsedEntry, parse_entry
from .model import Block, Document, Layer, Page

TEI_NS = "http://www.tei-c.org/ns/1.0"

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


def _witness_ids(attr: Attribution, registry: Registry) -> str:
  return " ".join(f"#wit-{registry.xml_id(w)}" for w in attr.witnesses)


def _editor_ids(attr: Attribution, registry: Registry) -> str:
  return " ".join(f"#ed-{registry.xml_id(e)}" for e in attr.editors)


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
  for q in quals & _PLACEMENT:
    for w in attr.witnesses:
      wd = ET.SubElement(app, "witDetail",
                         {"wit": f"#wit-{registry.xml_id(w)}"})
      wd.text = q


def _emit_app(parent: ET.Element, raw: str, parsed: ParsedEntry,
              registry: Registry, n: str | None,
              start_id: str | None, end_id: str | None) -> None:
  app = ET.SubElement(parent, "app")
  if n:
    app.set("n", n)
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
  order. Superscript marker digits are consumed (they ARE the end anchors,
  in structured form — the one normalization performed, declared in the
  header); start anchors are pure insertions."""
  ab = ET.SubElement(parent, "ab")
  lang = _lang(block.text)
  if lang:
    ab.set("xml:lang", lang)
  if block.generative:
    ab.set("subtype", "generative")

  marker_spans = marker_positions(block.text)
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
    pos = marker_spans.get(p.offset, p.offset)
  append_text(block.text[pos:])


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
      parsed = parse_entry(e.raw, registry) if registry is not None else None
      start_id = end_id = None
      if (e.anchor is not None and e.anchor.block_index is not None
          and e.anchor.char_offset is not None):
        # ids are minted per ENTRY, not per marker number: marker numbers
        # restart each printed page and may even repeat within one
        end_id = f"a-p{page.index}-e{ei}"
        anchors.setdefault(e.anchor.block_index, []).append(
          _AnchorPoint(e.anchor.char_offset, end_id, e.anchor.value))
        if parsed is not None:
          text = page.blocks[e.anchor.block_index].text
          start = locate_lemma_start(parsed.lemma, text, e.anchor.char_offset)
          if start is not None and start < e.anchor.char_offset:
            start_id = f"{end_id}-start"
            anchors.setdefault(e.anchor.block_index, []).append(
              _AnchorPoint(start, start_id, None))
      entries_plan.append((e, parsed, start_id, end_id))
    plan.append((block, entries_plan))
  return anchors, plan


def _header(tei: ET.Element, doc: Document, title: str | None,
            registry: Registry | None) -> ET.Element:
  header = ET.SubElement(tei, "teiHeader")
  fd = ET.SubElement(header, "fileDesc")
  ts = ET.SubElement(fd, "titleStmt")
  ET.SubElement(ts, "title").text = title or doc.source_name
  pub = ET.SubElement(fd, "publicationStmt")
  ET.SubElement(pub, "p").text = (
    f"Structural conversion produced by diorthosis {__version__} from "
    f"'{doc.source_name}' (ingest: {doc.ingest}). The text mirrors the "
    "source page for page. The single normalization applied: in-text "
    "superscript apparatus markers are encoded as tei:anchor elements "
    "(the marker gives the end anchor; lemma start anchors are computed "
    "by matching and omitted when the match is not confident). Parsed "
    "apparatus entries always retain the source's exact wording in a "
    "note[@type='verbatim']. Blocks marked subtype='generative' were "
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
    bibl.text = full if isinstance(full, str) else token


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
            _emit_app(edition, e.raw, parsed, registry,
                      e.anchor.value if e.anchor else None, start_id, end_id)
          else:
            note = ET.SubElement(edition, "note", {"type": "apparatus"})
            if e.anchor is not None:
              note.set("n", e.anchor.value)
            if end_id:
              note.set("target", f"#{end_id}")
            note.text = e.raw
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
  return unicodedata.normalize("NFC", raw) + "\n"


__all__ = ["to_tei", "TEI_NS"]
