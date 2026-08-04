# diorthosis

**Compile published critical editions into TEI P5 and AI-ready Markdown —
with the apparatus criticus anchored, deterministic, and honest about its
provenance.**

Two centuries of textual scholarship — the record of what the manuscripts
actually read, who conjectured what, which witness carries which variant —
exist only on paper and in PDFs. Even the flagship open corpora carry the
constituted text alone: **the apparatus criticus is absent from the digital
ecosystem**. No retrieval pipeline, no language model, no digital edition
can answer *"what does manuscript A read here?"* — because that data was
never structured anywhere.

The entire TEI ecosystem works forward (encode by hand, then publish).
`diorthosis` builds the road back: **published edition in → structured
edition out.**

```console
$ pip install diorthosis

$ diorthosis build edition.pdf -o out/
wrote out/edition.tei.xml
wrote out/edition.md
apparatus anchoring: 277/287 entries anchored

$ diorthosis build --alto page1.xml page2.xml -o out/   # any OCR engine

$ diorthosis validate out/edition.md                    # the spec, executable
OK: md-ce/0.2 invariants hold
```

One internal model, two outputs — **a single truth, two views**:

- **TEI P5** — the scholarly interchange: `<pb n="294"/>` printed folios,
  `<anchor>` elements at apparatus markers, `<note type="apparatus"
  target="#a-p300-m6">` entries pointing into the text, translation in its
  own `<div>`, page furniture as `<fw>`.
- **Markdown (`md-ce/0.2`)** — the AI-ready view, rendered deterministically
  from the same model: every section is a `###` header naming its layer with
  bracketed provenance, so **a chunker can never mix apparatus into text**;
  markers appear as `⟦6⟧` in the text and at the head of the matching entry.

```markdown
## page 294 (file index 300)

### text [source=born_digital generative=false confidence=0.90]
…καὶ τοὺς⟦7⟧ κατὰ τὸν νόμον τὸν Μωσέως⟦3⟧ πολιτευσαμένους…

### apparatus [source=born_digital generative=false confidence=0.90]
⟦3⟧ Μωσέως : Μωϋσέως Mign., Otto, Goodsp. (hic et infra : 45, 3)
⟦7⟧ Τοὺς add. sup. l. A1.
```

## The provenance contract

Inherited from [regreek](https://github.com/romain-girardi-eng/regreek),
which does the character-level work (legacy Greek font decoding) and the
page-level work (layer separation, printed-folio extraction):

1. **Nothing is generated.** Born-digital text is a deterministic decoding
   of the file's own glyph stream. The single normalization performed —
   superscript apparatus markers become anchors — is declared in the TEI
   header.
2. **OCR is welcome, and permanently marked.** `diorthosis` is
   **OCR-agnostic by design**: it never calls an engine, it ingests the
   standard output formats (ALTO today; hOCR and PAGE-XML planned) that
   Kraken, eScriptorium, Tesseract and Transkribus all export. Every block
   that came from OCR carries `generative=true` into both outputs, forever —
   a recognition model's guess is never allowed to impersonate a decoded
   text.
3. **Honest coverage.** Anchoring reports its own score (`277/287 entries
   anchored`); unanchored entries are preserved, never dropped; prose bands
   (apparatus fontium) are never forced into the numeric mold.

## What it does — and does not — do (v0.5)

**Does:** ingest born-digital PDFs (via regreek: 9 legacy Greek encodings,
validated 98–100 % on held-out texts) and any OCR engine's ALTO, hOCR or
PAGE-XML; separate layers; extract the citable printed folio; split
apparatus bands into entries and anchor each to its exact place in the
constituted text; **parse the apparatus into structured
`<app>/<lem>/<rdg>`** with witness and editor attributions drawn from the
edition's own conspectus siglorum, under three convention grammars —
numeric markers (Sources Chrétiennes family), verse-referenced (biblical
editions), line-referenced reledmac (DLL family) — plus superscript
sigla; refuse verbatim what a grammar does not define; emit
**schema-valid TEI P5** (validated against `tei_all.rng`) and
**md-ce/0.2** — a normative Markdown format with twelve mechanically
checkable invariants ([SPEC.md](SPEC.md)), enforced by
`diorthosis validate`. Outputs are byte-deterministic.

**Does not (yet):** parse the paragraphed-reledmac DOUBLE apparatus
(fontium + variants — in progress on the Plaoul commentary); represent
negative apparatus (where the lemma's support is implied by silence);
handle two-column layouts; and **no accuracy figures exist yet for noisy
OCR input** — every number below is measured on born-digital PDFs.

## Evidence — and what each test does and does not prove

The test suite is layered by epistemic strength. Read the labels: they
are different claims.

1. **Adversarial backtest** (the printed PDF and the scholarly TEI were
   produced *independently* of each other): the whole SBLGNT New
   Testament — the official published PDF against the PTA's TEI
   re-encoding of the same apparatus. **6 800 entries, 0 structural
   errors**, with 59 print-vs-TEI divergences documented one by one
   under an explicit adjudication protocol (a claimed divergence must be
   *provable from the extracted band itself* — the band contains our
   reading and not the TEI's, or the printed sigla side with us; every
   key carries its citation). This is the strongest evidence the suite
   has, and it covers ONE convention on ONE atypically regular apparatus
   (editions cited, not manuscripts).

2. **Toolchain-inversion tests** (the official PDF is *generated from*
   the reference TEI by the project's own toolchain — zero alignment
   ambiguity, but parser and typesetter see the same conventions): the
   DLL Bellum Alexandrinum, 563 entries, 0 errors, 100 % anchored.
   These prove the grammar inverts a real typesetting chain exactly.
   They do **not** prove generalization to independently set editions.

3. **Retypeset goldens** (we typeset the scholar's TEI ourselves, then
   parse our own print — self-generated ground truth, kept as
   *regression tests*): balex 524, SBLGNT 6 906, Problemata 5 524 —
   0 errors. A generator and a parser can share a blind spot; these
   numbers guard against regressions, nothing more.

4. **Real edition without digital ground truth** (self-validation
   metrics only): Bobichon's Justin Martyr, 2 031 entries — 99.3 %
   anchoring, 99.0 % parse, 97.5 % lemma concordance, **89.8 %
   attribution**. Read that last number honestly: roughly one entry in
   ten needs a human eye on its attributions. On such editions
   diorthosis is a *pre-annotation* tool, not a replacement for review.

What is **not** yet demonstrated: generalization to editions never seen
during grammar development. The next benchmark is a public table over
~10 unseen editions (including scanned Teubner-era prints through a real
OCR front-end) with independently double-keyed samples — until it
exists, the zeros above should be read within the limits stated here.

## Architecture

```
ingest/          borndigital (regreek) · alto · hocr · pagexml — one model out
model.py         Document/Page/Block with Layer + Source + generative flag
anchor.py        entry splitting + marker anchoring, honest counters
tei.py           TEI P5 emission (the canonical output)
md.py            md-ce renderer (a deterministic VIEW of the same model)
mdce_validate.py md-ce invariant checker (SPEC.md, executable)
cli.py           diorthosis build / inspect / validate
```

## Legal note

`diorthosis` is a tool, not a corpus: it ships no edition content, and what
you run it on is your responsibility under your jurisdiction. The ancient
text itself is not copyrightable; apparatus prose and modern translations
may be. There are unambiguous lawful uses — from editions you have the
rights to, to public-domain editions, to text/data-mining provisions where
they apply.

## Citation & license

MIT. If this tool contributes to published research, please cite it (see
`CITATION.cff`).
