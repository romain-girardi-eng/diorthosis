
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


## 15. Real-PDF ground truth — the printed page, as printed (2026-08-04)

§14's harness typeset the scholars' apparatus into OUR layout; Romain's
objection was exact: the real-world failures come from the printed layout
itself. Both §14 corpora exist as REAL printed PDFs of the same critical
text: the DLL's own born-digital `ldlt-balex.pdf` (reledmac: marginal line
numbers, ∥-separated entries, |-separated readings, glued sigla MUSTV,
one-line printer's footer on every page) and the official SBLGNT PDFs
(sblgnt.com: verse-referenced band, in-text anchor sigla ⸀⸂⸃, bold lemma
re-set in roman, "]" separator, • between entries).

`tools/golden/real_check.py` aligns diorthosis' reading of the REAL page
against the scholars' TEI by CONTENT (windowed in-order alignment; folded;
elliptical span lemmas "Βόες … Βόες" and glued bold-lemma doublets "δεδε"
handled as key variants):

| | text coverage | band coverage | contamination | false structures |
|---|---|---|---|---|
| balex-dll (88 pp.) | 93.0 % | 95.9 % | **0** | **0** |
| SBLGNT Matthew (66 pp.) | 97.0 % | **100.0 %** | 3 (word-order variants recurring near their locus — measurement noise) | **0** |

The honesty contract HOLDS on real layouts: both conventions are foreign
to P1's numeric-marker grammar, and not one wrong `<app>` was emitted —
everything stays verbatim `<note type="apparatus">`. The apparatus band is
cleanly separated from the text (zero rejected readings leak into the TEXT
layer), which is the precondition for everything else.

One REAL layout defect was found and fixed (regreek 0.6.1): a one-line
printer's footer below the apparatus claimed the last-candidate cut and
left the WHOLE apparatus fused into the text (52 contaminated readings,
band coverage 0.9 %). The cut now prefers the last candidate with a
substantial foot (≥3 lines), falling back to a small one only when
nothing else fires. Baseline before/after: contamination 52 → 0, band
coverage 0.9 % → 95.9 %.

Also learned, at the harness level (measurement, not product): greedy
content alignment must be WINDOWED (one frequent function-word match far
ahead cascade-fails everything: 92.6 % → 2.3 %), and never given blind
drift on misses (phantom advance never resorbs: 95.9 % → 4.1 %).

**v0.4 frontier, now measurable:** parsing the two real conventions
(line-referenced reledmac entries; verse-referenced NT bands with lemma ]
readings), superscript witness sigla (Problemata), and the residual ~5 %
band alignment on balex (band head truncated on the first edition page).


## 16. v0.4 — the verse-referenced grammar, zero errors on the real SBLGNT (2026-08-04)

The first FOREIGN convention fully parsed, on the edition AS PRINTED. The
NT tradition's apparatus (``1:18 Ἰησοῦ WH NIV RP ] – Treg • …``) is now a
first-class grammar (`versegrammar.py`): entries split on ``•`` and verse
references (bare numbers after a completed attribution), ``LEMMA SIGLA ]
reading SIGLA ; reading SIGLA`` parsed with edition sigla (WH/Treg/NIV/RP…
— declared as witnesses, exactly as the convention's own TEI does), ``–``
= empty <rdg>, ``+ X`` kept verbatim; anchors resolve by (verse window ×
lemma), tolerant of the text's own typography (anchor sigla ⸀⸂⸃ between
lemma words, NBSP, punctuation), the constituted text arbitrating between
candidate forms of a noisy printed lemma. loc travels as <app n="C:V">.

**Result on the REAL printed PDF, verse_check.py strict (lemma, every
reading, witness sets, anchors, per verse) against the scholars' TEI:**

- **Matthew, whole book: 822/822 scholar apps — 0 ERRORS** (1 documented
  print/TEI divergence: at Mt 3:16 the printed band merges two readings
  the TEI separates — verified against the extracted band; 50 honest
  unanchored gaps).
- Whole NT: 6 793 apps beyond Matthew, 123 errors (98.2 % zero-error),
  taxonomy identified per class (residual spacing artifacts of overlaid
  runs, a handful of witness-set clusters pending band-by-band
  verification as print/TEI divergences). The loop continues; every class
  is measurable and reproducible via /tmp-driver + verse_check.

**The deep fix underneath (regreek 0.7.0):** the SBLGNT PDFs overlay every
bold lemma with a displaced copy; text-level merging doubled lemmas
('δὲδὲ') and leaked copies into neighbouring entries. Line construction
now merges fragments at GLYPH level — x-sorted, overlaid duplicates
dropped at 0.15× glyph size (a geminate λλ/δδ/'11' is a full advance
apart and survives; a loose 0.5× threshold once ate every double letter
of the book), spacing re-synthesized from geometry. Also: emitters'
grammar honesty extended (glued '+X', occurrence numerals '1ἄλλῳ', sigla
glued to Greek words 'ἡμέραWH', ';' as punctuation-variant vs
reading-separator disambiguated by attribution presence).

Cost, measured and accepted: Bobichon anchoring 99.5 → 99.3 % (3 anchors
shifted by re-synthesized spacing; concordance and parse stable; full
battery green otherwise). All other gates unchanged: retypeset goldens
524 + 6 906 at 0/0, real balex 95.9 % band / 0 contamination / 0 false
structures, determinism, md-ce validate, tei_all.rng (Bobichon AND the
SBLGNT output).


## 17. The loop to zero — the whole NT at 0 apparatus errors (2026-08-04)

Continuing §16's loop on the 123 residual NT errors, by the discipline the
night taught: PROBE GEOMETRY FIRST, never tune blind (a blind threshold
sweep moved 123 -> 123; every real gain below came from a measured probe).

**Final: 6 800 scholar apps across the whole NT (all 27 books, real
printed PDFs) — 0 ERRORS**, with 59 print/TEI divergences documented in
`sblgnt_known_divergences.json`, EACH verified against the extracted band
(the printed form present, the TEI form absent — or the printed
attribution read directly around the ']'), and 433 honest unanchored gaps.

What the loop found, in order:

- **In-band anchor sigla open the lemma, numbered beyond the second
  occurrence** ("⸀ἄλλῳ", "⸁ἄλλῳ", "⸀1ἄλλῳ" — and some ToUnicode tables
  render the siglum AS the digit): stripped inside lemma tokens, before
  doublet reduction ("⸀ἐν⸀ἐν" -> "ἐν").
- **"em(endavit)"** qualifies the following editor ("+ καὶ τοῦ ἀδελφοῦ em
  Holmes") — peeled with the siglum.
- **"〚WH〛" is the spuria siglum** (WH's double-bracketed passages):
  normalized to WHspur; and a bare "] 〚WH〛" with no dash is the SPURIA
  MARK, transferred to the lemma's witnesses (Lk 24:6 family), never an
  omission.
- **Elliptical lemmas chain N parts and take the SHORTEST span** (two
  ellipses in Mk 4:8 "ἐν … καὶ ἓν … καὶ ἓν"; a repeated opening phrase in
  Lk 6:42 made the naive span leap over intervening text).
- **The divergence oracle**: a claimed error is a PRINT/TEI DIVERGENCE
  precisely when the extracted band contains our reading and not the
  TEI's (21 reading-level errata of the 2010 print: μωυσησ/μωσησ,
  τεσσεράκοντα/τεσσαράκοντα, ηλθαν/ηλθον…), or when the sigla printed
  around the "]" side with us (21 attribution corrections of the TEI
  re-encoding); plus the structural family: verse-bracketing entries the
  TEI does not encode as <app> (Western non-interpolations, Lk 24), and
  rdg additions marked resp="#JJM" (encoder refinements, up to the whole
  Pericope Adulterae embedded in one TEI rdg at Jn 7:52).

Every other gate stays green: Matthew 822 = 0 errors; retypeset goldens
524 + 6 906 = 0/0; real balex 95.9 % band / 0 contamination / 0 false
structures; Bobichon full battery; every emitted TEI valid against
tei_all.rng.

## 18. v0.5 — the line-referenced grammar (reledmac) and superscript sigla, to zero (2026-08-04)

Two new conventions, each driven to ZERO apparatus errors against a
scholar-encoded golden.

**Line-referenced (DLL Bellum Alexandrinum, reledmac).** The REAL
edition PDF (90 pages, 563 printed entries) parsed against the very TEI
it was typeset from: **563/563 compared, 0 errors, 0 anchoring gaps,
100 % anchored**, TEI valid against tei_all.rng, byte-deterministic
build, ONE documented divergence (72.2, where the golden itself encodes
a transposition narrative as italic <rdg> while encoding the identical
construction at 66.4 as a lemma-only note — we keep such narrative as
verbatim notes uniformly). The conventions the loop surfaced, all locked
in tests/test_linegrammar.py:

- entries split on ∥ with per-chapter line numbers, inherited when
  omitted; ranges span chapters ("14.24–15.2"); ◊ marks a crux;
- ∥ is OMITTED after a paren note, a dubitative "?" or a bare locus
  reference — the closing sign separates, the next entry opens with its
  line number ("…illius’) 11 ante A. Gabinium", "sed cf. 57.6 11 erat");
- glued sigla dissolve against the registry longest-first, ONLY on
  complete dissolution (MUSTcVac → M U S Tc Vac);
- the FIRST |-segment is the accepted text; a paren AFTER the
  attribution is a note, one BEFORE it belongs to the reading
  ("qui (sc. Alexandrini) Cellarius" vs "aptantur MUSTV (u. …)");
- citation tails (coll./u./cf./teste/uoce…), Latin relative clauses
  guarded by a preceding attribution token, "quam lacunam …",
  "an + gerundive", "nisi mauis + infinitive", ablative-absolute manner
  ("compendiis indicatis", "sensu repugnante") and transposition
  narrative are NOTES; "nisi mauis FORM (…) uel FORM (…)" and
  "an FORM?" are dubitative conjecture READINGS;
- witness-state vocabulary: "redit S" (a witness resumes), supra
  lineam, ex compendio, dubitanter, feliciter, auctore, ut uidetur;
- long lemmas close with a "]" terminator; "eius1" carries a
  superscript OCCURRENCE number; both are typography, not text;
- content-based anchoring resolves each lemma in the constituted text
  through hyphenation, em-dash line breaks, GLUED section numbers
  ("6Pugnabatur") and marginal line numbers caught mid-flow
  ("proficis- 10 ceretur"), degrading to a ≥5-char prefix when the tail
  hyphenates onto the next page — 563/563 anchored.

**Superscript sigla (Problemata golden, 5 524 apps).** The retypeset
golden prints two-letter sigla with a raised second letter (Nᵘ, Eᵃ, Pˣ)
in band and conspectus alike, plus Greek consensus letters (α β γ κ λ π)
and lowercase edition sigla (m, v): **0 apparatus errors, 47 honest
refusal gaps (0.85 %)**. What it taught:

- "alia", "recte", "male", "ego", "nos" as SINGLE tokens are ordinary
  Latin a reading can consist of — only the fixed editorial bigrams
  qualify ("alii alia", "non male", "fortasse recte");
- two discourse words in a row ("et sic") or a discourse word after a
  bare connector ("a. et") are running text, never attribution glue;
  re-dotting a bare token needs two letters (a lone "u" is a word);
- a repeated printer's/license footer is the mirror of a running head:
  cut it by cross-page repetition (≥3 pages, ≥25 chars, no apparatus
  separator) — geometry alone fails under a deep apparatus, and both
  the length and content guards are load-bearing (a wrapped "om. RP"
  repeats at many page feet);
- DEGENERATE pages (one line of text) starve the geometric layerer:
  the short text reads as a running head, the apparatus as the body —
  content reclassifies (a running head never carries multiple markers;
  an apparatus band opens "N … : "), and folio continuity recovers a
  page number glued to a band tail ("… Px 61").

Every gate green at release: real balex line 563 = 0/0; retypeset balex
524 = 0/0; retypeset SBLGNT 6 906 = 0/0; real NT 6 800 = 0 errors;
Problemata 5 524 = 0 errors; Bobichon full battery unchanged at
99.3 / 99.0 / 97.5 / 89.8 (2 031 entries).

## 19. v0.6 — the paragraphed-reledmac grammar and the double apparatus, to zero (2026-08-04)

Third real-backtesting case: Petrus Plaoul, *Commentary on the Sentences*
(ed. Jeffrey C. Witt, SCTA), lectio1-30 — **6,293 apparatus entries = 0
errors** against the scholars' TEI, on the PDF produced by the project's
own LombardPress/reledmac toolchain (`plaoul_build_pdf.py`,
byte-deterministic). This is the standard paragraphed reledmac foot
("N lemma] rdg SIG", juxtaposed, no separators) under a DOUBLE apparatus
(fontium tier above the variants), with crop marks, a diagonal DRAFT
watermark, folio marks and marginal line counters interleaved in the
glyph stream.

New module `paragraphgrammar.py`: entry boundaries are "NUM lemma]" hits
scanned WITHOUT consumption (fontium narrative must not swallow a genuine
boundary hiding inside its span), an elliptic lemma is guarded on its
pre-ellipsis head only, a single numeric token is a valid lemma; readings
split on witness-run ends; the LombardPress operator vocabulary (om.,
iterum, in textu, plus lectiones, add., add. sed del., interl., in marg.,
corr. ex) closes readings — only "plus lectiones" takes its list after
the operator; corr.-ex pre-correction text and post-witness facsimile
parens are notes. `--sigla R,V,S,SV` supplies the registry when the PDF
prints no conspectus.

What the print taught (all verified against the toolchain's XSLT and the
typeset page, none guessed):

- **The stylesheet is the rendering contract, warts included**: the
  template silencing `<note>` is COMMENTED OUT in the official
  critical.xslt, so English editorial notes leak into printed lemmas; the
  checker models the leak.
- **Elliptic printed lemmas match on the prefix only**: the printed
  suffix of a long lemma goes through typesetter transforms the TEI
  cannot model (a nested app's rdg folded into the last word, leaked
  notes); global-order alignment already pins the entry.
- **`@wit` tokens without `#` print verbatim** ("3V", "EV" — source-TEI
  typos become de-facto sigla on the page).
- **A duplicated siglum in one witness run is reading text** (Roman
  numerals collide with sigla): run-initial with nothing else on the
  reading ("I] V R SV S V") it is THIS reading's text; mid-run
  ("XIII] VIII R SV S V V") it opens the NEXT reading.

The loop also hardened regreek's layer separation (v0.7.2: corner-only
crop-mark test, gutter counters dropped, folio at the end of the line
list, true-band-edge requirement, widest-gap full split) — three
cross-corpus regressions caught by re-running every harness after each
change; see regreek's FINDINGS.

Every gate green at release: Plaoul 6,293 = 0 (anchored 94.9 %); real
balex line 563 = 0/0 at 100 % anchoring; retypeset balex 524 = 0/0;
retypeset SBLGNT 6,906 = 0/0; real NT 6,800 = 0; Problemata 5,524 = 0
errors / 47 honest gaps (stable since v0.5); real-PDF coverage balex
93.7 / 95.9 (zero contamination) and Matthew 97.0 / 100.0 (3 noise-level
contamination hits, stable since v0.4), zero false structures on both; Bobichon 2,031 entries at 99.3 / 99.0 / 97.5 / 89.8.
An end-to-end CLI build of lectio5 (`--text-lang la --sigla R,V,S,SV`)
emits 188 `<app>` (the scholar count), validates against tei_all.rng,
and passes `validate` and `roundtrip`.
