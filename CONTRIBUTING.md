# Contributing to diorthosis

diorthosis compiles a *published* critical edition into TEI and md-ce. That
means every structure it emits is a claim about what a scholar printed, and the
only thing separating this tool from a plausible-sounding fabricator is that
each claim is checked against ground truth somebody else encoded. Contributions
are welcome on exactly those terms: **a change is not finished when the code
works, it is finished when the evidence still holds.**

Read [SPEC.md](SPEC.md) for what the formats are, [docs/stability.md](docs/stability.md)
for what 1.0 freezes, and [FINDINGS.md](FINDINGS.md) for the lab notebook — most
"why is it done this way" questions are answered there by a measurement.

## Setting up

```console
$ git clone https://github.com/romain-girardi-eng/diorthosis
$ cd diorthosis
$ python3 -m pip install -e ".[dev]"
```

### The `PYTHONPATH` trap — read this before you file a bug

It has cost this project a full verification round, twice, in opposite
directions. The harnesses and several tools run from an **uninstalled
checkout**, and some of them spawn subprocesses that `import diorthosis`
without passing anything on. Against an interpreter with no diorthosis
installed, those subprocesses die with `ModuleNotFoundError` — and the honest
drivers report that as *nothing measured*, not as a failure of the tool. The
opposite mask is worse: a **stale editable install of an older version**
shadowing your working tree, so your green run measured code you did not write.

Two rules:

```console
$ python3 -c "import diorthosis, sys; print(diorthosis.__file__, diorthosis.__version__)"
$ PYTHONPATH=$PWD/src python3 -m pytest -q
```

1. Before trusting any run, print where `diorthosis` is imported from and which
   version it is. If it is not your checkout, uninstall it.
2. Export `PYTHONPATH=$PWD/src` for everything, and especially before
   `tools/golden/sblgnt_nt_driver.py` and `tools/golden/double_build.py`, which
   spawn subprocesses that need it.

**Read the denominator before you read the verdict.** A driver that says
`0 errors` on `0 examined` is telling you it did not run.

## The fast suite

```console
$ PYTHONPATH=$PWD/src python3 -m pytest -q
$ python3 -m ruff check src/ tests/
```

It runs in well under a minute and needs no network, no `tectonic`, and no
edition content: the fixtures are synthetic. CI runs exactly this on Python
3.10, 3.12 and 3.14.

The suite may contain tests that are **red on purpose** — a wave that writes
the contract before the code deliberately leaves the contract failing, and the
[CHANGELOG](CHANGELOG.md) says which wave did that and how many. So the bar is
not "the number is green", it is: **run the suite before your change, run it
after, and nothing may move that you did not intend to move.** If a test you
did not touch turns red, that is your finding, not noise.

## The bar a change must clear

1. **A new behaviour arrives with a test that fails without it.** Tests here are
   named after the contract they encode, not the function they call.
2. **A refusal is a feature.** If your change makes diorthosis emit structure it
   previously refused, the burden of proof is on the structure. If it makes it
   refuse something it previously emitted, say what the emitted claim was and
   why the page could not support it.
3. **Never soften a check to pass.** Do not relax a threshold, do not `xfail` a
   contract violation, do not whitelist an edition, do not add an
   edition-specific signal to a gate. Every gate in `convention.py` reads
   structural signals only, and it must stay that way or the generalization
   result means nothing.
4. **Do not invent edition content.** No Greek, no Latin, no siglum, no reading
   that is not in the source in front of you. Fixtures are synthetic or quoted
   with their provenance.
5. **`ruff check src/ tests/` is clean** and the code follows the surrounding
   style (2-space indent, module docstrings that say *why*).

### The non-negotiable

> **A change that touches a grammar, a gate or the layer splitter arrives WITH
> its full battery re-run.**

Not "I ran the unit tests". Not "it looks local". While v0.6 was hardening the
layer separation in regreek, re-running every harness **after each change**
caught **three cross-corpus regressions** that no unit test saw (FINDINGS §19).
That is why the batteries are re-run after each change to shared layering code,
not once at the end of the branch. The same lesson has a second edge: v0.7's
convention gate was measured **inert** on the three retypeset goldens precisely
because all three print the numeric-marker convention and therefore traverse the
gate that changed. "It cannot affect that corpus" is a hypothesis, and the
battery is how you test it.

Paste the battery output into the pull request. If a figure moves, do not
update the prose to match — explain the movement first. The one time a figure
legitimately moved (*Problemata* 47 → 50 gaps at v0.7) it took a paragraph of
evidence to establish that the movement was a **gain**, and that paragraph is
still in `tools/golden/README.md`.

## The batteries

`tools/golden/README.md` is the reference; this is the checklist. Fetch the
scholar TEI once, then run what your change can reach.

```console
$ sh tools/golden/fetch_sources.sh
```

| Battery | Command (from the repository root) | Must print |
|---|---|---|
| Retypeset balex | `python3 tools/golden/run_golden.py tools/golden/data/balex.xml tools/golden/work/balex --text-lang la --rng tools/golden/tei_all.rng` | 524 apps, **0 errors, 0 gaps** |
| Retypeset SBLGNT | `python3 tools/golden/run_golden.py tools/golden/data/sblgnt.xml tools/golden/work/sblgnt --rng tools/golden/tei_all.rng` | 6,906 apps, **0 errors, 0 gaps** |
| Retypeset *Problemata* | `python3 tools/golden/run_golden.py tools/golden/data/problemata.xml tools/golden/work/problemata --text-lang la --rng tools/golden/tei_all.rng` | 5,524 apps, **0 errors**, 50 gaps |
| Real balex, line grammar | `python3 tools/golden/line_check.py tools/golden/data/balex.xml out/ldlt-balex.tei.xml --known tools/golden/balex_known_divergences.json` after a `build … --pages 82-171 --conspectus-page 54 --text-lang la` | 563 compared, **0 errors, 0 gaps**, 17 typed divergences; 563 anchored = **515 attached + 48 end-only** |
| Real-print coverage | `python3 tools/golden/real_check.py tools/golden/data/balex.xml ldlt-balex.pdf --pages 82-171 --conspectus-page 54 --text-lang la` | **PASS**: text 530/555 = 95.5 %, band 555/555, 0 of 527 examined, 0 of 321 examined, floor 56 |
| Real Matthew | `python3 tools/golden/real_check.py tools/golden/data/sblgnt.xml 61-SBLGNT-Matthew.pdf --max-apps 770` | **PASS**: text 755/770 = 98.1 %, band 770/770, 0 of 488, 0 of 767, floor 77 |
| Whole NT oracle | `PYTHONPATH=$PWD/src python3 tools/golden/sblgnt_nt_driver.py tools/golden/data tools/golden/work/nt` | 6,921 source = 6,797 compared + 61 refused + 60 uncovered + 3 unaccounted; **0 errors**, 59 typed divergences; **exit 1** until the 3 are adjudicated by a human |
| Plaoul double apparatus | `python3 tools/golden/plaoul_build_pdf.py tools/golden/work/plaoul 1` then `python3 tools/golden/plaoul_check.py tools/golden/work/plaoul/lectio1.xml tools/golden/work/plaoul/lectio1.pdf` — repeat for lectios 1–30 | lectio 1 alone is 235 apps; the full sweep is 6,293 apps, **0 errors**, anchored 5,969/6,293 = 94.9 % |
| Determinism | `PYTHONPATH=$PWD/src python3 tools/golden/double_build.py ldlt-balex.pdf --pages 82-84 --conspectus-page 54 --text-lang la` | every output file MATCH |
| Bobichon (reference marker edition) | `python3 tools/evaluate.py EDITION.pdf --pages 188-560` (add the edition's own `--conspectus-page`) | 2,031 entries at 99.3 / 99.0 / 97.5 / 89.9; 186 of 186 marker bands accepted |
| Generalization | `sh tools/golden/fetch_generalization_corpus.sh` then `python3 tools/golden/generalize.py` | the nine-edition table of [docs/generalization.md](docs/generalization.md), unchanged edition by edition |

Three of those need inputs `fetch_sources.sh` does not download, because they
run on the edition **as its publisher printed it**: the DLL's own
`ldlt-balex.pdf`, the `sblgnt.com` per-book PDFs, and — for the Bobichon
line — a copyrighted Paradosis volume that is not redistributable at all. Say
so in your pull request if you could not run one; a battery you skipped is a
fact about the review, and hiding it is the failure mode this whole repository
exists to prevent.

Prerequisites, none of which pip can install for you: `tectonic` (all the
retypeset goldens, Plaoul), `git` and `saxonche` (Plaoul, Gracilis), a network
(the fetch scripts, Plaoul, Gracilis). `MAINTAINING.md` lists them with their
versions.

## Documentation is executable

`tests/test_docs.py` scans every Markdown file at the repository root and under
`docs/` and `paper/`. It will fail your change if you document a subcommand or
a flag that does not exist, link to a file that is not there, or paste a
console transcript in a shape the tool no longer prints. A block whose line
above is

```
<!-- diorthosis-doc: runnable -->
```

is **executed** by the suite, and every non-`$` line in it must really appear in
the output. Prefer marking your example runnable; a documentation example that
nothing runs is a documentation example that is already wrong.

## Reporting a bug

Open an issue with the template. The three things that decide whether a report
can be acted on at all: **which edition** (with a URL or a DOI, not a
description), **the exact command**, and **the coverage line** diorthosis
printed. Without the edition nobody can reproduce a layout problem, and layout
is where the failures are.

## What this project will not accept

- Ancient-language text that is not in the source. Not reconstructed, not
  completed, not "obviously what it says".
- A grammar tuned on the edition it is being measured against.
- A green number whose denominator is zero.
- Attribution of authorship to anything other than the people who wrote the
  code.
