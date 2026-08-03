"""Apparatus grammar tests. Every case mirrors a real entry shape observed in
the reference edition (Paradosis 47); expected values were verified against
the page during the calibration loop."""

from __future__ import annotations

from diorthosis.conspectus import Registry, with_builtin_editors
from diorthosis.grammar import parse_entry


def registry() -> Registry:
  reg = Registry()
  reg.witnesses = {"A": "Parisinus graecus 450", "B": "Musaei Britannici Ms",
                   "A1": "A prima manu"}
  reg.editors = {"Marc.": "Marcovich", "Mign.": "Migne", "Thirlb.": "Thirlby",
                 "Sylb.": "Sylburg", "Steph.": "Estienne", "Mar.": "Maran"}
  return with_builtin_editors(reg)


class TestLemmaReading:
  def test_simple_variant(self) -> None:
    e = parse_entry("Μωσέως : Μωϋσέως Mign., Otto, Goodsp. (hic et infra : 45, 3)",
                    registry())
    assert e is not None
    assert e.lemma == "Μωσέως"
    assert e.readings[0].text == "Μωϋσέως"
    assert e.readings[0].attribution.editors == ["Mign.,", "Otto,", "Goodsp."] \
      or [x.rstrip(",") for x in e.readings[0].attribution.editors] \
         == ["Mign.", "Otto", "Goodsp."]
    assert e.comments == ["(hic et infra : 45, 3)"]

  def test_lemma_attribution_with_connector(self) -> None:
    # "edd. ab Otto" = the editions from Otto onwards
    e = parse_entry("Γένους edd. a Mar. : γένος codd., cett. edd.", registry())
    assert e is not None
    assert e.lemma == "Γένους"
    assert "edd." in e.lemma_attribution.qualifiers
    assert e.readings[0].text == "γένος"

  def test_collective_and_source_tokens(self) -> None:
    e = parse_entry("Οὐδ’ οὐ μὴ codd., LXX : οὐδὲ μὴ Steph., Mar., Mign., Otto.",
                    registry())
    assert e is not None
    assert e.lemma == "Οὐδ’ οὐ μὴ"
    assert "LXX" in e.lemma_attribution.sources
    ed = [x.rstrip(",.") for x in e.readings[0].attribution.editors]
    assert ed == ["Steph.", "Mar.", "Mign.", "Otto"] \
      or [x.rstrip(".") for x in ed] == ["Steph", "Mar", "Mign", "Otto"]


class TestEditorialActions:
  def test_no_variant_action(self) -> None:
    # a word added above the line by the first hand: no variant reading
    e = parse_entry("Τοὺς add. sup. l. A1.", registry())
    assert e is not None
    assert e.lemma == "Τοὺς"
    assert e.readings == []
    assert "add." in e.lemma_attribution.qualifiers
    assert "sup. l." in e.lemma_attribution.qualifiers
    assert "A1" in e.lemma_attribution.witnesses

  def test_transposition_with_target(self) -> None:
    e = parse_entry(
      "Κατὰ − βουλὴν post εἰς τὸν transponendum Thirlb., transp. Marc.",
      registry())
    assert e is not None
    assert e.lemma == "Κατὰ − βουλὴν"
    assert any(q.startswith("post ") for q in e.lemma_attribution.qualifiers)

  def test_midword_parentheses_kept(self) -> None:
    # Κατα(να)θεματίζοντας: editorial letters inside the word stay VERBATIM
    # in the structured lemma (they are printed text, not commentary);
    # comparison-side folding strips the paren characters where needed
    e = parse_entry("Κατα(να)θεματίζοντας − ὅπως Sylb., Marc. : καταθεματίζοντας A",
                    registry())
    assert e is not None
    assert e.lemma.startswith("Κατα(να)θεματίζοντας")

  def test_slash_alternative_parentheses_stay_in_reading(self) -> None:
    # orthographic alternatives "(t/c)" and single letters "(a)" are text
    e = parse_entry("Cappadociae : cappado(t/c)i(a)e A B", registry())
    assert e is not None
    assert e.readings[0].text == "cappado(t/c)i(a)e"

  def test_discourse_word_is_text_when_not_between_attributions(self) -> None:
    e = parse_entry("Habebat : habebat et A B", registry())
    assert e is not None
    assert e.readings[0].text == "habebat et"

  def test_trailing_numeral_is_text_after_plain_word(self) -> None:
    e = parse_entry("Cohortibus XXII : cohortibus XXX A B", registry())
    assert e is not None
    assert e.lemma == "Cohortibus XXII"
    assert e.readings[0].text == "cohortibus XXX"


class TestHonestRefusal:
  def test_latin_prose_entry_refused(self) -> None:
    # a prose observation is not a LEMMA : READING entry; the caller keeps
    # it verbatim — refusing is the correct output
    e = parse_entry(
      "Post ἐσταυρωμένος Thirlb. et Mar. interrogationis signum collocarunt",
      registry())
    assert e is None

  def test_truncated_parenthesis_is_commentary(self) -> None:
    e = parse_entry(
      "Αἱρέσεις prop. Thirlb., Mar., coni. Otto (cf. I Cor. 11, 19 : αἱρέσεις ; Dial. 35,",
      registry())
    assert e is not None
    assert e.lemma == "Αἱρέσεις"
    assert any(c.startswith("(cf.") for c in e.comments)


class TestForeignSeriesRefusal:
  """Göttingen-style entries (']' separator, numeric minuscule sigla, bare
  operator keywords) must be REFUSED, never silently misattributed — all
  four cases below were real misparses before."""

  def test_bracket_separator_refused(self) -> None:
    assert parse_entry("ἐστιν] εσται 458", registry()) is None
    assert parse_entry("Ναβαυ] ιωʹ ναβω 86", registry()) is None

  def test_bare_operator_keyword_refused(self) -> None:
    assert parse_entry("om τῶν 2° 78-569 76", registry()) is None
    assert parse_entry("om σπεῖρον—σπορίμου 59(c pr m): homoiar",
                       registry()) is None

  def test_paradosis_entries_still_parse(self) -> None:
    # the guards must not harm the home series
    e = parse_entry("Μωσέως : Μωϋσέως Mign., Otto (hic et infra : 45, 3)",
                    registry())
    assert e is not None and e.lemma == "Μωσέως"
    e2 = parse_entry("Ἰακὼβ :   Ἰὼβ Sylb.   [ὅτι] prop. Thirlb.", registry())
    assert e2 is not None  # balanced editorial brackets are ours
