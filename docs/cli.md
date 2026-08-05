# The `diorthosis` command line

Every command on this page was executed against diorthosis 0.7.0 at
`bd01130` on 2026-08-05; the outputs are pasted from those runs. Where a
listing is long, it is cut and the cut is marked.

- **New here?** Read [tutorial.md](tutorial.md) first — it walks one real
  edition from PDF to checked TEI.
- **A command failed?** [troubleshooting.md](troubleshooting.md) lists the
  real messages and what each one means.

## Running it

Two ways, and the docs use whichever is shorter.

**Installed** (from PyPI once published, or from a clone — see
[the README](../README.md#install)). The console script is on your PATH:

```console
$ diorthosis --help
usage: diorthosis [-h] {build,inspect,validate,roundtrip,review} ...

Compile published critical editions into TEI P5 + AI-ready Markdown

positional arguments:
  {build,inspect,validate,roundtrip,review}
    build               compile a source into TEI + Markdown
    inspect             show one page's anchored structure
…
```

**From a working copy, uninstalled.** There is no console script, and
`python3 -m diorthosis.cli` only finds the package if you point at `src/`:

```console
$ cd /path/to/diorthosis
$ PYTHONPATH=$PWD/src python3 -m diorthosis.cli build …
```

Forgetting `PYTHONPATH` gives `No module named 'diorthosis'`. The drivers in
`tools/golden/` insert `src/` themselves, with one exception documented in
[troubleshooting.md](troubleshooting.md#no-module-named-diorthosis).

## Page numbers are 0-based, always

`--pages`, `--page` and `--conspectus-page` count **PDF file pages from 0**.
They are not the folios printed on the page, and they are not the 1-based
numbering most PDF viewers and `pdf2txt.py --page-numbers` show. The first
sheet of the file is `0`.

The folio *printed* on the page is a different thing: it is what `md-ce`
writes in `## page 25 (file index 7)` — `25` printed, `7` in the file — and
what the TEI carries as `<pb n="25"/>`. A page with no printed folio is `–`.

## Exit codes

Identical for every subcommand; printed by `--help`.

| code | meaning |
|---|---|
| `0` | success |
| `1` | **refused** — the command ran and diorthosis does not certify its result |
| `2` | user-actionable input error (bad flag, missing file, empty page set, malformed overrides) |
| `3` | internal fault — a diorthosis defect, not your input |

`1` is not a crash. It means the tool produced something it will not vouch
for: a degenerate build, an md-ce its own validator rejects, invariant
violations, a source too ambiguous to emit. **`build` writes its output files
before exiting 1** — they are on disk, they are simply not certified.

---

## `diorthosis build`

Compile one source into TEI P5 + md-ce + a witness table.

```console
$ diorthosis build --help
usage: diorthosis build [-h] [--alto XML [XML ...]] [--hocr HTML [HTML ...]]
                        [--page-xml XML [XML ...]] [--pages PAGES] -o OUT
                        [--title TITLE] [--conspectus-page CONSPECTUS_PAGE]
                        [--text-lang {grc,la}] [--overrides JSON]
                        [--sigla S1,S2,…] [--ignore-self-check]
                        [pdf]
…
```

### Source — exactly one

| flag | source |
|---|---|
| *(positional)* `PDF` | a born-digital PDF, decoded by [regreek](https://github.com/romain-girardi-eng/regreek) |
| `--alto XML [XML …]` | ALTO files, one per page (any OCR engine's export) |
| `--hocr HTML [HTML …]` | hOCR files (may be multi-page) |
| `--page-xml XML [XML …]` | PAGE-XML files, one per page (kraken / eScriptorium / Transkribus) |

Zero or two of these is a `2`:

```console
$ diorthosis build -o out/
diorthosis: error: build needs exactly one source: a PDF, or --alto/--hocr/--page-xml files
```

`--pages` and `--conspectus-page` are PDF-only, and passing them with an OCR
source is refused rather than silently ignored:

```console
$ diorthosis build --alto p1.xml --pages 0 -o out/
diorthosis: error: --pages selects pages of a PDF; with --alto/--hocr/--page-xml, pass only the page files you want built
```

### The three flags that decide the outcome

On the DLL *Bellum Alexandrinum* these three are the difference between
**0 apparatus entries and a refusal** and **563 entries, 0 refused**. See
[tutorial.md](tutorial.md) for the measured before/after.

**`--pages SPEC`** — 0-based selection. `82-171`, or `1,5,9`, or both
mixed: `122-126,142-165,265-266`. Omitted, every page of the file is built,
including front matter, indices and facing translations. The spec is
normalised to ascending order before ingestion; a reversed range, an empty
value or a non-numeric element is a `2`.

**`--conspectus-page N`** — 0-based page carrying the sigla list. Omitted,
diorthosis searches the front matter itself. Without a conspectus there is no
`listWit`, so manuscript sigla cannot be resolved and the readings lose their
attributions:

```console
$ diorthosis build balex.pdf --pages 82-171 --text-lang la -o out/     # no --conspectus-page
conspectus: 5 witnesses, 0 editors declared
$ diorthosis build balex.pdf --pages 82-171 --conspectus-page 54 --text-lang la -o out/
conspectus: 24 witnesses, 103 editors declared
```

When nothing is found you get a warning on stderr, never silence:

```
[!] no conspectus siglorum found in page 25: witnesses will be missing from
the TEI and manuscript sigla cannot be attributed
```

**`--text-lang {grc,la}`** — the language of the **constituted text**, not of
the apparatus, and PDF sources only. Default `grc`. On a Latin-script
edition the default reads the main band as a *translation* and the foot band
as *notes*, which produces a page-shaped TEI with no `text` layer and no
apparatus entries at all — the self-check names it and exits `1`.

### The rest

| flag | what it does |
|---|---|
| `-o, --out DIR` | **required**; created if absent |
| `--title TITLE` | TEI `<title>` and md-ce `# ` heading; defaults to the source file name |
| `--sigla S1,S2,…` | witness sigla for editions whose PDF prints no usable conspectus; merged into whatever the front matter yields, described in the witness table as `user-supplied siglum (--sigla)` |
| `--overrides JSON` | replay a `diorthosis-overrides/1` file; every applied override is marked `resp="#human-review"` in the TEI |
| `--ignore-self-check` | write the outputs and exit `0` even when the self-check refuses them; the findings are still printed |

### What it writes

For a source whose stem is `S` (first 60 characters of the file name):

| file | what it is |
|---|---|
| `S.tei.xml` | the citable artifact: TEI P5, `<pb>` printed folios, `<anchor>` at markers, `<app>/<lem>/<rdg>`, `<note type="verbatim">` per parsed entry, `<listWit>` from the conspectus |
| `S.md` | the retrieval view: `md-ce/0.3`, checked by `diorthosis validate` |
| `S.witnesses.json` | the sigla actually used by the emitted apparatus, with base siglum, hand and hand label |

### Console output

```console
$ diorthosis build balex.pdf --pages 82-171 --conspectus-page 54 --text-lang la -o out/
conspectus: 24 witnesses, 103 editors declared
wrote out/balex.tei.xml
wrote out/balex.md
wrote out/balex.witnesses.json
coverage: 563 entries — 563 parsed, 0 refused, 0 unparsed; 563 anchored (515 attached, 48 end-only), 0 unanchored
refusals: none
```

The `coverage:`/`refusals:` pair is one measurement rendered three times —
here, in the md-ce meta line, and under every md-ce page header (SPEC I11).
Two partitions of the same `entries` total:

- **what structure is claimed** — `parsed + refused + unparsed = entries`.
  `refused` is a gate or a reviewer saying no, and always carries a reason in
  the tally; `unparsed` is the accepted grammar failing on one entry.
- **how the entry reaches the text** — `attached + end-only + unanchored =
  entries`. `attached` is a complete double-end-point link (`@from` **and**
  `@to`); `end-only` carries `@to` alone because the lemma's start could not
  be located. Counting `end-only` as plainly "anchored" is the coverage claim
  SPEC I11 forbids.

You can re-derive the split from the TEI:

```console
$ grep -o '<app [^>]*>' out/balex.tei.xml | wc -l          # 563
$ grep -o '<app [^>]*>' out/balex.tei.xml | grep -c 'from='  # 515
```

`refusals:` is `none`, or `N× reason; M× reason`, with every run of digits in
a reason replaced by `n` so one key names one refusal *class*. Build the whole
balex file — front matter, indices and all — with neither of the two flags
that make it work, and you can see both halves at once:

```console
$ diorthosis build balex.pdf --text-lang la -o all/ --ignore-self-check
conspectus: 5 witnesses, 0 editors declared
…
coverage: 720 entries — 0 parsed, 720 refused, 0 unparsed; 0 anchored (0 attached, 0 end-only), 720 unanchored
refusals: 563× line convention gate refused band: only n/n trial sides carry convention attribution (n, minimum n); 157× marker convention gate refused band: numeric-marker entry splitting found no boundary
```

The `n`s are the masking, not a measurement: the tally replaces every run of
digits so that 563 distinct measurements collapse into one class instead of
563 keys. The unmasked per-band evidence is carried on each refused entry in
memory — for file page 82 of that run it reads `only 2/16 trial sides carry
convention attribution (12.5%; minimum 60%)`. `diorthosis review` renders it
per entry in `index.html`; it is deliberately NOT written into the TEI or the
md-ce, which record what the edition says, not how this tool decided.

An OCR source adds a permanent stderr warning:

```
[!] this document contains OCR-generated blocks (marked generative) — their
text is a recognition model's output, not a decoded stream
```

---

## `diorthosis inspect`

One page, ingested and anchored exactly as `build` would, printed to stdout
as md-ce with the coverage lines on stderr. Use it to see how the layerer
classified a page before committing to a page range.

```console
$ diorthosis inspect PDF --page N [--conspectus-page M]
```

```console
$ PYTHONPATH=$PWD/src python3 -m diorthosis.cli inspect balex.pdf --page 82
conspectus: 5 witnesses, 0 editors declared
coverage: 0 entries — 0 parsed, 0 refused, 0 unparsed; 0 anchored (0 attached, 0 end-only), 0 unanchored
refusals: none
# balex.pdf
…
### heading [source=born_digital generative=false confidence=0.85 block=0]

B E L L U M

A L E X A N D R I N U M


### translation [source=born_digital generative=false confidence=0.90 block=1]

1 1Bello Alexandrino conﬂato Caesar Rhodo atque ex Syria
…
```

Two limits, both real:

- **`inspect` has no `--text-lang`.** It always uses the `grc` default, so on
  a Latin edition it shows the constituted text as `translation` and the
  apparatus as `notes`, as above — a *different* structure from the one
  `build --text-lang la` emits. Read it as a layout probe, not as a preview
  of the build.
- `--page` takes exactly one page. `inspect` always exits `0`.

---

## `diorthosis validate`

Run SPEC.md's md-ce invariants against a file. The spec, executable.

```console
$ diorthosis validate out/balex.md
OK: md-ce/0.3 invariants hold
$ echo $?
0
```

One line per violation on stdout, a count on stderr, exit `1`:

```console
$ diorthosis validate naive/balex.md
naive/balex.md: [I7] file: folio '12.1–2' appears more than once
naive/balex.md: [I7] file: folio '13.5' appears more than once
…
23 violation(s)
$ echo $?
1
```

Violations are tagged with the invariant they break (`[I5]`, `[I7]`, …) or
`[grammar]` for a line that does not match the grammar at all. The validator
checks the version it supports and no other: a `md-ce/0.2` file is rejected
(see [troubleshooting.md](troubleshooting.md#validate-rejects-an-older-md-ce-file)).

`build` runs this validator on its own output before claiming success, so a
clean `build` implies a clean `validate`.

---

## `diorthosis roundtrip`

Check that the md-ce and the TEI from the same build carry the same projected
content: same folios in the same order, same normalised text per page, same
source-slice apparatus entries with the same multiplicities, same
`translation` and `notes`.

```console
$ diorthosis roundtrip out/balex.md out/balex.tei.xml
OK: md-ce and TEI carry the same content
$ echo $?
0
```

On failure, one line per violation and exit `1`. Pages are paired **by
printed folio**, which is a real limitation on editions that print none —
see
[troubleshooting.md](troubleshooting.md#roundtrip-says-folio-is-not-unique).

---

## `diorthosis review`

Generate the human-review page: every apparatus entry face to face with the
image snippet of the printed band lines it was split from, its parse, its
status, and an editable override form.

```console
$ diorthosis review PDF [--pages SPEC] -o DIR
                        [--conspectus-page N] [--text-lang {grc,la}]
                        [--overrides JSON]
```

```console
$ diorthosis review balex.pdf --pages 82-84 --conspectus-page 54 --text-lang la -o review/
conspectus: 24 witnesses, 103 editors declared
wrote review/index.html
review: 18 entries — 18 parsed, 0 refused, 0 unanchored, 0 reviewed; 18 snippets
$ ls review/
index.html
snippets
```

`index.html` is self-contained apart from `snippets/pN-eK.png`. It carries a
filter (`all` / `refused (work queue)` / `unanchored (work queue)` /
`parsed` / `reviewed`) and a **download overrides.json** button that
assembles the corrections you ticked. Replay them with
`build --overrides` — see [cookbook.md](cookbook.md#review-an-edition-and-replay-the-corrections).

Notes:

- needs the optional extra: `pip install 'diorthosis[review]'`
  (pypdfium2 + Pillow). Without it: exit `2` and a one-line message.
- PDF sources only — the review needs the page image.
- `review` reports its own counters, and they are **not** the `build`
  coverage report: `parsed / refused / unanchored / reviewed / snippets`,
  where `unanchored` and `refused` are the work queue.
- `review` crashes on PDFs whose CropBox differs from their MediaBox — exit
  `3` or `2` depending on the installed Pillow. Reproduction, diagnosis and a
  lossless workaround are in
  [troubleshooting.md](troubleshooting.md#review-crashes-with-systemerror-tile-cannot-extend-outside-image).

---

## What the CLI never does

- It never calls an OCR engine. It ingests ALTO / hOCR / PAGE-XML from
  whichever engine you ran.
- It never edits the apparatus wording. Every parsed entry keeps its exact
  source-band substring in `note[@type="verbatim"]`, whitespace and line
  breaks included.
- It never guesses a structure past a convention gate. A band whose
  convention is not one of the four implemented families is kept verbatim and
  counted as `refused`, with the gate's own sentence as the reason.
