"""Focused tests for the real-PDF checker's lemma-local contamination metric
and for the examined denominator a PASS is allowed to rest on."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "golden"))

pytest.importorskip("lxml", reason="the golden harness needs lxml")
from real_check import (  # noqa: E402
  exact_in,
  examination_floor,
  lemma_window,
  unproven,
)


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


def test_a_limit_examined_on_nothing_cannot_license_a_pass() -> None:
  # the real balex invocation: the convention gate refuses every band, so
  # zero production candidates reach the false-structure arbiter
  reasons = unproven(555, {"contamination": 518, "false-structure": 0})

  assert len(reasons) == 1
  assert "false-structure examined 0" in reasons[0]


def test_examination_at_the_floor_licenses_a_pass() -> None:
  floor = examination_floor(770)

  assert unproven(770, {"contamination": floor, "structure": floor}) == []
  assert len(unproven(770, {"contamination": floor - 1,
                            "structure": floor})) == 1


def test_certified_matthew_denominators_stay_above_the_floor() -> None:
  assert unproven(770, {"contamination": 488, "false-structure": 767}) == []


def test_an_empty_ground_truth_proves_nothing() -> None:
  assert examination_floor(0) == 1
  assert len(unproven(0, {"contamination": 0})) == 1
