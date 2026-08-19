# Changelog

All notable changes to diorthosis are recorded here, in the format of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html); what a major bump
would break is enumerated in [docs/stability.md](docs/stability.md).

Two notes so the dates below are read correctly. **The development history is
compressed**: 0.1.0 through 0.7.0 were tagged over three days, 3–5 August 2026,
each release driven by one measured failure of the release before it. And
**every figure quoted here is a measurement**, re-derived on the tree it is
attributed to; the lab notebook behind them, with the probes that produced them
and the ones that failed, is [FINDINGS.md](FINDINGS.md).

## [Unreleased]

The 1.0 waves. Wave B's red contracts were closed in wave C; the suite is
green on this tree (real-edition fixtures, not a synthetic PDF).

### First-run probe, OCR registers, Budé omissions

#### Added

- **`diorthosis probe`** samples a PDF and suggests `--pages`,
  `--conspectus-page` and `--text-lang`. Additive CLI surface; a suggestion
  is not a certification.
- **OCR adapters honor unambiguous declared region types** (PAGE
  `@type=apparatus`, ALTO `TAGREFS`/`LABEL=apparatus`, hOCR `ocr_header` /
  `ocr_pageno`). Layout guesses (`paragraph`, `footer`) stay `UNKNOWN`.
- **Budé `om.`-only entries** (`5 χρόνῳ om. L`) and **hand-superscript
  burst** (`ABVG²` → A B V G). Narrative leftovers still refuse.

#### Changed

- **regreek 0.7.3** (fail-closed two-column split): a bilingual spread
  becomes `greek_text` | `translation` only when the gutter is empty, both
  columns have at least three lines, and no line spans the mid-page. A
  spanning title keeps the page unsplit.

### Teubner / OCT and Budé grammars

#### Added

- **Teubner/OCT colon-negative grammar** (`teubnergrammar.py`). `LINE lemma]
  reading A : reading B` — the spaced colon the paragraph grammar refuses
  on purpose, so Plaoul is not stolen. A silent lemma emits `<lem>` without
  `@wit`; `cett.` is never invented.
- **Budé grammar** (`budegrammar.py`), written against the printed Herodian
  shape: `||` separates entries, the lemma carries witnesses, narrative
  leftovers (`euanida`, `in G uerbum …`) stay verbatim. Segrave-style
  `|| LINE lemma]` continuation is still refused.

### Cleanup — real fixtures, honest docs, CropBox review

#### Fixed

- **`diorthosis review` no longer crashes when CropBox ≠ MediaBox.** Snippet
  crops are translated from pdfminer (MediaBox) space onto the pdfium
  (CropBox) bitmap and skipped when the intersection is empty, instead of
  raising Pillow's `tile cannot extend outside image` / `lower < upper`.
- **CLI, adversarial and documentation nets run on a checksum-pinned published
  edition** (DLL *Bellum Alexandrinum*), not an in-process synthetic PDF.
- Stale "red on purpose" / "3 unaccounted, exit 1" claims in the test
  headers, CONTRIBUTING.md and the JOSS paper, which no longer described
  the tree.

### Wave A — the refusal promise made true again (`bd01130`)

#### Fixed

- **A fabrication that walked through the v0.7 gate.** On the *Insolubilia*'s
  odd (English) pages — outside every page selection of the generalization
  study — the generic marker grammar accepted a band of two English editorial
  footnotes and emitted footnote 47 as an apparatus variant: schema-valid TEI,
  `validate` and `roundtrip` green, exit 0. Numbered editorial prose reproduces
  the numeric-marker convention's entire printed shape; what it never carries is
  sigla. The gate now requires that at least one reading **somewhere in the
  band** name a witness, an editor or a cited version. Band-level deliberately:
  the entry-level rule was tried and reverted, because editions collated against
  a single witness print bare readings by design. Measured on the same 60 pages:
  1 `<app>` before, 0 after.
- **`build` exited 0 on a result its own validator rejects.** The README's own
  one-liner ran a 481-page PDF, found zero constituted-text blocks, produced zero
  apparatus entries and wrote md-ce its own validator rejects with `I7`
  duplicate-folio violations — at exit 0. `build` now self-validates before
  claiming success, with `--ignore-self-check` as the documented, loud escape.
- **One invocation announced two different coverage scores**, and all three
  emitters called an `<app>` carrying only its END anchor "anchored". There is
  now one `report` production rendered identically in the console, the md-ce
  meta line and every page header, partitioning entries twice. Real balex:
  563 entries, 563 parsed, 0 refused; 563 anchored = **515 attached + 48
  end-only**. Every earlier "100 % anchored" must be read through that split.
- **`real_check` could PASS on an empty examination.** A PASS now requires an
  examined denominator above a documented floor, else NOT-PROVEN. This convicted
  the balex invocation the golden README itself documented.
- **The whole-NT totals exceeded their own manifest.** Every source app now
  lands in exactly one bucket, asserted per book and on the corpus sum:
  6,921 = 6,797 compared + 61 refused + 60 uncovered + 3 unaccounted. The driver
  **exits 1** while those three await human adjudication.
- **Human corrections could land on the wrong entry.** Override keys were
  positional, so an edit re-targeted whatever became the *n*-th entry of a page
  on the next build — and emitted it carrying `resp="#human-review"`. Keys are
  now bound to the entry's byte-exact source slice by hash, and the file format
  is versioned (`diorthosis-overrides/1`).

### Wave B — executable documentation and a frozen surface (`434bd39`)

#### Added

- Documentation a stranger can follow: `docs/tutorial.md` (a real pinned edition
  end to end), `docs/cookbook.md`, `docs/troubleshooting.md`, `docs/cli.md`,
  `docs/api.md`, and `docs/stability.md` stating what 1.0 freezes. Every command
  in them was executed and its real output pasted.
- A **runnable-documentation convention**: a fenced block marked
  `<!-- diorthosis-doc: runnable -->` is executed by the test suite, and every
  output line it claims must really appear.
- `diorthosis.__all__` goes from 3 usable names to a declared 40-symbol pipeline
  API. The two exported emitters could not previously be called at all: they take
  a `Registry` that was not exported.
- 194 tests over the CLI contract, the adversarial input boundary and the
  documentation.

#### Changed

- Every published figure re-derived rather than retyped, and the missing lab
  notebook entries written (FINDINGS §20 for v0.7 gating, §21 for wave A).
- SPEC.md made normative for all four emitted formats, not md-ce alone.

#### Known — red on purpose at `434bd39`

**32 of wave B's tests failed deliberately** at the commit that added them. They
encoded contracts the tool did not yet keep, written before the code that keeps
them:

- a truncated hOCR file emitted `<span class=ocr_line` as **edition text** —
  source markup impersonating the constituted text, the same family as the
  fabrication wave A closed;
- 28 input-boundary cases leaked a dependency's exception (`PDFSyntaxError`,
  `PSEOF`, `PDFPasswordIncorrect`, `ParseError`) instead of the documented
  exit 2;
- the documentation harness disagreed with three verbatim tool transcripts.

### Wave C — closing the contracts, and a second reader (in progress)

#### Added

- `CONTRIBUTING.md`, `MAINTAINING.md`, this changelog, `SECURITY.md`, and issue
  and pull-request templates: what a change must clear, how a release is cut,
  what the harness needs that pip cannot install, and how to triage a red
  battery.
- `tools/golden/fetch_generalization_corpus.sh`. The flagship v0.7
  generalization table was **irreproducible**: its nine PDFs were named by
  hardcoded `/tmp` path with no URL. Every source has been recovered — Open Book
  Publishers, three HAL theses, Zenodo, BIT&S, HASP, OAPEN — and each download
  is verified against a recorded SHA-256. Seven of the nine are byte-identical to
  what was measured; the ninth (Gracilis) is rebuilt byte-identically from the
  SCTA TEI pinned at the commit that produced it. The one exception is stated in
  `docs/generalization.md` rather than left silent: Brill stamps a download date
  into *Universal Śaivism*, so the measured bytes are reviewer-local and the
  OAPEN copy is substituted, reproducing every published figure of that row
  except its apparatus-character count.
- A `[golden]` extra (`lxml`, `saxonche`) for the evidence harness.

#### Fixed

- Wave B's 32 red contracts. The input boundary now refuses a malformed source
  in diorthosis's own words at exit 2, naming the file, instead of leaking a
  dependency's exception — and a source a parser could not finish never becomes
  edition text.

## [0.7.0] — 2026-08-04

Convention gating. The release whose finding is the reason the project can claim
anything at all about editions it has not seen.

### Added

- **A whole-band convention gate per grammar** (`convention.py` plus one
  `gate_*` per grammar module). Structural signals only — foreign separators
  (`||`, `∥`, spaced `|`, `•`), orphan `]` closers beyond the split boundaries,
  token-weighted trial-parse consumption, the share of entries that trial-parse,
  the share of sides carrying an attribution — and, for the generic marker path,
  the mandatory evidence that numeric-marker splitting produced boundaries **and**
  that at least one of those markers resolved against the page's text layer.
  **No edition is whitelisted and no gate reads an edition-specific signal.**
- Every refusal stores its own measured reason on every entry of the band, so
  the review UI and the generalization harness both see *why*.
- `tools/golden/generalize.py` and `docs/generalization.md`: nine never-seen
  born-digital editions, 774 selected pages, measured out of the box.

### Fixed

- **The measured failure that motivated all of the above.** At v0.6, on those
  nine editions, 1,368 of 1,959 split entries were parsed and **31 of 36
  deterministic samples were false structures** — fontes paragraphs recast as
  lemmas, page-sized Budé bands collapsed into one lemma with many readings, tier
  headings promoted to readings, and twelve parses of explanatory prose in an
  edition with *no critical apparatus at all*. Every one was schema-valid TEI and
  seven of nine builds passed both `validate` and `roundtrip`. **Schema validity
  and round-trip stability are orthogonal to philological truth.** After gating,
  eight of nine editions refuse 100 % wholesale, *Insolubilia* keeps 20 of 923
  entries, and fabricated structures in the sampled population go 31 → 0.

### Changed

- ***Problemata* honest gaps 47 → 50** — the only regression-shaped movement, and
  it is a gain. Three pages carry a single opening phrase as their whole
  constituted text, the layerer reads that lone line as a running head, and the
  printed superscript has nowhere to resolve. v0.6 emitted the band as `<app>`
  anyway, with a lemma pointing at nothing. The band now stays verbatim, and each
  of the three counts two gaps where it counted one.

### Unchanged, and measured to be so

Bobichon identical on all four metrics with 186 of 186 marker bands still
accepted; real balex 563 = 0/0; retypeset balex 524 = 0/0; retypeset SBLGNT
6,906 = 0/0; Plaoul 6,293 = 0; real Matthew 822 = 0.

## [0.6.0] — 2026-08-04

The paragraphed-reledmac grammar and the double apparatus, to zero.

### Added

- `paragraphgrammar.py`: juxtaposed `NUM lemma] readings` entries with a
  **non-consuming** boundary scan (a fontes narrative must not swallow a genuine
  boundary hiding inside its span), an elliptic-head guard, the LombardPress
  operator vocabulary, corr.-ex and facsimile notes, and duplicate-siglum
  disambiguation (run-initial = this reading's text, mid-run = the next reading).
- `--sigla` for editions whose PDF prints no conspectus.
- `roundtrip`: a mechanical equivalence check between the two projections of one
  model — same folios in order, same normalised text, same verbatim entries with
  multiplicities, same translation and notes layers.
- `review`: every apparatus entry face to face with an image snippet of the
  printed band lines it was split from, and corrections exported as
  `overrides.json`; `build --overrides` replays them, marking each overridden
  entry `resp="#human-review"` with a declared `respStmt`.
- `STEM.witnesses.json`: every siglum used in the parsed apparatus, decomposed
  into base witness plus hand state — **only when the base is itself declared in
  the edition's conspectus**. An undeclared base leaves the siglum atomic.
- `tools/golden/plaoul_build_pdf.py`: the third real-backtesting case, built by
  the LombardPress/reledmac toolchain itself.

### Evidence

Plaoul lectio 1–30: **6,293 apparatus entries, 0 errors**, anchoring 94.9 %,
under a double apparatus with crop marks, a DRAFT watermark, folio marks and
marginal counters interleaved in the glyph stream.

## [0.5.0] — 2026-08-04

The line-referenced (reledmac) grammar and superscript sigla, both to zero.

### Added

- `linegrammar.py`: entries split on `∥` with per-chapter line numbers inherited
  when omitted, ranges spanning chapters, `◊` for a crux, omitted-separator
  boundaries, glued-sigla dissolution, note/reading discrimination.
- Superscript witness sigla in band and conspectus (`Nᵘ`, `Eᵃ`, `Pˣ`), Greek
  consensus letters, lowercase edition sigla.
- Degenerate-page reclassification and repeated-footer split in the born-digital
  adapter.

### Evidence

The **real** DLL *Bellum Alexandrinum* PDF against the TEI it was typeset from:
563 of 563 entries, **0 errors, 0 gaps**, one documented divergence.
*Problemata* 5,524 apps, 0 errors.

## [0.4.1] — 2026-08-04

### Fixed

The loop to zero on the whole New Testament, by the discipline the night taught:
probe the geometry first, never tune blind — a blind threshold sweep moved
123 → 123. In-band anchor sigla stripped inside lemma tokens including numbered
occurrences; `em(endavit)` peeled as a qualifier; `〚WH〛` normalised as the
spuria siglum and a bare `] 〚WH〛` transferred to the lemma's witnesses rather
than read as an omission; elliptical lemmas chained over N parts taking the
**shortest** span.

### Evidence

All 27 books of the real printed SBLGNT — **0 apparatus errors**, with 59
print/TEI divergences documented and each verified against the extracted band.
(Read through wave A: under the asserted bucket partition the compared count is
6,797 of 6,921 source leaf apps.)

## [0.4.0] — 2026-08-04

The first foreign convention fully parsed, on the edition as printed.

### Added

- `versegrammar.py` for the New Testament convention: entries split on `•` and
  verse references, `LEMMA SIGLA ] reading SIGLA` with edition sigla declared as
  witnesses exactly as the convention's own TEI does, `–` as an empty `<rdg>`,
  `+ X` kept verbatim; anchoring by verse window × lemma, tolerant of the text's
  own `⸀⸂⸃` anchor sigla, with the constituted text arbitrating between candidate
  forms of a noisy printed lemma.

### Fixed

- **The SBLGNT PDFs overlay every bold lemma with a displaced copy**, and
  text-level merging doubled lemmas (`δὲδὲ`) and leaked copies into neighbouring
  entries. Line construction now merges fragments at **glyph** level, dropping
  overlaid duplicates at 0.15× glyph size — a geminate is a full advance apart
  and survives, where a loose 0.5× threshold once ate every double letter in the
  book. (regreek 0.7.0.)

### Evidence

Matthew, whole book: **822 of 822 scholar apps, 0 errors**. Cost accepted and
measured: Bobichon anchoring 99.5 → 99.3 %, three anchors shifted by
re-synthesized spacing.

## [0.3.0] — 2026-08-03

### Added

- **The golden harness.** Scholar TEI editions with real `<app>/<lem>/<rdg>` are
  re-typeset into a born-digital critical-edition PDF, diorthosis compiles the
  PDF back, and `check_golden.py` requires the output to reproduce the scholars'
  apparatus exactly. Pagination is composed deterministically rather than left to
  TeX, with a page-count guard. Every `<app>` the adapter cannot represent
  faithfully is **skipped and counted** — the golden never contains a guess.
- The asymmetric bar that has governed the project since: a **wrong** structure
  fails the run; a **missing but honest** structure is a reported gap.

### Evidence

*Bellum Alexandrinum* 524 entries, 0 errors, 0 gaps. SBLGNT, the whole New
Testament, 6,906 entries, 0 errors, 0 gaps.

## [0.2.1] — 2026-08-03

### Fixed

- **The emitters violated invariant I3 twenty times in one book.** Anchoring
  accepted lemma-confirmed *detached* markers, but `md.py` and `tei.py` re-scanned
  for glued markers instead of using the resolved anchors: the apparatus showed
  `⟦258:4⟧` while the text kept a literal digit. Anchors now carry the exact digit
  span and both emitters rewrite from them — one source of truth.
- **Byte-determinism was broken across processes**: `_emit_reading` iterated a
  *set*, whose order varies with hash randomization, so two identical builds
  differed in `<witDetail>` order.
- Greek capitals with prosgegrammeni (U+1F88–1FAF) were missing from the lemma
  capital class, silently merging five genuine entries into their predecessors.

### Added

- `diorthosis validate`: the SPEC executed. Invariants I1–I7 and I10–I12 checked
  mechanically.

## [0.2.0] — 2026-08-03

Consolidation of an eight-angle adversarial hardening campaign.

### Fixed

- **The TEI was not even parseable**, on duplicate `xml:id`s minted from
  repeating marker numbers. It now validates against the official `tei_all.rng`.
- **Anchoring rebuilt on candidates plus lemma discrimination.** Marker numbers
  repeat within pages and the old first-wins rule silently chose wrong
  occurrences. Unanchored entries over the full book: 60 → 12.

### Added

- **Foreign-series refusal**: Göttingen-style entries are refused rather than
  silently misattributed. The cross-edition test had shown 53.8 % acceptance with
  essentially none correct.
- md-ce/0.2 with a normative SPEC and twelve mechanically-checkable invariants;
  page-scoped `⟦folio:n⟧` markers with an explicit `?` for unresolved anchors.
- hOCR and PAGE-XML adapters, wired as `--hocr` and `--page-xml`.
- TEI emission aligned with Guidelines ch. 13: `<variantEncoding
  method="double-end-point" location="internal">`, `@source` for conjectures
  rather than `@resp` (which would claim the encoder's agency), `om.` as an
  empty `<rdg>`, placement notes as `<witDetail>`.

## [0.1.0] — 2026-08-03

Initial release. One internal model, two outputs: TEI P5 and md-ce/0.1, whose
layer fences make it impossible for a retrieval chunker to mix apparatus into
text. Apparatus bands split into entries and anchored to their in-text
superscript markers; entries preserved **verbatim**, with interpretation into
`<app>/<lem>/<rdg>` deferred rather than guessed. Ingestion of born-digital PDFs
and of ALTO from any OCR engine, with every OCR-sourced block permanently marked
generative in both outputs.

0.1.0 was never tagged; it is commit `c7e57d5`. Tags exist from `v0.2.0` on.

[Unreleased]: https://github.com/romain-girardi-eng/diorthosis/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/romain-girardi-eng/diorthosis/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/romain-girardi-eng/diorthosis/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/romain-girardi-eng/diorthosis/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/romain-girardi-eng/diorthosis/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/romain-girardi-eng/diorthosis/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/romain-girardi-eng/diorthosis/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/romain-girardi-eng/diorthosis/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/romain-girardi-eng/diorthosis/releases/tag/v0.2.0
