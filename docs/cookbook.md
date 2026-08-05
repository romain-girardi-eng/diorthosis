# Cookbook

Task-oriented recipes. Every command was executed on 2026-08-05 against
diorthosis 0.7.0 at commit `bd01130`; the console blocks are the real output,
cut where long and marked where cut.

Start with [tutorial.md](tutorial.md) if you have never built an edition.
Flag reference: [cli.md](cli.md). Error messages:
[troubleshooting.md](troubleshooting.md).

Commands are written for an installed `diorthosis`. From an uninstalled
working copy, prefix with
`PYTHONPATH=$PWD/src python3 -m diorthosis.cli` instead.

---

## Supply sigla when the edition has no usable conspectus

Some editions print no sigla table at all; others define their witnesses in
running prose in the introduction (`E8 = Erfurt, Universitäts- und
Forschungsbibliothek …`), which the conspectus bootstrap does not recognise
as a list. Either way you get a warning and an apparatus with no attributions.

Walter Segrave's *Insolubilia* is the second kind. Its manuscripts are
described on PDF page 26; pointing `--conspectus-page` there finds nothing:

```console
$ diorthosis build insolubles.pdf --pages 40 --conspectus-page 26 --text-lang la -o out/
[!] no conspectus siglorum found in page 26: witnesses will be missing from the TEI and manuscript sigla cannot be attributed
…
```

Read the sigla off the page yourself and declare them. This is **input, not
tuning**: you are transcribing what the edition prints. (The runs below keep
`--conspectus-page 25`, the value the generalization table uses; it finds
nothing either, which is exactly why `--sigla` is needed.)

```console
$ diorthosis build insolubles.pdf --pages 30,32,34,36,38,40,42,44,46,48 \
      --conspectus-page 25 --text-lang la -o without/
coverage: 105 entries — 0 parsed, 105 refused, 0 unparsed; 0 anchored (0 attached, 0 end-only), 105 unanchored
refusals: 99× paragraph convention gate refused band: foreign separator '||' is not consumed; 6× paragraph convention gate refused band: trial parse left n of tokens unconsumed (maximum n)

$ diorthosis build insolubles.pdf --pages 30,32,34,36,38,40,42,44,46,48 \
      --conspectus-page 25 --sigla E4,E8,O --text-lang la -o with/
coverage: 105 entries — 6 parsed, 99 refused, 0 unparsed; 6 anchored (5 attached, 1 end-only), 99 unanchored
refusals: 99× paragraph convention gate refused band: foreign separator '||' is not consumed
```

Same pages, same everything else. Without the sigla, six further bands fail
the gate's unconsumed-token ceiling — an unresolvable siglum is a token the
trial parse cannot account for. With them, six entries carry structure:

```xml
<app n="2" from="#a-p40-e1-start" to="#a-p40-e1">
  <lem>istud</lem>
  <rdg wit="#wit-E8">quod</rdg>
  <note type="verbatim">2 istud] quod add. E8</note>
</app>
```

Declared sigla are labelled as such in the witness table, so a reader can
always tell what came from the edition and what you typed:

```console
$ cat with/insolubles.witnesses.json
[
 {
  "siglum": "E4",
  "base": "E4",
  "hand": "",
  "hand_label": "",
  "description": "user-supplied siglum (--sigla)"
 },
…
```

Notes:

- `--sigla` **merges** into whatever the front matter yielded; it never
  replaces it.
- Only sigla actually used by the emitted apparatus reach
  `witnesses.json`. `O` was declared above and does not appear: no reading in
  those ten pages cites it.
- `--sigla` does not weaken any gate. The other 99 bands still refuse.

---

## Review an edition and replay the corrections

A grammar gets an edition to 90–99 %. The rest is human, and diorthosis makes
it replayable rather than manual.

### 1. Generate the review page

```console
$ pip install 'diorthosis[review]'
$ diorthosis review balex.pdf --pages 82-84 --conspectus-page 54 --text-lang la -o review/
conspectus: 24 witnesses, 103 editors declared
wrote review/index.html
review: 18 entries — 18 parsed, 0 refused, 0 unanchored, 0 reviewed; 18 snippets
```

`review/index.html` is self-contained apart from `review/snippets/pN-eK.png`.
Each entry shows the **image crop of the printed band lines it was split
from**, its parse, its status, and an editable override form. The filter
(`all` / `refused (work queue)` / `unanchored (work queue)` / `parsed` /
`reviewed`) puts the work queue first. Tick "include in overrides.json" on
what you corrected, then **download overrides.json**.

### 2. What the exported file looks like

`diorthosis-overrides/1`. The interesting part is `source_sha`: the first 12
hex characters of SHA-256 over the entry's immutable source slice, with
physical line breaks unwrapped to single spaces.

```json
{
 "format": "diorthosis-overrides/1",
 "entries": {
  "p82-e6": {
   "action": "verbatim",
   "note": "reviewer: keep verbatim",
   "source_sha": "cbf68924a0c3",
   "source_excerpt": "12 ac MTV | et U | a S"
  },
  "p83-e0": {
   "action": "parse",
   "lemma": "expectans",
   "lemma_wits": ["M", "U", "S", "T", "V"],
   "lemma_editors": [],
   "lemma_qualifiers": [],
   "readings": [
    {"text": "spectans", "wits": [], "editors": ["Vascosanus"], "qualifiers": []}
   ],
   "comments": [],
   "note": "reviewer: checked",
   "source_sha": "2a5df7443e18",
   "source_excerpt": "16 expectans MUSTV (cf. BC 3.43.3 et u. Damon 2015b 116 n.32) | spectans Vascosanus (cf. BC 3.85.2)"
  }
 }
}
```

The key `p{page}-e{k}` **locates** a candidate — `page` is the 0-based file
page, `k` counts apparatus entries across the whole page in document order.
`source_sha` **decides** whether that candidate is the entry the human
actually corrected. Two actions: `parse` replaces the grammar's structure,
`verbatim` forces the honest refusal. The raw entry text is never touched by
either.

### 3. Replay

```console
$ diorthosis build balex.pdf --pages 82-84 --conspectus-page 54 --text-lang la \
      --overrides overrides.json -o out/
conspectus: 24 witnesses, 103 editors declared
overrides: 1 parses replaced, 1 forced verbatim
wrote out/balex.tei.xml
wrote out/balex.md
wrote out/balex.witnesses.json
coverage: 18 entries — 17 parsed, 1 refused, 0 unparsed; 18 anchored (15 attached, 3 end-only), 0 unanchored
refusals: 1× human review forced the entry verbatim
```

The reviewer's refusal is *in the coverage report*, under its own reason. It
did not quietly become an `unparsed`.

In the TEI, both corrections are attributed:

```console
$ grep -n 'human-review' out/balex.tei.xml
7:        <respStmt xml:id="human-review">
8:          <resp>Entries marked resp='#human-review' were corrected or reclassified by a human reviewer through a diorthosis overrides file; their verbatim source wording is retained unchanged.</resp>
185:        <note type="apparatus" n="12" target="#a-p82-e6" resp="#human-review">12 ac MTV | et U | a S</note>
224:        <app n="16" resp="#human-review" from="#a-p83-e0-start" to="#a-p83-e0">
```

### 4. What the binding protects you from

If the band splitting changes — a grammar fix, a different page range, a new
diorthosis — a positional key alone would silently re-target your correction
onto a *different* entry, and emit it carrying `resp="#human-review"`. The
hash catches that, and the replay is **all or nothing**:

```console
$ diorthosis build balex.pdf --pages 82-84 --conspectus-page 54 --text-lang la \
      --overrides overrides-drifted.json -o out/
error: 1 override(s) no longer match the entry they were made against; refusing to replay ANY of them.
Applying a drifted correction would attach a human-reviewed parse (resp="#human-review") to a different apparatus entry.
  p83-e0: bound to 000000000000, entry is now 2a5df7443e18
      made against: 16 expectans MUSTV (cf. BC 3.43.3 et u. Damon 2015b 116 n.32) | spectans Vascosanus (cf. BC 3.85.2)
      now reads:     16 expectans MUSTV (cf. BC 3.43.3 et u. Damon 2015b 116 n.32) | spectans Vascosanus (cf. BC 3.85.2)
$ echo $?
2
```

A key matching **no** entry is a lesser problem — you lose a correction, you
do not gain a false one — so it warns and continues:

```console
$ diorthosis build … --overrides overrides-stale.json -o out/
[!] 1 override key(s) matched no entry (stale file?): p99-e0
$ echo $?
0
```

### 5. Scripted export (batches, inter-annotator studies)

The download button's Python twin is `diorthosis.review.bind_record` +
`export_file`. Use it when a person is not clicking — the binding is computed
from the build, never typed in:

```python
# export_overrides.py
import json
import sys

from diorthosis.anchor import anchor_page
from diorthosis.conspectus import bootstrap_registry
from diorthosis.ingest import ingest_pdf
from diorthosis.overrides import entry_keys
from diorthosis.review import bind_record, export_file

pdf = "balex.pdf"
registry, _ = bootstrap_registry(pdf, 54)
doc = ingest_pdf(pdf, [82, 83, 84], text_lang="la")
for page in doc.pages:
    anchor_page(page, registry)

by_key = {k: e for p in doc.pages for k, e in entry_keys(p)}
records = {
    "p82-e6": bind_record({"action": "verbatim",
                           "note": "reviewer: keep verbatim"}, by_key["p82-e6"]),
}
json.dump(export_file(records), open(sys.argv[1], "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
for k, r in records.items():
    print(f"  {k}  source_sha={r['source_sha']}  {r['source_excerpt'][:60]}")
```

```console
$ python3 export_overrides.py overrides.json
  p82-e6  source_sha=cbf68924a0c3  12 ac MTV | et U | a S
```

`docs/generalization.md` specifies a two-annotator protocol built on this
same file format.

---

## Consume the md-ce for retrieval

md-ce exists so a chunker can never mix apparatus into constituted text. The
contract is SPEC.md's C1–C4; the whole parser is a dozen lines of stdlib.

```python
# chunk.py — implements C1/C2; refuses to split on blank lines
import json
import re
import sys

HEAD = re.compile(r"^## page (?P<folio>.+?) \(file index (?P<idx>\d+)\)")
SEC = re.compile(r"^### (?P<layer>\w+) \[source=(?P<source>\w+) "
                 r"generative=(?P<gen>\w+) confidence=(?P<conf>[\d.]+) "
                 r"block=(?P<block>\d+)\]")

def chunks(path):
    page = cur = None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if m := HEAD.match(line):
            if cur: yield cur
            cur, page = None, m.groupdict()
            continue
        if m := SEC.match(line):
            if cur: yield cur
            cur = {**m.groupdict(), "folio": page["folio"],
                   "file_index": int(page["idx"]), "body": []}
            continue
        if cur is not None and line.strip():
            cur["body"].append(line)
    if cur: yield cur

out = list(chunks(sys.argv[1]))
print(f"{len(out)} chunks")
for layer in ("text", "apparatus", "translation", "notes", "heading", "unclassified"):
    if n := sum(c["layer"] == layer for c in out):
        print(f"  {layer:14} {n}")
print("generative chunks:", sum(c["gen"] == "true" for c in out))
sample = next(c for c in out if c["layer"] == "apparatus")
print(json.dumps({k: v for k, v in sample.items() if k != "body"}, ensure_ascii=False))
print("first entry:", sample["body"][0][:80])
```

```console
$ python3 chunk.py out/balex.md
269 chunks
  text           90
  apparatus      89
  notes          89
  heading        1
generative chunks: 0
{"layer": "apparatus", "source": "born_digital", "gen": "false", "conf": "0.90", "block": "2", "folio": "–", "file_index": 82}
first entry: 5 cotidie operibus USTV | cotidie M (cf. BC 3.112.9) | nouis cotidie  operibus C
```

Four rules that are not optional:

- **C1** — a chunk is one `### ` section. **Never split on blank lines**:
  blank lines separate *printed lines*, not paragraphs.
- **C2** — carry the `## page` header and the `metadata` as chunk metadata. A
  `text` chunk and an `apparatus` chunk must never merge.
- **C3** — `generative=true` is recognition-engine output. Surface it as such
  wherever you quote it. It is not verbatim edition text.
- **C4** — a marker with `?` (`⟦25:3?⟧`) is unresolved and MUST NOT be
  resolved by search. Markers are page-scoped; cross-page resolution is
  forbidden.

Markers appear only on numeric-marker editions. The line-referenced balex has
none (`markers=0` in every page header); a marker-convention build looks like
this, the same `⟦25:n⟧` on both sides of the page:

```
## page 25 (file index 7) [markers=4 entries=4 unresolved=0]
<!-- md-ce page: 4 entries — 4 parsed, 0 refused, 0 unparsed; 4 anchored (4 attached, 0 end-only), 0 unanchored -->

### text [source=born_digital generative=false confidence=0.90 block=1]

… illud expectans⟦25:1⟧ primum ut, cum in duas partes es-
set urbs⟦25:2⟧ diuisa, acies uno consilio atque imperio administraretur …

### apparatus [source=born_digital generative=false confidence=0.90 block=2]

⟦25:1⟧ Expectans M U S T V : spectans Vascosanus
⟦25:2⟧ Urbs U : ubrs M : urbis S T V
```

The meta line names the TEI the md-ce was projected from
(`tei: balex.tei.xml`). **Cite the TEI, index the md-ce.** md-ce deliberately
omits the parsed lemma/reading structure, the witness declarations, and all
page furniture; if you need any of those, read the TEI.

For a downstream evaluation of whether this representation actually helps a
model answer apparatus questions, see
[llm-consumption.md](llm-consumption.md).

---

## Consume `witnesses.json`

Every build writes `S.witnesses.json`: the sigla the emitted apparatus
actually cites, resolved against the conspectus, with the hand decomposed.

```console
$ python3 -c "
import json
for w in json.load(open('out/balex.witnesses.json'))[:6]:
    print(f\"{w['siglum']:6} base={w['base']:4} hand={w['hand'] or '-':4} {w['hand_label'] or '-':28} {w['description'][:40]}\")"
M      base=M    hand=-    -                            Florence, BML Plut.
Mac    base=M    hand=ac   before correction            The uncorrected reading in M. Equivalent
Mc     base=M    hand=c    after correction / corrector Corrections by the original scribe, who
Mmr    base=M    hand=mr   later hand (manus recentior) Corrections by one or more later hands (
S      base=S    hand=-    -                            Florence, BML Ashburnham 33 (s. x2–3)
Sac    base=S    hand=ac   before correction            The uncorrected reading in S, Equivalent
```

| field | meaning |
|---|---|
| `siglum` | the siglum as printed and as cited in the apparatus |
| `base` | the manuscript it belongs to — `Mac`, `Mc`, `Mmr` all have base `M` |
| `hand` | the hand suffix: `ac` (*ante correctionem*), `c`, `mr`, … |
| `hand_label` | that suffix spelled out |
| `description` | the conspectus line, as printed |

Use `base` to group readings by manuscript rather than by hand — that is the
question most stemmatic work actually asks. The same information is in the
TEI as `<listWit>` with `@corresp` pointing from a hand to its base witness.

Two honest caveats: `description` is the conspectus line as extracted, so it
can be clipped where the printed line wrapped (`"Florence, BML Plut."`); and
the file lists only sigla the apparatus *used*, not everything the conspectus
declared.

---

## Process OCR output instead of a PDF

diorthosis is **OCR-agnostic by design**: it never calls an engine, it
ingests what engines export. Run Kraken, eScriptorium, Tesseract or
Transkribus yourself and pass the result.

```console
$ diorthosis build --alto p1.xml p2.xml -o out/        # one file per page
$ diorthosis build --hocr scan.html -o out/            # may be multi-page
$ diorthosis build --page-xml p1.xml p2.xml -o out/    # kraken / eScriptorium
```

A minimal ALTO page, and what comes out:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
  <Layout><Page><PrintSpace>
    <TextBlock ID="text">
      <TextLine>
        <String CONTENT="Bello" WC="0.99"/><SP/><String CONTENT="Alexandrino" WC="0.97"/>
        <SP/><String CONTENT="conflato" WC="0.95"/><SP/><String CONTENT="Caesar" WC="0.99"/>
      </TextLine>
    </TextBlock>
    <TextBlock ID="apparatus">
      <TextLine>
        <String CONTENT="5" WC="0.92"/><SP/><String CONTENT="cotidie" WC="0.96"/>
        <SP/><String CONTENT="operibus" WC="0.94"/><SP/><String CONTENT="USTV" WC="0.88"/>
      </TextLine>
    </TextBlock>
  </PrintSpace></Page></Layout>
</alto>
```

```console
$ diorthosis build --alto p1.xml -o out/
[!] this document contains OCR-generated blocks (marked generative) — their text is a recognition model's output, not a decoded stream
wrote out/p1.tei.xml
wrote out/p1.md
wrote out/p1.witnesses.json
coverage: 0 entries — 0 parsed, 0 refused, 0 unparsed; 0 anchored (0 attached, 0 end-only), 0 unanchored
refusals: none
```

`cat out/p1.md`:

```markdown
# p1

<!-- md-ce/0.3 · diorthosis 0.7.0 · ingest: alto · pages: 0-0 · coverage: 0 entries — 0 parsed, 0 refused, 0 unparsed; 0 anchored (0 attached, 0 end-only), 0 unanchored · refusals: none · generative-blocks: 2 · escaped-lines: 0 · tei: p1.tei.xml -->

## page – (file index 0) [markers=0 entries=0 unresolved=0]
<!-- md-ce page: 0 entries — 0 parsed, 0 refused, 0 unparsed; 0 anchored (0 attached, 0 end-only), 0 unanchored -->

### unclassified [source=ocr generative=true confidence=0.94 block=0]

Bello Alexandrino conflato Caesar

### unclassified [source=ocr generative=true confidence=0.93 block=1]

5 cotidie operibus USTV
```

Read that output honestly, because it is the current state of the OCR path:

- **Provenance works and is permanent.** `source=ocr`, `generative=true`,
  `generative-blocks: 2`, a per-block confidence carried from the engine's own
  word confidences, and a stderr warning on every run. A recognition model's
  guess is never allowed to impersonate a decoded text, in either output.
- **Layering does not happen.** Every OCR block is `unclassified`. diorthosis
  deliberately does not guess a layer from OCR input, so the constituted text
  and the apparatus band are not separated, and **no apparatus is parsed —
  `0 entries`** — even though the band is right there.
- Therefore: today the OCR path gives you a provenance-marked, chunkable,
  schema-valid transcription. It does not give you a structured apparatus.
  `--pages` and `--conspectus-page` are refused with OCR sources (there is no
  PDF to index into and no front matter to search); pass exactly the page
  files you want built.
- **No accuracy figures exist for noisy OCR input.** Every measured number in
  this project is on born-digital PDFs.

The hOCR path behaves identically (`ingest: hocr`, `generative-blocks: 1` for
a one-block page). The designed hybrid pipeline for scans — a CTC engine
defining the geometry, a VLM reading line crops inside it, three arbitration
states and no silent choice — is specified in
[ocr-hybrid.md](ocr-hybrid.md); it is a design, not shipped behaviour.

---

## Run the golden harnesses on your own edition

`tools/golden/` is not just this project's CI. If you hold a scholar-encoded
TEI **and** its printed PDF, you can measure diorthosis on your material with
the same instruments, and the bar is asymmetric by design: a **wrong**
structure fails the run; a **missing but honest** one (kept verbatim, left
unanchored) is a reported gap, never a failure.

None of these run from an installed wheel — they live in the repository.
Work from a clone, and install the dev extra:

```console
$ git clone https://github.com/romain-girardi-eng/diorthosis && cd diorthosis
$ pip install -e '.[dev]'          # pytest, ruff, lxml
$ ./tools/golden/fetch_sources.sh  # scholar TEI + tei_all.rng, checksummed
```

### Determinism: does the same input give the same bytes?

Run this first on your own edition. It builds twice in two separate processes
and byte-compares every output, so hash randomisation cannot hide an order
dependence.

```console
$ python3 tools/golden/double_build.py /tmp/ldlt-balex.pdf --pages 82-84 \
      --conspectus-page 54 --text-lang la
build 1: …/build-1
…
MATCH  ldlt-balex.md
MATCH  ldlt-balex.tei.xml
MATCH  ldlt-balex.witnesses.json
PASS: both builds produced byte-identical files
```

This driver spawns `python -m diorthosis.cli` as a subprocess, so unlike the
other drivers it needs diorthosis importable in that subprocess: either
installed, or `PYTHONPATH=$PWD/src` exported.

### Retypeset golden: TEI → PDF → diorthosis → compare

`run_golden.py` typesets the scholars' TEI into a critical-edition PDF
(numeric-marker convention, conspectus page, paginated deterministically),
compiles it back, and compares. Needs [tectonic](https://tectonic-typesetting.github.io/).

```console
$ python3 tools/golden/run_golden.py tools/golden/data/balex.xml work/balex \
      --text-lang la --rng tools/golden/tei_all.rng
524 compared of 567 source apps (43 excluded: {'nested_app_subtree': 28, 'no_lem': 1, 'punctuation_lemma': 14}) | 0 ERRORS | 0 gaps
PASS: zero apparatus errors (gaps are honest refusals)
…
LEDGER: 524 compared of 567 source apps (43 excluded: …)

$ python3 tools/golden/run_golden.py tools/golden/data/sblgnt.xml work/sblgnt \
      --rng tools/golden/tei_all.rng
6906 compared of 6929 source apps (23 excluded: {'nested_app_subtree': 18, 'punctuation_lemma': 5}) | 0 ERRORS | 0 gaps
PASS: zero apparatus errors (gaps are honest refusals)

$ python3 tools/golden/run_golden.py tools/golden/data/problemata.xml work/problemata \
      --text-lang la --rng tools/golden/tei_all.rng
gap   p26 n=7 [GAP_UNANCHORED] app has no @to
…
5524 compared of 7812 source apps (2288 excluded: {'nested_app_subtree': 2011, 'no_lem': 212, 'punctuation_lemma': 64, 'typeset_duplicate_position': 1}) | 0 ERRORS | 50 gaps
PASS: zero apparatus errors (gaps are honest refusals)
```

Every excluded `<app>` is **counted and named** — nested apps, `rdgGrp`,
discontinuous span lemmas, punctuation-only lemmas — so the ledger never
hides a denominator. And read the epistemic label: a retypeset golden is a
**regression test**. A generator and a parser can share a blind spot.

### Real print, real convention: the line-referenced checker

This one runs diorthosis on the edition **as actually printed** and compares
against the scholars' TEI:

```console
$ diorthosis build /tmp/ldlt-balex.pdf --pages 82-171 --conspectus-page 54 \
      --text-lang la -o out/
$ python3 tools/golden/line_check.py tools/golden/data/balex.xml out/ldlt-balex.tei.xml \
      --known tools/golden/balex_known_divergences.json
563 scholar apps | 563 compared | 0 ERRORS | 0 gaps | 17 documented divergences | 0 verbatim notes
PASS: zero apparatus errors
$ echo $?
0
```

The 17 divergences are **typed and executable**: a claimed print-vs-TEI
difference must be provable from the extracted band itself, and each record
carries its evidence and its expected error class
(`tools/golden/divergences.py`). A divergence file is not a whitelist — a
record whose evidence stops matching fails the run.

### Whole-corpus accounting: the NT oracle

The strongest instrument here, and the one whose *reporting* wave A rebuilt.
It builds all 27 SBLGNT book PDFs and asserts a bucket **partition** per book
and on the corpus sum before it may exit 0. `fetch_sources.sh` does not
download the PDFs — put the publisher's own bundle in
`tools/golden/data/sblgnt_pdfs/` first:

```console
$ mkdir -p tools/golden/data/sblgnt_pdfs && cd tools/golden/data/sblgnt_pdfs
$ curl -sSL -o sblgnt.zip https://sblgnt.com/download/SBLGNTpdf.zip
$ python3 -c "import zipfile; zipfile.ZipFile('sblgnt.zip').extractall('.')" && rm sblgnt.zip
$ ls | wc -l
      29
```

```console
$ PYTHONPATH=$PWD/src python3 tools/golden/sblgnt_nt_driver.py tools/golden/data work/nt
SOURCE MANIFEST: 27 books, 6921 leaf apps
B01 Matthew            COMPARED  822/ 826 |   4 uncovered in   4 loci | PASS
B02 Mark               COMPARED  928/ 930 |   1 uncovered in   1 loci | FAIL 1 unaccounted
…
B18 Philemon           REFUSED   17 apps — single-chapter book: band opens with bare verse numbers; verse grammar requires C:V
…
TOTAL: 6921 source leaf apps = 6797 compared + 61 refused-with-reason + 60 uncovered + 3 unaccounted + 0 adjudicated + 0 unexamined | 0 ERRORS | 430 gaps | 59 typed divergences
ACCOUNTING: identity holds — 6921 == 6921 source leaf apps, all 27 books reconciled
UNACCOUNTED (fatal, pending human adjudication): 3 source apps in no outcome bucket
   B02 Mark 6:33[1]: no counterpart emitted — scholar lemma 'αυτουσ'; our band at 6:33: '33  ἐπέγνωσαν NIV ] + αὐτὸν RP; ἔγνωσαν WH Treg'
   B04 John 9:11[3]: no counterpart emitted — scholar lemma 'τον'; …
   B04 John 9:11[4]: no counterpart emitted — scholar lemma 'ουν'; …
wrote …/work/nt/nt_errors.json with 3 fatal failures
$ echo $?
1
```

Read that exit code. **6,797 entries compared with 0 structural errors** and
the accounting identity holds — and the driver still exits `1`, because three
source apps fall in no bucket. They are named, with their scholar lemma and
our extracted band, for human adjudication. That is the point: an app that
vanishes is worse than an app that fails.

### The scholastic double apparatus

`plaoul_check.py` compares against the LombardPress print toolchain's own
output, per app: lemma, reading count, reading texts, witness sets.

```console
$ PYTHONPATH=$PWD/src python3 tools/golden/plaoul_check.py lectio1.xml lectio1.pdf
235 scholar apps | 235 compared | 0 ERRORS | 0 documented divergences | 2 suffix-unverified | anchored 206/235 | excluded rendered fields={'lemma_attribution_not_printed': 13, 'app_note_not_printed': 45}
PASS: zero apparatus errors
```

The excluded-field counters are the contract being explicit: this validates
the stylesheet's *rendered* subset, not full TEI semantics.

Sweep a whole corpus the same way:

```console
$ total=0; errs=0
$ for i in $(seq 1 30); do
    out=$(python3 tools/golden/plaoul_check.py /tmp/plaoul30/lectio$i.xml /tmp/plaoul30/lectio$i.pdf 2>&1 | tail -2 | head -1)
    n=$(echo "$out" | sed -n 's/^\([0-9]*\) scholar apps.*/\1/p')
    e=$(echo "$out" | sed -n 's/.*| \([0-9]*\) ERRORS.*/\1/p')
    total=$((total+n)); errs=$((errs+e))
    printf "lectio%-3s %5s apps  %s ERRORS\n" "$i" "$n" "$e"
  done; echo "TOTAL apps=$total errors=$errs"
lectio1     235 apps  0 ERRORS
lectio2      82 apps  0 ERRORS
…
lectio30    255 apps  0 ERRORS
TOTAL apps=6293 errors=0
```

### The unit suite

```console
$ pytest -q
219 passed in 0.42s
$ ruff check src/
All checks passed!
```

(Re-derived on 2026-08-05 in a fresh clone of `bd01130`. These are the two
commands CI runs, on Python 3.10, 3.12 and 3.14.)

### Where the harnesses stop

`tools/golden/README.md` documents the corpus and the integrity rules;
[generalization.md](generalization.md) reports what happens on nine editions
the grammars have never seen, with the fabrication spot-checks and the
inter-annotator protocol that has **not** yet been executed. Read the labels:
adversarial backtest, toolchain inversion, retypeset regression and
self-validation are four different claims.
