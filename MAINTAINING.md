# Maintaining diorthosis

Everything a maintainer needs that is not in [CONTRIBUTING.md](CONTRIBUTING.md):
how a release is actually cut, what the evidence harness needs installed before
any of it can be re-derived, and what to do when a battery goes red.

Nothing here is automated on purpose. A release of this tool republishes a set
of measured claims, and a human has to be able to say they re-derived them.

## 1. The release procedure, end to end

### 1.1 Decide the number

Semantic versioning, read through [docs/stability.md](docs/stability.md): the
six frozen contracts are what a *major* bump is for. Removing a subcommand or
an option, changing what an option means, changing an exit code, breaking an
md-ce invariant, or dropping a name from `diorthosis.__all__` is a break.
Adding a grammar, a refusal reason, a subcommand or an option is a minor.

`md-ce` and `diorthosis-overrides` carry their **own** versions inside the
artefact and move independently of the package version. Bumping md-ce is not
optional politeness: the 0.3 validator refuses a 0.4 file rather than
half-reading it, and that is the mechanism the freeze rests on.

### 1.2 The version lives in TWO files, and a test knows it

```console
$ python3 -m pytest tests/test_public_api.py -q -k version
```

- `pyproject.toml` → `version = "…"`
- `src/diorthosis/__init__.py` → `__version__ = "…"`

`test_version_matches_pyproject` fails if they disagree, so this pair cannot
drift. A third copy exists in `CITATION.cff` (`version:` and `date-released:`)
which **no test checks** — update it by hand, in the same commit, or the
archived citation will name a version that never shipped.

`__version__` is assigned *before* the relative imports in `__init__.py`
because `tei.py` and `md.py` do `from . import __version__` to stamp their
output. Moving that assignment breaks the package at import time; a test
guards the ordering.

### 1.3 The pre-tag gate

In order, from a clean tree:

1. `PYTHONPATH=$PWD/src python3 -m pytest -q` — green, with any deliberately
   red contract test accounted for in the CHANGELOG.
2. `python3 -m ruff check src/ tests/` — clean.
3. Every battery in CONTRIBUTING.md re-run, and every figure it prints compared
   with the figure this repository publishes. **Re-derive, never retype.**
4. `python3 -m build`, then install the wheel into a *fresh* environment and run
   the documented CLI against a real edition. This is the step that catches a
   missing `package-data` entry, and nothing else does.
5. FINDINGS.md gets the release's lab-notebook entry, and CHANGELOG.md its
   section. If a published figure moved, the entry explains the movement before
   the prose is updated.

### 1.4 Tag, release, publish

```console
$ git tag -a vX.Y.Z -m "diorthosis X.Y.Z"
$ git push origin vX.Y.Z
```

Then create the **GitHub release** from that tag. Two things hang off that
single action, so do them in this order:

- **Zenodo must be switched on for the repository *before* the release is
  created.** Zenodo only archives releases made after the repository is
  enabled; enabling it afterwards archives nothing and the release has to be
  redone. Once archived, edit the deposit (title, version, ORCID, affiliation,
  licence, keywords) and record **both** DOIs: the *version* DOI for this
  release and the *concept* DOI for the series.
- **PyPI publishing is triggered by the release**, not by the tag:
  `.github/workflows/publish.yml` runs on `release: [published]`, builds with
  `python -m build`, and uploads through `pypa/gh-action-pypi-publish` from the
  `pypi` GitHub environment with `id-token: write`. That is **Trusted
  Publishing over OIDC — there is no PyPI token stored anywhere**, and there
  must never be one. The publisher-side configuration lives on PyPI and cannot
  be verified from this clone: owner `romain-girardi-eng`, repository
  `diorthosis`, workflow `publish.yml`, environment `pypi`, spelling and case
  exact.

After publication, verify on PyPI: version, both artefacts, the project URLs,
the licence metadata, and a clean-environment install of the *published* wheel.

Never move a published tag. If something is wrong, the fix is a new patch
release, because the Zenodo DOI and the PyPI artefact already point at the old
one.

`paper/RELEASE_CHECKLIST.md` carries the JOSS-specific gates (paper word count,
impact evidence, reviewer screening) and is the authority for a submission; it
is not repeated here.

## 2. Harness prerequisites nobody wrote down

`pip install -e ".[dev]"` gets you the fast suite and nothing else. The
evidence harness stands on four things pip cannot give you.

### 2.1 External binaries

| Binary | Needed by | Note |
|---|---|---|
| `tectonic` | every retypeset golden (`run_golden.py`), `plaoul_build_pdf.py` | Verified with 0.17.0. It self-fetches its TeX packages on first run, so the first invocation needs a network and is slow. |
| `git` | `plaoul_build_pdf.py` | Clones `lombardpress/lbp-print-xslt` and `lombardpress/lombardpress-lists` at pinned commits. |
| `curl` | `fetch_sources.sh`, `fetch_generalization_corpus.sh`, `plaoul_build_pdf.py` | |

### 2.2 Python extras

| Extra | Contents | Needed by |
|---|---|---|
| `[dev]` | `pytest`, `ruff`, `lxml` | the fast suite; `lxml` powers every golden checker, and the harness tests `importorskip` it |
| `[review]` | `pypdfium2`, `Pillow` | `diorthosis review` only — it rasterizes the page snippet each entry is shown against. **`pypdfium2` is BSD/Apache; PyMuPDF's AGPL is deliberately avoided.** Without this extra `review` cannot produce snippets. |
| `[golden]` | `lxml`, `saxonche` | the golden harness end to end. `saxonche` (Saxon-C HE) is the XSLT 3.0 processor that runs LombardPress's own `critical.xslt`; nothing else in the project needs XSLT. |

```console
$ python3 -m pip install -e ".[dev,review,golden]"
```

### 2.3 Which drivers need the network

| Driver | Network | What it fetches |
|---|---|---|
| `tools/golden/fetch_sources.sh` | **yes, once** | the three scholar TEI editions at pinned commits, and `tei_all.rng` pinned by SHA-256 |
| `tools/golden/fetch_generalization_corpus.sh` | **yes** | the eight published PDFs of the generalization corpus, each checked by SHA-256; `--with-gracilis` also clones two repositories and fetches the SCTA TEI |
| `tools/golden/plaoul_build_pdf.py` | **yes** | the Plaoul TEI per lectio, plus two GitHub clones; `tectonic` may also fetch TeX packages |
| `run_golden.py`, `real_check.py`, `line_check.py`, `verse_check.py`, `plaoul_check.py`, `sblgnt_nt_driver.py`, `double_build.py`, `generalize.py`, `tools/evaluate.py` | no | they run on files already on disk |
| the pytest suite | no | synthetic fixtures only |

### 2.4 Inputs that are not fetched at all

`fetch_sources.sh` downloads the scholars' **TEI**, not the publishers' printed
PDFs. The real-print batteries additionally need the DLL's own
`ldlt-balex.pdf` and the `sblgnt.com` per-book PDFs, and the Bobichon
reference battery needs a Paradosis volume that is **not redistributable**.
These are reviewer-local by licence, not by neglect, and any claim derived from
them has to say so.

## 3. Triaging a red battery

The first question is never "which threshold do I move".

**0. Is the harness measuring anything?** Read the denominator first. `0 errors`
of `0 examined` is not a pass — `real_check` now says NOT-PROVEN for exactly
that case, and a `ModuleNotFoundError` in a spawned subprocess produces a
driver that reports *nothing measured* while looking calm. Check
`import diorthosis` resolves to your checkout, export `PYTHONPATH=$PWD/src`,
and re-read the totals.

**1. Is the tool wrong, or is the ground truth?** Both happen, and the project
has a shape for each answer:

- The tool is wrong → fix the tool. That is the default and the presumption.
- The **print and the encoding genuinely disagree** → that is a *typed
  divergence*, recorded in `tools/golden/divergences.py` with the error kind,
  both forms, and literal band evidence. An exception fires only when the
  observed kind matches *and* the printed form is present in the extracted
  band; a stale exception is itself an error. There are 59 for the SBLGNT and
  17 for balex, and every one was verified against the extracted band before it
  was written down. **A divergence record is not a way to silence a failure.**

**2. Did the structure become wrong, or merely absent?** The bar is asymmetric
and stays that way: a *wrong* structure — phantom entry, wrong
lemma/reading/witness/editor, misplaced anchor, altered verbatim, dangling
IDREF — **fails** the run. A *missing but honest* structure — the entry kept as
a verbatim note, the entry left unanchored — is a **reported gap**, never a
failure. A change that converts errors into gaps is usually a gain; say so and
show the entries.

**3. Is the movement real or is it accounting?** Read the partition, not the
total. The three *Problemata* gaps added at v0.7 are one entry each counted
twice (`kept as verbatim note` + `note has no target`), and the corresponding
`<app>` had been pointing at nothing. The NT driver deliberately **exits 1**
while three apps fall in no bucket; that non-zero exit is the feature.

**4. Cross-corpus, always.** A change to a grammar, a gate or the layer
splitter is re-certified against *every* battery before it is believed —
including the corpora you are sure it cannot reach, because those are the ones
that got broken last time.

**5. Whatever the answer, write it in FINDINGS.md.** Not the fix — the
measurement, its date, and the tree it was measured on. A notebook entry
records what was true on its date; correcting one in place destroys the thing
that made the correction legible, so later entries carry forward references
instead.
