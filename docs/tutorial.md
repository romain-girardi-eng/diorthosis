# Your first edition, end to end

You will take a published critical edition — a real PDF, downloaded from its
publisher — and turn it into a TEI P5 file with an anchored apparatus
criticus and an AI-ready Markdown view, then check both mechanically.

Every command below was executed on 2026-08-05 against diorthosis 0.7.0 at
commit `bd01130`, on macOS with CPython 3.13. The console blocks are the real
output. Where a listing is long it is cut, and the cut is marked.

Budget: about ten minutes, most of it downloading.

**The edition.** The *Bellum Alexandrinum*, edited by Cynthia Damon and
collaborators for the [Library of Digital Latin Texts](https://digitallatin.org/),
CC BY-SA 4.0. Its born-digital PDF is in the project's own public repository,
so you can fetch the exact bytes this tutorial used. Latin, ninety PDF pages
of edition ending at printed page 89, a line-referenced reledmac apparatus —
one of the four conventions diorthosis implements.

---

## 1. Get the tool

```console
$ python3 -m venv .venv
$ . .venv/bin/activate
$ pip install diorthosis            # once published to PyPI — 404 today
```

Until the first PyPI release lands, install from a checkout. This is the path
the tutorial used:

```console
$ git clone https://github.com/romain-girardi-eng/diorthosis
$ python3 -m venv .venv
$ . .venv/bin/activate
$ pip install ./diorthosis
$ diorthosis --help
usage: diorthosis [-h] {build,inspect,validate,roundtrip,review} ...

Compile published critical editions into TEI P5 + AI-ready Markdown

positional arguments:
…
```

The tutorial ran exactly this against the public repository, whose `HEAD` is
`bd01130`. Everything below assumes the virtualenv is active, so `diorthosis`
is on your PATH.

Python 3.10 or newer. Two dependencies, both installed for you: `regreek`
(character- and page-level decoding) and `pdfminer.six`.

## 2. Get the edition

```console
$ mkdir first-edition && cd first-edition
$ curl -fsSL -o balex.pdf \
    https://raw.githubusercontent.com/Library-of-Digital-Latin-Texts/balex/0e6ee82976a6ffeff41b5515594826719bfdfb0f/ldlt-balex.pdf
$ shasum -a 256 balex.pdf
6702fceb54ec347406c0d857ea508e2ff05e2e4dac9a5111df3f6aa2f96c1325  balex.pdf
```

The URL is pinned to a commit, so that checksum is what you should get. If it
differs, you have a different file and your numbers will differ from mine.

## 3. Find the edition's pages, and its conspectus

This is the step nobody can do for you, and the step that decides everything
that follows. You must tell diorthosis **which pages carry the edition** and
**where the sigla are declared**. Both are 0-based PDF page indices — the
first sheet of the file is `0`, not `1`.

A 481-page PDF holds a preface, a bibliography, the edition, an appendix and
an index. Only some of it is the edition. Save this probe — it prints the
first lines of each page, which is where running heads and section openings
live:

```python
# find_pages.py
import re
import sys
from pdfminer.high_level import extract_text          # already installed

HEADINGS = re.compile(
    r"sigla|conspectus|manuscript|manoscritt|témoins|zeugen|codices|"
    r"bibliograph|abbreviation", re.I)

pdf, first, last = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
for i in range(first, last + 1):                      # 0-based, like --pages
    text = extract_text(pdf, page_numbers=[i]) or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    head = " / ".join(lines[:4])[:100]
    flag = "  <== sigla?" if HEADINGS.search(" ".join(lines[:6])) else ""
    print(f"{i:4d}  {head}{flag}")
```

Sweep the front matter:

```console
$ python3 find_pages.py balex.pdf 50 58
  50  Acknowledgements / xliii / Acknowledgements / As we said at the outset, this edition rests on the wo
  51  xliv / Preface / toria Burmeister, Sean Carpenter, Greg Callaghan, Brian / Credo, Maxwell Dietrich,
  52  Acknowledgements / xlv / Greg Crane, Uwe Springmann, and Katie Rawson); Amy / Lewis, who helped edit
  53  xlvi / Preface / reading this edition online, has been instrumental in all / aspects of this project
  54  B I B L I O G R A P H Y / Manuscripts / [ω] Common source of / [μ] Common source of M and U  <== sigla?
  55  xlviii / Bibliography / [Mc] Corrections by the original scribe, who usually / recovers the reading   <== sigla?
  56  Manuscripts / xlix / [Sc] Corrections made by the original scribe or a close / contemporary.  <== sigla?
  57  l / Bibliography / [ϛ] A reading found in one or more later manuscripts. / Early Editions  <== sigla?
  58  Modern Editions / li / Modern Editions / [Andrieu] J. Andrieu, ed. Pseudo-César, Guerre d’Alexandrie
```

Page **54** opens the sigla list: `[ω]`, `[μ]`, `[M]`. That is
`--conspectus-page 54`. The list runs on for several pages; you pass the page
where it *starts* and diorthosis reads forward from there.

Now the edition itself:

```console
$ python3 find_pages.py balex.pdf 78 84
  78  40.2 / 40.2 / 42.2 / 42.3
  79  lxxii / Conspectus Editionum / 60.5 / 61.4  <== sigla?
  80  78.2 / quod ⟨regnum⟩ / quod / lxxiii
  81  This file presents data in the public beta version (0.0.1) of this edition.
  82  B E L L U M / A L E X A N D R I N U M / 1 1Bello Alexandrino conﬂato Caesar Rhodo atque ex Syria / C
  83  2 / Bellum Alexandrinum / 15 / pauimentis. 4Caesar maxime studebat ut, quam angustis-
  84  Bellum Alexandrinum / 3 / quibus domini locupletiores uictum cotidianum stipendi- / umque praebebant
```

```console
$ python3 find_pages.py balex.pdf 168 174
 168  Bellum Alexandrinum / 87 / 3Insequitur has acies hostium. Et clamore / primuntur.
 169  88 / Bellum Alexandrinum / 15 / 20
 170  89 / 78 1Ita per Gallograeciam Bithyniamque in Asiam iter / facit omniumque earum prouinciarum de co
 171  This file presents data in the public beta version (0.0.1) of this edition.
 172  A P P E N D I X C R I T I C A / 1.1 Rhodo] et ordo S / 1.1 Creta] certa S / 1.2 operibus om. M
 173  92 / Appendix critica / 2.1 oppidum] -do Uac / 2.2 urbe] hurbe S
 174  93 / 3.3 Caesarem] ac cessarem S / 3.4 non] on Sac / 3.4 ex om. V
```

Note page 79: the flag also fires on the *Conspectus Editionum*, a list of
printed editions, not of manuscripts. The flag is a hint, not an answer —
look at the lines.

The title drops at **82**; the running head *Bellum Alexandrinum* runs to
**170**; **172** starts a different thing, the *Appendix critica*. So the
edition is `--pages 82-171`.

Three practical notes:

- **The probe reads what pdfminer can decode.** On a Latin edition that is
  the text. On a Greek edition set in a pre-Unicode font it will be garbage —
  that decoding is regreek's job, not pdfminer's. Use
  `diorthosis inspect PDF --page N` instead, which routes through the real
  ingest. The probe *does* work on Unicode-Greek PDFs: run on the Herodian
  thesis edition of [generalization.md](generalization.md) — a reviewer-supplied
  file this repository cannot redistribute — the same script prints
  `376  SIGLA / A Monacensis Graecus 157, saec. XIV / B Vindobonensis Gr. 59, saec. XV …`,
  then `377  LIVRE I`, then `378  ΗΡΩΔΙΑΝΟΥ ΤΗΣ ΜΕΤΑ ΜΑΡΚΟΝ ΒΑΣΙΛΕΙΑΣ …`,
  then `379  HISTOIRE DE L’EMPIRE APRÈS LE RÈGNE DE MARC AURÈLE …` — sigla
  page, book opening, Greek, facing French, in four lines.
- **Facing translations.** Many editions alternate source and translation
  page by page. Select only the source pages:
  `--pages 378,380,382,…` — the spec takes comma-separated pages and ranges
  in any mix.
- **Being a page or two generous is harmless.** `82-171` includes the
  publisher's colophon page 171; it lands in the `notes` layer and changes no
  apparatus count.

## 4. The build — first the way that fails

Run the obvious command, the one with no flags:

```console
$ diorthosis build balex.pdf -o naive/
self-check FAILED: this build is not certified
  degenerate: no constituted-text block across 481 page(s): the layerer classified 29 heading, 956 notes, 505 translation and nothing as text. A Latin-script constituted text is read as a translation unless --text-lang la is given, and a page range covering front matter or a facing translation produces the same shape — select the edition's own pages with --pages.
  md-ce: 23 violation(s) of SPEC.md — the file 'naive/balex.md' is not a valid md-ce document:
    [I7] file: folio '12.1–2' appears more than once
    [I7] file: folio '13.5' appears more than once
    [I7] file: folio '17.1–3' appears more than once
    [I7] file: folio '2.5' appears more than once
    [I7] file: folio '22.1–2' appears more than once
    … 18 more; run 'diorthosis validate naive/balex.md' for the full list
the files above were written but are NOT certified; fix the command line, or pass --ignore-self-check to accept them as they are
conspectus: 5 witnesses, 0 editors declared
wrote naive/balex.tei.xml
wrote naive/balex.md
wrote naive/balex.witnesses.json
coverage: 0 entries — 0 parsed, 0 refused, 0 unparsed; 0 anchored (0 attached, 0 end-only), 0 unanchored
refusals: none
$ echo $?
1
```

(Findings go to stderr and the progress lines to stdout. Redirecting one of
them, as the capture above does, changes the interleaving; the content is
the same.)

Read that carefully, because it is the whole design in one screen. The build
*succeeded mechanically*: it wrote three schema-shaped files. It produced
**zero** apparatus entries and **zero** constituted text, and its own md-ce
validator rejects its own Markdown. Before wave A of 1.0 this exact command
— the one printed in this project's own README — exited `0`. It now exits
`1`, and it names the option that would have avoided each finding.

## 5. The build that works

```console
$ diorthosis build balex.pdf --pages 82-171 --conspectus-page 54 --text-lang la -o out/
conspectus: 24 witnesses, 103 editors declared
wrote out/balex.tei.xml
wrote out/balex.md
wrote out/balex.witnesses.json
coverage: 563 entries — 563 parsed, 0 refused, 0 unparsed; 563 anchored (515 attached, 48 end-only), 0 unanchored
refusals: none
$ echo $?
0
```

Same PDF, same tool, three flags: **0 → 563 entries**. Note the conspectus
line too: 5 witnesses and 0 editors when diorthosis had to guess, 24
witnesses and 103 editors when told where to look.

`--text-lang la` is the one people miss. It declares the language of the
**constituted text**, not of the apparatus. Default is `grc`; on a
Latin-script edition the default reads the main band as a translation, which
is exactly the 505-translation-blocks shape you saw above.

## 6. Read the coverage line

```
coverage: 563 entries — 563 parsed, 0 refused, 0 unparsed; 563 anchored (515 attached, 48 end-only), 0 unanchored
refusals: none
```

563 apparatus entries were split out of the printed bands, and the same
number is partitioned twice.

**What structure is claimed** — `parsed + refused + unparsed = entries`.

- `parsed` — emitted as `<app>/<lem>/<rdg>` with attributions.
- `refused` — a convention gate, or a human reviewer, said no. Kept verbatim.
  Always carries a reason in the `refusals:` tally.
- `unparsed` — the accepted grammar simply failed on this entry. Kept
  verbatim.

**How the entry reaches the text** — `attached + end-only + unanchored =
entries`.

- `attached` — a complete double-end-point link: the TEI `<app>` carries both
  `@from` and `@to`, so the lemma's span in the constituted text is delimited
  at both ends.
- `end-only` — `@to` alone. The apparatus marker gives the end; the lemma's
  *start* could not be located confidently, so no start anchor is minted.
- `unanchored` — no link into the text at all.

The 48 end-only entries are the reason this line exists. Until wave A of 1.0,
an `<app>` carrying only its end anchor counted as "anchored", so this
edition was reported at 100 % anchoring — a true sentence about a weaker
claim than the words suggested. `515 attached, 48 end-only` is the same
graph, honestly labelled. You can re-derive it from the emitted file:

```console
$ grep -o '<app [^>]*>' out/balex.tei.xml | wc -l
     563
$ grep -o '<app [^>]*>' out/balex.tei.xml | grep -c 'from='
515
```

A start anchor is minted only when the lemma can be located confidently in
the text immediately before the end anchor. Here is one of the 48 where it
cannot be. The printed marker `9` fell inside the hyphenated word
`foram-` / `ina`, so the characters preceding the end anchor are
`…per foram-\n\nin`, not the preposition `in` this entry is about:

```xml
<app n="9" to="#a-p82-e3">
  <lem wit="#wit-M #wit-U #wit-S #wit-T #wit-V">in</lem>
  <rdg source="#ed-Schneider">[in]</rdg>
  <note type="comment">coll. Hirt. 8.27.4</note>
  <note type="verbatim">9 in

MUSTV | [in] Schneider coll. Hirt. 8.27.4</note>
</app>
```

The same report appears in the md-ce meta line and under every md-ce page
header (SPEC I11) — one invocation can never announce two scores. From
`head -8 out/balex.md`, after the `# balex.pdf` title line:

```markdown
<!-- md-ce/0.3 · diorthosis 0.7.0 · ingest: borndigital · pages: 82-171 · coverage: 563 entries — 563 parsed, 0 refused, 0 unparsed; 563 anchored (515 attached, 48 end-only), 0 unanchored · refusals: none · generative-blocks: 0 · escaped-lines: 0 · tei: balex.tei.xml -->

## page – (file index 82) [markers=0 entries=7 unresolved=0]
<!-- md-ce page: 7 entries — 7 parsed, 0 refused, 0 unparsed; 7 anchored (6 attached, 1 end-only), 0 unanchored -->
```

The meta report is the sum of the ninety page reports; this page contributes
7 of the 563.

## 7. Refusals — and why they are the point

`refusals: none` is what a **supported** convention looks like. Refusals are
not the tool failing; they are the tool declining to invent. Three kinds —
the first two are reproducible with the files you already have.

### A band whose convention is not implemented

The SBL Greek New Testament, published as free per-book PDFs, exercises the
verse-referenced grammar. Fetch the publisher's bundle:

```console
$ curl -sSL -o sblgnt.zip https://sblgnt.com/download/SBLGNTpdf.zip
$ python3 -c "import zipfile; z=zipfile.ZipFile('sblgnt.zip'); \
  open('61-SBLGNT-Matthew.pdf','wb').write(z.read('61-SBLGNT-Matthew.pdf')); \
  open('78-SBLGNT-Philemon.pdf','wb').write(z.read('78-SBLGNT-Philemon.pdf'))"
```

Matthew parses (no page flags needed — the file *is* the edition):

```console
$ diorthosis build 61-SBLGNT-Matthew.pdf -o mt/
[!] no conspectus siglorum found in the front matter: witnesses will be missing from the TEI and manuscript sigla cannot be attributed
wrote mt/61-SBLGNT-Matthew.tei.xml
wrote mt/61-SBLGNT-Matthew.md
wrote mt/61-SBLGNT-Matthew.witnesses.json
coverage: 827 entries — 827 parsed, 0 refused, 0 unparsed; 777 anchored (770 attached, 7 end-only), 50 unanchored
refusals: none
```

Philemon does not:

```console
$ diorthosis build 78-SBLGNT-Philemon.pdf -o phm/
[!] no conspectus siglorum found in the front matter: witnesses will be missing from the TEI and manuscript sigla cannot be attributed
wrote phm/78-SBLGNT-Philemon.tei.xml
wrote phm/78-SBLGNT-Philemon.md
wrote phm/78-SBLGNT-Philemon.witnesses.json
coverage: 14 entries — 0 parsed, 14 refused, 0 unparsed; 0 anchored (0 attached, 0 end-only), 14 unanchored
refusals: 14× paragraph convention gate refused band: foreign separator '•' is not consumed
```

Same publisher, same series, same page design. Philemon is a single-chapter
book, so its band opens with bare verse numbers instead of `chapter:verse`;
the verse grammar does not fire, the paragraph grammar is tried, and its gate
finds a `•` it cannot account for. Rather than emit fourteen plausible
`<lem>/<rdg>` pairs, diorthosis keeps all fourteen entries as verbatim notes
and says so — with the gate's own sentence, not a generic "failed".

This is the behaviour wave A had to restore. An Opus assessment found the
tool emitting a numbered English editorial *footnote* as a `<lem>/<rdg>`
apparatus variant, in schema-valid TEI, at exit `0`. The gates that stop that
also stop Philemon, and that trade is deliberate: **a refusal costs you an
entry; a fabrication costs you the archive.**

Exit code here is `0`, not `1`. A refusal with a stated reason is a correct
result, not a failed run.

### A band that is detected but yields nothing

Back on balex, ask for the *Appendix critica*:

```console
$ diorthosis build balex.pdf --pages 172-180 --conspectus-page 54 --text-lang la -o appcrit/
self-check FAILED: this build is not certified
  degenerate: 9 apparatus band(s) were detected but no entry was split from any of them: the apparatus is present in the TEI as verbatim prose only, and nothing is anchored.
the files above were written but are NOT certified; fix the command line, or pass --ignore-self-check to accept them as they are
conspectus: 24 witnesses, 103 editors declared
wrote appcrit/balex.tei.xml
wrote appcrit/balex.md
wrote appcrit/balex.witnesses.json
coverage: 0 entries — 0 parsed, 0 refused, 0 unparsed; 0 anchored (0 attached, 0 end-only), 0 unanchored
refusals: none
$ echo $?
1
```

The *Appendix critica* is a full-page list of orthographic variants, not a
foot apparatus keyed to a constituted text on the same page. diorthosis sees
the band, splits no entry from it, and refuses to call that a success. The
prose is still in the TEI, verbatim; it simply is not structure.

### A whole edition refused

For the shape of a wholesale refusal on never-seen conventions — eight of
nine reviewer-supplied editions, 100 % verbatim-refused, measured — see
[generalization.md](generalization.md). That table is the honest ceiling of
what "general-purpose" currently means.

## 8. Check the outputs

Two mechanical checks. Run both; they check different things.

```console
$ diorthosis validate out/balex.md
OK: md-ce/0.3 invariants hold
$ echo $?
0
```

`validate` runs SPEC.md's invariants: no text/apparatus mixing, marker
syntax and page scoping, delimiter purity, addressability, page ordering,
provenance flags, and the coverage-honesty invariant that forces the meta
line, the page lines and the console to render one report. `build` already
ran this on its own output before claiming success — which is why the naive
build in step 4 exited `1`.

```console
$ diorthosis roundtrip out/balex.md out/balex.tei.xml
OK: md-ce and TEI carry the same content
$ echo $?
0
```

`roundtrip` checks that the two views are projections of one model: same
folios in the same order, same normalised text per page, same source-slice
apparatus entries with the same multiplicities, same translation and notes.

Third, validate the TEI itself against the TEI-all RELAX NG schema. Neither
`lxml` nor the schema ships with diorthosis — the schema is the same URL and
the same pinned checksum `tools/golden/fetch_sources.sh` uses:

```console
$ pip install lxml
$ curl -fsSL -o tei_all.rng https://tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng
$ shasum -a 256 tei_all.rng
b0f115095ead2ccc6933aa3365c6f4a82cba3b2ec7eee7f76bb616d7a63b7e48  tei_all.rng
$ python3 -c "
from lxml import etree
rng = etree.RelaxNG(etree.parse('tei_all.rng'))
print('TEI valid against tei_all.rng:', rng.validate(etree.parse('out/balex.tei.xml')))"
TEI valid against tei_all.rng: True
```

## 9. TEI or md-ce — which do I cite?

**The TEI is the citable artifact. The md-ce is the retrieval surface.**
They are two projections of one internal model, and md-ce is *deliberately
lossy*.

Here is one apparatus entry in both. md-ce, one entry per physical line, the
printed band's own wording:

```
### apparatus [source=born_digital generative=false confidence=0.90 block=2]

5 cotidie operibus USTV | cotidie M (cf. BC 3.112.9) | nouis cotidie  operibus Castiglioni (cf. Tac. Hist. 2.76.4)
7 aptantur MUSTV (u.  BC 3.112.7–9 et cf. Virg. Aen. 3.472) | temptantur Nipperdey (cf. BC  3.40.1) | alii alia (u. Gaertner-Hausburg 48 n.87)
```

TEI, the same entry with its structure and its provenance:

```xml
<app n="5" from="#a-p82-e0-start" to="#a-p82-e0">
  <lem wit="#wit-U #wit-S #wit-T #wit-V">cotidie operibus</lem>
  <rdg wit="#wit-M">cotidie</rdg>
  <rdg source="#ed-Castiglioni">nouis cotidie operibus</rdg>
  <note type="comment">(cf. BC 3.112.9)</note>
  <note type="comment">(cf. Tac. Hist. 2.76.4)</note>
  <note type="verbatim">5 cotidie operibus USTV | cotidie M (cf. BC 3.112.9) | nouis cotidie

operibus Castiglioni (cf. Tac. Hist. 2.76.4)</note>
</app>
```

| | TEI P5 | md-ce/0.3 |
|---|---|---|
| lemma / readings / witnesses | `<lem>`, `<rdg>`, `@wit`, `@source` | **omitted** |
| exact printed wording | `<note type="verbatim">`, line breaks preserved | present, one entry per line, line breaks unwrapped to single spaces |
| anchoring into the text | `<anchor>` + `@from`/`@to` | numeric markers only, `⟦folio:n⟧` |
| witness declarations | `<listWit>` from the conspectus | **omitted** — see `S.witnesses.json` |
| running heads, page numbers | `<fw>` | **omitted** |
| chunking for retrieval | — | `### ` sections, layer named, provenance bracketed |

So: **cite the TEI**, always. `<app>` elements carry no `xml:id`; the stable
handle is the anchor they point at — `#a-p82-e0` above, which encodes the
0-based file page and the entry ordinal — together with the `@n` the edition
printed and the enclosing `<pb>`. Feed the md-ce to a chunker, a search index
or a language model — its one job is that a chunker can never mix apparatus
into constituted text, and its meta line names the TEI it came from. If your
md-ce and your TEI ever disagree, `roundtrip` is the arbiter.

An entry the tool refused is *still there* in both views — as
`<note type="apparatus">` in the TEI and as a plain line in the md-ce. Nothing
is dropped. That is what makes refusals safe to act on.

## 10. Where the last 1–10 % goes

Grammars get a real edition to somewhere between 90 % and 99 %. On the one
edition measured against no digital ground truth (Bobichon's *Justin Martyr*,
2,031 entries, measured 2026-08-04) attribution coverage is 89.9 % — roughly
one entry in ten needs a human eye. The review loop exists for that stretch,
and makes it replayable:

```console
$ pip install 'diorthosis[review]'
$ diorthosis review balex.pdf --pages 82-84 --conspectus-page 54 --text-lang la -o review/
conspectus: 24 witnesses, 103 editors declared
wrote review/index.html
review: 18 entries — 18 parsed, 0 refused, 0 unanchored, 0 reviewed; 18 snippets
```

Open `review/index.html`: each entry sits beside the **image snippet of the
printed band lines it was split from**, cropped from the PDF itself. Refusals
and unanchored entries filter to the front as a work queue. Correct what is
wrong, download `overrides.json`, and replay it on every rebuild with
`build --overrides` — each corrected entry is marked `resp="#human-review"`
in the TEI, never silently merged into what the grammar read.

The full loop, including what the hashed override format protects you from,
is in [cookbook.md](cookbook.md#review-an-edition-and-replay-the-corrections).

## Next

- [cookbook.md](cookbook.md) — sigla without a conspectus, overrides,
  retrieval, `witnesses.json`, OCR input, running the golden harnesses.
- [cli.md](cli.md) — every subcommand, every flag, the four exit codes.
- [troubleshooting.md](troubleshooting.md) — the real failure messages.
- [generalization.md](generalization.md) — what happens on editions the
  grammars have never seen.
- [../SPEC.md](../SPEC.md) — md-ce/0.3, normative.
