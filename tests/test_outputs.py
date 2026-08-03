"""TEI and Markdown emission tests on a synthetic two-page document.

The fixture mirrors the observed geometry of a real bilingual edition
(Greek verso with apparatus, French recto with notes) using dummy content —
no copyrighted material is embedded.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from diorthosis.anchor import anchor_page
from diorthosis.md import MD_CE_VERSION, to_markdown
from diorthosis.model import Block, Document, Layer, Page, Source
from diorthosis.tei import TEI_NS, to_tei


def _block(layer: Layer, text: str, generative: bool = False) -> Block:
  return Block(
    layer=layer, text=text,
    source=Source.OCR if generative else Source.BORN_DIGITAL,
    generative=generative, confidence=0.9,
  )


def fixture() -> Document:
  doc = Document(source_name="edition.pdf", ingest="borndigital")
  greek = Page(index=10, printed_page="24")
  greek.blocks = [
    _block(Layer.RUNNING_HEAD, "AUCTOR"),
    _block(Layer.TEXT, "καὶ ὁ λόγος2 ἐστὶν ἀληθής."),
    _block(Layer.APPARATUS, "2 Λόγος A : νόμος B"),
    _block(Layer.PAGE_NUMBER, "24"),
  ]
  french = Page(index=11, printed_page="25")
  french.blocks = [
    _block(Layer.HEADING, "Le discours véritable"),
    _block(Layer.TRANSLATION, "Et la parole est vraie."),
    _block(Layer.NOTES, "a Cf. Jn 1, 1"),
  ]
  doc.pages = [greek, french]
  for p in doc.pages:
    anchor_page(p)
  return doc


class TestTEI:
  def test_is_valid_namespaced_xml(self) -> None:
    tei = to_tei(fixture())
    root = ET.fromstring(tei)
    assert root.tag == f"{{{TEI_NS}}}TEI"

  def test_apparatus_is_anchored_and_never_inside_text(self) -> None:
    tei = to_tei(fixture())
    root = ET.fromstring(tei)
    ns = {"t": TEI_NS}
    ab = root.find(".//t:div[@type='edition']/t:ab", ns)
    assert ab is not None
    # the marker digit became an anchor: no bare '2' remains in the text
    assert "2" not in "".join(ab.itertext())
    anchor = ab.find("t:anchor", ns)
    assert anchor is not None and anchor.get("n") == "2"
    note = root.find(".//t:note[@type='apparatus']", ns)
    assert note is not None
    assert note.get("target") == "#a-p10-m2"
    assert note.text == "Λόγος A : νόμος B"

  def test_printed_folio_becomes_pb(self) -> None:
    root = ET.fromstring(to_tei(fixture()))
    ns = {"t": TEI_NS}
    assert [pb.get("n") for pb in root.findall(".//t:pb", ns)] == ["24", "25"]

  def test_greek_gets_language_tag(self) -> None:
    root = ET.fromstring(to_tei(fixture()))
    ns = {"t": TEI_NS}
    ab = root.find(".//t:div[@type='edition']/t:ab", ns)
    xml_ns = "{http://www.w3.org/XML/1998/namespace}lang"
    assert ab is not None and ab.get(xml_ns) == "grc"

  def test_translation_lives_in_its_own_division(self) -> None:
    root = ET.fromstring(to_tei(fixture()))
    ns = {"t": TEI_NS}
    tr = root.find(".//t:div[@type='translation']/t:p", ns)
    assert tr is not None and tr.text == "Et la parole est vraie."

  def test_generative_blocks_are_marked(self) -> None:
    doc = fixture()
    doc.pages[0].blocks[1] = _block(Layer.TEXT, "ὁ λόγος", generative=True)
    root = ET.fromstring(to_tei(doc))
    ns = {"t": TEI_NS}
    ab = root.find(".//t:div[@type='edition']/t:ab", ns)
    assert ab is not None and ab.get("subtype") == "generative"


class TestMarkdown:
  def test_contract_header_and_layer_fences(self) -> None:
    md = to_markdown(fixture())
    assert f"md-ce/{MD_CE_VERSION}" in md
    assert "## page 24 (file index 10)" in md
    assert "### text [source=born_digital generative=false confidence=0.90]" in md
    assert "### apparatus" in md and "### translation" in md

  def test_markers_link_text_and_apparatus_visibly(self) -> None:
    md = to_markdown(fixture())
    assert "λόγος⟦2⟧" in md
    assert "⟦2⟧ Λόγος A : νόμος B" in md

  def test_page_furniture_is_excluded_from_the_view(self) -> None:
    md = to_markdown(fixture())
    assert "AUCTOR" not in md  # running head: TEI keeps it, the view drops it

  def test_deterministic(self) -> None:
    assert to_markdown(fixture()) == to_markdown(fixture())
