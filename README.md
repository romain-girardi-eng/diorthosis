# diorthosis

**Compile published critical editions into TEI P5 and AI-ready Markdown —
with the apparatus criticus anchored, deterministic, and honest about its
provenance.**

Two centuries of textual scholarship — the record of what the manuscripts
actually read, who conjectured what, which witness carries which variant —
exist only on paper and in PDFs. Even the flagship open corpora carry the
constituted text alone (of ~1,356 TEI files in First1KGreek, exactly 2
contain `<app>`; census recorded for this project): **the apparatus criticus
is nearly absent from the digital ecosystem**.

The entire TEI ecosystem works forward — encode by hand, then publish.
`diorthosis` builds the road back: **published edition in → structured
edition out.**

To our knowledge it is the first published, *general-purpose* tool —
convention grammars, not single-edition rules — that reconstructs a TEI
apparatus anchored to the constituted text from the printed page itself. The
honest version of that claim, with the real prior art it rests on (Bambaci's
Kennicott pipeline, Turnbull's dcodex_variants, Boschetti et al. 2009)
addressed head-on, is in [docs/prior-art.md](docs/prior-art.md) — a
154-reference review.

---

## Install

**From PyPI** — once the first release is published. `pip install diorthosis`
returns 404 today; the packaging and the release workflow exist, the release
does not.

```console
$ pip install diorthosis
$ pip install 'diorthosis[review]'   # + the review UI (pypdfium2, Pillow)
```

**From a clone** — the path that works right now, and the one every command
in the docs was executed with:

```console
$ git clone https://github.com/romain-girardi-eng/diorthosis
$ python3 -m venv .venv && . .venv/bin/activate
$ pip install ./diorthosis
$ diorthosis --help
```

Python 3.10+. Two runtime dependencies:
[regreek](https://github.com/romain-girardi-eng/regreek) and `pdfminer.six`.

## Three minutes, on a real edition

Fetch a published critical edition — the DLL *Bellum Alexandrinum*
(ed. Damon et al., CC BY-SA 4.0), pinned to a commit so you get these bytes:

```console
$ curl -fsSL -o balex.pdf \
    https://raw.githubusercontent.com/Library-of-Digital-Latin-Texts/balex/0e6ee82976a6ffeff41b5515594826719bfdfb0f/ldlt-balex.pdf
$ shasum -a 256 balex.pdf
6702fceb54ec347406c0d857ea508e2ff05e2e4dac9a5111df3f6aa2f96c1325  balex.pdf
```

Now build it. **Three flags carry the whole result** — which pages are the
edition, where the sigla are declared, and what language the constituted text
is in. All page numbers are 0-based PDF indices:

```console
$ diorthosis build balex.pdf --pages 82-171 --conspectus-page 54 --text-lang la -o out/
conspectus: 24 witnesses, 103 editors declared
wrote out/balex.tei.xml
wrote out/balex.md
wrote out/balex.witnesses.json
coverage: 563 entries — 563 parsed, 0 refused, 0 unparsed; 563 anchored (515 attached, 48 end-only), 0 unanchored
refusals: none

$ diorthosis validate out/balex.md
OK: md-ce/0.3 invariants hold

$ diorthosis roundtrip out/balex.md out/balex.tei.xml
OK: md-ce and TEI carry the same content
```

Drop the three flags and the same command produces **zero** apparatus
entries, zero constituted text, and an md-ce its own validator rejects — so
it refuses to certify itself and exits `1`:

```console
$ diorthosis build balex.pdf -o naive/
self-check FAILED: this build is not certified
  degenerate: no constituted-text block across 481 page(s): the layerer classified 29 heading, 956 notes, 505 translation and nothing as text. A Latin-script constituted text is read as a translation unless --text-lang la is given, …
  md-ce: 23 violation(s) of SPEC.md — the file 'naive/balex.md' is not a valid md-ce document:
…
$ echo $?
1
```

**0 versus 563, on the same PDF.** Finding an edition's page range and its
conspectus page is the one thing nobody can do for you, and
[docs/tutorial.md](docs/tutorial.md) shows exactly how — with a probe script,
on this edition, output pasted.

Exit codes are part of the contract: `0` success, `1` refused (diorthosis
does not certify what it produced), `2` your input, `3` a diorthosis defect.

OCR input instead of a PDF:

```console
$ diorthosis build --alto page1.xml page2.xml -o out/   # any OCR engine
```

**Documentation:** [tutorial.md](docs/tutorial.md) (start here) ·
[cookbook.md](docs/cookbook.md) · [cli.md](docs/cli.md) ·
[troubleshooting.md](docs/troubleshooting.md) · [SPEC.md](SPEC.md) ·
[generalization.md](docs/generalization.md)

## One model, two outputs

- **TEI P5** — the scholarly interchange, and **the citable artifact**:
  `<pb n="294"/>` printed folios, `<anchor>` elements delimiting lemma spans,
  `<app>/<lem>/<rdg>` with `@wit` and `@source` resolved through `<listWit>`,
  the exact printed wording retained in `<note type="verbatim">`, translation
  in its own `<div>`, page furniture as `<fw>`.
- **Markdown (`md-ce/0.3`)** — the retrieval surface, rendered
  deterministically from the same model: every section is a `###` header
  naming its layer with bracketed provenance, so **a chunker can never mix
  apparatus into text**; numeric markers appear as `⟦folio:n⟧` in the text and
  at the head of the matching entry. Twelve mechanically checkable invariants
  ([SPEC.md](SPEC.md)), enforced by `diorthosis validate`.

Real output, from the build above:

```markdown
## page – (file index 82) [markers=0 entries=7 unresolved=0]
<!-- md-ce page: 7 entries — 7 parsed, 0 refused, 0 unparsed; 7 anchored (6 attached, 1 end-only), 0 unanchored -->

### text [source=born_digital generative=false confidence=0.90 block=1]

1 1Bello Alexandrino conﬂato Caesar Rhodo atque ex Syria

Ciliciaque omnem classem arcessit. Creta sagittarios, eq-

### apparatus [source=born_digital generative=false confidence=0.90 block=2]

5 cotidie operibus USTV | cotidie M (cf. BC 3.112.9) | nouis cotidie  operibus Castiglioni (cf. Tac. Hist. 2.76.4)
7 aptantur MUSTV (u.  BC 3.112.7–9 et cf. Virg. Aen. 3.472) | temptantur Nipperdey (cf. BC  3.40.1) | alii alia (u. Gaertner-Hausburg 48 n.87)
```

and the first of those entries in the TEI:

```xml
<app n="5" from="#a-p82-e0-start" to="#a-p82-e0">
  <lem wit="#wit-U #wit-S #wit-T #wit-V">cotidie operibus</lem>
  <rdg wit="#wit-M">cotidie</rdg>
  <rdg source="#ed-Castiglioni">nouis cotidie operibus</rdg>
  <note type="comment">(cf. BC 3.112.9)</note>
  <note type="verbatim">5 cotidie operibus USTV | cotidie M (cf. BC 3.112.9) | nouis cotidie

operibus Castiglioni (cf. Tac. Hist. 2.76.4)</note>
</app>
```

On a numeric-marker edition the two views share page-scoped markers, so an
entry and its place in the text can be matched without parsing the TEI:

```markdown
### text [source=born_digital generative=false confidence=0.90 block=1]

… illud expectans⟦25:1⟧ primum ut, cum in duas partes es-
set urbs⟦25:2⟧ diuisa, acies uno consilio atque imperio administraretur …

### apparatus [source=born_digital generative=false confidence=0.90 block=2]

⟦25:1⟧ Expectans M U S T V : spectans Vascosanus
⟦25:2⟧ Urbs U : ubrs M : urbis S T V
```

## The provenance contract

Inherited from [regreek](https://github.com/romain-girardi-eng/regreek),
which does the character-level work (legacy Greek font decoding) and the
page-level work (layer separation, printed-folio extraction):

1. **Nothing is generated.** Born-digital text is a deterministic decoding of
   the file's own glyph stream. The single normalization performed —
   superscript apparatus markers become anchors — is declared in the TEI
   header.
2. **OCR is welcome, and permanently marked.** diorthosis is **OCR-agnostic
   by design**: it never calls an engine, it ingests the standard formats
   (ALTO, hOCR, PAGE-XML) that Kraken, eScriptorium, Tesseract and
   Transkribus all export. Every block that came from OCR carries
   `generative=true` into both outputs, forever — a recognition model's guess
   is never allowed to impersonate a decoded text.
3. **Honest coverage.** One report, three renderings — console, md-ce meta
   line, md-ce page headers — partitioning the same entries twice
   (`parsed + refused + unparsed`, `attached + end-only + unanchored`).
   `end-only` is an apparatus link that reaches the text at one end only; it
   used to be counted as plainly "anchored", which is how the edition above
   once reported "100 % anchored". Refused and unanchored entries are
   preserved verbatim, never dropped.
4. **Outputs are byte-deterministic.** Enforced by a two-process build that
   byte-compares every emitted file, so hash randomization cannot hide an
   order dependence.

## What it supports — and what it refuses

**Supported today (v0.7.0).** Ingest born-digital PDFs and any OCR engine's
ALTO / hOCR / PAGE-XML; separate layers; extract the citable printed folio;
split apparatus bands into entries and anchor each to its place in the
constituted text; parse the apparatus into `<app>/<lem>/<rdg>` with witness
and editor attributions drawn from the edition's own conspectus siglorum,
under **four convention grammars**:

| family | shape | reference corpus |
|---|---|---|
| numeric markers | superscript `n` in the text, `n lemma : reading SIGLA` band | *Sources Chrétiennes* family |
| verse-referenced | `chapter:verse lemma ] reading SIGLA` | biblical editions (SBLGNT) |
| line-referenced reledmac | `∥ line lemma SIGLA \| reading SIGLA` | DLL family |
| paragraphed reledmac | numbered `lemma] reading SIG`, double apparatus | LombardPress / scholastic |

plus superscript sigla. Emits schema-valid TEI P5 (validated against
`tei_all.rng`) and `md-ce/0.3`.

**Refused, on purpose.** A band whose convention is not one of the four is
kept **verbatim** — source slice preserved, no invented structure — and
counted as `refused` with the refusing gate's own sentence as the reason.
Nothing is dropped; what you lose is structure, not evidence.

**The measured result of that policy.** On nine reviewer-supplied editions
the grammars had never seen (before/after table in
[docs/generalization.md](docs/generalization.md)), whole-band convention
gating fails closed. Eight are 100 % verbatim-refused. The ninth, Segrave's
*Insolubilia*, parses 20 of 923 entries (2.2 %) — the locally separator-free
ones — and refuses every band carrying the unsupported `|| lemma]`
continuation; the fabrication spot-check in the linked table finds those
samples 5/5 faithful. The eight public-CLI runs re-derived on 2026-08-05:

```
insolubles  923 entries —  20 parsed, 903 refused   903× paragraph gate: foreign separator '||' not consumed
britannico  343 entries —   0 parsed, 343 refused   217× + 79× marker gate; 47× paragraph gate
derivas      74 entries —   0 parsed,  74 refused    40× + 34× marker gate
iacopone    146 entries —   0 parsed, 146 refused   126× paragraph gate: orphan ']' closers; 20× marker gate
blacasset    53 entries —   0 parsed,  53 refused    53× marker gate: no boundary found
pigna        66 entries —   0 parsed,  66 refused    64× + 2× marker gate  (edition has no apparatus at all)
saivism      82 entries —   0 parsed,  82 refused    81× + 1× marker gate
susruta     254 entries —   0 parsed, 254 refused   233× + 21× paragraph gate
```

(The ninth, a locally generated Gracilis PDF, is in the linked table.) Before
gating, the same deterministic samples were **false** in every edition that
parsed anything: 5/5 false on Britannico, Herodian, Iacopone, Blacasset and
Pigna, 4/5 on *Insolubilia*, 1/5 on Suśruta, 1/1 on Gracilis. That is what
the gates removed. This is conservative convention recognition, not new
coverage: a refused layout still needs an explicit grammar and human review
before it becomes data.

**Not done yet.** Negative apparatus (where the lemma's support is implied by
silence); two-column layouts; **layering and apparatus parsing on OCR input**
— today the OCR path gives you a provenance-marked, chunkable transcription
with every block `unclassified` and zero apparatus parsed; and consequently
**no accuracy figures exist for noisy OCR input**. Every number on this page
is measured on born-digital PDFs.

## Evidence — and what each test does and does not prove

The suite is layered by epistemic strength. Read the labels: they are
different claims. Every figure below was re-derived on 2026-08-05 at commit
`bd01130`, except where marked.

**1. Adversarial backtest** — the printed PDF and the scholarly TEI were
produced *independently*. The whole SBLGNT New Testament: the official
published PDFs against the PTA's TEI re-encoding of the same apparatus.

```
TOTAL: 6921 source leaf apps = 6797 compared + 61 refused-with-reason + 60 uncovered
       + 3 unaccounted + 0 adjudicated + 0 unexamined | 0 ERRORS | 430 gaps | 59 typed divergences
ACCOUNTING: identity holds — 6921 == 6921 source leaf apps, all 27 books reconciled
UNACCOUNTED (fatal, pending human adjudication): 3 source apps in no outcome bucket
```

**6,797 entries compared, 0 structural errors**, with 59 print-vs-TEI
divergences documented one by one under an explicit adjudication protocol (a
claimed divergence must be *provable from the extracted band itself*; every
key carries its citation). The driver asserts that every source app lands in
exactly one bucket — and **exits 1**, because three apps land in none. They
are named, with their scholar lemma and our extracted band, for human
adjudication. This is the strongest evidence the suite has, and it covers ONE
convention on ONE atypically regular apparatus (editions cited, not
manuscripts).

**2. Toolchain inversion** — the official PDF is *generated from* the
reference TEI by the project's own toolchain. Zero alignment ambiguity, but
parser and typesetter see the same conventions.

```
563 scholar apps | 563 compared | 0 ERRORS | 0 gaps | 17 documented divergences | 0 verbatim notes
PASS: zero apparatus errors                        (DLL Bellum Alexandrinum, real printed PDF)

235 scholar apps | 235 compared | 0 ERRORS | 0 documented divergences | anchored 206/235
PASS: zero apparatus errors                        (Plaoul lectio 1, LombardPress toolchain PDF)
```

Sweeping all thirty Plaoul lectios with the same checker: **6,293 apps
compared, 0 errors** (235 + 82 + 155 + … + 255; the per-lectio table is
`plaoul_check.py` run thirty times).

Those 563 balex entries are `515 attached + 48 end-only` in the coverage report —
the same graph the old "100 % anchored" described less carefully. These prove
the grammars invert a real typesetting chain exactly. They do **not** prove
generalization to independently set editions.

**3. Retypeset goldens** — we typeset the scholar's TEI ourselves, then parse
our own print. Self-generated ground truth, kept as *regression tests*.

```
 524 compared of  567 source apps (  43 excluded) | 0 ERRORS |  0 gaps   balex
6906 compared of 6929 source apps (  23 excluded) | 0 ERRORS |  0 gaps   SBLGNT
5524 compared of 7812 source apps (2288 excluded) | 0 ERRORS | 50 gaps   Problemata
```

Every exclusion is named and counted (nested apps, `rdgGrp`, discontinuous
span lemmas, punctuation-only lemmas), so the ledger never hides a
denominator. A generator and a parser can share a blind spot; these numbers
guard against regressions, nothing more.

**4. Real edition without digital ground truth** — self-validation metrics
only. Bobichon's *Justin Martyr*, 2,031 entries: **99.3 % anchoring, 99.0 %
parse, 97.5 % lemma concordance, 89.9 % attribution**, measured 2026-08-04.
This is the one tier a reader cannot reproduce from public inputs — the
edition is a copyrighted book, not redistributable — and it is reported here
because deleting it would flatter the others. Read that last number honestly:
roughly one entry in ten needs a human eye on its attributions. On such
editions diorthosis is a *pre-annotation* tool, not a replacement for review.

**Also green at `bd01130`:** `219 passed` (`pytest -q`, fresh clone),
`ruff check src/` clean, byte-identical double build, and the emitted TEI
valid against `tei_all.rng`.

**Still not demonstrated:** double-keyed human validation of the parses. The
sampling design, annotation unit, agreement statistics and adjudication
procedure are specified in
[docs/generalization.md](docs/generalization.md) — as a protocol to execute,
with no result claimed. Until it exists, the zeros above should be read
within the limits stated here.

Run any of it yourself:
[docs/cookbook.md](docs/cookbook.md#run-the-golden-harnesses-on-your-own-edition).

## The review loop

A grammar gets an edition to 90–99 %; the last stretch is human review —
made REPLAYABLE:

```console
$ pip install 'diorthosis[review]'
$ diorthosis review balex.pdf --pages 82-84 --conspectus-page 54 --text-lang la -o review/
conspectus: 24 witnesses, 103 editors declared
wrote review/index.html
review: 18 entries — 18 parsed, 0 refused, 0 unanchored, 0 reviewed; 18 snippets
```

`review/index.html` shows every apparatus entry face to face with the IMAGE
SNIPPET of the printed band lines it was split from — per-entry provenance a
reviewer can check at a glance. Refusals and unanchored entries filter into a
work queue; each entry carries an editable override form; "download
overrides.json" exports the corrections, and

```console
$ diorthosis build balex.pdf … --overrides overrides.json -o out/
overrides: 1 parses replaced, 1 forced verbatim
…
refusals: 1× human review forced the entry verbatim
```

replays them on every rebuild. Every overridden entry is marked
`resp="#human-review"` in the TEI with a `respStmt` declaration — a human
correction is provenance, never silently merged into what the grammar read;
the verbatim source wording is retained regardless, and a reviewer's refusal
is counted as a refusal in the coverage report, under its own reason.

Each record is bound to its entry's **byte-exact source slice by hash**
(`diorthosis-overrides/1`). If the band splitting drifts, the replay refuses
— itemised, all or nothing — instead of re-targeting a scholar's authority
onto a different entry. Full recipe:
[docs/cookbook.md](docs/cookbook.md#review-an-edition-and-replay-the-corrections).

## Architecture

```
ingest/              borndigital (regreek) · alto · hocr · pagexml — one model out
model.py             Document/Page/Block with Layer + Source + generative flag
anchor.py            entry splitting + marker anchoring, honest counters
match.py             lemma-to-text location (what decides attached vs end-only)
convention.py        the gate decision object every grammar refuses through
grammar.py           numeric-marker convention + the shared entry parser
versegrammar.py      verse-referenced convention
linegrammar.py       line-referenced reledmac convention
paragraphgrammar.py  paragraphed reledmac convention (double apparatus)
conspectus.py        sigla bootstrap · witnesses.py the emitted witness table
overrides.py         hash-bound human corrections · review.py the review UI
tei.py               TEI P5 emission (the canonical output)
md.py                md-ce renderer + the one coverage measurement
mdce_validate.py     md-ce invariant checker (SPEC.md, executable)
roundtrip.py         md-ce ↔ TEI equivalence
cli.py               build / inspect / validate / roundtrip / review
```

## Legal note

`diorthosis` is a tool, not a corpus: it ships no edition content, and what
you run it on is your responsibility under your jurisdiction. The ancient
text itself is not copyrightable; apparatus prose and modern translations may
be. There are unambiguous lawful uses — from editions you have the rights to,
to public-domain editions, to text/data-mining provisions where they apply.

## Citation & license

MIT. If this tool contributes to published research, please cite it (see
`CITATION.cff`).
