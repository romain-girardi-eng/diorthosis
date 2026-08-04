"""Adversarial refusal tests for the verse-referenced apparatus grammar."""

from diorthosis.versegrammar import parse_verse_entry, split_verse_entries


def test_unattributed_rejected_reading_refuses_structure() -> None:
  raw = "1:1 α WH ] β"
  entries = split_verse_entries(raw)

  assert len(entries) == 1
  entry = parse_verse_entry(entries[0])
  assert not entry.parsed
  assert entry.raw == "α WH ] β"


def test_glued_bullet_splits_without_rewriting_source_slices() -> None:
  band = "1:1 α WH ] β RP•γ WH ] δ Treg"
  entries = split_verse_entries(band)

  assert [(entry.loc, entry.raw) for entry in entries] == [
    ("1:1", "α WH ] β RP"),
    ("1:1", "γ WH ] δ Treg"),
  ]
  assert [entry.source_slice for entry in entries] == [
    "1:1 α WH ] β RP",
    "γ WH ] δ Treg",
  ]
