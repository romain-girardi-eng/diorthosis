"""diorthosis: compile published critical editions into TEI P5 + AI-ready
Markdown, with anchored apparatus and block-level provenance."""

__version__ = "0.4.0"

from .anchor import anchor_page, detect_marginal_line_numbers, split_entries
from .md import to_markdown
from .model import (
  Anchor,
  ApparatusEntry,
  Block,
  Document,
  Layer,
  Page,
  Source,
)
from .tei import to_tei

__all__ = [
  "Anchor", "ApparatusEntry", "Block", "Document", "Layer", "Page", "Source",
  "anchor_page", "detect_marginal_line_numbers", "split_entries",
  "to_markdown", "to_tei", "__version__",
]
