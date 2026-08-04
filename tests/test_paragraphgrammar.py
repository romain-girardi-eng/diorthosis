"""The paragraphed-reledmac grammar — every convention here was learned
from the Petrus Plaoul golden (official LombardPress toolchain, 6,293
apps over lectio1-30) and is locked by it."""

from diorthosis.conspectus import Registry
from diorthosis.paragraphgrammar import (
  looks_paragraph_referenced,
  parse_paragraph_entry,
  split_paragraph_entries,
)


def reg() -> Registry:
  r = Registry()
  for w in ("R", "V", "S", "SV", "3V", "EV"):
    r.witnesses[w] = w
  return r


def parse(raw: str):
  _, entries = split_paragraph_entries(raw)
  assert len(entries) == 1, entries
  return parse_paragraph_entry(entries[0], reg())


# -- convention detection ----------------------------------------------

def test_looks_paragraph_referenced() -> None:
  assert looks_paragraph_referenced(
    "18 est] om. R 20 in] om. R SV S 20 Guillelmum] Guillelmi R")


def test_dll_separators_are_not_this_convention() -> None:
  assert not looks_paragraph_referenced(
    "18 est ] om. R ∥ 20 in ] om. R SV S")
  assert not looks_paragraph_referenced(
    "5 cotidie operibus USTV | cotidie M : nouis 7 aptantur MUSTV ]")


# -- splitting ---------------------------------------------------------

def test_fontium_preamble_stays_verbatim() -> None:
  pre, entries = split_paragraph_entries(
    "56-57 I Ad Corinthios 13:12 60 Augustinus, De Trinitate "
    "25 super] supra V 15 considerabo] considera R SV")
  assert "Corinthios" in pre
  assert [e.line for e in entries] == ["25", "15"]


def test_fontium_narrative_does_not_swallow_a_boundary() -> None:
  # "15-16 Psalm 118:18 ..." is narrative (locus refs), NOT an entry —
  # but the genuine boundary hiding after it must still be found
  _, entries = split_paragraph_entries(
    "15-16 Psalm 118:18 tenetur 18 est] om. R 20 in] om. S")
  assert [e.line for e in entries] == ["18", "20"]


def test_elliptic_lemma_head_guard() -> None:
  # an elliptic lemma may end with anything ("nam …52:1]") if its HEAD
  # is clean; fontium narrative must not ride in on the ellipsis
  _, entries = split_paragraph_entries(
    "11 nam …52:1] om. V 13 et] om. R")
  assert [e.line for e in entries] == ["11", "13"]


def test_single_numeric_lemma_is_valid() -> None:
  _, entries = split_paragraph_entries(
    "20 20] vigesimo S 22 et] om. V")
  assert [e.line for e in entries] == ["20", "22"]


# -- parsing -----------------------------------------------------------

def test_juxtaposed_readings_split_on_witness_runs() -> None:
  e = parse("15 considerabo] considera R SV considerata S")
  assert e.parsed
  assert [(r.text, r.attribution.witnesses) for r in e.readings] == [
    ("considera", ["R", "SV"]),
    ("considerata", ["S"]),
  ]


def test_om_and_operator_vocabulary() -> None:
  e = parse("18 est] om. R SV")
  assert e.parsed
  (r,) = e.readings
  assert r.attribution.qualifiers == ["om."]
  assert r.attribution.witnesses == ["R", "SV"]


def test_corr_ex_pre_correction_text_is_a_note() -> None:
  e = parse("315 decretali] decretali corr. ex dectali R")
  assert e.parsed
  (r,) = e.readings
  assert r.text == "decretali"
  assert "corr. ex dectali" in " ".join(r.comments)
  assert r.attribution.witnesses == ["R"]


def test_facsimile_paren_after_witness_is_a_note() -> None:
  e = parse("7 unum] duo S (2r/21)")
  assert e.parsed
  (r,) = e.readings
  assert r.attribution.witnesses == ["S"]
  assert "(2r/21)" in r.comments


def test_duplicate_siglum_run_initial_is_reading_text() -> None:
  # "I] V R SV S V": the FIRST V is the reading's text (Roman numeral),
  # the final V a legitimate witness of the same run
  e = parse("35 I] V R SV S V")
  assert e.parsed
  (r,) = e.readings
  assert r.text == "V"
  assert r.attribution.witnesses == ["R", "SV", "S", "V"]


def test_duplicate_siglum_mid_run_opens_next_reading() -> None:
  # "XIII] VIII R SV S V V": VIII in R SV S, then reading 'V' in V
  e = parse("35 XIII] VIII R SV S V V")
  assert e.parsed
  assert [(r.text, r.attribution.witnesses) for r in e.readings] == [
    ("VIII", ["R", "SV", "S"]),
    ("V", ["V"]),
  ]


def test_trailing_numeric_residue_popped() -> None:
  # a next-entry line number hyphen-split at a band break must not
  # become a witness-less "reading"
  e = parse("18 est] om. R 139–")
  assert e.parsed
  assert len(e.readings) == 1


def test_no_witness_no_qualifier_refuses() -> None:
  e = parse("18 est] fortasse recte")
  assert not e.parsed
