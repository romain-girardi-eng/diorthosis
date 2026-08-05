"""The whole-NT oracle's outcome buckets must partition the source manifest.

A fail-closed source-complete oracle earns nothing from printing per-book
numbers that do not add up: an app counted twice hides an app counted never.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "golden"))

pytest.importorskip("lxml", reason="the golden harness needs lxml")
from sblgnt_nt_driver import identity_failures  # noqa: E402

MANIFEST = {
  "B01": {"source_apps": 826, "chapters": list(range(1, 29))},
  "B18": {"source_apps": 17, "chapters": [1]},
}


def test_every_book_in_exactly_one_bucket_reconciles() -> None:
  assigned = {"B01": {"compared": 822, "uncovered": 4},
              "B18": {"refused": 17}}

  assert identity_failures(assigned, MANIFEST) == []


def test_refused_book_also_counted_as_uncovered_is_caught() -> None:
  # the shipped defect: an empty build covers no locus, so the checker
  # reported the whole book as uncovered AND the driver as refused —
  # 6,797 + 61 + 121 summed to 6,979 of 6,921 source leaf apps
  assigned = {"B01": {"compared": 822, "uncovered": 4},
              "B18": {"refused": 17, "uncovered": 17}}

  failures = identity_failures(assigned, MANIFEST)

  assert any(failure.startswith("B18:") for failure in failures)
  assert any(failure.startswith("corpus:") for failure in failures)


def test_source_app_landing_in_no_bucket_is_caught() -> None:
  assigned = {"B01": {"compared": 821, "uncovered": 4, "unaccounted": 0},
              "B18": {"refused": 17}}

  failures = identity_failures(assigned, MANIFEST)

  assert any(failure.startswith("B01:") for failure in failures)


def test_naming_the_residual_apps_restores_the_identity() -> None:
  assigned = {"B01": {"compared": 821, "uncovered": 4, "unaccounted": 1},
              "B18": {"refused": 17}}

  assert identity_failures(assigned, MANIFEST) == []


def test_a_corpus_sum_that_balances_by_coincidence_is_not_a_pass() -> None:
  # one book over-counts exactly what another loses: the corpus total is
  # intact and every per-book row is wrong
  assigned = {"B01": {"compared": 823, "uncovered": 4},
              "B18": {"refused": 16}}

  failures = identity_failures(assigned, MANIFEST)

  assert [failure.split(":")[0] for failure in failures] == ["B01", "B18"]


def test_a_book_with_no_bucket_at_all_is_caught() -> None:
  failures = identity_failures({"B01": {"compared": 826}}, MANIFEST)

  assert any(failure.startswith("B18:") for failure in failures)
