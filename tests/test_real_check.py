"""Focused tests for the real-PDF checker's lemma-local contamination metric."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "golden"))

from real_check import exact_in, lemma_window  # noqa: E402


def test_neighbouring_vocabulary_outside_lemma_window_is_not_contamination() -> None:
  rejected = "βληθη εισ γεενναν"
  text = rejected + " " + ("γειτων " * 30) + "ιδιον λημμα"

  located = lemma_window(text, "ιδιον λημμα", radius=150)

  assert located is not None
  local, _, _ = located
  assert not exact_in(rejected, local)


def test_rejected_reading_inside_lemma_window_is_contamination() -> None:
  text = "πριν ιδιον λημμα μετα βληθη εισ γεενναν"

  located = lemma_window(text, "ιδιον λημμα", radius=150)

  assert located is not None
  local, _, _ = located
  assert exact_in("βληθη εισ γεενναν", local)
