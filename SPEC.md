# diorthosis output formats — normative specification

`diorthosis build` emits three files, and `diorthosis review` exports a fourth.
All four are specified here; nothing a consumer may rely on is left to the
source code.

| Part | Format | Written by | Versioned in the file |
|---|---|---|---|
| [1](#part-1--md-ce03--markdown-for-critical-editions) | `md-ce/0.3` — the retrieval view | `build` → `STEM.md` | yes, `md-ce/0.3` |
| [2](#part-2--the-tei-p5-shape) | TEI P5 — the citable artefact | `build` → `STEM.tei.xml` | no (TEI's own P5 versioning) |
| [3](#part-3--witnessesjson) | `witnesses.json` — the sigla actually used | `build` → `STEM.witnesses.json` | no |
| [4](#part-4--diorthosis-overrides1) | `diorthosis-overrides/1` — human review | `review` → `overrides.json` | yes, `diorthosis-overrides/1` |

What each of these promises across releases, and what a break to one would
require, is in [docs/stability.md](docs/stability.md). This file says what they
*are*.

---

# Part 1 — md-ce/0.3 — Markdown for Critical Editions

A md-ce file is a UTF-8, NFC-normalised, LF-terminated Markdown document. It is a
DERIVED, DELIBERATELY LOSSY VIEW of a TEI P5 file produced from the same document
model. **The TEI is the citable artefact; md-ce is the retrieval surface.**

This spec is executable: `diorthosis validate FILE.md` checks every invariant
below that is decidable from the file alone (I1-I7, I10-I12; I8/I9 concern the
relationship to the source and are enforced at emission). Exit 0 = clean,
exit 1 = violations, one line each.

**What 0.3 changed.** The meta line used to carry `anchored: a/b` counting the
view's own numeric markers, while the same invocation printed a different score
on the console and the TEI showed a third picture (an `<app>` with only its end
anchor counted as fully anchored). 0.3 replaces it with ONE `report` production,
rendered identically in the meta line, under every page header, and by the CLI,
splitting the entries on both axes that made the old number unreadable. A 0.2
file is not a 0.3 file: the validator rejects the version it does not check.

## Grammar (every production starts at column 0; SP = U+0020)

    file       = title LF LF meta 1*page
    title      = "# " text-run
    meta       = "<!-- md-ce/" ver " · diorthosis " semver " · ingest: " id
                 " · pages: " range " · coverage: " report
                 " · refusals: " tally
                 " · generative-blocks: " int " · escaped-lines: " int
                 " · tei: " filename " -->"
    page       = LF LF "## page " folio " (file index " int ")" page-stats
                 LF page-cov 1*block
    folio      = 1*(%x21-27 / %x2A-FF)          ; printed folio, or "–" if none printed
    page-stats = " [markers=" int " entries=" int " unresolved=" int "]"
    page-cov   = "<!-- md-ce page: " report " -->"
    report     = int " entries — " int " parsed, " int " refused, "
                 int " unparsed; " int " anchored (" int " attached, "
                 int " end-only), " int " unanchored"
    tally      = "none" / item *("; " item)
    item       = int "× " reason
    reason     = the refusing gate's own sentence, every run of digits replaced
                 by "n" so one key names one refusal CLASS; MUST NOT contain
                 ";" or "·", the field separators of the lines it lives on
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

`page-stats` keeps md-ce/0.2's three fields, in that order, so a consumer
matching it with an end-anchored regex keeps working; `unresolved` is the
report's `unanchored` and `entries` is its `entries`.

## Invariants (normative; each is mechanically checkable)

    I1  Line-start discipline. Every line matching /^(#{1,6} |<!-- md-ce)/ is
        structural. Emitters MUST escape such a line inside `body` by prefixing
        "\\" and MUST count it in meta `escaped-lines`. Consumers MAY therefore
        split on /^### / with no lookahead. A file where `escaped-lines` differs
        from the count of /^\\(#{1,6} |<!-- md-ce)/ lines in bodies is invalid.
    I2  No text/apparatus mixing. Splitting on /^### / yields sections whose layer
        is the first token of the header; no section contains another header.
    I3  Marker syntax and scope. Markers are page-scoped: ⟦folio:n⟧. For each
        apparatus entry marker ⟦f:n⟧ without "?", exactly one ⟦f:n⟧ occurs in a
        `text` or `heading` block of page f — a printed section title carries
        the constituted text and its markers with it. With "?", zero occur.
        Duplicate ⟦f:n⟧ inside one page is invalid. The correspondence is a
        BICONDITIONAL: a ⟦f:n⟧ standing in a text or heading block of page f
        with no resolved apparatus entry ⟦f:n⟧ on that page is equally invalid.
        A marker in the constituted text is a link, and a link to nothing is
        the dangling reference this format exists to prevent. Markers occur
        nowhere else: never in a `translation`, `notes` or `unclassified`
        block, and never on a second position of an apparatus entry line.
    I4  Delimiter purity. U+27E6/U+27E7 MUST NOT appear in body text except as
        `marker`. An emitter encountering them in source text MUST refuse (exit
        non-zero) rather than emit an ambiguous file.
    I5  Metadata parseability. Every `### ` line matches `metadata` exactly; keys
        appear in the fixed order source, generative, confidence, block; no key is
        omitted; `confidence` always has 2 decimals.
    I6  Addressability. (file index, block) is unique in the file, and determines
        the layer. `block` is the 0-based ordinal of the block within its page,
        counting furniture, so it is stable against md-ce's own filtering and
        matches the TEI block order. The FILE INDEX is the address, not the
        folio: I7 makes the index unique while deliberately permitting "–", the
        ABSENCE of a printed folio, to repeat, so (folio, block) is not unique in
        a document containing two folio-less pages — 46 of the 90 pages of the
        reference build of the DLL Bellum Alexandrinum print no folio, and
        ("–", 1) addresses 45 different sections there. Where a folio IS
        printed it is unique by I7, so (folio, block) then names the same
        section and remains the citable form of the address.
    I7  Page ordering. Pages appear in strictly increasing `file index` order, and
        each PRINTED folio appears at most once — "–" is the absence of a printed
        folio, not a folio, and may repeat. A build whose page selection is not
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
    I11 Honesty of coverage. ONE report, three renderings: `coverage:` in the meta
        line, `page-cov` under every page header, and the line the tool prints are
        the same `report` production, so one invocation can never announce two
        scores. Each report partitions its own entries twice — parsed + refused +
        unparsed = entries (what structure is claimed) and attached + end-only +
        unanchored = entries (how the entry reaches the text). `attached` is a
        complete double-end-point link (TEI @from AND @to); `end-only` carries @to
        alone because the lemma's start could not be located, and counting it as
        plainly "anchored" is the coverage claim this invariant forbids. Every
        refused entry is named in `tally`, whose counts sum to `refused`; "none"
        is legal only when `refused` is 0. The meta report is the sum of the page
        reports, and each page's `entries` equals the number of apparatus entry
        lines on that page. Since md-ce omits the parsed structure and every
        non-numeric anchor (I9), `parsed` and `attached` are not re-derivable from
        the bodies; the bodies BOUND them instead — a page's resolved ⟦f:n⟧
        entries never exceed its `anchored`, and its ⟦f:n?⟧ entries never exceed
        its `unanchored`.
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

---

# Part 2 — the TEI P5 shape

The TEI is the citable artefact and the only complete one: md-ce omits the
parsed structure, the conspectus and the page furniture by I9. This part
specifies the shape a consumer selects on. It follows TEI P5 ≥ 4.12 chapter 13
("Critical Apparatus") and is validated against `tei_all.rng` by the golden
harness.

    T1  Document skeleton. TEI/text/body carries div[@type='edition'], page by
        page in ingestion order, and — when the source has one — a single
        trailing div[@type='translation'] collecting the translation blocks of
        every page in the same order. No other div nesting is inferred: a
        printed section title becomes label[@type='section-title'], never
        <head>, because <head> is legal only in a div's opening sequence and
        guessing the division it opens would be an editorial claim.
    T2  Pages. Each ingested page opens with pb/@xml:id = "page-{file index}";
        @n carries the printed folio when the page prints one and is ABSENT
        otherwise. The file index, not the folio, is the identifier — same
        reason as md-ce I6.
    T3  Anchors and attachment. Apparatus links use the double-end-point-attached
        method with location="internal", declared once by
        variantEncoding[@method='double-end-point'][@location='internal'], which
        is present exactly when the document contains an <app>. For entry k of
        page p:
          - anchor/@xml:id = "a-p{p}-e{k}" is the END anchor, placed at the
            printed marker, and carries @n = the marker as printed;
          - anchor/@xml:id = "a-p{p}-e{k}-start" is the START anchor, present
            ONLY when the lemma's start was located confidently, and carries no
            @n;
          - app/@to names the end anchor, app/@from the start anchor.
        **app/@to without app/@from is an END-ONLY link**: the lemma's start
        could not be located, and the entry MUST NOT be read as a located span.
        This is the same distinction md-ce I11 reports as `end-only` versus
        `attached`, and conflating the two is the coverage lie both formats
        exist to prevent. Ids are minted per ENTRY, not per marker number,
        because printed marker numbers restart on each page and may repeat
        within one.
    T4  Parsed versus unparsed. A parsed entry is an <app> carrying <lem>, its
        <rdg>s, note[@type='comment'] for parenthesised commentary, and always
        note[@type='verbatim'] with the entry's byte-exact printed source slice
        — including its internal line breaks and whitespace. An entry no grammar
        structured is note[@type='apparatus'] holding the same byte-exact slice,
        with @n when it has a marker and @target = "#a-p{p}-e{k}" when it is
        anchored. An apparatus band that produced no entries at all is one
        note[@type='apparatus'] holding the whole band. Nothing is dropped in
        any of these cases.
    T5  Attribution. Manuscripts go to @wit as "#wit-{token}", editors to
        @source as "#ed-{token}" (13.1.2: @source "indicates the scholar
        responsible for asserting the existence of that reading"; @resp would
        claim the ENCODER's responsibility and is reserved for T7). An omission
        is an EMPTY <lem>/<rdg> (13.4); "ut vid."/"fort." set @cert="low"; a
        placement qualifier ("sup. l.", "in marg."…) becomes a witDetail/@wit
        sibling; cited versions and loci become note[@type='cited-source']
        inside the reading. Everything a grammar did not classify remains in the
        verbatim note.
    T6  The registry. Declared witnesses appear in sourceDesc/listWit as
        witness/@xml:id = "wit-{token}", each with abbr[@type='siglum'] carrying
        the siglum exactly as printed and the conspectus's own description as
        its tail; a witness STATE ("Mac") carries @corresp pointing at its
        declared base ("#wit-M"). Editors actually used appear in
        sourceDesc/listBibl as bibl/@xml:id = "ed-{token}" with an <abbr>
        carrying the printed token. {token} is escaped INJECTIVELY: ASCII
        alphanumerics pass through, every other character becomes "u{hex}", so
        ω is wit-u3c9 and M* cannot collide with M. Dereferencing @wit and
        @source depends on this escape, which is therefore part of the format.
    T7  Human review. An entry whose structure came from an overrides file
        carries @resp="#human-review" — on the <app> when the reviewer supplied
        a parse, on the note[@type='apparatus'] when the reviewer forced the
        entry verbatim. The document then declares titleStmt/respStmt/@xml:id =
        "human-review" stating what the marking means. A human correction is
        provenance, never silently merged into what the grammar read, and the
        verbatim source wording is untouched by an override.
    T8  Provenance. OCR-borne text carries @subtype="generative" on its <ab>,
        its unclassified <ab type="unclassified">, or its translation <p>,
        permanently. Page furniture is kept, not dropped:
        fw[@type='running-head'] and fw[@type='page-number']. A text block whose
        letters are more than half Greek carries @xml:lang="grc"; no other
        language is asserted.
    T9  Serialization. XML declaration; two-space indentation except inside
        mixed content, so an <ab> stays byte-verbatim; NFC-normalised;
        newline-terminated. Codepoints XML 1.0 forbids in content are replaced
        with U+FFFD — visibly, never silently. Byte-determinism is required of
        this file exactly as md-ce I12 requires it of the Markdown, and is
        enforced by the same two-process byte comparison.

---

# Part 3 — witnesses.json

`STEM.witnesses.json` answers one question: which sigla does the emitted
apparatus actually use, and what did the edition itself say they were.

    W1  Container. A JSON ARRAY, UTF-8, one-space indentation (json.dumps with
        indent=1), non-ASCII left unescaped, one object per siglum, sorted by
        siglum.
    W2  Scope. Exactly the sigla appearing in an emitted @wit — that is, drawn
        from the same resolved structures the TEI emits, never from the whole
        conspectus. A siglum the apparatus never used is not a witness of this
        build.
    W3  Row schema. Five keys, always all present, all values strings:

            {"siglum": "Mac", "base": "M", "hand": "ac",
             "hand_label": "before correction",
             "description": "The uncorrected reading in M. Equivalent to"}

        siglum       the token as printed in the apparatus;
        base         the DECLARED witness it is a state of, or the siglum
                     itself when it is not a compound or the base was never
                     declared — a base is never inferred;
        hand         the state suffix: "ac", "pc", "c", "mr", "*", or a digit;
                     "" when there is none;
        hand_label   the stable English expansion of `hand`; "" when there is
                     none;
        description  the conspectus siglorum's own words, or "" when the
                     edition declared nothing. An undeclared siglum is reported
                     with an empty description, never with a guessed one.

---

# Part 4 — diorthosis-overrides/1

The human-review file. A grammar gets an edition to 90-99 %; the last stretch
is a scholar's eye, and this format makes that review REPLAYABLE — and, more
importantly, makes a replay that no longer applies REFUSE.

    O1  Container. A JSON object with exactly two meaningful keys:

            {"format": "diorthosis-overrides/1", "entries": { … }}

        `format` is checked for EQUALITY. An unversioned file (the pre-1.0 flat
        object, which bound corrections by position alone) and a version from a
        newer diorthosis are both clean errors, never best-effort reads.
    O2  Keys. An entry key is "p{page.index}-e{k}": the 0-based file page, and k
        counting apparatus entries across the WHOLE page in document order —
        the sequence `entry_keys(page)` produces.
    O3  Content binding. Every record carries `source_sha`: the first 12 hex
        characters of SHA-256 over the entry's immutable source slice, with each
        CRLF, CR and LF replaced by one U+0020 (md-ce I8's sole declared
        apparatus transform — where the printed band happened to wrap is a
        typographic accident; the codepoints are the content). SHA-256 and not
        `hash()`: PYTHONHASHSEED must never decide whether a human correction
        replays.
    O4  Replay semantics. The key LOCATES a candidate entry; `source_sha`
        DECIDES whether that candidate is the entry the human corrected. A
        mismatch is never re-matched fuzzily and never skipped in silence: the
        whole replay refuses, itemised, naming each drifted key, the digest it
        was bound to, and what its entry now says. Application is ALL OR
        NOTHING — a two-pass implementation, so a drifted file leaves the
        document untouched rather than half-corrected. A key matching NO entry
        is a different severity: it loses a correction rather than fabricating
        one, and is reported as `unmatched` without failing the build.
    O5  Records.

            action     "parse" | "verbatim", and nothing else.
            lemma      required when action is "parse".
            lemma_wits, lemma_editors, lemma_qualifiers
                       arrays of strings, optional, default empty.
            readings   array of {text, wits, editors, qualifiers}, optional.
            comments   array of strings, optional.
            source_excerpt, note
                       provenance for the reviewer. They are carried into drift
                       reports so a human can see BOTH texts, and they NEVER
                       affect matching.

        "verbatim" forces the honest refusal: the entry is kept as
        note[@type='apparatus']. It is the correct action when a grammar
        mis-parsed narrative prose as a variant.
    O6  What an override may not touch. The verbatim source wording of an entry
        is never modified by an override, and every applied override is marked
        resp="#human-review" in the TEI (T7). An override changes what
        diorthosis CLAIMS about a printed entry; it can never change what the
        entry printed.
