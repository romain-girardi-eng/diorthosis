"""Typed, fail-closed print/TEI divergence records shared by checkers.

Free-text allowlists turn evidence into decoration: a matching string can
silence a different future defect.  This loader makes the evidence schema
executable and leaves matching observed error kinds to the corpus checker.
"""

from __future__ import annotations

import json
from pathlib import Path

_FIELDS = frozenset({
  "book", "locus", "error_kinds", "print_form", "tei_form",
  "band_evidence", "reason",
})


def load_divergences(path: Path, book: str | None = None) -> tuple[dict, list[str]]:
  """Load records for ``book`` and return schema errors separately.

  A partial-book run must not call exceptions from other books stale, but a
  malformed record anywhere is still fatal: an evidence file is one unit.
  """
  try:
    raw = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError) as exc:
    return {}, [f"cannot load typed divergences {path}: {exc}"]
  if not isinstance(raw, dict):
    return {}, ["typed divergence file must contain a JSON object"]
  errors: list[str] = []
  selected: dict = {}
  for key, record in raw.items():
    if not isinstance(key, str) or not isinstance(record, dict):
      errors.append(f"{key!r}: key must be text and value must be a record")
      continue
    missing = sorted(_FIELDS - record.keys())
    if missing:
      errors.append(f"{key}: missing fields {missing}")
      continue
    rec_book = record["book"]
    if not isinstance(rec_book, str) or not key.startswith(f"{rec_book}:"):
      errors.append(f"{key}: key is not scoped to record book {rec_book!r}")
    if not isinstance(record["locus"], str) or not record["locus"]:
      errors.append(f"{key}: locus must be nonempty text")
    kinds = record["error_kinds"]
    if not isinstance(kinds, list) or not kinds or not all(
        isinstance(kind, str) and kind for kind in kinds):
      errors.append(f"{key}: error_kinds must be a nonempty string list")
    elif len(kinds) != len(set(kinds)):
      errors.append(f"{key}: error_kinds contains duplicates")
    for field in ("print_form", "tei_form", "band_evidence", "reason"):
      if not isinstance(record[field], str):
        errors.append(f"{key}: {field} must be text")
    if record.get("unproven") is not None and record.get("unproven") is not True:
      errors.append(f"{key}: unproven, when present, must be true")
    if book is None or rec_book == book:
      selected[key] = record
  return selected, errors
