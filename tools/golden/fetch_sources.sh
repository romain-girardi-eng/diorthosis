#!/bin/sh
# Fetch the scholar-encoded TEI editions the golden harness runs against.
# The data lands in tools/golden/data/ (gitignored): diorthosis ships no
# edition content — the golden corpus is reproducible from these URLs.
#
#   Bellum Alexandrinum  — LDLT, ed. Damon et al.   CC BY-SA 4.0
#   SBLGNT               — TEI re-encoding (PTA org) of Holmes 2010, CC BY 4.0
#   Problemata           — LDLT, ed. Mutch          CC BY-SA 4.0
set -e
cd "$(dirname "$0")"
mkdir -p data
curl -sL -o data/balex.xml \
  https://raw.githubusercontent.com/Library-of-Digital-Latin-Texts/balex/main/ldlt-balex.xml
curl -sL -o data/sblgnt.xml \
  https://raw.githubusercontent.com/PatristicTextArchive/sblgnt-tei/master/xml/sblgnt_tei.xml
curl -sL -o data/problemata.xml \
  https://raw.githubusercontent.com/DigitalLatin/Problemata/master/edition.xml
# TEI-all RELAX NG schema (validation target for the emitted TEI)
curl -sL -o tei_all.rng \
  https://tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng
ls -la data/
