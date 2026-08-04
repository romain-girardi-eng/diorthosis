---
title: "diorthosis: compiling printed critical editions into TEI P5 and AI-ready Markdown"
tags:
  - digital humanities
  - textual criticism
  - critical apparatus
  - TEI
  - OCR
authors:
  - name: Romain Girardi
    affiliation: 1
affiliations:
  - name: CEPAM-UMR 7264, Université Côte d'Azur
    index: 1
date: 4 August 2026
bibliography: paper.bib
---

<!-- TODO: add Romain Girardi's ORCID before submission. -->

# Summary

`diorthosis` is a Python command-line tool for converting a printed critical
edition into TEI P5 and a deliberately lossy Markdown retrieval view. It
separates constituted text from the apparatus, parses edition conventions with
explicit grammars, anchors readings to the text, distinguishes manuscript
witnesses from editorial sources, and preserves every apparatus source slice
verbatim. When the evidence is insufficient, it emits the source as an
unparsed note instead of manufacturing a plausible reading. The TEI is the
citable artifact; the `md-ce/0.2` view is intended for retrieval and language-
model pipelines.

# Statement of need

In the major open corpora surveyed for this project, machine-actionable
apparatus is effectively absent: Perseus and First1KGreek provide constituted
texts, while the corpus census recorded for this project found only two files
containing `<app>` among approximately 1,356 First1KGreek TEI files
[@first1kgreek; @perseusGreek; @perseusLatin]. This is the gap identified by
@damon2016: digital editions commonly discard the transmission evidence and
editorial reasoning recorded by a critical apparatus.

The printed page is not safely recoverable by asking a vision-language model to
transcribe it freely. On ancient Greek critical editions, @karamolegkou2026
show that errors can remain fluent and visually unsupported. A parser governed
by a verbatim-refusal contract is therefore an antidote and verifier, not a
competitor to generative OCR: uncertain material remains inspectable and is not
silently promoted to philological fact.

> **To our knowledge, diorthosis is the first published, general-purpose
> tool — driven by convention grammars rather than single-edition rules —
> that reconstructs a TEI critical apparatus (`<app>/<lem>/<rdg>` with
> witness attributions) anchored to the constituted text, from the
> PRINTED PAGE of scholarly editions (PDF), across multiple apparatus
> conventions and languages, under a verbatim-refusal contract.**

Every qualifier is necessary. Bambaci's Kennicott work is the closest genuine
precedent: it applies formal, rule-based parsing to the OCR of one printed
Hebrew edition and reconstructs its collated witnesses
[@bambaci2021; @bambaci2021ijist; @bambaci2022; @bambaci2025]. Turnbull's `dcodex_variants`
produces TEI for UBS5 and NA28, but starts from pre-tagged Logos HTML and uses
edition-specific importers [@turnbullVariants]. @boschetti2009 established an
OCR workflow for classical critical editions, with manual separation of text
and apparatus rather than structural apparatus parsing. `diorthosis` therefore
does not claim to be the first printed-apparatus parser.

# Functionality

The pipeline ingests decoded PDF text or OCR output, classifies page regions,
segments apparatus entries, applies a selected convention grammar, and resolves
page-scoped markers. Its TEI uses internal double-end-point attachment:
`<anchor>` elements delimit confidently located lemma spans, while `<app>`
contains `<lem>` and `<rdg>` elements. Witness sigla resolve through
`listWit`; editorial attributions use `@source`; and each parsed entry retains
an exact `note[@type="verbatim"]`. A missing start match is represented by an
end-only apparatus link, and an unparsed entry remains `note[@type="apparatus"]`.
Human corrections are supplied as review overrides without changing the stored
source wording.

# Quality control

Validation is deliberately stratified, because no tier substitutes for another.

1. **Adversarial real print.** The whole-NT SBLGNT harness compares 6,797
   apparatus entries with zero oracle errors and accounts for all 6,921 source
   leaf apparatus entries by explicit outcomes. This is evidence for that
   edition and oracle, not for unseen conventions.
2. **Official-toolchain inversion.** LombardPress-derived fixtures give
   `balex` 563 comparisons with zero errors and zero gaps, and Plaoul 6,293
   comparisons with zero errors. They test recovery from pages produced by an
   independent publishing toolchain, but not independent editorial encoding.
3. **Retypeset round trips.** The `balex`, SBLGNT, and *Problemata* fixtures
   compare respectively 524, 6,906, and 5,524 representable apparatus entries
   with zero structural errors; the *Problemata* ledger also records 47 honest
   gaps. These are deterministic regression tests. A round trip is not an
   adversarial test.
4. **Self-validation.** On 2,031 Bobichon entries, the pipeline reports 99.3%
   anchoring, 99.0% parse success, 97.5% lemma concordance, and 89.9%
   attribution coverage. These are internal consistency and coverage measures,
   not accuracy against an external ground truth.

Known print/TEI mismatches are stored as typed, executable divergence records
whose evidence and expected error class must still match. A two-process fixture
compares emitted files byte for byte, and the current automated suite contains
159 tests. Together these controls support reproducibility and fail-closed
accounting; they do not establish OCR accuracy on noisy scans or generalization
to every apparatus tradition.

The figures above are emitted by `tools/golden/sblgnt_nt_driver.py`,
`tools/golden/line_check.py`, `tools/golden/plaoul_check.py`,
`tools/golden/check_golden.py`, and `tools/evaluate.py`; typed divergences and
byte checks are executable in `tools/golden/divergences.py` and
`tools/golden/double_build.py`, and the test count is reported by `pytest`.

# Acknowledgements

<!-- TODO: funding and acknowledgements before submission. -->

# References
