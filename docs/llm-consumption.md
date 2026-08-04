# LLM consumption: variant-QA evaluation and verification

## What this evaluation measures

The harness tests a narrow, falsifiable claim: given the same critical-edition
evidence, does an LLM answer apparatus questions more accurately when the
evidence is isolated and structured than when it is presented as a flat
printed page?

The 300 questions are generated mechanically from the two scholar-encoded TEI
sources used by the golden harness. No LLM writes or paraphrases a question.
Every item contains only `question`, `gold_answer`, `app_ref`, and `type`; the
app reference is a stable document-order pointer back to the source `<app>`.
Before seeded sampling, the builder excludes every locus in the golden
harness's typed print/TEI divergence registries. Otherwise a prompt could be
scored wrong for faithfully reporting the printed source instead of the TEI
re-encoding, confounding representation with an adjudicated source difference.
The five templates are:

- `witness_of_reading`: recover the TEI `@wit` set for a reading;
- `reading_of_witness`: recover the unique reading assigned to one witness;
- `lemma_vs_variant`: distinguish `<lem>` from `<rdg>`;
- `editor_attribution`: recover Balex `@source` attribution;
- `count`: count direct `<rdg>` children.

Balex has 30 questions of each type. SBLGNT has no editor `@source` data—its
sigla name comparison editions in `@wit`—so its 150 questions are balanced as
38/38/37/37 across the four applicable types. Treating `WH`, `Treg`, `NIV`, or
`RP` as editors merely to manufacture a fifth category would change the TEI's
semantics.

For every question, `run_eval.py` builds three prompts:

- **FLAT:** all raw bands on the relevant real PDF page, decoded by `regreek`.
  The runner discovers the known `/tmp` and `tools/golden/data` PDF locations,
  or accepts explicit paths. If a PDF or matching page is unavailable, it uses
  the committed short TEI-derived fallback: local constituted-text context plus
  one lossless-for-QA apparatus line. Force either behavior with
  `--flat-source pdf` or `--flat-source fallback`.
- **STRUCTURED-TEI:** the scholar facts rendered in diorthosis' canonical
  `<app>/<lem>/<rdg>` shape for the referenced locus, including normalized
  `#wit-`/`#ed-` identifiers and the `<note type="verbatim">` evidence.
- **STRUCTURED-MD:** a minimal md-ce/0.2 page section for the same constituted
  context and apparatus entry, including a shared page-scoped marker.

This is downstream QA, not a general comprehension benchmark. It measures
retrieval of lemma/reading roles and attributions from apparatus evidence. It
does not measure philological judgment, stemmatics, translation, or whether a
model can read a page image. The PDF condition tests `regreek`'s decoded page,
not pixels. The fallback condition is useful for deterministic plumbing tests
but is less cluttered than a real page and must be reported separately.

## Pre-registered hypothesis

The primary outcome is exact accuracy pooled over `witness_of_reading` and
`reading_of_witness`, computed on the fixed seed-20260804 items. The primary
directional hypothesis is:

> STRUCTURED-TEI accuracy is higher than FLAT accuracy on witness attribution.

STRUCTURED-MD versus FLAT is a secondary replication of the same directional
hypothesis. `lemma_vs_variant` is a negative-control-like secondary outcome:
FLAT may tie either structured condition because the constituted text and the
apparatus separator often expose that distinction directly. Editor attribution
and reading count are additional secondary outcomes.

These statements can lose. The primary claim is refuted for a tested model if
STRUCTURED-TEI does not exceed FLAT on the pooled witness outcome; a tie is not
support. A gain confined to lemma/variant classification does not support the
primary claim. Report every condition and type, the 95% bootstrap intervals,
the exact model identifier, endpoint implementation, flat-source counts,
dataset seed, and any failed request. Do not select a provider/model after
looking at these answers and describe the result as pre-registered.

Scoring is case- and whitespace-normalized exact match. Witness/editor lists
are set-matched, so order is irrelevant; other answers remain exact. Confidence
intervals use 10,000 deterministic bootstrap resamples by default. Prompt token
counts in dry-run output are provider-neutral UTF-8/4 estimates, not billing
tokenizer counts.

## Build and run

Fetch the pinned source TEI if it is not already present, then rebuild and
dry-run from the repository root:

```console
./tools/golden/fetch_sources.sh
python3 tools/eval/build_qa_dataset.py --seed 20260804
python3 tools/eval/run_eval.py --dry-run
```

The dry-run parses both datasets, resolves every `app_ref`, builds all 900
condition prompts, extracts real PDF pages when available, validates nonempty
contexts, and prints prompt-count and token-estimate summaries. It never reads
an API key and never makes an HTTP request. A network-free fallback-only check
is:

```console
python3 tools/eval/run_eval.py --dry-run --flat-source fallback
```

One OpenAI-compatible run (the base may be OpenAI or another compatible
`/v1` endpoint):

```console
OPENAI_API_KEY=… python3 tools/eval/run_eval.py \
  --provider openai --model MODEL_ID \
  --base-url https://api.openai.com/v1 \
  --output tools/eval/results/openai-MODEL_ID.json
```

One Anthropic Messages run:

```console
ANTHROPIC_API_KEY=… python3 tools/eval/run_eval.py \
  --provider anthropic --model MODEL_ID \
  --base-url https://api.anthropic.com/v1 \
  --output tools/eval/results/anthropic-MODEL_ID.json
```

`OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`, `EVAL_PROVIDER`, and `EVAL_MODEL` are
equivalent environment configuration. `BALEX_PDF` and `SBLGNT_PDF_DIR` override
PDF discovery; `--balex-pdf` and `--sblgnt-pdf-dir` do the same on the command
line. Use `--conditions`, `--edition`, or development-only `--limit` to narrow a
run. A completed results JSON retains each prompt, raw response, normalized
correctness decision, input provenance/page index, token estimate, and the
per-condition/per-type summary.

The generated data and its licenses are documented in
[`tools/eval/data/README.md`](../tools/eval/data/README.md). The committed files
contain short per-app excerpts only, never full printed pages.

## Verifier positioning: a hallucination gate, not another recognizer

Karamolegkou, Angleraud, Sagot, and Clérice (2026), [“Reading or Guessing?
Visual Grounding Failures of Vision-Language Models for OCR in Ancient Greek
Editions”](https://arxiv.org/abs/2605.27750), report fluent but visually
ungrounded Greek substitutions on this class of material. As summarized in
[`prior-art.md`](prior-art.md), that makes diorthosis most useful downstream of
a VLM/LLM as a **verifier**: the recognizer may propose text, while a
deterministic apparatus grammar decides whether the proposal is structurally
supported and makes abstention inspectable.

A concrete gate works as follows:

1. Keep VLM/OCR blocks marked `source=ocr`, `generative=true`; never silently
   promote generated text to decoded source.
2. Run diorthosis with the edition's declared sigla registry. For every parsed
   entry, compare the candidate's locus, lemma, reading count, reading strings,
   and witness/editor sets with the trusted TEI or other independently keyed
   reference.
3. Preserve the exact candidate apparatus slice in
   `<note type="verbatim">` beside `<lem>/<rdg>`. A parser disagreement can
   therefore be audited against what the recognizer actually emitted; structure
   never replaces its evidence.
4. Classify differences by typed kind—for example `PHANTOM`, `LEMMA`,
   `LEMMA_WITNESSES`, `READING_COUNT`, `READING_TEXT`, or
   `READING_WITNESSES`. Reject or queue every unmatched difference.
5. Allow a known print/reference discrepancy only through the fail-closed typed
   divergence schema used by `tools/golden/divergences.py`: the exact
   edition/book, locus, error kinds, print form, TEI form, band evidence, and
   reason must match. Free-text similarity is not an allowlist.

The gate returns **accept** only when structure and attribution agree,
**known-divergence** only when an exact adjudicated record accounts for the
difference, and **review/reject** otherwise. The review view can then put the
verbatim band beside the PDF crop. Important limit: a verbatim note proves what
the recognizer said, not what the pixels contain. Without an independent
reference or human/image check, diorthosis can detect unsupported structure and
force abstention but cannot certify a VLM transcription as visually true.

### Worked SBLGNT example

The seeded harness contains `sblgnt:app-00125`, locus `B01 8:7`:

```text
καὶ ] καὶ Treg NIV RP; om. WH
```

Its generated question asks which witnesses transmit `καὶ`; the gold set is
`{Treg, NIV, RP}`. Suppose a fluent VLM transcription instead assigns `καὶ`
to `WH` and treats the other editions as the omission set.
Diorthosis retains that candidate wording verbatim, while the typed comparison
against `<rdg wit="#Treg #NIV #RP">καὶ</rdg>` emits
`READING_WITNESSES` (expected `Treg/NIV/RP`, observed `WH`) at the precise app
reference. Unless an exact typed-divergence
record supplies page-band evidence for that locus, the candidate cannot enter a
critical-text database. It is rejected or sent to the page-crop review queue.
This is the same attribution fact tested in downstream QA, reused as a
machine-checkable ingestion oracle.

## Sigla normalization: `witnesses.json` is the machine interface

Every build writes `<stem>.witnesses.json` from `witness_table`; consumers
should use this sidecar, not regexes over the printed band and not a global list
of familiar sigla. Each used printed form has:

```json
{
  "siglum": "Mac",
  "base": "M",
  "hand": "ac",
  "hand_label": "before correction",
  "description": "codex M"
}
```

`siglum` is the normalized, edition-declared identifier used by apparatus
attributions. `base` links a recognized state such as `Mac`, `Mpc`, `Mmr`, or
`M1` to the declared base; `hand` and `hand_label` type that state;
`description` carries the conspectus description. Superscript-distinguished
atomic sigla such as `Nu` remain atomic. Undeclared forms are preserved with an
empty description rather than guessed.

The corresponding TEI uses registry-derived IDs such as `#wit-Mac`; join those
references through the sidecar's `siglum`. Across editions, scope identity as
`(edition, siglum)`: the letter `M` in two conspectuses is not automatically the
same manuscript. Cross-edition software may reconcile scoped records using
their descriptions or external identifiers, but the sidecar is the sole
supported boundary between printed typography and stable application IDs. This
keeps glued, superscript, and hand-state parsing in one tested implementation
instead of reproducing edition-specific guesses in every downstream LLM tool.
