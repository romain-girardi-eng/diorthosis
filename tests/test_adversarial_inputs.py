"""The ingest boundary must fail HONESTLY.

Everything here is a file a real user will hand the tool by accident: a
download that produced nothing, a PDF that is really a text file, a
publisher's encrypted PDF, a scan with no text layer, an OCR export that was
truncated mid-write, the wrong format under the wrong flag. None of them is a
critical edition, and the tool's whole promise is that it says so.

Four properties, asserted over the whole corpus:

1. **Never a traceback.** A Python stack on a scholar's terminal says nothing
   the scholar can act on.
2. **A clean exit code.** The contract (``cli.py``) reserves 3 for "an
   internal fault — a diorthosis defect, not an input problem". A malformed
   input file is an input problem: 1 or 2, never 3.
3. **An actionable message.** It must name the offending file, or say in the
   tool's own vocabulary what the file is not.
4. **Never a fabricated structure.** No ``<app>``, and no fragment of the
   source's own markup emitted as edition text.

KNOWN DEFECTS AT HEAD — the following are RED on purpose; each carries its
reproduction in the test that names it:

- ``test_exit_code_is_never_an_internal_fault`` fails for the zero-byte PDF,
  the text file renamed ``.pdf``, the truncated PDF, the encrypted PDF, and
  every truncated or empty ALTO / PAGE-XML file. All of them surface as
  ``internal error: …`` + "please report it" at exit 3.
- ``test_a_malformed_source_is_never_certified`` fails for truncated hOCR:
  ``html.parser`` recovers from the unterminated tag, and the build exits 0.
- ``test_source_markup_never_becomes_edition_text`` fails for the same file:
  the recovered fragment ``<span class='ocr_line'`` is emitted as an md-ce
  body — markup impersonating edition text, at exit 0.
- ``test_a_foreign_file_is_identified_as_not_that_format`` fails for
  ``--alto``: the ALTO adapter has no "not ALTO" guard, so a foreign XML file
  yields the generic degeneracy advice "run an OCR engine and pass its output
  with --alto/--hocr/--page-xml" — which is what the user just did.
- ``test_message_is_not_a_bare_library_exception`` and
  ``test_message_names_the_offending_file`` fail wherever a dependency's
  exception is the whole diagnosis: ``PDFSyntaxError``,
  ``PDFPasswordIncorrect`` (with an EMPTY message after the colon), ``PSEOF``,
  ``ParseError``. The hOCR adapter is the counter-example that proves it is
  fixable: it says "no ocr_page element — not hOCR output", with the path.

None of these is fixed in ``src/``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest
from conftest import assert_no_traceback, write_pdf

ALTO_OK = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout><Page><PrintSpace>
<TextBlock ID="b1"><TextLine><String CONTENT="Bellum" WC="0.98"/><SP/>
<String CONTENT="ciuile" WC="0.97"/></TextLine></TextBlock>
</PrintSpace></Page></Layout></alto>
"""
HOCR_OK = """<html><body>
<div class='ocr_page' id='page_1' title='bbox 0 0 100 100'>
 <span class='ocr_line' title='bbox 1 1 99 9'>
  <span class='ocrx_word' title='bbox 1 1 40 9; x_wconf 96'>Bellum</span>
 </span></div></body></html>
"""
PAGE_OK = """<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">
 <Page imageWidth="100" imageHeight="100"><TextRegion id="r1"><TextLine id="l1">
 <TextEquiv conf="0.95"><Unicode>Bellum ciuile</Unicode></TextEquiv>
 </TextLine></TextRegion></Page></PcGts>
"""
# A real file from another world: an EAD-ish finding aid. Not ALTO, not hOCR,
# not PAGE — and the adapter should say which.
FOREIGN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ead xmlns="urn:isbn:1-931666-22-9"><archdesc level="collection">
 <did><unittitle>Papiers d'un editeur</unittitle></did></archdesc></ead>
"""


def encrypted_pdf(path: Path) -> Path:
  """A PDF behind the standard security handler, with no usable password."""
  raw = write_pdf(path.with_name("plain.pdf"),
                  [[(90.0, 700.0, 11.0, "Bellum ciuile gestum est.")]]).read_bytes()
  size = int(re.search(rb"/Size (\d+)", raw).group(1))
  encrypt = (b"<< /Filter /Standard /V 1 /R 2 /Length 40 /P -1 /O <"
             + b"41" * 32 + b"> /U <" + b"42" * 32 + b"> >>")
  head, tail = raw.split(b"xref\n0 ", 1)
  out = (head + str(size).encode() + b" 0 obj\n" + encrypt + b"\nendobj\n"
         + b"xref\n0 " + tail)
  out = out.replace(b"/Root 1 0 R >>",
                    b"/Root 1 0 R /Encrypt " + str(size).encode()
                    + b" 0 R /ID [<AA> <AA>] >>")
  path.write_bytes(out)
  return path


def truncated_pdf(path: Path) -> Path:
  raw = write_pdf(path.with_name("whole.pdf"),
                  [[(90.0, 700.0, 11.0, "Bellum ciuile gestum est.")]]).read_bytes()
  path.write_bytes(raw[: len(raw) // 2])
  return path


@dataclass(frozen=True)
class Case:
  """One adversarial input and what the contract says about it."""

  name: str
  filename: str
  flag: str | None
  """``None`` = positional PDF argument."""
  body: str | bytes | None = None
  build: object = None
  """Callable(Path) -> Path, for inputs a string cannot express."""
  extra: tuple[str, ...] = ()
  well_formed: bool = False
  """False = the file is structurally broken; certifying it is never right."""
  foreign_format: bool = False
  """True = a well-formed file of the WRONG format for the flag it was given."""


CASES: tuple[Case, ...] = (
  Case("pdf-zero-byte", "empty.pdf", None, body=b""),
  Case("pdf-text-renamed", "prose.pdf", None,
       body="Bellum ciuile gestum est apud Alexandriam.\n"),
  Case("pdf-truncated", "cut.pdf", None, build=truncated_pdf),
  Case("pdf-encrypted", "locked.pdf", None, build=encrypted_pdf),
  Case("pdf-no-text-operators", "scan.pdf", None,
       build=lambda p: write_pdf(p, [[]]), extra=("--text-lang", "la"),
       well_formed=True),
  Case("pdf-pages-select-nothing", "one.pdf", None,
       build=lambda p: write_pdf(p, [[(90.0, 700.0, 11.0, "Bellum ciuile.")]]),
       extra=("--pages", "900"), well_formed=True),

  Case("alto-truncated", "p.xml", "--alto", body=ALTO_OK[: len(ALTO_OK) // 2]),
  Case("alto-empty", "p.xml", "--alto", body=""),
  Case("alto-foreign-vocabulary", "p.xml", "--alto", body=FOREIGN_XML,
       well_formed=True, foreign_format=True),
  Case("alto-binary", "p.xml", "--alto",
       build=lambda p: write_pdf(p, [[(90.0, 700.0, 11.0, "Bellum.")]])),

  Case("hocr-truncated", "p.html", "--hocr",
       body="<html><body><div class='ocr_page' title='bbox 0 0 10 10'>"
            "<span class='ocr_line'"),
  Case("hocr-empty", "p.html", "--hocr", body=""),
  Case("hocr-foreign-vocabulary", "p.html", "--hocr", body=FOREIGN_XML,
       well_formed=True, foreign_format=True),
  Case("hocr-binary", "p.html", "--hocr",
       build=lambda p: write_pdf(p, [[(90.0, 700.0, 11.0, "Bellum.")]])),

  Case("pagexml-truncated", "p.xml", "--page-xml",
       body=PAGE_OK[: len(PAGE_OK) // 2]),
  Case("pagexml-empty", "p.xml", "--page-xml", body=""),
  Case("pagexml-foreign-vocabulary", "p.xml", "--page-xml", body=FOREIGN_XML,
       well_formed=True, foreign_format=True),
  Case("pagexml-binary", "p.xml", "--page-xml",
       build=lambda p: write_pdf(p, [[(90.0, 700.0, 11.0, "Bellum.")]])),
)

IDS = [c.name for c in CASES]


@pytest.fixture
def attempt(cli, tmp_path):
  """Build one adversarial file and run ``build`` on it."""

  def run(case: Case):
    src = tmp_path / case.filename
    if case.build is not None:
      case.build(src)
    elif isinstance(case.body, bytes):
      src.write_bytes(case.body)
    else:
      src.write_text(case.body or "", encoding="utf-8")
    out = tmp_path / "out"
    args = ["build"]
    args += [case.flag, str(src)] if case.flag else [str(src)]
    args += [*case.extra, "-o", str(out)]
    return cli(*args), out

  return run


def emitted(out: Path) -> list[Path]:
  return sorted(out.glob("*")) if out.is_dir() else []


# --------------------------------------------------------------------------
# 1. never a traceback
# --------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_never_a_traceback(attempt, case: Case) -> None:
  result, _ = attempt(case)
  assert_no_traceback(result)


# --------------------------------------------------------------------------
# 2. a clean exit code
# --------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_exit_code_is_never_an_internal_fault(attempt, case: Case) -> None:
  """Exit 3 means "a diorthosis defect, not an input problem" and asks the
  user to file a bug. A file the user chose badly is an input problem.

  Reproduce (zero-byte PDF)::

      : > empty.pdf && diorthosis build empty.pdf -o out/
      # internal error: PDFSyntaxError: No /Root object! - Is this really a PDF?
      # this is a diorthosis defect, not an input problem; please report it
      # exit 3
  """
  result, _ = attempt(case)
  assert result.returncode != 3, result.report()
  assert result.returncode in (0, 1, 2), result.report()
  assert "please report it" not in result.stderr, result.report()


@pytest.mark.parametrize("case", [c for c in CASES if not c.well_formed],
                         ids=[c.name for c in CASES if not c.well_formed])
def test_a_malformed_source_is_never_certified(attempt, case: Case) -> None:
  """A file that is not even well formed cannot yield a certified edition.

  Reproduce (truncated hOCR)::

      printf "<html><body><div class='ocr_page' title='bbox 0 0 10 10'>" \\
        "<span class='ocr_line'" > p.html
      diorthosis build --hocr p.html -o out/
      # wrote out/p.tei.xml … exit 0
  """
  result, _ = attempt(case)
  assert result.returncode != 0, result.report()


# --------------------------------------------------------------------------
# 3. an actionable message
# --------------------------------------------------------------------------


LEAKED_EXCEPTIONS = (
  "PDFSyntaxError", "PDFPasswordIncorrect", "PDFException", "PSEOF",
  "PSSyntaxError", "ParseError", "XMLSyntaxError", "UnicodeDecodeError",
  "FileExistsError", "KeyError",
)
"""Exception classes belonging to a dependency. Their repr is a stack-trace
fragment, not a sentence: whenever one of them reaches the terminal the user
has been handed diorthosis's internals instead of a diagnosis."""


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_message_is_not_a_bare_library_exception(attempt, case: Case) -> None:
  """The refusal must be the tool's own words.

  Reproduce (encrypted PDF — note the message is EMPTY after the colon)::

      diorthosis build locked.pdf -o out/
      # internal error: PDFPasswordIncorrect:
  """
  result, _ = attempt(case)
  if result.returncode == 0:
    pytest.skip("accepted; the message contract applies to refusals")
  assert result.stderr.strip(), result.report()
  leaked = [name for name in LEAKED_EXCEPTIONS if name in result.stderr]
  assert not leaked, f"{leaked} reached the user{result.report()}"


OCR_CASES = [c for c in CASES if c.flag]


@pytest.mark.parametrize("case", OCR_CASES, ids=[c.name for c in OCR_CASES])
def test_message_names_the_offending_file(attempt, case: Case) -> None:
  """``--alto``/``--hocr``/``--page-xml`` take MANY files. A refusal that does
  not say which one is unusable on a 400-page scan.

  Reproduce::

      diorthosis build --alto good.xml truncated.xml -o out/
      # internal error: ParseError: unclosed token: line 3, column 19
      #                             ^ which of the two?
  """
  result, _ = attempt(case)
  if result.returncode == 0:
    pytest.skip("accepted; the message contract applies to refusals")
  assert result.stderr.strip(), result.report()
  assert case.filename in result.stderr, result.report()


@pytest.mark.parametrize("case", [c for c in CASES if c.foreign_format],
                         ids=[c.name for c in CASES if c.foreign_format])
def test_a_foreign_file_is_identified_as_not_that_format(attempt, case: Case) -> None:
  """``--hocr`` says "no ocr_page element — not hOCR output" and
  ``--page-xml`` says "not PAGE-XML — root is <ead>, expected <PcGts>".
  ``--alto`` has no such guard, so a foreign file falls through to the generic
  degeneracy advice — which tells the user to do what they just did.

  Reproduce::

      diorthosis build --alto finding-aid.xml -o out/
      # degenerate: the 1 selected page(s) carry no decodable text at all.
      #   If this is a scanned edition, diorthosis never calls an OCR engine:
      #   run one and pass its output with --alto/--hocr/--page-xml.
  """
  result, _ = attempt(case)
  assert result.returncode != 0, result.report()
  fmt = {"--alto": "ALTO", "--hocr": "hOCR", "--page-xml": "PAGE-XML"}[case.flag]
  assert re.search(rf"not {re.escape(fmt)}\b", result.stderr, re.I), result.report()


# --------------------------------------------------------------------------
# 4. never a fabricated structure
# --------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_no_fabricated_apparatus(attempt, case: Case) -> None:
  """Whatever else happens, no adversarial input yields an ``<app>``: not one
  of these files contains a collation."""
  _, out = attempt(case)
  for path in emitted(out):
    if path.suffix == ".xml":
      text = path.read_text(encoding="utf-8", errors="replace")
      assert "<app " not in text and "<rdg" not in text, path


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_source_markup_never_becomes_edition_text(attempt, case: Case) -> None:
  """Recovering from broken markup must not turn the markup itself into text.

  Reproduce (truncated hOCR, exit 0)::

      ### unclassified [source=ocr generative=true confidence=0.00 block=0]

      <span class='ocr_line'
  """
  _, out = attempt(case)
  for path in emitted(out):
    if path.suffix != ".md":
      continue
    for line in path.read_text(encoding="utf-8").split("\n"):
      if line.startswith(("#", "<!-- md-ce", "*refs:")) or not line.strip():
        continue
      assert not re.search(r"<\s*/?\s*(span|div|p|html|body|meta|alto|PcGts|"
                           r"TextBlock|TextLine|String|Unicode)\b", line), (
        f"{path}: source markup emitted as edition text: {line!r}")


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_anything_written_is_valid_md_ce(cli, attempt, case: Case) -> None:
  """If a file was written at all, it is either certified or explicitly not —
  and an md-ce the shipped validator rejects may never leave at exit 0."""
  result, out = attempt(case)
  if result.returncode != 0:
    return
  for path in emitted(out):
    if path.suffix == ".md":
      checked = cli("validate", path)
      assert checked.returncode == 0, checked.report()
