---
name: Bug report
about: A crash, a wrong exit code, a broken output file, or a tool that misbehaves
title: "[bug] "
labels: bug
---

<!--
For a wrong or missing APPARATUS STRUCTURE, use the other template instead —
that one asks for the printed band, which is what settles those.
-->

## Before anything else: which diorthosis ran?

This project has lost verification rounds to both halves of this trap — a
missing install (subprocesses die and the driver honestly reports *nothing
measured*) and a **stale editable install shadowing the working tree**.

```console
$ python3 -c "import diorthosis, sys; print(diorthosis.__file__, diorthosis.__version__)"
```

Output:

## The exact command

```console
$ diorthosis build EDITION.pdf --pages 30-60 --text-lang la -o out/
```

Exit code:

<!--
The four exit codes are a contract (docs/stability.md §1):
  0  success, and diorthosis certifies the result
  1  REFUSED — it ran, it does not certify what it produced
  2  user-actionable input error (bad flags, missing file, bad page spec)
  3  internal fault — a diorthosis defect
"I got exit 1" is usually not a bug: it is the tool declining to certify. Exit 3
on a valid input always is.
-->

## What happened

Paste the full console output, including the `coverage:` and `refusals:` lines
if the command got that far. If a traceback reached the terminal, paste all of
it — a library exception reaching the user is itself a defect.

## What you expected

## The input

Which edition (URL or DOI), or which OCR engine produced the ALTO/hOCR/PAGE
export. If the file is small and shareable, attach it; if it is a truncated or
corrupt export, say so — those are a supported input class, not an excuse.

## Environment

- diorthosis version and where it was imported from (above):
- Python version:
- Operating system:
- Installed from PyPI, or a checkout at commit:
