"""The validator must accept what the emitter produces and reject every
mechanically checkable invariant breach — including the exact defect class
that motivated it (a resolved apparatus marker with no text counterpart,
the pre-v0.2.1 detached-marker bug)."""

from __future__ import annotations

from diorthosis.anchor import anchor_page
from diorthosis.md import to_markdown
from diorthosis.mdce_validate import validate_text
from diorthosis.model import Block, Document, Layer, Page, Source


def _block(layer: Layer, text: str, generative: bool = False) -> Block:
  return Block(
    layer=layer, text=text,
    source=Source.OCR if generative else Source.BORN_DIGITAL,
    generative=generative, confidence=0.9,
  )


def fixture_md() -> str:
  doc = Document(source_name="edition.pdf", ingest="borndigital")
  p1 = Page(index=10, printed_page="24")
  p1.blocks = [
    _block(Layer.TEXT, "καὶ ὁ λόγος2 ἐστὶν ἀληθής."),
    _block(Layer.APPARATUS, "2 Λόγος A : νόμος B"),
  ]
  p2 = Page(index=11, printed_page="25")
  p2.blocks = [
    _block(Layer.HEADING, "Le discours"),
    _block(Layer.TRANSLATION, "Et la parole est vraie."),
  ]
  doc.pages = [p1, p2]
  for p in doc.pages:
    anchor_page(p)
  return to_markdown(doc, tei_name="edition.tei.xml")


def invariants(md: str) -> set[str]:
  return {v.invariant for v in validate_text(md)}


class TestAcceptsEmitterOutput:
  def test_emitted_file_is_clean(self) -> None:
    assert validate_text(fixture_md()) == []

  def test_generative_and_unresolved_files_are_clean(self) -> None:
    doc = Document(source_name="e.pdf", ingest="hocr")
    page = Page(index=0, printed_page="12")
    page.blocks = [
      _block(Layer.TEXT, "καὶ ὁ λόγος ἐστίν.", generative=True),
      _block(Layer.APPARATUS, "4 Ἄλογος : λόγος B"),
    ]
    doc.pages = [page]
    anchor_page(page)
    md = to_markdown(doc)
    assert "⟦12:4?⟧" in md
    assert validate_text(md) == []


class TestRejectsViolations:
  def test_i3_resolved_marker_without_text_counterpart(self) -> None:
    """The historical bug: apparatus says ⟦24:2⟧, text kept a literal digit."""
    md = fixture_md().replace("λόγος⟦24:2⟧", "λόγος 2")
    assert "I3" in invariants(md)

  def test_i3_unresolved_marker_present_in_text(self) -> None:
    md = fixture_md().replace("⟦24:2⟧ Λόγος", "⟦24:2?⟧ Λόγος")
    vs = validate_text(md)
    assert any(v.invariant == "I3" for v in vs)
    # and the per-page unresolved count no longer matches either
    assert any(v.invariant == "I11" for v in vs)

  def test_i3_cross_page_marker(self) -> None:
    md = fixture_md().replace("λόγος⟦24:2⟧", "λόγος⟦25:2⟧")
    assert "I3" in invariants(md)

  def test_i4_stray_delimiter(self) -> None:
    md = fixture_md().replace("ἀληθής.", "ἀληθής⟧.")
    assert "I4" in invariants(md)

  def test_i1_unescaped_structural_line_and_bad_count(self) -> None:
    md = fixture_md().replace("Et la parole", "# forged\nEt la parole")
    assert "I1" in invariants(md)

  def test_i5_corrupt_section_header(self) -> None:
    md = fixture_md().replace("confidence=0.90", "confidence=high")
    assert "I5" in invariants(md)

  def test_i6_duplicate_block_ordinal(self) -> None:
    md = fixture_md().replace(
      "### apparatus [source=born_digital generative=false confidence=0.90 block=1]",
      "### apparatus [source=born_digital generative=false confidence=0.90 block=0]")
    assert "I6" in invariants(md)

  def test_i7_page_order(self) -> None:
    md = fixture_md()
    a = md.index("\n## page 24")
    b = md.index("\n## page 25")
    swapped = md[:a] + md[b:] + md[a:b]
    vs = invariants(swapped)
    assert "I7" in vs or "I11" in vs  # order broken; meta range breaks with it

  def test_i11_forged_coverage(self) -> None:
    md = fixture_md().replace("anchored: 1/1", "anchored: 9/9")
    assert "I11" in invariants(md)

  def test_i10_forged_generative_count(self) -> None:
    md = fixture_md().replace("generative-blocks: 0", "generative-blocks: 3")
    assert "I10" in invariants(md)

  def test_i12_crlf_and_missing_final_newline(self) -> None:
    md = fixture_md()
    assert "I12" in invariants(md.replace("\n", "\r\n"))
    assert "I12" in invariants(md.rstrip("\n"))

  def test_i12_nfc(self) -> None:
    import unicodedata

    md = unicodedata.normalize("NFD", fixture_md())
    assert "I12" in invariants(md)
