---
name: Wrong or missing apparatus structure
about: diorthosis claimed something the page does not support, or refused something it does
title: "[structure] <edition>: "
labels: apparatus
---

<!--
This is the report that matters most. A structure diorthosis emits is a claim
about what a scholar printed; a structure it refuses is a claim that the page
could not support one. Either can be wrong, and both are worth an issue.
-->

## Which edition

A URL, a DOI, or a repository path. **Not a description.** Nobody can reproduce
a layout problem from prose, and layout is where the failures are. If the
edition cannot be shared, say so — the report is still useful, but it will be
adjudicated on your evidence rather than on a re-run.

- Source:
- Pages (0-based file indices, as `--pages` takes them):

## The exact command

```console
$ diorthosis build EDITION.pdf --pages 30-60 --text-lang la -o out/
```

Exit code:

## The coverage line diorthosis printed

Paste the `coverage:` line and the `refusals:` line verbatim from the console
(they are also in the md-ce meta line). They partition the entries twice, and
that partition is usually where the answer is.

```
coverage:
refusals:
```

## What the page prints

The printed band, transcribed or screenshotted, for the entry in question.

## What diorthosis produced

The `<app>` (or the `<note type="apparatus">`) it emitted, and its
`source_slice` if you have it — `diorthosis review` shows both next to the image
of the printed band.

## Which is wrong

- [ ] **Fabrication** — diorthosis claimed a lemma, reading, witness or anchor
      the printed band does not support.
- [ ] **Over-refusal** — the band is a plain instance of a supported convention
      and diorthosis refused it anyway. Quote the refusal reason.
- [ ] **Mis-layered** — apparatus text landed in the constituted text, or the
      reverse.
- [ ] Something else:
