"""TEI P5 emission — the canonical output.

P1 emits honest TEI-lite: the constituted text with in-text anchors, the
apparatus as **anchored but unparsed** ``<note type="apparatus">`` elements
pointing at those anchors, translation and editorial notes in their own
divisions, printed folios as ``<pb>``, page furniture as ``<fw>``. Turning
entries into ``<app>/<lem>/<rdg>`` requires the per-series apparatus grammar
(phase 2); emitting them verbatim-anchored today is already enough for a
retrieval pipeline to never confuse apparatus with text.

Provenance survives: blocks whose text was produced by OCR carry
``@subtype="generative"`` and the header declares the ingest chain.
"""

from __future__ import annotations

import unicodedata
import xml.etree.ElementTree as ET
from xml.dom import minidom

from . import __version__
from .anchor import _MARKER
from .model import Block, Document, Layer, Source

TEI_NS = "http://www.tei-c.org/ns/1.0"


def _lang(text: str) -> str | None:
  letters = [c for c in text if c.isalpha()]
  if not letters:
    return None
  greek = sum(1 for c in letters if "Ͱ" <= c <= "Ͽ" or "ἀ" <= c <= "῿")
  return "grc" if greek / len(letters) > 0.5 else None


def _anchored_ab(parent: ET.Element, block: Block, page_index: int) -> None:
  """Emit block text as <ab>, converting superscript markers to <anchor/>.

  The digit marker IS the anchor in structured form; replacing it is the one
  normalization performed, and it is documented in the header.
  """
  ab = ET.SubElement(parent, "ab")
  lang = _lang(block.text)
  if lang:
    ab.set("xml:lang", lang)
  if block.generative:
    ab.set("subtype", "generative")
  pos = 0
  text = block.text
  last_node: ET.Element | None = None
  for m in _MARKER.finditer(text):
    chunk = text[pos:m.start()]
    if last_node is None:
      ab.text = (ab.text or "") + chunk
    else:
      last_node.tail = (last_node.tail or "") + chunk
    last_node = ET.SubElement(ab, "anchor")
    last_node.set("xml:id", f"a-p{page_index}-m{m.group(1)}")
    last_node.set("n", m.group(1))
    pos = m.end()
  tail = text[pos:]
  if last_node is None:
    ab.text = (ab.text or "") + tail
  else:
    last_node.tail = (last_node.tail or "") + tail


def to_tei(doc: Document, title: str | None = None) -> str:
  tei = ET.Element("TEI", {"xmlns": TEI_NS})
  header = ET.SubElement(tei, "teiHeader")
  fd = ET.SubElement(header, "fileDesc")
  ts = ET.SubElement(fd, "titleStmt")
  ET.SubElement(ts, "title").text = title or doc.source_name
  pub = ET.SubElement(fd, "publicationStmt")
  ET.SubElement(pub, "p").text = (
    f"Structural conversion produced by diorthosis {__version__} from "
    f"'{doc.source_name}' (ingest: {doc.ingest}). The text mirrors the source "
    "page for page; the apparatus is anchored but not interpreted. The single "
    "normalization applied: in-text superscript apparatus markers are encoded "
    "as tei:anchor elements. Blocks marked subtype='generative' were produced "
    "by OCR and are a recognition model's output, not a decoded text stream."
  )
  sd = ET.SubElement(fd, "sourceDesc")
  ET.SubElement(sd, "p").text = doc.source_name

  text_el = ET.SubElement(tei, "text")
  body = ET.SubElement(text_el, "body")
  edition = ET.SubElement(body, "div", {"type": "edition"})
  translation_blocks: list[tuple[str | None, Block]] = []

  for page in doc.pages:
    pb = ET.SubElement(edition, "pb")
    if page.printed_page:
      pb.set("n", page.printed_page)
    pb.set("facs", f"page-{page.index}")
    for block in page.blocks:
      if block.layer is Layer.TEXT:
        _anchored_ab(edition, block, page.index)
        for ref in block.inline_refs:
          note = ET.SubElement(edition, "note", {"type": "witness-ref"})
          note.text = ref
      elif block.layer is Layer.HEADING:
        ET.SubElement(edition, "head").text = block.text
      elif block.layer is Layer.APPARATUS:
        for e in block.entries or []:
          note = ET.SubElement(edition, "note", {"type": "apparatus"})
          if e.anchor is not None:
            note.set("n", e.anchor.value)
            if e.anchor.block_index is not None:
              note.set("target", f"#a-p{page.index}-m{e.anchor.value}")
          note.text = e.raw
        if not block.entries:
          note = ET.SubElement(edition, "note", {"type": "apparatus"})
          note.text = block.text
      elif block.layer is Layer.TRANSLATION:
        translation_blocks.append((page.printed_page, block))
      elif block.layer is Layer.NOTES:
        note = ET.SubElement(edition, "note", {"type": "editorial"})
        note.text = block.text
      elif block.layer is Layer.RUNNING_HEAD:
        ET.SubElement(edition, "fw", {"type": "running-head"}).text = block.text
      elif block.layer is Layer.PAGE_NUMBER:
        ET.SubElement(edition, "fw", {"type": "page-number"}).text = block.text
      else:
        unk = ET.SubElement(edition, "ab", {"type": "unclassified"})
        if block.generative:
          unk.set("subtype", "generative")
        unk.text = block.text

  if translation_blocks:
    tr = ET.SubElement(body, "div", {"type": "translation"})
    for printed, block in translation_blocks:
      p = ET.SubElement(tr, "p")
      if printed:
        p.set("n", printed)
      if block.generative:
        p.set("subtype", "generative")
      p.text = block.text

  raw = ET.tostring(tei, encoding="unicode")
  pretty = minidom.parseString(raw).toprettyxml(indent="  ")
  # minidom adds a decl; normalize + NFC
  pretty = "\n".join(ln for ln in pretty.split("\n") if ln.strip())
  return unicodedata.normalize("NFC", pretty) + "\n"


__all__ = ["to_tei", "Source"]
