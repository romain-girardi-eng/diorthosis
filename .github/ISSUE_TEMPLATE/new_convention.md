---
name: Support a new apparatus convention
about: Ask for a printed apparatus convention diorthosis does not yet parse
title: "[convention] "
labels: convention
---

<!--
diorthosis implements four convention grammars: numeric-marker, verse-referenced,
line-referenced (reledmac) and paragraphed-reledmac. Everything else refuses
wholesale, on purpose — docs/generalization.md measures what happened the last
time a grammar was allowed to guess.

A convention is added when it can be driven to ZERO errors against ground truth
somebody else encoded. So the question this template really asks is: what would
we check the implementation against?
-->

## The convention

Name it as its tradition names it, and describe the entry shape as printed:
what separates entries, what separates readings, what the locator looks like,
where the sigla sit.

## An edition that prints it

- Source (URL or DOI):
- Licence:
- Pages that carry the apparatus (0-based file indices):
- Does it print a conspectus siglorum? On which page?

## What diorthosis does today

```console
$ diorthosis build EDITION.pdf --pages 30-60 --text-lang la -o out/
```

Paste the `coverage:` and `refusals:` lines. A wholesale refusal with a named
reason is the expected and correct behaviour; the reason tells us which gate
the convention trips.

## Ground truth

**This is the deciding question.** Does a machine-readable encoding of this same
edition exist — a TEI file with real `<app>/<lem>/<rdg>`, from the editors or
from a project like the DLL, SCTA or PTA?

- Ground-truth encoding (URL, licence):
- If none exists: is a qualified editor willing to double-annotate a sample?
  `docs/generalization.md` §"Inter-annotator protocol" sizes that work.

Without one of those two, a new grammar cannot be certified, and an uncertified
grammar is the thing this project refuses to ship.

## Three or four printed entries

Transcribed exactly as printed, including the separators and the sigla. Real
entries, never reconstructed ones.
