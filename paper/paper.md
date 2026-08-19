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
date: 5 August 2026
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
citable artifact; the `md-ce/0.3` view is intended for retrieval and language-
model pipelines.

# Statement of need

In the major open corpora, machine-actionable apparatus is effectively absent.
A census run for this paper counted, in the edition TEI files under `data/`
(excluding the `__cts__.xml` catalogue stubs) of three pinned repository
states — First1KGreek at `bfea9ac`, `canonical-greekLit` at `790c842`, and
`canonical-latinLit` at `59b8b8b`, all August 2026
[@first1kgreek; @perseusGreek; @perseusLatin]:

| repository | edition files | files with `<app>` | files with `<rdg>` | `<rdg>` elements |
|---|---:|---:|---:|---:|
| First1KGreek | 1,204 | 3 | 3 | 60 |
| canonical-greekLit | 1,612 | 6 | 0 | 0 |
| canonical-latinLit | 687 | 17 | 1 | 1 |
| **total** | **3,503** | **26** | **4** | **61** |

The `<app>` count overstates the coverage: 22 of the 26 files use
`<app><lem>…</lem></app>` with no reading at all, which anchors an editorial
note but records no variant, and one of the three First1KGreek files carries a
single empty placeholder (`<app><lem></lem> <rdg source="foo" wit="a"></rdg></app>`)
beside an apparatus encoded as `<note>` prose. Four files in 3,503 contain a
`<rdg>` of any kind, and 45 of the 61 `<rdg>` elements are non-empty. This is
the gap identified by @damon2016: digital editions commonly discard the
transmission evidence and editorial reasoning recorded by a critical apparatus.

An earlier version of this claim, taken from a GitHub code search rather than
a clone, reported "two files among approximately 1,356"; the count above was
re-derived on full clones and supersedes it.

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
Every figure below was re-derived on the release tree; where a harness reports
a limit as untested, that is stated rather than counted as a zero.

1. **Adversarial real print.** The whole-NT SBLGNT harness compares 6,797
   apparatus entries with zero oracle errors: the officially published PDFs
   on one side, a TEI re-encoding of the same apparatus produced independently
   of them on the other. Its partition
   accounts for every one of the 6,921 source leaf entries by an explicit
   outcome — 6,797 compared, 61 refused with a named convention reason
   (the four single-chapter books, whose bands open on bare verse numbers),
   60 uncovered, 0 unaccounted, 3 adjudicated — and the identity is asserted
   per book and on the corpus sum before the run may exit 0. The three
   remaining apps (Mark 6:33, John 9:11 twice) are typed, evidence-checked
   records rather than a silent remainder. This is evidence for that edition
   and oracle, not for unseen conventions.
2. **Publisher-toolchain inversion.** The Digital Latin Library's own
   reledmac PDF of `balex` gives 563 comparisons with zero errors, zero gaps
   and 17 typed divergences, and the LombardPress/SCTA toolchain PDF of
   Plaoul gives 6,293 comparisons with zero errors. They test recovery from
   pages produced by an independent publishing toolchain, but the printed page
   and the reference encoding descend from one source, so they do not test
   independent editorial encoding.
3. **Retypeset round trips.** The `balex`, SBLGNT, and *Problemata* fixtures
   compare respectively 524, 6,906, and 5,524 representable apparatus entries
   with zero structural errors; the *Problemata* ledger also records 50 honest
   gaps. These are deterministic regression tests. A round trip is not an
   adversarial test.
4. **Self-validation.** On 2,031 Bobichon entries, the pipeline reports 99.3%
   anchoring, 99.0% parse success, 97.5% lemma concordance, and 89.9%
   attribution coverage. These are internal consistency and coverage measures,
   not accuracy against an external ground truth.
5. **Out-of-the-box generalization, measured and negative.** On nine
   never-seen born-digital editions (774 selected pages, no grammar or
   threshold changed), whole-band convention gates refuse eight of the nine
   wholesale; the ninth, Segrave's *Insolubilia*, parses 20 of 923 entries
   (2.2%), all five deterministic samples faithful. The published claim of
   this tier is a refusal rate, not an accuracy rate: no unseen apparatus
   tradition is supported, and a refused band is retained verbatim with the
   gate's own measured reason attached.

Coverage is reported on two axes, because "anchored" alone was a claim
stronger than its evidence. An entry is *attached* when its `<app>` carries
both `@from` and `@to`, and *end-only* when the lemma's start could not be
located. The real `balex` build anchors 563 of 563 entries — 515 attached,
48 end-only — and the same one-line report is emitted to the console and into
the `md-ce` meta line so a single invocation cannot announce two scores.

Known print/TEI mismatches are stored as typed, executable divergence records
whose evidence and expected error class must still match. A two-process fixture
compares emitted files byte for byte, and the automated suite contains 219
tests at the measured revision. Together these controls support
reproducibility and fail-closed
accounting; they do not establish OCR accuracy on noisy scans or generalization
to every apparatus tradition.

The verbatim-refusal contract is a claim about the software, so it is tested
adversarially and its failures are published. The most recent one, closed in
the 1.0 hardening pass, is instructive: on the English translation pages of
the *Insolubilia* — pages the generalization study's page selection excluded —
a numbered English editorial footnote was emitted as a `<lem>`/`<rdg>`
apparatus variant, in schema-valid TEI, at exit 0. Numbered editorial prose
reproduces the numeric-marker convention's entire printed shape and can only
be told apart by what it never carries: sigla. The generic marker grammar now
requires that at least one reading somewhere in the band name a witness, an
editor or a cited version, and the same 60 pages now emit zero `<app>` and
119 verbatim refusals with named evidence. The gate is measured inert on the
certified marker corpus and on the nine unseen editions.

The figures above are emitted by `tools/golden/sblgnt_nt_driver.py`,
`tools/golden/line_check.py`, `tools/golden/plaoul_check.py`,
`tools/golden/check_golden.py`, `tools/golden/real_check.py`,
`tools/golden/generalize.py`, and `tools/evaluate.py`; typed divergences and
byte checks are executable in `tools/golden/divergences.py` and
`tools/golden/double_build.py`; `diorthosis validate` checks the `md-ce`
invariants, and the test count is reported by `pytest`.

# Acknowledgements

<!-- TODO: funding and acknowledgements before submission. -->

# References
