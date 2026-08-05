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

**2. Synthetic editions, built in-process, shipping no edition content.**
:func:`write_pdf` is a ~50-line PDF writer with no third-party dependency: one
uncompressed content stream per page, Type 1 Times-Roman, absolute text
positions. That is enough for the whole pipeline — regreek's geometric layerer
reads font-size registers and vertical gaps, and both are under our control —
and it means the net never needs reportlab, a network, or a byte of anyone's
critical edition. The Latin text below is invented for the fixture; the sigla
(A, B, Marc.) are shapes, not a real conspectus.
"""

from __future__ import annotations

import os
import subprocess
import sys
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
# a minimal, dependency-free PDF writer
# --------------------------------------------------------------------------

PAGE_W, PAGE_H = 612.0, 792.0
"""US Letter, in PDF units — the fixture pages' MediaBox."""

Item = tuple[float, float, float, str]
"""(x, y, font size, text) — one absolutely positioned line of Type 1 text."""


def _escape(text: str) -> bytes:
  out = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
  return out.encode("cp1252", "replace")


def write_pdf(path: Path, pages: list[list[Item]]) -> Path:
  """Write a born-digital PDF: one uncompressed text stream per page.

  ``pages`` is one list of :data:`Item` per page. An empty list produces a page
  carrying no text operator at all — what a scanned page looks like to a text
  extractor, and the fixture behind the image-only adversarial case.
  """
  objs: list[bytes] = [b"", b""]              # 1 = catalog, 2 = page tree

  def add(body: bytes) -> int:
    objs.append(body)
    return len(objs)

  font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman "
                b"/Encoding /WinAnsiEncoding >>")
  kids: list[int] = []
  for items in pages:
    stream = b"\n".join(
      b"BT /F1 " + f"{size:g}".encode() + b" Tf " + f"{x:g} {y:g}".encode()
      + b" Td (" + _escape(text) + b") Tj ET"
      for x, y, size, text in items
    )
    contents = add(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
                   + stream + b"\nendstream")
    kids.append(add(
      b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
      + f"{PAGE_W:g} {PAGE_H:g}".encode() + b"] /Resources << /Font << /F1 "
      + str(font_id).encode() + b" 0 R >> >> /Contents "
      + str(contents).encode() + b" 0 R >>"))
  objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
  objs[1] = (b"<< /Type /Pages /Kids ["
             + b" ".join(str(k).encode() + b" 0 R" for k in kids)
             + b"] /Count " + str(len(kids)).encode() + b" >>")

  out = bytearray(b"%PDF-1.4\n")
  offsets: list[int] = []
  for i, body in enumerate(objs, start=1):
    offsets.append(len(out))
    out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
  xref_at = len(out)
  out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
  for off in offsets:
    out += f"{off:010d} 00000 n \n".encode()
  out += (b"trailer\n<< /Size " + str(len(objs) + 1).encode()
          + b" /Root 1 0 R >>\nstartxref\n" + str(xref_at).encode()
          + b"\n%%EOF\n")
  path.write_bytes(bytes(out))
  return path


# --------------------------------------------------------------------------
# the synthetic edition: a conspectus page + two edition pages
# --------------------------------------------------------------------------

CONSPECTUS: list[Item] = [
  (220.0, PAGE_H - 90, 12.0, "CONSPECTVS SIGLORVM"),
  (120.0, PAGE_H - 130, 10.0, "A = Codex Ambrosianus, s. IX"),
  (120.0, PAGE_H - 146, 10.0, "B = Codex Bernensis, s. X"),
  (120.0, PAGE_H - 162, 10.0, "Marc. = Marcovich"),
]

# Invented Latin, in the shape a marker-convention edition prints: numbered
# superscript markers glued to the word they annotate, and one entry per line
# in the foot band, each naming who reads what.
PAGE_ONE_TEXT = [
  "Bellum ciuile1 gestum est apud Alexandriam, ubi Caesar",
  "cum paucis cohortibus2 remansit et hostium impetum",
  "fortiter sustinuit3 donec auxilia ex Syria uenirent.",
  "Nam classis regia portum obsidebat et copiae4 regis",
  "totam urbem tenebant, cum subito nuntius adfuit.",
]
PAGE_ONE_APPARATUS = [
  "1 Ciuile : ciuili A",
  "2 Cohortibus : cohortes B, Marc.",
  "3 Sustinuit : sustinet A B",
  "4 Copiae : copias A",
]
PAGE_TWO_TEXT = [
  "Interim Caesar naues longas1 comparauit atque milites",
  "in litore instruxit, ne quis exitus hostibus2 pateret.",
  "Alexandrini contra turres ligneas erexerunt et tela",
  "in nostros coniecerunt, sed uirtus3 legionum uicit.",
  "Postero die pax facta est et rex in castra uenit.",
]
PAGE_TWO_APPARATUS = [
  "1 Longas : longos B",
  "2 Hostibus : hostis A",
  "3 Uirtus : uirtute Marc.",
]


def edition_page(folio: int, text: list[str], band: list[str]) -> list[Item]:
  """One edition page: running head, text register, foot band, printed folio.

  The registers are what the layerer keys on — 11 pt text against an 8 pt band
  separated by a gap far larger than the body pitch — so the geometry, not a
  content guess, is what puts the apparatus in the apparatus layer.
  """
  items: list[Item] = [(PAGE_W / 2 - 40, PAGE_H - 54, 9.0, "LIBER PRIMVS")]
  y = PAGE_H - 100
  for line in text:
    items.append((90.0, y, 11.0, line))
    y -= 15
  y = 150.0
  for line in band:
    items.append((90.0, y, 8.0, line))
    y -= 10
  items.append((PAGE_W / 2 - 4, 50.0, 9.0, str(folio)))
  return items


@pytest.fixture(scope="session")
def synthetic_edition(tmp_path_factory: pytest.TempPathFactory) -> Path:
  """A three-page Latin edition: page 0 conspectus, pages 1-2 the edition.

  Built to be compiled with ``--pages 1-2 --text-lang la``: 7 apparatus
  entries, all of them parseable and anchorable, so it exercises the happy
  path of every subcommand.
  """
  path = tmp_path_factory.mktemp("edition") / "ed.pdf"
  return write_pdf(path, [
    CONSPECTUS,
    edition_page(11, PAGE_ONE_TEXT, PAGE_ONE_APPARATUS),
    edition_page(12, PAGE_TWO_TEXT, PAGE_TWO_APPARATUS),
  ])


@pytest.fixture(scope="session")
def numbered_prose_edition(tmp_path_factory: pytest.TempPathFactory) -> Path:
  """The fabrication shape wave A closed: a NUMBERED EDITORIAL FOOTNOTE band.

  Same printed geometry as an apparatus, same superscript numbering, same
  ``:`` — and not one siglum, because editorial prose never names a witness.
  Emitting these as ``<lem>/<rdg>`` variants is the defect an Opus assessment
  found in the Segrave *Insolubilia*; the band-level marker gate must refuse
  the whole band and keep the prose verbatim.
  """
  band = [
    "1 Ciuile here renders the phrase discussed at length above.",
    "2 Cohortibus should be understood in the technical sense.",
  ]
  path = tmp_path_factory.mktemp("prose") / "footnotes.pdf"
  return write_pdf(path, [CONSPECTUS, edition_page(11, PAGE_ONE_TEXT, band)])


@pytest.fixture(scope="session")
def unattributed_edition(tmp_path_factory: pytest.TempPathFactory) -> Path:
  """A band shaped exactly like an apparatus — but no reading names anybody.

  This reaches the marker gate's last clause (the one the token-consumption
  and parse-rate floors let through), so it is the direct regression test for
  wave A's "an apparatus records WHO reads WHAT" rule.
  """
  band = ["1 Ciuile : ciuili", "2 Cohortibus : cohortes"]
  path = tmp_path_factory.mktemp("bare") / "unattributed.pdf"
  return write_pdf(path, [CONSPECTUS, edition_page(11, PAGE_ONE_TEXT, band)])


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
def built_edition(cli, synthetic_edition: Path,
                  tmp_path_factory: pytest.TempPathFactory):
  """``build`` of :func:`synthetic_edition`, run once for the whole session."""
  out = tmp_path_factory.mktemp("built")
  result = cli("build", synthetic_edition, "--pages", "1-2",
               "--text-lang", "la", "-o", out)
  assert result.returncode == 0, result.report()
  return result, out


def assert_no_traceback(result: CliResult) -> None:
  """A user-facing CLI never shows a Python traceback — SPEC's exit-code
  contract calls a traceback the one failure mode that tells the user nothing.
  """
  assert "Traceback (most recent call last)" not in result.output, result.report()
  assert "\n  File \"" not in result.output, result.report()
