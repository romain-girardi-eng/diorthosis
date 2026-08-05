"""The correction loop: overrides replace parses REPLAYABLY, every human
touch is provenance-marked in the TEI, and a correction that no longer
matches the entry it was made against REFUSES rather than land elsewhere."""

import json
import os
import subprocess
import sys
import textwrap

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
from diorthosis.overrides import (
  FORMAT,
  apply_overrides,
  entry_keys,
  load_overrides,
  source_digest,
  source_excerpt,
)
from diorthosis.review import bind_record, entry_line_span, export_file
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


def bound(doc: Document, key: str, body: dict) -> dict:
  """A one-record overrides file bound to the CURRENT content of `key`."""
  entry = dict(entry_keys(doc.pages[0]))[key]
  return export_file({key: bind_record(body, entry)})


def write(tmp_path, payload) -> str:
  p = tmp_path / "ov.json"
  p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
  return str(p)


PARSE_BODY = {
  "action": "parse",
  "lemma": "Beta",
  "lemma_wits": ["A"],
  "readings": [{"text": "delta", "wits": [], "editors": ["Otto"]}],
  "comments": ["reviewer note"],
}


def test_entry_keys_count_across_page():
  doc = doc_with_entries()
  keys = [k for k, _ in entry_keys(doc.pages[0])]
  assert keys == ["p3-e0", "p3-e1"]


def test_apply_parse_override_wins_and_is_marked(tmp_path):
  doc = doc_with_entries()
  payload = bound(doc, "p3-e0", PARSE_BODY)
  payload["entries"]["p3-e9"] = {"action": "verbatim",
                                 "source_sha": "0" * 12}
  stats = apply_overrides(doc, load_overrides(write(tmp_path, payload)))
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
  payload = bound(doc, "p3-e0", {"action": "verbatim"})
  stats = apply_overrides(doc, load_overrides(write(tmp_path, payload)))
  assert stats["verbatim"] == 1
  xml = to_tei(doc)
  # the entry is a note, not an app — and still review-marked
  assert xml.count("<app") == 0
  assert 'resp="#human-review"' in xml


def test_load_rejects_bad_shapes(tmp_path):
  doc = doc_with_entries()
  for body, expect in (({"action": "nope"}, "'action' must be"),
                       ({"action": "parse"}, "needs a 'lemma'")):
    with pytest.raises(ValueError, match=expect):
      load_overrides(write(tmp_path, bound(doc, "p3-e0", body)))


def test_load_rejects_a_record_with_no_content_binding(tmp_path):
  payload = {"format": FORMAT,
             "entries": {"p3-e0": {"action": "verbatim"}}}
  with pytest.raises(ValueError, match="source_sha"):
    load_overrides(write(tmp_path, payload))


def test_load_rejects_unversioned_and_unknown_formats(tmp_path):
  doc = doc_with_entries()
  legacy = bound(doc, "p3-e0", PARSE_BODY)["entries"]   # the pre-1.0 flat file
  with pytest.raises(ValueError, match="no 'format' key"):
    load_overrides(write(tmp_path, legacy))
  future = bound(doc, "p3-e0", PARSE_BODY)
  future["format"] = "diorthosis-overrides/2"
  with pytest.raises(ValueError, match="unknown overrides format"):
    load_overrides(write(tmp_path, future))
  with pytest.raises(ValueError, match="'entries' object"):
    load_overrides(write(tmp_path, {"format": FORMAT}))


def test_digest_is_stable_across_processes():
  """No PYTHONHASHSEED dependence: the same slice must bind identically in
  the process that reviewed and the process that rebuilds."""
  code = textwrap.dedent("""
    from diorthosis.model import ApparatusEntry
    from diorthosis.overrides import source_digest
    print(source_digest(ApparatusEntry(raw="x", source="1 Beta : delta A")))
  """)
  seen = set()
  for seed in ("0", "1", "12345"):
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, check=True,
                         env={**os.environ, "PYTHONHASHSEED": seed})
    seen.add(out.stdout.strip())
  assert len(seen) == 1
  assert seen == {source_digest(
    ApparatusEntry(raw="x", source="1 Beta : delta A"))}
  assert len(seen.pop()) == 12                # short enough to read in a diff


def test_digest_ignores_band_rewrapping_but_not_content():
  """A band that re-wraps is the same entry; a band that reads differently
  is not — md-ce I8's line unwrap is the only transform in the binding."""
  flat = ApparatusEntry(raw="x", source="1 Beta : delta A")
  wrapped = ApparatusEntry(raw="x", source="1 Beta :\ndelta A")
  crlf = ApparatusEntry(raw="x", source="1 Beta :\r\ndelta A")
  assert source_digest(flat) == source_digest(wrapped) == source_digest(crlf)
  assert source_digest(flat) != source_digest(
    ApparatusEntry(raw="x", source="1 Beta : delta B"))
  # spacing is content: it is where the splitter drew the boundary
  assert source_digest(flat) != source_digest(
    ApparatusEntry(raw="x", source="1  Beta : delta A"))


def test_drifted_binding_refuses_loudly_and_itemised(tmp_path):
  doc = doc_with_entries()
  payload = bound(doc, "p3-e0", PARSE_BODY)
  payload["entries"]["p3-e0"]["source_sha"] = "deadbeefcafe"
  overrides = load_overrides(write(tmp_path, payload))
  with pytest.raises(ValueError) as excinfo:
    apply_overrides(doc, overrides)
  msg = str(excinfo.value)
  assert "p3-e0" in msg                       # WHICH entry drifted
  assert "deadbeefcafe" in msg                # what it was bound to
  assert "1 Beta : delta A" in msg            # what it NOW says
  assert "resp=\"#human-review\"" in msg      # why this matters
  # refusal is total: nothing was half-applied
  assert all(e.override_action == "" and e.parsed_override is None
             for _, e in entry_keys(doc.pages[0]))


def test_apply_refuses_an_unbound_record_even_bypassing_the_loader():
  """The dangerous function defends itself: a hand-built dict that never
  went through load_overrides is still refused, not applied on trust."""
  doc = doc_with_entries()
  with pytest.raises(ValueError, match="no source_sha"):
    apply_overrides(doc, {"p3-e0": dict(PARSE_BODY)})


def test_upstream_resplit_cannot_retarget_a_correction(tmp_path):
  """The defect this binding exists for: a changed band split shifts the
  positional numbering, so the old key now points at a DIFFERENT entry."""
  doc = doc_with_entries()
  payload = bound(doc, "p3-e0", PARSE_BODY)
  # upstream now splits one more entry ahead of it
  drifted = doc_with_entries()
  drifted.pages[0].blocks[1].entries.insert(
    0, ApparatusEntry(raw="0 alpha : omega B"))
  overrides = load_overrides(write(tmp_path, payload))
  with pytest.raises(ValueError, match="0 alpha : omega B"):
    apply_overrides(drifted, overrides)


def test_export_file_round_trips_through_load_and_apply(tmp_path):
  """What the review page downloads is what a build can replay."""
  doc = doc_with_entries()
  entry = dict(entry_keys(doc.pages[0]))["p3-e1"]
  record = bind_record({"action": "verbatim", "note": "prose"}, entry)
  assert record["source_sha"] == source_digest(entry)
  assert record["source_excerpt"] == source_excerpt(entry)
  payload = export_file({"p3-e1": record})
  assert payload["format"] == FORMAT
  stats = apply_overrides(doc, load_overrides(write(tmp_path, payload)))
  assert stats == {"applied": 0, "verbatim": 1, "unmatched": []}


def test_source_excerpt_is_clipped_and_flattened():
  entry = ApparatusEntry(raw="x", source="1 Beta :\n  " + "delta " * 60)
  excerpt = source_excerpt(entry)
  assert "\n" in entry.source_slice and "\n" not in excerpt
  assert len(excerpt) == 120 and excerpt.endswith("…")


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
