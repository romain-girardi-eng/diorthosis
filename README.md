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
```

One internal model, two outputs — **a single truth, two views**:

- **TEI P5** — the scholarly interchange: `<pb n="294"/>` printed folios,
  `<anchor>` elements at apparatus markers, `<note type="apparatus"
  target="#a-p300-m6">` entries pointing into the text, translation in its
  own `<div>`, page furniture as `<fw>`.
- **Markdown (`md-ce/0.1`)** — the AI-ready view, rendered deterministically
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

## What P1 does — and does not — do

**Does:** ingest born-digital PDFs (via regreek: 9 legacy Greek encodings,
validated 98–100 % on held-out texts) and any OCR engine's ALTO, hOCR or
PAGE-XML; separate layers; extract the citable printed folio; split
apparatus bands into entries; anchor them to their in-text markers with
lemma discrimination (99.4 % of 2 026 entries over the full reference
edition); parse them into lemma/readings/attributions with honest refusal
(98.8 % parse; foreign conventions are refused, never misattributed); emit
**schema-valid TEI P5** (validated against `tei_all.rng`) and
**md-ce/0.2** — a normative Markdown format with twelve mechanically
checkable invariants ([SPEC.md](SPEC.md)).

**Does not (yet):** *interpret* the apparatus. Entries are anchored but kept
verbatim — turning `Μωσέως : Μωϋσέως Mign., Otto` into
`<app><lem>Μωσέως</lem><rdg resp="#Mign #Otto">Μωϋσέως</rdg></app>` requires
per-series grammar files (each series has its own conventions), which is
phase 2, together with the conspectus-siglorum parser that will supply the
witness registry. Marginal line-number anchoring (Teubner/OCT style) is
detected but not yet resolved. Two-column layouts are a known limitation.

## Architecture

```
ingest/          borndigital (regreek) · alto — one common model out
model.py         Document/Page/Block with Layer + Source + generative flag
anchor.py        entry splitting + marker anchoring, honest counters
tei.py           TEI P5 emission (the canonical output)
md.py            md-ce renderer (a deterministic VIEW of the same model)
cli.py           diorthosis build / inspect
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
