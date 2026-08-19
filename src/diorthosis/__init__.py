"""diorthosis: compile published critical editions into TEI P5 + AI-ready
Markdown, with anchored apparatus and block-level provenance.

``diorthosis.__all__`` below IS the public Python API — the whole of it. It is
small on purpose and sufficient on purpose: every name it lists is needed to
run the documented pipeline (ingest → registry → anchoring → coverage →
emission → validation → overrides) from Python, and nothing that is not
needed for that is listed.

**Everything else in this package is internal.** ``diorthosis.grammar``,
``diorthosis.linegrammar``, ``diorthosis.versegrammar``,
``diorthosis.paragraphgrammar``, ``diorthosis.match``, ``diorthosis.review``,
``diorthosis.ingest.*`` and every underscore-prefixed name are implementation:
they may be renamed, split, merged or deleted in any release, including a
patch. Import them and your code is coupled to a moving part. The one thing
they are good for is reading the source to understand a decision — which is
encouraged, and is not the same as depending on it.

``diorthosis.cli`` is not part of the Python API either; the *command line* it
implements is a separate frozen contract (subcommands, flags and the four exit
codes). Both contracts, and what a break to either would require, are written
down in ``docs/stability.md``; ``docs/api.md`` holds a runnable end-to-end
example.

Import-time note, load-bearing: ``__version__`` is assigned BEFORE the imports
below because ``tei.py`` and ``md.py`` do ``from . import __version__`` (they
stamp the tool version into every artefact they emit). Moving the assignment
after the import block breaks the package at import time. ``tests/
test_public_api.py`` pins this in a fresh interpreter.
"""

__version__ = "1.1.0"

from .anchor import anchor_page, split_entries
from .conspectus import Registry, bootstrap_registry, with_builtin_editors
from .convention import GateDecision
from .grammar import Attribution, ParsedEntry, Reading
from .ingest import ingest_alto, ingest_hocr, ingest_pagexml, ingest_pdf
from .md import (
  MD_CE_VERSION,
  Coverage,
  MarkerDelimiterError,
  coverage,
  to_markdown,
)
from .mdce_validate import (
  MD_CE_SUPPORTED,
  Violation,
  validate_file,
  validate_text,
)
from .model import (
  Anchor,
  ApparatusEntry,
  Block,
  Document,
  Layer,
  Page,
  Source,
)
from .overrides import FORMAT as OVERRIDES_FORMAT
from .overrides import apply_overrides, entry_keys, load_overrides
from .roundtrip import check_roundtrip
from .tei import TEI_NS, resolve_parsed, to_tei
from .witnesses import witness_table


def parse_page_spec(spec: str | None) -> list[int] | None:
  """Parse a CLI-style page selection into 0-based page indices.

  ``"290-320"``, ``"1,5,9"`` and ``"1,5-7"`` are all accepted; the result is
  sorted and de-duplicated, and ``None`` (select every page) passes through.
  Sorting is not cosmetic: pdfminer yields pages in document order whatever
  order they were asked for, so an unsorted selection would silently label
  one page's content with another's index.

  Raises ``ValueError`` on an empty spec, a reversed range, or an element
  that is neither an integer nor ``A-B`` — the same errors the CLI turns
  into exit code 2.

  This is the public name of the page-spec parser the ``build`` and
  ``review`` subcommands use; ``diorthosis.cli`` keeps the private alias it
  has always called. The delegation is imported lazily so that ``import
  diorthosis`` never pulls in the command-line layer.
  """
  from .cli import _parse_pages

  return _parse_pages(spec)


__all__ = [
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
