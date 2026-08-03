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
    assert note.get("target") == "#a-p10-e0"
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
    assert "anchored: " in md and "escaped-lines: " in md
    assert "## page 24 (file index 10)" in md
    assert "### text [source=born_digital generative=false confidence=0.90 block=1]" in md
    assert "### apparatus" in md and "### translation" in md

  def test_markers_link_text_and_apparatus_visibly(self) -> None:
    md = to_markdown(fixture())
    assert "λόγος⟦24:2⟧" in md
    assert "⟦24:2⟧ Λόγος A : νόμος B" in md

  def test_page_furniture_is_excluded_from_the_view(self) -> None:
    md = to_markdown(fixture())
    assert "AUCTOR" not in md  # running head: TEI keeps it, the view drops it

  def test_deterministic(self) -> None:
    assert to_markdown(fixture()) == to_markdown(fixture())


class TestTEIStandardsAlignment:
  """TEI P5 ch. 13 conformity, locked by tests (Guidelines v4.12)."""

  def doc_with_registry(self):
    from diorthosis.conspectus import Registry, with_builtin_editors

    reg = Registry()
    reg.witnesses = {"A": "Parisinus graecus 450"}
    reg.editors = {"Mign.": "Migne", "Thirlb.": "Thirlby"}
    doc = fixture()
    return doc, with_builtin_editors(reg)

  def tei_root(self):
    doc, reg = self.doc_with_registry()
    return ET.fromstring(to_tei(doc, registry=reg))

  def test_variant_encoding_present_when_apps_emitted(self) -> None:
    root = self.tei_root()
    ns = {"t": TEI_NS}
    ve = root.find(".//t:encodingDesc/t:variantEncoding", ns)
    assert ve is not None
    assert ve.get("method") == "double-end-point"
    assert ve.get("location") == "internal"

  def test_double_end_point_anchors(self) -> None:
    root = self.tei_root()
    ns = {"t": TEI_NS}
    app = root.find(".//t:app", ns)
    assert app is not None
    assert app.get("to") == "#a-p10-e0"
    assert app.get("from") == "#a-p10-e0-start"
    # both anchors exist in the text
    ids = {a.get("{http://www.w3.org/XML/1998/namespace}id")
           for a in root.findall(".//t:ab/t:anchor", ns)}
    assert {"a-p10-e0", "a-p10-e0-start"} <= ids

  def test_manuscripts_get_wit_editors_get_source(self) -> None:
    root = self.tei_root()
    ns = {"t": TEI_NS}
    rdg = root.find(".//t:app/t:rdg", ns)
    assert rdg is not None
    # fixture apparatus: "2 Λόγος A : νόμος B" — B undeclared here, A declared
    lem = root.find(".//t:app/t:lem", ns)
    assert lem is not None and lem.get("wit") == "#wit-A"
    assert lem.get("resp") is None  # @resp would claim the ENCODER's agency

  def test_verbatim_note_always_present(self) -> None:
    root = self.tei_root()
    ns = {"t": TEI_NS}
    note = root.find(".//t:app/t:note[@type='verbatim']", ns)
    assert note is not None and "Λόγος A" in note.text

  def test_omission_is_an_empty_rdg(self) -> None:
    from diorthosis.anchor import anchor_page
    from diorthosis.model import Document, Layer, Page

    doc = Document(source_name="e.pdf", ingest="borndigital")
    page = Page(index=1, printed_page="10")
    page.blocks = [
      _block(Layer.TEXT, "καὶ ὁ λόγος7 ἐστίν."),
      _block(Layer.APPARATUS, "7 Λόγος A : om. B"),
    ]
    doc.pages = [page]
    anchor_page(page)
    _, reg = self.doc_with_registry()
    reg.witnesses["B"] = "Musaei Britannici Ms"
    root = ET.fromstring(to_tei(doc, registry=reg))
    ns = {"t": TEI_NS}
    rdgs = root.findall(".//t:app/t:rdg", ns)
    empty = [r for r in rdgs if not (r.text or "").strip()]
    assert empty and empty[0].get("wit") == "#wit-B"

  def test_editor_tokens_are_clean(self) -> None:
    from diorthosis.grammar import parse_entry

    _, reg = self.doc_with_registry()
    e = parse_entry("Μωσέως : Μωϋσέως Mign., Thirlb.", reg)
    assert e is not None
    assert e.readings[0].attribution.editors == ["Mign.", "Thirlb."]


class TestMdCeInvariants:
  """md-ce/0.2 normative invariants (SPEC.md), mechanically checked."""

  def test_i1_structural_lines_escaped_and_counted(self) -> None:
    doc = fixture()
    doc.pages[1].blocks[1].text = "# forged header\nEt la parole est vraie."
    md = to_markdown(fixture())  # control
    forged = to_markdown(doc)
    assert "\\# forged header" in forged
    assert "escaped-lines: 1" in forged
    assert "escaped-lines: 0" in md

  def test_i3_unresolved_marker_carries_question_mark(self) -> None:
    from diorthosis.model import Document, Layer, Page

    doc = Document(source_name="e.pdf", ingest="borndigital")
    page = Page(index=3, printed_page="12")
    page.blocks = [
      _block(Layer.TEXT, "καὶ ὁ λόγος ἐστίν."),          # no marker in text
      _block(Layer.APPARATUS, "4 Ἄλογος : λόγος B"),
    ]
    doc.pages = [page]
    from diorthosis.anchor import anchor_page
    anchor_page(page)
    md = to_markdown(doc)
    assert "⟦12:4?⟧" in md
    assert "unresolved=1" in md

  def test_i3_detached_marker_is_rewritten_in_text_and_tei(self) -> None:
    """A lemma-confirmed DETACHED marker (``ἐδήλωσέ 4``) must be rewritten
    in the text exactly like a glued one: ⟦f:n⟧ in text AND apparatus, the
    printed ``  4`` consumed; in TEI the anchor replaces the digit span.
    Pre-v0.2.1 both outputs re-scanned find_markers (glued only) and the
    apparatus showed a resolved marker with no counterpart in the text."""
    from diorthosis.anchor import anchor_page
    from diorthosis.conspectus import Registry
    from diorthosis.model import Document, Layer, Page

    doc = Document(source_name="e.pdf", ingest="borndigital")
    page = Page(index=5, printed_page="258")
    page.blocks = [
      _block(Layer.TEXT, "τοῦτο γὰρ ἐδήλωσέ 4 καὶ εἶπεν."),
      _block(Layer.APPARATUS, "4 Ἐδήλωσέ A : ἐδήλου B"),
    ]
    doc.pages = [page]
    reg = Registry()
    reg.witnesses = {"A": "Parisinus", "B": "Musaei Britannici Ms"}
    stats = anchor_page(page, reg)
    assert stats["anchored"] == 1

    md = to_markdown(doc)
    assert "ἐδήλωσέ⟦258:4⟧ καὶ" in md          # digit AND its space consumed
    assert "⟦258:4⟧ Ἐδήλωσέ A : ἐδήλου B" in md
    assert md.count("⟦258:4⟧") == 2            # I3: exactly one per side
    assert " 4 " not in md

    root = ET.fromstring(to_tei(doc, registry=reg))
    ns = {"t": TEI_NS}
    ab = root.find(".//t:div[@type='edition']/t:ab", ns)
    assert ab is not None
    assert "4" not in "".join(ab.itertext())   # digit consumed, not duplicated
    anchors = ab.findall("t:anchor", ns)
    end = next(a for a in anchors if a.get("n") == "4")
    # the end anchor sits glued to its word (its preceding text ends on the
    # word, the detachment space consumed) and the text resumes after it
    idx = list(ab).index(end)
    before = ab.text if idx == 0 else list(ab)[idx - 1].tail
    assert (before or "").endswith("ἐδήλωσέ")
    assert (end.tail or "").startswith(" καὶ")

  def test_i3_digit_without_resolved_entry_stays_verbatim(self) -> None:
    """A glued digit whose entry did NOT resolve must stay a literal digit:
    I3 demands ZERO ⟦f:n⟧ in the text for an unresolved entry."""
    from diorthosis.anchor import anchor_page
    from diorthosis.model import Document, Layer, Page

    doc = Document(source_name="e.pdf", ingest="borndigital")
    page = Page(index=7, printed_page="30")
    page.blocks = [
      # two glued candidates for "3", no registry → no lemma discrimination
      _block(Layer.TEXT, "ὁ λόγος3 καὶ ὁ νόμος3 ἐστίν."),
      _block(Layer.APPARATUS, "3 Λόγος A : νόμος B"),
    ]
    doc.pages = [page]
    anchor_page(page)
    md = to_markdown(doc)
    assert "⟦30:3?⟧ Λόγος A : νόμος B" in md
    assert "λόγος3 καὶ ὁ νόμος3" in md          # digits untouched
    assert md.count("⟦30:3") == 1               # only the apparatus side

  def test_i4_marker_delimiter_in_source_refuses(self) -> None:
    import pytest as _pytest

    from diorthosis.md import MarkerDelimiterError

    doc = fixture()
    doc.pages[0].blocks[1].text = "καὶ ⟦τοῦτο⟧ ἐστίν"
    with _pytest.raises(MarkerDelimiterError):
      to_markdown(doc)

  def test_i11_coverage_recomputable(self) -> None:
    md = to_markdown(fixture())
    import re as _re

    m = _re.search(r"anchored: (\d+)/(\d+)", md)
    assert m is not None
    per_page = _re.findall(r"entries=(\d+) unresolved=(\d+)", md)
    total = sum(int(e) for e, _ in per_page)
    unres = sum(int(u) for _, u in per_page)
    assert (int(m.group(1)), int(m.group(2))) == (total - unres, total)
