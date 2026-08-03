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
    # Κατα(να)θεματίζοντας: editorial letters inside the word, not commentary
    e = parse_entry("Κατα(να)θεματίζοντας − ὅπως Sylb., Marc. : καταθεματίζοντας A",
                    registry())
    assert e is not None
    assert e.lemma.startswith("Καταναθεματίζοντας")


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
