# Troubleshooting

Real failure modes, with the exact messages diorthosis prints and what each
one means. Everything below was reproduced on 2026-08-05 against diorthosis
0.7.0 at commit `bd01130`; the console blocks are the real output.

**First: the exit code tells you the category.**

| code | category | what to do |
|---|---|---|
| `0` | success | nothing. A run with `refusals:` in the report is still a `0` |
| `1` | **refused** — diorthosis does not certify what it produced | read the finding; it names the option that fixes it |
| `2` | your input | fix the flag, the path or the file |
| `3` | **a diorthosis defect** | not your fault; see [exit 3](#exit-3-internal-error) |

---

## `No module named 'diorthosis'`

```console
$ python3 -m diorthosis.cli build edition.pdf -o out/
…/python3: Error while finding module specification for 'diorthosis.cli' (ModuleNotFoundError: No module named 'diorthosis')
```

You are running from a working copy without installing. Point Python at
`src/`:

```console
$ cd /path/to/diorthosis
$ PYTHONPATH=$PWD/src python3 -m diorthosis.cli build edition.pdf -o out/
```

or install it (`pip install .`), which also gives you the `diorthosis`
console script.

The same error can appear *from inside a harness driver*. The drivers in
`tools/golden/` insert `src/` into `sys.path` themselves — except
`double_build.py`, which by design spawns two **separate processes** that do
not inherit that:

```console
$ python3 tools/golden/double_build.py balex.pdf --pages 82-84 …
build 1: …/python3 -m diorthosis.cli build …
…: Error while finding module specification for 'diorthosis.cli' (ModuleNotFoundError: No module named 'diorthosis')
build 1 failed with exit code 1
$ echo $?
1
```

Export `PYTHONPATH=$PWD/src`, or install the package.

---

## `self-check FAILED: this build is not certified` (exit 1)

`build` runs its own validator on its own outputs before claiming success.
Exit `1` means the files **were written** — they are on disk — but diorthosis
will not vouch for them. Two kinds of finding appear: *degeneracies* (three
of them, below) and *md-ce violations*. Every degeneracy names the option
that would have avoided it.

### `the N selected page(s) carry no decodable text at all`

```console
$ diorthosis build scan.pdf -o out/
self-check FAILED: this build is not certified
  degenerate: the 1 selected page(s) carry no decodable text at all. If this is a scanned edition, diorthosis never calls an OCR engine: run one and pass its output with --alto/--hocr/--page-xml.
…
$ echo $?
1
```

The PDF has no text layer — it is page images. diorthosis decodes glyph
streams; it does not recognise pixels, ever, by design. Run Kraken,
eScriptorium, Tesseract or Transkribus yourself and pass the export
(`--alto` / `--hocr` / `--page-xml`); see
[cookbook.md](cookbook.md#process-ocr-output-instead-of-a-pdf), and read what
the OCR path does and does not do today before you rely on it.

### `no constituted-text block across N page(s)`

```console
$ diorthosis build balex.pdf -o naive/
self-check FAILED: this build is not certified
  degenerate: no constituted-text block across 481 page(s): the layerer classified 29 heading, 956 notes, 505 translation and nothing as text. A Latin-script constituted text is read as a translation unless --text-lang la is given, and a page range covering front matter or a facing translation produces the same shape — select the edition's own pages with --pages.
  md-ce: 23 violation(s) of SPEC.md — the file 'naive/balex.md' is not a valid md-ce document:
    [I7] file: folio '12.1–2' appears more than once
    …
$ echo $?
1
```

The histogram is the diagnosis. `505 translation` and `0 text` on a Latin
edition means **the `--text-lang` default is wrong for you**; see
[wrong `--text-lang`](#wrong---text-lang) below. `29 heading, 956 notes`
across 481 pages means you also built the whole file, front matter and index
included, instead of the edition's pages.

Fix: `--pages 82-171 --text-lang la`. On this edition that turns
`0 entries` into `563 entries, 0 refused`.

### `N apparatus band(s) were detected but no entry was split`

```console
$ diorthosis build balex.pdf --pages 172-180 --conspectus-page 54 --text-lang la -o appcrit/
self-check FAILED: this build is not certified
  degenerate: 9 apparatus band(s) were detected but no entry was split from any of them: the apparatus is present in the TEI as verbatim prose only, and nothing is anchored.
the files above were written but are NOT certified; fix the command line, or pass --ignore-self-check to accept them as they are
$ echo $?
1
```

The layerer found something apparatus-shaped, and no entry splitter produced
a boundary in any of it. Two common causes:

1. **The pages are not a foot apparatus.** Above, pages 172-180 are the
   *Appendix critica*, a standalone page-wide list of orthographic variants,
   not a band keyed to a constituted text on the same page. Nothing is wrong;
   those pages simply do not belong in an apparatus build.
2. **The convention is not one diorthosis implements**, and the band is
   whole-file foreign. See [generalization.md](generalization.md).

Either way the prose is in the TEI verbatim; it is just not structure.

### `md-ce: N violation(s) of SPEC.md`

The build wrote an md-ce file its own validator rejects. Get the full list:

```console
$ diorthosis validate naive/balex.md
naive/balex.md: [I7] file: folio '12.1–2' appears more than once
…
23 violation(s)
```

`[I7]` duplicate-folio violations usually mean **the page range is wrong**
(front matter re-uses section-relative numbering) or **the PDF re-exposes the
same visible page on adjacent file pages** (tagged PDFs do this; the
Blacasset edition in [generalization.md](generalization.md) produces 72 such
violations for that reason). SPEC I7 lets `–` — no printed folio — repeat;
it does not let a real folio repeat, because that would make
`(folio, block)` addressing ambiguous.

### Accepting an uncertified build anyway

```console
$ diorthosis build balex.pdf -o naive2/ --ignore-self-check
…
[!] --ignore-self-check: exiting 0 with an uncertified artifact
$ echo $?
0
```

The findings are still printed. Use it when you know why the output looks
like that — for instance `tools/golden/generalize.py` passes it, because a
build diorthosis refuses to certify is a *row* of the generalization table,
not a missing row.

---

## The build succeeded but everything is `refused`

This is not an error. Exit code `0`, and the reason is named:

```console
$ diorthosis build 78-SBLGNT-Philemon.pdf -o phm/
coverage: 14 entries — 0 parsed, 14 refused, 0 unparsed; 0 anchored (0 attached, 0 end-only), 14 unanchored
refusals: 14× paragraph convention gate refused band: foreign separator '•' is not consumed
```

Every refused entry is kept **verbatim** in both outputs — as
`<note type="apparatus">` in the TEI, as a plain line in the md-ce. Nothing
is dropped. What you do not get is `<lem>/<rdg>` structure, because
diorthosis could not derive it without guessing.

### Reading the tally

`refusals:` is `N× reason; M× reason`, sorted by descending count. Every run
of digits inside a reason is replaced by `n`, so one key names one refusal
*class* rather than one measured value — which is why you see things like
`n numeric markers resolved` (the real measurement was `0`) and
`left n of tokens unconsumed (maximum n)`.

### What each gate phrasing means

Each reason is prefixed by the grammar that refused: `marker`,
`verse-referenced`, `line-referenced` or `paragraph`.

**Any grammar**

| phrasing | meaning |
|---|---|
| `foreign separator '\|\|' is not consumed` / `'∥'` / `'•'` / `'\|'` | the band contains a separator this convention does not define. Consuming it would mean guessing what it joins |
| `n unmatched ']' lemma separator(s) are not consumed` | more lemma closers than the split accounted for — an unmodelled nesting |
| `n orphan ']' closer(s) beyond the n split boundaries signal an unconsumed foreign structure` | same, tolerated up to a fifth of entries, then refused |
| `trial parse left n of tokens unconsumed (maximum n)` | the trial parse could not account for enough of the band's own words |

**Marker grammar (numeric superscripts — the *Sources Chrétiennes* family)**

| phrasing | meaning |
|---|---|
| `numeric-marker entry splitting found no boundary` | no numbered entry openings at all. This band is not marker-conventional |
| `n numeric markers resolved against the text layer` | markers were found but **none** resolves to a marker in the page's own text. An apparatus points into its text; this one does not |
| `no registry is available for a trial parse` | no conspectus and no `--sigla`, so no trial parse can be judged |
| `only n/m marker entries parsed in trial (minimum 50%)` | fewer than half the entries parse |
| `no witness, editor or source is named on any of the n reading(s) proposed by n/m trial-parsed entries — a numbered prose band, not a variant apparatus` | **the fabrication gate.** An apparatus criticus records *who reads what*. Numbered editorial prose — footnotes, fontes paragraphs, translators' notes — copies the printed shape but never the sigla. This is the gate that closed the leak wave A was built for: a numbered English editorial footnote had been emitted as a `<lem>/<rdg>` variant, in schema-valid TEI, at exit `0`. It is a **whole-band** floor on purpose: single-witness editions legitimately print bare readings, and refusing them entry by entry cost the reference edition 6 points of parse rate |

**Verse-referenced grammar (biblical editions)**

| phrasing | meaning |
|---|---|
| `verse-reference splitting found no entry` | no `chapter:verse` openings. Single-chapter books print bare verse numbers and land here — this is why SBLGNT Philemon, 2 John, 3 John and Jude refuse |
| `trial parse left n of tokens unconsumed and only n% of entries parsed` | both conditions together; one honestly-refused giant entry must not condemn a band whose others parse |
| `only n/m trial sides carry edition sigla (n%; minimum 90%)` | too few readings name a cited edition |

**Line-referenced grammar (DLL / reledmac)**

| phrasing | meaning |
|---|---|
| `only n entry was split` | the `∥` / spaced `\|` signature yields fewer than two entries |
| `only n/m trial sides carry convention attribution (n%; minimum 60%)` | too few sides name a witness, editor or qualifier — the threshold that keeps bare *fontes* prose from looking like variants |

**Paragraph reledmac (LombardPress / scholastic, double apparatus)**

| phrasing | meaning |
|---|---|
| `only n numbered lemma boundary/boundaries found` | fewer than two numbered `lemma]` boundaries |
| `a short non-locus preamble signals a tier heading, not a fontes tier` | the band opens with a heading, so the tier structure is not the one this grammar models |
| `trial parse left n nonempty reading segment(s) without a witness or operator` | a proposed reading names nobody and does nothing |

**Human review**

| phrasing | meaning |
|---|---|
| `human review forced the entry verbatim` | a reviewer's `action: "verbatim"` override. Counted as a refusal, with its own reason, so a human decision is visible in the coverage report |

### The gates are not tunable, and that is the point

There is no flag to relax a gate. A gate that can be talked out of a refusal
is not a gate. If a real convention is being refused, the fix is a grammar
with its own positive and negative corpus certification — see the
"Precise TODO" in [generalization.md](generalization.md).

---

## Wrong `--text-lang`

Symptom: constituted text shows up as `translation`, the apparatus as
`notes`, and the coverage line says `0 entries`.

```console
$ diorthosis inspect balex.pdf --page 82
…
### translation [source=born_digital generative=false confidence=0.90 block=1]

1 1Bello Alexandrino conﬂato Caesar Rhodo atque ex Syria
…
### notes [source=born_digital generative=false confidence=0.90 block=2]

5 cotidie operibus USTV | cotidie M (cf. BC 3.112.9) | nouis cotidie
```

`--text-lang` declares the language of the **constituted text**, not of the
apparatus. The default is `grc`; on a Latin-script edition the default reads
the main band as a translation. Pass `--text-lang la`.

Note that **`inspect` has no `--text-lang` flag** — it always uses the `grc`
default. On a Latin edition it will always show the layout above, even when
`build --text-lang la` gets it right. Judge `inspect` as a layout probe, not
as a preview of the build.

Only `grc` and `la` ship. Italian, Occitan, Sanskrit IAST and Devanagari were
measured through `--text-lang la` in
[generalization.md](generalization.md); that limitation is part of that
result.

---

## `no conspectus siglorum found`

```
[!] no conspectus siglorum found in page 25: witnesses will be missing from
the TEI and manuscript sigla cannot be attributed
```

or, without `--conspectus-page`, `… found in the front matter: …`.

Warning, not an error — the build continues, with no `<listWit>` and no
resolvable manuscript sigla. Three causes:

1. **You did not say where it is.** Find it (the probe in
   [tutorial.md](tutorial.md#3-find-the-editions-pages-and-its-conspectus)),
   then pass `--conspectus-page N`, 0-based. On balex this is the difference
   between `conspectus: 5 witnesses, 0 editors declared` and
   `conspectus: 24 witnesses, 103 editors declared`.
2. **The sigla are declared in running prose**, not as a list — common in
   introductions (`E8 = Erfurt, Universitäts- und Forschungsbibliothek …`).
   The bootstrap does not recognise these. Both PDF pages 25 and 26 of the
   Segrave *Insolubilia* yield zero witnesses for that reason.
3. **The edition prints no conspectus at all.**

For 2 and 3, transcribe the sigla and declare them:
`--sigla E4,E8,O`. That is declared input, not parser tuning; the witness
table records them as `user-supplied siglum (--sigla)`. Recipe with the
measured before/after:
[cookbook.md](cookbook.md#supply-sigla-when-the-edition-has-no-usable-conspectus).

---

## `validate` rejects an older md-ce file

The file below is a build kept from diorthosis 0.6; if you have none, the same
two violations come from any file whose meta comment is `md-ce/0.2`.

```console
$ diorthosis validate old-build/Bellum_Alexandrinum.md
old-build/Bellum_Alexandrinum.md: [grammar] line 3: meta comment does not match the grammar
old-build/Bellum_Alexandrinum.md: [grammar] file: no md-ce meta comment found
2 violation(s)
```

The file is `md-ce/0.2`; this validator checks `0.3` and, by design, rejects
the version it does not check. 0.3 replaced the old `anchored: a/b` meta
field with the single `coverage:` report (SPEC I11). Rebuild the edition with
this diorthosis.

A file that is not md-ce at all gives — here an ordinary Markdown note whose
first line happens to be a `# ` title, so only the meta comment is missing:

```console
$ diorthosis validate notes.md
notes.md: [grammar] file: no md-ce meta comment found
1 violation(s)
```

And a hand-written fragment — an excerpt from documentation, say — fails on
every structural line:

```console
$ diorthosis validate sample.md
sample.md: [grammar] line 1: first line is not a '# title'
sample.md: [grammar] line 1: '## ' line is not a valid page header
sample.md: [I5] line 3: section header not parseable: '### text [source=born_digital generative=false confidence=0.90]'
sample.md: [I5] line 6: section header not parseable: '### apparatus [source=born_digital generative=false confidence=0.90]'
sample.md: [grammar] file: no md-ce meta comment found
5 violation(s)
```

(`[I5]` here: the section header is missing `block=`, which 0.3 requires.)
Only real build output is a md-ce document. Do not paste examples into a file
and expect them to validate — this exact fragment was in this project's own
README until 2026-08-05.

---

## `roundtrip` says `folio is not unique`

```console
$ diorthosis roundtrip mt/61-SBLGNT-Matthew.md mt/61-SBLGNT-Matthew.tei.xml
mt/…md <> mt/…tei.xml: TEI translation for folio –: cannot assign it to a page (folio is not unique)
… (repeated)
mt/…md <> mt/…tei.xml: page – (file index 27): translation differs (md-ce='13:44–58'; TEI='')
mt/…md <> mt/…tei.xml: page – (file index 33): text differs (md-ce='Σαδδουκαίων. 12 τότε συνῆκαν ὅτι οὐκ εἶπεν προσέχειν ἀπὸ τῆς ζύμης ⸂τῶν ἄρτων⸃ ἀλλ ὰ ἀπὸ τῆς διδαχῆς τῶν Φαρισαίων καὶ …'; TEI='Σαδδουκαίων. 12 τότε συνῆκαν ὅτι οὐκ εἶπεν προσέχειν ἀπὸ τῆς ζύμης ⸂τῶν ἄρτων⸃ ἀλλ ὰ ἀπὸ τῆς διδαχῆς τῶν Φαρισαίων καὶ …')
76 violation(s)
$ echo $?
1
```

(The `mt/…md` abbreviations are this page's; every other character is the
tool's, including the `…` with which it truncates its own quotations.)

Of those 76, 33 are the `folio is not unique` line (counted by piping the
same command through `grep -c "folio is not unique"`).

Note that the same build **passes `validate` and exits 0**:

```console
$ diorthosis validate mt/61-SBLGNT-Matthew.md
OK: md-ce/0.3 invariants hold
```

This is a real limitation, not a corrupted build. `roundtrip` pairs TEI
`translation` and `notes` blocks to md-ce pages **by printed folio**. This
edition prints no folio that diorthosis extracts, so every page's folio is
`–`; md-ce I7 explicitly allows `–` to repeat (it is the *absence* of a
folio, not a folio), and the pairing then has nothing to key on. Every
`translation differs (…; TEI='')` line is that same failure showing up once
per page.

The `text differs` lines have a separate, small cause: the two projections
differ by whitespace. On file index 33 the difference is exactly one inserted
space in 1,833 characters. Diagnose one yourself:

```python
import difflib
from diorthosis import roundtrip as rt

mds, _ = rt._parse_markdown(open("mt/61-SBLGNT-Matthew.md", encoding="utf-8").read())
teis, _ = rt._parse_tei("mt/61-SBLGNT-Matthew.tei.xml")
p = {q.index: q for q in mds}[33]
q = {t.index: t for t in teis}[33]
a, b = rt._markdown_text(p), rt._tei_text(q)
print("equal:", a == b, "len", len(a), len(b))
for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
    if tag != "equal":
        print(tag, repr(a[i1:i2])[:100], "->", repr(b[j1:j2])[:100])
```

```console
equal: False len 1833 1834
insert '' -> ' '
```

(Those are private helpers; they may move between releases.)

What to do meanwhile: on editions that print folios, `roundtrip` works and is
worth running — balex passes. On editions that print none, treat the TEI as
the artifact, use `validate` for the md-ce, and check the apparatus with a
harness that compares against ground truth
([cookbook.md](cookbook.md#run-the-golden-harnesses-on-your-own-edition))
rather than against the sibling view.

---

## `review needs the optional extra`

```console
$ diorthosis review balex.pdf --pages 82 -o review/
review needs the optional extra: pip install 'diorthosis[review]'
$ echo $?
2
```

The review UI rasterises page snippets, which needs `pypdfium2` and
`Pillow`. They are not core dependencies — you can build, validate and
roundtrip without them.

```console
$ pip install 'diorthosis[review]'
```

(PyMuPDF is deliberately avoided: pypdfium2 is BSD/Apache, PyMuPDF is AGPL.)

---

## `review` crashes with `SystemError: tile cannot extend outside image`

The file below is Walter Segrave's *Insolubles* (Open Book Publishers 2024,
CC BY-NC 4.0), fetched and checksummed in
[cookbook.md](cookbook.md#the-edition-this-recipe-was-written-for); nothing
here is specific to it, only to its CropBox.

With Pillow 12.1.1:

```console
$ diorthosis review insolubles.pdf --pages 40-42 --text-lang la -o review/
conspectus: 0 witnesses, 0 editors declared
internal error: SystemError: tile cannot extend outside image
this is a diorthosis defect, not an input problem; please report it with the command line that produced it
$ echo $?
3
```

**The same bug wears several faces.** The exception Pillow raises for an
out-of-bounds crop depends on its version and on which coordinate goes out
of range first, so the same PDF and the same page can also give you a `2` and
a message that blames your input, which is wrong — it is still a diorthosis
defect. All of these were reproduced on the same file:

```console
$ diorthosis review insolubles.pdf --pages 41 --text-lang la -o review/   # Pillow 12.1.1
error: Coordinate 'lower' is less than 'upper'
$ echo $?
2
```

Page by page, on Pillow 12.1.1:

```console
$ for p in 40 41 42; do
    out=$(diorthosis review insolubles.pdf --pages $p --text-lang la -o rv-$p 2>&1)
    echo "page $p: exit=$? $(echo "$out" | grep -E '^(error|internal error)')"
  done
page 40: exit=3 internal error: SystemError: tile cannot extend outside image
page 41: exit=2 error: Coordinate 'lower' is less than 'upper'
page 42: exit=2 error: Coordinate 'lower' is less than 'upper'
```

Under Pillow 12.3.0 the same loop reported page 40 as
`exit=2 error: cannot write empty image` — a third face of one defect, and the
reason none of the three should be read as a verdict on your input.

If `review` fails on a PDF while `build` succeeds, suspect this regardless of
which of the three messages you got.

**Cause.** The snippet cropper measures apparatus boxes in the coordinate
space pdfminer reports, and crops them out of a bitmap pdfium rendered. When
the PDF's **CropBox differs from its MediaBox**, those two spaces are not the
same and the crop falls outside the image. On this file:

```console
$ python3 -c "
import pypdfium2
from pdfminer.high_level import extract_pages
doc = pypdfium2.PdfDocument('insolubles.pdf')
p = doc[40]
print('pdfium size  ', p.get_size())
print('mediabox     ', p.get_mediabox())
print('cropbox      ', p.get_cropbox())
print('pdfminer bbox', next(iter(extract_pages('insolubles.pdf', page_numbers=[40]))).bbox)"
pdfium size   (442.0799865722656, 663.1199951171875)
mediabox      (0.0, 0.0, 612.0, 792.0)
cropbox       (84.95999908447266, 64.44000244140625, 527.0399780273438, 727.5599975585938)
pdfminer bbox (0, 0, 612.0, 792.0)
```

612×792 against 442×663 — that is the whole bug. `build`, `validate` and
`roundtrip` are unaffected; only `review` rasterises.

**Workaround: remove the CropBox.** pdfium then renders the MediaBox, which
is the space the boxes are already in. This is lossless for the text stream:

`pikepdf` is not a diorthosis dependency — install it just for this repair:

```console
$ pip install pikepdf
```

```console
$ python3 -c "
import pikepdf
with pikepdf.open('insolubles.pdf') as pdf:
    n = 0
    for page in pdf.pages:
        if '/CropBox' in page:
            del page['/CropBox']; n += 1
    pdf.save('insolubles-nocrop.pdf')
print('removed CropBox from', n, 'pages')"
removed CropBox from 160 pages

$ diorthosis review insolubles-nocrop.pdf --pages 40-42 --conspectus-page 25 \
      --text-lang la -o review/
wrote review/index.html
review: 19 entries — 0 parsed, 19 refused, 0 unanchored, 0 reviewed; 19 snippets
$ echo $?
0
```

The snippets are correct crops of the printed band, not blank or shifted
rectangles.

**Verify the workaround changed nothing.** Build both files over the same
pages and compare the extracted apparatus:

```console
$ diorthosis build insolubles.pdf         --pages 40-42 --text-lang la -o orig/
$ diorthosis build insolubles-nocrop.pdf  --pages 40-42 --text-lang la -o nocrop/
$ python3 -c "
import re
def apps(p):
    t = open(p, encoding='utf-8').read()
    return ''.join(re.findall(r'^### apparatus[^\n]*\n\n(.*?)(?=\n### |\n## |\Z)', t, re.S|re.M))
a = apps('orig/insolubles.md'); b = apps('nocrop/insolubles-nocrop.md')
print('chars', len(a), len(b), '| identical:', a == b)"
chars 1221 1221 | identical: True
```

**Do NOT use ghostscript for this.** `gs -dUseCropBox` also makes `review`
work, and it silently rewrites the content stream. On the same three pages it
changes the extracted apparatus:

```console
$ gs -o insolubles-gs.pdf -sDEVICE=pdfwrite -dUseCropBox -dFirstPage=41 -dLastPage=43 insolubles.pdf
$ diorthosis build insolubles-gs.pdf --pages 0-2 --text-lang la -o gs/
$ # same comparison as above:
chars 1221 1096 | identical: False
```

The diff on that band is `-30 album] albus E4 (cid:105)  (cid:105) …` versus
`+30 album] albus E4` — here ghostscript happened to drop unmapped-glyph
noise, which looks like an improvement and is exactly the problem: after a
re-encode, your input is no longer the publisher's own glyph stream, and the
provenance contract ("a deterministic decoding of the file's own glyph
stream") no longer describes what you built. Strip the CropBox; do not
re-encode.

---

## `--pages` and other input errors (exit 2)

```console
$ diorthosis build balex.pdf --pages 171-82 -o out/
error: --pages range '171-82' is reversed

$ diorthosis build balex.pdf --pages "" -o out/
error: --pages given but empty; omit the flag to process all pages

$ diorthosis build balex.pdf --pages 82-84,xii -o out/
error: --pages element 'xii' is not a 0-based page number or A-B range

$ diorthosis build balex.pdf --pages 9000 -o out/
error: no pages ingested: the requested pages do not exist in this document

$ diorthosis build nope.pdf -o out/
error: file not found: nope.pdf
```

Remember: **0-based**. `--pages 1` is the *second* sheet of the file, and
most PDF viewers (and `pdf2txt.py --page-numbers`) count from 1.

Source-selection errors:

```console
$ diorthosis build -o out/
diorthosis: error: build needs exactly one source: a PDF, or --alto/--hocr/--page-xml files

$ diorthosis build balex.pdf --alto p1.xml -o out/
diorthosis: error: build needs exactly one source: a PDF, or --alto/--hocr/--page-xml files

$ diorthosis build --alto p1.xml --pages 0 -o out/
diorthosis: error: --pages selects pages of a PDF; with --alto/--hocr/--page-xml, pass only the page files you want built

$ diorthosis build --alto p1.xml --conspectus-page 0 -o out/
diorthosis: error: --conspectus-page points into a PDF; OCR page files carry no front matter to search
```

The last two are refusals of *silently ignored* flags. A flag that does
nothing is worse than a flag that errors.

---

## Overrides errors

**Unversioned file** (written before `diorthosis-overrides/1`):

```console
$ diorthosis build … --overrides old.json -o out/
error: old.json: not a versioned overrides file (no 'format' key). Files written before diorthosis-overrides/1 bind corrections by position alone, so replaying them can attach a human-reviewed parse to a different entry. Re-run 'diorthosis review' on this build and re-export.
$ echo $?
2
```

**A format this diorthosis does not read:**

```console
$ diorthosis build … --overrides newer.json -o out/
error: newer.json: unknown overrides format 'diorthosis-overrides/2'; this diorthosis reads diorthosis-overrides/1
```

**Drifted binding** — the key still finds an entry, but not *that* entry.
The whole replay refuses, itemised, and the document is left untouched:

```console
$ diorthosis build … --overrides drifted.json -o out/
error: 1 override(s) no longer match the entry they were made against; refusing to replay ANY of them.
Applying a drifted correction would attach a human-reviewed parse (resp="#human-review") to a different apparatus entry.
  p83-e0: bound to 000000000000, entry is now 2a5df7443e18
      made against: 16 expectans MUSTV (cf. BC 3.43.3 et u. Damon 2015b 116 n.32) | spectans Vascosanus (cf. BC 3.85.2)
      now reads:     16 expectans MUSTV (cf. BC 3.43.3 et u. Damon 2015b 116 n.32) | spectans Vascosanus (cf. BC 3.85.2)
Re-run 'diorthosis review' on this build, re-check these entries and re-export the corrections.
$ echo $?
2
```

Fix: re-run `diorthosis review` on the current build, re-check those entries,
re-export. Never edit `source_sha` by hand — it exists precisely to stop a
correction from being detached from what it was made against.

**Stale key** — matches no entry at all. Lesser problem (you lose a
correction, you do not gain a false one), so it warns and continues:

```console
$ diorthosis build … --overrides stale.json -o out/
[!] 1 override key(s) matched no entry (stale file?): p99-e0
overrides: 0 parses replaced, 0 forced verbatim
…
$ echo $?
0
```

Other validation refusals from the loader, all exit `2`: a record without a
12-character `source_sha`, an `action` that is neither `parse` nor
`verbatim`, an `action: "parse"` with no `lemma`.

---

## `refused: …` with no other message (exit 1)

```
refused: <message about ⟦ or ⟧>
```

The source text contains U+27E6 `⟦` or U+27E7 `⟧`, which md-ce reserves for
markers (SPEC I4). Emitting the file would make it ambiguous — a consumer
could not tell a marker from edition text — so diorthosis refuses to emit
rather than produce a file that lies. This is not an input error: the source
is legitimate, the format simply declines to represent it.

---

## exit 3: `internal error`

```
internal error: <ExceptionType>: <message>
this is a diorthosis defect, not an input problem; please report it with the
command line that produced it
```

Exit `3` means a diorthosis bug, not a bad input. You will never see a raw
traceback from the CLI. Please report it with the exact command line.

The one reproducible instance documented today is the
[`review` CropBox crash](#review-crashes-with-systemerror-tile-cannot-extend-outside-image)
— and note that the *same* defect exits `2` under a different Pillow version.
So exit `2` is not a guarantee that the fault is yours: if the message names
image coordinates, a tile, or an empty image, it is this bug.

---

## Nothing above matches

- Re-run with a single page (`--pages N`) and look at
  `diorthosis inspect PDF --page N` to see how the page was layered.
- Check that the printed folios in the md-ce match the printed folios in the
  book. If they do not, your `--pages` selection is off.
- Compare against [generalization.md](generalization.md): nine
  reviewer-supplied editions, with page selections, sigla, layer censuses,
  wall times, and what each one refused.
- The normative behaviour of the Markdown view is [../SPEC.md](../SPEC.md);
  every invariant there is checkable with `diorthosis validate`.
