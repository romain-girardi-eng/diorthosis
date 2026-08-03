#!/usr/bin/env python3
"""Real-PDF ground truth: compare diorthosis' reading of a REAL printed
edition against the scholars' TEI encoding of the SAME text.

Unlike check_golden.py (which typesets the scholars' apparatus into a
layout we control), this harness takes the edition AS PRINTED — reledmac
line-number apparatus, verse-referenced bands, glued sigla, whatever the
book does — and measures, by CONTENT alignment:

  text_coverage   for each TEI <app>, does its <lem> occur in the
                  constituted TEXT diorthosis extracted? (folded substring)
  band_coverage   greedy in-order alignment: does each TEI app's lemma or
                  first reading occur, at a non-decreasing position, in the
                  concatenated APPARATUS band text?
  contamination   multi-word REJECTED readings that leak into the TEXT
                  layer (apparatus quoted as text — the worst failure)
  false_structure <app> elements diorthosis parsed whose lemma matches no
                  TEI lemma (wrong structure is worse than no structure)

Usage:
  real_check.py scholar.xml real.pdf --pages A-B [--text-lang la]
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from lxml import etree

from diorthosis.anchor import anchor_page
from diorthosis.conspectus import Registry, with_builtin_editors
from diorthosis.grammar import parse_entry
from diorthosis.ingest import ingest_pdf
from diorthosis.model import Layer

TEI = "{http://www.tei-c.org/ns/1.0}"


def fold(s: str) -> str:
  s = unicodedata.normalize("NFKC", s)   # ﬁ/ﬂ ligatures -> fi/fl
  s = re.sub(r"[⸀-⸏⟦⟧∥|◊]", " ", s)
  s = re.sub(r"(?<=\S)-\s+", "", s)
  d = unicodedata.normalize("NFD", s)
  out = "".join(c for c in d if not unicodedata.combining(c)).lower()
  out = out.replace("ς", "σ").replace("ʼ", "'").replace("’", "'")
  out = re.sub(r"[,.;·:!?…]+", " ", out)   # punctuation never decides alignment
  return re.sub(r"\s+", " ", out).strip()


def tei_apps(path: Path) -> list[dict]:
  root = etree.parse(str(path)).getroot()
  apps = []
  for app in root.iter(f"{TEI}app"):
    if any(isinstance(d.tag, str) and d.tag == f"{TEI}app"
           for d in app.iterdescendants()):
      continue
    lem = app.find(f"{TEI}lem")
    if lem is None:
      continue
    lem_text = fold(" ".join(lem.itertext()))
    rdgs = [fold(" ".join(r.itertext())) for r in app.findall(f"{TEI}rdg")]
    if not lem_text:
      continue
    apps.append({"lemma": lem_text, "readings": [r for r in rdgs if r]})
  return apps


def main() -> int:
  ap_xml = Path(sys.argv[1])
  pdf = sys.argv[2]
  pages = None
  if "--pages" in sys.argv:
    a, b = sys.argv[sys.argv.index("--pages") + 1].split("-")
    pages = list(range(int(a), int(b) + 1))
  text_lang = (sys.argv[sys.argv.index("--text-lang") + 1]
               if "--text-lang" in sys.argv else "grc")

  apps = tei_apps(ap_xml)
  if "--max-apps" in sys.argv:
    apps = apps[: int(sys.argv[sys.argv.index("--max-apps") + 1])]
  print(f"TEI ground truth: {len(apps)} apps")

  doc = ingest_pdf(pdf, pages=pages, text_lang=text_lang)
  registry = with_builtin_editors(Registry())
  layer_counts: dict[str, int] = {}
  parsed_apps: list[str] = []
  entries_total = 0
  for page in doc.pages:
    anchor_page(page, registry)
    for b in page.blocks:
      layer_counts[b.layer.value] = layer_counts.get(b.layer.value, 0) + 1
      if b.layer is Layer.APPARATUS:
        for e in b.entries or []:
          entries_total += 1
          p = parse_entry(e.raw, registry)
          if p is not None:
            parsed_apps.append(fold(p.lemma))

  text_all = fold("\n".join(
    b.text for p in doc.pages for b in p.blocks
    if b.layer in (Layer.TEXT, Layer.HEADING)))
  band_all = fold("\n".join(
    b.text for p in doc.pages for b in p.blocks
    if b.layer is Layer.APPARATUS))
  print(f"layers: {layer_counts}")
  print(f"text chars: {len(text_all)} | band chars: {len(band_all)} | "
        f"split entries: {entries_total} | parsed as <app>: {len(parsed_apps)}")

  # text coverage: the constituted text must contain each lemma
  t_hit = sum(1 for a in apps if a["lemma"] in text_all)

  # band coverage: greedy in-order content alignment
  # The printed band follows text order, so each app must appear within a
  # BOUNDED window after the previous hit — an unbounded greedy find lets
  # one frequent function-word lemma match far ahead and cascade-fail
  # everything after it (measured: 92.6 % -> 2.3 % from one bad jump).
  WINDOW = 8000
  pos = 0
  b_hit = 0
  misses: list[str] = []
  for a in apps:
    seg = band_all[pos: pos + WINDOW]
    seg_padded = f" {seg} "
    keys: list[str] = []
    for k in (a["lemma"], *(a["readings"][:1])):
      if not k:
        continue
      keys.append(k)
      w = k.split()
      if len(w) >= 3:
        # printed bands compress span lemmas elliptically ("Βόες … Βόες")
        keys.append(f"{w[0]} {w[-1]}")
      if len(w) == 1:
        # a bold lemma re-set in roman extracts glued twice ("δεδε")
        keys.append(k + k)
    best = -1
    for k in keys:
      if len(k) >= 4:
        i = seg.find(k)
      else:
        # function-word lemmas (δέ, ὁ, ὑπό) align word-bounded
        j = seg_padded.find(f" {k} ")
        i = -1 if j < 0 else max(0, j - 1)
      if i >= 0 and (best < 0 or i < best):
        best = i
    if best >= 0:
      b_hit += 1
      pos += best
    elif len(misses) < 8:
      misses.append(f"lemma={a['lemma'][:40]!r} rdg1="
                    f"{(a['readings'][0] if a['readings'] else '')[:40]!r}")
  # contamination: a REJECTED reading leaking into the TEXT near its locus.
  # Common short phrases (Greek: "ἐν τοῖς οὐρανοῖς") legitimately recur all
  # over a text, so the probe demands >= 4 words AND proximity to the
  # lemma's own position — the only place a leak could actually happen.
  contam = 0
  samples = []
  for a in apps:
    li = text_all.find(a["lemma"])
    if li < 0:
      continue
    lo, hi = max(0, li - 400), li + len(a["lemma"]) + 400
    window = text_all[lo:hi]
    for r in a["readings"]:
      if r != a["lemma"] and len(r.split()) >= 4 and r in window:
        contam += 1
        if len(samples) < 5:
          samples.append(r[:60])
        break

  # false structure: parsed <app> lemmas that match no TEI lemma
  tei_lemmas = {a["lemma"] for a in apps}
  tei_lemma_words = {w for a in apps for w in a["lemma"].split()}
  false_structs = [
    fl for fl in parsed_apps
    if fl not in tei_lemmas and not set(fl.split()) & tei_lemma_words
  ]

  n = len(apps) or 1
  print(f"\ntext coverage    : {t_hit}/{len(apps)} = {100*t_hit/n:.1f} % "
        "(TEI lemma found in extracted TEXT)")
  print(f"band coverage    : {b_hit}/{len(apps)} = {100*b_hit/n:.1f} % "
        "(in-order alignment in APPARATUS band)")
  print(f"contamination    : {contam} rejected multi-word readings inside TEXT")
  for s in samples:
    print(f"   e.g. {s!r}")
  print(f"false structures : {len(false_structs)} parsed <app> foreign to the TEI")
  for s in false_structs[:5]:
    print(f"   e.g. {s[:60]!r}")
  if misses:
    print("unaligned sample:")
    for m in misses:
      print(f"   {m}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
