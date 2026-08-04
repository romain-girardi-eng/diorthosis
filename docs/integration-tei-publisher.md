# Using diorthosis output with TEI Publisher and EVT 2

This guide describes the TEI that `diorthosis` currently emits and a cautious
integration path for two downstream viewers. It distinguishes documented viewer
features from behavior that has not been exercised against a running instance.
The canonical artifact should remain the original diorthosis TEI; viewer-specific
transformations should be generated derivatives.

## The emitted TEI contract

`src/diorthosis/tei.py` implements TEI P5 double-end-point attachment and emits
the required declaration whenever at least one parsed apparatus entry exists:

```xml
<encodingDesc>
  <variantEncoding method="double-end-point" location="internal"/>
</encodingDesc>
```

The constituted text is stored in `div[@type='edition']/ab`. Printed apparatus
markers become internal anchors. A confidently located lemma has both endpoints;
if its start cannot be located without guessing, only `@to` is emitted:

```xml
<ab>... <anchor xml:id="a-p1-e0-start"/>λόγος<anchor xml:id="a-p1-e0" n="1"/> ...</ab>
<app n="1" from="#a-p1-e0-start" to="#a-p1-e0">
  <lem wit="#wit-A">λόγος</lem>
  <rdg wit="#wit-B" source="#ed-Otto">θεός</rdg>
  <note type="verbatim">λόγος A : θεός B Otto</note>
</app>
```

The exact element order and attributes depend on the source. The stable points
for integration are:

- `listWit/witness/@xml:id` declares every pointer in `lem/@wit` and
  `rdg/@wit`; `witness/abbr[@type='siglum']` holds the display siglum.
- `listBibl/bibl/@xml:id` declares editorial sources referenced by `@source`.
  These are editors responsible for a reported reading, not manuscript
  witnesses.
- An omission is an empty `rdg`; uncertainty may be `@cert="low"`; placement
  information may occur in `witDetail`.
- `note[@type='verbatim']` is evidence, not display normalization: its whitespace
  and line breaks must not be rewritten by a viewer transformation.
- A refused or unparsed entry is `note[@type='apparatus']`, optionally with a
  `@target` to its printed marker. It must not be converted into a fabricated
  `app`.

Validate the artifact before viewer work:

```sh
diorthosis validate edition.md
diorthosis roundtrip edition.md edition.tei.xml
```

## Compatibility summary

| diorthosis feature | TEI Publisher | EVT 2 |
|---|---|---|
| Upload/store valid TEI and render ordinary text | Documented core workflow | Documented from `data/text` via `dataUrl` |
| Page breaks and generic TEI elements | Base ODD or a small display rule may suffice | Generic fallback and project CSS may suffice |
| Double-end-point `app/@from` and `app/@to` | Requires project rules for span lookup and interaction | Not the documented EVT 2 critical-apparatus model |
| Parallel-segmentation apparatus | Possible with an ODD, but unnecessary for storage | Documented critical-edition input model |
| `listWit` and space-separated `@wit` pointers | Resolve in a custom model/template | Witness lists and filters are documented for EVT's supported model |
| `@source` editor pointers | Custom rendering required | Display behavior not established by the consulted guide |
| Verbatim/refused notes | Render as ordinary or styled notes | Generic rendering is possible; a critical-apparatus role is not documented |

“May suffice” is intentional: it describes an encoding path, not a successful
test with the versions deployed by a particular project.

## TEI Publisher

TEI Publisher stores TEI in eXist-db and uses a TEI Processing Model expressed
in ODD. Its documentation recommends a project ODD derived from
`teipublisher.odd`, ordering specific models before generic fallbacks, and
regenerating the processing model after manual ODD changes. Uploading the file
therefore does not by itself create an interactive critical apparatus.

Start by uploading an unchanged diorthosis TEI, creating a custom ODD, and
checking the edition text and page boundaries. The following illustrative
fragment provides a readable fallback for anchors and apparatus entries. Insert
the `elementSpec` children into the schema specification of the project's ODD;
do not treat it as a complete ODD file.

```xml
<elementSpec mode="change" ident="anchor">
  <model predicate="@n" behaviour="inline" cssClass="app-anchor">
    <param name="content" value="@n"/>
    <outputRendition>
      vertical-align: super; font-size: 0.75em;
    </outputRendition>
  </model>
  <model behaviour="inline"/>
</elementSpec>

<elementSpec mode="change" ident="app">
  <model behaviour="block" cssClass="apparatus-entry">
    <outputRendition>
      display: block; margin-block: 0.4rem;
    </outputRendition>
  </model>
</elementSpec>

<elementSpec mode="change" ident="lem">
  <model behaviour="inline" cssClass="lemma">
    <outputRendition>font-weight: bold;</outputRendition>
  </model>
</elementSpec>

<elementSpec mode="change" ident="rdg">
  <model behaviour="inline" cssClass="reading"/>
</elementSpec>
```

This fallback exposes document-order content. It does **not** highlight the
span between `@from` and `@to`, dereference `@wit` or `@source`, or create a
popup. For that behavior, add a project template/XQuery component that:

1. indexes each `app` by its `@from` and `@to` identifiers;
2. resolves identifiers against the full document root (important when the
   processing model receives a paginated or virtual document);
3. tokenizes space-separated `@wit` and `@source` values and resolves every
   pointer to `listWit` or `listBibl`;
4. treats a missing `@from` as an explicitly end-only link;
5. exposes `note[@type='verbatim']` as a diplomatic evidence view without
   normalizing its text.

The official FAQ's pattern for resolving a node outside the current fragment is
`id(substring-after(@target, '#'), root($parameters?root))`. Adapt that pattern
to each token rather than assuming that XPath `id()` is operating on the full
document.

References: [TEI Publisher ODD documentation](https://faq.teipublisher.com/odd/),
[accessing an arbitrary node from an ODD](https://faq.teipublisher.com/odd/accessarbitrarynode/),
and [diagnosing an unapplied model](https://faq.teipublisher.com/odd/modelnotapplied/).

## EVT 2

The EVT 2 user guide documents critical editions encoded with the TEI parallel-
segmentation method. Its apparatus, witness filters, reading selection, and
collation views should therefore not be assumed to understand an unchanged
double-end-point diorthosis file. EVT also has a generic TEI-to-HTML fallback
that can be styled in `config-style.css`, but generic rendering is not the same
as relational apparatus support.

For a basic smoke test, copy the XML into EVT's `data/text` directory and set
`dataUrl` in `config.json` to that file. This can establish whether the text and
generic elements load. It cannot establish that the critical-apparatus UI has
resolved endpoints correctly.

For EVT's documented critical-edition features, generate a derivative TEI by
transforming suitable double-end-point entries into parallel segmentation:

```xml
<p>... <app n="1">
  <lem wit="#wit-A">λόγος</lem>
  <rdg wit="#wit-B" source="#ed-Otto">θεός</rdg>
  <note type="verbatim">λόγος A : θεός B Otto</note>
</app> ...</p>
```

Change the derivative's declaration to
`<variantEncoding method="parallel-segmentation" location="internal"/>`.
Only inline an entry when both endpoints exist and the selected spans can be
represented without overlap. End-only entries, crossing spans, ambiguous text
matches, and refused notes require an explicit project policy or human review;
do not guess a start position to make EVT accept the file. Retain `listWit`,
`@wit`, `listBibl`, `@source`, and the verbatim note in the derivative, then
configure EVT's witness list against `listWit` and test each displayed siglum.

Reference: the EVT 2
[English user guide](https://github.com/evt-project/evt-viewer/blob/master/USER_README_EN.md).

## The `md-ce` alternative

If a downstream application is not TEI-aware, use the generated `md-ce/0.2`
view instead of flattening the TEI ad hoc. It preserves exact-line apparatus
slices, page folios, stable metadata, source ordering, rejection state, and
provenance, while intentionally omitting the full parsed `<app>/<lem>/<rdg>`
graph. It is well suited to search, retrieval-augmented generation, and review
interfaces; it is not a substitute for the citable TEI. Keep both files and run
`diorthosis roundtrip` so that page, text, and source-slice invariants remain
checked.

## To verify in running installations

The viewers were not installed or executed while preparing this guide. Before
publishing an integration claim, record the exact TEI Publisher and EVT 2
versions and verify:

- whether the current `teipublisher.odd` already assigns models to `app`,
  `lem`, `rdg`, `anchor`, `listWit`, `witDetail`, and `note[@type='verbatim']`;
- whether TEI Publisher preserves whitespace and line breaks in the verbatim
  note through HTML and API serialization;
- whether an end-only `app/@to` can be exposed accessibly in the chosen custom
  component;
- whether EVT 2 loads the unchanged double-end-point file, and whether it merely
  prints stand-off apparatus nodes or ignores them;
- whether EVT 2 displays `witness/abbr[@type='siglum']`, multiple `@wit`
  pointers, empty omission readings, `@cert`, `witDetail`, and editor
  `@source` pointers as intended after conversion;
- whether EVT 2 preserves `note[@type='verbatim']` byte-for-byte when its
  project build or export path rewrites XML; and
- whether the double-end-point-to-parallel transform rejects crossing,
  overlapping, missing-start, and unresolved-pointer cases rather than
  producing invalid or misleading TEI.
