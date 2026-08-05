"""Per-edition human-review overrides — the correction loop.

A grammar gets an edition to 90–99 %; the last stretch is human review.
Overrides make that review REPLAYABLE: a JSON file per edition records
each correction, `diorthosis build --overrides` applies it on every
rebuild, and the TEI marks every overridden entry with
``resp="#human-review"`` — a human correction is provenance, never
silently merged into what the grammar read.

Because an override carries a scholar's authority into the TEI, WHERE it
lands is a correctness question, not a convenience one. A positional key
alone cannot answer it: any upstream change in band splitting shifts the
numbering, and the correction would then be replayed onto a DIFFERENT
entry — a fabricated structure wearing ``resp="#human-review"``. So each
record is bound to the CONTENT it was made against, and a replay that no
longer matches REFUSES, loudly and itemised.

File format (``diorthosis-overrides/1``)::

    {
      "format": "diorthosis-overrides/1",
      "entries": {
        "p300-e6": {
          "source_sha": "5e7a5cd50cd1",
          "source_excerpt": "3 Μωσέως : Μωϋσέως Mign., Otto, Goodsp.",
          "action": "parse",
          "lemma": "Μωσέως",
          "lemma_wits": [], "lemma_editors": [],
          "readings": [
            {"text": "Μωϋσέως", "wits": [], "editors": ["Mign.", "Otto"],
             "qualifiers": []}
          ],
          "comments": ["(hic et infra : 45, 3)"],
          "note": "reviewer: split the glued editors"
        },
        "p301-e2": {"source_sha": "0f0d0e6c6b70",
                    "action": "verbatim",
                    "note": "prose note, not a variant entry"}
      }
    }

``format`` is checked exactly: an unversioned file (the pre-1.0 flat
object) and a version from a newer diorthosis are both clean errors, not
best-effort reads. 1.0 can freeze this shape.

The key ``p{page.index}-e{k}`` LOCATES a candidate entry (``page.index``
is the 0-based file page, ``k`` counts apparatus entries across the whole
page in document order). ``source_sha`` then DECIDES whether that
candidate is the entry the human corrected. A mismatch is never
re-matched fuzzily and never skipped in silence: the whole replay
refuses, naming each drifted key and what its entry now says.

Actions:

- ``parse``   — replace the grammar's structured reading of the entry;
- ``verbatim`` — force the honest refusal: the entry is kept as a
  verbatim note (use it when the grammar mis-parses narrative).

The verbatim raw text of the entry is NEVER touched by an override.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .grammar import Attribution, ParsedEntry, Reading
from .model import Document, Layer

FORMAT = "diorthosis-overrides/1"
"""Explicit format marker. Version 1 fixes both the container shape and
the digest (first 12 hex characters of SHA-256 over the line-unwrapped
source slice); any change to either is a new version, never a silent
reinterpretation of files already on disk."""

_SHA_CHARS = 12
_EXCERPT_CHARS = 120


def entry_keys(page) -> list[tuple[str, object]]:
  """(key, entry) pairs for one page, entries counted across all
  apparatus blocks in document order."""
  out = []
  k = 0
  for block in page.blocks:
    if block.layer is not Layer.APPARATUS:
      continue
    for e in block.entries or []:
      out.append((f"p{page.index}-e{k}", e))
      k += 1
  return out


def source_digest(entry) -> str:
  """Content binding for one apparatus entry.

  SHA-256, not ``hash()``: PYTHONHASHSEED must never decide whether a
  human correction replays. Truncated to 12 hex characters so the binding
  stays readable in a diff — it is only ever compared for equality
  against the single entry the positional key located, so it is an
  integrity check, not a lookup key.

  Hashed over the IMMUTABLE ``source_slice`` with its physical line
  breaks unwrapped to single spaces — md-ce I8's sole declared apparatus
  transform. Where the printed band happened to wrap is a typographic
  accident; the codepoints, spacing and entry boundaries are the content,
  and any change to those is exactly the drift this binding must catch.
  """
  flat = (entry.source_slice.replace("\r\n", "\n").replace("\r", "\n")
          .replace("\n", " "))
  return hashlib.sha256(flat.encode("utf-8")).hexdigest()[:_SHA_CHARS]


def source_excerpt(entry) -> str:
  """Human-readable trace of what the correction was made against.

  Carried in the record for the reviewer's benefit — a drift report can
  then show BOTH texts. It is provenance only: matching is decided by
  ``source_sha`` alone, never by this string.
  """
  return _clip(" ".join(entry.source_slice.split()))


def _clip(text: str) -> str:
  return text if len(text) <= _EXCERPT_CHARS else text[:_EXCERPT_CHARS - 1] + "…"


def load_overrides(path: str | Path) -> dict[str, dict]:
  """Read and validate an overrides file; returns its entry records.

  Every failure here is a refusal to guess: an unversioned or unknown
  container, a record with no content binding, an unusable action. A file
  that loads is a file whose every record can be checked against the
  build it is replayed on.
  """
  data = json.loads(Path(path).read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError(f"{path}: overrides file must be a JSON object")

  version = data.get("format")
  if version is None:
    raise ValueError(
      f"{path}: not a versioned overrides file (no 'format' key). Files "
      f"written before {FORMAT} bind corrections by position alone, so "
      f"replaying them can attach a human-reviewed parse to a different "
      f"entry. Re-run 'diorthosis review' on this build and re-export.")
  if version != FORMAT:
    raise ValueError(
      f"{path}: unknown overrides format {version!r}; this diorthosis "
      f"reads {FORMAT}")
  entries = data.get("entries")
  if not isinstance(entries, dict):
    raise ValueError(f"{path}: {FORMAT} needs an 'entries' object")

  for key, ov in entries.items():
    if not isinstance(ov, dict) or ov.get("action") not in ("parse", "verbatim"):
      raise ValueError(
        f"override {key!r}: 'action' must be 'parse' or 'verbatim'")
    sha = ov.get("source_sha")
    if not isinstance(sha, str) or len(sha) != _SHA_CHARS:
      raise ValueError(
        f"override {key!r}: needs a {_SHA_CHARS}-character 'source_sha' "
        f"binding it to the entry it was made against")
    if ov["action"] == "parse" and not isinstance(ov.get("lemma"), str):
      raise ValueError(f"override {key!r}: action 'parse' needs a 'lemma'")
  return entries


def _attribution(d: dict, wits_key: str, eds_key: str,
                 quals_key: str) -> Attribution:
  a = Attribution()
  a.witnesses = [str(w) for w in d.get(wits_key, [])]
  a.editors = [str(e) for e in d.get(eds_key, [])]
  a.qualifiers = [str(q) for q in d.get(quals_key, [])]
  return a


def _drift_report(items: list[tuple[str, str, str, str, str]]) -> str:
  lines = [
    f"{len(items)} override(s) no longer match the entry they were made "
    f"against; refusing to replay ANY of them.",
    "Applying a drifted correction would attach a human-reviewed parse "
    "(resp=\"#human-review\") to a different apparatus entry.",
  ]
  for key, want, got, was, now in items:
    lines.append(f"  {key}: bound to {want}, entry is now {got}")
    if was:
      lines.append(f"      made against: {was}")
    lines.append(f"      now reads:     {now}")
  lines.append(
    "Re-run 'diorthosis review' on this build, re-check these entries and "
    "re-export the corrections.")
  return "\n".join(lines)


def apply_overrides(doc: Document, overrides: dict[str, dict]) -> dict:
  """Apply overrides in place, ALL or NOTHING.

  Two passes on purpose: the first only locates and verifies, so a
  drifted file leaves the document untouched instead of half-corrected.
  A content mismatch raises with an itemised report — never a silent
  skip, never a fuzzy re-match onto some other entry that looks close.

  Returns honest counters. Note the deliberate severity split: a key
  matching NO entry loses a correction and is reported in ``unmatched``
  for the caller to surface, while a key matching an entry whose content
  drifted would FABRICATE one, and refuses the build.
  """
  stats = {"applied": 0, "verbatim": 0, "unmatched": []}
  remaining = dict(overrides)
  plan: list[tuple[object, dict]] = []
  drift: list[tuple[str, str, str, str, str]] = []
  for page in doc.pages:
    for key, e in entry_keys(page):
      ov = remaining.pop(key, None)
      if ov is None:
        continue
      want = ov.get("source_sha")
      got = source_digest(e)
      if not isinstance(want, str) or not want:
        drift.append((key, "nothing (no source_sha)", got,
                      _clip(str(ov.get("source_excerpt", ""))),
                      source_excerpt(e)))
        continue
      if want != got:
        drift.append((key, want, got,
                      _clip(str(ov.get("source_excerpt", ""))),
                      source_excerpt(e)))
        continue
      plan.append((e, ov))
  if drift:
    raise ValueError(_drift_report(drift))

  for e, ov in plan:
    if ov["action"] == "verbatim":
      e.override_action = "verbatim"
      stats["verbatim"] += 1
      continue
    e.override_action = "parse"
    e.parsed_override = ParsedEntry(
      lemma=ov["lemma"],
      lemma_attribution=_attribution(
        ov, "lemma_wits", "lemma_editors", "lemma_qualifiers"),
      readings=[
        Reading(text=str(r.get("text", "")),
                attribution=_attribution(
                  r, "wits", "editors", "qualifiers"))
        for r in ov.get("readings", [])
      ],
      comments=[str(c) for c in ov.get("comments", [])],
    )
    stats["applied"] += 1
  stats["unmatched"] = sorted(remaining)
  return stats
