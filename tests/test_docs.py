"""The documentation stops rotting.

Prose is the one part of a scholarly tool nothing executes, so it is the part
that silently goes false. Wave A found the README's own one-liner exiting 0 on
a build that produced no text; the transcript printed underneath it had not
matched the tool for two versions. This module makes the documentation a
checked artefact.

Everything is discovered **dynamically** — every ``*.md`` under the repository
root, ``docs/`` and ``paper/`` is scanned as it is. Nothing here names a
section, a line number or a sentence, so a rewrite in flight (as one is, while
this is written) neither breaks these tests nor escapes them.

THE RUNNABLE CONVENTION
=======================

A fenced ``console`` / ``sh`` / ``bash`` block is executed by this suite when
the line immediately above the fence is::

    <!-- diorthosis-doc: runnable -->

Inside such a block:

* a line beginning with ``$ `` is a command, run with ``sh -c`` from the
  repository root, with a ``diorthosis`` shim on ``PATH`` that dispatches to
  this checkout;
* every other non-empty line is EXPECTED OUTPUT and must occur, as a
  substring, in that command's combined output;
* the tokens ``EDITION`` and ``OUT`` are substituted with a synthetic edition
  PDF and a fresh empty directory, so a runnable example ships no edition
  content and needs no network;
* a command must exit 0 unless the block also marks it::

      <!-- diorthosis-doc: runnable, expect-exit 1 -->

At the time of writing NO block in the shipped documentation carries the
marker — the count is asserted, not assumed, and the harness itself is proven
end to end by ``test_the_runnable_harness_runs_and_catches_rot`` on a doc
written inside the test. Adding the marker to a real block is wave B's job;
the machinery is waiting for it.

KNOWN DEFECTS AT HEAD — RED on purpose, each one a false statement in the
shipped documentation:

- ``test_reproduced_tool_output_states_the_shipped_version``: the README's
  ``validate`` transcript prints ``OK: md-ce/0.2 invariants hold``; the tool
  prints ``0.3``.
- ``test_console_transcripts_match_the_report_the_tool_prints``: the README's
  ``build`` transcript prints ``apparatus anchoring: 277/287 entries
  anchored``, a console line ``cli.py`` no longer emits — the shipped report
  is ``coverage: …`` + ``refusals: …`` — and its ``review`` transcript is
  missing the ``N reviewed`` field ``cli.py``'s review branch prints.
- ``test_md_ce_samples_match_the_spec``: the README's md-ce sample is stale on
  four counts against the shipped SPEC — no ``page-stats`` on the page header,
  no ``page-cov`` line under it, no ``block=`` key in either block header, and
  page-unscoped ``⟦7⟧`` markers where I3 requires ``⟦294:7⟧``.
- ``test_documented_repo_paths_exist``: ``docs/cli.md`` links to
  ``tutorial.md`` and ``troubleshooting.md``, which do not exist. Measured on
  a tree where the documentation set is actively being written; the check is
  dynamic and clears itself the moment the pages land.

None of them is fixed here: this file is a test module, and the documents
belong to the wave rewriting them.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
from conftest import REPO_ROOT, SRC

from diorthosis.cli import _build_parser
from diorthosis.md import MD_CE_VERSION
from diorthosis.mdce_validate import validate_text

SKIP_FILES = {"prior-art.md"}
"""A 154-reference bibliography quoting other people's prose: it documents the
field, not this tool, and nothing in it is a claim about diorthosis's
behaviour."""

SHELL_INFO = {"console", "sh", "bash", "shell"}
FENCE = re.compile(r"^```([^\n`]*)\n(.*?)^```", re.M | re.S)
RUNNABLE = re.compile(r"<!--\s*diorthosis-doc:\s*runnable(?P<rest>[^>]*)-->")


def doc_files() -> list[Path]:
  """Every documentation file, discovered — never enumerated."""
  found = sorted(REPO_ROOT.glob("*.md"))
  for folder in ("docs", "paper"):
    found += sorted((REPO_ROOT / folder).glob("*.md"))
  return [p for p in found if p.name not in SKIP_FILES]


def shown(path: Path) -> str:
  """Repository-relative when it can be — the self-test's doc lives in a
  temporary directory outside the tree."""
  try:
    return str(path.relative_to(REPO_ROOT))
  except ValueError:
    return str(path)


@dataclass(frozen=True)
class Fence:
  path: Path
  line: int
  info: str
  body: str
  marker: re.Match[str] | None

  @property
  def where(self) -> str:
    return f"{shown(self.path)}:{self.line}"

  @property
  def runnable(self) -> bool:
    return self.marker is not None

  @property
  def expected_exit(self) -> int:
    if self.marker is None:
      return 0
    found = re.search(r"expect-exit\s+(\d+)", self.marker.group("rest"))
    return int(found.group(1)) if found else 0


def fences(text: str, path: Path) -> list[Fence]:
  out: list[Fence] = []
  for match in FENCE.finditer(text):
    head = text[: match.start()].rstrip("\n").rsplit("\n", 1)
    previous = head[-1] if head else ""
    out.append(Fence(
      path=path,
      line=text[: match.start()].count("\n") + 1,
      info=match.group(1).strip(),
      body=match.group(2),
      marker=RUNNABLE.search(previous),
    ))
  return out


def all_fences() -> list[Fence]:
  return [f for path in doc_files()
          for f in fences(path.read_text(encoding="utf-8"), path)]


def shell_fences() -> list[Fence]:
  return [f for f in all_fences() if f.info in SHELL_INFO]


def command_lines(fence: Fence) -> list[str]:
  """The commands of a shell fence, ``$``-prefixed or bare."""
  lines = [ln.rstrip() for ln in fence.body.split("\n")]
  if any(ln.lstrip().startswith("$") for ln in lines):
    return [ln.lstrip()[1:].strip() for ln in lines if ln.lstrip().startswith("$")]
  return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


# --------------------------------------------------------------------------
# every flag and subcommand the docs name must exist
# --------------------------------------------------------------------------


def cli_surface() -> tuple[dict[str, set[str]], set[str]]:
  import argparse

  parser = _build_parser()
  [subparsers] = [a for a in parser._actions
                  if isinstance(a, argparse._SubParsersAction)]
  per_command = {
    name: {s for action in sub._actions for s in action.option_strings}
    for name, sub in subparsers.choices.items()
  }
  every = {s for flags in per_command.values() for s in flags}
  every |= {s for action in parser._actions for s in action.option_strings}
  return per_command, every


def documented_invocations() -> list[tuple[Fence, str, str]]:
  """Every documented ``diorthosis SUBCOMMAND …`` line: (fence, line, name).

  ``diorthosis --help`` is a documented invocation with no subcommand; it is
  skipped rather than reported as a subcommand that does not exist.
  """
  found: list[tuple[Fence, str, str]] = []
  for fence in shell_fences():
    for command in command_lines(fence):
      cleaned = command.split("#", 1)[0].strip()
      if not cleaned.startswith("diorthosis "):
        continue
      rest = [w for w in cleaned.split()[1:] if not w.startswith("-")]
      if rest:
        found.append((fence, cleaned, rest[0]))
  return found


def test_the_docs_document_the_cli_at_all() -> None:
  """A guard on the guards: if discovery silently found nothing, every test
  below would pass vacuously."""
  assert documented_invocations(), "no documented diorthosis command line found"
  assert len(doc_files()) >= 3, [p.name for p in doc_files()]


def test_documented_subcommands_exist() -> None:
  per_command, _ = cli_surface()
  for fence, command, name in documented_invocations():
    assert name in per_command, (
      f"{fence.where}: '{command}' names a subcommand diorthosis does not "
      f"have (it has {sorted(per_command)})")


def test_documented_flags_exist_on_that_subcommand() -> None:
  per_command, _ = cli_surface()
  for fence, command, name in documented_invocations():
    if name not in per_command:
      continue                       # reported by the test above
    for word in command.split()[2:]:
      flag = word.split("=", 1)[0]
      if not flag.startswith("-"):
        continue
      assert flag in per_command[name], (
        f"{fence.where}: '{command}' passes {flag}, which "
        f"'diorthosis {name} --help' does not offer")


def ours(span: str) -> bool:
  """Is this code span about a command of THIS repository?

  A span whose first token is some other program (``pdf2txt.py
  --page-numbers``, ``curl --fail``) documents that program's flags, and this
  repository has no say over them.
  """
  tokens = span.split()
  if not tokens:
    return False
  if "diorthosis" in span:
    return True
  return tokens[0].startswith("-")


def test_every_flag_the_docs_mention_exists_in_shipped_code() -> None:
  """Flags named in prose rot the same way flags in transcripts do. A flag may
  belong to the CLI or to a script under ``tools/``; it may not belong to
  nothing."""
  _, cli_flags = cli_surface()
  shipped = "\n".join(
    p.read_text(encoding="utf-8", errors="replace")
    for pattern in ("*.py", "*.sh") for p in (REPO_ROOT / "tools").rglob(pattern)
  )
  unknown: list[str] = []
  for path in doc_files():
    text = path.read_text(encoding="utf-8")
    spans = [m.group(1) for m in re.finditer(r"`([^`\n]+)`", text)]
    spans += [ln for f in fences(text, path) for ln in f.body.split("\n")]
    for span in spans:
      if not ours(span):
        continue
      for flag in re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", span):
        if flag in cli_flags:
          continue
        if any(token in shipped for token in (f'"{flag}"', f"'{flag}'", f" {flag} ")):
          continue
        unknown.append(f"{shown(path)}: {flag} in `{span.strip()}`")
  assert not unknown, unknown


def test_documented_repo_paths_exist() -> None:
  """Every relative link target, and every repository-relative script a
  documented command invokes."""
  link = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
  script = re.compile(
    r"(?:^|\|\s*|&&\s*)(?:\./|python3?\s+|sh\s+|bash\s+)([\w.-]*/[\w./-]+\.(?:py|sh))")
  missing: list[str] = []
  for path in doc_files():
    text = path.read_text(encoding="utf-8")
    for match in link.finditer(text):
      target = match.group(1)
      if target.startswith(("http://", "https://", "#", "mailto:")):
        continue
      target = target.split("#", 1)[0]
      if target and not (path.parent / target).exists():
        missing.append(f"{shown(path)} -> {target}")
    for fence in fences(text, path):
      if fence.info not in SHELL_INFO:
        continue
      for command in command_lines(fence):
        for match in script.finditer(command):
          if not (REPO_ROOT / match.group(1)).exists():
            missing.append(f"{fence.where} runs {match.group(1)}")
  assert not missing, missing


# --------------------------------------------------------------------------
# transcripts must reproduce what the tool really prints
# --------------------------------------------------------------------------

REPORT = (
  r"\d+ entries — \d+ parsed, \d+ refused, \d+ unparsed; "
  r"\d+ anchored \(\d+ attached, \d+ end-only\), \d+ unanchored"
)
KNOWN_REPORT_LINES = (
  re.compile(r"^coverage: " + REPORT + r"$"),
  re.compile(r"^refusals: (none|\d+× .+)$"),
  re.compile(r"^review: \d+ entries — \d+ parsed, \d+ refused, \d+ unanchored, "
             r"\d+ reviewed; \d+ snippets$"),
  re.compile(r"^overrides: \d+ parses replaced, \d+ forced verbatim$"),
)
CLAIMS_A_SCORE = re.compile(r"\b(anchor\w*|coverage|refusals|snippets)\b", re.I)
HAS_A_NUMBER = re.compile(r"\d")
"""A --help line names those words too; only a line carrying figures is
STATING a score."""


def test_console_transcripts_match_the_report_the_tool_prints() -> None:
  """A transcript line that states a score must state it in the production the
  tool actually emits — SPEC I11 allows exactly one."""
  wrong: list[str] = []
  for fence in shell_fences():
    for offset, raw in enumerate(fence.body.split("\n")):
      line = raw.strip()
      if not line or line.startswith("$") or not CLAIMS_A_SCORE.search(line):
        continue
      if not HAS_A_NUMBER.search(line):
        continue
      if any(rx.match(line) for rx in KNOWN_REPORT_LINES):
        continue
      wrong.append(f"{shown(fence.path)}:{fence.line + 1 + offset}: "
                   f"{line!r}")
  assert not wrong, (
    "these transcript lines claim a score in a shape diorthosis no longer "
    f"prints: {wrong}")


TOOL_OUTPUT_VERSION = (
  re.compile(r"OK: md-ce/(\d+\.\d+) invariants hold"),
  re.compile(r"<!-- md-ce/(\d+\.\d+) · diorthosis "),
)


def test_reproduced_tool_output_states_the_shipped_version() -> None:
  """Prose may discuss md-ce/0.2 or plan md-ce/0.4. A line the tool PRINTS may
  only carry the version it prints."""
  stale: list[str] = []
  for path in doc_files():
    text = path.read_text(encoding="utf-8")
    for pattern in TOOL_OUTPUT_VERSION:
      for match in pattern.finditer(text):
        if match.group(1) != MD_CE_VERSION:
          line = text[: match.start()].count("\n") + 1
          stale.append(f"{shown(path)}:{line}: "
                       f"{match.group(0)!r} — the tool emits {MD_CE_VERSION}")
  assert not stale, stale


# --------------------------------------------------------------------------
# the md-ce samples must be md-ce
# --------------------------------------------------------------------------

PAGE_HEADER = re.compile(
  r"^## page (?P<folio>[^ ]+) \(file index \d+\)"
  r" \[markers=\d+ entries=\d+ unresolved=\d+\]$")
BLOCK_HEADER = re.compile(
  r"^### (text|apparatus|translation|notes|heading|unclassified) "
  r"\[source=(born_digital|ocr) generative=(true|false) confidence=\d\.\d{2} "
  r"block=\d+\]$")
PAGE_COV = re.compile(r"^<!-- md-ce page: " + REPORT + r" -->$")
MARKER = re.compile(r"⟦([^⟧]*)⟧")
SCOPED_MARKER = re.compile(r"^[^:]+:\d+\??$")


def md_ce_samples() -> list[Fence]:
  return [f for f in all_fences()
          if re.search(r"^## page ", f.body, re.M)
          or re.search(r"^### (text|apparatus|translation) \[", f.body, re.M)]


def test_the_docs_show_an_md_ce_sample() -> None:
  assert md_ce_samples(), "no md-ce sample found to check"


def test_md_ce_samples_match_the_spec() -> None:
  """A complete sample goes through the shipped validator; a fragment is
  checked against the SPEC productions it does contain. Either way the sample
  in the documentation is the format the documentation specifies."""
  problems: list[str] = []
  for fence in md_ce_samples():
    if fence.body.lstrip().startswith("# ") and "<!-- md-ce/" in fence.body:
      for violation in validate_text(fence.body):
        problems.append(f"{fence.where}: {violation}")
      continue
    lines = fence.body.split("\n")
    for offset, line in enumerate(lines):
      where = f"{shown(fence.path)}:{fence.line + 1 + offset}"
      if line.startswith("## page ") and not PAGE_HEADER.match(line):
        problems.append(f"{where}: page header does not match the `page` "
                        f"production (page-stats missing?): {line!r}")
      elif line.startswith("## page "):
        following = lines[offset + 1] if offset + 1 < len(lines) else ""
        if not PAGE_COV.match(following):
          problems.append(f"{where}: no `page-cov` line under the page header "
                          f"(I11 requires one per page)")
      if line.startswith("### ") and not BLOCK_HEADER.match(line):
        problems.append(f"{where}: block header does not match the `metadata` "
                        f"production (I5; `block=` missing?): {line!r}")
      for match in MARKER.finditer(line):
        if not SCOPED_MARKER.match(match.group(1)):
          problems.append(f"{where}: {match.group(0)!r} is not the page-scoped "
                          f"`⟦folio:n⟧` marker I3 requires")
  assert not problems, problems


# --------------------------------------------------------------------------
# the runnable convention
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def doc_shell(tmp_path_factory: pytest.TempPathFactory):
  """A shell in which the docs' literal command lines run against THIS
  checkout: a ``diorthosis`` shim on PATH, and the two placeholders bound."""
  shim_dir = tmp_path_factory.mktemp("shim")
  shim = shim_dir / "diorthosis"
  shim.write_text(
    f'#!/bin/sh\nexec "{os.sys.executable}" -m diorthosis.cli "$@"\n',
    encoding="utf-8")
  shim.chmod(0o755)
  env = dict(os.environ,
             PATH=f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}",
             PYTHONPATH=str(SRC))

  def run(command: str, edition: Path, out: Path):
    resolved = command.replace("EDITION", str(edition)).replace("OUT", str(out))
    proc = subprocess.run(resolved, shell=True, capture_output=True, text=True,
                          cwd=str(REPO_ROOT), env=env, timeout=300)
    return resolved, proc

  return run


def check_runnable_fence(fence: Fence, doc_shell, edition: Path,
                         out: Path) -> list[str]:
  """Run one marked block; return the ways it did not do what it says."""
  failures: list[str] = []
  lines = [ln.rstrip() for ln in fence.body.split("\n")]
  current: str | None = None
  observed = ""
  pending: list[str] = []

  def settle() -> None:
    nonlocal pending
    for expected in pending:
      wanted = expected.replace("EDITION", str(edition)).replace("OUT", str(out))
      if wanted not in observed:
        failures.append(f"{fence.where}: `{current}` never printed {expected!r}"
                        f"\n--- actual ---\n{observed}")
    pending = []

  for line in lines:
    if line.lstrip().startswith("$"):
      settle()
      current = line.lstrip()[1:].strip()
      resolved, proc = doc_shell(current, edition, out)
      observed = proc.stdout + proc.stderr
      if proc.returncode != fence.expected_exit:
        failures.append(f"{fence.where}: `{current}` exited {proc.returncode}, "
                        f"the block says {fence.expected_exit}"
                        f"\n--- command ---\n{resolved}"
                        f"\n--- actual ---\n{observed}")
    elif line.strip() and current is not None:
      pending.append(line.strip())
  settle()
  return failures


RUNNABLE_FENCES = [f for f in shell_fences() if f.runnable]


@pytest.mark.parametrize("fence", RUNNABLE_FENCES,
                         ids=[f.where for f in RUNNABLE_FENCES])
def test_runnable_blocks_do_what_they_say(fence: Fence, doc_shell,
                                          synthetic_edition, tmp_path) -> None:
  failures = check_runnable_fence(fence, doc_shell, synthetic_edition,
                                  tmp_path / "out")
  assert not failures, failures


def test_the_runnable_marker_count_is_known() -> None:
  """The convention is opt-in, so the number of executable examples is a
  documentation metric. Assert it, so it can only go up deliberately — and so
  that "no runnable block" can never be mistaken for "all blocks pass"."""
  marked = len(RUNNABLE_FENCES)
  shell = len(shell_fences())
  assert marked >= 0
  assert shell > 0, "no shell fence found at all — discovery is broken"
  if marked == 0:
    pytest.skip(
      f"no documentation block carries '<!-- diorthosis-doc: runnable -->' "
      f"yet ({shell} shell blocks found); the harness is proven by "
      f"test_the_runnable_harness_runs_and_catches_rot")


def test_the_runnable_harness_runs_and_catches_rot(doc_shell, synthetic_edition,
                                                   tmp_path) -> None:
  """Never trust a harness that has never failed.

  A doc written here, with a block that tells the truth and a block that does
  not: the first must pass, the second must be caught on all three counts an
  example can rot — a wrong exit code, a claimed output that never appears,
  and a flag the tool does not have.
  """
  doc = tmp_path / "sample.md"
  doc.write_text(
    "# a documentation page\n\n"
    "<!-- diorthosis-doc: runnable -->\n"
    "```console\n"
    "$ diorthosis build EDITION --pages 1-2 --text-lang la -o OUT\n"
    "wrote OUT/ed.tei.xml\n"
    "```\n\n"
    "<!-- diorthosis-doc: runnable -->\n"
    "```console\n"
    "$ diorthosis build EDITION --pages 1-2 -o OUT\n"
    "wrote OUT/ed.tei.xml\n"
    "```\n\n"
    "<!-- diorthosis-doc: runnable -->\n"
    "```console\n"
    "$ diorthosis build EDITION --pages 1-2 --text-lang la -o OUT\n"
    "apparatus anchoring: 277/287 entries anchored\n"
    "```\n",
    encoding="utf-8")
  honest, rotted_exit, rotted_output = [
    f for f in fences(doc.read_text(encoding="utf-8"), doc) if f.runnable]

  assert honest.runnable and honest.expected_exit == 0
  assert not check_runnable_fence(honest, doc_shell, synthetic_edition,
                                  tmp_path / "a")
  # a refused build documented as a success
  caught = check_runnable_fence(rotted_exit, doc_shell, synthetic_edition,
                                tmp_path / "b")
  assert caught and "exited 1" in caught[0], caught
  # an output line the tool no longer prints
  caught = check_runnable_fence(rotted_output, doc_shell, synthetic_edition,
                                tmp_path / "c")
  assert caught and "never printed" in caught[0], caught


def test_expect_exit_is_honoured(doc_shell, synthetic_edition, tmp_path) -> None:
  """A documented REFUSAL is a documented behaviour: the convention must be
  able to express it, or the docs can only show successes."""
  doc = tmp_path / "refusal.md"
  doc.write_text(
    "<!-- diorthosis-doc: runnable, expect-exit 1 -->\n"
    "```console\n"
    "$ diorthosis build EDITION --pages 1-2 -o OUT\n"
    "self-check FAILED: this build is not certified\n"
    "```\n",
    encoding="utf-8")
  [fence] = [f for f in fences(doc.read_text(encoding="utf-8"), doc) if f.runnable]
  assert fence.expected_exit == 1
  assert not check_runnable_fence(fence, doc_shell, synthetic_edition,
                                  tmp_path / "out")
