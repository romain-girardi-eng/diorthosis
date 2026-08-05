# The Python API

`diorthosis.__all__` is the public Python surface — the whole of it. Everything
else in the package is internal and may be renamed, split or deleted in any
release, including a patch. What a break to this surface would require is in
[stability.md](stability.md); the artefact formats it produces are specified in
[../SPEC.md](../SPEC.md).

The command line is a *separate* contract with the same guarantee. Most users
should stay there:

```console
$ diorthosis build edition.pdf --pages 82-91 --conspectus-page 54 --text-lang la -o out/
```

Use the Python API when you need what the CLI does not hand you: the model
between the steps, the coverage object, the parsed structure of one entry, or a
pipeline of your own around the same guarantees.

## The pipeline, end to end

This script is the whole documented pipeline: PDF → anchored `Document` → TEI +
md-ce, validated. It uses nothing outside `__all__`.

```python
"""diorthosis end to end: a printed critical edition -> anchored TEI + md-ce.

    python3 example.py path/to/ldlt-balex.pdf /tmp/out

The input used below is the Digital Latin Library's own PDF of Cynthia
Damon's *Bellum Alexandrinum* (LDLT, CC BY): file pages 82-91, conspectus
siglorum on file page 54. diorthosis ships no edition content, so fetch that
PDF first -- any born-digital critical edition works, with its own page
numbers.
"""

import sys
from pathlib import Path

from diorthosis import (
  MD_CE_VERSION,
  anchor_page,
  bootstrap_registry,
  check_roundtrip,
  coverage,
  entry_keys,
  ingest_pdf,
  parse_page_spec,
  resolve_parsed,
  to_markdown,
  to_tei,
  validate_text,
  witness_table,
)

pdf = sys.argv[1]
out = Path(sys.argv[2] if len(sys.argv) > 2 else "out")
out.mkdir(parents=True, exist_ok=True)

# 1. Ingest. The printed page becomes a Document of layered Blocks; nothing
#    is generated, and OCR-borne blocks would carry generative=True forever.
doc = ingest_pdf(pdf, pages=parse_page_spec("82-91"), text_lang="la")
print(f"ingested {len(doc.pages)} page(s) via {doc.ingest}")

# 2. The edition's own conspectus siglorum IS the witness registry.
registry, note = bootstrap_registry(pdf, conspectus_page=54)
print(note or "no conspectus siglorum found")

# 3. Anchor: split each apparatus band into entries and link each entry to
#    its place in the constituted text. Returns per-page counters.
for page in doc.pages:
  anchor_page(page, registry)

# 4. Measure ONCE. This Coverage is the only score diorthosis states, and the
#    same object is rendered in the console, in the md-ce meta line and under
#    every page header (SPEC I11).
cov = coverage(doc, registry)
for line in cov.lines:
  print(line)

# 5. Two views of the SAME model. The TEI is the citable artefact; md-ce is
#    the retrieval surface, and must be given the coverage measured above.
tei_name = "example.tei.xml"
(out / tei_name).write_text(
  to_tei(doc, title="Bellum Alexandrinum", registry=registry), encoding="utf-8")
md = to_markdown(doc, title="Bellum Alexandrinum", tei_name=tei_name, cov=cov)
(out / "example.md").write_text(md, encoding="utf-8")

# 6. The spec, executable: md-ce invariants, then md-ce <-> TEI equivalence.
print(f"md-ce/{MD_CE_VERSION}: {len(validate_text(md))} violation(s)")
print(f"roundtrip: {len(check_roundtrip(out / 'example.md', out / tei_name))} violation(s)")

# 7. Read the structure back off the model. entry_keys() gives the same key an
#    overrides record uses, so this is also how you write one by hand.
structured = [
  (key, entry, parsed)
  for page in doc.pages
  for key, entry in entry_keys(page)
  if (parsed := resolve_parsed(entry, registry)) is not None and parsed.readings
]
if structured:
  key, entry, parsed = structured[0]
  print(f"{key}: {entry.source_slice!r}")
  print(f"  lemma   {parsed.lemma!r}")
  print(f"  reading {parsed.readings[0].text!r} "
        f"wit={parsed.readings[0].attribution.witnesses}")
else:
  print("no entry parsed: the apparatus is present verbatim, nothing is claimed")

# 8. Describe only the sigla the emitted apparatus actually uses.
used = set()
for page in doc.pages:
  for _key, entry in entry_keys(page):
    parsed = resolve_parsed(entry, registry)
    if parsed is None:
      continue
    used.update(parsed.lemma_attribution.witnesses)
    for reading in parsed.readings:
      used.update(reading.attribution.witnesses)
rows = witness_table(registry, used)
print(f"witnesses used: {len(rows)}")
print(rows[0] if rows else "no siglum attributed")
```

Run on `ldlt-balex.pdf` (diorthosis 0.7.0, regreek 0.7.2, CPython 3.13.5),
verbatim:

```console
$ python3 example.py ldlt-balex.pdf /tmp/out
ingested 10 page(s) via borndigital
conspectus: 24 witnesses, 103 editors declared
coverage: 63 entries — 63 parsed, 0 refused, 0 unparsed; 63 anchored (60 attached, 3 end-only), 0 unanchored
refusals: none
md-ce/0.3: 0 violation(s)
roundtrip: 0 violation(s)
p82-e0: '5 cotidie operibus USTV | cotidie M (cf. BC 3.112.9) | nouis cotidie\n\noperibus Castiglioni (cf. Tac. Hist. 2.76.4)'
  lemma   'cotidie operibus'
  reading 'cotidie' wit=['M']
witnesses used: 15
{'siglum': 'M', 'base': 'M', 'hand': '', 'hand_label': '', 'description': 'Florence, BML Plut.'}
```

Two things in that output are the contract, not decoration. **`63 anchored (60
attached, 3 end-only)`** — three entries reach the text by their end anchor
alone, because the lemma's start could not be located with confidence; SPEC I11
forbids reporting them as plainly anchored. And **`entry.source_slice`** still
carries the printed band's own line break inside the entry (`\n\n`), because the
slice is byte-exact: the parsed lemma and reading are a *reading of* it, never a
replacement for it.

`tests/test_public_api.py` extracts this exact block from this file, checks it
uses only frozen names, and runs it whenever a born-digital PDF is available.

## The symbols

Everything below is frozen; see [stability.md](stability.md) for what that
means. Nothing else in the package is.

### Metadata

| Symbol | What it is |
|---|---|
| `__version__` | `str`, the tool version. Stamped into every TEI header and md-ce meta line. Equals the version in `pyproject.toml`. |

### Ingest — a source file becomes a `Document`

| Symbol | What it is |
|---|---|
| `ingest_pdf(path, pages=None, text_lang="grc") -> Document` | Born-digital PDF, via regreek: legacy-font decoding, layer separation, printed-folio extraction. `text_lang="la"` reads the Latin-script main band as the constituted text and its foot band as the apparatus. |
| `ingest_alto(paths) -> Document` | ALTO XML, one file per page — any OCR engine's export. |
| `ingest_hocr(paths) -> Document` | hOCR, possibly multi-page. |
| `ingest_pagexml(paths) -> Document` | PAGE-XML, one file per page. |
| `parse_page_spec(spec) -> list[int] \| None` | `"290-320"`, `"1,5,9"`, `"1,5-7"` → sorted, de-duplicated 0-based indices; `None` passes through. Raises `ValueError` on an empty spec, a reversed range, or a non-numeric element. |

Every block an OCR adapter produces carries `generative=True`, permanently, into
both outputs. diorthosis never calls a recognition engine itself.

### The document model

| Symbol | What it is |
|---|---|
| `Document` | `source_name`, `pages`, `ingest`; `.any_generative`. |
| `Page` | `index` (0-based file coordinate), `printed_page` (the citable folio, or `None`), `blocks`; `.blocks_of(layer)`. |
| `Block` | `layer`, `text`, `source`, `generative`, `confidence`, `evidence`, `inline_refs`, `entries`. |
| `Layer` | `TEXT`, `APPARATUS`, `TRANSLATION`, `NOTES`, `HEADING`, `RUNNING_HEAD`, `PAGE_NUMBER`, `UNKNOWN`. |
| `Source` | `BORN_DIGITAL`, `OCR`. |
| `Anchor` | How one entry reaches the text: `kind` (`"marker"` / `"line"`), `value`, `block_index`, `char_offset`, `digit_start`, `digit_end`. |
| `ApparatusEntry` | One split, uninterpreted entry. `raw` is the normalized parsing view; **`source_slice` is the immutable byte-exact substring** and is what every citable output quotes. Also `anchor`, `parsed_*`, `override_action`, `marker_eligible`, `refusal_evidence`. |

### The witness registry

| Symbol | What it is |
|---|---|
| `Registry` | `witnesses: dict[str, str]`, `editors: dict[str, str]`; `.is_witness`, `.is_editor`, `.xml_id`. |
| `bootstrap_registry(pdf_path, conspectus_page=None) -> (Registry, str)` | Find and parse the edition's own conspectus siglorum, extended with the built-in editor registry. The `str` is a human-readable note, empty when nothing was found. |
| `with_builtin_editors(reg) -> Registry` | Extend a hand-built registry with the curated editor list; declared entries win. Use this on the OCR path, where there is no front matter to search. |
| `witness_table(registry, used_sigla) -> list[dict]` | The `witnesses.json` rows: `siglum`, `base`, `hand`, `hand_label`, `description`. Undeclared sigla keep an empty description rather than an invented one. |

### Anchoring and coverage

| Symbol | What it is |
|---|---|
| `anchor_page(page, registry=None) -> dict[str, int]` | Split every apparatus band on the page into entries, run the convention gates, anchor what can be anchored. Mutates the page; returns counters. |
| `split_entries(apparatus_text) -> list[ApparatusEntry]` | Numeric-marker entry splitting alone, verbatim — to inspect a band without anchoring it. |
| `coverage(doc, registry=None) -> Coverage` | Measure once. Pass the *same* registry the TEI is emitted with, or parsing is understated. |
| `Coverage` | `entries`, `parsed`, `refused`, `unparsed`, `attached`, `end_only`, `unanchored`, `refusals`, `pages`; `.anchored`, `.report`, `.refusal_tally`, `.lines`. Two partitions of the same entries: structure and attachment. |

### The parsed apparatus structure

| Symbol | What it is |
|---|---|
| `ParsedEntry` | `lemma`, `lemma_attribution`, `readings`, `comments`. |
| `Reading` | `text`, `attribution`. An omission is an empty `text` with `om.` among the qualifiers. |
| `Attribution` | `witnesses`, `editors`, `qualifiers`, `sources`, `references`; `.empty`. Manuscripts and editors are kept apart because the TEI puts them in different attributes. |
| `resolve_parsed(entry, registry) -> ParsedEntry \| None` | One entry's structured reading, in priority order: human review wins over every grammar, a review `verbatim` forces the refusal, a gate refusal returns `None`. The TEI emitter and the review UI both call this, so they can never show different structures. |
| `GateDecision` | `grammar`, `accepted`, `evidence`; `.accept()`, `.refuse()`. A whole-band convention gate's verdict. A refusal carries its own sentence, which becomes a key in the coverage refusal tally. |

### Emission

| Symbol | What it is |
|---|---|
| `to_tei(doc, title=None, registry=None) -> str` | TEI P5, the citable artefact. Serialized, NFC-normalized, newline-terminated. |
| `to_markdown(doc, title=None, tei_name="", cov=None) -> str` | md-ce, the retrieval view. Pass the `Coverage` you measured; omitting it re-measures registry-less and understates parsing. |
| `TEI_NS` | `"http://www.tei-c.org/ns/1.0"`. |
| `MD_CE_VERSION` | The md-ce version this build **emits**. |
| `MarkerDelimiterError` | Raised by `to_markdown` when source text contains `⟦`/`⟧` (SPEC I4): an ambiguous file is refused, never emitted. Subclass of `ValueError`. |

### Validation — the spec, executable

| Symbol | What it is |
|---|---|
| `validate_text(content) -> list[Violation]` | Check a md-ce document against SPEC.md. Empty list = clean. |
| `validate_file(path) -> list[Violation]` | Same, from disk. |
| `Violation` | `invariant`, `line` (1-based; 0 = file-level), `message`; `str()` renders the CLI's line. |
| `MD_CE_SUPPORTED` | The md-ce version this validator **checks**. A file of another version is rejected, not best-effort read. |
| `check_roundtrip(md_path, tei_path) -> list[str]` | Verify the two views carry the same projected content. Empty list = equivalent. |

### Human-review overrides

| Symbol | What it is |
|---|---|
| `OVERRIDES_FORMAT` | `"diorthosis-overrides/1"`. |
| `load_overrides(path) -> dict[str, dict]` | Read and validate an overrides file. Every failure is a refusal to guess: unversioned container, missing content binding, unusable action. |
| `apply_overrides(doc, overrides) -> dict` | Apply in place, **all or nothing**. A record whose `source_sha` no longer matches its entry raises with an itemised drift report rather than replaying a human correction onto a different entry. Returns `applied`, `verbatim`, `unmatched`. |
| `entry_keys(page) -> list[tuple[str, ApparatusEntry]]` | The `p{index}-e{k}` keys an overrides file uses. |

## What is deliberately not here

`detect_marginal_line_numbers` was exported by 0.7.0 and is **not** part of the
frozen surface: it is a layer-detection diagnostic that no pipeline step calls.
It still exists at `diorthosis.anchor.detect_marginal_line_numbers`, on internal
terms.

The convention grammars (`grammar`, `linegrammar`, `versegrammar`,
`paragraphgrammar`), the lemma matcher (`match`), the review UI (`review`), the
ingest adapters' internals and `cli` itself are internal. Read them; do not
import them.
