"""What the ingest boundary says when it cannot read a file.

Every adapter in this package stands on somebody else's parser — pdfminer for
PDFs, ``xml.etree`` for ALTO and PAGE, ``html.parser`` for hOCR — and each of
them fails in its own vocabulary: ``PDFSyntaxError``, ``PSEOF``,
``ParseError``, ``PDFPasswordIncorrect`` with nothing at all after the colon.
None of that is a diagnosis a scholar can act on, and letting it reach the
terminal also spends the exit-code contract on a lie: a download that produced
nothing is the user's problem to fix, not a diorthosis defect to report.

Two rules, and this module is both of them:

1. **An adapter that cannot parse its input refuses it — in diorthosis's own
   words, naming the file.** ``--alto``/``--hocr``/``--page-xml`` take many
   files; a refusal that does not say which one is unusable on a 400-page
   scan.
2. **A library's failure is translated, never swallowed wholesale.** Only the
   dependency's *own* exception hierarchy — the one that means "this document
   is bad" — becomes a :class:`SourceRefused`. A plain ``TypeError`` out of
   diorthosis or regreek is a diorthosis defect and still reaches exit 3,
   where the contract puts it.

The refusal is also what keeps a broken file from being *recovered into*
edition text: markup a parser could not finish is markup, and emitting it as
text would be fabrication in the shape of a scan.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


class SourceRefused(ValueError):
  """This file is not the format it was handed over as.

  Its message is the whole diagnosis: the offending path, what the file is
  not, and what to do instead. ``ValueError`` is the base so that any caller
  already treating a bad argument as a user error keeps doing so; ``cli.run``
  maps it to exit 2 — a user-actionable input error, never 3.
  """


# Leading bytes that settle the question before any parser is asked. The
# common slip is the scan itself under --alto: an XML parser answers that
# with "not well-formed (invalid token): line 1, column 8", which describes
# the file's first byte instead of the mistake.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
  (b"%PDF-", "a PDF"),
  (b"\x89PNG\r\n\x1a\n", "a PNG image"),
  (b"\xff\xd8\xff", "a JPEG image"),
  (b"II*\x00", "a TIFF image"),
  (b"MM\x00*", "a TIFF image"),
  (b"PK\x03\x04", "a ZIP container (an .odt / .docx / .epub?)"),
  (b"\x1f\x8b", "a gzip archive"),
)


def _looks_like(raw: bytes) -> str | None:
  for magic, what in _SIGNATURES:
    if raw.startswith(magic):
      return what
  return None


def read_source(path: str | Path, fmt: str) -> bytes:
  """The file's bytes, or a refusal naming it.

  A missing file stays a ``FileNotFoundError``: the CLI already reports that
  one in its own words, and re-labelling it here would say less.
  """
  raw = Path(path).read_bytes()
  if not raw.strip():
    raise SourceRefused(
      f"{path}: the file is empty ({len(raw)} bytes) — there is nothing to "
      f"read as {fmt}; the export or the download produced no data")
  what = _looks_like(raw)
  if what is not None:
    hint = ("pass it as the positional argument instead: "
            "diorthosis build FILE.pdf" if what == "a PDF" else
            f"diorthosis never calls an OCR engine: run one over this file "
            f"and pass its {fmt} export")
    raise SourceRefused(f"{path}: this is {what}, not {fmt} — {hint}")
  return raw


def read_source_text(path: str | Path, fmt: str) -> str:
  """The file's text. Undecodable bytes are a refusal, not a traceback."""
  raw = read_source(path, fmt)
  try:
    return raw.decode("utf-8")
  except UnicodeDecodeError as exc:
    raise SourceRefused(
      f"{path}: not {fmt} — the file is not UTF-8 text (byte {exc.start} "
      f"cannot be decoded); re-export this page from your OCR engine"
    ) from None


def parse_xml(path: str | Path, fmt: str) -> ET.Element:
  """Parse ``path`` as XML, or refuse it in diorthosis's words.

  Parsed from BYTES on purpose: an XML declaration may name an encoding other
  than UTF-8, and honouring it is the format's own rule, not a guess.
  """
  raw = read_source(path, fmt)
  try:
    return ET.fromstring(raw)  # noqa: S314 — stdlib parser, no external entities
  except ET.ParseError as exc:
    raise SourceRefused(
      f"{path}: not {fmt} — the file is not well-formed XML ({exc}); a "
      f"truncated or interrupted export is the usual cause, so re-export "
      f"this page from your OCR engine") from None
