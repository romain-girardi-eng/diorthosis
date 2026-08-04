"""Per-edition human-review overrides — the correction loop.

A grammar gets an edition to 90–99 %; the last stretch is human review.
Overrides make that review REPLAYABLE: a JSON file per edition records
each correction against a stable entry key, `diorthosis build
--overrides` applies it on every rebuild, and the TEI marks every
overridden entry with ``resp="#human-review"`` — a human correction is
provenance, never silently merged into what the grammar read.

File format (JSON object, one key per corrected entry)::

    {
      "p300-e6": {
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
      "p301-e2": {"action": "verbatim",
                  "note": "prose note, not a variant entry"}
    }

The key is ``p{page.index}-e{k}`` where ``page.index`` is the 0-based
file page and ``k`` counts apparatus entries across the WHOLE page in
document order (builds are deterministic, so keys are stable).

Actions:

- ``parse``   — replace the grammar's structured reading of the entry;
- ``verbatim`` — force the honest refusal: the entry is kept as a
  verbatim note (use it when the grammar mis-parses narrative).

The verbatim raw text of the entry is NEVER touched by an override.
"""

from __future__ import annotations

import json
from pathlib import Path

from .grammar import Attribution, ParsedEntry, Reading
from .model import Document, Layer


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


def load_overrides(path: str | Path) -> dict[str, dict]:
  data = json.loads(Path(path).read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError("overrides file must be a JSON object keyed by entry id")
  for key, ov in data.items():
    if not isinstance(ov, dict) or ov.get("action") not in ("parse", "verbatim"):
      raise ValueError(
        f"override {key!r}: 'action' must be 'parse' or 'verbatim'")
    if ov["action"] == "parse" and not isinstance(ov.get("lemma"), str):
      raise ValueError(f"override {key!r}: action 'parse' needs a 'lemma'")
  return data


def _attribution(d: dict, wits_key: str, eds_key: str,
                 quals_key: str) -> Attribution:
  a = Attribution()
  a.witnesses = [str(w) for w in d.get(wits_key, [])]
  a.editors = [str(e) for e in d.get(eds_key, [])]
  a.qualifiers = [str(q) for q in d.get(quals_key, [])]
  return a


def apply_overrides(doc: Document, overrides: dict[str, dict]) -> dict:
  """Apply overrides in place. Returns honest counters, including the
  keys that matched nothing (a stale overrides file must be VISIBLE)."""
  stats = {"applied": 0, "verbatim": 0, "unmatched": []}
  remaining = dict(overrides)
  for page in doc.pages:
    for key, e in entry_keys(page):
      ov = remaining.pop(key, None)
      if ov is None:
        continue
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
