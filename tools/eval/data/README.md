# Variant-QA evaluation data

These files are deterministic derivatives of the scholar-encoded TEI fetched
by `tools/golden/fetch_sources.sh`. Regenerate them from the repository root:

```console
python3 tools/eval/build_qa_dataset.py --seed 20260804
```

`balex.json` and `sblgnt.json` contain only questions, short answers, question
types, and document-order `<app>` references. The `*-flat-fallback.json` files
contain one short constituted-text context (at most 72 source words) and one
apparatus entry per sampled app. They are a no-PDF fallback, not a copy of an
edition or of any printed page. The evaluation runner prefers real local PDFs.
Loci in the golden harness's typed print/TEI divergence registries are excluded
before sampling, so a representation comparison is not scored against two
adjudicated source forms that genuinely disagree.

Source and data licenses:

- `balex*.json`: *Bellum Alexandrinum*, ed. Cynthia Damon et al., Library of
  Digital Latin Texts, public beta 0.0.1. Source and these derived data are
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- `sblgnt*.json`: *The Greek New Testament: SBL Edition*, Michael W. Holmes
  (2010), TEI conversion by Joey McCollum, fetched from the Patristic Text
  Archive pinned source. Source and these derived data are
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The Python evaluation harness remains covered by the repository's MIT license.
