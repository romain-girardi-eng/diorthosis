#!/bin/sh
# Fetch the scholar-encoded TEI editions the golden harness runs against.
# The data lands in tools/golden/data/ (gitignored): diorthosis ships no
# edition content — the golden corpus is reproducible from these URLs.
# Remote GitHub sources are pinned below to commits resolved via the GitHub API
# on 2026-08-04. The mutable TEI schema URL is pinned by its SHA-256 checksum.
# To re-pin, review the upstream diff, replace the relevant commit/checksum, and
# update the date in this comment; never advance a branch name implicitly.
#
#   Bellum Alexandrinum  — LDLT, ed. Damon et al.   CC BY-SA 4.0
#   SBLGNT               — TEI re-encoding (PTA org) of Holmes 2010, CC BY 4.0
#   Problemata           — LDLT, ed. Mutch          CC BY-SA 4.0
set -e
cd "$(dirname "$0")"
mkdir -p data
curl -fsSL -o data/balex.xml \
  https://raw.githubusercontent.com/Library-of-Digital-Latin-Texts/balex/0e6ee82976a6ffeff41b5515594826719bfdfb0f/ldlt-balex.xml
curl -fsSL -o data/sblgnt.xml \
  https://raw.githubusercontent.com/PatristicTextArchive/sblgnt-tei/bc827c34d0cad904b740f32c475b3349049e048e/xml/sblgnt_tei.xml
curl -fsSL -o data/problemata.xml \
  https://raw.githubusercontent.com/DigitalLatin/Problemata/fc6efb31108a5373a0869c71be280bc1e3867dd4/edition.xml
# TEI-all RELAX NG schema (validation target for the emitted TEI)
curl -fsSL -o tei_all.rng \
  https://tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng
tei_all_sha256=b0f115095ead2ccc6933aa3365c6f4a82cba3b2ec7eee7f76bb616d7a63b7e48
actual_sha256=$(shasum -a 256 tei_all.rng | awk '{print $1}')
if [ "$actual_sha256" != "$tei_all_sha256" ]; then
  echo "ERROR: tei_all.rng SHA-256 mismatch: expected $tei_all_sha256, got $actual_sha256." >&2
  echo "Review the upstream diff and re-pin the checksum before using this schema." >&2
  exit 1
fi
ls -la data/
