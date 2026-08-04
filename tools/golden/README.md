# The golden harness — scholar-encoded ground truth, zero apparatus errors

The strongest test diorthosis has: apparatus entries **encoded by scholars**
(TEI editions with real `<app>/<lem>/<rdg>`) are re-typeset into a
born-digital critical-edition PDF, diorthosis compiles that PDF back, and
the output TEI must reproduce the scholars' apparatus **exactly** — every
lemma, reading, witness, editor, verbatim string and anchor.

    scholar TEI ──tei_to_edition.py──▶ edition JSON
    edition JSON ──typeset_golden.py──▶ paginated .tex + golden.json
    tectonic ──▶ born-digital PDF (conspectus page + text + numbered band)
    diorthosis build ──▶ TEI + md
    check_golden.py: TEI vs golden.json ──▶ 0 errors or FAIL

Run everything with one command:

    ./fetch_sources.sh                       # once: download the TEI sources
    python3 run_golden.py data/balex.xml  work/balex  --text-lang la --rng tei_all.rng
    python3 run_golden.py data/sblgnt.xml work/sblgnt --rng tei_all.rng

The bar is asymmetric, matching the tool's honesty contract: a **wrong**
structure (phantom entry, wrong lemma/reading/witness/editor, misplaced
anchor, altered verbatim, dangling IDREF) fails the run; a **missing but
honest** structure (entry kept as a verbatim note, entry left unanchored)
is a reported gap, never a failure.

Ground-truth integrity rules:

- the apparatus CONTENT flows unchanged from the scholars' TEI; only the
  serialization to a printed convention (numeric superscript markers,
  ``N Lemma : reading SIGLA`` band, conspectus siglorum page) is ours;
- every `<app>` the adapter cannot represent faithfully is SKIPPED AND
  COUNTED (nested apps, rdgGrp, discontinuous span lemmas,
  punctuation-variant lemmas) — the golden never contains a guess;
- pagination is composed deterministically (never left to TeX) and a page
  count guard fails the run if the typeset ever overflows.

Corpus status (2026-08-04, v0.6):

| edition | language | entries | result |
|---|---|---|---|
| Bellum Alexandrinum (LDLT, Damon) | Latin | 524 | **0 errors, 0 gaps** |
| SBLGNT (Holmes 2010, TEI re-encoding) | Greek | 6 906 | **0 errors, 0 gaps** |
| Problemata XIX (LDLT, Mutch) | Medieval Latin | 5 524 | **0 errors**, 47 gaps
(honest refusals, stable since v0.5) |
| Plaoul lectio1-30 (SCTA, Witt) — real toolchain PDF | Medieval Latin | 6 293 | **0 errors** (plaoul_check.py) |

The `data/` directory is gitignored: diorthosis ships no edition content;
the corpus is reproducible from `fetch_sources.sh` (CC BY / CC BY-SA
sources).

## Real-PDF ground truth (`real_check.py`)

The typeset harness controls the layout; `real_check.py` does not: it runs
diorthosis on the edition **as actually printed** (the DLL's own
`ldlt-balex.pdf`, the official SBLGNT PDFs) and aligns the result against
the scholars' TEI by content. Measured (2026-08-04): balex 93.9 % text /
96.8 % band, SBLGNT Matthew 97.0 % / 100.0 %. The fail-closed production-path
check is deliberately RED: with each rejected reading searched only in its
own uniquely located lemma window (±100 folded characters), balex reports
45/518 contamination candidates and Matthew 12/480; false structures are
21/336 and 4/758 respectively. Every contamination candidate prints its full
marked window, while unassigned/ambiguous loci remain in the skip accounting.

    python3 real_check.py data/balex.xml balex-dll.pdf --pages 84-171 --text-lang la
    python3 real_check.py data/sblgnt.xml 61-SBLGNT-Matthew.pdf --max-apps 770

The line-referenced STRUCTURED check on the same real balex PDF (563
scholar apps = 0 errors, 100 % anchored) — note the canonical page range
STARTS AT 82 (pages 82-83 carry chapters 1-2) and the conspectus
siglorum lives on page 54:

    python3 -m diorthosis.cli build ldlt-balex.pdf --pages 82-171 \
        --conspectus-page 54 --text-lang la -o out/
    python3 line_check.py data/balex.xml out/ldlt-balex.tei.xml \
        --known balex_known_divergences.json

## The third real-backtesting case: Petrus Plaoul (double apparatus)

The Plaoul *Commentary on the Sentences* (ed. Jeffrey C. Witt,
scta-texts/plaoulcommentary) carries ~6,300 `<app>` entries concentrated
in lectio1–30, collated against four witnesses (R V S SV) with genuine
scholastic typology (om., add., interl., in marg., corr. ex, iterum,
multi-way lectiones). No published PDF exists, but the project's own
print toolchain does — lombardpress/lbp-print-xslt → reledmac — and
`plaoul_build_pdf.py` runs THAT toolchain (three environment patches
documented in its docstring), producing a byte-deterministic PDF whose
page shows reledmac's standard paragraphed DOUBLE apparatus: fontium on
top, variants below, in the "N lemma] rdg SIG" convention (distinct from
the DLL's "∥ … | …" style). Selected 2026-08-04 after a systematic sweep
(LDLT, LombardPress/SCTA, PTA, HAB Wolfenbüttel, ENC, RIDE reviews);
runner-up kept in reserve: the Suśruta Project's Sū.1.16 (published
born-digital PDF at HASP + TEI, 212 apps, Sanskrit — outside the
Greek/Latin domain).

    python3 plaoul_build_pdf.py workdir/ 1        # lectio1: 235 apps
    python3 plaoul_build_pdf.py workdir/ {1..30}  # ~6,300 apps

**License note:** the Plaoul TEI is CC BY-NC-ND 3.0 — the harness
fetches it at use and never commits or redistributes edition content
(same fetch-at-use contract as the rest of `data/`); the generated PDF
stays local. The harness itself ships no Plaoul edition content beyond short apparatus excerpts quoted for documentation and unit-test fixtures (scholarly citation of individual readings).

Status (2026-08-04, v0.6): **looped to zero — 6,293 apps across all 30
lectios, 0 errors** (`plaoul_check.py lectioN.xml lectioN.pdf`, per-app
comparison of lemma, reading count, reading texts and witness sets under
the project's own critical.xslt rendering contract — with that contract's
tolerances stated plainly: folded normalization, elliptic lemmas matched
on their pre-ellipsis prefix, witness sets checked scholar-side
(extra witnesses on our side would not fail), alignment by global order;
this validates the stylesheet's rendered subset, not full TEI semantics). Anchoring 5,969/6,293
(94.9 %). Key contract points learned from the print: leaked English
editorial notes DO print (the XSLT's note-silencing template is commented
out); elliptic printed lemmas match on the pre-ellipsis prefix only (the
suffix goes through typesetter transforms the TEI cannot model);
`@wit` tokens without `#` ("3V", "EV") print verbatim as de-facto sigla;
a duplicated siglum in a witness run is reading text, run-initial =
same reading, mid-run = next reading.
