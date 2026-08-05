<!--
CONTRIBUTING.md has the reasoning behind every box below. The short version:
a change is not finished when the code works, it is finished when the evidence
still holds.
-->

## What this changes, and why

<!-- If it changes what diorthosis CLAIMS about a page — a new structure, a
     structure withdrawn, an anchor moved — say that first and in those words. -->

## Evidence

- [ ] `PYTHONPATH=$PWD/src python3 -m pytest -q` — run **before and after**;
      nothing moved that I did not intend to move.
- [ ] `python3 -m ruff check src/ tests/` is clean.
- [ ] New behaviour arrives with a test that fails without it.

Suite before → after:

```
```

## Does this touch a grammar, a gate, or the layer splitter?

- [ ] **No** — nothing under `grammar.py`, `versegrammar.py`, `linegrammar.py`,
      `paragraphgrammar.py`, `convention.py`, `anchor.py`, or the ingest
      layering.
- [ ] **Yes** — then the full battery is re-run and pasted below. Not "it looks
      local": re-running every harness after each change is what caught three
      cross-corpus regressions during v0.6 that no unit test saw.

| Battery | Expected | Observed |
|---|---|---|
| Retypeset balex | 524 apps, 0 errors, 0 gaps | |
| Retypeset SBLGNT | 6,906 apps, 0 errors, 0 gaps | |
| Retypeset *Problemata* | 5,524 apps, 0 errors, 50 gaps | |
| Real balex, line grammar | 563 = 0 errors / 0 gaps, 17 typed divergences, 563 anchored = 515 attached + 48 end-only | |
| Real-print coverage (balex, Matthew) | PASS on non-zero denominators | |
| Whole NT oracle | 6,921 = 6,797 + 61 + 60 + 3, 0 errors | |
| Plaoul | 6,293 apps, 0 errors, anchored 94.9 % | |
| Determinism (`double_build.py`) | every output MATCH | |
| Bobichon | 2,031 at 99.3 / 99.0 / 97.5 / 89.9 | |
| Generalization | nine-edition table unchanged | |

Batteries I could **not** run, and why (the real-print and Bobichon inputs are
reviewer-local by licence — say so, do not leave the row blank):

## If a published figure moved

<!-- Explain the movement BEFORE updating any prose to match it. The one time a
     figure legitimately moved (Problemata 47 -> 50 gaps at v0.7) it took a
     paragraph of evidence to establish that the movement was a gain. -->

- Which figure, from what to what:
- Entry by entry, what changed side and why:
- Is it a gain, a loss, or accounting?
- [ ] FINDINGS.md records the measurement, its date, and the tree it was
      measured on.

## Declarations

- [ ] No ancient-language text, siglum or reading was invented. Everything
      quoted is present in the source in front of me, and fixtures are synthetic
      or carry their provenance.
- [ ] No threshold was relaxed, no contract test was `xfail`ed, no edition was
      whitelisted, and no gate reads an edition-specific signal.
- [ ] No green number in this PR has a zero denominator.
- [ ] Documentation touched by this change still passes `tests/test_docs.py`
      (flags exist, links resolve, transcripts match what the tool prints).
