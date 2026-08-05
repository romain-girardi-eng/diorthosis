# Out-of-the-box generalization: v0.6 baseline, v0.7 convention gating, and the wave A fabrication

## Scope and method

This document reports two measurements, not a tuning exercise. The baseline
measures diorthosis 0.6.0 at Git revision
`6102801ccd20811a32120793560b225abb555d7d` on eight reviewer-supplied,
never-seen born-digital editions and one optional same-toolchain,
unseen-content case; no grammar, threshold, override, parser source, or test
was changed for that run. The post-gating run holds every input and option
fixed and changes only convention dispatch/refusal. The command-line options
in both runs are limited to page selection, the shipped `la` or `grc`
text-band model, a printed conspectus page, and sigla transcribed unambiguously
from front matter. Thus a refusal is a successful application of the
verbatim-refusal contract: the source slice remains present without invented
structure.

The post-gating table was re-derived on the 1.0 wave A tree (`bd01130`) on
2026-08-05 and is unchanged, edition by edition, from the v0.7 run recorded
below. Two things about the harness itself changed with wave A and are stated
here because they affect how the table must be read. First, `generalize.py`
now passes `--ignore-self-check`: since wave A a `build` refuses to exit 0 on
a result its own validator rejects, and Blacasset's tagged PDF is exactly such
a result — a build the tool refuses to certify is a ROW of this table, not a
missing row, and the refusal is reported in the Validate column. Second, and
more important, **the fabrication column below measures only the pages this
study selected**; §"The fabrication the table could not see" records a
marker-path fabrication that lived on pages it excluded.

Page numbers below are zero-based PDF file indices, as expected by the CLI.
`tools/golden/generalize.py` now runs the v0.7 gated production path, measures
its wall time,
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

### v0.6 baseline (before convention gating)

This table is intentionally retained unchanged: it is the measured failure
that motivated the gate, and provides the before side of the comparison.

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

### v0.7 post-gating remeasurement

The identical PDFs, page selections, declared sigla, and five-sample protocol
were rerun after adding whole-band convention gates. No edition-specific
signal participates in a gate. A refused band retains its exact source slices;
the paragraph/line/verse split views are retained only to keep the review work
queue stable, and no refused trial parse is emitted as `<app>` structure.

| Edition | Language | Convention family | PDF pages (0-based) | Pages | Entries | Parsed % (by grammar) | Refused % | Anchored % | Fabrication check | Notes |
|---|---|---|---|---:|---:|---|---:|---:|---|---|
| Walter Segrave, *Insolubilia* | Scholastic Latin | paragraph reledmac, `\|\|` variant | `30,32,...,148` | 60 | 923 | 2.2% (paragraph 20) | 97.8% | 2.1% | **PASS: 5/5 faithful — on these pages only\*** | all 903 entries in bands containing unconsumed `\|\|` refused; only locally separator-free bands parsed |
| Britannico, Persius commentary | Humanist Latin | two-tier `vv.ll.` / fontes, colon | `160-433` | 274 | 343 | 0.0% (none) | 100.0% | 0.0% | N/A: 0 parsed | wholesale verbatim refusal |
| Herodian, Books I–II | Ancient Greek | Budé locus + colon + `\|\|` | two alternating runs | 56 | 74 | 0.0% (none) | 100.0% | 0.0% | N/A: 0 parsed | numeric-marker splitting/resolution signature absent |
| Iacopone, *Laudario* | Medieval Italian | three-tier negative apparatus | eight runs, `122-266` | 49 | 146 | 0.0% (none) | 100.0% | 0.0% | N/A: 0 parsed | closing-lemma density is incompatible with paragraph entries |
| Blacasset | Occitan | stanza/verse `lemma]`, internal `\|` | `115-262` | 148 | 53 | 0.0% (none) | 100.0% | 0.0% | N/A: 0 parsed | no resolved numeric-marker pipeline |
| Pigna, *Gli Heroici* | 16th-c. Italian | no critical apparatus | `44-127` | 84 | 66 | 0.0% (none) | 100.0% | 0.0% | N/A: 0 parsed | explanatory notes stay verbatim |
| Universal Śaivism | Sanskrit IAST | compact composite-siglum, multi-tier | `72-153` | 82 | 82 | 0.0% (none) | 100.0% | 0.0% | N/A: 0 parsed | remains 100% refused |
| *Suśrutasaṃhitā* 1.16 | Sanskrit, Devanagari | stacked `lemma]` tiers | `58-67` | 10 | 254 | 0.0% (none) | 100.0% | 0.0% | N/A: 0 parsed | short tier preambles or unattributed trial segments refuse each band |
| Petrus Gracilis, b1q1 | Scholastic Latin | LombardPress double reledmac | `0-10` | 11 | 18 | 0.0% (none) | 100.0% | 0.0% | N/A: 0 parsed | extracted bands lack a strong complete paragraph or marker signature |

**\*** The fabrication column is bounded by the page selection of its own row.
On the *Insolubilia*'s EXCLUDED odd (English) pages, v0.7 emitted an English
editorial footnote as a `<lem>`/`<rdg>` variant at exit 0; wave A closed that
and emits zero structure there. See “The fabrication the table could not see”.

The post-gating integrity checks stayed PASS except for Blacasset's pre-existing
72 duplicate-folio `I7` violations. Suśruta's post-gating roundtrip is now
PASS because the foreign tier structure is no longer emitted. Anchoring also
drops with refusal: a rejected convention is not reused to make a structural
lemma-to-text claim. Since wave A, Blacasset's `I7` failure also makes its
build refuse to certify itself (exit 1); `generalize.py` passes
`--ignore-self-check` so the row is measured and the failure is reported in the
Validate column rather than removing the edition from the study.

#### Gate designs and thresholds

- **Numeric marker / generic grammar.** A band must contain entries opened by
  the numeric-marker splitter and at least one of those marker numbers must
  resolve against the page's text layer. `parse_entry` is dispatched only for
  those marker-produced entries; a preamble or a band split by another grammar
  is ineligible. The whole band refuses on `\|\|`, `∥`, an unmatched `]`, more
  than 60% trial-unconsumed tokens, or fewer than half of marker entries parsing
  in trial. The 60% ceiling is deliberately the loosest threshold: Bobichon has
  one structurally consistent five-entry band with four successful entries and
  one long narrative refusal (57.5% of its tokens), while every measured
  foreign marker candidate fails the mandatory resolved-marker signal.
- **Verse-referenced.** Splitting must produce verse entries; `\|\|`, `∥`,
  and spaced `|` are foreign. Orphan `]` closers beyond the split boundaries
  are tolerated up to a fifth of the entries (strict bracket-balance equality
  refused the legitimate Jn 7:52 band, whose pericope-sized reading carries
  editorial brackets). The unconsumed-token ceiling (10%) only convicts when
  fewer than 60% of the entries parse — one giant honestly-refused entry must
  not condemn a band whose other entries parse cleanly (Jn 7:52 again). At
  least 90% of lemma/reading sides must carry edition sigla. Matthew is
  stronger than the thresholds: all 827 extracted entries trial-parse and
  every side is attributed.
- **DLL line-referenced.** The `∥` entry and spaced `|` reading signature must
  yield at least two entries. `\|\|` and `•` are foreign; at most 20% of trial
  tokens may be unconsumed, and at least 60% of parsed sides must carry a
  witness/editor/qualifier attribution. The real balex band set trial-parses
  563/563 entries and attributes 1,476/1,486 sides; the lower attribution
  threshold permits its documented editorial-narrative sides without making
  bare fontes prose look like variants.
- **Paragraph reledmac.** A band needs at least two numbered `lemma]`
  boundaries and no `\|\|`, `∥`, spaced `|`, or `•`. Orphan `]` closers
  beyond the split boundaries are tolerated up to a fifth of the entries
  (strict bracket-balance equality refused legitimate Plaoul lectios whose
  bands carry an editorial `[` or a fontium locus). A short non-numeric preamble is treated as a tier
  heading rather than a fontes tier. Trial parsing may leave at most 20% of
  tokens unconsumed and may leave no nonempty reading segment without a
  witness or operator. In the checked Plaoul lectios every candidate entry
  trial-parses and no reading is unattributed; the closing-density check
  separates Iacopone, and the preamble/unattributed checks separate Suśruta.

Each refusal is stored on every affected `ApparatusEntry` as a band-level
evidence string naming the gate and measured reason. The review UI displays it,
and `tools/golden/generalize.py` carries it into the refusal counts.

#### Validated-family invariance after the gate change

| Target | Post-gating result (re-derived 2026-08-05 at `bd01130`) |
|---|---|
| Plaoul lectio 1 / 5 / 14 / 22 | 235 / 188 / 304 / 271 compared; **0 errors each** (all 30 lectios: 6,293 compared, 0 errors, anchored 5,969/6,293 = 94.9%) |
| Real DLL balex line grammar | 563 compared; **0 errors, 0 gaps, 17 typed divergences; 563/563 anchored — 515 attached, 48 end-only** |
| Retypeset balex golden | 524 compared; **0 errors, 0 gaps** |
| Retypeset SBLGNT golden | 6,906 compared; **0 errors, 0 gaps** |
| Retypeset *Problemata* golden | 5,524 compared; **0 errors, 50 gaps** (47 at v0.6; the three added by the gate are named in `tools/golden/README.md`) |
| Real SBLGNT Matthew verse grammar | 822 compared; **0 errors** |
| Whole real NT, source-complete oracle | 6,797 compared, **0 errors**, 59 typed divergences; partition 6,797 + 61 refused + 60 uncovered + 3 unaccounted = 6,921 = source total |
| Bobichon marker grammar, pages 188–560 | 2,031 entries; **99.3% anchoring, 99.0% parse, 97.5% concordance, 89.9% attribution**; 186/186 marker bands accepted by the gate |

“563/563 anchored” is not “100% attached”. diorthosis anchors by internal
double-end-point attachment; 48 of the 563 balex entries carry `@to` only,
because the start of the lemma span could not be located. Until wave A the
build reported the aggregate alone, and that single number was the coverage
claim this document should never have quoted unqualified.

#### Post-gating fabrication spot-check

Only *Insolubilia* retained parsed samples. The five deterministic keys were
checked against both their exact source slices and rendered pages:
`p40-e1` (`istud] quod add. E8`), `p50-e3` (`mentitur] mentitus E8`),
`p50-e4` (`probabilius] probabiliter E4`), `p66-e3`
(`quia] quare E8`), and `p66-e5` (`super hoc] semper E4`) are all faithful in
lemma, reading segmentation/text, and attribution. Verdict: **5/5 faithful,
zero fabricated structures**. The other eight editions have zero parsed
entries, hence no proposed structures to sample and no possible fabrication in
the parsed-sample population. Re-derived at `bd01130`: the same five keys, the
same five source slices, the same five parses.

That verdict is exactly as wide as its population — *parsed entries on the
selected pages*. It says nothing about the pages the study did not select, and
that is where the next section found a fabrication.

#### The fabrication the table could not see

**Status: found after v0.7, closed in wave A (`bd01130`), reproducible below.**

An adversarial assessment built the *Insolubilia* on pages this study
excludes. The PDF prints Latin on even pages and the English translation, with
numbered English editorial footnotes, on odd pages; the study selects
`30,32,...,148`. On page 63 — odd, hence never measured here — the generic
numeric-marker grammar accepted a band of two English footnotes and emitted
footnote 47 as an apparatus variant: `<app n="47">` with the note's opening
sentence as `<lem>` and its quotation of Bradwardine's second postulate as
`<rdg>`, plus four `(cid:105)` fragments as `<note type="comment">`. The TEI
was schema-valid, `validate` and `roundtrip` passed, and the build exited 0.

The mechanism is worth stating because it is the failure mode this whole
document exists to detect: numbered editorial prose reproduces the numeric
marker convention's *entire printed shape* — a superscript number glued to a
word, a colon inside the sentence — so shape alone cannot separate it from an
apparatus. What it never carries is sigla. The gate now requires that at least
one reading somewhere in an accepted band name a witness, an editor or a cited
version. It is a whole-band floor deliberately: the entry-level version of the
rule was tried and reverted, because editions collated against a single witness
print bare readings by design; the release record puts the cost of the
entry-level variant at six points of Bobichon parse rate (99.0 → 93.0), a
figure carried over from that adjudication and not re-derived here.

Reproduce, on the 60 English pages of the same PDF:

```console
$ pages=$(python3 -c "print(','.join(str(p) for p in range(31,150,2)))")
$ python3 -m diorthosis.cli build /tmp/gen10/insolubles.pdf \
      --pages "$pages" --text-lang la -o out/
```

| tree | `<app>` emitted | `<rdg>` | verbatim apparatus notes | exit |
|---|---:|---:|---:|---|
| v0.7.0 (`b7c85b4`) | **1** | **1** | 118 | 0 |
| wave A (`bd01130`) | 0 | 0 | 119 | 0 |

At `bd01130` the same run prints its refusals by class — 83 bands on the
unconsumed-token ceiling, 24 with no marker boundary, 9 below the trial-parse
majority, **2 on the new attribution floor**, 1 with no resolved marker — and
`coverage: 119 entries — 0 parsed, 119 refused, 0 unparsed`.

Cost, measured: the gate is inert on everything already certified. Bobichon
pages 188–560 keep 186 of 186 marker bands accepted and all four
self-validation metrics identical to v0.6 (99.3 / 99.0 / 97.5 / 89.9); the
nine-edition table above is unchanged; and the three retypeset goldens — which
all print the numeric-marker convention, so all traverse the gate that
changed — are unchanged at balex 524 = 0 errors / 0 gaps, SBLGNT
6,906 = 0 / 0, *Problemata* 5,524 = 0 errors / 50 gaps.

Two lessons this document should carry forward. A fabrication check is bounded
by its sampling frame, and a page selection chosen to isolate the edited text
is a sampling frame — a future run of this study should include a slice of each
edition's *non-apparatus* matter (translation pages, footnote apparatus,
front matter) precisely because that is where a grammar has nothing true to
find. And "schema-valid, round-trip stable, exit 0" was already known here not
to imply "philologically true"; it now also does not imply "not fabricated".

**Precise TODO — separate workstream:** add the *Insolubilia* paragraph
variant in which `\|\|` opens another `lemma]` unit inside the same numbered
line entry. That extension must consume every separator, split and trial-parse
every unit, conserve its source slice, and receive its own positive/negative
corpus certification. Until then, any band containing `\|\|` refuses
wholesale; this gate must not be weakened to simulate support.

### v0.6 baseline layer and integrity diagnostics

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

## What generalized, what refused, and what fabricated in the v0.6 baseline

The four v0.6 families were generic marker/colon, verse, DLL-style line, and
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

The v0.6 fabrication check was therefore a critical finding. It failed in every
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

One more fabrication belongs in this ledger, found after the gates were built
and closed in wave A: on the *Insolubilia*'s English pages — outside every
page selection in this document — the generic marker grammar emitted an
English editorial footnote as a `<lem>`/`<rdg>` variant. It is recorded with
its reproduction under “The fabrication the table could not see”, and it is
the reason the discussion above must be read as *what fabricated on the
selected pages*, not *what fabricated*.

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

**That table sizes the v0.6 study and is retained for it. After gating the
populations invert, and so does the study.** At v0.7/wave A the parsed
population is 20 entries in *Insolubilia* (sample n = 17, a near-census) and
zero everywhere else, so a parse-correctness interval is not estimable for
eight of the nine editions. The population that now carries the result is the
REFUSED one — 1,939 entries — and its sizing under the same formula is:

| Edition | Refused population N | Double-annotated refused sample n |
|---|---:|---:|
| Insolubilia | 903 | 87 |
| Britannico | 343 | 76 |
| Herodian | 74 | 43 |
| Iacopone | 146 | 59 |
| Blacasset | 53 | 35 |
| Pigna | 66 | 40 |
| Universal Śaivism | 82 | 45 |
| Suśruta | 254 | 70 |
| Gracilis | 18 | 16 |

The question that study answers is not “is the parse right” but “was the
refusal appropriate, and what did it cost” — for each sampled entry, whether a
qualified editor could have produced a defensible structured parse from the
printed band alone. A refusal rate is only good news if the refused material
was genuinely out of reach; measuring that is the point, and it is not
measured yet. Pigna is the built-in control: it has no critical apparatus, so
every one of its 66 refusals must be judged appropriate or the gate is
mis-specified.

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
