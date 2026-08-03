#!/usr/bin/env python3
"""The self-improvement harness: measurable objectives on a real edition.

The document validates itself. Four metrics, each with a ground truth that
does not depend on our own code being right:

1. **anchoring rate** — entries whose number found its in-text marker;
2. **parse rate** — entries the grammar accepted (refusals are honest);
3. **lemma concordance** — a parsed lemma must MATCH the text immediately
   before its anchor marker (accent-insensitively, case-insensitively):
   the strongest signal, because the edition itself provides the answer;
4. **attribution coverage** — parsed readings that carry at least one
   witness or editor (an apparatus entry almost always names its source).

Run:  python3 tools/evaluate.py <pdf> --pages 290-340 [--conspectus-page N]
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "src")

from diorthosis.anchor import anchor_page
from diorthosis.conspectus import (
  Registry,
  find_conspectus_pages,
  parse_conspectus,
  with_builtin_editors,
)
from diorthosis.grammar import parse_entry
from diorthosis.ingest import ingest_pdf
from diorthosis.match import lemma_matches_before
from diorthosis.model import Layer


def lemma_matches_anchor(lemma: str, page, anchor) -> bool | None:
  """None = unresolvable anchor; else delegate to the shared conventions."""
  if anchor is None or anchor.block_index is None or anchor.char_offset is None:
    return None
  text = page.blocks[anchor.block_index].text
  return lemma_matches_before(lemma, text[: anchor.char_offset])


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("pdf")
  ap.add_argument("--pages", required=True, help="e.g. 290-340")
  ap.add_argument("--conspectus-page", type=int, default=None)
  ap.add_argument("--show-failures", type=int, default=8)
  args = ap.parse_args()

  a, b = args.pages.split("-")
  pages = list(range(int(a), int(b) + 1))

  registry = Registry()
  rng = [args.conspectus_page] if args.conspectus_page is not None else range(0, 200)
  text = find_conspectus_pages(args.pdf, rng)
  if text:
    registry = parse_conspectus(text)
  registry = with_builtin_editors(registry)
  print(f"registry: {len(registry.witnesses)} witnesses, "
        f"{len(registry.editors)} editor tokens")

  doc = ingest_pdf(args.pdf, pages=pages)
  m = {"entries": 0, "anchored": 0, "parsed": 0,
       "lemma_ok": 0, "lemma_bad": 0, "lemma_uncheckable": 0,
       "attributed": 0, "readings": 0}
  fail_parse: list[str] = []
  fail_lemma: list[tuple[str, str]] = []

  for page in doc.pages:
    anchor_page(page)
    for block in page.blocks_of(Layer.APPARATUS):
      for e in block.entries:
        m["entries"] += 1
        if e.anchor is not None and e.anchor.block_index is not None:
          m["anchored"] += 1
        parsed = parse_entry(e.raw, registry)
        if parsed is None:
          fail_parse.append(e.raw[:110])
          continue
        m["parsed"] += 1
        ok = lemma_matches_anchor(parsed.lemma, page, e.anchor)
        if ok is None:
          m["lemma_uncheckable"] += 1
        elif ok:
          m["lemma_ok"] += 1
        else:
          m["lemma_bad"] += 1
          t = page.blocks[e.anchor.block_index].text
          ctx = t[max(0, e.anchor.char_offset - 35): e.anchor.char_offset + 4]
          fail_lemma.append((parsed.lemma[:40], f"ctx=…{ctx!r} | {e.raw[:60]}"))
        for r in parsed.readings:
          m["readings"] += 1
          a = r.attribution
          # collective sigla (codd., edd., cett.) and cited versions (LXX)
          # attribute a reading just as named witnesses/editors do
          collective = {"codd.", "cod.", "edd.", "ed.", "cett.", "al."}
          if (a.witnesses or a.editors or a.sources
              or any(q in collective for q in a.qualifiers)):
            m["attributed"] += 1

  e = m["entries"] or 1
  checkable = (m["lemma_ok"] + m["lemma_bad"]) or 1
  r = m["readings"] or 1
  print(f"\nentries          : {m['entries']}")
  print(f"anchoring rate   : {m['anchored']}/{m['entries']} = {100*m['anchored']/e:.1f} %")
  print(f"parse rate       : {m['parsed']}/{m['entries']} = {100*m['parsed']/e:.1f} %")
  print(f"lemma concordance: {m['lemma_ok']}/{checkable} = {100*m['lemma_ok']/checkable:.1f} % "
        f"({m['lemma_uncheckable']} uncheckable)")
  print(f"attribution      : {m['attributed']}/{r} readings = {100*m['attributed']/r:.1f} %")

  if fail_parse[: args.show_failures]:
    print("\n-- unparsed (sample) --")
    for x in fail_parse[: args.show_failures]:
      print("  ", x)
  if fail_lemma[: args.show_failures]:
    print("\n-- lemma mismatches (sample) --")
    for lemma, raw in fail_lemma[: args.show_failures]:
      print(f"   lemma={lemma!r} | {raw}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
