#!/usr/bin/env python3
"""Strict verse-referenced check: diorthosis' structured apparatus from a
REAL printed NT edition vs the scholars' TEI — zero errors or fail.

Alignment is by verse reference (@loc / @n), k-th entry to k-th entry
within each verse. Wrong structure (lemma, reading text, witness set,
phantom/lost entries, misplaced anchor) is an ERROR; an entry diorthosis
kept as a verbatim note, or left unanchored, is a GAP.

Usage: verse_check.py scholar.xml ours.tei.xml [--book B01] [--rng rng]
"""

from __future__ import annotations

import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from divergences import load_divergences
from lxml import etree

TEI = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def fold(s: str) -> str:
  s = unicodedata.normalize("NFKC", s)
  s = re.sub(r"[⸀-⸏⟦⟧〚〛]", " ", s)
  s = s.replace("[", "").replace("]", "")   # editorial brackets: δ[ε] == δε
  s = re.sub(r"\+\s*", "+ ", s)   # glued addition operator: "+των" == "+ των"
  d = unicodedata.normalize("NFD", s)
  out = "".join(c for c in d if not unicodedata.combining(c)).lower()
  out = out.replace("ς", "σ")
  out = re.sub(r"[,.;·:!?…\-–—'ʼ’]+", " ", out)
  return re.sub(r"\s+", " ", out).strip()


def scholar_apps(path: Path, book: str | None) -> dict[str, list[dict]]:
  """Apps grouped by verse loc, scoped to one book by following the verse
  milestones (xml:id B01K1V8 = book 1) in document order."""
  root = etree.parse(str(path)).getroot()
  by_loc: dict[str, list[dict]] = defaultdict(list)
  current_book = None
  for el in root.iter():
    if not isinstance(el.tag, str):
      continue
    xid = el.get("{http://www.w3.org/XML/1998/namespace}id") or ""
    m = re.match(r"B(\d+)K", xid)
    if m:
      current_book = f"B{m.group(1)}"
    if el.tag != f"{TEI}app":
      continue
    app = el
    if book and current_book != book:
      continue
    if any(isinstance(d.tag, str) and d.tag == f"{TEI}app"
           for d in app.iterdescendants()):
      continue
    lem = app.find(f"{TEI}lem")
    if lem is None:
      continue
    loc = app.get("loc") or "?"
    readings = []
    for rdg in app.findall(f"{TEI}rdg"):
      wits = [w.removeprefix("#") for w in (rdg.get("wit") or "").split()]
      text = " ".join(rdg.itertext())
      # English editorial parentheticals in the TEI ("(and re-number SBL
      # v. 13 as 14)") are encoder commentary the printed band never shows
      text = re.sub(r"\([^)]*[a-zA-Z][^)]*\)", " ", text)
      readings.append({"text": fold(text), "wits": wits})
    by_loc[loc].append({
      "loc": loc,
      "lemma": fold(" ".join(lem.itertext())),
      "readings": readings,
    })
  return by_loc


def our_apps(path: Path) -> tuple[dict[str, list[dict]], dict, list]:
  root = ET.parse(path).getroot()
  wit_names = {}
  for w in root.iter(f"{TEI}witness"):
    xid = w.get(XML_ID) or ""
    abbr = w.find(f"{TEI}abbr")
    wit_names[xid] = (abbr.text or "").strip() if abbr is not None else \
      xid.removeprefix("wit-")
  by_loc: dict[str, list[dict]] = defaultdict(list)
  notes = []
  # page text streams for anchor verification
  streams: dict[str, tuple[str, str | None]] = {}
  edition = root.find(f".//{TEI}div[@type='edition']")
  chunks: list[tuple[str, str | None]] = []
  for el in edition.iter():
    tag = el.tag.rsplit("}", 1)[-1]
    if tag == "ab":
      text = el.text or ""
      for child in el:
        if child.tag == f"{TEI}anchor":
          chunks.append((text, child.get(XML_ID)))
          text = child.tail or ""
        else:
          text += "".join(child.itertext()) + (child.tail or "")
      chunks.append((text, None))
  buf = ""
  for text, aid in chunks:
    buf += text
    if aid:
      streams[aid] = (buf, None)
  for app in edition.iter(f"{TEI}app"):
    loc = app.get("n") or "?"
    lem = app.find(f"{TEI}lem")
    readings = []
    for rdg in app.findall(f"{TEI}rdg"):
      wits = [wit_names.get(w.removeprefix("#"), w) for w in
              (rdg.get("wit") or "").split()]
      text = "".join(rdg.itertext())
      text = re.sub(r"\([^)]*[a-zA-Z][^)]*\)", " ", text)
      readings.append({"text": fold(text), "wits": wits})
    lem_wits = [wit_names.get(w.removeprefix("#"), w) for w in
                (lem.get("wit") or "").split()] if lem is not None else []
    by_loc[loc].append({
      "loc": loc,
      "lemma": fold("".join(lem.itertext())) if lem is not None else "",
      "lem_wits": lem_wits,
      "readings": readings,
      "to": (app.get("to") or "").removeprefix("#"),
      "band": next((n.text or "" for n in app.findall(f"{TEI}note")
                    if n.get("type") == "verbatim"), ""),
    })
  for note in edition.iter(f"{TEI}note"):
    if note.get("type") == "apparatus":
      notes.append(note.text or "")
  return by_loc, streams, notes


def main() -> int:
  scholar_path, ours_path = Path(sys.argv[1]), Path(sys.argv[2])
  book = None
  if "--book" in sys.argv:
    book = sys.argv[sys.argv.index("--book") + 1]
  known: dict = {}
  known_errors: list[str] = []
  if "--known" in sys.argv:
    known, known_errors = load_divergences(
      Path(sys.argv[sys.argv.index("--known") + 1]), book)
  gold = scholar_apps(scholar_path, book)
  ours, streams, notes = our_apps(ours_path)

  if "--rng" in sys.argv:
    rng = etree.RelaxNG(etree.parse(sys.argv[sys.argv.index("--rng") + 1]))
    if not rng.validate(etree.parse(str(ours_path))):
      print(f"ERROR SCHEMA: {rng.error_log.last_error}")
      return 1

  errors_raw: list[tuple[str, str, str]] = []  # (key, kind, message)
  gaps: list[str] = []
  fired: dict[str, set[str]] = defaultdict(set)
  matched = 0
  # Partial-page builds remain useful, but the missing source denominator is
  # now explicit instead of being deleted from the ground truth.
  covered = set(ours.keys())
  gold_covered = {loc: apps for loc, apps in gold.items() if loc in covered}

  def evidence_ok(exc_key: str, record: dict, band: str) -> bool:
    if record.get("unproven") is True:
      errors_raw.append((exc_key, "UNPROVEN_EXCEPTION",
                         f"{exc_key}: exception is explicitly unproven"))
      return False
    print_form = fold(record["print_form"])
    stored = fold(record["band_evidence"])
    actual = fold(band)
    if record["band_evidence"] and (
        not print_form or print_form not in stored or print_form not in actual):
      errors_raw.append((exc_key, "EVIDENCE",
                         f"{exc_key}: print_form is not present in both the "
                         "stored and extracted band evidence"))
      return False
    return True

  def record_error(exc_key: str, kind: str, message: str, band: str) -> None:
    record = known.get(exc_key)
    if record is None or kind not in record["error_kinds"]:
      errors_raw.append((exc_key, kind, message))
      return
    if evidence_ok(exc_key, record, band):
      fired[exc_key].add(kind)

  for loc, gapps in sorted(gold_covered.items()):
    oapps = ours.get(loc, [])
    if len(oapps) > len(gapps):
      exc_key = f"{book}:{loc}" if book else loc
      band = " | ".join(a["band"] for a in oapps)
      record_error(exc_key, "PHANTOM",
                   f"{loc}: PHANTOM — {len(oapps)} ours vs "
                   f"{len(gapps)} scholar", band)
    for k, g in enumerate(gapps):
      key = f"{loc}[{k}]"
      exc_key = f"{book}:{key}" if book else key
      if k >= len(oapps):
        gaps.append(f"{key}: LOST/unparsed (verbatim note expected)")
        continue
      o = oapps[k]
      errs: list[tuple[str, str]] = []
      g_lem = g["lemma"]
      g_r1 = g["readings"][0] if g["readings"] else {"text": "", "wits": []}
      def sp(x: str) -> str:
        return x.replace(" ", "")
      if o["lemma"] != g_lem and o["lemma"] != g_r1["text"] \
         and sp(o["lemma"]) not in (sp(g_lem), sp(g_r1["text"])):
        errs.append(("LEMMA", f"{key} LEMMA ours={o['lemma'][:40]!r} "
                     f"scholar={g_lem[:40]!r}"))
      else:
        if sorted(o["lem_wits"]) != sorted(g_r1["wits"]):
          errs.append(("LEMMA_WITNESSES",
                       f"{key} LEMWITS lemma={g_lem[:30]!r} "
                       f"ours={o['lem_wits']} scholar={g_r1['wits']}"))
        g_rest = g["readings"][1:]
        if len(o["readings"]) != len(g_rest):
          errs.append(("READING_COUNT",
                       f"{key} NREADINGS ours={len(o['readings'])} "
                       f"scholar={len(g_rest)}"))
        else:
          for ord_, (orr, grr) in enumerate(zip(o["readings"], g_rest,
                                                strict=True)):
            o_text = orr["text"].removeprefix("+ ").strip()
            g_text = grr["text"].removeprefix("+ ").strip()
            if o_text != g_text and sp(o_text) != sp(g_text):
              errs.append(("READING_TEXT",
                           f"{key} RDG{ord_} ours={orr['text'][:36]!r} "
                           f"scholar={grr['text'][:36]!r}"))
            if sorted(orr["wits"]) != sorted(grr["wits"]):
              errs.append(("READING_WITNESSES",
                           f"{key} RDGWITS{ord_} lemma={g_lem[:30]!r} "
                           f"rdg={grr['text'][:24]!r} ours={orr['wits']} "
                           f"scholar={grr['wits']}"))
        if not o["to"]:
          gaps.append(f"{key}: unanchored")
        elif o["to"] in streams:
          before = fold(streams[o["to"]][0])
          lem_last = (g_lem.split() or [""])[-1]
          if lem_last and not before.endswith(lem_last):
            errs.append(("ANCHOR",
                         f"{key} ANCHOR text before ends "
                         f"…{before[-30:]!r}, lemma ends {lem_last!r}"))
        else:
          errs.append(("ANCHOR",
                       f"{key} ANCHOR target {o['to']!r} does not resolve"))
      for kind, message in errs:
        record_error(exc_key, kind, message, o["band"])
      matched += 1

  for message in known_errors:
    errors_raw.append(("known", "EXCEPTION_SCHEMA", message))
  for exc_key, record in known.items():
    missing_kinds = set(record["error_kinds"]) - fired.get(exc_key, set())
    if missing_kinds:
      errors_raw.append((exc_key, "STALE_EXCEPTION",
                         f"{exc_key}: stale exception kinds "
                         f"{sorted(missing_kinds)} never fired"))

  source_total = sum(len(v) for v in gold.values())
  covered_total = sum(len(v) for v in gold_covered.values())
  uncovered_locs = sorted(set(gold) - covered)
  uncovered_apps = sum(len(gold[loc]) for loc in uncovered_locs)
  label = book or "selected corpus"
  print(f"{source_total} source apps | {covered_total} in covered loci | "
        f"{matched} compared | {uncovered_apps} uncovered apps in "
        f"{len(uncovered_locs)} loci | {len(errors_raw)} ERRORS | "
        f"{len(gaps)} gaps | {len(fired)} documented print/TEI divergences | "
        f"{len(notes)} verbatim notes")
  print(f"uncovered {label}: {uncovered_apps} source apps across "
        f"{len(uncovered_locs)} loci" +
        (f" ({', '.join(uncovered_locs[:12])})" if uncovered_locs else ""))
  for _, _, e_ in errors_raw[:25]:
    print(f"  ERROR {e_}")
  for g_ in gaps[:8]:
    print(f"  gap   {g_}")
  if errors_raw:
    print("FAIL")
    return 1
  print("PASS: zero apparatus errors")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
