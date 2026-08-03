"""md-ce/0.2 validation — the spec, executable.

SPEC.md promises that every invariant is mechanically checkable; this module
is that promise kept. It parses a md-ce file the way the grammar says a
consumer may (pages on ``^## page ``, sections on ``^### `` WITHIN a page —
splitting on ``^### `` alone across the whole file once produced hundreds of
false positives) and checks every invariant that is decidable from the file
alone:

- **I1** unescaped structural lines / ``escaped-lines`` count;
- **I2** no section contains another header (a corollary of I1 + I5: every
  ``#``-line is either the title, a page header, a section header, or
  escaped — anything else is reported);
- **I3** marker scope and coverage: every resolved apparatus marker ⟦f:n⟧
  has exactly one counterpart in a text/heading block of page f; an
  unresolved ⟦f:n?⟧ has zero; markers never cross pages;
- **I4** delimiter purity: ⟦/⟧ appear only as well-formed markers, and only
  where markers may live (apparatus line prefix; text/heading bodies);
- **I5** metadata parseability of every section header;
- **I6** (folio, block) addressability;
- **I7** page ordering (strictly increasing file index, folios unique);
- **I10** ``generative-blocks`` equals the count of generative headers;
- **I11** ``anchored: a/b`` recomputable from the per-page stats, and the
  per-page stats recomputable from the apparatus bodies themselves;
- **I12** NFC normalization, LF line endings, trailing newline.

``markers=`` in the page stats counts the *printed* glued superscripts of
the source document; it is not recomputable from the view and is therefore
not checked (I9: the md is deliberately lossy).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

MD_CE_SUPPORTED = "0.2"

_TITLE = re.compile(r"^# \S")
_META = re.compile(
  r"^<!-- md-ce/(?P<ver>[0-9.]+) · diorthosis (?P<tool>\S+) · "
  r"ingest: (?P<ingest>\S+) · pages: (?P<first>\d+)-(?P<last>\d+) · "
  r"anchored: (?P<a>\d+)/(?P<b>\d+) · "
  r"generative-blocks: (?P<gen>\d+) · "
  r"escaped-lines: (?P<esc>\d+) · tei: (?P<tei>[^>]*?) -->$"
)
_PAGE = re.compile(
  r"^## page (?P<folio>\S+) \(file index (?P<index>\d+)\)"
  r" \[markers=(?P<markers>\d+) entries=(?P<entries>\d+)"
  r" unresolved=(?P<unres>\d+)\]$"
)
_SECTION = re.compile(
  r"^### (?P<layer>text|apparatus|translation|notes|heading|unclassified) "
  r"\[source=(?P<source>born_digital|ocr) generative=(?P<gen>true|false) "
  r"confidence=(?P<conf>\d\.\d{2}) block=(?P<block>\d+)\]$"
)
_MARKER = re.compile(r"⟦(?P<folio>[^:⟦⟧]+):(?P<n>\d{1,3})(?P<q>\?)?⟧")
_ESCAPED = re.compile(r"^\\(#{1,6} |<!-- md-ce)")
_STRUCTURAL = re.compile(r"^(#{1,6} |<!-- md-ce)")


@dataclass
class Violation:
  invariant: str
  line: int
  """1-based line number; 0 for file-level findings."""
  message: str

  def __str__(self) -> str:
    where = f"line {self.line}" if self.line else "file"
    return f"[{self.invariant}] {where}: {self.message}"


@dataclass
class _Section:
  header_line: int
  layer: str
  generative: bool
  block: int
  body: list[tuple[int, str]] = field(default_factory=list)
  """(1-based line number, line) pairs."""


@dataclass
class _PageRec:
  header_line: int
  folio: str
  index: int
  entries: int
  unresolved: int
  sections: list[_Section] = field(default_factory=list)


def validate_text(content: str) -> list[Violation]:
  out: list[Violation] = []

  # -- I12: byte discipline ------------------------------------------------
  if "\r" in content:
    out.append(Violation("I12", 0, "CR found: line endings must be LF"))
  if content != unicodedata.normalize("NFC", content):
    out.append(Violation("I12", 0, "content is not NFC-normalized"))
  if content and not content.endswith("\n"):
    out.append(Violation("I12", 0, "missing trailing newline"))

  lines = content.split("\n")

  # -- structure: title, meta, pages, sections -----------------------------
  if not lines or not _TITLE.match(lines[0]):
    out.append(Violation("grammar", 1, "first line is not a '# title'"))

  meta = None
  meta_line = 0
  pages: list[_PageRec] = []
  current_page: _PageRec | None = None
  current_section: _Section | None = None

  for i, line in enumerate(lines):
    ln = i + 1
    if ln == 1 and _TITLE.match(line):
      continue
    if line.startswith("<!-- md-ce"):
      m = _META.match(line)
      if m is None:
        out.append(Violation("grammar", ln, "meta comment does not match the grammar"))
      elif meta is not None:
        out.append(Violation("grammar", ln, "duplicate meta comment"))
      else:
        meta, meta_line = m, ln
      continue
    if line.startswith("## "):
      m = _PAGE.match(line)
      if m is None:
        out.append(Violation("grammar", ln, "'## ' line is not a valid page header"))
        continue
      current_page = _PageRec(
        header_line=ln, folio=m.group("folio"), index=int(m.group("index")),
        entries=int(m.group("entries")), unresolved=int(m.group("unres")),
      )
      pages.append(current_page)
      current_section = None
      continue
    if line.startswith("### "):
      m = _SECTION.match(line)
      if m is None:
        out.append(Violation("I5", ln, f"section header not parseable: {line[:80]!r}"))
        continue
      if current_page is None:
        out.append(Violation("grammar", ln, "section header before any page header"))
        continue
      current_section = _Section(
        header_line=ln, layer=m.group("layer"),
        generative=m.group("gen") == "true", block=int(m.group("block")),
      )
      current_page.sections.append(current_section)
      continue
    if _STRUCTURAL.match(line):
      # any other structural-looking line is an unescaped body line (I1);
      # it is also what would break the I2 no-lookahead splitting promise
      out.append(Violation("I1", ln, f"unescaped structural line: {line[:80]!r}"))
      continue
    if current_section is not None:
      current_section.body.append((ln, line))

  if meta is None:
    out.append(Violation("grammar", 0, "no md-ce meta comment found"))
    return out
  if meta.group("ver") != MD_CE_SUPPORTED:
    out.append(Violation(
      "grammar", meta_line,
      f"md-ce/{meta.group('ver')} file; this validator checks md-ce/{MD_CE_SUPPORTED}"))

  # -- I7: page ordering ---------------------------------------------------
  indices = [p.index for p in pages]
  if indices != sorted(set(indices)):
    out.append(Violation("I7", 0, f"page file indices not strictly increasing: {indices}"))
  folios = [p.folio for p in pages if p.folio != "–"]
  dup_folios = sorted({f for f in folios if folios.count(f) > 1})
  for f in dup_folios:
    out.append(Violation("I7", 0, f"folio {f!r} appears more than once"))
  if pages and (int(meta.group("first")) != pages[0].index
                or int(meta.group("last")) != pages[-1].index):
    out.append(Violation(
      "I11", meta_line,
      f"meta pages {meta.group('first')}-{meta.group('last')} != actual "
      f"{pages[0].index}-{pages[-1].index}"))

  # -- I6: addressability --------------------------------------------------
  for p in pages:
    seen: dict[int, int] = {}
    for s in p.sections:
      if s.block in seen:
        out.append(Violation(
          "I6", s.header_line,
          f"page {p.folio}: block ordinal {s.block} already used at line "
          f"{seen[s.block]}"))
      seen[s.block] = s.header_line

  # -- I3 + I4: markers ----------------------------------------------------
  esc_count = 0
  gen_count = sum(1 for p in pages for s in p.sections if s.generative)
  entries_total = 0
  anchored_total = 0

  for p in pages:
    resolved: dict[str, int] = {}
    unresolved_ns: set[str] = set()
    text_markers: dict[str, int] = {}
    app_lines = 0
    app_unresolved = 0

    for s in p.sections:
      for ln, line in s.body:
        if _ESCAPED.match(line):
          esc_count += 1
        stripped = _MARKER.sub("", line)
        if "⟦" in stripped or "⟧" in stripped:
          out.append(Violation("I4", ln, "stray ⟦/⟧ not forming a marker"))
        for m in _MARKER.finditer(line):
          if m.group("folio") != p.folio:
            out.append(Violation(
              "I3", ln,
              f"marker {m.group(0)} on page {p.folio}: markers are page-scoped"))
        if s.layer == "apparatus":
          if not line.strip():
            continue
          app_lines += 1
          m = _MARKER.match(line)
          if m is None:
            app_unresolved += 1     # entry with no anchor at all
          elif m.group("q"):
            app_unresolved += 1
            unresolved_ns.add(m.group("n"))
          else:
            resolved[m.group("n")] = resolved.get(m.group("n"), 0) + 1
          for extra in list(_MARKER.finditer(line))[1 if m else 0:]:
            out.append(Violation(
              "I3", ln, f"marker {extra.group(0)} inside an apparatus entry body"))
        elif s.layer in ("text", "heading"):
          for m in _MARKER.finditer(line):
            if m.group("q"):
              out.append(Violation(
                "I3", ln, f"unresolved marker {m.group(0)} in a {s.layer} block"))
            else:
              text_markers[m.group("n")] = text_markers.get(m.group("n"), 0) + 1
        else:
          for m in _MARKER.finditer(line):
            out.append(Violation(
              "I3", ln, f"marker {m.group(0)} in a {s.layer} block"))

    for n, count in sorted(resolved.items()):
      if count != 1:
        out.append(Violation(
          "I3", p.header_line, f"page {p.folio}: duplicate apparatus marker "
          f"⟦{p.folio}:{n}⟧ ({count}×)"))
      if text_markers.get(n, 0) != count:
        out.append(Violation(
          "I3", p.header_line,
          f"page {p.folio}: resolved ⟦{p.folio}:{n}⟧ has "
          f"{text_markers.get(n, 0)} text counterpart(s), expected {count}"))
    for n in sorted(unresolved_ns):
      if text_markers.get(n, 0):
        out.append(Violation(
          "I3", p.header_line,
          f"page {p.folio}: entry ⟦{p.folio}:{n}?⟧ is unresolved but "
          f"⟦{p.folio}:{n}⟧ occurs in the text"))
    for n in sorted(set(text_markers) - set(resolved)):
      out.append(Violation(
        "I3", p.header_line,
        f"page {p.folio}: text marker ⟦{p.folio}:{n}⟧ has no resolved "
        "apparatus entry"))

    # -- I11: per-page stats recomputable from the body --------------------
    if app_lines != p.entries:
      out.append(Violation(
        "I11", p.header_line,
        f"page {p.folio}: entries={p.entries} but {app_lines} apparatus "
        "entry line(s) present"))
    if app_unresolved != p.unresolved:
      out.append(Violation(
        "I11", p.header_line,
        f"page {p.folio}: unresolved={p.unresolved} but {app_unresolved} "
        "unresolved entry line(s) present"))
    entries_total += p.entries
    anchored_total += p.entries - p.unresolved

  # -- I11 / I10 / I1: meta counters ---------------------------------------
  if (int(meta.group("a")), int(meta.group("b"))) != (anchored_total, entries_total):
    out.append(Violation(
      "I11", meta_line,
      f"meta anchored {meta.group('a')}/{meta.group('b')} != recomputed "
      f"{anchored_total}/{entries_total}"))
  if int(meta.group("gen")) != gen_count:
    out.append(Violation(
      "I10", meta_line,
      f"meta generative-blocks {meta.group('gen')} != {gen_count} generative "
      "header(s)"))
  if int(meta.group("esc")) != esc_count:
    out.append(Violation(
      "I1", meta_line,
      f"meta escaped-lines {meta.group('esc')} != {esc_count} escaped "
      "line(s) found"))

  out.sort(key=lambda v: (v.line, v.invariant))
  return out


def validate_file(path: str | Path) -> list[Violation]:
  return validate_text(Path(path).read_text(encoding="utf-8"))


__all__ = ["Violation", "validate_text", "validate_file", "MD_CE_SUPPORTED"]
