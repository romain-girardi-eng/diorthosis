#!/usr/bin/env python3
"""Compare a diorthosis TEI against a scholar-derived golden — 0 errors or fail.

The bar is asymmetric, matching the tool's honesty contract:

- **ERRORS** (any one fails the run): structure that is WRONG — a phantom
  entry, a wrong lemma, a wrong/missing reading, a wrong witness or editor,
  an anchor placed where the golden lemma does not end, an altered verbatim,
  an unresolved IDREF, a duplicated token inside @wit/@source.
- **GAPS** (reported, never fatal): structure that is MISSING but honest —
  an entry kept as a verbatim <note type="apparatus"> instead of a parsed
  <app>, an entry left unanchored. A refusal is not an error; a wrong claim
  is.

Usage: check_golden.py golden.json output.tei.xml [--rng tei_all.rng]
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def fold(s: str) -> str:
  s = re.sub(r"(?<=\S)-\s+", "", s)      # printed line-break hyphenation
  s = s.replace("—", " ").replace("–", " ")
  d = unicodedata.normalize("NFD", s)
  out = "".join(c for c in d if not unicodedata.combining(c)).lower()
  return re.sub(r"\s+", " ", out.replace("ς", "σ")).strip()


def toks(s: str) -> list[str]:
  return [w.strip(".,·;:!»«()[]") for w in fold(s).split() if w.strip(".,·;:!»«()[]")]


@dataclass
class Finding:
  kind: str      # ERROR_* | GAP_*
  page: str
  n: str
  detail: str

  @property
  def fatal(self) -> bool:
    return self.kind.startswith("ERROR")


@dataclass
class PageOut:
  """What diorthosis emitted for one printed page."""
  printed: str
  ab_stream: list[tuple[str, str | None]] = field(default_factory=list)
  """(text-chunk, anchor-id-after-it) pairs, in order, across the page's abs."""
  apps: list[ET.Element] = field(default_factory=list)
  notes: list[ET.Element] = field(default_factory=list)


def _q(tag: str) -> str:
  return f"{{{TEI_NS}}}{tag}"


def parse_tei(path: Path) -> tuple[dict[str, PageOut], ET.Element]:
  root = ET.parse(path).getroot()
  edition = root.find(f".//{_q('div')}[@type='edition']")
  if edition is None:
    raise SystemExit("no <div type='edition'> in TEI")
  pages: dict[str, PageOut] = {}
  cur: PageOut | None = None
  for el in edition:
    tag = el.tag.rsplit("}", 1)[-1]
    if tag == "pb":
      cur = PageOut(printed=el.get("n") or "?")
      pages[cur.printed] = cur
    elif cur is None:
      continue
    elif tag == "ab":
      chunk = el.text or ""
      for child in el:
        if child.tag == _q("anchor"):
          cur.ab_stream.append((chunk, child.get(XML_ID)))
          chunk = child.tail or ""
        else:
          chunk += ("".join(child.itertext()) or "") + (child.tail or "")
      cur.ab_stream.append((chunk, None))
    elif tag == "app":
      cur.apps.append(el)
    elif tag == "note" and el.get("type") == "apparatus":
      cur.notes.append(el)
  return pages, root


def check_idrefs(root: ET.Element) -> list[Finding]:
  out: list[Finding] = []
  declared = {el.get(XML_ID) for el in root.iter() if el.get(XML_ID)}
  for el in root.iter():
    for attr in ("wit", "source", "from", "to", "target"):
      val = el.get(attr)
      if not val:
        continue
      refs = val.split()
      if len(refs) != len(set(refs)):
        out.append(Finding("ERROR_DUP_REF", "-", "-",
                           f"duplicated token in @{attr}: {val!r}"))
      for ref in refs:
        if not ref.startswith("#") or ref[1:] not in declared:
          out.append(Finding("ERROR_IDREF", "-", "-",
                             f"@{attr} points to undeclared {ref!r}"))
  return out


def id_maps(root: ET.Element) -> tuple[dict[str, str], dict[str, str]]:
  """xml:id -> printed token, from the emitted TEI's own declarations."""
  wit_map: dict[str, str] = {}
  ed_map: dict[str, str] = {}
  for w in root.iter(_q("witness")):
    xid = w.get(XML_ID)
    abbr = w.find(_q("abbr"))
    if xid:
      wit_map[xid] = ((abbr.text or "").strip()
                      if abbr is not None else xid.removeprefix("wit-"))
  for b in root.iter(_q("bibl")):
    xid = b.get(XML_ID)
    if xid and xid.startswith("ed-"):
      ed_map[xid] = (b.text or "").strip() or xid.removeprefix("ed-")
  return wit_map, ed_map


def _reading_sides(app: ET.Element, wit_map: dict[str, str],
                   ed_map: dict[str, str]) -> list[dict]:
  sides = []
  for tag in ("lem", "rdg"):
    for el in app.findall(_q(tag)):
      note = el.find(_q("note"))
      sides.append({
        "tag": tag,
        "text": (el.text or "").strip(),
        "wits": [wit_map.get(w.removeprefix("#"), w.removeprefix("#wit-"))
                 for w in (el.get("wit") or "").split()],
        "editors": [ed_map.get(e.removeprefix("#"), e.removeprefix("#ed-"))
                    for e in (el.get("source") or "").split()],
        "cited": (note.text or "") if note is not None else "",
      })
  return sides


def anchor_context(page: PageOut, anchor_id: str) -> str | None:
  """The folded text immediately before the anchor, or None if absent."""
  buf = ""
  for chunk, aid in page.ab_stream:
    buf += chunk
    if aid == anchor_id:
      return buf
    if aid is not None:
      buf += ""
  return None


# Attribution tokens that our grammar deliberately classifies as technical
# qualifiers, not named editors: they are preserved in the verbatim note and
# excluded from the strict editor-set comparison.
_QUALIFIER_ATTRIB = frozenset({
  "ed. pr.", "edd.", "ed.", "cett.", "codd.", "cod.", "rell.", "dett.",
  "recc.", "vett.", "vulg.", "al.",
})


def _strict_editors(tokens: list[str]) -> list[str]:
  return sorted(e.rstrip(".") for e in tokens if e not in _QUALIFIER_ATTRIB)


def compare(golden: dict, pages: dict[str, PageOut],
            wit_map: dict[str, str], ed_map: dict[str, str]) -> list[Finding]:
  out: list[Finding] = []
  for gp in golden["pages"]:
    folio = gp["printed_page"]
    page = pages.get(folio)
    if page is None:
      if gp["entries"]:
        out.append(Finding("ERROR_MISSING_PAGE", folio, "-",
                           "printed page absent from TEI"))
      continue
    emitted = len(page.apps) + len(page.notes)
    if emitted > len(gp["entries"]):
      out.append(Finding("ERROR_PHANTOM", folio, "-",
                         f"{emitted} apparatus items emitted, golden has "
                         f"{len(gp['entries'])}"))
    if emitted < len(gp["entries"]):
      out.append(Finding("ERROR_LOST", folio, "-",
                         f"{emitted} apparatus items emitted, golden has "
                         f"{len(gp['entries'])} — entries were LOST"))

    apps_by_n = {}
    for a in page.apps:
      apps_by_n.setdefault(a.get("n") or "?", []).append(a)
    notes_by_n = {}
    for nt in page.notes:
      notes_by_n.setdefault(nt.get("n") or "?", []).append(nt)

    for g in gp["entries"]:
      n = g["n"]
      app = (apps_by_n.get(n) or [None])[0]
      note = (notes_by_n.get(n) or [None])[0]
      if app is None and note is None:
        out.append(Finding("ERROR_LOST", folio, n, "entry absent from TEI"))
        continue
      if app is None:
        # honest refusal: verbatim must still be intact
        if fold(note.text or "") != fold(g["band"].split(" ", 1)[1]):
          out.append(Finding("ERROR_VERBATIM", folio, n,
                             f"note text != printed band: {note.text!r}"))
        else:
          out.append(Finding("GAP_UNPARSED", folio, n, "kept as verbatim note"))
        if note.get("target") is None:
          out.append(Finding("GAP_UNANCHORED", folio, n, "note has no target"))
        continue

      sides = _reading_sides(app, wit_map, ed_map)
      lem = next((s for s in sides if s["tag"] == "lem"), None)
      rdgs = [s for s in sides if s["tag"] == "rdg"]
      if lem is None or fold(lem["text"]) != fold(g["lemma"]):
        out.append(Finding("ERROR_LEMMA", folio, n,
                           f"lem={lem['text'] if lem else None!r} "
                           f"golden={g['lemma']!r}"))
      if lem is not None and sorted(lem["wits"]) != sorted(g["lemma_wits"]):
        out.append(Finding("ERROR_WIT", folio, n,
                           f"lem wits {lem['wits']} != {g['lemma_wits']}"))
      if len(rdgs) != len(g["readings"]):
        out.append(Finding("ERROR_READING", folio, n,
                           f"{len(rdgs)} readings != {len(g['readings'])}"))
      for rd, gr in zip(rdgs, g["readings"], strict=False):
        if fold(rd["text"]) != fold(gr["text"]):
          out.append(Finding("ERROR_READING", folio, n,
                             f"rdg={rd['text']!r} golden={gr['text']!r}"))
        if sorted(rd["wits"]) != sorted(gr["wits"]):
          out.append(Finding("ERROR_WIT", folio, n,
                             f"rdg wits {rd['wits']} != {gr['wits']}"))
        if _strict_editors(rd["editors"]) != _strict_editors(gr["editors"]):
          out.append(Finding("ERROR_EDITOR", folio, n,
                             f"rdg editors {rd['editors']} != {gr['editors']}"))
      verb = app.find(f"{_q('note')}[@type='verbatim']")
      if verb is None or fold(verb.text or "") != fold(g["band"].split(" ", 1)[1]):
        out.append(Finding("ERROR_VERBATIM", folio, n,
                           "verbatim note missing or altered"))

      # anchoring: the text before the end anchor must end with the golden
      # anchor word (the lemma's last word, where the marker was typeset)
      to = app.get("to")
      if to is None:
        out.append(Finding("GAP_UNANCHORED", folio, n, "app has no @to"))
      else:
        ctx = anchor_context(page, to.removeprefix("#"))
        if ctx is None:
          out.append(Finding("ERROR_ANCHOR", folio, n,
                             f"@to anchor {to!r} not found in the page text"))
        else:
          tw = toks(ctx)
          if not tw or tw[-1] != toks(g["anchor_word"] + " x")[0]:
            out.append(Finding("ERROR_ANCHOR", folio, n,
                               f"text before anchor ends {tw[-3:]} — expected "
                               f"{g['anchor_word']!r}"))
  return out


def main() -> int:
  if len(sys.argv) < 3:
    print("usage: check_golden.py golden.json out.tei.xml [--rng tei_all.rng]",
          file=sys.stderr)
    return 2
  golden = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
  tei_path = Path(sys.argv[2])
  findings: list[Finding] = []

  if "--rng" in sys.argv:
    from lxml import etree
    rng_path = sys.argv[sys.argv.index("--rng") + 1]
    rng = etree.RelaxNG(etree.parse(rng_path))
    if not rng.validate(etree.parse(str(tei_path))):
      findings.append(Finding("ERROR_SCHEMA", "-", "-",
                              str(rng.error_log.last_error)))

  pages, root = parse_tei(tei_path)
  wit_map, ed_map = id_maps(root)
  findings += check_idrefs(root)
  findings += compare(golden, pages, wit_map, ed_map)

  errors = [f for f in findings if f.fatal]
  gaps = [f for f in findings if not f.fatal]
  for f in findings:
    print(f"{'ERROR' if f.fatal else 'gap  '} p{f.page} n={f.n} "
          f"[{f.kind}] {f.detail}")
  total = sum(len(p["entries"]) for p in golden["pages"])
  print(f"\n{total} golden entries | {len(errors)} ERRORS | {len(gaps)} gaps")
  if errors:
    print("FAIL: the apparatus contains wrong structure")
    return 1
  print("PASS: zero apparatus errors (gaps are honest refusals)")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
