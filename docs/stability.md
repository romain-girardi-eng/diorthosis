# What 1.0 freezes

A tool that compiles a scholar's edition into a citable artefact makes a
promise beyond correctness: that the artefact keeps its meaning. A TEI file
produced today must still be readable by the same XPath in three years; an
`overrides.json` a reviewer filled in must still land on the entry they were
looking at; a pipeline that shells out to `diorthosis build` must still be able
to tell success from refusal by the exit code alone.

This document says exactly what is frozen, exactly what is not, and what a
break to a frozen thing would require. It is deliberately conservative about
what it promises: **everything not listed here is internal.** Freezing little
and honouring it is worth more than freezing much and drifting.

Six contracts are frozen:

1. the command line — subcommands, flags, and the four exit codes;
2. `md-ce/0.3` — its grammar, its twelve invariants (ten of which
   `diorthosis validate` decides from the file alone; I8/I9 concern the
   relationship to the source and are enforced at emission), its chunking
   contract;
3. the TEI shape — the element and attribute patterns a consumer selects on;
4. the `witnesses.json` row schema;
5. `diorthosis-overrides/1` — the human-review file;
6. `diorthosis.__all__` — the Python API.

Two of them carry their own version *inside the artefact* (`md-ce/0.3`,
`diorthosis-overrides/1`). That is the mechanism that makes a future break
safe: a reader that meets a version it does not implement refuses it, and no
file is ever reinterpreted under rules it was not written for.

---

## 1. The command line

Frozen: the subcommand names, the option names and their semantics, and the
exit codes. Not frozen: help prose, progress messages, and the wording of
anything printed other than the coverage report, whose shape is fixed by §2.

```
diorthosis build     [PDF | --alto XML… | --hocr HTML… | --page-xml XML…]
                     -o DIR [--pages SPEC] [--title T] [--conspectus-page N]
                     [--text-lang grc|la] [--overrides JSON] [--sigla S1,S2,…]
                     [--ignore-self-check]
diorthosis inspect   PDF --page N [--conspectus-page N]
diorthosis validate  FILE.md
diorthosis roundtrip FILE.md FILE.tei.xml
diorthosis review    PDF -o DIR [--pages SPEC] [--conspectus-page N]
                     [--text-lang grc|la] [--overrides JSON]
```

`build` writes exactly three files into `-o`, named from the source stem
(truncated to 60 characters, `edition` if empty): `STEM.tei.xml`, `STEM.md`,
`STEM.witnesses.json`. `review` writes `index.html` and its snippets.

`--pages` takes 0-based file indices: `290-320`, `1,5,9`, or a mix. The
selection is sorted and de-duplicated before ingestion.

### The four exit codes

| Code | Meaning |
|---|---|
| `0` | Success. The command ran and diorthosis certifies its result. |
| `1` | **Refused.** The command ran and diorthosis does *not* certify what it produced: a degenerate build, md-ce its own validator rejects, invariant violations, a source too ambiguous to emit. Files may have been written; they are explicitly uncertified. |
| `2` | User-actionable input error: bad flags, missing file, empty or reversed page spec. |
| `3` | Internal fault — a diorthosis defect, not an input problem. |

The distinction between `1` and `2` is the whole point of having four codes: a
caller must be able to tell "your command was wrong" from "your edition is
harder than this tool can honestly handle". `--ignore-self-check` turns a
`build` **self-check** refusal into `0` **and says so on stderr**; it never
suppresses the findings, and it does not touch the other refusals (an
ambiguous source that md-ce cannot represent still exits `1`).

A future change may add a subcommand, an option, or a new refusal *reason*.
Removing a subcommand or an option, changing what an option means, or making a
code mean something else is a break.

## 2. md-ce/0.3

Normative in [../SPEC.md](../SPEC.md): the ABNF-style grammar, the twelve
invariants I1–I12, the round-trip guarantee, and the chunking contract C1–C4.
`diorthosis validate` is that specification executed, and `MD_CE_SUPPORTED`
names the one version it checks.

Frozen, and worth naming because consumers build on them:

- **One coverage report, three renderings.** The `report` production is
  rendered identically in the meta line, under every page header, and by the
  CLI. It partitions its entries twice — `parsed + refused + unparsed =
  entries` and `attached + end-only + unanchored = entries` — and `attached`
  means a complete double-end-point link, never an end anchor alone (I11).
- **Refusals are named.** Every refused entry appears in the meta refusal
  tally, whose counts sum to `refused`; `none` is legal only when `refused` is
  0.
- **`⟦folio:n⟧` markers are page-scoped** and never resolvable across pages
  (I3, C4). A `?` marks an unresolved anchor and must not be resolved by
  search.
- **Layers never merge.** A chunk is one `### ` section; a `text` chunk and an
  `apparatus` chunk are separate chunks with separate provenance (I2, C1, C2).
- **`generative=true` is derived from the model, never from content** (I10),
  and must be surfaced wherever the text is quoted (C3).
- **Addressability**: `(file index, block)` identifies a section for the life
  of the file, `block` counting furniture so the ordinal matches the TEI's
  block order (I6).
- **Determinism**: byte-identical input and version give byte-identical output
  (I12).

The *content* of a refusal reason is data, not contract: gates may be reworded
or added, and the tally keys change with them. Their *shape* is frozen — a
reason may not contain `;` or `·`, and the tally must always sum.

A change to any invariant, or to the grammar, is `md-ce/0.4`, and the 0.3
validator will reject 0.4 files rather than half-read them.

## 3. The TEI shape

Normative definition: [../SPEC.md](../SPEC.md) Part 2, T1–T9. What is frozen is
the shape a consumer selects on — element names, attribute names, `xml:id`
patterns, and the meaning of each. What is *not* frozen is which entries manage
to be parsed at all, or the prose of the header paragraph.

```
TEI/text/body/div[@type='edition']          the edition, page by page
TEI/text/body/div[@type='translation']      facing translation, if any
```

| Pattern | Meaning |
|---|---|
| `pb/@xml:id = "page-{file index}"` | one per ingested page; `@n` is the printed folio when the page prints one |
| `anchor/@xml:id = "a-p{file index}-e{k}"` | **end** anchor of entry `k` of that page, at the printed marker; `@n` is the marker as printed |
| `anchor/@xml:id = "a-p{file index}-e{k}-start"` | **start** anchor, present only when the lemma's start was located confidently; carries no `@n` |
| `app/@from`, `app/@to` | `@to` is the end anchor, `@from` the start anchor. **`@to` without `@from` is an end-only link** — the lemma's start could not be located, and the entry must not be read as a located span |
| `app/@n` | the marker as printed, when the entry carries one |
| `app/@resp = "#human-review"` | the structure comes from a human reviewer's override, not from a grammar |
| `note[@type='verbatim']` | the entry's byte-exact printed source slice, always present on a parsed `app` |
| `note[@type='apparatus']` | an entry diorthosis did **not** parse, kept whole; `@target` points at its end anchor when it has one, `@resp="#human-review"` when a reviewer forced it verbatim |
| `note[@type='comment']` | parenthesised commentary attached to a parsed entry |
| `note[@type='cited-source']` | cited versions/loci inside a reading's attribution |
| `note[@type='witness-ref']` | a witness reference printed inline in the text band |
| `note[@type='editorial']` | an editorial/translator's note block |
| `lem`, `rdg` | `@wit="#wit-…"` for manuscripts, `@source="#ed-…"` for editors (TEI 13.1.2), `@cert="low"` for `ut vid.`/`fort.`. An omission is an **empty** element |
| `witDetail/@wit` | a placement note (`sup. l.`, `in marg.`…) about one witness |
| `listWit/witness/@xml:id = "wit-{token}"` | `@corresp` points a witness *state* at its declared base; `abbr[@type='siglum']` carries the siglum as printed |
| `listBibl/bibl/@xml:id = "ed-{token}"` | `abbr` carries the editor token as printed |
| `respStmt/@xml:id = "human-review"` | emitted whenever any entry was overridden |
| `variantEncoding` | `method="double-end-point" location="internal"`, present exactly when the document contains an `app` |
| `ab/@subtype='generative'`, `p/@subtype='generative'`, `ab[@type='unclassified']` | OCR-borne text, permanently marked |
| `fw[@type='running-head']`, `fw[@type='page-number']` | page furniture, kept rather than dropped |
| `label[@type='section-title']` | a printed section heading (`head` is not legal outside a `div`'s opening sequence, and diorthosis refuses to infer `div` nesting) |

`{token}` in `wit-` / `ed-` is the siglum or editor abbreviation passed through
an **injective** escape: ASCII alphanumerics unchanged, every other character
as `u{hex}`. That is why `ω` becomes `wit-u3c9` and `M*` cannot collide with
`M`. The escape is frozen because dereferencing `@wit` depends on it.

The output is serialized with an XML declaration, indented two spaces except
inside mixed content (`ab` stays byte-verbatim), NFC-normalized, and
newline-terminated. Codepoints XML 1.0 forbids are replaced with `U+FFFD`,
visibly.

## 4. `witnesses.json`

Normative definition: [../SPEC.md](../SPEC.md) Part 3, W1–W3.
`STEM.witnesses.json` is a JSON **array**, UTF-8, `indent=1`, non-ASCII
unescaped, one row per siglum the emitted apparatus actually uses, sorted by
siglum. Frozen row schema — all five keys always present, all values strings:

```json
{
  "siglum": "Mac",
  "base": "M",
  "hand": "ac",
  "hand_label": "before correction",
  "description": "The uncorrected reading in M. Equivalent to"
}
```

| Key | Meaning |
|---|---|
| `siglum` | the token as printed in the apparatus |
| `base` | the declared witness it is a state of, or `siglum` itself when it is not a compound or the base is undeclared — never an inferred base |
| `hand` | the state suffix: `ac`, `pc`, `c`, `mr`, `*`, or a digit; `""` when there is none |
| `hand_label` | the stable English expansion of `hand`; `""` when there is none |
| `description` | the conspectus siglorum's own words, `""` when the edition declared nothing — an undeclared siglum is reported empty, never described from guesswork |

The set of `hand` values and their labels may grow. Renaming a key, dropping
one, or changing a label's meaning is a break.

## 5. `diorthosis-overrides/1`

Normative definition: [../SPEC.md](../SPEC.md) Part 4, O1–O6. The human-review
file. Its container is versioned inside the file, and `load_overrides` checks
`format` exactly: an unversioned file (the pre-1.0 flat object) and a version
from a newer diorthosis are both clean errors.

```json
{
  "format": "diorthosis-overrides/1",
  "entries": {
    "p300-e6": {
      "source_sha": "5e7a5cd50cd1",
      "source_excerpt": "3 Μωσέως : Μωϋσέως Mign., Otto, Goodsp.",
      "action": "parse",
      "lemma": "Μωσέως",
      "lemma_wits": [], "lemma_editors": [], "lemma_qualifiers": [],
      "readings": [
        {"text": "Μωϋσέως", "wits": [], "editors": ["Mign.", "Otto"],
         "qualifiers": []}
      ],
      "comments": ["(hic et infra : 45, 3)"],
      "note": "reviewer: split the glued editors"
    },
    "p301-e2": {
      "source_sha": "0f0d0e6c6b70",
      "action": "verbatim",
      "note": "prose note, not a variant entry"
    }
  }
}
```

Frozen:

- the key `p{page.index}-e{k}` — 0-based file page, `k` counting apparatus
  entries across the whole page in document order (`entry_keys`);
- `source_sha` — the first **12** hex characters of SHA-256 over the entry's
  immutable `source_slice` with `CRLF`/`CR`/`LF` each replaced by one space
  (md-ce I8's sole declared apparatus transform). Not `hash()`:
  `PYTHONHASHSEED` must never decide whether a human correction replays;
- `action` — `"parse"` or `"verbatim"`, and nothing else. `"parse"` requires
  `lemma`;
- the replay semantics: the positional key *locates* a candidate,
  `source_sha` *decides*, and a mismatch refuses **the whole file**, itemised,
  rather than re-matching fuzzily. A drifted correction replayed onto another
  entry would be a fabricated structure wearing `resp="#human-review"`;
- `source_excerpt` and `note` are provenance for the reviewer and never affect
  matching.

Any change to the container, the key form, or the digest is
`diorthosis-overrides/2` — never a silent reinterpretation of files already on
disk.

## 6. `diorthosis.__all__`

Forty names, listed and documented in [api.md](api.md), grouped as: version;
ingest and page selection; the document model; the witness registry; anchoring
and coverage; the parsed apparatus structure; emission; validation; overrides.
`tests/test_public_api.py` asserts the list literally, so adding or removing a
name is a deliberate, reviewed act.

Frozen: each name exists, each keeps its meaning, and the listed attributes of
each exported dataclass keep their names and meanings. Adding a field to a
dataclass, or adding a keyword argument with a default that preserves current
behaviour, is not a break.

Not frozen inside the package: `diorthosis.cli` as an importable module (the
*command line* is frozen, not its Python shape), the module in which a public
name happens to live, and every underscore-prefixed name.

One import-time property is contractual because it is fragile:
`diorthosis.__version__` is assigned **before** the package's own imports,
because `tei.py` and `md.py` do `from . import __version__` to stamp the tool
version into every artefact. Reordering breaks the package at import time; a
test pins it in a fresh interpreter.

---

## What is **not** frozen

Saying this plainly is part of the contract. None of the following may be
depended on, and all of it may change in a patch release:

- **Everything internal.** `grammar`, `linegrammar`, `versegrammar`,
  `paragraphgrammar`, `match`, `review`, `roundtrip`'s internals, the ingest
  adapters' internals, `conspectus`'s regular expressions, and every
  underscore-prefixed name anywhere. Module boundaries themselves may move.
- **Gate thresholds and heuristics.** The token-consumption ratios, the
  marker-band evidence rule, the pitch/size geometry regreek uses to separate
  layers, the conspectus search horizon. These exist to make refusal *right*,
  and tightening them is exactly the maintenance this tool needs. A change here
  can move which entries parse — which is why coverage is measured and printed
  rather than promised.
- **Coverage numbers.** `563 parsed`, `99.3 % anchored` and the like are
  *measurements of a specific edition at a specific revision*, re-derivable
  from the harnesses in `tools/golden/`. They are evidence, not API. A version
  that parses more, or refuses more because it learned to distrust something,
  is not in breach.
- **Refusal reason strings**, and therefore the md-ce refusal tally keys. Their
  shape is frozen (§2); their wording is not.
- **The built-in editor registry** (`diorthosis/data/editors.json`). It grows.
  An edition's own conspectus always wins over it.
- **The review UI**: `index.html`, its layout, its CSS, the snippet file names.
  What it *exports* is `diorthosis-overrides/1`, and that is frozen.
- **Console prose** other than the coverage report and the exit codes: notes,
  warnings, the conspectus summary, `[!]` lines.
- **The regreek dependency's behaviour.** diorthosis pins a compatible range;
  layer separation is upstream and evolves with its own evidence.
- **Python version support** beyond the declared `requires-python`, which may
  rise in a minor release.

## What a break would require

A break is any change that makes a previously valid artefact, invocation or
import stop working or change meaning. To ship one:

1. **Bump the artefact's own version first.** `md-ce/0.4`,
   `diorthosis-overrides/2`. The reader for the old version must refuse the new
   one explicitly rather than best-effort read it — that mechanism already
   exists in both readers and is the reason a break can be safe at all.
2. **Bump the tool's major version** and name the break in the changelog: what
   changed, why the old behaviour was wrong, and what a reader or a stored file
   must do about it. "It was cleaner" is not a reason; "it stated something
   false" is.
3. **Keep the old name importable for one minor release** with a
   `DeprecationWarning` whenever a Python symbol is removed or renamed, unless
   the old name is itself the defect.
4. **Re-derive every published figure.** The certified numbers in `README.md`,
   `FINDINGS.md` and `docs/generalization.md` are measured through the output
   shapes above; a change to those shapes invalidates them until the harnesses
   in `tools/golden/` are re-run and the numbers re-stated from the re-run, not
   retyped from the previous release.
5. **Show the migration on a real edition**, not a fixture: build the same
   pages before and after, and diff.

The one thing that never needs a version bump is *refusing more*. If a gate
learns that something it used to structure was not evidence, tightening it is a
bug fix, however many entries it moves out of `parsed` — the numbers are
measurements, and a structure that was never supported by the printed page was
never data.
