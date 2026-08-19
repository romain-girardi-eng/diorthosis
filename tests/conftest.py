"""Shared fixtures for the CLI, adversarial-input and documentation nets.

Two jobs, both of them things wave A had to do by hand.

**1. The suite tests the WORKING TREE.** The ambient interpreter carries no
``diorthosis``; without help every test here fails at collection, and the
usual cure — an editable install — is exactly what shadowed the working tree
during wave A's verification (a stale v0.6.0 answered while v0.7.0 was being
measured). So the repository's ``src/`` is prepended to ``sys.path`` here,
before any test module imports the package, and
``test_cli.py::test_the_suite_tests_the_working_tree`` asserts that the module
that answered really is the one in this checkout.

**2. Edition tests use a checksum-pinned published edition.** The fixture
accepts an explicit local file, then a gitignored cache, then the pinned
publisher URL. Every route verifies the same SHA-256 before a test can use the
file. If no verified copy is available, the tests skip with retrieval
instructions instead of substituting generated material.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"

if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

# Several tests re-enter Python in a subprocess (digest stability across
# interpreters, the double build, the CLI net below). They inherit the
# environment, not sys.path, so the same working tree has to be exported —
# otherwise the suite passes or fails depending on how pytest was invoked,
# which is the trap this file exists to remove.
_PYTHONPATH = os.environ.get("PYTHONPATH", "")
if str(SRC) not in _PYTHONPATH.split(os.pathsep):
  os.environ["PYTHONPATH"] = (f"{SRC}{os.pathsep}{_PYTHONPATH}" if _PYTHONPATH
                              else str(SRC))


# --------------------------------------------------------------------------
# the checksum-pinned real edition
# --------------------------------------------------------------------------

REAL_EDITION_URL = (
  "https://raw.githubusercontent.com/Library-of-Digital-Latin-Texts/balex/"
  "0e6ee82976a6ffeff41b5515594826719bfdfb0f/ldlt-balex.pdf"
)
REAL_EDITION_SHA256 = "6702fceb54ec347406c0d857ea508e2ff05e2e4dac9a5111df3f6aa2f96c1325"
REAL_EDITION_CACHE = REPO_ROOT / ".test-cache" / "ldlt-balex.pdf"


def _sha256(path: Path) -> str:
  digest = hashlib.sha256()
  with path.open("rb") as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
      digest.update(chunk)
  return digest.hexdigest()


def _verified(path: Path) -> tuple[bool, str]:
  if not path.is_file():
    return False, "file not found"
  try:
    actual = _sha256(path)
  except OSError as exc:
    return False, str(exc)
  if actual != REAL_EDITION_SHA256:
    return False, f"SHA-256 {actual}, expected {REAL_EDITION_SHA256}"
  return True, ""


@pytest.fixture(scope="session")
def real_edition() -> Path:
  """The published Bellum Alexandrinum PDF, verified before every return path."""
  failures: list[str] = []
  configured = os.environ.get("DIORTHOSIS_TEST_PDF")
  candidates = []
  if configured:
    candidates.append(("DIORTHOSIS_TEST_PDF", Path(configured).expanduser()))
  candidates.append(("test cache", REAL_EDITION_CACHE))

  for label, path in candidates:
    valid, reason = _verified(path)
    if valid:
      return path
    failures.append(f"{label} {path}: {reason}")

  try:
    with urllib.request.urlopen(REAL_EDITION_URL, timeout=30) as response:
      body = response.read()
  except (OSError, urllib.error.URLError) as exc:
    failures.append(f"download failed: {exc}")
  else:
    actual = hashlib.sha256(body).hexdigest()
    if actual != REAL_EDITION_SHA256:
      failures.append(
        f"download SHA-256 {actual}, expected {REAL_EDITION_SHA256}"
      )
    else:
      try:
        REAL_EDITION_CACHE.parent.mkdir(parents=True, exist_ok=True)
        REAL_EDITION_CACHE.write_bytes(body)
      except OSError as exc:
        failures.append(f"could not write test cache: {exc}")
      else:
        valid, reason = _verified(REAL_EDITION_CACHE)
        if valid:
          return REAL_EDITION_CACHE
        failures.append(f"written test cache failed verification: {reason}")

  pytest.skip(
    "real-edition tests need the checksum-pinned PDF; set DIORTHOSIS_TEST_PDF "
    f"to a local copy or fetch {REAL_EDITION_URL}. " + " | ".join(failures)
  )


@dataclass(frozen=True)
class RealEditionWindow:
  """A fast page slice of the real edition, with its known-good options."""

  pdf: Path
  pages: str = "82-84"
  conspectus_page: int = 54
  text_lang: str = "la"

  def args(self, *, include_text_lang: bool = True) -> tuple[object, ...]:
    args: tuple[object, ...] = (
      self.pdf, "--pages", self.pages,
      "--conspectus-page", self.conspectus_page,
    )
    if include_text_lang:
      args += ("--text-lang", self.text_lang)
    return args


@pytest.fixture(scope="session")
def real_edition_window(real_edition: Path) -> RealEditionWindow:
  """Pages 82–84 of the same verified edition; less work, not a smaller PDF."""
  return RealEditionWindow(real_edition)


@pytest.fixture(scope="session")
def image_only_real_page(real_edition: Path,
                         tmp_path_factory: pytest.TempPathFactory) -> Path:
  """One real edition page rasterized into a PDF with no extractable text."""
  pdfium = pytest.importorskip(
    "pypdfium2",
    reason="the real-PDF image-only case needs diorthosis[review] (pypdfium2)",
  )
  pytest.importorskip(
    "PIL",
    reason="the real-PDF image-only case needs diorthosis[review] (Pillow)",
  )
  path = tmp_path_factory.mktemp("image-only") / "ldlt-balex-page-82.pdf"
  document = pdfium.PdfDocument(real_edition)
  page = document[82]
  bitmap = page.render(scale=1)
  image = bitmap.to_pil().convert("RGB")
  try:
    image.save(path, format="PDF", resolution=72.0)
  finally:
    image.close()
    bitmap.close()
    page.close()
    document.close()
  return path


# --------------------------------------------------------------------------
# running the CLI as a user runs it
# --------------------------------------------------------------------------


class CliResult:
  """A finished CLI run, with the assertions every caller wants."""

  def __init__(self, argv: list[str], proc: subprocess.CompletedProcess[str]):
    self.argv = argv
    self.returncode = proc.returncode
    self.stdout = proc.stdout
    self.stderr = proc.stderr

  @property
  def output(self) -> str:
    return self.stdout + self.stderr

  @property
  def command(self) -> str:
    return "diorthosis " + " ".join(self.argv)

  def report(self) -> str:
    return (f"\ncommand: {self.command}\nexit: {self.returncode}"
            f"\nstdout:\n{self.stdout}\nstderr:\n{self.stderr}")


@pytest.fixture(scope="session")
def cli():
  """Run ``diorthosis …`` in a subprocess — the surface a user actually meets.

  In-process calls would miss what this net is for: the process exit code, and
  whether an unhandled exception reaches the terminal as a traceback.
  """
  env = dict(os.environ, PYTHONPATH=str(SRC))
  env.pop("PYTHONWARNINGS", None)

  def run(*args: object, hashseed: str | None = None) -> CliResult:
    argv = [str(a) for a in args]
    run_env = dict(env, PYTHONHASHSEED=hashseed) if hashseed else env
    proc = subprocess.run(
      [sys.executable, "-m", "diorthosis.cli", *argv],
      capture_output=True, text=True, env=run_env, cwd=str(REPO_ROOT),
      timeout=300,
    )
    return CliResult(argv, proc)

  return run


@pytest.fixture(scope="session")
def built_edition(cli, real_edition_window: RealEditionWindow,
                  tmp_path_factory: pytest.TempPathFactory):
  """A known-good three-page build from the checksum-pinned real edition."""
  out = tmp_path_factory.mktemp("built")
  result = cli("build", *real_edition_window.args(), "-o", out)
  assert result.returncode == 0, result.report()
  return result, out


def assert_no_traceback(result: CliResult) -> None:
  """A user-facing CLI never shows a Python traceback — SPEC's exit-code
  contract calls a traceback the one failure mode that tells the user nothing.
  """
  assert "Traceback (most recent call last)" not in result.output, result.report()
  assert "\n  File \"" not in result.output, result.report()
