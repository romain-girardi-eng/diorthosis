# Security

diorthosis is a command-line compiler for scholarly documents. It has no server,
no daemon, no listening socket, no database and no credential store, and it
never calls out to a network at run time. The realistic threat is therefore
narrow and worth stating plainly rather than dressing up.

## What it touches

diorthosis reads files a scholar downloaded from somewhere:

- **PDFs**, parsed with `pdfminer.six` (through `regreek`);
- **ALTO** and **PAGE-XML**, parsed with the standard library's
  `xml.etree.ElementTree`;
- **hOCR**, parsed with the standard library's `html.parser`;
- **`overrides.json`**, a review file produced by `diorthosis review`.

All four are untrusted input. A published edition is usually downloaded from a
repository the user did not build, and an OCR export usually comes out of a
pipeline the user did not write.

It writes files into the directory given with `-o`, and nothing else. It does
not execute anything from its input. The `tools/` harness *does* use the
network and *does* shell out to `git`, `curl` and `tectonic`, but that is
developer machinery, not the packaged tool: nothing under `src/diorthosis/`
opens a socket or spawns a process.

## XML posture, measured

The honest summary is that diorthosis inherits **expat's defaults through
`xml.etree.ElementTree`** and adds no XML hardening of its own. Measured on
2026-08-05 with CPython 3.13.5 / expat 2.7.1, on the adapters' own entry point
`diorthosis.ingest.errors.parse_xml`:

| Attack | Result |
|---|---|
| External general entity, `<!ENTITY x SYSTEM "file:///etc/passwd">` | **Not resolved.** The parser reports `undefined entity &x;` and the adapter refuses the file (exit 2). No file disclosure. |
| External DTD on an unreachable host | **Not fetched.** The document parses instantly; nothing dials out. |
| Entity amplification ("billion laughs"), deep nesting | **Refused** by expat's own guard: `limit on input amplification factor (from DTD and entities) breached`. |
| Entity amplification, small | **Expands.** A four-level bomb produced 30,000 characters from a 400-byte file: below expat's activation threshold, the guard does not fire. |

So: no XXE and no server-side request forgery through the XML path, and
bounded — but not zero — internal entity expansion. That bound is expat's, not
diorthosis's, and it moves when the interpreter's expat moves. If you feed
this tool XML from a source you do not trust *at all*, run it under a memory
limit; that is a cheaper and more honest control than a claim this project
would have to re-verify on every Python release.

`html.parser`, used for hOCR, resolves only the fixed set of HTML character
references and cannot be pointed at a file or a URL.

## Denial of service is in scope, exploitation is not

A malformed PDF or a pathological XML file can make diorthosis slow or make it
allocate a lot of memory. Nothing about that crosses a trust boundary — you ran
a command on your own file — so it is a bug worth fixing but not an emergency.

There is one class this project does treat as serious even though it is not a
memory-safety issue, because it is the failure the whole tool exists to
prevent: **input that causes diorthosis to emit invented structure, or to
present source markup as edition text**. A truncated hOCR file whose
`<span class=ocr_line` reaches the constituted text is that bug. Report it, and
it will be handled like the fabrications in the changelog: closed with a gate
and a regression test, not with a note in the documentation.

## Reporting

Open a **private security advisory** on GitHub:
<https://github.com/romain-girardi-eng/diorthosis/security/advisories/new>.
If that is not available to you, open a normal issue **without** the payload
and say a file is available on request.

Include the input file (or the smallest fragment that reproduces it), the exact
command, and the diorthosis version. Expect an acknowledgement within a week —
this is a single-maintainer research tool, not a vendor, and pretending
otherwise would be the first false claim in a repository built to avoid them.

Only the latest release is supported. Fixes ship in a new patch release; a
published tag is never moved.
