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

**Interpreter note, measured the hard way.** These drivers put the repo's
`src/` on `sys.path` for their own imports, but the ones that shell out to the
CLI do not all pass it on. `run_golden.py`, `real_check.py`, `line_check.py`
and `plaoul_check.py` run from an uninstalled checkout; `sblgnt_nt_driver.py`
spawns `python -m diorthosis.cli` with `cwd=REPO` and no `PYTHONPATH`, so
against an interpreter with no diorthosis installed all 27 books fail with
`ModuleNotFoundError` — reported honestly (`6921 unexamined`, identity holds,
28 fatal failures, exit 1) but reported as nothing measured. Export it:

    PYTHONPATH=$(git rev-parse --show-toplevel)/src python3 sblgnt_nt_driver.py data work/nt

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

Corpus status (2026-08-05, v0.7.0 + wave A, re-derived on this tree):

| edition | language | entries | result |
|---|---|---|---|
| Bellum Alexandrinum (LDLT, Damon) | Latin | 524 | **0 errors, 0 gaps** |
| SBLGNT (Holmes 2010, TEI re-encoding) | Greek | 6 906 | **0 errors, 0 gaps** |
| Problemata XIX (LDLT, Mutch) | Medieval Latin | 5 524 | **0 errors**, 50 gaps (honest refusals; 47 at v0.6 — see below) |
| Plaoul lectio1-30 (SCTA, Witt) — real toolchain PDF | Medieval Latin | 6 293 | **0 errors**, anchored 5 969/6 293 = 94.9 % (plaoul_check.py) |

**The Problemata gap count moved 47 → 50 at v0.7 and has been stable since.**
Three entries changed side, each on a page (printed folios 61, 105, 477) whose
constituted text is a SINGLE opening phrase — `SED SICUT.1`,
`HUIUS AUTEM.1`, `QUIA QUEMADMODUM.1`. The geometric layerer reads that lone
short line as a running head, so the page carries no text/heading block at
all and the printed superscript `1` has nowhere to resolve. v0.6 emitted the
band as `<app>` anyway, with a lemma pointing at nothing (`app has no @to`);
v0.7's marker gate requires at least one marker resolved against the text
layer, so the whole band now stays a verbatim `<note type="apparatus">`
(`kept as verbatim note` + `note has no target`). Each of the three therefore
counts two gaps where it counted one: 47 + 3 = 50. Nothing was lost — the
printed band is retained byte for byte — and the structural claim that was
dropped was one the page could not support. Reproduce with:

    python3 run_golden.py data/problemata.xml work/problemata --text-lang la \
        --rng tei_all.rng | grep -E '^gap +p(61|105|477) '

The `data/` directory is gitignored: diorthosis ships no edition content;
the corpus is reproducible from `fetch_sources.sh` (CC BY / CC BY-SA
sources).

## Real-PDF ground truth (`real_check.py`)

The typeset harness controls the layout; `real_check.py` does not: it runs
diorthosis on the edition **as actually printed** (the DLL's own
`ldlt-balex.pdf`, the official SBLGNT PDFs) and aligns the result against
the scholars' TEI by content. Both declared limits now PASS on a stated
denominator — since wave A, a PASS requires an examined denominator at or
above `examination_floor` (a tenth of the ground truth), so "0 violations of
0 examined" reports NOT-PROVEN instead. Measured 2026-08-05 on this tree:

| run | text coverage | band coverage | contamination | false structures | verdict |
|---|---|---|---|---|---|
| balex, `--pages 82-171 --conspectus-page 54` | 530/555 = 95.5 % | 555/555 = 100.0 % | 0 / 527 examined | 0 / 321 examined | **PASS** (floor 56) |
| SBLGNT Matthew, `--max-apps 770` | 755/770 = 98.1 % | 770/770 = 100.0 % | 0 / 488 examined | 0 / 767 examined | **PASS** (floor 77) |

    python3 real_check.py data/balex.xml ldlt-balex.pdf --pages 82-171 \
        --conspectus-page 54 --text-lang la
    python3 real_check.py data/sblgnt.xml 61-SBLGNT-Matthew.pdf --max-apps 770

**Use the canonical balex range.** The older `--pages 84-171` invocation with
no `--conspectus-page` is a different measurement and it is reported here so
nobody re-derives it and thinks the harness regressed: it starts two pages
late, bootstraps a 5-witness registry instead of the printed 24 + 103 editors,
and the line grammar therefore refuses the whole band — 93.9 % text / 96.8 %
band, 0/518 contamination, and **0 of 0 production candidates examined, which
the harness now reports as NOT-PROVEN** rather than as a passing zero. A
limit that was never tested is not a limit that held.

Each rejected reading is searched only in its own uniquely located lemma
window (±100 folded characters); every contamination candidate prints its
full marked window, and unassigned or page-ambiguous loci stay visible in the
skip accounting instead of quietly leaving the denominator.

The line-referenced STRUCTURED check on the same real balex PDF (563 scholar
apps = 0 errors, 0 gaps, 17 documented divergences; **563/563 anchored — 515
attached, 48 end-only**, see the anchoring note below) — note the canonical
page range STARTS AT 82 (pages 82-83 carry chapters 1-2) and the conspectus
siglorum lives on page 54:

    python3 -m diorthosis.cli build ldlt-balex.pdf --pages 82-171 \
        --conspectus-page 54 --text-lang la -o out/
    python3 line_check.py data/balex.xml out/ldlt-balex.tei.xml \
        --known balex_known_divergences.json

### What "563/563 anchored" means — read the split

That build prints, in the console and identically in the md-ce meta line:

    coverage: 563 entries — 563 parsed, 0 refused, 0 unparsed;
              563 anchored (515 attached, 48 end-only), 0 unanchored

Until wave A the same run said "100 % anchored", and that was a coverage claim
stronger than its evidence. diorthosis anchors by internal double-end-point
attachment: `attached` means the `<app>` carries BOTH `@from` and `@to`, so
the lemma's extent in the constituted text is located; `end-only` means the
lemma's start could not be located and only `@to` was emitted. 48 of the 563
balex entries are end-only. They are honest — the entry is present, the
verbatim slice is intact, the end of the span is real — but they do not
support a claim about where the lemma BEGINS, and counting them as plainly
"anchored" hid that. Every place this figure is quoted must carry the split.

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

Status (re-derived 2026-08-05 on v0.7.0 + wave A; unchanged since v0.6):
**looped to zero — 6,293 apps across all 30
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
