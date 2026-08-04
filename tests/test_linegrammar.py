"""The line-referenced (reledmac) grammar — every convention here was
learned from the DLL Bellum Alexandrinum golden and is locked by it."""

from diorthosis.conspectus import Registry
from diorthosis.linegrammar import (
  burst_sigla,
  parse_line_entry,
  split_line_entries,
)


def reg() -> Registry:
  r = Registry()
  for w in ("M", "U", "S", "T", "V", "Mc", "Mac", "Tc", "Tac", "Uc",
            "Vac", "ϛ"):
    r.witnesses[w] = w
  for e in ("Nipperdey", "Castiglioni", "Schneider", "Larsen", "Klotz",
            "Vielhaber", "Oudendorp", "Madvig", "Cellarius", "Dauisius",
            "Du Pontet", "DuPontet", "Fleischer"):
    r.editors[e] = e
  return r


def parse(raw: str, line: str = "5"):
  entries = split_line_entries(f"{line} {raw}")
  assert len(entries) == 1, entries
  return parse_line_entry(entries[0], reg())


# -- splitting ---------------------------------------------------------

def test_split_on_separator_and_inherited_line():
  es = split_line_entries("5 alpha M ∥ beta U ∥ 7 gamma S")
  assert [(e.line, e.raw) for e in es] == [
    ("5", "alpha M"), ("5", "beta U"), ("7", "gamma S")]


def test_split_crux_and_range():
  es = split_line_entries("11–12 ◊ alpha M ∥ 14.24–15.2 beta U")
  assert es[0].crux and es[0].line == "11–12"
  assert es[1].line == "14.24–15.2"


def test_unseparated_boundaries():
  # after a paren note, a dubitative "?", or a bare locus reference the
  # ∥ is omitted and the next entry opens with its line number
  es = split_line_entries(
    "5 alpha M (cf. BC 1.2) 7 beta U | an gamma (u. supra)? "
    "9 delta S | sed cf. 57.6 11 epsilon T")
  assert [e.line for e in es] == ["5", "7", "9", "11"]


def test_parenthesized_reading_before_number_refuses_ambiguous_boundary():
  raw = "5 duodecim M | (ut dicitur) 12 milia U | duodecim V"
  entries = split_line_entries(raw)
  assert len(entries) == 1
  assert entries[0].raw == raw.removeprefix("5 ")
  parsed = parse_line_entry(entries[0], reg())
  assert not parsed.parsed


# -- sigla -------------------------------------------------------------

def test_burst_glued_sigla_longest_first():
  assert burst_sigla(["MUSTV"], reg()) == ["M", "U", "S", "T", "V"]
  assert burst_sigla(["USTcV"], reg()) == ["U", "S", "Tc", "V"]
  assert burst_sigla(["MUSTcVac,"], reg()) == ["M", "U", "S", "Tc", "Vac,"]


def test_burst_only_on_complete_dissolution():
  assert burst_sigla(["MUX"], reg()) == ["MUX"]      # X undeclared
  assert burst_sigla(["multa"], reg()) == ["multa"]  # plain word


# -- parsing -----------------------------------------------------------

def test_lemma_and_readings():
  e = parse("aptantur MUSTV | temptantur Nipperdey")
  assert e.parsed
  assert e.lemma == "aptantur"
  assert e.lemma_attribution.witnesses == ["M", "U", "S", "T", "V"]
  assert [(r.text, r.attribution.editors) for r in e.readings] == [
    ("temptantur", ["Nipperdey"])]


def test_final_paren_is_note_mid_paren_stays():
  e = parse("intermittebat U (cf. 37.1) | intermittebant (sc. Alexandrini) M")
  assert e.lemma == "intermittebat"
  assert "(cf. 37.1)" in e.comments
  assert e.readings[0].text == "intermittebant (sc. Alexandrini)"


def test_relative_clause_only_after_attribution():
  e = parse("foramina U | foramina S, quos secutus foramina seclusit "
            "Vielhaber ut glossema")
  assert e.readings[0].text == "foramina"
  # the clause went to comments, not into the reading
  assert any("quos secutus" in c for c in e.comments)
  # a comma-clause inside a sentence-length reading is the reading's text
  e2 = parse("alpha M | ut uix defendi posse se confiderent, quibus et "
             "superioribus locis subleuabantur Larsen")
  assert e2.readings[0].text.startswith("ut uix")
  assert "quibus et superioribus" in e2.readings[0].text


def test_ref_tails_are_comments():
  e = parse("in MUSTV | [in] Schneider coll. Hirt. 8.27.4")
  assert e.readings[0].text == "[in]"
  assert e.readings[0].attribution.editors == ["Schneider"]
  assert any(c.startswith("coll.") for c in e.comments)


def test_uel_tail_after_siglum():
  e = parse("suffossa Uc | soffosa Vac uel soffossa")
  assert e.readings[0].text == "soffosa"
  assert any(c.startswith("uel") for c in e.comments)


def test_an_conjecture_vs_gerundive():
  e = parse("obiectis M | an contexerant (cf. BC 2.10.5)?")
  assert e.readings[0].text == "contexerant"
  assert "an?" in e.readings[0].attribution.qualifiers
  e2 = parse("hostium MUSTV | an secludendum ut glossema?")
  assert e2.readings == []          # editorial ACTION: note, not a form


def test_nisi_mauis_conjectures_and_narrative():
  e = parse("obiectis M | nisi mauis iunctis (cf. Vitr. 10.2.14) uel adiunctis")
  assert [r.text for r in e.readings] == ["iunctis", "adiunctis"]
  assert all("nisi mauis" in r.attribution.qualifiers for r in e.readings)
  e2 = parse("casum M | nisi mauis casum secludere (cf. Liu. 21.34.8)")
  assert e2.readings == []          # infinitive tail = narrative


def test_editor_recovery_mid_segment():
  e = parse("alpha M | constantiaque uirtutum Klotz post facta transposuerit")
  assert e.readings[0].text == "constantiaque uirtutum"
  assert e.readings[0].attribution.editors == ["Klotz"]


def test_lemma_bracket_terminator_and_occurrence_digit():
  e = parse("Nam palam sexagiens cum ] | alpha M")
  assert e.lemma == "Nam palam sexagiens cum"
  e2 = parse("defensionem eius1 M | defensonem eius Uc")
  assert e2.lemma == "defensionem eius"


def test_spaced_editor_prepass():
  e = parse("adiuuante natura MUSTV | adiuuante ⟨nostros⟩ natura Du Pontet")
  assert e.readings[0].attribution.editors == ["DuPontet"]
