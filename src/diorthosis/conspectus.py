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
# Sigla in the wild also include Greek letters for hyparchetypes and families
# (π = common source of T and V; ω = the archetype), archaic Greek numerals
# (ϛ = the consensus of the editiones ueteres in Caesarian editions), and
# starred/numbered states of a witness (M*, M2) — all standard conventions.
_TOKEN_CHR = "A-Za-zÀ-ÖØ-öø-ÿĀ-ŽΑ-Ωα-ωϘ-ϡ"
_DECL = re.compile(
  r"^\s*([" + _TOKEN_CHR + r"][" + _TOKEN_CHR + r"0-9*.,\- ]{0,24}?)\s*=\s*(.+?)\s*$")
_SIGLUM = re.compile(r"^[A-ZΑ-Ωα-ωϘ-ϡ][0-9]?\*?$")
# editor names include compounds (Gaertner-Hausburg) and disambiguating
# initials written solid (DSimons, JSimons)
_EDITOR = re.compile(r"^[A-ZÀ-ÞĀ-Ž][A-Za-zà-öø-ÿā-žÀ-ÞĀ-Ž-]+\.?$")


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
    """A stable, INJECTIVE xml:id fragment for a siglum or editor token.

    ASCII alphanumerics pass through; every other character becomes
    ``u<hex>`` so distinct tokens can never collide (stripping once mapped
    both π and ω to the empty string, folding M* into M — duplicate
    xml:ids that made the TEI unparseable). Hex-escaping is applied to ALL
    non-ASCII because libxml2 validates NCNames against the old XML 1.0
    4th-edition letter table, which lacks characters like ϛ (stigma).
    """
    return "".join(
      c if c.isascii() and c.isalnum() else f"u{ord(c):x}" for c in token
    )


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


def bootstrap_registry(
  pdf_path: str, conspectus_page: int | None = None,
) -> tuple[Registry, str]:
  """The one way to build a registry from a PDF, shared by the CLI (build
  and inspect) and the evaluation harness — the edition's own conspectus,
  extended with the built-in editors.

  Returns ``(registry, note)`` where ``note`` says what was found: a summary
  when the conspectus was located, an empty string when it was not (the
  caller decides how loudly to warn).
  """
  registry = Registry()
  rng = ([conspectus_page] if conspectus_page is not None else range(0, 200))
  text = find_conspectus_pages(pdf_path, rng)
  note = ""
  if text:
    registry = parse_conspectus(text)
    note = (f"conspectus: {len(registry.witnesses)} witnesses, "
            f"{len(registry.editors)} editors declared")
  return with_builtin_editors(registry), note


def find_conspectus_pages(pdf_path: str, search_range: range | list[int]) -> str:
  """Return the raw text of the page(s) declaring sigla and abbreviations.

  Located by their own heading (SIGLES / sigla / conspectus / abréviations),
  the one page-level convention that is universal across series. A sigla
  list often runs over SEVERAL pages: once the opening page is found, the
  following pages are appended for as long as a majority of their non-empty
  lines are still ``token = description`` declarations.
  """
  from pdfminer.high_level import extract_text

  head = re.compile(r"sigl|conspectus|abr[eé]viations", re.I)
  for page in search_range:
    text = extract_text(pdf_path, page_numbers=[page]) or ""
    if head.search(text.split("\n", 3)[0] if text else "") or (
      head.search(text[:200]) and "=" in text
    ):
      for cont in range(page + 1, page + 9):
        more = extract_text(pdf_path, page_numbers=[cont]) or ""
        lines = [ln for ln in more.splitlines() if ln.strip()]
        if not lines:
          break
        decls = sum(1 for ln in lines if _DECL.match(ln))
        if decls < 0.5 * len(lines):
          break
        text += "\n" + more
      return text
  return ""
