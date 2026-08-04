# Out-of-the-box generalization of diorthosis v0.6

## Scope and method

This is a measurement, not a tuning exercise. It measures diorthosis 0.6.0 at
Git revision `6102801ccd20811a32120793560b225abb555d7d` on eight reviewer-supplied,
never-seen born-digital editions and one optional same-toolchain, unseen-content
case. No grammar, threshold, override, parser source, or test was changed. The
command-line options are limited to page selection, the shipped `la` or `grc`
text-band model, a printed conspectus page, and sigla transcribed unambiguously
from front matter. Thus a refusal is a successful application of the
verbatim-refusal contract: the source slice remains present without invented
structure.

Page numbers below are zero-based PDF file indices, as expected by the CLI.
`tools/golden/generalize.py` runs `diorthosis build`, measures its wall time,
runs `validate` and `roundtrip`, then re-ingests the identical pages to count
layers, entry splitting, grammar selection, and anchors. It prints both tables
below and a deterministic sample of up to five parsed entries per edition:

```console
python tools/golden/generalize.py
python tools/golden/generalize.py --only insolubles --samples 5
```

“Parsed %” and “refused %” use split apparatus entries as the denominator.
“Anchored %” is the number of entries with a text-band anchor divided by the
same denominator; it is independent of parse status. A parsed sample passes the
fabrication check only if its lemma, reading segmentation and text, and witness
attributions are all supported by the extracted apparatus at the granularity
of one real apparatus entry. Recasting a fontes paragraph as a lemma, retaining
a following `lemma]` inside a reading, or treating a heading as another reading
is a false structural claim even though its characters occur in the PDF.

Up to five samples per edition were chosen by the driver's fixed
SHA-256-derived seed and checked manually against their exact `source_slice`;
representative rendered pages established each band's visual convention. This
is a fabrication spot-check, not the double annotation study proposed below.

## Locating the edition pages and sigla

Page ranges were found first with pdfminer text probes for section headings,
language/script changes, and terminal index/translation headings, then checked
on rendered pages. Alternating source/translation pages were filtered to the
source language. The CLI conspectus bootstrap found zero witnesses on each of
the three explicit conspectus pages, so the exact printed witness sigla were
also passed through the documented `--sigla` option; this is declared input,
not parser tuning.

| Edition | Selected edition pages and how found | Conspectus / declared sigla | Band observation |
|---|---|---|---|
| Walter Segrave, *Insolubilia* | `30,32,...,148` (60 pages); Latin and English alternate after the manuscript discussion, and rendered Latin pages contain the critical band | PDF 25–26, “The Manuscripts and the Edition”: `E4`, `E8`, `O`; `--conspectus-page 25 --sigla E4,E8,O` | Latin text with a compact reledmac `line lemma] reading sigla` band |
| Giovanni Britannico, Persius commentary | `160-433` (274 pages); the edited commentary begins at 160 and the index begins at 434 | No titled single conspectus; PDF 154–155 explicitly defines `a`, `b`, `c`, passed with `--sigla` | Two bottom tiers: `vv.ll. Brit.` variants and `Fontes` parallels |
| Herodian, Books I–II | `378,380,...,432;452,454,...,506` (56 pages); `SIGLA` is at 376, `LIVRE I` at 377, and Greek source pages alternate with French translation | PDF 376: `A`, `B`, `V`, `G`, `F`, `L`, `Io`; `--conspectus-page 376` plus those exact `--sigla` values | Budé-style run-in Greek apparatus using locus, colon, and `\|\|` |
| Iacopone da Todi, *Laudario* | `122-126,142-165,174-176,188-189,209-215,226-227,247-250,265-266` (49 pages); “TESTI CRITICI” occurs at 106 and the eight rendered critical-text runs were selected | No single conspectus; “MANOSCRITTI UTILIZZATI” at 50–55 prints `As,Be,H,Ch,Sp,Va,Vb,Ch’,B,Ash’,Lc,Cs,Mga,G,L,M,Br,N,Ox’,Pd’,P,Pr,O,A,A’,Ve,S,F,Ma,Mb,BON,TRES` | Large three-tier negative apparatus, generally `locus lemma] variants` |
| Blacasset | `115-262` (148 pages), the complete “Testi” section before the glossary/index | PDF 267, “INDICE DEI MANOSCRITTI”: `a1,A,B,C,D-Da-Dc,E,f,F,G,H,I,K,L,M,N,O,P,Q,S,T,U,V,VeAg,W`; `--conspectus-page 267` plus those exact `--sigla` values | Verse/stanza apparatus, but the tagged extraction duplicates adjacent page contents and interleaves text with commentary |
| G. B. Pigna, *Gli Heroici* | `44-127` (84 pages); the edited work starts at 44 and “TAVOLA” starts at 128 | No conspectus and no witness sigla | No critical apparatus band: explanatory scholarly footnotes only |
| Bisschop, *Universal Śaivism* | `72-153` (82 pages); the IAST critical edition starts at 72 and the English translation at 154 | No single conspectus; source inventory at 57–61 supplies flattened composite sigla `N7K7o,N8K2,N1K2,N4C5,N5K8,B9C9,Ś6S7,P3T2,P7T2,EN` | Source-parallel tier plus compact critical tier with composite superscript/subscript sigla |
| *Suśrutasaṃhitā* 1.16 | `58-67` (10 pages); the Sanskrit edition begins at 58 and the translation at 68 | No single conspectus; PDFs 46 and 56 define `K`, `N`, `H`, and `A` | Devanagari text with separately labelled witness, Su1938, and notes/variants tiers |
| Petrus Gracilis, b1q1 | `0-10` (11 pages), all pages of the locally generated PDF | The generated PDF prints no conspectus; no manual sigla | LombardPress double reledmac foot: fontes plus variants |

Only `la` and `grc` text-band models ship in v0.6. Italian, Occitan, Sanskrit
IAST, and Devanagari Sanskrit were therefore measured through `--text-lang la`
as requested. This limitation is part of the result.

The optional Gracilis case was included. The sibling `pg-b1q1.xml` was built
with the same pinned `tools/golden/plaoul_build_pdf.py` and its existing
toolchain; the only content parameterization was one assignment (well below
the ten-line ceiling):

```python
import sys

from tools.golden import plaoul_build_pdf as p
p.TEI_RAW = "file:///tmp/gracilis_verify/pg-b1q{n}.xml"
sys.argv = ["plaoul_build_pdf.py", "/tmp/gracilis_generalization", "1"]
p.main()
```

It is labelled “same-toolchain unseen content,” not an independent publisher
convention.

## Results

| Edition | Language | Convention family | PDF pages (0-based) | Pages | Entries | Parsed % (by grammar) | Refused % | Anchored % | Fabrication check | Notes |
|---|---|---|---|---:|---:|---|---:|---:|---|---|
| Walter Segrave, *Insolubilia* | Scholastic Latin | paragraph reledmac | `30,32,...,148` | 60 | 923 | 98.5% (paragraph 908, marker 1) | 1.5% | 90.7% | **CRITICAL FAIL: 4/5 false** | `\|\|`-joined later lemmas remain inside readings |
| Britannico, Persius commentary | Humanist Latin | two-tier `vv.ll.` / fontes, colon | `160-433` | 274 | 343 | 29.2% (marker 68, paragraph 32) | 70.8% | 2.0% | **CRITICAL FAIL: 5/5 false** | sampled fontes or merged tiers became lemmas |
| Herodian, Books I–II | Ancient Greek | Budé locus + colon + `\|\|` | two alternating runs | 56 | 74 | 73.0% (marker 54) | 27.0% | 0.0% | **CRITICAL FAIL: 5/5 false** | whole page bands became one structured entry |
| Iacopone, *Laudario* | Medieval Italian | three-tier negative apparatus | eight runs, `122-266` | 49 | 146 | 61.6% (paragraph 90) | 38.4% | 0.0% | **CRITICAL FAIL: 5/5 false** | tiers and successive lemmas were merged |
| Blacasset | Occitan | stanza/verse `lemma]`, internal `\|` | `115-262` | 148 | 53 | 15.1% (marker 8) | 84.9% | 0.0% | **CRITICAL FAIL: 5/5 false** | tagged-page duplication/layer failure; validate fails |
| Pigna, *Gli Heroici* | 16th-c. Italian | no critical apparatus | `44-127` | 84 | 66 | 18.2% (marker 12) | 81.8% | 0.0% | **CRITICAL FAIL: 5/5 false** | prose/footnotes became lemmas; copy flag was ignored |
| Bisschop, *Universal Śaivism* | Sanskrit IAST | compact composite-siglum, multi-tier | `72-153` | 82 | 82 | 0.0% (none) | 100.0% | 0.0% | N/A: 0 parsed | wholesale verbatim refusal; no structure to fabricate |
| *Suśrutasaṃhitā* 1.16 | Sanskrit, Devanagari | stacked `lemma]` tiers | `58-67` | 10 | 254 | 76.4% (paragraph 194) | 23.6% | 39.8% | **CRITICAL FAIL: 1/5 false** | four samples faithful; one heading became a reading; roundtrip fails |
| Petrus Gracilis, b1q1 | Scholastic Latin | LombardPress double reledmac | `0-10` | 11 | 18 | 5.6% (marker 1) | 94.4% | 0.0% | **CRITICAL FAIL: 1/1 false** | sole parse was a fontes paragraph |

### Layer and integrity diagnostics

Layer counts are `blocks` and, after the slash, distinct `pages` containing
that layer. “App. chars” is the extracted apparatus-layer character count.
Wall time measures only the public CLI build on this machine on 2026-08-04;
it excludes the diagnostic re-ingest, validation, and roundtrip commands.

| Edition | Layer blocks / pages | App. chars | Anchored / unanchored / ambiguous | Validate | Roundtrip | CLI wall |
|---|---|---:|---:|---|---|---:|
| Insolubilia | apparatus 60/60; heading 18/10; text 78/60 | 38,724 | 837 / 86 / 0 | PASS | PASS | 1.58 s |
| Britannico | apparatus 271/271; heading 149/74; notes 137/137; running head 96/96; text 384/274 | 84,581 | 7 / 336 / 0 | PASS | PASS | 14.14 s |
| Herodian | apparatus 56/56; heading 1/1; page number 56/56; running head 1/1; text 56/56 | 39,226 | 0 / 74 / 0 | PASS | PASS | 8.15 s |
| Iacopone | apparatus 49/49; heading 7/4; page number 49/49; running head 2/2; text 54/49 | 164,515 | 0 / 146 / 0 | PASS | PASS | 18.68 s |
| Blacasset | apparatus 53/53; heading 279/146; page number 144/144; running head 4/4; text 278/148 | 58,661 | 0 / 53 / 0 | **FAIL** | PASS | 8.14 s |
| Pigna | apparatus 65/65; page number 81/81; running head 76/76; text 81/81 | 42,009 | 0 / 66 / 0 | PASS | PASS | 15.29 s |
| Universal Śaivism | apparatus 82/82; heading 11/5; page number 40/40; running head 82/82; text 92/82 | 153,294 | 0 / 82 / 0 | PASS | PASS | 5.61 s |
| Suśruta | apparatus 10/10; heading 1/1; page number 1/1; running head 10/10; text 10/10 | 12,417 | 101 / 153 / 0 | PASS | **FAIL** | 6.93 s |
| Gracilis | apparatus 9/9; page number 10/10; running head 11/11; text 11/11 | 2,541 | 0 / 18 / 0 | PASS | PASS | 3.90 s |

Blacasset's validation failure comprises 72 `I7` duplicate-folio violations.
The tagged PDF exposes the same visible-page text on adjacent PDF pages, which
also explains duplicated deterministic samples and inflated heading/text block
counts. Suśruta's roundtrip failure comprises six main-text differences in
Devanagari spacing or glyph adjacency; its Markdown validation passes.

## What generalized, what refused, and what fabricated

The four shipped families are generic marker/colon, verse, DLL-style line, and
paragraph/reledmac. In this sample only the generic marker and paragraph
grammars fired. The reledmac-like Insolubilia and Devanagari `lemma]` apparatus
are closest to an implemented family. Insolubilia consequently reaches 98.5%
parse and Suśruta 76.4%, but high parse rate is not correctness: internal
multi-lemma separators in Insolubilia and a tier heading in Suśruta produce
false structures. No sampled edition exercised a faithful verse or DLL-line
parse.

Britannico and Iacopone have superficially familiar delimiters but foreign
multi-tier organization. Herodian's run-in Budé convention uses colons and
`\|\|` at a granularity the generic grammar does not model. Blacasset fails
earlier at tagged-page extraction and layer separation. Pigna has no critical
apparatus at all, so its 12 parses are unequivocal false positives. The compact
composite-siglum Śaiva convention is absent from the four families and is the
cleanest refusal result: all 82 extracted page-sized entries remain verbatim,
with no fabricated structure.

| Edition | One-sentence family assessment |
|---|---|
| Insolubilia | The paragraph/reledmac family exists in v0.6, but this edition's `\|\|`-joined multiple lemmas are only partially modeled. |
| Britannico | Its combined `vv.ll.` and fontes two-tier family does not exist; generic marker parsing is only a superficial delimiter match. |
| Herodian | Its page-run Budé colon/`\|\|` family does not exist at the edition's entry granularity. |
| Iacopone | Its three-tier negative-apparatus family does not exist, despite sharing `lemma]` with the paragraph grammar. |
| Blacasset | Verse parsing exists nominally, but this tagged extraction does not deliver the stanza apparatus cleanly enough to exercise it. |
| Pigna | Not applicable: the selected edition has no critical apparatus band. |
| Universal Śaivism | Its composite-siglum, multi-tier Sanskrit family does not exist. |
| Suśruta | The paragraph `lemma]` family exists and handles many entries, but not the stacked tier boundaries. |
| Gracilis | Paragraph/reledmac exists, but the double fontes/variant foot as extracted is not faithfully covered. |

The fabrication check is therefore a critical finding. It failed in every
edition with parsed output. Specifically:

- Insolubilia: four of five samples correctly began with a real first lemma but
  absorbed one or more later `\|\| lemma] reading` units as readings of it; the
  fifth sample (`p120-e0`) was faithful.
- Britannico: all five samples structured fontes citations or combined tiers as
  lemmas/readings.
- Herodian: all five samples treated a page-sized sequence of distinct variants
  as one lemma with many readings and generally left witness strings inside
  reading text.
- Iacopone: all five samples crossed tier and entry boundaries; some local
  reading/witness pairs were real, but the enclosing lemma/readings structure
  was not.
- Blacasset: all five samples were verse text or commentary mislayered as
  apparatus, including duplicated adjacent-page content.
- Pigna: all five samples were explanatory prose or references, not apparatus.
- Suśruta: four samples had real lemmas, readings, and witnesses; `p67-e7`
  appended “Variants from Su 1938” as a second reading.
- Gracilis: its only parse was a fontes paragraph, not a variant.
- Universal Śaivism: no parses existed to sample; no fabrication was found.

These spot checks do not estimate correctness rates. They demonstrate that
schema-valid and roundtrip-stable output can still be philologically false and
motivate the protocol below.

## Inter-annotator protocol for future human validation

This section is a protocol for Romain and a colleague to execute. No annotation
or agreement result is claimed here.

### Sampling

The primary population is each edition's parsed entries. For a 95% confidence
interval with a worst-case proportion of 0.5 and margin of error ±10 percentage
points, the infinite-population requirement is
`n0 = 1.96² × 0.5 × 0.5 / 0.10² = 96.04`. Apply the finite-population correction
and round up: `n = ceil(N × 96.04 / (N - 1 + 96.04))`. Use a recorded
cryptographic seed and sample without replacement, stratified proportionally by
grammar with at least one entry from each grammar that fired. The resulting
sample sizes for this run are:

| Edition | Parsed population N | Double-annotated parsed sample n |
|---|---:|---:|
| Insolubilia | 909 | 87 |
| Britannico | 100 | 50 |
| Herodian | 54 | 35 |
| Iacopone | 90 | 47 |
| Blacasset | 8 | 8 (census) |
| Pigna | 12 | 11 |
| Universal Śaivism | 0 | 0; report “not estimable” |
| Suśruta | 194 | 65 |
| Gracilis | 1 | 1 (census) |

To validate the refusal side separately, also double-annotate 30 randomly
selected refused entries per edition, or all refused entries when fewer than
30. This secondary audit asks whether verbatim refusal was appropriate; it is
not included in the parse-correctness confidence interval.

### Annotation unit and decisions

The unit is one stable apparatus entry, `p{PDF-page}-e{entry}`. Before starting,
freeze the PDF, build outputs, sample manifest, seed, and diorthosis revision.
Each annotator works independently and sees the rendered apparatus crop, raw
extracted source slice, and proposed parse. Neither sees the other's labels.

For every parsed entry, independently label each field `correct`, `incorrect`,
or `unsure`:

1. **Lemma:** exact lemma text and entry boundary correspond to the band; a
   locator is not silently promoted to lemma text.
2. **Readings:** all reading texts, omission/addition semantics, segmentation,
   and completeness are correct; a second lemma, tier heading, or prose note is
   not a reading.
3. **Witnesses:** lemma and reading witness/editor attributions are complete and
   attached to the correct object.

The derived overall label is `correct` only when all three fields are correct,
`incorrect` when any field is incorrect, and `unsure` otherwise. “Unsure” is a
real outcome, never silently dropped or converted to agreement. For refused
entries, choose either `verbatim` (refusal is appropriate) or supply a complete
parse; use `unsure` when the PDF itself does not support a defensible choice.

### Files and review UI

Each annotator exports a separate file from the existing review UI, for example
`overrides.romain.json` and `overrides.colleague.json`. Check “include” for
every sampled entry. Preserve the exact `overrides.json` shape already emitted
by the UI: `action: parse` with lemma/readings/witness fields when the entry can
be structured, or `action: verbatim` when it cannot. For a correct proposed
parse, include it unchanged so that every sampled key is represented. Put the
three judgments and overall judgment in the existing string `note` field using
this controlled prefix:

```json
{
  "<entry-key>": {
    "action": "parse",
    "lemma": "<verified-or-corrected lemma>",
    "lemma_wits": [],
    "lemma_editors": [],
    "lemma_qualifiers": [],
    "readings": [],
    "comments": [],
    "note": "IA1; lemma=correct; readings=incorrect; witnesses=unsure; overall=incorrect; reason=<brief evidence>"
  }
}
```

The example is a schema illustration, not an annotation. Do not add a new
top-level study schema: retaining the review UI's replayable override format
keeps corrections inspectable and applicable by `diorthosis build
--overrides`.

### Agreement, adjudication, and reporting

Freeze both independent files before comparison. Report, for each edition and
for a pooled micro-average, the label counts, strict overall correctness rate,
95% Wilson interval, `unsure` rate, raw agreement, and unweighted Cohen's kappa
for lemma, readings, witnesses, and derived overall label. Kappa is computed on
the three pre-adjudication categories. If a field has no between-entry category
variation and kappa is undefined, report `NA` plus raw agreement rather than
forcing a number. Add a 95% percentile interval from 2,000 entry-level bootstrap
resamples within each edition.

Only after those values are frozen do the two annotators discuss disagreements
with the PDF and edition's stated convention in view. Record the agreed
correction in `overrides.adjudicated.json`. If discussion does not resolve a
case, retain `unsure`; if a third qualified editor is available, that person may
break the tie, but the original labels and pre-adjudication kappa remain in the
report. Publish both independent override files, the adjudicated file, the
sample manifest/seed, and the calculation script so the study can be replayed.
