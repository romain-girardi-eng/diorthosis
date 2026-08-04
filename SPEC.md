# md-ce/0.2 — Markdown for Critical Editions

A md-ce file is a UTF-8, NFC-normalised, LF-terminated Markdown document. It is a
DERIVED, DELIBERATELY LOSSY VIEW of a TEI P5 file produced from the same document
model. **The TEI is the citable artefact; md-ce is the retrieval surface.**

This spec is executable: `diorthosis validate FILE.md` checks every invariant
below that is decidable from the file alone (I1-I7, I10-I12; I8/I9 concern the
relationship to the source and are enforced at emission). Exit 0 = clean,
exit 1 = violations, one line each.

## Grammar (every production starts at column 0; SP = U+0020)

    file       = title LF LF meta 1*page
    title      = "# " text-run
    meta       = "<!-- md-ce/" ver " · diorthosis " semver " · ingest: " id
                 " · pages: " range " · anchored: " int "/" int
                 " · generative-blocks: " int " · escaped-lines: " int
                 " · tei: " filename " -->"
    page       = LF LF "## page " folio " (file index " int ")" page-stats 1*block
    folio      = 1*(%x21-27 / %x2A-FF)          ; printed folio, or "–" if none printed
    page-stats = " [markers=" int " entries=" int " unresolved=" int "]"
    block      = LF LF "### " layer SP metadata [LF refs] LF LF body
    layer      = "text" / "apparatus" / "translation" / "notes" / "heading"
               / "unclassified"
    metadata   = "[source=" ("born_digital"/"ocr") SP "generative=" ("true"/"false")
                 SP "confidence=" DIGIT "." 2DIGIT SP "block=" int "]"
    refs       = "*refs: " ref *(", " ref) "*"  ; verbatim printed witness refs
    body       = *(line LF)                     ; ends at the next "### "/"## "/EOF
    marker     = "⟦" folio ":" int ["?"] "⟧"    ; "?" = anchor unresolved
    app-entry  = [marker SP] source-entry        ; apparatus body: ONE entry per line
    source-entry = exact source slice with each CRLF/LF/CR replaced by one SP

## Invariants (normative; each is mechanically checkable)

    I1  Line-start discipline. Every line matching /^(#{1,6} |<!-- md-ce)/ is
        structural. Emitters MUST escape such a line inside `body` by prefixing
        "\\" and MUST count it in meta `escaped-lines`. Consumers MAY therefore
        split on /^### / with no lookahead. A file where `escaped-lines` differs
        from the count of /^\\#{1,6} / lines in bodies is invalid.
    I2  No text/apparatus mixing. Splitting on /^### / yields sections whose layer
        is the first token of the header; no section contains another header.
    I3  Marker syntax and scope. Markers are page-scoped: ⟦folio:n⟧. For each
        apparatus entry marker ⟦f:n⟧ without "?", exactly one ⟦f:n⟧ occurs in a
        `text` block of page f. With "?", zero occur. Duplicate ⟦f:n⟧ inside one
        page is invalid.
    I4  Delimiter purity. U+27E6/U+27E7 MUST NOT appear in body text except as
        `marker`. An emitter encountering them in source text MUST refuse (exit
        non-zero) rather than emit an ambiguous file.
    I5  Metadata parseability. Every `### ` line matches `metadata` exactly; keys
        appear in the fixed order source, generative, confidence, block; no key is
        omitted; `confidence` always has 2 decimals.
    I6  Addressability. (folio, layer, block) is unique in the file. `block` is the
        0-based ordinal of the block within its page, counting furniture, so it is
        stable against md-ce's own filtering and matches the TEI block order.
    I7  Page ordering. Pages appear in strictly increasing `file index` order, and
        each folio appears at most once. A build whose page selection is not
        ascending MUST be normalised before emission, never emitted permuted.
    I8  Order preservation. Within a page, blocks appear in printed order; within
        an apparatus block, entries appear in printed order; nothing is merged,
        reordered, corrected or de-hyphenated. Because md-ce requires one entry
        per physical line, entry-internal source line breaks are the sole
        apparatus transform: each CRLF, LF or CR becomes one U+0020. The TEI
        note[@type='verbatim'] retains the exact line breaks and whitespace.
    I9  Declared lossiness. md-ce OMITS running heads, page numbers, the conspectus
        siglorum and the parsed lemma/reading structure. Those live in the TEI named
        by meta `tei:`. Omission of anything else is a defect.
    I10 Provenance. `generative=true` marks recognition-engine output. It is derived
        from the model, never from content; no body line can introduce or alter it
        (guaranteed by I1). meta `generative-blocks` equals the count of such headers.
    I11 Honesty of coverage. meta `anchored=a/b` equals the sum of per-page
        `entries − unresolved` over `entries`; the numbers are recomputable from the
        file itself, so an unverifiable coverage claim is impossible.
    I12 Determinism. Byte-identical input + version ⇒ byte-identical output. This is
        enforced by `tools/golden/double_build.py`, which runs the same build in two
        separate processes and byte-compares every output file so process-specific
        hash randomization cannot hide order dependence. `diorthosis validate` checks
        only I12's LF line endings, NFC normalization and trailing-newline subset.

## Round-trip guarantee

md-ce and TEI P5 are projections of the same internal document model. For every
build, `diorthosis roundtrip EDITION.md EDITION.tei.xml` mechanically verifies
that both outputs carry the same projected content. Exit 0 means:

- the same page folios occur in the same order;
- each page has the same normalised text after md-ce markers and TEI anchors are
  removed;
- each page has the same source-slice apparatus entries, including rejected
  entries, with the same multiplicities after md-ce's declared line unwrapping;
  and
- each page has the same normalised `translation` and `notes` layers.

## Chunking contract for retrieval

    C1  A chunk is one `### ` section. Chunkers MUST NOT split on blank lines: body
        blank lines separate PRINTED LINES, not paragraphs.
    C2  A chunk MUST carry its `## page` header and its `metadata` as chunk
        metadata. A `text` chunk and an `apparatus` chunk never merge.
    C3  Generative chunks (generative=true) MUST be surfaced as recognition output
        wherever quoted; they are not verbatim edition text.
    C4  A marker with "?" MUST NOT be resolved by search. Cross-page resolution of
        any marker is forbidden — markers are page-scoped by I3.
