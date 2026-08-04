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
# the optional second lowercase letter is a superscript distinguisher in
# print (Nᵘ = "Nu"); a lone lowercase letter declares an early edition
# ("m", "v" in the Problemata tradition)
_SIGLUM = re.compile(r"^[A-Za-zΑ-Ωα-ωϘ-ϡ][a-z]?[0-9]?\*?$")
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


# The LDLT/DLL bracket format: "[ω] Common source of …", "[Mc] Corrections
# by the original scribe…", "[Hoffmann 1890] E. Hoffmann, ed. …". Witness
# sigla are short (letter + optional hand-state suffix ac/c/mr/*, Greek
# family letters); bracketed editors are capitalized names, their year
# disambiguator stripped for the printed-band token.
_BRACKET_DECL = re.compile(r"^\s*\[([^\]\n]{1,24})\]\s+(\S.*)$")
_BRACKET_WITNESS = re.compile(r"^[A-ZΑ-Ωα-ωϘ-ϡ](?:ac|c|mr)?\*?[0-9]?$")
# ﬀ-ﬆ — the fi/fl/ff ligatures a born-digital text layer keeps
# ("Wölfﬂin", "Ciafﬁ-Griffa"); the registry stores them verbatim so the
# apparatus band, which carries the same ligatures, matches exactly
_BRACKET_EDITOR = re.compile(
  r"^([A-ZÀ-ÞĀ-Ž][A-Za-zà-öø-ÿā-žÀ-ÞĀ-Ž.'ﬀ-ﬆ-]+)"
  r"(?:\s+\d{4}[a-z]?)?$")

_BRACKET_INITIAL = re.compile(
  r"^([A-ZÀ-ÞĀ-Ž])\.\s+([A-ZÀ-ÞĀ-Ž][A-Za-zà-öø-ÿā-žﬀ-ﬆ'-]+)$")

_BRACKET_MULTI = re.compile(
  r"^([A-ZÀ-ÞĀ-Ž][A-Za-zà-öø-ÿā-žﬀ-ﬆ.'-]*"
  r"(?:\s+[A-ZÀ-ÞĀ-Ž][A-Za-zà-öø-ÿā-žﬀ-ﬆ.'-]+)+)"
  r"(?:\s+\d{4}[a-z]?)?$")


def parse_conspectus(text: str) -> Registry:
  reg = Registry()
  for raw_line in text.splitlines():
    m = _DECL.match(raw_line)
    if m:
      tokens, description = m.group(1), m.group(2)
      # "A1, B1 = A, B prima manu" declares several sigla at once
      for tok in (t.strip() for t in tokens.split(",")):
        if not tok:
          continue
        if _SIGLUM.match(tok):
          reg.witnesses[tok] = description
        elif _EDITOR.match(tok):
          reg.editors[tok] = description
      continue
    b = _BRACKET_DECL.match(raw_line)
    if b:
      tok, description = b.group(1).strip(), b.group(2)
      if _BRACKET_WITNESS.match(tok):
        reg.witnesses[tok] = description
      else:
        e = _BRACKET_EDITOR.match(tok)
        if e:
          reg.editors[e.group(1)] = description
        else:
          # an editor declared with an initial ("D. Simons") — the
          # apparatus prints the name GLUED ("DSimons"): register both
          i = _BRACKET_INITIAL.match(tok)
          mw = _BRACKET_MULTI.match(tok)
          if i:
            reg.editors[f"{i.group(1)}. {i.group(2)}"] = description
            reg.editors[f"{i.group(1)}{i.group(2)}"] = description
          elif mw:
            # a multi-word surname ("Du Pontet"): the spaced form for
            # the line grammar's pre-pass, the glued form for peeling
            name = mw.group(1)
            reg.editors[name] = description
            reg.editors[name.replace(" ", "")] = description
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

  head = re.compile(r"sigl|conspectus|abr[eé]viations|manuscripts", re.I)
  explicit = isinstance(search_range, list) and len(search_range) == 1
  for page in search_range:
    text = extract_text(pdf_path, page_numbers=[page]) or ""
    if head.search(text.split("\n", 3)[0] if text else "") or (
      head.search(text[:200]) and ("=" in text or "[" in text)
    ):
      # a sigla list runs over several pages; bracket-format bibliographies
      # (DLL) run over MANY — with an explicitly given page the caller
      # vouches for the region, so the window widens
      horizon = 40 if explicit else 8
      for cont in range(page + 1, page + 1 + horizon):
        more = extract_text(pdf_path, page_numbers=[cont]) or ""
        lines = [ln for ln in more.splitlines() if ln.strip()]
        if not lines:
          break
        decls = sum(1 for ln in lines
                    if _DECL.match(ln) or _BRACKET_DECL.match(ln))
        if decls < max(2, 0.5 * len(lines)) and not (
            explicit and decls >= 2):
          break
        text += "\n" + more
      return text
  return ""
