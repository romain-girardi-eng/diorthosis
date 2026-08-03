
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
