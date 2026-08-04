"""Anchoring tests — every expected value mirrors a real convention observed
in the reference edition (Paradosis 47); nothing is invented."""

from __future__ import annotations

from diorthosis.anchor import (
  anchor_block_text,
  anchor_page,
  find_markers,
  split_entries,
)
from diorthosis.match import locate_lemma_start
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

  def test_capital_with_prosgegrammeni_opens_an_entry(self) -> None:
    # ᾝ (U+1F9D) lives in the prosgegrammeni sub-ranges (U+1F88-1FAF),
    # disjoint from the other Greek Extended capitals — p196 of the
    # reference edition went unsplit without them.
    entries = split_entries("1   ᾝρει Sylb. Mor., edd. a Mar. : ἤρει codd.")
    assert [e.anchor.value for e in entries if e.anchor] == ["1"]
    assert entries[0].raw.startswith("ᾝρει")

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
    assert stats == {"entries": 3, "anchored": 2, "unanchored": 1,
                     "ambiguous": 0, "duplicate_markers": 0}
    entries = p.blocks[1].entries
    assert entries[0].anchor is not None and entries[0].anchor.block_index == 0
    assert entries[0].anchor.char_offset == "λοιπὸν ζήσητε".index("ζ") + len("ζήσητε")
    # entry 9 has no marker in the text: anchored fields stay None, the
    # entry itself is preserved — never dropped
    assert entries[2].anchor is not None
    assert entries[2].anchor.block_index is None


class TestMarkerConventionGate:
  def registry(self):
    from diorthosis.conspectus import Registry

    registry = Registry()
    registry.witnesses = {"A": "A", "B": "B", "L": "L"}
    return registry

  def test_resolved_numeric_marker_band_passes(self) -> None:
    page = Page(index=1, printed_page="1", blocks=[
      block(Layer.TEXT, "alpha1 beta2"),
      block(
        Layer.APPARATUS,
        "1 Alpha A : gamma B   2 Beta A : delta B",
      ),
    ])

    anchor_page(page, self.registry())

    entries = page.blocks[1].entries
    assert len(entries) == 2
    assert all(entry.marker_eligible for entry in entries)
    assert all(not entry.refusal_evidence for entry in entries)

  def test_foreign_bracket_separator_refuses_with_evidence(self) -> None:
    page = Page(index=1, printed_page="1", blocks=[
      block(Layer.TEXT, "alpha1"),
      block(Layer.APPARATUS, "1 Alpha] gamma A"),
    ])

    anchor_page(page, self.registry())

    [entry] = page.blocks[1].entries
    assert not entry.marker_eligible
    assert "marker convention gate refused band" in entry.refusal_evidence
    assert "unmatched ']'" in entry.refusal_evidence

  def test_bude_band_never_reaches_generic_parser(self) -> None:
    page = Page(index=1, printed_page="1", blocks=[
      block(Layer.TEXT, "foreign prose without markers"),
      block(Layer.APPARATUS, "1.54 ἐς om. L || 61 τούτων ABV"),
    ])

    anchor_page(page, self.registry())

    [entry] = page.blocks[1].entries
    assert not entry.marker_eligible
    assert "numeric-marker entry splitting found no boundary" \
      in entry.refusal_evidence


class TestDuplicateMarkers:
  """Marker numbers may repeat within a page (5 pages of the reference
  edition). The lemma is the discriminator; without a unique confirmation
  the anchor honestly stays unresolved."""

  def registry(self):
    from diorthosis.conspectus import Registry, with_builtin_editors
    return with_builtin_editors(Registry())

  def page(self) -> Page:
    p = Page(index=208, printed_page="202")
    p.blocks.append(block(
      Layer.TEXT, "δὲ αὐτοὺς καλοῦσιν8. ἔπειτα πεποίηνται τότε8 τὰ ἔργα."))
    p.blocks.append(block(Layer.APPARATUS, "8 Τότε : ποτέ prop. Pearson."))
    return p

  def test_lemma_discriminates_between_occurrences(self) -> None:
    p = self.page()
    stats = anchor_page(p, self.registry())
    assert stats["duplicate_markers"] == 1
    [entry] = p.blocks[1].entries
    assert entry.anchor is not None and entry.anchor.char_offset is not None
    # the SECOND occurrence (after τότε) is the right one
    before = p.blocks[0].text[: entry.anchor.char_offset]
    assert before.endswith("τότε")

  def test_without_registry_ambiguous_stays_unresolved(self) -> None:
    p = self.page()
    stats = anchor_page(p, None)
    assert stats["ambiguous"] == 1
    [entry] = p.blocks[1].entries
    assert entry.anchor is not None and entry.anchor.block_index is None


class TestMarkerTypography:
  def test_marker_after_editorial_bracket_and_elision(self) -> None:
    # full-book histogram: ] 16x, elision apostrophe 10x, ) 2x, ; 1x
    assert [n for n, _ in find_markers("[λέγειν καὶ]8 ἕπεται")] == ["8"]
    assert [n for n, _ in find_markers("οὐκ ἐσθίομεν, ἀλλ’8 ἢ διὰ")] == ["8"]
    assert [n for n, _ in find_markers("τὴν μάθησιν)3, τοῦτο")] == ["3"]
    assert [n for n, _ in find_markers("Τί γάρ ;7 πᾶσα")] == ["7"]

  def test_marker_glued_to_following_greek(self) -> None:
    # lookahead accepts a following Greek letter (πονηρὰ10τοῦ)
    assert [n for n, _ in find_markers("ἀπειθεῖ πονηρὰ10τοῦ")] == ["10"]

  def test_latin_context_numbers_are_not_markers(self) -> None:
    # punctuation alone never carries a marker: needs Greek nearby
    assert find_markers("cf. p. 45, et Dial. 66") == []

  def test_detached_marker_needs_lemma_confirmation(self) -> None:
    from diorthosis.conspectus import Registry, with_builtin_editors

    p = Page(index=264, printed_page="258")
    p.blocks.append(block(Layer.TEXT, "καὶ τὸ ὄνομα ἐδήλωσέ 4 πᾶσιν."))
    p.blocks.append(block(Layer.APPARATUS, "4 Ἐδήλωσέ : ἐδήλωσε A"))
    registry = with_builtin_editors(Registry())
    registry.witnesses["A"] = "A"
    stats = anchor_page(p, registry)
    assert stats["anchored"] == 1
    [entry] = p.blocks[1].entries
    before = p.blocks[0].text[: entry.anchor.char_offset]
    assert before.rstrip().endswith("ἐδήλωσέ")


class TestEntryMonotonicity:
  def test_locus_reference_does_not_fabricate_an_entry(self) -> None:
    # "cf. … 136,  2  Marc." inside entry 1 must NOT split into entry 2
    band = ("1 Τοιγαροῦν : ἐγερῶ edd. (σπερῶ ex LXX et Dial. 136,  "
            "2  Μαρξ.) : τοιγαροῦν ἐγερῶ codd.")
    entries = split_entries(band)
    assert len(entries) == 1
    assert "136" in entries[0].raw


class TestLemmaStart:
  def test_repeated_words_keep_the_full_lemma_span(self) -> None:
    text = "ante Βόες ἐκ τῆς Ῥαχάβ, Βόες post"
    end = text.index(" post")
    assert locate_lemma_start("Βόες ἐκ τῆς Ῥαχάβ, Βόες", text, end) == 5

  def test_punctuation_boundary_and_line_break_hyphenation(self) -> None:
    glued = "diuersa mutatione similiter.Et"
    assert locate_lemma_start("Et", glued, len(glued)) == glued.rindex("Et")

    broken = "naturam verum preter nat-\n\nuram existentis"
    start = broken.index("nat-\n\nuram")
    assert locate_lemma_start("Naturam existentis", broken, len(broken)) == start

  def test_missing_full_sequence_refuses_short_start(self) -> None:
    text = "Alterius rei, deinde alterius"
    assert locate_lemma_start("Alterius rei copiam, alterius", text, len(text)) is None
