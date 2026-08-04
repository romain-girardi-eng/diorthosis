"""The correction loop: overrides replace parses REPLAYABLY and every
human touch is provenance-marked in the TEI."""

import json

import pytest

from diorthosis.conspectus import Registry
from diorthosis.model import (
  Anchor,
  ApparatusEntry,
  Block,
  Document,
  Layer,
  Page,
  Source,
)
from diorthosis.overrides import apply_overrides, entry_keys, load_overrides
from diorthosis.review import entry_line_span
from diorthosis.tei import to_tei


def doc_with_entries() -> Document:
  doc = Document(source_name="ed.pdf", ingest="borndigital")
  page = Page(index=3, printed_page="294")
  text = Block(layer=Layer.TEXT, text="alpha beta1 gamma",
               source=Source.BORN_DIGITAL, generative=False, confidence=0.9)
  app = Block(layer=Layer.APPARATUS, text="",
              source=Source.BORN_DIGITAL, generative=False, confidence=0.9)
  app.entries = [
    ApparatusEntry(raw="1 Beta : delta A",
                   anchor=Anchor(kind="marker", value="1", block_index=0,
                                 char_offset=11, digit_start=10,
                                 digit_end=11)),
    ApparatusEntry(raw="2 prose note the grammar refuses"),
  ]
  page.blocks = [text, app]
  doc.pages = [page]
  return doc


def test_entry_keys_count_across_page():
  doc = doc_with_entries()
  keys = [k for k, _ in entry_keys(doc.pages[0])]
  assert keys == ["p3-e0", "p3-e1"]


def test_apply_parse_override_wins_and_is_marked(tmp_path):
  doc = doc_with_entries()
  ov = {
    "p3-e0": {
      "action": "parse",
      "lemma": "Beta",
      "lemma_wits": ["A"],
      "readings": [{"text": "delta", "wits": [], "editors": ["Otto"]}],
      "comments": ["reviewer note"],
    },
    "p3-e9": {"action": "verbatim"},
  }
  p = tmp_path / "ov.json"
  p.write_text(json.dumps(ov), encoding="utf-8")
  stats = apply_overrides(doc, load_overrides(p))
  assert stats["applied"] == 1
  assert stats["unmatched"] == ["p3-e9"]   # stale keys stay VISIBLE
  reg = Registry()
  reg.witnesses["A"] = "codex A"
  reg.editors["Otto"] = "Otto"
  xml = to_tei(doc, registry=reg)
  assert 'resp="#human-review"' in xml
  assert "human reviewer" in xml            # header respStmt declared
  assert "<lem" in xml and "Otto" in xml
  # the verbatim raw is retained even under an override
  assert "1 Beta : delta A" in xml


def test_force_verbatim(tmp_path):
  doc = doc_with_entries()
  p = tmp_path / "ov.json"
  p.write_text(json.dumps({"p3-e0": {"action": "verbatim"}}),
               encoding="utf-8")
  stats = apply_overrides(doc, load_overrides(p))
  assert stats["verbatim"] == 1
  xml = to_tei(doc)
  # the entry is a note, not an app — and still review-marked
  assert xml.count("<app") == 0
  assert 'resp="#human-review"' in xml


def test_load_rejects_bad_shapes(tmp_path):
  p = tmp_path / "ov.json"
  p.write_text(json.dumps({"k": {"action": "nope"}}), encoding="utf-8")
  with pytest.raises(ValueError):
    load_overrides(p)
  p.write_text(json.dumps({"k": {"action": "parse"}}), encoding="utf-8")
  with pytest.raises(ValueError):
    load_overrides(p)


def test_entry_line_span_exact_and_fallback():
  lines = ["5 cotidie operibus USTV | cotidie M ∥ 7 aptantur",
           "MUSTV | temptantur Nipperdey ∥ per foramina MU",
           "| foramina STV"]
  # an entry spanning lines 0-1 (split rejoined the flat text)
  span = entry_line_span(lines, "7 aptantur MUSTV | temptantur Nipperdey")
  assert span == (0, 1)
  span = entry_line_span(lines, "per foramina MU | foramina STV")
  assert span == (1, 2)
  # unfindable text falls back to None (whole band)
  assert entry_line_span(lines, "totally absent words here okay") is None
