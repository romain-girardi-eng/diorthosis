"""Teubner/OCT colon-negative apparatus — pinned to printed shapes.

These entries are the convention as West, Maurer and the Teubner/OCT
series print it. They are not reconstructed. The grammar must not steal
Plaoul (no spaced colon) or Budé (``||``).
"""

from diorthosis.conspectus import Registry
from diorthosis.teubnergrammar import (
  gate_teubner_band,
  looks_teubner,
  parse_teubner_entry,
  split_teubner_entries,
)


def reg(*sigla: str) -> Registry:
  r = Registry()
  for s in sigla or ("A", "B", "M", "V"):
    r.witnesses[s] = s
  r.editors["vulg."] = "vulgata"
  return r


def parse(raw: str, registry: Registry | None = None):
  entries = split_teubner_entries(raw)
  assert len(entries) == 1, entries
  return parse_teubner_entry(entries[0], registry or reg())


def test_looks_teubner_requires_the_colon() -> None:
  assert looks_teubner("12 λόγος] λέξις A : om. B")
  assert not looks_teubner("18 est] om. R 20 in] om. R SV S")


def test_plaoul_shape_is_not_this_convention() -> None:
  assert not looks_teubner(
    "18 est] om. R 20 in] om. R SV S 20 Guillelmum] Guillelmi R")


def test_reledmac_and_bude_separators_are_foreign() -> None:
  assert not looks_teubner("12 λόγος] λέξις A ∥ 15 εἶπεν] λέγει B")
  assert not looks_teubner("12 λόγος] λέξις A | εἶπεν B")
  assert not looks_teubner("12 λέξις : λόγος A || ῥῆμα B")


def test_gate_accepts_a_negative_band() -> None:
  decision = gate_teubner_band(
    "12 λόγος] λέξις A : om. B 15-16 καὶ εἶπεν] om. M",
    reg(),
  )
  assert decision.accepted, decision.evidence


def test_gate_refuses_unattributed_prose() -> None:
  decision = gate_teubner_band(
    "12 hello] this is editorial prose : still prose here",
    reg(),
  )
  assert not decision.accepted


def test_split_two_entries() -> None:
  entries = split_teubner_entries(
    "12 λόγος] λέξις A : om. B 15 καὶ εἶπεν] om. M")
  assert [e.line for e in entries] == ["12", "15"]
  assert entries[0].source_slice.startswith("12 ")


def test_negative_lemma_has_no_witnesses() -> None:
  entry = parse("12 λόγος] λέξις A : om. B")
  assert entry.parsed
  assert entry.lemma == "λόγος"
  assert entry.lemma_attribution is not None
  assert entry.lemma_attribution.empty
  assert [r.text for r in entry.readings] == ["λέξις", ""]
  assert entry.readings[0].attribution.witnesses == ["A"]
  assert "om." in entry.readings[1].attribution.qualifiers
  assert entry.readings[1].attribution.witnesses == ["B"]


def test_vulgata_and_range() -> None:
  entry = parse("15-16 εἰπεῖν] εἶπεν vulg. : λέγει A", reg("A"))
  assert entry.parsed
  assert entry.line == "15-16"
  assert "vulg." in entry.readings[0].attribution.qualifiers
  assert entry.readings[1].attribution.witnesses == ["A"]
