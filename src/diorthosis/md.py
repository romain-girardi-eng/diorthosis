"""The AI-ready Markdown view — md-ce/0.3, a normative, executable format.

This is a VIEW, never a second truth: derived from the same document model
as the TEI, block for block. The full grammar and the twelve invariants live
in SPEC.md at the repository root; the ones that shape this module:

- **I1** any body line that could impersonate structure (``#…``, a ``<!--
  md-ce`` comment) is escaped with a backslash and counted in the header;
- **I3** markers are page-scoped ``⟦folio:n⟧``; an unresolved anchor renders
  ``⟦folio:n?⟧`` and never pretends to link;
- **I4** the marker delimiters may not occur in source text — if they do,
  emission REFUSES rather than produce an ambiguous file;
- **I6** every section header carries the block's 0-based ordinal within its
  page, counting furniture, so (folio, block) is a stable address;
- **I9** lossiness is declared: page furniture, the conspectus and the parsed
  apparatus structure live in the TEI named by the header, nowhere else;
- **I11** ONE coverage report, rendered from a single :class:`Coverage`, is
  the only score diorthosis states: the meta line and every page line carry
  the same production, and the CLI prints that exact text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import __version__
from .anchor import find_markers
from .conspectus import Registry
from .match import locate_lemma_start
from .model import Document, Layer
from .tei import resolve_parsed

MD_CE_VERSION = "0.3"

_LAYER_TITLES = {
  Layer.TEXT: "text",
  Layer.APPARATUS: "apparatus",
  Layer.TRANSLATION: "translation",
  Layer.NOTES: "notes",
  Layer.HEADING: "heading",
  Layer.UNKNOWN: "unclassified",
}
_FURNITURE = (Layer.RUNNING_HEAD, Layer.PAGE_NUMBER)
_STRUCTURAL = re.compile(r"^(#{1,6} |<!-- md-ce)")

HUMAN_VERBATIM = "human review forced the entry verbatim"
"""Tally key for an entry a reviewer refused: it has no gate evidence, but a
refusal without a stated reason is exactly what SPEC I11 forbids."""

# Gate reasons carry their own measurements ("trial parse left 41.7% of
# tokens unconsumed (maximum 25%)"). Collapsing every numeric run gives ONE
# tally key per refusal CLASS instead of one key per measured value; the
# thresholds themselves live in the grammars, not in the artifact.
_REASON_NUMBER = re.compile(r"\d+(?:[.,]\d+)*%?")


def _refusal_key(evidence: str) -> str:
  """The tally key of one band-gate refusal.

  ``;`` and ``·`` delimit the meta line's own fields, so a reason may not
  carry them. They are FOLDED, never dropped: a sanitised character stays
  visible in the artifact instead of silently shortening a scholar-facing
  refusal reason.
  """
  key = _REASON_NUMBER.sub("n", " ".join(evidence.split()))
  return key.replace("·", ".").replace(";", ",")


@dataclass(frozen=True)
class Coverage:
  """The single coverage report — the only score diorthosis states.

  Before 0.3 one invocation announced two different numbers: the console
  printed model-level anchoring while the md-ce meta printed the *view's*
  numeric-marker resolution (0/563 on an edition the console called
  563/563), and "anchored" counted the END anchor of a double-end-point
  attachment alone, so an entry whose lemma start was never located still
  counted as fully anchored. Every counter below is therefore split on the
  axis that made the old number unreadable:

  - structure: ``parsed + refused + unparsed == entries``. ``refused`` is a
    convention gate's or a reviewer's explicit refusal and always carries a
    reason in ``refusals``; ``unparsed`` is an entry the accepted grammar
    simply produced no structure for.
  - attachment: ``attached + end_only + unanchored == entries``.
    ``attached`` is a full double-end-point link (TEI ``@from`` and ``@to``);
    ``end_only`` carries ``@to`` alone because the lemma's start could not be
    located with confidence.
  """

  entries: int = 0
  parsed: int = 0
  refused: int = 0
  unparsed: int = 0
  attached: int = 0
  end_only: int = 0
  unanchored: int = 0
  refusals: tuple[tuple[str, int], ...] = ()
  """(reason, count), sorted by descending count then reason; sums to
  ``refused``."""
  pages: tuple[Coverage, ...] = ()
  """Per-page breakdown, aligned with ``Document.pages``; empty on a page's
  own Coverage."""

  @property
  def anchored(self) -> int:
    return self.attached + self.end_only

  @property
  def report(self) -> str:
    """The one production shared by the console, the meta line and every
    page line — rendered once so the three can never drift apart."""
    return (
      f"{self.entries} entries — {self.parsed} parsed, {self.refused} refused, "
      f"{self.unparsed} unparsed; {self.anchored} anchored "
      f"({self.attached} attached, {self.end_only} end-only), "
      f"{self.unanchored} unanchored"
    )

  @property
  def refusal_tally(self) -> str:
    if not self.refusals:
      return "none"
    return "; ".join(f"{count}× {reason}" for reason, count in self.refusals)

  @property
  def lines(self) -> tuple[str, str]:
    """The report as the CLI prints it; the meta line joins the same two
    strings with the field separator."""
    return (f"coverage: {self.report}", f"refusals: {self.refusal_tally}")


@dataclass
class _Counts:
  """Mutable accumulator; frozen Coverage is the published shape."""

  entries: int = 0
  parsed: int = 0
  refused: int = 0
  unparsed: int = 0
  attached: int = 0
  end_only: int = 0
  unanchored: int = 0
  refusals: dict[str, int] = field(default_factory=dict)

  def add(self, other: _Counts) -> None:
    self.entries += other.entries
    self.parsed += other.parsed
    self.refused += other.refused
    self.unparsed += other.unparsed
    self.attached += other.attached
    self.end_only += other.end_only
    self.unanchored += other.unanchored
    for reason, count in other.refusals.items():
      self.refusals[reason] = self.refusals.get(reason, 0) + count

  def freeze(self, pages: tuple[Coverage, ...] = ()) -> Coverage:
    return Coverage(
      entries=self.entries, parsed=self.parsed, refused=self.refused,
      unparsed=self.unparsed, attached=self.attached, end_only=self.end_only,
      unanchored=self.unanchored,
      # sorted so the artifact is byte-deterministic (I12): dict order
      # follows insertion, which follows page order, which a page filter
      # would change
      refusals=tuple(sorted(self.refusals.items(), key=lambda kv: (-kv[1], kv[0]))),
      pages=pages,
    )


def coverage(doc: Document, registry: Registry | None = None) -> Coverage:
  """Measure one document's apparatus coverage.

  ``attached`` mirrors the predicate ``tei._collect_page_apparatus`` uses to
  mint a start anchor, because the report must describe the TEI that is
  actually emitted; ``test_outputs`` locks the two together by counting
  ``<app>/@from`` in the emitted file.
  """
  pages: list[Coverage] = []
  total = _Counts()
  for page in doc.pages:
    counts = _Counts()
    for block in page.blocks:
      if block.layer is not Layer.APPARATUS:
        continue
      for entry in block.entries or []:
        counts.entries += 1
        parsed = resolve_parsed(entry, registry)
        if parsed is not None:
          counts.parsed += 1
        else:
          reason = ""
          if entry.override_action == "verbatim":
            reason = HUMAN_VERBATIM
          elif entry.refusal_evidence:
            reason = _refusal_key(entry.refusal_evidence)
          if reason:
            counts.refused += 1
            counts.refusals[reason] = counts.refusals.get(reason, 0) + 1
          else:
            counts.unparsed += 1

        anchor = entry.anchor
        if (anchor is None or anchor.block_index is None
            or anchor.char_offset is None):
          counts.unanchored += 1
          continue
        digit_start = (anchor.digit_start if anchor.digit_start is not None
                       else anchor.char_offset)
        start = (
          locate_lemma_start(parsed.lemma,
                             page.blocks[anchor.block_index].text,
                             anchor.char_offset)
          if parsed is not None else None
        )
        if start is not None and start < digit_start:
          counts.attached += 1
        else:
          counts.end_only += 1
    pages.append(counts.freeze())
    total.add(counts)
  return total.freeze(pages=tuple(pages))


class MarkerDelimiterError(ValueError):
  """Source text contains ⟦ or ⟧ (I4): the file would be ambiguous."""


def _escape_body(text: str, counter: list[int]) -> str:
  out: list[str] = []
  for line in text.split("\n"):
    if _STRUCTURAL.match(line):
      counter[0] += 1
      line = "\\" + line
    out.append(line)
  return "\n".join(out)


def _marker(folio: str, n: str, resolved: bool) -> str:
  return f"⟦{folio}:{n}⟧" if resolved else f"⟦{folio}:{n}?⟧"


def _line_unwrap_source(text: str) -> str:
  """md-ce keeps one apparatus entry per line; only source line breaks are
  unwrapped to U+0020. All source tokens, including hyphens, remain intact."""
  return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")


def to_markdown(doc: Document, title: str | None = None,
                tei_name: str = "", cov: Coverage | None = None) -> str:
  """Render the md-ce view.

  ``cov`` MUST be the :func:`coverage` of the same document measured with
  the SAME registry the TEI was emitted with — the parsed/attached counters
  describe the model, not the view, so they cannot be recomputed here. The
  CLI passes the one it prints; omitting it measures registry-less, which
  understates parsing for any document that was anchored with a conspectus.
  """
  if cov is None:
    cov = coverage(doc)
  if len(cov.pages) != len(doc.pages):
    raise ValueError(
      f"coverage describes {len(cov.pages)} page(s) but the document has "
      f"{len(doc.pages)}: the report would not be recomputable (I11)")

  pages_out: list[str] = []
  escaped = [0]
  generative_blocks = 0
  first_index = doc.pages[0].index if doc.pages else 0
  last_index = doc.pages[-1].index if doc.pages else 0

  for page, page_cov in zip(doc.pages, cov.pages, strict=True):
    folio = page.printed_page or "–"
    n_markers = sum(
      len(find_markers(b.text)) for b in page.blocks
      if b.layer in (Layer.TEXT, Layer.HEADING)
    )
    entries = [e for b in page.blocks if b.layer is Layer.APPARATUS
               for e in (b.entries or [])]

    lines: list[str] = []
    lines.append("")
    lines.append(
      f"## page {folio} (file index {page.index})"
      f" [markers={n_markers} entries={page_cov.entries}"
      f" unresolved={page_cov.unanchored}]"
    )
    # the full per-page report on its own structural line: the page header
    # keeps md-ce/0.2's three fields (consumers parse it with a $-anchored
    # regex), and I11's recomputability needs every counter per page
    lines.append(f"<!-- md-ce page: {page_cov.report} -->")
    for bi, block in enumerate(page.blocks):
      if block.layer in _FURNITURE:
        continue
      if "⟦" in block.text or "⟧" in block.text:
        raise MarkerDelimiterError(
          f"page {page.index}: source text contains the marker delimiter "
          "⟦/⟧ — refusing to emit an ambiguous md-ce file (I4)"
        )
      if block.generative:
        generative_blocks += 1
      meta = (
        f"[source={block.source.value} generative={str(block.generative).lower()} "
        f"confidence={block.confidence:.2f} block={bi}]"
      )
      lines.append("")
      lines.append(f"### {_LAYER_TITLES[block.layer]} {meta}")
      if block.inline_refs:
        lines.append(f"*refs: {', '.join(block.inline_refs)}*")
      lines.append("")
      if block.layer is Layer.APPARATUS and block.entries:
        for e in block.entries:
          if e.anchor is not None and e.anchor.kind == "marker":
            resolved = e.anchor.block_index is not None
            prefix = _marker(folio, e.anchor.value, resolved) + " "
          else:
            prefix = ""  # verse-referenced: the reference is in the raw
          lines.append(prefix + _escape_body(
            _line_unwrap_source(e.source_slice), escaped))
      elif block.layer in (Layer.TEXT, Layer.HEADING):
        text = block.text
        # Rewrite markers from the page's RESOLVED anchors — the single
        # source of truth. Re-scanning find_markers here (the pre-v0.2.1
        # behaviour) saw only glued markers and missed lemma-confirmed
        # detached ones, so the apparatus showed a resolved ⟦f:n⟧ with no
        # counterpart in the text: a real I3 violation. Digits without a
        # resolved entry stay verbatim (I3: an unresolved entry has ZERO
        # ⟦f:n⟧ in the text).
        spans = sorted(
          (e.anchor.digit_start, e.anchor.digit_end, e.anchor.value)
          for e in entries
          if e.anchor is not None and e.anchor.kind == "marker"
          and e.anchor.block_index == bi
          and e.anchor.digit_start is not None and e.anchor.digit_end is not None
        )
        pos = 0
        parts: list[str] = []
        for ds, de, n in spans:
          if ds < pos:
            continue
          parts.append(text[pos:ds])
          parts.append(_marker(folio, n, True))
          pos = de
        parts.append(text[pos:])
        lines.append(_escape_body("".join(parts), escaped))
      else:
        lines.append(_escape_body(block.text, escaped))
    pages_out.append("\n".join(lines))

  header = f"# {title or doc.source_name}"
  report, refusals = cov.lines
  meta = (
    f"<!-- md-ce/{MD_CE_VERSION} · diorthosis {__version__} · "
    f"ingest: {doc.ingest} · pages: {first_index}-{last_index} · "
    f"{report} · {refusals} · "
    f"generative-blocks: {generative_blocks} · "
    f"escaped-lines: {escaped[0]} · tei: {tei_name} -->"
  )
  return "\n".join([header, "", meta, *pages_out]).rstrip() + "\n"


__all__ = ["Coverage", "MarkerDelimiterError", "MD_CE_VERSION", "coverage",
           "to_markdown"]
