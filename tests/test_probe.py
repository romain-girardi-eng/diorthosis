"""First-run probe: page clustering and the suggested build line."""

from diorthosis.probe import (
  ProbeReport,
  cluster_edition,
  format_ranges,
  sample_indices,
)


def test_sample_covers_head_mid_and_tail() -> None:
  got = sample_indices(200, 20)
  assert got[0] == 0
  assert got[-1] == 199
  assert len(got) <= 20
  assert any(40 <= p <= 160 for p in got)


def test_small_pdf_is_fully_sampled() -> None:
  assert sample_indices(10, 24) == list(range(10))


def test_format_ranges() -> None:
  assert format_ranges([82, 83, 84, 90, 91]) == "82-84,90-91"
  assert format_ranges([7]) == "7"
  assert format_ranges([]) == ""


def test_cluster_fills_a_small_gap_only() -> None:
  sampled = [80, 90, 100, 140]
  edition = {80, 90, 100}
  assert cluster_edition(sampled, edition, max_gap=12) == list(range(80, 101))
  assert 140 not in cluster_edition(sampled, edition, max_gap=12)


def test_suggested_command_carries_the_three_flags() -> None:
  report = ProbeReport(
    pdf="balex.pdf",
    page_count=481,
    sampled=[82, 90, 171],
    edition_pages=list(range(82, 172)),
    pages_spec="82-171",
    conspectus_page=54,
    text_lang="la",
    two_column_pages=[],
  )
  assert report.command == (
    "diorthosis build balex.pdf --pages 82-171 "
    "--conspectus-page 54 --text-lang la -o out/"
  )
