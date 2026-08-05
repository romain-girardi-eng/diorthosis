"""Apparatus grammar tests. Every case mirrors a real entry shape observed in
the reference edition (Paradosis 47); expected values were verified against
the page during the calibration loop."""

from __future__ import annotations

from diorthosis.conspectus import Registry, with_builtin_editors
from diorthosis.grammar import gate_marker_band, parse_entry
from diorthosis.model import Anchor, ApparatusEntry


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
  def test_first_person_action_is_current_editor_attribution(self) -> None:
    e = parse_entry("Obiectis scripsimus : obiectis A B", registry())
    assert e is not None
    assert e.lemma == "Obiectis"
    assert e.lemma_attribution.editors == ["scripsimus"]
    assert e.lemma_attribution.qualifiers == []

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
  def test_unattributed_reading_parses_in_marker_convention(self) -> None:
    # single-witness editions print manuscript readings bare (Bobichon's
    # codex A); the anchored marker is the structural evidence here, so
    # the generic grammar keeps them — the attribution-based refusals
    # belong to the verse/line/paragraph grammars (review adjudication)
    e = parse_entry("alpha : beta", registry())
    assert e is not None and [r.text for r in e.readings] == ["beta"]

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


def marker_entry(number: str, raw: str) -> ApparatusEntry:
  return ApparatusEntry(raw=raw, anchor=Anchor(kind="marker", value=number))


class TestMarkerBandAttributionFloor:
  """Numbered editorial PROSE — footnotes, fontes, translators' notes —
  carries the marker convention's whole printed shape: a superscript number
  glued to a word, a colon inside the note. Shape alone cannot tell it from
  an apparatus; the printed sigla can. Hence a whole-band floor: somewhere
  in an accepted band a proposed variant must name a witness, an editor or
  a cited version. Measured inert on the reference edition (Bobichon,
  pages 188-560: 186/186 marker bands still accepted)."""

  def test_numbered_footnote_band_is_refused(self) -> None:
    # /tmp/gen10/insolubles.pdf page 63, verbatim: an ENGLISH editorial
    # footnote band. Note 46 refuses; note 47's PROSE colon made it "parse",
    # one entry in two cleared the 50% floor, and the note was emitted as
    # <lem>/<rdg> with the footnote number as the locus.
    entries = [
      marker_entry("46", "See Aristotelis opera cum Averrois commentaria, "
                         "vol. VIII In Metaphysicen V 7, de ente, comm. 14 f. 117E."),
      marker_entry("47", "Note that in this argument, Segrave implicitly appeals "
                         "to Bradwardine’s famous second postulate : “Every "
                         "proposition signifies or means as a matter of fact or "
                         "absolutely everything which follows from it as a matter "
                         "of fact or absolutely”."),
    ]

    decision = gate_marker_band(entries, registry(), resolved_markers=1)

    assert not decision.accepted
    assert decision.evidence.startswith("marker convention gate refused band:")
    assert "no witness, editor or source is named" in decision.evidence
    assert "1/2 trial-parsed entries" in decision.evidence

  def test_bibliographic_note_band_without_readings_is_refused(self) -> None:
    # same edition, page 16: a pure reference note. It parses only because a
    # trailing locus ("p. 198.") looks like an attribution, and proposes NO
    # reading at all — a band that claims a lemma and nothing else is prose.
    entries = [
      marker_entry("13", "See, e.g., Klima, ‘Existence and Reference in "
                         "Medieval Logic’, p. 198."),
    ]

    decision = gate_marker_band(entries, registry(), resolved_markers=1)

    assert not decision.accepted
    assert "no witness, editor or source is named on any of the 0 reading(s)" \
      in decision.evidence

  def test_bare_entry_rides_on_the_band_of_an_attributed_neighbour(self) -> None:
    # THE distinction this floor must not cross: editions collated against a
    # single witness print their readings bare by design (Bobichon's codex A,
    # ~121 entries). Refusing them entry by entry cost 6 points of parse rate
    # (99.0 -> 93.0) and was reverted; the floor is band-level for that reason.
    bare = marker_entry("1", "Ἰακὼβ : Ἰὼβ")
    entries = [bare, marker_entry("2", "Μωσέως : Μωϋσέως Mign.")]

    decision = gate_marker_band(entries, registry(), resolved_markers=1)

    assert decision.accepted and decision.evidence == ""
    parsed = parse_entry(bare.raw, registry())
    assert parsed is not None
    assert parsed.readings[0].attribution.empty

  def test_a_cited_version_satisfies_the_floor(self) -> None:
    # "Ἔθνεσιν : τῷ ἔθνει LXX" — a version is an authority like a siglum
    entries = [marker_entry("4", "Ἔθνεσιν : τῷ ἔθνει LXX")]

    assert gate_marker_band(entries, registry(), resolved_markers=1).accepted

  def test_qualifiers_alone_do_not_satisfy_the_floor(self) -> None:
    # "om.", "ed.", "cf.", "sic" are ordinary prose words as often as they
    # are apparatus latinity; a band evidenced only by them names nobody
    entries = [marker_entry("5", "Alpha : beta om."),
               marker_entry("6", "Gamma : delta cf.")]

    decision = gate_marker_band(entries, registry(), resolved_markers=1)

    assert not decision.accepted
    assert "no witness, editor or source is named" in decision.evidence

  def test_earlier_gate_conditions_still_report_first(self) -> None:
    # the floor is the LAST condition: a foreign separator must keep naming
    # itself, so the refusal evidence stays diagnostic
    entries = [marker_entry("1", "Alpha : beta || Gamma : delta")]

    decision = gate_marker_band(entries, registry(), resolved_markers=1)

    assert not decision.accepted
    assert "foreign separator '||'" in decision.evidence
