"""TEI and Markdown emission tests on a synthetic two-page document.

The fixture mirrors the observed geometry of a real bilingual edition
(Greek verso with apparatus, French recto with notes) using dummy content —
no copyrighted material is embedded.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter

import pytest

from diorthosis import cli
from diorthosis.anchor import anchor_page
from diorthosis.conspectus import Registry
from diorthosis.md import MD_CE_VERSION, MarkerDelimiterError, coverage, to_markdown
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

  def test_every_verbatim_note_is_an_exact_immutable_source_slice(self) -> None:
    registry = Registry()
    registry.witnesses = {token: token for token in ("A", "B", "M", "U", "R", "V")}
    bands = [
      "18 est] om.\n R\n20   in] om. V",
      "5 alpha M | beta\n U ∥ 7 gamma V | delta R",
      "1:1 λόγος WH ] 〚WH〛 ; –RP",
      "1 Λόγος A : νόμος B\n2 Alpha A : beta B",
    ]
    doc = Document(source_name="source-slices.pdf", ingest="borndigital")
    for index, band in enumerate(bands):
      page = Page(index=index, printed_page=str(index + 1))
      page.blocks = [_block(Layer.APPARATUS, band)]
      anchor_page(page, registry)
      doc.pages.append(page)

    entries = [entry for page in doc.pages for block in page.blocks
               for entry in block.entries]
    assert entries
    for page in doc.pages:
      band = page.blocks[0].text
      assert all(entry.source_slice in band for entry in page.blocks[0].entries)

    original = entries[0].source_slice
    with pytest.raises(AttributeError):
      entries[0]._source_slice = "rewritten"
    assert entries[0].source_slice == original

    root = ET.fromstring(to_tei(doc, registry=registry))
    ns = {"t": TEI_NS}
    emitted = [note.text or "" for note in root.findall(
      ".//t:app/t:note[@type='verbatim']", ns)]
    emitted += [note.text or "" for note in root.findall(
      ".//t:note[@type='apparatus']", ns)]
    assert Counter(emitted) == Counter(entry.source_slice for entry in entries)


class TestMarkdown:
  def test_contract_header_and_layer_fences(self) -> None:
    md = to_markdown(fixture())
    assert f"md-ce/{MD_CE_VERSION}" in md
    assert "coverage: " in md and "escaped-lines: " in md
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
    reg.witnesses = {
      "A": "Parisinus graecus 450",
      "B": "Musaei Britannici Ms",
    }
    reg.editors = {"Mign.": "Migne", "Thirlb.": "Thirlby"}
    doc = fixture()
    reg = with_builtin_editors(reg)
    anchor_page(doc.pages[0], reg)
    return doc, reg

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
    _, reg = self.doc_with_registry()
    reg.witnesses["B"] = "Musaei Britannici Ms"
    anchor_page(page, reg)
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


def _attachment_fixture() -> tuple[Document, Registry]:
  """One entry whose lemma IS locatable before its marker and one whose is
  not: the first becomes a complete double-end-point <app>, the second
  carries its end anchor alone."""
  reg = Registry()
  reg.witnesses = {"A": "Parisinus graecus 450", "B": "Musaei Britannici Ms"}
  doc = Document(source_name="attach.pdf", ingest="borndigital")
  page = Page(index=4, printed_page="41")
  page.blocks = [
    _block(Layer.TEXT, "καὶ ὁ λόγος2 ἐστίν· καὶ ὁ νόμος3 μένει."),
    _block(Layer.APPARATUS, "2 Λόγος A : νόμος B\n3 Παρουσία A : ἀπουσία B"),
  ]
  doc.pages = [page]
  anchor_page(page, reg)
  return doc, reg


class TestCoverageMatchesTheEmittedTEI:
  """The report describes the file that is actually emitted.

  ``md.coverage`` mirrors the predicate ``tei._collect_page_apparatus`` uses
  to mint a start anchor; this class is what keeps the two from drifting.
  """

  def test_attached_counts_double_end_point_apps(self) -> None:
    doc, reg = _attachment_fixture()
    cov = coverage(doc, reg)
    root = ET.fromstring(to_tei(doc, registry=reg))
    apps = root.findall(".//t:app", {"t": TEI_NS})
    assert cov.entries == len(apps) == 2
    assert cov.attached == sum(a.get("from") is not None for a in apps) == 1
    assert cov.end_only == sum(
      a.get("from") is None and a.get("to") is not None for a in apps) == 1
    assert cov.unanchored == 0

  def test_end_only_entry_is_not_reported_as_fully_anchored(self) -> None:
    doc, reg = _attachment_fixture()
    cov = coverage(doc, reg)
    assert cov.anchored == 2
    assert "2 anchored (1 attached, 1 end-only)" in cov.report

  def test_parsed_counts_the_entries_that_become_apps(self) -> None:
    doc, reg = _attachment_fixture()
    cov = coverage(doc, reg)
    root = ET.fromstring(to_tei(doc, registry=reg))
    ns = {"t": TEI_NS}
    assert cov.parsed == len(root.findall(".//t:app", ns))
    assert cov.refused + cov.unparsed == len(
      root.findall(".//t:note[@type='apparatus']", ns))


class TestMdCeInvariants:
  """md-ce normative invariants (SPEC.md), mechanically checked."""

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
    """The meta report is the sum of the page reports — the file states its
    own coverage in a form a reader can add up."""
    import re as _re

    md = to_markdown(fixture())
    fields = _re.compile(
      r"(\d+) entries — (\d+) parsed, (\d+) refused, (\d+) unparsed; "
      r"(\d+) anchored \((\d+) attached, (\d+) end-only\), (\d+) unanchored")
    lines = md.split("\n")
    meta = fields.search(lines[2])
    pages = [m.groups() for line in lines
             if line.startswith("<!-- md-ce page: ")
             for m in [fields.search(line)] if m]
    assert meta is not None and len(pages) == 2
    for column in range(8):
      assert int(meta.group(column + 1)) == sum(int(p[column]) for p in pages)

  def test_i11_one_report_three_renderings(self) -> None:
    """The console lines and the meta line carry the SAME text: a build can
    no longer announce two different anchoring scores."""
    doc = fixture()
    cov = coverage(doc)
    report, refusals = cov.lines
    meta = to_markdown(doc, cov=cov).split("\n")[2]
    assert f" · {report} · {refusals} · " in meta
    page_reports = [line for line in to_markdown(doc, cov=cov).split("\n")
                    if line.startswith("<!-- md-ce page: ")]
    assert len(page_reports) == len(doc.pages)
    assert page_reports[0] == f"<!-- md-ce page: {cov.pages[0].report} -->"

  def test_i11_refusal_tally_sums_to_refused(self) -> None:
    """Every refusal is accounted for by name: the fixture is anchored
    without a registry, so the marker gate refuses the whole band."""
    cov = coverage(fixture())
    assert cov.refused == 1
    assert sum(count for _, count in cov.refusals) == cov.refused
    assert "no registry is available" in cov.refusals[0][0]

  def test_i11_partitions_on_both_axes(self) -> None:
    cov = coverage(fixture())
    assert cov.parsed + cov.refused + cov.unparsed == cov.entries
    assert cov.attached + cov.end_only + cov.unanchored == cov.entries
    assert cov.anchored == cov.attached + cov.end_only

  def test_i11_coverage_measured_for_another_document_is_refused(self) -> None:
    """A report that does not describe THIS document would make the page
    numbers unverifiable; emission refuses instead of mislabelling them."""
    import pytest as _pytest

    doc = fixture()
    with _pytest.raises(ValueError, match="recomputable"):
      to_markdown(doc, cov=coverage(Document(source_name="other.pdf")))


ALTO_PAGE = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
  <Layout><Page><PrintSpace><TextBlock ID="b1"><TextLine>
    <String CONTENT="καὶ" WC="0.98"/><SP/><String CONTENT="λόγος" WC="0.95"/>
  </TextLine></TextBlock></PrintSpace></Page></Layout>
</alto>
"""


class TestDegeneracy:
  """A build that produced nothing must say so.

  The project's own documented one-liner used to exit 0 on its flagship
  edition after emitting zero text blocks and zero apparatus entries.
  """

  def test_layered_document_without_a_text_block_is_degenerate(self) -> None:
    doc = Document(source_name="e.pdf", ingest="borndigital")
    page = Page(index=0, printed_page="1")
    page.blocks = [_block(Layer.TRANSLATION, "Toute la page en français."),
                   _block(Layer.NOTES, "1. une note")]
    doc.pages = [page]
    [finding] = cli.degeneracies(doc, coverage(doc))
    assert "no constituted-text block" in finding
    assert "--text-lang la" in finding      # the option that would fix it

  def test_a_text_block_is_enough_to_pass(self) -> None:
    assert cli.degeneracies(fixture(), coverage(fixture())) == []

  def test_undecodable_page_set_is_named_as_such(self) -> None:
    doc = Document(source_name="scan.pdf", ingest="borndigital")
    page = Page(index=0, printed_page=None)
    page.blocks = [_block(Layer.TEXT, "   ")]
    doc.pages = [page]
    [finding] = cli.degeneracies(doc, coverage(doc))
    assert "no decodable text" in finding and "--alto" in finding

  def test_ocr_input_is_exempt_from_the_layer_census(self) -> None:
    """OCR adapters assign no layer on purpose (nothing is guessed), so
    'no text block' is not evidence of a failed build there."""
    doc = Document(source_name="p1.xml", ingest="alto")
    page = Page(index=0, printed_page=None)
    page.blocks = [Block(layer=Layer.UNKNOWN, text="καὶ λόγος",
                         source=Source.OCR, generative=True, confidence=0.95)]
    doc.pages = [page]
    assert cli.degeneracies(doc, coverage(doc)) == []

  def test_apparatus_band_without_entries_is_degenerate(self) -> None:
    doc = Document(source_name="e.pdf", ingest="borndigital")
    page = Page(index=0, printed_page="1")
    page.blocks = [_block(Layer.TEXT, "ὁ λόγος"),
                   _block(Layer.APPARATUS, "     ")]
    doc.pages = [page]
    page.blocks[1].entries = []
    [finding] = cli.degeneracies(doc, coverage(doc))
    assert "no entry was split" in finding


class TestBuildExitCodes:
  """Exit codes are a contract: 0 success, 1 refused, 2 input, 3 defect."""

  def _alto(self, tmp_path):
    page = tmp_path / "p1.xml"
    page.write_text(ALTO_PAGE, encoding="utf-8")
    return page

  def test_ocr_build_succeeds_and_its_md_validates(self, tmp_path) -> None:
    from diorthosis.mdce_validate import validate_file

    out = tmp_path / "out"
    code = cli.main(["build", "--alto", str(self._alto(tmp_path)),
                     "-o", str(out)])
    assert code == cli.EXIT_OK
    assert validate_file(out / "p1.md") == []

  def test_self_check_refuses_an_invalid_md_ce_file(self, tmp_path) -> None:
    md = tmp_path / "e.md"
    md.write_text("# not md-ce at all\n", encoding="utf-8")
    doc = fixture()
    code = cli.self_check(doc, coverage(doc), md, ignore=False)
    assert code == cli.EXIT_REFUSED

  def test_the_escape_flag_accepts_it_knowingly(self, tmp_path, capsys) -> None:
    md = tmp_path / "e.md"
    md.write_text("# not md-ce at all\n", encoding="utf-8")
    doc = fixture()
    assert cli.self_check(doc, coverage(doc), md, ignore=True) == cli.EXIT_OK
    assert "--ignore-self-check" in capsys.readouterr().err

  def test_missing_input_file_is_a_user_error(self, monkeypatch) -> None:
    monkeypatch.setattr(
      "sys.argv", ["diorthosis", "build", "/nonexistent.pdf", "-o", "/tmp/x"])
    assert cli.run() == cli.EXIT_INPUT

  def test_an_unexpected_exception_is_an_internal_fault(self, monkeypatch) -> None:
    def boom(argv=None):
      raise RuntimeError("a defect, not an input problem")

    monkeypatch.setattr(cli, "main", boom)
    assert cli.run() == cli.EXIT_INTERNAL

  def test_an_ambiguous_source_is_refused_not_blamed_on_the_user(
      self, monkeypatch) -> None:
    def refuse(argv=None):
      raise MarkerDelimiterError("⟦ in source text")

    monkeypatch.setattr(cli, "main", refuse)
    assert cli.run() == cli.EXIT_REFUSED
