"""The CLI contract, end to end — the net wave A's defects walked through.

Every defect wave A fixed coexisted with a fully green suite, because nothing
tested the tool the way a stranger uses it: as a process, with an exit code, a
console report and a pair of files on disk. This module tests exactly that.

What it pins down:

- each subcommand's happy path on a synthetic edition built in-process
  (``conftest.write_pdf``: no reportlab, no network, no edition content);
- the four documented exit codes, each provoked deliberately;
- ``--ignore-self-check`` demoting a refusal to a warning, without changing
  what was written or hiding the findings;
- the ONE coverage report (SPEC I11): the console line, the md-ce meta and
  every page line are the same production, and the meta is the sum of the
  pages — the drift wave A closed;
- ``build`` refusing a degenerate result — the README's own one-liner used to
  exit 0 having produced no text at all;
- the band-level marker gate refusing a numbered PROSE band instead of
  emitting it as ``<app>/<lem>/<rdg>`` — the fabrication wave A killed;
- the CLI surface itself, frozen, so a flag cannot quietly appear or vanish.

KNOWN DEFECTS AT HEAD — these tests are RED on purpose and are the
deliverable, not an accident (see the report accompanying this change):

- ``test_output_dir_that_is_an_existing_file_is_a_user_error`` — ``-o`` aimed
  at an existing file exits 3 ("this is a diorthosis defect… please report
  it") for what is plainly a user input error.

Nothing here is fixed in ``src/``: a test that exposes a defect reports it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import REPO_ROOT, assert_no_traceback, write_pdf

import diorthosis
from diorthosis.cli import EXIT_INPUT, EXIT_INTERNAL, EXIT_OK, EXIT_REFUSED, _build_parser
from diorthosis.md import MD_CE_VERSION

# SPEC.md's `report` production, verbatim. The console line, the md-ce meta
# field and every page comment must all match it.
REPORT = (
  r"(?P<entries>\d+) entries — (?P<parsed>\d+) parsed, (?P<refused>\d+) refused, "
  r"(?P<unparsed>\d+) unparsed; (?P<anchored>\d+) anchored "
  r"\((?P<attached>\d+) attached, (?P<end_only>\d+) end-only\), "
  r"(?P<unanchored>\d+) unanchored"
)
CONSOLE_COVERAGE = re.compile(r"^coverage: " + REPORT + r"$", re.M)
META_COVERAGE = re.compile(r" · coverage: " + REPORT + r" · refusals: ")
PAGE_COVERAGE = re.compile(r"^<!-- md-ce page: " + REPORT + r" -->$", re.M)


def counts(match: re.Match[str]) -> dict[str, int]:
  return {k: int(v) for k, v in match.groupdict().items()}


# --------------------------------------------------------------------------
# what is under test
# --------------------------------------------------------------------------


def test_the_suite_tests_the_working_tree() -> None:
  """A stale editable install shadowed the package during wave A's own
  verification round. The suite must be able to say which code answered."""
  answered = Path(diorthosis.__file__).resolve()
  expected = (REPO_ROOT / "src" / "diorthosis" / "__init__.py").resolve()
  assert answered == expected, (
    f"tests are measuring {answered}, not this checkout's {expected}; "
    "uninstall the shadowing copy (pip uninstall diorthosis) before trusting "
    "any number this suite prints"
  )


# --------------------------------------------------------------------------
# happy paths, one per subcommand
# --------------------------------------------------------------------------


def test_build_happy_path(built_edition) -> None:
  result, out = built_edition
  stem = "ed"
  for suffix in (".tei.xml", ".md", ".witnesses.json"):
    path = out / f"{stem}{suffix}"
    assert path.is_file(), result.report()
    assert f"wrote {path}" in result.stdout, result.report()

  tei = (out / f"{stem}.tei.xml").read_text(encoding="utf-8")
  md = (out / f"{stem}.md").read_text(encoding="utf-8")
  assert tei.count("<app ") == 7, result.report()
  assert "⟦11:1⟧" in md and "⟦12:1⟧" in md, "markers are page-scoped (I3)"
  assert "### text " in md and "### apparatus " in md
  assert_no_traceback(result)


def test_validate_happy_path(cli, built_edition) -> None:
  _, out = built_edition
  result = cli("validate", out / "ed.md")
  assert result.returncode == EXIT_OK, result.report()
  assert result.stdout.strip() == f"OK: md-ce/{MD_CE_VERSION} invariants hold"


def test_roundtrip_happy_path(cli, built_edition) -> None:
  _, out = built_edition
  result = cli("roundtrip", out / "ed.md", out / "ed.tei.xml")
  assert result.returncode == EXIT_OK, result.report()
  assert "OK: md-ce and TEI carry the same content" in result.stdout


def test_inspect_happy_path(cli, synthetic_edition) -> None:
  result = cli("inspect", synthetic_edition, "--page", "1")
  assert result.returncode == EXIT_OK, result.report()
  assert result.stdout.startswith("# "), result.report()
  assert "<!-- md-ce/" in result.stdout
  assert CONSOLE_COVERAGE.search(result.stderr), result.report()


def test_inspect_emits_a_valid_md_ce_document(cli, synthetic_edition, tmp_path) -> None:
  """``inspect`` prints md-ce to stdout; what it prints must be md-ce."""
  result = cli("inspect", synthetic_edition, "--page", "1")
  page = tmp_path / "inspected.md"
  page.write_text(result.stdout, encoding="utf-8")
  checked = cli("validate", page)
  assert checked.returncode == EXIT_OK, checked.report()


def test_review_happy_path(cli, synthetic_edition, tmp_path) -> None:
  pytest.importorskip("pypdfium2", reason="review needs diorthosis[review]")
  out = tmp_path / "review"
  result = cli("review", synthetic_edition, "--pages", "1-2",
               "--text-lang", "la", "-o", out)
  assert result.returncode == EXIT_OK, result.report()
  assert (out / "index.html").is_file()
  assert re.search(
    r"^review: \d+ entries — \d+ parsed, \d+ refused, \d+ unanchored, "
    r"\d+ reviewed; \d+ snippets$", result.stdout, re.M), result.report()


def test_review_without_the_optional_extra_is_a_user_error(cli, synthetic_edition,
                                                           tmp_path) -> None:
  """Documented behaviour when ``pypdfium2`` is absent: exit 2 naming the
  extra to install. Only assertable when the extra really is absent."""
  try:
    import pypdfium2  # noqa: F401
  except ImportError:
    result = cli("review", synthetic_edition, "-o", tmp_path / "r")
    assert result.returncode == EXIT_INPUT, result.report()
    assert "pip install 'diorthosis[review]'" in result.stderr
  else:
    pytest.skip("pypdfium2 is installed; the missing-extra path is unreachable")


ALTO = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout><Page><PrintSpace>
<TextBlock ID="b1"><TextLine><String CONTENT="Bellum" WC="0.98"/><SP/>
<String CONTENT="ciuile" WC="0.97"/></TextLine></TextBlock>
</PrintSpace></Page></Layout></alto>
"""
HOCR = """<html><body>
<div class='ocr_page' id='page_1' title='bbox 0 0 100 100; lpageno 11'>
 <span class='ocr_line' title='bbox 1 1 99 9'>
  <span class='ocrx_word' title='bbox 1 1 40 9; x_wconf 96'>Bellum</span>
  <span class='ocrx_word' title='bbox 45 1 99 9; x_wconf 94'>ciuile</span>
 </span></div></body></html>
"""
PAGE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">
 <Page imageWidth="100" imageHeight="100">
  <TextRegion id="r1"><TextLine id="l1"><TextEquiv conf="0.95">
   <Unicode>Bellum ciuile</Unicode></TextEquiv></TextLine></TextRegion>
 </Page></PcGts>
"""


@pytest.mark.parametrize(("flag", "name", "body"), [
  ("--alto", "p1.xml", ALTO),
  ("--hocr", "p1.html", HOCR),
  ("--page-xml", "p1.xml", PAGE_XML),
])
def test_ocr_ingest_happy_path(cli, tmp_path, flag: str, name: str, body: str) -> None:
  """Every OCR path builds — and marks its blocks generative, forever."""
  src = tmp_path / name
  src.write_text(body, encoding="utf-8")
  out = tmp_path / "out"
  result = cli("build", flag, src, "-o", out)
  assert result.returncode == EXIT_OK, result.report()
  md = next(out.glob("*.md")).read_text(encoding="utf-8")
  assert "generative=true" in md, result.report()
  assert "generative-blocks: 1" in md, result.report()
  assert "OCR-generated blocks" in result.stderr, result.report()


# --------------------------------------------------------------------------
# the four exit codes, provoked deliberately
# --------------------------------------------------------------------------


def test_exit_codes_are_documented_in_help(cli) -> None:
  result = cli("--help")
  assert result.returncode == EXIT_OK
  for line in ("0  success",
               "1  refused",
               "2  user-actionable input error",
               "3  internal fault"):
    assert line in result.stdout, result.report()


def test_exit_0_is_success(built_edition) -> None:
  result, _ = built_edition
  assert result.returncode == EXIT_OK == 0


@pytest.mark.parametrize("case", ["degenerate-build", "invalid-md-ce",
                                  "roundtrip-mismatch", "marker-delimiter"])
def test_exit_1_is_a_refusal(cli, synthetic_edition, built_edition, tmp_path,
                             case: str) -> None:
  """Exit 1 = the command ran and diorthosis does not certify its result."""
  _, built = built_edition
  if case == "degenerate-build":
    # the README's own one-liner: a Latin edition without --text-lang la
    result = cli("build", synthetic_edition, "--pages", "1-2", "-o", tmp_path / "o")
    assert "self-check FAILED" in result.stderr, result.report()
  elif case == "invalid-md-ce":
    bad = tmp_path / "bad.md"
    bad.write_text("# not md-ce\n\nnothing here\n", encoding="utf-8")
    result = cli("validate", bad)
    assert "violation(s)" in result.stderr, result.report()
  elif case == "roundtrip-mismatch":
    other = tmp_path / "other"
    cli("build", "--alto", _write(tmp_path / "p.xml", ALTO), "-o", other)
    result = cli("roundtrip", built / "ed.md", next(other.glob("*.tei.xml")))
    assert "violation(s)" in result.stderr, result.report()
  else:  # marker-delimiter: SPEC I4, an ambiguous file is never emitted
    src = _write(tmp_path / "delim.xml",
                 ALTO.replace('CONTENT="ciuile"', 'CONTENT="⟦ciuile⟧"'))
    result = cli("build", "--alto", src, "-o", tmp_path / "o2")
    assert "refusing to emit an ambiguous md-ce file" in result.stderr, result.report()
  assert result.returncode == EXIT_REFUSED, result.report()
  assert_no_traceback(result)


def _write(path: Path, body: str) -> Path:
  path.write_text(body, encoding="utf-8")
  return path


@pytest.mark.parametrize(("args", "expected"), [
  (("build", "MISSING.pdf", "-o", "OUT"), "file not found"),
  (("build", "EDITION", "--pages", "", "-o", "OUT"), "--pages given but empty"),
  (("build", "EDITION", "--pages", "5-1", "-o", "OUT"), "is reversed"),
  (("build", "EDITION", "--pages", "chapitre", "-o", "OUT"),
   "is not a 0-based page number"),
  (("build", "EDITION", "--pages", "900", "--text-lang", "la", "-o", "OUT"),
   "the requested pages do not exist"),
  (("build", "-o", "OUT"), "exactly one source"),
  (("build", "EDITION", "--alto", "MISSING.pdf", "-o", "OUT"), "exactly one source"),
  (("build", "--alto", "MISSING.pdf", "--pages", "1", "-o", "OUT"),
   "--pages selects pages of a PDF"),
  (("build", "--alto", "MISSING.pdf", "--conspectus-page", "0", "-o", "OUT"),
   "--conspectus-page points into a PDF"),
  (("build", "EDITION", "--text-lang", "syr", "-o", "OUT"), "invalid choice"),
  (("validate", "MISSING.md"), "file not found"),
  (("roundtrip", "MISSING.md", "MISSING.xml"), "file not found"),
  (("inspect", "MISSING.pdf", "--page", "0"), "file not found"),
])
def test_exit_2_is_a_user_actionable_input_error(cli, synthetic_edition, tmp_path,
                                                 args, expected: str) -> None:
  resolved = [str(synthetic_edition) if a == "EDITION"
              else str(tmp_path / "out") if a == "OUT" else a for a in args]
  result = cli(*resolved)
  assert result.returncode == EXIT_INPUT, result.report()
  assert expected in result.output, result.report()
  assert_no_traceback(result)


def test_exit_3_is_an_internal_fault(monkeypatch, synthetic_edition, tmp_path,
                                     capsys) -> None:
  """The last-resort handler: an unexpected exception becomes exit 3 with a
  named defect, never a traceback on a scholar's terminal."""
  from diorthosis import cli as cli_mod

  def boom(*_args, **_kwargs):
    raise RuntimeError("a defect nobody anticipated")

  monkeypatch.setattr(cli_mod, "to_tei", boom)
  monkeypatch.setattr("sys.argv", [
    "diorthosis", "build", str(synthetic_edition), "--pages", "1-2",
    "--text-lang", "la", "-o", str(tmp_path / "out")])
  code = cli_mod.run()
  captured = capsys.readouterr()
  assert code == EXIT_INTERNAL == 3
  assert "internal error: RuntimeError: a defect nobody anticipated" in captured.err
  assert "this is a diorthosis defect, not an input problem" in captured.err
  assert "Traceback (most recent call last)" not in captured.err


def test_output_dir_that_is_an_existing_file_is_a_user_error(cli, synthetic_edition,
                                                             tmp_path) -> None:
  """KNOWN DEFECT (red at HEAD). ``-o`` pointing at an existing FILE raises
  ``FileExistsError`` out of ``outdir.mkdir()``; ``run()``'s generic handler
  turns it into exit 3 and tells the user to file a bug report. Choosing a bad
  output path is the user's mistake, and the contract reserves 3 for
  diorthosis's own.

  Reproduce::

      diorthosis build EDITION --pages 1-2 --text-lang la -o EDITION
      # internal error: FileExistsError: [Errno 17] File exists: 'EDITION'
      # exit 3
  """
  result = cli("build", synthetic_edition, "--pages", "1-2",
               "--text-lang", "la", "-o", synthetic_edition)
  assert_no_traceback(result)
  assert result.returncode == EXIT_INPUT, result.report()


# --------------------------------------------------------------------------
# --ignore-self-check: a refusal demoted to a warning, and nothing else
# --------------------------------------------------------------------------


def test_ignore_self_check_turns_the_refusal_into_a_warning(
    cli, synthetic_edition, tmp_path) -> None:
  strict = tmp_path / "strict"
  loose = tmp_path / "loose"
  refused = cli("build", synthetic_edition, "--pages", "1-2", "-o", strict)
  accepted = cli("build", synthetic_edition, "--pages", "1-2", "-o", loose,
                 "--ignore-self-check")

  assert refused.returncode == EXIT_REFUSED, refused.report()
  assert accepted.returncode == EXIT_OK, accepted.report()

  # the escape hatch changes the VERDICT, never the artifact
  assert sorted(p.name for p in strict.iterdir()) == \
         sorted(p.name for p in loose.iterdir())
  for name in (p.name for p in strict.iterdir()):
    assert (strict / name).read_bytes() == (loose / name).read_bytes()

  # and it never silences the findings
  assert "self-check FAILED" in accepted.stderr, accepted.report()
  assert "degenerate:" in accepted.stderr, accepted.report()
  assert "--ignore-self-check: exiting 0 with an uncertified artifact" \
         in accepted.stderr, accepted.report()


def test_build_refuses_a_degenerate_result(cli, synthetic_edition, tmp_path) -> None:
  """The README one-liner regression: a build that produced no constituted
  text must not report success — and must name the option that fixes it."""
  result = cli("build", synthetic_edition, "--pages", "1-2", "-o", tmp_path / "o")
  assert result.returncode == EXIT_REFUSED, result.report()
  assert "no constituted-text block" in result.stderr, result.report()
  assert "--text-lang la" in result.stderr, (
    "an honest failure has to be actionable: name the flag that avoids it"
    + result.report())


def test_build_refuses_a_page_carrying_no_text(cli, tmp_path) -> None:
  """A scanned page, as a text extractor sees it: no text operator at all."""
  scan = write_pdf(tmp_path / "scan.pdf", [[]])
  result = cli("build", scan, "--text-lang", "la", "-o", tmp_path / "o")
  assert result.returncode == EXIT_REFUSED, result.report()
  assert "no decodable text at all" in result.stderr, result.report()
  assert "--alto/--hocr/--page-xml" in result.stderr, (
    "diorthosis never calls an OCR engine; it must say what to do instead"
    + result.report())


# --------------------------------------------------------------------------
# the ONE coverage report (SPEC I11)
# --------------------------------------------------------------------------


def test_coverage_line_shape(built_edition) -> None:
  result, _ = built_edition
  match = CONSOLE_COVERAGE.search(result.stdout)
  assert match, result.report()
  assert re.search(r"^refusals: (none|\d+× .+)$", result.stdout, re.M), result.report()
  c = counts(match)
  assert c["parsed"] + c["refused"] + c["unparsed"] == c["entries"]
  assert c["attached"] + c["end_only"] + c["unanchored"] == c["entries"]
  assert c["attached"] + c["end_only"] == c["anchored"]


def test_console_meta_and_page_reports_are_one_report(built_edition) -> None:
  """Before 0.3 one invocation announced two scores. Three renderings now, one
  production: the console line, the md-ce meta, and every page comment."""
  result, out = built_edition
  md = (out / "ed.md").read_text(encoding="utf-8")

  console = counts(CONSOLE_COVERAGE.search(result.stdout))
  meta_match = META_COVERAGE.search(md)
  assert meta_match, md[:400]
  meta = counts(meta_match)
  assert console == meta, "the console and the md-ce meta state different scores"

  pages = [counts(m) for m in PAGE_COVERAGE.finditer(md)]
  assert len(pages) == md.count("\n## page "), "every page carries its report"
  for key in meta:
    assert sum(p[key] for p in pages) == meta[key], (
      f"meta {key}={meta[key]} is not the sum of the page reports")


def test_refusal_tally_sums_to_refused(cli, unattributed_edition, tmp_path) -> None:
  result = cli("build", unattributed_edition, "--pages", "1",
               "--text-lang", "la", "-o", tmp_path / "o")
  coverage = counts(CONSOLE_COVERAGE.search(result.stdout))
  tally = re.search(r"^refusals: (.+)$", result.stdout, re.M)
  assert tally, result.report()
  if coverage["refused"] == 0:
    assert tally.group(1) == "none"
  else:
    items = re.findall(r"(\d+)× ", tally.group(1))
    assert sum(int(n) for n in items) == coverage["refused"], result.report()
    for reason in re.split(r"; ", tally.group(1)):
      assert ";" not in reason and "·" not in reason, (
        "a refusal reason may not carry the meta line's field separators")


def test_anchored_is_split_and_never_over_claims(built_edition) -> None:
  """"100 % anchored" once counted the END anchor of a double-end-point
  attachment alone. `attached` must mean @from AND @to in the TEI."""
  result, out = built_edition
  c = counts(CONSOLE_COVERAGE.search(result.stdout))
  tei = (out / "ed.tei.xml").read_text(encoding="utf-8")
  both_ends = len(re.findall(r"<app\b[^>]*\bfrom=[^>]*\bto=", tei))
  assert both_ends == c["attached"], result.report()


# --------------------------------------------------------------------------
# the fabrication wave A killed
# --------------------------------------------------------------------------


def test_numbered_prose_band_is_refused_not_emitted_as_variants(
    cli, numbered_prose_edition, tmp_path) -> None:
  """An English editorial footnote printed in the apparatus register carries
  the same numbering and the same ``:`` as the convention — and never a
  siglum. Shape alone cannot tell them apart; the printed sigla can."""
  out = tmp_path / "o"
  result = cli("build", numbered_prose_edition, "--pages", "1",
               "--text-lang", "la", "-o", out)
  assert_no_traceback(result)
  tei = (out / "footnotes.tei.xml").read_text(encoding="utf-8")
  md = (out / "footnotes.md").read_text(encoding="utf-8")

  assert "<app " not in tei, (
    "numbered editorial prose was emitted as an apparatus variant" + result.report())
  assert "<rdg" not in tei and "<lem" not in tei, result.report()
  # refused, counted, and named
  c = counts(CONSOLE_COVERAGE.search(result.stdout))
  assert c["refused"] == c["entries"] > 0, result.report()
  assert "marker convention gate refused band" in result.stdout, result.report()
  # and the prose is preserved verbatim, never dropped
  assert "here renders the phrase discussed at length above." in md, result.report()


def test_a_band_naming_no_authority_is_refused(cli, unattributed_edition,
                                               tmp_path) -> None:
  """The gate's last clause: an apparatus records WHO reads WHAT. A band whose
  readings name no witness, editor or version is refused whole."""
  out = tmp_path / "o"
  result = cli("build", unattributed_edition, "--pages", "1",
               "--text-lang", "la", "-o", out)
  tei = (out / "unattributed.tei.xml").read_text(encoding="utf-8")
  assert "<app " not in tei, result.report()
  assert "no witness, editor or source is named" in result.stdout, result.report()


def test_an_attributed_band_is_accepted(built_edition) -> None:
  """The gate is a floor, not a wall: the same shape WITH sigla parses."""
  result, out = built_edition
  tei = (out / "ed.tei.xml").read_text(encoding="utf-8")
  assert tei.count("<app ") == 7, result.report()
  assert 'wit="' in tei or "wit='" in tei, result.report()
  assert counts(CONSOLE_COVERAGE.search(result.stdout))["refused"] == 0


# --------------------------------------------------------------------------
# determinism and a frozen surface
# --------------------------------------------------------------------------


def test_build_is_byte_deterministic_across_processes(cli, synthetic_edition,
                                                      tmp_path) -> None:
  """SPEC I12, at CLI level: two separate processes, deliberately different
  hash seeds, byte-identical outputs."""
  first, second = tmp_path / "a", tmp_path / "b"
  args = (synthetic_edition, "--pages", "1-2", "--text-lang", "la")
  one = cli("build", *args, "-o", first, hashseed="0")
  two = cli("build", *args, "-o", second, hashseed="12345")
  assert one.returncode == two.returncode == EXIT_OK
  names = sorted(p.name for p in first.iterdir())
  assert names == sorted(p.name for p in second.iterdir())
  for name in names:
    assert (first / name).read_bytes() == (second / name).read_bytes(), name
  # the console report too, once the output directory itself is factored out
  assert one.stdout.replace(str(first), "OUT") == two.stdout.replace(str(second), "OUT")


EXPECTED_SURFACE = {
  "build": {"pdf", "--alto", "--hocr", "--page-xml", "--pages", "--out",
            "--title", "--conspectus-page", "--text-lang", "--overrides",
            "--sigla", "--ignore-self-check"},
  "inspect": {"pdf", "--page", "--conspectus-page"},
  "validate": {"file"},
  "roundtrip": {"md", "tei"},
  "review": {"pdf", "--pages", "--out", "--conspectus-page", "--text-lang",
             "--overrides"},
}
"""The CLI surface, frozen. Changing it is fine — changing it by accident is
not, and a published tool's flags are a contract with its users."""


def cli_surface() -> dict[str, set[str]]:
  import argparse

  parser = _build_parser()
  [subparsers] = [a for a in parser._actions
                  if isinstance(a, argparse._SubParsersAction)]
  surface: dict[str, set[str]] = {}
  for name, sub in subparsers.choices.items():
    options: set[str] = set()
    for action in sub._actions:
      if action.dest in ("help", argparse.SUPPRESS):
        continue
      options.add(action.option_strings[-1] if action.option_strings
                  else action.dest)
    surface[name] = options
  return surface


def test_cli_surface_is_frozen() -> None:
  assert cli_surface() == EXPECTED_SURFACE, (
    "the CLI surface changed; update EXPECTED_SURFACE deliberately, and the "
    "documentation with it"
  )


def test_every_subcommand_has_a_help_page(cli) -> None:
  for name in EXPECTED_SURFACE:
    result = cli(name, "--help")
    assert result.returncode == EXIT_OK, result.report()
    assert result.stdout.startswith(f"usage: diorthosis {name}"), result.report()
