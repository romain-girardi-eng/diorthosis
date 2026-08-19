"""Budé run-in apparatus — ``||`` separates entries, lemma carries wits.

Pinned to the printed Herodian shape (de Rivas 2022)::

    5 μυθῶδες ABVGF : ἀσθενές L || 6 ἐλεγχθήσεται VGFL : ἐλεχθήσεται AB
"""

from diorthosis.budegrammar import (
  gate_bude_band,
  looks_bude,
  parse_bude_entry,
  split_bude_entries,
)
from diorthosis.conspectus import Registry


def reg(*sigla: str) -> Registry:
  r = Registry()
  for s in sigla or ("A", "B", "V", "G", "F", "L"):
    r.witnesses[s] = s
  return r


def parse(raw: str, registry: Registry | None = None):
  entries = split_bude_entries(raw)
  assert len(entries) == 1, [e.raw for e in entries]
  return parse_bude_entry(entries[0], registry or reg())


def test_looks_bude_requires_parallel_and_a_colon() -> None:
  assert looks_bude("5 μυθῶδες ABVGF : ἀσθενές L || 6 ἐλεγχθήσεται VGFL : ἐλεχθήσεται AB")
  assert not looks_bude("12 λόγος] λέξις A : om. B")


def test_editorial_brackets_after_a_colon_are_not_segrave() -> None:
  assert looks_bude("3 ὡς ἂν μὴ ABV : [ὡς ἄν] FL || 5 μυθῶδες ABV : ἀσθενές L")


def test_segrave_continuation_is_not_this_convention() -> None:
  band = "30 album] albus E4 || 31 lemma] reading E8"
  assert not looks_bude(band)
  decision = gate_bude_band(band, reg("E4", "E8"))
  assert not decision.accepted
  assert "paragraph continuation" in decision.evidence


def test_gate_accepts_herodian_clean_pair() -> None:
  decision = gate_bude_band(
    "5 μυθῶδες ABVGF : ἀσθενές L || 6 ἐλεγχθήσεται VGFL : ἐλεχθήσεται AB",
    reg(),
  )
  assert decision.accepted, decision.evidence


def test_gate_refuses_a_page_of_narrative() -> None:
  decision = gate_bude_band(
    "see the note || and also this commentary || still no colon here",
    reg(),
  )
  assert not decision.accepted


def test_split_on_parallel() -> None:
  entries = split_bude_entries(
    "5 μυθῶδες ABVGF : ἀσθενές L || 6 ἐλεγχθήσεται VGFL : ἐλεχθήσεται AB")
  assert [e.line for e in entries] == ["5", "6"]


def test_inherited_locus() -> None:
  entries = split_bude_entries(
    "5 μυθῶδες ABVGF : ἀσθενές L || ἐλεγχθήσεται VGFL : ἐλεχθήσεται AB")
  assert [e.line for e in entries] == ["5", "5"]


def test_parse_positive_lemma() -> None:
  entry = parse("5 μυθῶδες ABVGF : ἀσθενές L")
  assert entry.parsed
  assert entry.lemma == "μυθῶδες"
  assert entry.lemma_attribution is not None
  assert set(entry.lemma_attribution.witnesses) == {"A", "B", "V", "G", "F"}
  assert entry.readings[0].text == "ἀσθενές"
  assert entry.readings[0].attribution.witnesses == ["L"]


def test_narrative_remainder_is_verbatim() -> None:
  entry = parse("1.11 ἔργων ABV : τῶν L in G uerbum ἔργων difficile legitur ἐνίων F")
  assert not entry.parsed


def test_omission_only_entry() -> None:
  entry = parse("5 χρόνῳ om. L")
  assert entry.parsed
  assert entry.line == "5"
  assert entry.lemma == "χρόνῳ"
  assert entry.readings[0].text == ""
  assert "om." in entry.readings[0].attribution.qualifiers
  assert entry.readings[0].attribution.witnesses == ["L"]


def test_glued_hand_siglum_bursts() -> None:
  entry = parse("43 βασιλειῶν ABVG² : βασιλέων GL")
  assert entry.parsed
  assert entry.lemma == "βασιλειῶν"
  assert set(entry.lemma_attribution.witnesses) == {"A", "B", "V", "G"}


def test_section_dot_locus() -> None:
  entry = parse("1.11 ἔργων ABV : τῶν L")
  assert entry.parsed
  assert entry.line == "1.11"
  assert entry.lemma == "ἔργων"
  assert "A" in entry.lemma_attribution.witnesses
  assert entry.readings[0].text == "τῶν"
