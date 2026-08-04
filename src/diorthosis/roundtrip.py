"""Mechanical equivalence checks for md-ce and TEI outputs."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .tei import TEI_NS

_NS = {"tei": TEI_NS}
_XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
_TEI = f"{{{TEI_NS}}}"

_PAGE = re.compile(
  r"^## page (?P<folio>\S+) \(file index (?P<index>\d+)\)"
  r" \[markers=\d+ entries=\d+ unresolved=\d+\]$"
)
_SECTION = re.compile(r"^### (?P<layer>\S+)(?:\s|$)")
_MARKER = re.compile(r"⟦[^⟦⟧]+⟧")
_APPARATUS_MARKER = re.compile(r"^⟦[^⟦⟧]+⟧[ \t]+")
_REFS = re.compile(r"^\*refs: .+\*$")
_ESCAPED_STRUCTURAL = re.compile(r"^\\(?=#{1,6} |<!-- md-ce)")
_PAGE_ID = re.compile(r"^page-(?P<index>\d+)$")


@dataclass
class _MdSection:
  layer: str
  body: list[str] = field(default_factory=list)


@dataclass
class _MdPage:
  folio: str
  index: int
  sections: list[_MdSection] = field(default_factory=list)


@dataclass
class _TeiPage:
  folio: str
  index: int | None
  children: list[ET.Element] = field(default_factory=list)
  translations: list[str] = field(default_factory=list)


def _normalise(text: str) -> str:
  return " ".join(text.split())


def _preview(text: str, limit: int = 120) -> str:
  if len(text) <= limit:
    return text
  return text[: limit - 1] + "…"


def _parse_markdown(content: str) -> tuple[list[_MdPage], list[str]]:
  pages: list[_MdPage] = []
  violations: list[str] = []
  current_page: _MdPage | None = None
  current_section: _MdSection | None = None

  for line_number, line in enumerate(content.split("\n"), start=1):
    if line.startswith("## "):
      match = _PAGE.fullmatch(line)
      current_section = None
      if match is None:
        violations.append(
          f"md-ce line {line_number}: page header is not parseable: {line!r}"
        )
        current_page = None
        continue
      current_page = _MdPage(
        folio=match.group("folio"),
        index=int(match.group("index")),
      )
      pages.append(current_page)
      continue

    if line.startswith("### "):
      match = _SECTION.match(line)
      if match is None or current_page is None:
        violations.append(
          f"md-ce line {line_number}: section header is outside a page"
        )
        current_section = None
        continue
      current_section = _MdSection(layer=match.group("layer"))
      current_page.sections.append(current_section)
      continue

    if current_section is not None:
      current_section.body.append(line)

  return pages, violations


def _section_lines(section: _MdSection) -> list[str]:
  lines = list(section.body)
  if lines and _REFS.fullmatch(lines[0]):
    lines.pop(0)
  while lines and not lines[0].strip():
    lines.pop(0)
  while lines and not lines[-1].strip():
    lines.pop()
  return [_ESCAPED_STRUCTURAL.sub("", line, count=1) for line in lines]


def _markdown_layer_text(page: _MdPage, layer: str) -> str:
  blocks = ["\n".join(_section_lines(section))
            for section in page.sections if section.layer == layer]
  return _normalise(" ".join(blocks))


def _markdown_text(page: _MdPage) -> str:
  return _normalise(_MARKER.sub("", _markdown_layer_text(page, "text")))


def _markdown_apparatus(page: _MdPage) -> Counter[str]:
  entries: list[str] = []
  for section in page.sections:
    if section.layer != "apparatus":
      continue
    for line in _section_lines(section):
      if not line.strip():
        continue
      raw = _APPARATUS_MARKER.sub("", line, count=1)
      entries.append(_normalise(raw))
  return Counter(entries)


def _element_text_without_anchors(element: ET.Element) -> str:
  parts = [element.text or ""]
  for child in element:
    if child.tag != f"{_TEI}anchor":
      parts.append(_element_text_without_anchors(child))
    parts.append(child.tail or "")
  return "".join(parts)


def _parse_tei(path: str | Path) -> tuple[list[_TeiPage], list[str]]:
  violations: list[str] = []
  try:
    root = ET.parse(path).getroot()
  except ET.ParseError as exc:
    return [], [f"TEI is not well-formed XML: {exc}"]

  body = root.find("./tei:text/tei:body", _NS)
  edition = None if body is None else body.find("./tei:div[@type='edition']", _NS)
  if edition is None:
    return [], ["TEI has no text/body/div[@type='edition']"]

  pages: list[_TeiPage] = []
  current_page: _TeiPage | None = None
  for child in edition:
    if child.tag == f"{_TEI}pb":
      xml_id = child.get(_XML_ID, "")
      match = _PAGE_ID.fullmatch(xml_id)
      index = int(match.group("index")) if match is not None else None
      if index is None:
        violations.append(
          f"TEI page {child.get('n') or '–'}: xml:id {xml_id!r} is not page-I"
        )
      current_page = _TeiPage(
        folio=child.get("n") or "–",
        index=index,
      )
      pages.append(current_page)
    elif current_page is not None:
      current_page.children.append(child)

  translations = body.findall("./tei:div[@type='translation']/tei:p", _NS)
  for paragraph in translations:
    folio = paragraph.get("n") or "–"
    candidates = [page for page in pages if page.folio == folio]
    if len(candidates) != 1:
      reason = "no page has that folio" if not candidates else "folio is not unique"
      violations.append(
        f"TEI translation for folio {folio}: cannot assign it to a page ({reason})"
      )
      continue
    candidates[0].translations.append("".join(paragraph.itertext()))

  return pages, violations


def _tei_text(page: _TeiPage) -> str:
  blocks = [
    _element_text_without_anchors(child)
    for child in page.children
    if child.tag == f"{_TEI}ab" and child.get("type") is None
  ]
  return _normalise(" ".join(blocks))


def _tei_apparatus(page: _TeiPage, violations: list[str]) -> Counter[str]:
  entries: list[str] = []
  app_number = 0
  for child in page.children:
    if child.tag == f"{_TEI}app":
      app_number += 1
      notes = child.findall("./tei:note[@type='verbatim']", _NS)
      if len(notes) != 1:
        violations.append(
          f"TEI page {page.folio}: app {app_number} has {len(notes)} "
          "note[@type='verbatim'] elements, expected 1"
        )
      entries.extend(_normalise("".join(note.itertext())) for note in notes)
    elif child.tag == f"{_TEI}note" and child.get("type") == "apparatus":
      entries.append(_normalise("".join(child.itertext())))
  return Counter(entries)


def _tei_layer_text(page: _TeiPage, layer: str) -> str:
  if layer == "translation":
    return _normalise(" ".join(page.translations))
  notes = [
    "".join(child.itertext())
    for child in page.children
    if child.tag == f"{_TEI}note" and child.get("type") == "editorial"
  ]
  return _normalise(" ".join(notes))


def _compare_text_layer(
  page_label: str,
  layer: str,
  markdown: str,
  tei: str,
  violations: list[str],
) -> None:
  if markdown == tei:
    return
  violations.append(
    f"page {page_label}: {layer} differs "
    f"(md-ce={_preview(markdown)!r}; TEI={_preview(tei)!r})"
  )


def _compare_apparatus(
  page_label: str,
  markdown: Counter[str],
  tei: Counter[str],
  violations: list[str],
) -> None:
  for entry, count in (tei - markdown).items():
    violations.append(
      f"page {page_label}: apparatus entry present only in TEI "
      f"({count} occurrence(s)): {_preview(entry)!r}"
    )
  for entry, count in (markdown - tei).items():
    violations.append(
      f"page {page_label}: apparatus entry present only in md-ce "
      f"({count} occurrence(s)): {_preview(entry)!r}"
    )


def check_roundtrip(md_path: str | Path, tei_path: str | Path) -> list[str]:
  """Return violations when md-ce and TEI do not carry equivalent content."""
  markdown = Path(md_path).read_text(encoding="utf-8")
  md_pages, violations = _parse_markdown(markdown)
  tei_pages, tei_violations = _parse_tei(tei_path)
  violations.extend(tei_violations)

  md_folios = [page.folio for page in md_pages]
  tei_folios = [page.folio for page in tei_pages]
  if md_folios != tei_folios:
    violations.append(
      f"page folios differ: md-ce has {md_folios!r}; TEI has {tei_folios!r}"
    )

  md_indices = [page.index for page in md_pages]
  tei_indices = [page.index for page in tei_pages]
  if md_indices != tei_indices:
    violations.append(
      f"page file indices differ: md-ce has {md_indices!r}; TEI has {tei_indices!r}"
    )

  for md_page, tei_page in zip(md_pages, tei_pages, strict=False):
    label = f"{md_page.folio} (file index {md_page.index})"
    _compare_text_layer(
      label, "text", _markdown_text(md_page), _tei_text(tei_page), violations
    )
    _compare_apparatus(
      label,
      _markdown_apparatus(md_page),
      _tei_apparatus(tei_page, violations),
      violations,
    )
    for layer in ("translation", "notes"):
      _compare_text_layer(
        label,
        layer,
        _markdown_layer_text(md_page, layer),
        _tei_layer_text(tei_page, layer),
        violations,
      )

  return violations


__all__ = ["check_roundtrip"]
