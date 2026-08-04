#!/usr/bin/env python3
"""Strict paragraphed-reledmac check: diorthosis' structured apparatus
from the OFFICIAL-toolchain Plaoul PDF vs the scholarly TEI it was
typeset from (scta-texts/plaoulcommentary, parallel segmentation).

The PDF and the TEI share one source, so alignment is by GLOBAL ORDER.
The EXPECTED printed shape of each reading follows the project's own
critical.xslt, type by type (om./iterum/in textu/plus lectiones/add./
add. sed del./corr. ex) — the stylesheet is the rendering contract.

Usage: plaoul_check.py lectio.xml lectio.pdf [--known file]
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from lxml import etree

from diorthosis.anchor import anchor_page
from diorthosis.conspectus import Registry, with_builtin_editors
from diorthosis.ingest import ingest_pdf
from diorthosis.model import Layer

TEI = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def fold(s: str) -> str:
  # NFKC decomposes "…" into "..." which the punctuation strip would eat
  s = s.replace("…", "").replace("....", ".")
  s = unicodedata.normalize("NFKC", s)
  s = re.sub(r"(?<=\w)-\s+", "", s)
  for br in "⟨⟩〈〉〈〉†":
    s = s.replace(br, "")
  d = unicodedata.normalize("NFD", s)
  out = "".join(c for c in d if not unicodedata.combining(c)).lower()
  out = re.sub(r"[,.;·:!?\-–—'ʼ’‘“”\"()\[\]]+", " ", out)
  out = out.replace("", "…")
  return re.sub(r"\s+", " ", out).strip()


def lem_match(ours: str, scholar: str) -> bool:
  """Long lemmas print ELLIPTICALLY ("diversae …fidei ]"): match on the
  PREFIX only — the printed suffix goes through typesetter transforms
  the TEI cannot model (nested rdgs folded into the last word, leaked
  English notes); global-order alignment already pins the app."""
  if "…" in ours:
    pw = ours.partition("…")[0].split()
    return bool(pw) and scholar.split()[: len(pw)] == pw
  o, g = ours, scholar
  return o == g or o.replace(" ", "") == g.replace(" ", "")


def text_of(el) -> str:
  if el is None:
    return ""
  return " ".join(
    etree.tostring(el, method="text", encoding="unicode").split())


def rendered_text(el) -> str:
  """The PRINTED form of a lem/rdg under the project's own critical.xslt:
  a NESTED app renders as its own lem; a subst prints its add side;
  ``bibl`` is routed to the fontium tier; and — a verified quirk of the
  official stylesheet — the template silencing ``note`` is COMMENTED
  OUT, so English editorial notes LEAK into the printed lemma; the
  checker must model the print, warts included."""
  if el is None:
    return ""
  parts = [el.text or ""]
  for c in el:
    if not isinstance(c.tag, str):
      parts.append(c.tail or "")
      continue
    ln = etree.QName(c).localname
    if ln == "app":
      parts.append(rendered_text(c.find(f"{TEI}lem")))
    elif ln == "bibl":
      pass
    elif ln == "subst":
      parts.append(rendered_text(c.find(f"{TEI}add")))
    else:
      parts.append(rendered_text(c))
    parts.append(c.tail or "")
  return " ".join("".join(parts).split())


def registry_from_tei(root) -> Registry:
  reg = Registry()
  for w in root.iter(f"{TEI}witness"):
    xid = w.get(XML_ID) or ""
    if xid:
      reg.witnesses[xid] = text_of(w)[:80]
  # a @wit token WITHOUT "#" is a source-TEI typo ("3V", "EV") that the
  # XSLT prints verbatim as a de-facto siglum — the print contract again
  for r in root.iter(f"{TEI}rdg"):
    for tok in (r.get("wit") or "").split():
      if not tok.startswith("#") and tok not in reg.witnesses:
        reg.witnesses[tok] = "sic in source TEI @wit"
  return with_builtin_editors(reg)


def scholar_apps(root) -> list[dict]:
  """Expected (lemma, readings) per app, following critical.xslt's
  rendering contract; app-level <note> elements are NOT printed."""
  apps = []
  for app in root.iter(f"{TEI}app"):
    lem = app.find(f"{TEI}lem")
    if lem is None:
      continue
    lem_text = rendered_text(lem) or (lem.get("n") or "")
    rdgs = []
    for r in app.findall(f"{TEI}rdg"):
      t = r.get("type") or ""
      wits = [w.removeprefix("#") for w in (r.get("wit") or "").split()
              if w.removeprefix("#")]
      if t == "variation-absent" or t == "variation-present" and r.get("cause") == "repetition":
        text = ""
      elif t == "variation-choice":
        text = " ".join(text_of(s) for s in r.iter(f"{TEI}seg"))
      elif t == "correction-deletion":
        text = text_of(r.find(f"{TEI}del"))
      elif t == "correction-addition":
        text = text_of(r.find(f"{TEI}add"))
      elif t in ("correction-substitution", "correction-transposition"):
        text = text_of(r.find(f"{TEI}subst/{TEI}add"))
      else:
        # untyped / literal "om." / fallback: the rdg's own content
        text = rendered_text(r)
      rdgs.append({"text": fold(text), "wits": sorted(wits)})
    apps.append({
      "id": app.get(XML_ID) or "",
      "lem": fold(lem_text),
      "rdgs": rdgs,
    })
  return apps


def our_apps(pdf_path: str, registry: Registry) -> tuple[list[dict], dict]:
  doc = ingest_pdf(pdf_path, text_lang="la")
  stats = {"entries": 0, "parsed": 0, "anchored": 0, "preambles": 0}
  out = []
  for page in doc.pages:
    anchor_page(page, registry)
    for block in page.blocks:
      if block.layer is not Layer.APPARATUS:
        continue
      for e in block.entries or []:
        pe = getattr(e, "parsed_paragraph", None)
        if pe is None or not pe.parsed:
          continue
        stats["entries"] += 1
        if e.anchor is not None and e.anchor.block_index is not None:
          stats["anchored"] += 1
        out.append({
          "line": pe.line,
          "lem": fold(pe.lemma),
          "rdgs": [{"text": fold(r.text),
                    "wits": sorted(r.attribution.witnesses)}
                   for r in pe.readings],
        })
  return out, stats


def main() -> int:
  root = etree.parse(sys.argv[1]).getroot()
  known: dict = {}
  if "--known" in sys.argv:
    known = json.loads(
      Path(sys.argv[sys.argv.index("--known") + 1]).read_text())
  registry = registry_from_tei(root)
  gold = scholar_apps(root)
  ours, stats = our_apps(sys.argv[2], registry)

  errors: list[str] = []
  divergences = 0
  n = min(len(gold), len(ours))
  for k in range(n):
    g, o = gold[k], ours[k]
    key = g["id"] or str(k)
    errs: list[str] = []
    if not lem_match(o["lem"], g["lem"]):
      errs.append(f"{key} LEM ours={o['lem'][:38]!r} scholar={g['lem'][:38]!r}")
    elif len(o["rdgs"]) != len(g["rdgs"]):
      errs.append(f"{key} NRDGS ours={len(o['rdgs'])} "
                  f"scholar={len(g['rdgs'])} lem={g['lem'][:26]!r}")
    else:
      for i, (orr, grr) in enumerate(zip(o["rdgs"], g["rdgs"],
                                         strict=True)):
        if orr["text"] != grr["text"] and \
           orr["text"].replace(" ", "") != grr["text"].replace(" ", ""):
          errs.append(f"{key} RDG{i} ours={orr['text'][:34]!r} "
                      f"scholar={grr['text'][:34]!r}")
        if [w for w in grr["wits"] if w not in orr["wits"]]:
          errs.append(f"{key} RDGWITS{i} ours={orr['wits']} "
                      f"scholar={grr['wits']}")
    if errs and key in known:
      divergences += 1
    else:
      errors.extend(errs)
  if len(ours) != len(gold):
    errors.append(f"COUNT ours={len(ours)} scholar={len(gold)}")

  print(f"{len(gold)} scholar apps | {n} compared | {len(errors)} ERRORS | "
        f"{divergences} documented divergences | "
        f"anchored {stats['anchored']}/{stats['entries']}")
  for e in errors[:30]:
    print(f"  ERROR {e}")
  if errors:
    print("FAIL")
    return 1
  print("PASS: zero apparatus errors")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
