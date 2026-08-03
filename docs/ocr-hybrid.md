# Hybrid OCR architecture — design (August 2026)

Status: **design, grounded in published evidence**. Implementation follows the
line-granular ALTO ingest prerequisite (see § Prerequisites).

diorthosis stays OCR-agnostic: it ingests standard formats and never calls an
engine. This document fixes the *recommended* pipeline for scans, and the
arbitration semantics the model will carry.

## The two readers

**Reader A — the geometric and textual authority.** Kraken ≥ 7 with the CLLG
polytonic Greek model ([Zenodo 10.5281/zenodo.21295925](https://doi.org/10.5281/zenodo.21295925),
CC BY 4.0; measured CER 4.1 % median on a 90-page held-out benchmark whose
composition — Sources Chrétiennes, PG, GCS, Belles Lettres — matches this
project's target corpus; [arXiv 2605.27750](https://arxiv.org/abs/2605.27750)).
The model spans Greek and Latin scripts (fine-tuned from CATMuS-Print).
Reader A produces the ALTO: baselines, polygons, per-word confidence —
**it defines the geometry**. For character-level confidence, prefer Kraken's
hOCR output (`x_conf` per character).

**Reader B — the independent witness.** A vision-language model
(reference results: Qwen3-VL-8B fine-tuned synth→real, CER 1.0 % median,
[arXiv 2603.02803](https://arxiv.org/abs/2603.02803)) — **never on full
pages**. B reads line crops cut from A's polygons: every B output is born
inside an existing `TextLine`, so bbox provenance stays honest. This kills
the (real, verified) tooling gap: nothing serializes free VLM output into
coordinate-faithful ALTO; imposing the geometry beforehand makes the problem
disappear.

Why B can never be the sole reader: under controlled perturbation the VLM's
error grows 7× faster than the CTC engine's (ΔCER +0.21 vs +0.03), and its
errors are **fluent, in-lexicon Greek words** — visually unanchored
substitutions, the exact failure mode a scholarly pipeline must fear.
CTC errors are local recognition noise: loud, visible, honest.

## Arbitration — three states, never a silent choice

Per line, after NFD normalization, elision-apostrophe unification and
dehyphenation; character alignment on the line (existing tooling:
dinglehopper / ocrd-cor-asv-ann / ocreval):

| state | condition | confidence | handling |
|---|---|---|---|
| `agree` | identical in strict NFD | 0.97 | high-confidence generative |
| `agree_base` | same base letters, diacritics differ | 0.75 | light flag — the dominant, least-harmful divergence class (42–57 % of VLM errors are accentual) |
| `disagree` | base letters differ | min(conf_A, 0.5) | region flagged, **both readings preserved** |

Special rule: a span read by A but absent from B that looks like page
furniture (running head, line number, siglum) is NOT a disagreement — it is
A's dominant error class (32 %, usually *correct* readings excluded from
ground truth) and routes to the furniture layers.

**No LM post-correction.** Measured gains are marginal-to-negative on
low-resource scripts ([arXiv 2502.01205](https://arxiv.org/abs/2502.01205)),
and correction repairs text without restoring visual anchoring —
incompatible with the provenance contract.

## Why agreement (evidence)

- OCR ensemble voting is proven: ISRI 1994/1996 (42 % error reduction),
  Lopresti & Zhou 1997 (20–50 %), Reul et al. (confidence-weighted voting).
- Agreement as a *reliability estimator* is validated between VLMs
  (Consensus Entropy, [arXiv 2504.11101](https://arxiv.org/abs/2504.11101)).
- The known counter-example — CHURRO ([arXiv 2509.19768](https://arxiv.org/abs/2509.19768)):
  an Azure+Gemini ensemble did not beat its components — refutes *fusion for
  accuracy* (picking a winner), not *agreement for confidence* (knowing
  where not to trust). diorthosis only wants the second.
- **Open gap, publishable**: no published value of P(correct | agreement)
  exists in any OCR domain; CTC/autoregressive error independence is always
  assumed, never measured. Measuring it on this corpus is a contribution.

## Semantics in diorthosis

- `generative` stays `true` everywhere, without exception: agreement raises
  `confidence`, never touches provenance. An agreed span remains a machine
  guess — one that two architectures with disjoint failure modes produced
  independently.
- Model: `Block.readings: list[Reading(engine, text, confidence)]` and
  `Block.agreement ∈ {agree, agree_base, disagree, single}`.
- **TEI — the trap to avoid**: never encode an OCR disagreement as
  `<app>/<rdg>`. `<app>` is the *editor's* apparatus; polluting it with
  machine noise would destroy the project's value. Divergent spans are
  `<choice>` of two `<unclear>` with `@resp` pointing to the engines
  declared in `<respStmt>`, plus `@cert="low"`.
- md-ce: `### text [source=ocr generative=true confidence=0.55
  agreement=disagree]`, divergent span rendered explicitly:
  `‹A:προσβολὴν|B:προσβολήν›`.

## Prerequisites and open verifications

- `ingest/alto.py` currently flattens TextLines into blocks; arbitration
  requires line granularity — to be reworked first.
- CLLG model is three weeks old (7 downloads at review time): promising,
  unproven at scale; its Zenodo self-reported CER (1.18 %) is likely
  in-domain vs the 4.1 % held-out figure — use 4.1 %.
- Qwen3VL-8B-synth_real weights carry **no license** at review time: the
  deterministic Kraken path is the only one that is licensing-clean today.
- Kraken per-char confidence in ALTO/PAGE: undocumented (hOCR only) — test
  before freezing the ingest.
