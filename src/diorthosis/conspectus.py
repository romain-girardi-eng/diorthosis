"""Conspectus siglorum parsing — the witness registry, for free.

Every critical edition opens with a list that DECLARES its apparatus
vocabulary: manuscript sigla (``A = Parisinus graecus 450, a. D. 1362``),
editors (``Marc. = Marcovich``) and abbreviations. Parsing that one page
gives the ``@wit``/``@resp`` registry the TEI needs — no guessing, the
edition itself is the authority.

The parser is deliberately narrow: it consumes ``token = description`` lines
and classifies the token by shape. Sigla are short (a capital, optionally a
corrector digit: ``A1``); editors are capitalized abbreviations, usually
dotted. Anything else is ignored rather than misfiled.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

# "A = Parisinus graecus 450" / "Marc. = Marcovich" / "A1, B1 = A, B prima manu"
_DECL = re.compile(r"^\s*([A-Z][A-Za-z0-9., ]{0,12}?)\s*=\s*(.+?)\s*$")
_SIGLUM = re.compile(r"^[A-Z][0-9]?$")
_EDITOR = re.compile(r"^[A-Z][a-z]+\.?$")


@dataclass
class Registry:
  """The apparatus vocabulary declared by the edition itself."""

  witnesses: dict[str, str] = field(default_factory=dict)
  """siglum -> description (e.g. 'A' -> 'Parisinus graecus 450, a. D. 1362')."""
  editors: dict[str, str] = field(default_factory=dict)
  """abbreviation -> full name (e.g. 'Marc.' -> 'Marcovich')."""

  def is_witness(self, token: str) -> bool:
    return token in self.witnesses

  def is_editor(self, token: str) -> bool:
    return token in self.editors or token.rstrip(",") in self.editors

  def xml_id(self, token: str) -> str:
    """A stable xml:id for a siglum or editor abbreviation."""
    return re.sub(r"[^A-Za-z0-9]", "", token)


@lru_cache(maxsize=1)
def builtin_editors() -> dict[str, str]:
  """abbreviation-or-surname -> canonical surname, from the curated registry
  of the major editors of classical and patristic texts. Fallback vocabulary
  only: an edition's own conspectus always takes precedence."""
  with resources.files("diorthosis.data").joinpath("editors.json").open(encoding="utf-8") as f:
    data = json.load(f)
  out: dict[str, str] = {}
  for surname, abbrevs in data["editors"].items():
    out[surname] = surname
    for a in abbrevs:
      out[a] = surname
  return out


def with_builtin_editors(reg: Registry) -> Registry:
  """The edition's declared vocabulary, extended with the built-in registry.
  Declared entries win on collision."""
  merged = dict(builtin_editors())
  merged.update(reg.editors)
  reg.editors = merged
  return reg


def parse_conspectus(text: str) -> Registry:
  reg = Registry()
  for raw_line in text.splitlines():
    m = _DECL.match(raw_line)
    if not m:
      continue
    tokens, description = m.group(1), m.group(2)
    # "A1, B1 = A, B prima manu" declares several sigla at once
    for tok in (t.strip() for t in tokens.split(",")):
      if not tok:
        continue
      if _SIGLUM.match(tok):
        reg.witnesses[tok] = description
      elif _EDITOR.match(tok):
        reg.editors[tok] = description
      # anything else: not part of the apparatus vocabulary — skip, never guess
  return reg


def find_conspectus_pages(pdf_path: str, search_range: range) -> str:
  """Return the raw text of the page(s) declaring sigla and abbreviations.

  Located by their own heading (SIGLES / sigla / conspectus / abréviations),
  the one page-level convention that is universal across series.
  """
  from pdfminer.high_level import extract_text

  head = re.compile(r"sigl|conspectus|abr[eé]viations", re.I)
  for page in search_range:
    text = extract_text(pdf_path, page_numbers=[page]) or ""
    if head.search(text.split("\n", 3)[0] if text else "") or (
      head.search(text[:200]) and "=" in text
    ):
      return text
  return ""
