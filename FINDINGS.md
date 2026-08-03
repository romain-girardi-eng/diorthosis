
## 12. Eight-angle hardening campaign (2026-08-03)

Eight independent adversarial reviewers attacked P1 (TEI schema validity,
grammar, pipeline, cross-edition generalization, md-ce, code quality,
missing adapters, anchoring census). Every finding was verified against the
code before action. Highlights of what was found and fixed:

- **TEI now validates against the official `tei_all.rng`** (lxml/RelaxNG),
  from a starting point where the file was not even parseable (duplicate
  `xml:id` minted from repeating marker numbers). Ids are per-entry now;
  `<sourceDesc>` uses `<bibl>`; section titles are `<label>` (mid-div
  `<head>` is illegal); `<pb>` carries `xml:id` instead of a dangling
  `@facs`; mixed-content serialization switched to `ET.indent` (minidom's
  pretty-printer corrupted `<ab>` whitespace).
- **Anchoring rebuilt on candidates + lemma discrimination**: marker numbers
  repeat within pages (5 pages in the reference edition) and the old
  first-wins rule silently chose wrong occurrences; the lemma now
  discriminates, detached markers (``ἐδήλωσέ 4``) are accepted only under
  lemma confirmation, the glue class follows the full-book histogram
  (``]`` 16×, ``’`` 10×…), and entry splitting is parenthesis-aware and
  monotone (phantom entries eliminated). Unanchored entries on the full
  book: 60 → 12 (99.4 %).
- **Foreign-series refusal**: Göttingen-style entries (unbalanced ``]``,
  bare operator keywords, numeric minuscule ranges, numerals-as-references
  without context) are refused rather than silently misattributed — the
  cross-edition test had shown 53.8 % acceptance with essentially none
  correct. The reference series is unharmed (98.8 % parse on 2 026 entries).
- **md-ce/0.2**: normative SPEC.md with twelve mechanically-checkable
  invariants; page-scoped markers ``⟦folio:n⟧`` with explicit ``?`` for
  unresolved anchors; structural-line escaping; refusal when source text
  contains the marker delimiters; recomputable coverage numbers in-file.
- **hOCR and PAGE-XML adapters** (reviewer-contributed, spec-grounded),
  wired as ``--hocr`` / ``--page-xml``; the hOCR path reads the citable
  ``lpageno`` folio.
- **Pipeline**: page requests sorted before pairing with pdfminer's
  document-order yield (silent cross-labeling — also fixed in regreek
  v0.5.1); loud diagnostics for missing conspectus and empty ingestion;
  no user-facing tracebacks.

Full-book metrics after the campaign (pages 188-560, 2 026 entries):
anchoring 99.4 %, parse 98.8 % (refusals are honest), lemma concordance
97.6 %, attribution 91.1 %.


## 13. v0.2.1 — the spec made executable, and the honest floor (2026-08-03)

Verification pass after v0.2.0 ("pas absolument parfait" — correct).

**Fixed:**

- **I3 was violated by the emitters themselves** (20 occurrences full-book):
  lemma-confirmed *detached* markers (``ἐδήλωσέ 4``) were anchored, but
  ``md.py``/``tei.py`` re-scanned ``find_markers()`` (glued only) instead of
  using the resolved anchors — the apparatus showed ``⟦258:4⟧`` while the
  text kept a literal `` 4`` and no marker; the TEI inserted the anchor
  WITHOUT consuming the digit. Anchors now carry the exact digit span
  (``digit_start``/``digit_end``, detachment space included) and both
  emitters rewrite from the resolved anchors — one source of truth. A digit
  whose entry did not resolve stays verbatim (I3: unresolved ⇒ zero ⟦f:n⟧
  in the text).
- **``diorthosis validate``** now exists (``mdce_validate.py``): the spec's
  invariants I1-I7 and I10-I12, mechanically checked; pages split on
  ``^## page ``, sections on ``^### `` *within* a page (a naive ``^### ``
  split across the file produced ~280 false I2 positives — the validator
  had to be a real tool). The full book (373 pages, 2 026 entries) passes
  with zero violations.
- **Byte-determinism was broken across processes**: ``_emit_reading``
  iterated ``quals & _PLACEMENT`` — a *set*, whose order varies with hash
  randomization. Two identical builds differed in ``<witDetail>`` order.
  Now sorted; two full builds are byte-identical again (TEI and md).
- **CLI coherence**: ``--pages``/``--conspectus-page`` now error loudly with
  OCR sources instead of being silently ignored; ``inspect`` uses the same
  registry bootstrap as ``build`` (it anchored without lemma discrimination
  before, showing a different structure than the one built);
  ``bootstrap_registry`` factored into ``conspectus.py`` and shared with
  ``tools/evaluate.py``.
- **One more capital-class gap**: capitals with prosgegrammeni
  (ᾈ-ᾏ/ᾘ-ᾟ/ᾨ-ᾯ, U+1F88-1FAF) were missing from ``_LEMMA_CAPITAL``. Five
  genuine entries across the book were silently merged into their
  predecessor (ᾟ p194, ᾝρει p196, ᾜδεσαν p204, ᾞρται p454 and p506 — each
  verified individually, each sitting in a clean monotone band). Same bug
  family as §12's Ἀ-ῼ lesson: Greek Extended capitals live in disjoint
  sub-ranges, and every sub-range must be listed deliberately. Entry count
  2 026 → 2 031; anchoring 99.4 % → 99.5 %.

**The honest floor (censused, not estimated).** 11 entries of 2 031
(0.5 %) remain unanchored, plus 2 ambiguous (duplicate marker numbers with
no unique lemma confirmation). All 11 are ONE class: *the marker digit is
absent from the extracted text stream at the expected position* — the
printed superscript exists on paper, but the PDF's text layer does not
carry it where the word is (five are the corrupt-digit pages documented in
§12: p208/300/318/326/364, where the stream carries a *wrong* digit; two
are Latin prose notes with no in-text marker at all: p394's Catena note and
LXX collation). No regex can fix this: the information is simply not in the
stream. **v0.3 lead:** regreek has glyph geometry — a superscript digit is
recognizable by its y-offset and font size regardless of its position in
the text stream; a geometric marker sweep would recover most of this class
and could also verify every stream-based anchor.

Full-book gates after this pass: 75 tests; md-ce validate 0 violations;
TEI valid against ``tei_all.rng``; byte-identical double build; anchoring
99.5 %, parse 98.8 %, lemma concordance 97.6 %, attribution 91.2 %.


## 14. The golden harness — scholar ground truth, zero apparatus errors (2026-08-04)

The strongest verification the project has had: apparatus entries **encoded
by scholars** (open TEI editions with real `<app>/<lem>/<rdg>`) are
re-typeset into a born-digital critical-edition PDF (tectonic; conspectus
siglorum page(s) + text with numeric superscript markers + one-entry-per-
line band — deterministic pagination, page-count guard), diorthosis
compiles that PDF back, and `tools/golden/check_golden.py` requires the
output TEI to reproduce the scholars' apparatus EXACTLY — lemma, readings,
witnesses, editors, verbatim, anchors, IDREF integrity, RNG validity.
Wrong structure fails; honest refusal (verbatim note / unanchored) is a
reported gap, never a failure.

**Results:**

- **Bellum Alexandrinum** (LDLT, ed. Damon et al., CC BY-SA 4.0; Latin,
  witness families M U S T V + ϛ + Greek-letter hyparchetypes, ~65 named
  editors): 524 entries — **0 errors, 0 gaps**.
- **SBLGNT** (Holmes 2010, TEI re-encoding, CC BY 4.0; Greek, the whole
  NT, edition-sigla witnesses WH/Treg/NIV/RP/NA…): 6 906 entries —
  **0 errors, 0 gaps**.
- **Problemata XIX** (LDLT, ed. Mutch; medieval Latin, ~30 witnesses in
  stemma families): open frontier — its superscript witness sigla
  (Eᵃ/Pˣ/Vᵐ) are flattened to bare letters by the ADAPTER (three distinct
  P-states become indistinguishable), so the golden itself degrades before
  diorthosis runs. v0.3 work: superscript-aware siglum rendering.

**What the campaign forced into existence** (every one driven by a real
failure against scholar data):

- **Latin editions end to end**: `--text-lang la` (regreek labels a Latin
  main band "translation" and its foot "notes"); marker detection was
  GREEK-ONLY (`arcessit1` was invisible) — `_TEXT_LETTER` now spans Greek
  and Latin script; em/en dashes as marker boundaries; `}` in the glue
  class.
- **Sigla of the wild**: Greek-letter sigla (π ω μ ν), archaic ϛ (the
  editiones-ueteres consensus), starred states (M*), compound and
  solid-initial editors (Gaertner-Hausburg, DSimons), accented names
  (Kübler, Wölfflin) — conspectus declaration, xml:id minting (injective
  hex-escaping; libxml2 still validates NCNames against XML 1.0 4th-ed
  tables, which lack ϛ) and attribution peeling all extended.
- **Entry splitting generalized**: one-entry-per-line bands (SC/TeX
  convention) split on former line starts; entries may open with an
  editorial bracket (`<Ab> incendio`); hyphenation inside the band
  ("An- drieu") rejoined before parsing.
- **Grammar honesty at the edges**: a discourse word or bare numeral
  adjacent to plain text is the READING'S TEXT, not attribution
  ("regnum et", "cohortibus XXX", a lemma that IS the numeral V);
  plain-prose parentheticals ("(uel ex)", "(sc. Alexandrini)", slash
  alternatives "(t/c)") stay verbatim in the text while technical ones
  (digits, "= …", leading connector, placement bigrams, editors) remain
  commentary; ';' between loci no longer stops reference peeling.
- **regreek layer separation hardened** (v0.6.0): fragments of one
  physical line re-joined in x-order (superscripts made pdfminer split
  justified lines and the y-sort displaced them), wide gaps preserved as
  double spaces (the entry-boundary idiom); the main/foot split takes the
  LAST size-drop candidate (an early heading gap no longer preempts the
  real boundary) with the reference register computed above the candidate
  (apparatus-dominant pages exist); a running head never ends a sentence
  (a one-line section end above the band was being eaten).
- **XML safety**: a degenerate ToUnicode can map missing glyphs to U+FFFF
  — TEI emission now replaces XML-invalid codepoints with U+FFFD, visibly.

Bobichon full-book after all of the above (no regression, slight parse
gain): 2 031 entries, anchoring 99.5 %, parse 98.9 %, lemma concordance
97.6 %, attribution 89.7 % (down 1.5 pt from v0.2.1: readings whose only
"attribution" was a misfiled trailing numeral or discourse word no longer
count — the previous figure was inflated), byte-identical two-process
build, md-ce validate clean, tei_all.rng valid.
