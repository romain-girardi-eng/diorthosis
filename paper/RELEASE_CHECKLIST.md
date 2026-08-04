# JOSS release and submission checklist

This checklist separates actions that can be completed now from evidence that
must exist before submission. The local repository history inspected on
4 August 2026 is concentrated on 3--4 August 2026. It does not establish when
the repository first became public, six months of public development, or
research adoption.

## Submission gates

- [ ] **Confirm current JOSS eligibility before doing release administration.**
  Current JOSS guidance asks for a public repository older than six months,
  active development spanning more than six months, and demonstrated research
  impact. Supply public evidence outside the local clone if it exists;
  otherwise continue open development and document research use before
  submitting. See the [JOSS submission
  requirements](https://joss.readthedocs.io/en/latest/submitting.html).
- [ ] **Reconcile the paper with the guidelines in force on submission day.**
  The requested draft is 250--1,000 words and uses the requested section set.
  As consulted on 4 August 2026, JOSS instead specifies 750--1,750 words and
  requires `State of the field`, `Software design`, `Research impact
  statement`, and `AI usage disclosure` sections in addition to the other
  front matter. The draft already overlaps the current word range and includes
  the disclosure, but it still needs an evidence-backed impact statement and
  final heading alignment. See [JOSS paper
  format](https://joss.readthedocs.io/en/latest/paper.html).
- [ ] Add evidence of scholarly use, reuse, citation, teaching, or contribution
  outside the author. Do not turn downloads, stars, or self-validation into an
  impact claim without the evidence JOSS requests.
- [ ] Re-run the First1KGreek corpus count immediately before submission and
  record the repository revision and counting command. Keep “approximately
  1,356” and “two files containing `<app>`” only if reproduced.
- [ ] Re-run the prior-art search, especially for work published after the
  review recorded in `docs/prior-art.md`. Retain every qualifier in the novelty
  claim.

## Author and paper metadata

- [ ] Obtain Romain Girardi's ORCID and add it to the JOSS author metadata.
  Do not invent or infer the identifier.
- [ ] Complete the acknowledgement section with funding, institutional support,
  contributors, and conflicts as applicable.
- [ ] Have the named author review, edit, and validate all AI-assisted prose,
  confirm that the core research and software-design decisions were human-made,
  and replace the provisional AI disclosure with that attestation. Follow the
  [current JOSS AI policy](https://joss.readthedocs.io/en/latest/policies.html#artificial-intelligence-ai-generated-content-and-tool-use).
- [ ] Check every bibliography entry against its DOI landing page or primary
  repository and ensure every in-text claim is within what the source supports.
- [ ] Build the paper with the current JOSS toolchain and inspect the rendered
  PDF for citation, table, code, Unicode Greek, and line-overflow problems.

## Software release

- [ ] Decide whether the changes after tag `v0.6.0` require `v0.6.1` or
  `v0.7.0`; synchronize `pyproject.toml`, the release tag, and the paper's
  archived software citation.
- [ ] Run the complete test and evidence battery from a clean environment,
  including all golden, adversarial, real-print, round-trip, validation, and
  two-process determinism checks. Save the commands, source revisions, fixture
  hashes, and outputs used for every number in the paper.
- [ ] Confirm that the source-complete SBLGNT ledger still reports 6,921 source
  leaf entries, 6,797 comparisons, and zero oracle errors; investigate rather
  than merely updating prose if any value changes.
- [ ] Confirm the other paper figures: `balex` 563 with zero errors/zero gaps;
  Plaoul 6,293 with zero errors; retypeset `balex` 524, SBLGNT 6,906, and
  *Problemata* 5,524 with zero structural errors and 47 honest gaps; Bobichon
  2,031 at 99.3/99.0/97.5/89.9; and 159 tests.
- [ ] Update stale figures in public project documentation before release so
  that the paper, README, findings, and harness reports do not disagree.
- [ ] Build both source and wheel, inspect their contents and metadata, install
  the wheel into a fresh environment, and exercise the documented CLI.
- [ ] Create a signed or otherwise attributable version tag and GitHub release
  only after the checks pass. Do not move a published tag.

## PyPI trusted publishing

The repository already contains an OIDC publishing workflow at
`.github/workflows/publish.yml` with a `pypi` environment and
`id-token: write`; the remaining publisher-side configuration cannot be proved
from this clone.

- [ ] On PyPI, add or verify a Trusted Publisher for owner
  `romain-girardi-eng`, repository `diorthosis`, workflow `publish.yml`, and
  environment `pypi`. Match spelling and case exactly. Follow [PyPI's Trusted
  Publisher instructions](https://docs.pypi.org/trusted-publishers/adding-a-publisher/).
- [ ] Protect the GitHub `pypi` environment as appropriate for releases.
- [ ] Publish the chosen release through the workflow and verify the version,
  files, hashes, project URLs, license metadata, and clean-environment install
  on PyPI. Do not store a long-lived PyPI API token if trusted publishing works.

## Zenodo archive and DOI

- [ ] Sign in to Zenodo with GitHub, authorize repository access, and toggle
  `diorthosis` **On** before creating the archival GitHub release. Zenodo only
  archives releases made after the repository is enabled. Follow GitHub's
  [Zenodo guide](https://docs.github.com/en/repositories/archiving-a-github-repository/referencing-and-citing-content).
- [ ] After the release is archived, edit the Zenodo record: title, version,
  author name and ORCID, affiliation, description, license, keywords, related
  GitHub URL, and release date. Verify the files in the deposit.
- [ ] Record the version DOI returned for the reviewed release and the concept
  DOI for the software series. Use the version DOI where JOSS asks for the
  archived reviewed release; do not substitute a badge URL.
- [ ] Add the final DOI to the README, citation metadata, and paper bibliography,
  then rebuild the paper. If this changes the release artifact, resolve the
  ordering with the JOSS editor rather than silently replacing the archive.

## JOSS submission

- [ ] Read the [JOSS author guide](https://joss.readthedocs.io/en/latest/submitting.html)
  again on submission day and complete its pre-submission checklist.
- [ ] Open the JOSS submission form and provide the repository URL, exact
  release/version, Zenodo version DOI, paper source, software license, research
  field, author metadata, conflicts, and an evidence-backed statement of
  research impact.
- [ ] Confirm that installation and core functionality can be reviewed without
  private data, proprietary services, or undocumented credentials.
- [ ] Keep the review in the public issue/PR workflow and answer reviewer
  requests with commits, tests, and citations. Under the current policy, do not
  use generative AI to compose author--editor or author--reviewer exchanges
  except for permitted translation.
- [ ] At acceptance, archive the exact reviewed release requested by the editor
  and verify that the DOI, tag, package, and paper all identify the same code.

## Possible reviewers to screen

These names all occur in `docs/prior-art.md`. They are suggestions by subject
proximity, not endorsements. Check JOSS eligibility, availability, recent
collaboration, institutional relationships, competition, and all other
conflicts before proposing anyone.

- Luigi Bambaci
- Robert Turnbull
- Federico Boschetti
- Matteo Romanello
- Thibault Clérice
