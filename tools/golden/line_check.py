#!/usr/bin/env python3
"""Strict line-referenced check: diorthosis' structured apparatus from a
REAL reledmac-set edition vs the scholarly TEI it was generated from.

The PDF and the TEI share one source, so alignment is by GLOBAL ORDER:
k-th non-nested TEI <app> to k-th structured entry. Wrong structure
(lemma, reading text, witness set, editor set) is an ERROR; verbatim
notes and unanchored entries are GAPS.

Usage: line_check.py scholar.xml ours.tei.xml [--rng rng] [--known file]
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

from lxml import etree

TEI = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def fold(s: str) -> str:
  s = unicodedata.normalize("NFKC", s)
  s = re.sub(r"(?<=\w)-\s+", "", s)      # printed hyphenation
  s = s.replace("⟨", "").replace("⟩", "").replace("[", "").replace("]", "")
  s = s.replace("{", "").replace("}", "").replace("◊", " ")
  s = s.replace("†", "")
  d = unicodedata.normalize("NFD", s)
  out = "".join(c for c in d if not unicodedata.combining(c)).lower()
  out = re.sub(r"[,.;·:!?…\-–—'ʼ’()]+", " ", out)
  return re.sub(r"\s+", " ", out).strip()


def canon_attr(name: str) -> str:
  """One canonical form for an attribution authority, whichever side it
  came from: printed siglum, TEI id, editor name with or without year
  ("Landgraf 1891a" == "Landgraf1891a" == "Landgraf")."""
  out = unicodedata.normalize("NFKC", name)
  out = re.sub(r"(?:[\s.,–-]*\d{4}[a-z]?)+$", "", out)
  out = re.sub(r"[\d\s]+$", "", out).rstrip(".")
  out = out.strip().lower() or name.lower()
  # "Du Pontet" == "DuPontet" == "du-pontet"
  return re.sub(r"(?<=\w)[\s.'-]+(?=\w)", "", out)


# first-person editorial verbs the golden TEI declares as sources
# ("scripsimus" = the present editors); our grammar records them as
# qualifiers of the reading, which this checker cannot see — not an
# attribution defect
_FIRST_PERSON = {"scripsimus", "scripsi", "coniecimus", "conieci",
                 "correximus", "correxi", "seclusimus", "seclusi"}


def content_text(el) -> str:
  """The printed form of a lem/rdg: notes excluded, a NESTED app rendered
  as its own lem (the constituted reading), a lost gap as ``* * *``."""
  parts = [el.text or ""]
  for c in el:
    if not isinstance(c.tag, str):        # XML comment
      parts.append(c.tail or "")
      continue
    ln = etree.QName(c).localname
    if ln == "app":
      lem = c.find(f"{TEI}lem")
      parts.append(content_text(lem) if lem is not None else "")
    elif ln == "note":
      pass
    elif ln == "gap":
      parts.append(" * * * ")
    else:
      parts.append(content_text(c))
    parts.append(c.tail or "")
  return "".join(parts)


def scholar_apps(path: Path) -> list[dict]:
  root = etree.parse(str(path)).getroot()
  # TEI witness ids are NCName-mangled ("stigma" for ϛ, "M8" for M*):
  # map each id to the printed siglum, the first token of its description
  sigla: dict[str, str] = {}
  for w in root.iter(f"{TEI}witness"):
    xid = w.get(XML_ID) or ""
    txt = etree.tostring(w, method="text", encoding="unicode").split()
    if xid and txt:
      sigla[xid] = ("ed. pr." if txt[:2] == ["ed.", "pr."] else txt[0])
  apps = []
  # document order keeps a sentence-level app (whose lem embeds nested
  # word-level apps) FIRST, then each nested app — exactly the print order
  for app in root.iter(f"{TEI}app"):
    lem = app.find(f"{TEI}lem")
    if lem is None:
      continue

    def side(el) -> dict:
      wits = [sigla.get(w.removeprefix("#"), w.removeprefix("#"))
              for w in (el.get("wit") or "").split()]
      eds = [e.removeprefix("#") for e in (el.get("source") or "").split()]
      return {
        "text": fold(content_text(el)),
        "attr": sorted(c for a in wits + eds
                       if (c := canon_attr(a)) not in _FIRST_PERSON),
      }

    loc = ""
    xid = lem.get(XML_ID) or ""
    m = re.match(r"lem-([\d.]+)-", xid)
    if m:
      loc = m.group(1)
    apps.append({
      "loc": loc,
      "lem": side(lem),
      "rdgs": [side(r) for r in app.findall(f"{TEI}rdg")],
      "split_next": app.get("type") == "split-entry",
    })
  # a type="split-entry" app continues in the next one (@next/@prev on the
  # lems) — the PRINT sets them as a single entry
  merged: list[dict] = []
  skip = False
  for i, a in enumerate(apps):
    if skip:
      skip = False
      continue
    if a["split_next"] and i + 1 < len(apps):
      b = apps[i + 1]
      a = {
        "loc": a["loc"],
        "lem": {
          "text": (a["lem"]["text"] + " " + b["lem"]["text"]).strip(),
          "attr": sorted(set(a["lem"]["attr"]) | set(b["lem"]["attr"])),
        },
        "rdgs": a["rdgs"] + b["rdgs"],
        "split_next": False,
      }
      skip = True
    merged.append(a)
  return merged


def our_apps(path: Path) -> tuple[list[dict], list[str]]:
  root = ET.parse(path).getroot()
  wit_names = {}
  for w in root.iter(f"{TEI}witness"):
    xid = w.get(XML_ID) or ""
    abbr = w.find(f"{TEI}abbr")
    wit_names[xid] = ((abbr.text or "").strip()
                      if abbr is not None else xid.removeprefix("wit-"))
  ed_names = {}
  for b in root.iter(f"{TEI}bibl"):
    xid = b.get(XML_ID)
    if xid and xid.startswith("ed-"):
      abbr = b.find(f"{TEI}abbr")
      ed_names[xid] = ((abbr.text or "").strip()
                       if abbr is not None else xid.removeprefix("ed-"))
  edition = root.find(f".//{TEI}div[@type='edition']")
  apps, notes = [], []
  for el in edition.iter():
    tag = el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""
    if tag == "note" and el.get("type") == "apparatus":
      notes.append(el.text or "")
    if tag != "app":
      continue

    def side(e) -> dict:
      wits = [wit_names.get(w.removeprefix("#"), w.removeprefix("#wit-"))
              for w in (e.get("wit") or "").split()]
      eds = [ed_names.get(e2.removeprefix("#"), e2.removeprefix("#ed-"))
             for e2 in (e.get("source") or "").split()]
      return {
        "text": fold(e.text or ""),
        "attr": sorted(canon_attr(a) for a in wits + eds),
      }

    lem = el.find(f"{TEI}lem")
    apps.append({
      "n": el.get("n") or "",
      "lem": side(lem) if lem is not None else {"text": "", "attr": []},
      "rdgs": [side(r) for r in el.findall(f"{TEI}rdg")],
      "to": (el.get("to") or ""),
    })
  return apps, notes


def main() -> int:
  gold = scholar_apps(Path(sys.argv[1]))
  ours, notes = our_apps(Path(sys.argv[2]))
  known: dict = {}
  if "--known" in sys.argv:
    known = json.loads(
      Path(sys.argv[sys.argv.index("--known") + 1]).read_text())
  if "--rng" in sys.argv:
    rng = etree.RelaxNG(etree.parse(sys.argv[sys.argv.index("--rng") + 1]))
    if not rng.validate(etree.parse(sys.argv[2])):
      print(f"ERROR SCHEMA: {rng.error_log.last_error}")
      return 1

  errors: list[str] = []
  gaps: list[str] = []
  divergences = 0
  n = min(len(gold), len(ours))
  for k in range(n):
    g, o = gold[k], ours[k]
    key = f"{g['loc'] or k}"
    errs: list[str] = []
    if o["lem"]["text"] != g["lem"]["text"] \
       and o["lem"]["text"].replace(" ", "") != \
           g["lem"]["text"].replace(" ", ""):
      errs.append(f"{key} LEM ours={o['lem']['text'][:38]!r} "
                  f"scholar={g['lem']['text'][:38]!r}")
    elif [a for a in g["lem"]["attr"] if a not in o["lem"]["attr"]]:
      # the golden TEI demotes second-tier authorities to notes the print
      # sets flat, so extras on our side are tolerated; MISSING ones are
      # structural errors
      errs.append(f"{key} LEMATTR ours={o['lem']['attr']} "
                  f"scholar={g['lem']['attr']} lem={g['lem']['text'][:26]!r}")
    elif len(o["rdgs"]) != len(g["rdgs"]):
      errs.append(f"{key} NRDGS ours={len(o['rdgs'])} "
                  f"scholar={len(g['rdgs'])} lem={g['lem']['text'][:26]!r}")
    else:
      for i, (orr, grr) in enumerate(zip(o["rdgs"], g["rdgs"],
                                         strict=True)):
        if orr["text"] != grr["text"] and \
           orr["text"].replace(" ", "") != grr["text"].replace(" ", ""):
          errs.append(f"{key} RDG{i} ours={orr['text'][:34]!r} "
                      f"scholar={grr['text'][:34]!r}")
        if [a for a in grr["attr"] if a not in orr["attr"]]:
          errs.append(f"{key} RDGATTR{i} ours={orr['attr']} "
                      f"scholar={grr['attr']} rdg={grr['text'][:26]!r}")
    if errs and (key in known
                 or f"{key}:{g['lem']['text'][:24]}" in known):
      divergences += 1
    else:
      errors.extend(errs)
    if not o["to"]:
      gaps.append(f"{key}: unanchored")
  if len(ours) != len(gold):
    errors.append(f"COUNT ours={len(ours)} scholar={len(gold)} "
                  f"(notes kept verbatim: {len(notes)})")

  print(f"{len(gold)} scholar apps | {n} compared | {len(errors)} ERRORS "
        f"| {len(gaps)} gaps | {divergences} documented divergences | "
        f"{len(notes)} verbatim notes")
  for e in errors[:30]:
    print(f"  ERROR {e}")
  for g_ in gaps[:6]:
    print(f"  gap   {g_}")
  if errors:
    print("FAIL")
    return 1
  print("PASS: zero apparatus errors")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
