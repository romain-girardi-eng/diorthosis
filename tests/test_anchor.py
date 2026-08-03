"""Anchoring tests — every expected value mirrors a real convention observed
in the reference edition (Paradosis 47); nothing is invented."""

from __future__ import annotations

from diorthosis.anchor import (
  anchor_block_text,
  anchor_page,
  find_markers,
  split_entries,
)
from diorthosis.model import Block, Layer, Page, Source


def block(layer: Layer, text: str) -> Block:
  return Block(
    layer=layer, text=text,
    source=Source.BORN_DIGITAL, generative=False, confidence=0.9,
  )


class TestSplitEntries:
  def test_numbered_entries_with_capitalized_lemmas(self) -> None:
    band = "1 Ὥστε prop. Mar.   2 Ζήσητε edd. : ζήσετε A   3 Μωσέως : Μωϋσέως Mign."
    entries = split_entries(band)
    assert [e.anchor.value for e in entries if e.anchor] == ["1", "2", "3"]
    assert entries[0].raw.startswith("Ὥστε")
    assert entries[2].raw == "Μωσέως : Μωϋσέως Mign."

  def test_cross_reference_numbers_do_not_split(self) -> None:
    # "cf. 62, 2 (ὅτι …)" cites chapter 62 § 2: the 2 opens a parenthesis,
    # not a capitalized lemma, and must stay inside entry 8.
    band = "8 Ὅτι ...σωθήσεσθαι : cf. 62,  2  (ὅτι ...εἰρηκέναι) ; 69,  4  (Ζαχαρίας φησίν)"
    entries = split_entries(band)
    assert len(entries) == 1
    assert entries[0].anchor is not None and entries[0].anchor.value == "8"
    assert "(ὅτι" in entries[0].raw and "69," in entries[0].raw

  def test_greek_capital_lemma_across_the_full_alphabet(self) -> None:
    # Κ (U+039A) sits in the basic capitals block, OUTSIDE the accented
    # range Ά-Ώ — the regression that once collapsed 13 entries into 3.
    entries = split_entries("4 Ἰακὼβ : Ἰὼβ Sylb.   5 Καὶ : ἢ prop. Thirlb.")
    assert [e.anchor.value for e in entries if e.anchor] == ["4", "5"]

  def test_prose_band_stays_single_and_unanchored(self) -> None:
    # apparatus fontium is prose: never forced into the numeric mold
    entries = split_entries("a Cf. Is. 1, 16   b cf. Is. 55, 7 ; Mc. 1, 4")
    assert len(entries) == 1
    assert entries[0].anchor is None


class TestMarkers:
  def test_marker_after_greek_word(self) -> None:
    text = "λοιπὸν ζήσητε2. καὶ σωθήσεται6,"
    assert find_markers(text) == [("2", text.index("2")), ("6", text.index("6"))]

  def test_marker_after_editorial_bracket(self) -> None:
    # Ὥς<τε>1 — the marker follows the closing editorial bracket
    assert [n for n, _ in find_markers("Ὥς<τε>1 τεμόντας")] == ["1"]

  def test_plain_numbers_are_not_markers(self) -> None:
    # section numbers ("45. 1 −") and years stand after spaces or Latin,
    # never glued to a Greek word: no marker may fire on them
    assert find_markers("45. 1 − Καὶ ὁ Τρύφων ἐν 1982") == []

  def test_rewrite_is_the_single_normalization(self) -> None:
    b = block(Layer.TEXT, "λοιπὸν ζήσητε2.")
    assert anchor_block_text(b) == "λοιπὸν ζήσητε⟦2⟧."


class TestAnchorPage:
  def page(self) -> Page:
    p = Page(index=300, printed_page="294")
    p.blocks.append(block(Layer.TEXT, "λοιπὸν ζήσητε2. εἶπον3 δὲ ταῦτα."))
    p.blocks.append(block(
      Layer.APPARATUS,
      "2 Ζήσητε edd. : ζήσετε A   3 Μωσέως : Μωϋσέως Mign.   9 Ὀρφανός sine loco",
    ))
    return p

  def test_resolution_and_honest_counters(self) -> None:
    p = self.page()
    stats = anchor_page(p)
    assert stats == {"entries": 3, "anchored": 2, "unanchored": 1}
    entries = p.blocks[1].entries
    assert entries[0].anchor is not None and entries[0].anchor.block_index == 0
    assert entries[0].anchor.char_offset == "λοιπὸν ζήσητε".index("ζ") + len("ζήσητε")
    # entry 9 has no marker in the text: anchored fields stay None, the
    # entry itself is preserved — never dropped
    assert entries[2].anchor is not None
    assert entries[2].anchor.block_index is None
