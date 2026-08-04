"""Witness-state decomposition and used-witness table tests."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from diorthosis.cli import _used_witness_sigla
from diorthosis.conspectus import Registry
from diorthosis.grammar import Attribution, ParsedEntry, Reading
from diorthosis.model import ApparatusEntry, Block, Document, Layer, Page, Source
from diorthosis.tei import TEI_NS, to_tei
from diorthosis.witnesses import decompose, hand_label, witness_table


def registry() -> Registry:
  reg = Registry()
  reg.witnesses = {
    "M": "codex M",
    "A": "codex A",
    "N": "codex N",
    "E": "codex E",
    "P": "codex P",
    "V": "codex V",
    "Nu": "N superscript u",
    "Ea": "E superscript a",
    "Px": "P superscript x",
    "Vm": "V superscript m",
    "ϛ": "older editions",
    "π": "common source",
    "Xac": "isolated witness state",
  }
  return reg


@pytest.mark.parametrize(("siglum", "expected"), [
  ("Mac", ("M", "ac")),
  ("Mpc", ("M", "pc")),
  ("Mc", ("M", "c")),
  ("Mmr", ("M", "mr")),
  ("M*", ("M", "*")),
  ("A1", ("A", "1")),
  ("A9", ("A", "9")),
  ("M", ("M", "")),
])
def test_decompose_recognized_states(siglum, expected):
  assert decompose(siglum, registry()) == expected


@pytest.mark.parametrize("siglum", ["Nu", "Ea", "Px", "Vm", "Nuc", "Nu1"])
def test_decompose_superscript_sigla_stay_atomic(siglum):
  assert decompose(siglum, registry()) == (siglum, "")


def test_decompose_requires_a_declared_base():
  assert decompose("Xac", registry()) == ("Xac", "")


@pytest.mark.parametrize(("siglum", "expected"), [
  ("ϛc", ("ϛ", "c")),
  ("π2", ("π", "2")),
])
def test_decompose_greek_bases(siglum, expected):
  assert decompose(siglum, registry()) == expected


@pytest.mark.parametrize(("hand", "label"), [
  ("ac", "before correction"),
  ("pc", "after correction / corrector"),
  ("c", "after correction / corrector"),
  ("mr", "later hand (manus recentior)"),
  ("*", "reading that prompted a correction"),
  ("1", "hand 1"),
  ("9", "hand 9"),
  ("", ""),
])
def test_hand_label(hand, label):
  assert hand_label(hand) == label


def test_witness_table_is_sorted_and_uses_description_fallbacks():
  reg = registry()
  reg.witnesses["Mac"] = "M before correction"
  assert witness_table(reg, ["Xac", "Mpc", "Mac", "Zc", "Mac"]) == [
    {
      "siglum": "Mac",
      "base": "M",
      "hand": "ac",
      "hand_label": "before correction",
      "description": "M before correction",
    },
    {
      "siglum": "Mpc",
      "base": "M",
      "hand": "pc",
      "hand_label": "after correction / corrector",
      "description": "codex M",
    },
    {
      "siglum": "Xac",
      "base": "Xac",
      "hand": "",
      "hand_label": "",
      "description": "isolated witness state",
    },
    {
      "siglum": "Zc",
      "base": "Zc",
      "hand": "",
      "hand_label": "",
      "description": "",
    },
  ]


def _block(layer: Layer) -> Block:
  return Block(
    layer=layer,
    text="",
    source=Source.BORN_DIGITAL,
    generative=False,
    confidence=0.9,
  )


def doc_with_entries() -> Document:
  parsed = ParsedEntry(
    lemma="alpha",
    lemma_attribution=Attribution(witnesses=["Mac", "M"]),
    readings=[
      Reading(text="beta", attribution=Attribution(witnesses=["Mc"])),
      Reading(text="gamma", attribution=Attribution(witnesses=["Mpc", "Mac"])),
    ],
    comments=[],
  )
  excluded = ParsedEntry(
    lemma="delta",
    lemma_attribution=Attribution(witnesses=["M*"]),
    readings=[],
    comments=[],
  )
  ignored = ParsedEntry(
    lemma="epsilon",
    lemma_attribution=Attribution(witnesses=["A1"]),
    readings=[],
    comments=[],
  )
  apparatus = _block(Layer.APPARATUS)
  apparatus.entries = [
    ApparatusEntry(raw="alpha Mac M : beta Mc : gamma Mpc Mac",
                   parsed_override=parsed),
    ApparatusEntry(raw="delta M*", parsed_override=excluded,
                   override_action="verbatim"),
  ]
  notes = _block(Layer.NOTES)
  notes.entries = [ApparatusEntry(raw="epsilon A1", parsed_override=ignored)]
  return Document(
    source_name="edition.pdf",
    ingest="borndigital",
    pages=[Page(index=0, printed_page="1", blocks=[apparatus, notes])],
  )


def test_document_table_uses_resolved_apparatus_entries():
  reg = registry()
  reg.witnesses.update({
    "Mac": "M before correction",
    "Mc": "M corrector",
  })
  rows = witness_table(reg, _used_witness_sigla(doc_with_entries(), reg))
  assert [row["siglum"] for row in rows] == ["M", "Mac", "Mc", "Mpc"]
  assert rows[1] == {
    "siglum": "Mac",
    "base": "M",
    "hand": "ac",
    "hand_label": "before correction",
    "description": "M before correction",
  }
  assert rows[3]["description"] == "codex M"


def test_tei_witness_states_correspond_to_declared_bases():
  reg = Registry(witnesses={
    "M": "base witness",
    "Mac": "state witness",
    "Nu": "superscript witness",
    "Xac": "state without base",
  })
  root = ET.fromstring(to_tei(Document(source_name="edition.pdf"), registry=reg))
  ns = {"t": TEI_NS}
  witnesses = {
    witness.find("t:abbr", ns).text: witness
    for witness in root.findall(".//t:listWit/t:witness", ns)
  }
  assert witnesses["Mac"].get("corresp") == "#wit-M"
  assert witnesses["M"].get("corresp") is None
  assert witnesses["Nu"].get("corresp") is None
  assert witnesses["Xac"].get("corresp") is None
