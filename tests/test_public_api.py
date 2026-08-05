"""The frozen public surface, pinned.

``docs/stability.md`` §6 promises that ``diorthosis.__all__`` IS the public
Python API and that adding or removing a name is a deliberate, reviewed act.
This module is the mechanism that makes that true rather than aspirational:
``FROZEN`` below is a second, independent copy of the surface, so any change to
``__init__.__all__`` — in either direction — fails here and has to be argued
for.

It also pins two things that are fragile in ways a reader would not guess:

- ``__version__`` is assigned BEFORE the package's own imports, because
  ``tei.py`` and ``md.py`` do ``from . import __version__`` to stamp the tool
  version into every artefact. Reordering breaks the package at import time, in
  a way no ordinary test would catch — so the assignment order is checked
  statically AND a fresh interpreter is asked to import the package.
- ``docs/api.md`` holds a runnable end-to-end example and the output it
  produced. Both are extracted from the file itself: the example may use no
  name outside the frozen surface, and, wherever the documented edition is
  available, running it must still print exactly what the document claims.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import diorthosis

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
API_DOC = REPO / "docs" / "api.md"

# The public surface of diorthosis, frozen. Keep this list and
# src/diorthosis/__init__.py's __all__ identical, in the same order.
FROZEN = [
  # version
  "__version__",
  # ingest: a source file becomes a Document
  "ingest_pdf", "ingest_alto", "ingest_hocr", "ingest_pagexml",
  "parse_page_spec",
  # the document model
  "Document", "Page", "Block", "Layer", "Source", "Anchor", "ApparatusEntry",
  # the witness registry, declared by the edition's own conspectus siglorum
  "Registry", "bootstrap_registry", "with_builtin_editors", "witness_table",
  # anchoring and the ONE coverage report
  "anchor_page", "split_entries", "Coverage", "coverage",
  # the parsed apparatus structure, and how a band gate refuses
  "ParsedEntry", "Reading", "Attribution", "resolve_parsed", "GateDecision",
  # emission
  "to_tei", "to_markdown", "TEI_NS", "MD_CE_VERSION", "MarkerDelimiterError",
  # validation: the spec, executable
  "validate_text", "validate_file", "Violation", "MD_CE_SUPPORTED",
  "check_roundtrip",
  # human-review overrides
  "load_overrides", "apply_overrides", "entry_keys", "OVERRIDES_FORMAT",
]

# Names 0.7.0 exported that the frozen surface deliberately does NOT carry.
# Each is still reachable on internal terms; none is part of the contract.
DEMOTED = ["detect_marginal_line_numbers"]


def _subprocess(code: str) -> subprocess.CompletedProcess:
  """Run code in a FRESH interpreter against this working tree.

  PYTHONPATH is set explicitly rather than inherited: a stale installed
  diorthosis has shadowed the package before, and a test of the working tree
  that silently tested a released wheel is worse than no test.
  """
  env = dict(os.environ)
  env["PYTHONPATH"] = str(SRC)
  return subprocess.run(
    [sys.executable, "-c", code], env=env, capture_output=True, text=True)


class TestFrozenSurface:
  def test_all_is_exactly_the_frozen_list(self):
    assert diorthosis.__all__ == FROZEN

  def test_no_name_is_exported_twice(self):
    """Checked on the package's own list, not on FROZEN: a duplicate there is
    what a careless edit produces, and `from diorthosis import *` would import
    it twice in silence."""
    assert sorted(set(diorthosis.__all__)) == sorted(diorthosis.__all__)

  def test_every_frozen_name_imports_and_is_bound(self):
    for name in FROZEN:
      namespace: dict[str, object] = {}
      exec(f"from diorthosis import {name}", namespace)  # noqa: S102
      assert namespace[name] is not None, name
      assert getattr(diorthosis, name) is namespace[name], name

  def test_demoted_names_are_not_on_the_public_surface(self):
    for name in DEMOTED:
      assert name not in diorthosis.__all__
      assert not hasattr(diorthosis, name)

  def test_parse_page_spec_is_the_promoted_page_parser(self):
    from diorthosis.cli import _parse_pages

    assert diorthosis.parse_page_spec("290-292,1") == [1, 290, 291, 292]
    assert diorthosis.parse_page_spec(None) is None
    assert diorthosis.parse_page_spec("5,7") == _parse_pages("5,7")
    with pytest.raises(ValueError):
      diorthosis.parse_page_spec("320-290")


class TestVersion:
  def test_version_matches_pyproject(self):
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    declared = re.search(r'(?m)^version = "([^"]+)"$', text)
    assert declared is not None, "pyproject.toml declares no static version"
    assert diorthosis.__version__ == declared.group(1)

  def test_version_is_assigned_before_the_packages_own_imports(self):
    """The landmine, checked statically so the failure names itself.

    tei.py and md.py do ``from . import __version__``; if the assignment moves
    below the import block the package raises ImportError on ``import
    diorthosis``.
    """
    module = ast.parse((SRC / "diorthosis" / "__init__.py").read_text("utf-8"))
    assigned = [
      node.lineno for node in module.body
      if isinstance(node, ast.Assign)
      and any(getattr(t, "id", None) == "__version__" for t in node.targets)
    ]
    relative_imports = [
      node.lineno for node in module.body
      if isinstance(node, ast.ImportFrom) and node.level > 0
    ]
    assert assigned, "__init__.py no longer assigns __version__"
    assert relative_imports, "__init__.py no longer imports the package"
    assert min(assigned) < min(relative_imports), (
      "__version__ must be assigned BEFORE the relative imports: tei.py and "
      "md.py do 'from . import __version__' and would fail at import time")


class TestImportTime:
  """A fresh interpreter, because import order is invisible once cached."""

  def test_importing_the_package_works(self):
    done = _subprocess("import diorthosis; print(diorthosis.__version__)")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == diorthosis.__version__

  @pytest.mark.parametrize("first", [
    "import diorthosis.tei",
    "import diorthosis.md",
    "from diorthosis.tei import to_tei",
    "from diorthosis.md import to_markdown",
    "from diorthosis.mdce_validate import validate_text",
  ])
  def test_importing_a_submodule_first_works(self, first):
    """A submodule import runs the package __init__ first; this is the exact
    path the __version__ ordering protects."""
    done = _subprocess(first)
    assert done.returncode == 0, done.stderr

  def test_importing_the_package_does_not_pull_in_the_command_line(self):
    """parse_page_spec delegates lazily on purpose: importing the library
    must not drag in the application layer."""
    done = _subprocess(
      "import sys, diorthosis;"
      " print('diorthosis.cli' in sys.modules);"
      " diorthosis.parse_page_spec('1-2');"
      " print('diorthosis.cli' in sys.modules)")
    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == ["False", "True"]


def _fenced(language: str) -> list[str]:
  blocks = re.findall(
    rf"(?ms)^```{language}\n(.*?)^```\n", API_DOC.read_text(encoding="utf-8"))
  assert blocks, f"docs/api.md carries no ```{language} block"
  return blocks


def _example_source() -> str:
  blocks = _fenced("python")
  assert len(blocks) == 1, (
    f"docs/api.md must hold exactly one python block, found {len(blocks)}")
  return blocks[0]


def _documented_run() -> tuple[str, str]:
  """(command line, expected stdout) from the console block that runs it."""
  for block in _fenced("console"):
    if block.startswith("$ python3 example.py "):
      command, _, output = block.partition("\n")
      return command[2:], output
  raise AssertionError(
    "docs/api.md carries no '$ python3 example.py …' console block")


def _documented_pdf() -> Path | None:
  """The edition docs/api.md is written against, if this machine has it.

  diorthosis ships no edition content, so the example's input has to be
  fetched. Point DIORTHOSIS_BALEX_PDF at the Digital Latin Library's own PDF
  of Damon's Bellum Alexandrinum to run the documented example here.
  """
  candidates = [
    os.environ.get("DIORTHOSIS_BALEX_PDF"),
    "/tmp/ldlt-balex.pdf",
    str(REPO / "tools" / "golden" / "data" / "ldlt-balex.pdf"),
    str(REPO / "tools" / "golden" / "work" / "ldlt-balex.pdf"),
  ]
  for candidate in candidates:
    if candidate and Path(candidate).is_file():
      return Path(candidate)
  return None


class TestDocumentedExample:
  def test_example_uses_only_frozen_names(self):
    tree = ast.parse(_example_source())
    imported: list[str] = []
    for node in ast.walk(tree):
      if isinstance(node, ast.ImportFrom) and (node.module or "").split(
          ".")[0] == "diorthosis":
        assert node.module == "diorthosis", (
          f"docs/api.md imports from the internal module {node.module!r}: the "
          "example must use the frozen surface only")
        imported += [alias.name for alias in node.names]
      if isinstance(node, ast.Import):
        assert not any(a.name.startswith("diorthosis") for a in node.names), (
          "docs/api.md must import diorthosis names, not diorthosis modules")
    assert imported, "docs/api.md's example imports nothing from diorthosis"
    assert set(imported) <= set(FROZEN), sorted(set(imported) - set(FROZEN))

  def test_example_is_valid_python(self):
    compile(_example_source(), "docs/api.md", "exec")

  def test_documented_command_line_matches_the_example(self):
    command, _ = _documented_run()
    assert command.split()[:2] == ["python3", "example.py"]
    assert len(command.split()) == 4, (
      "the documented invocation must pass the PDF and the output directory")

  def test_example_runs_and_prints_what_the_document_claims(self, tmp_path):
    pdf = _documented_pdf()
    if pdf is None:
      pytest.skip(
        "the documented edition is not on this machine: diorthosis ships no "
        "edition content. Fetch the Digital Latin Library's ldlt-balex.pdf "
        "and set DIORTHOSIS_BALEX_PDF to it to run docs/api.md's example.")
    script = tmp_path / "example.py"
    script.write_text(_example_source(), encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    done = subprocess.run(
      [sys.executable, str(script), str(pdf), str(tmp_path / "out")],
      env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    _, expected = _documented_run()
    assert done.stdout == expected, (
      "docs/api.md's pasted output is stale: the example now prints\n"
      f"{done.stdout}\ninstead of\n{expected}")
    assert (tmp_path / "out" / "example.tei.xml").is_file()
    assert (tmp_path / "out" / "example.md").is_file()
