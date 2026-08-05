#!/bin/sh
# Rebuild the nine-edition generalization corpus of docs/generalization.md.
#
# Until 1.0 the flagship v0.7 table was IRREPRODUCIBLE: tools/golden/generalize.py
# names nine PDFs by hardcoded /tmp path and no URL, so nobody outside the
# reviewer's laptop could re-derive a single row. This script recovers the
# provenance. Every file below is fetched from its publisher, checked against a
# SHA-256 recorded on 2026-08-05, and written where generalize.py expects it.
#
# diorthosis ships no edition content: this is fetch-at-use, exactly like
# fetch_sources.sh. What each publisher grants is recorded next to the URL.
#
#   insolubles  Walter Segrave, Insolubles, ed. B. Bartocci & S. Read,
#               Open Book Publishers 2024, doi:10.11647/obp.0359    CC BY-NC 4.0
#   britannico  F. Rossetti, Il commento a Persio di Giovanni Britannico,
#               thesis 2017, HAL tel-01706755         HAL open deposit (author)
#   derivas     J. de Rivas, Hérodien, livres I-II, thesis 2022,
#               HAL tel-04929819                      HAL open deposit (author)
#   iacopone    A. Giraudo, Il laudario di Iacopone da Todi, thesis 2020,
#               HAL tel-02905402                      HAL open deposit (author)
#   blacasset   B. Francioni, Il trovatore Blacasset, Ledizioni 2024
#               (Biblioteca di Carte Romanze 19), doi:10.5281/zenodo.11658375
#                                                 CC BY 4.0 (Zenodo deposit)
#   pigna       G. B. Pigna, Gli Heroici, ed. M. De Masi & S. Jossa,
#               BIT&S 2025, ISBN 979-12-80391-44-5           CC BY-NC-ND 3.0 IT
#   saivism     P. C. Bisschop, Universal Śaivism, Brill 2018 (Gonda
#               Indological Studies 18), doi:10.1163/9789004384361      CC BY-NC
#               *** SUBSTITUTE COPY — read the note printed at the end ***
#   susruta     D. Wujastyk et al., On the Plastic Surgery of the Ears and
#               Nose, HASP 2023, doi:10.11588/hasp.1203            CC BY-SA 4.0
#   gracilis    Petrus Gracilis, b1q1 (SCTA, ed. Witt & Slotemaker),
#               CC BY-NC-SA 4.0 — NOT a published PDF: built locally, see
#               --with-gracilis below.
#
# To re-pin: fetch the file, review what changed at the publisher, replace the
# checksum, and update the date in this comment. Never silence a mismatch.
#
# Usage:
#   sh tools/golden/fetch_generalization_corpus.sh
#   sh tools/golden/fetch_generalization_corpus.sh --dest /tmp/gen10
#   sh tools/golden/fetch_generalization_corpus.sh --with-gracilis
set -e

DEST=/tmp/gen10                      # generalize.py's hardcoded location
GRACILIS_DEST=/tmp/gracilis_generalization
WITH_GRACILIS=no

# The Gracilis PDF is not published: it is typeset from the SCTA TEI by the
# LombardPress toolchain plaoul_build_pdf.py already pins. The TEI commit below
# is the one whose bytes produced the measured PDF (checked, not guessed).
GRACILIS_TEI_COMMIT=f4f168e349506c7eabf0ea80abb7e994ae13f8fb
GRACILIS_TEI_SHA=1db9209ea7b033c850722ea300a2264a2b3ddf29e0ce3dd19ab55845ee526cb9
GRACILIS_PDF_SHA=c0f87ef21676d7b42b75eeb8105ce7bb60801c69606f7bc4d16d2b9ff1d5c536

# Two publishers disagree about who curl is, so the agent is per source and
# both reasons are stated rather than hidden:
#   - Open Book Publishers answers curl's default agent with 202 and an EMPTY
#     body, a "download" that silently produces nothing. It needs a browser.
#   - HAL sits behind an anti-bot interstitial that challenges browser agents
#     and serves a 12 kB "Making sure you're not a bot!" page instead of the
#     thesis. It needs curl to say it is curl.
# Anything not marked `browser` below is fetched as plain curl.
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

usage() {
  # the whole leading comment block, however long it grows
  awk 'NR == 1 { next } /^#/ { print; next } { exit }' "$0"
  echo
  echo "  --dest DIR          where the eight PDFs land (default $DEST)"
  echo "  --gracilis-dest DIR where the ninth is built (default $GRACILIS_DEST)"
  echo "  --with-gracilis     also build the ninth edition (needs tectonic,"
  echo "                      saxonche and git; several minutes)"
  echo "  --help              this text"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dest) DEST=$2; shift 2 ;;
    --gracilis-dest) GRACILIS_DEST=$2; shift 2 ;;
    --with-gracilis) WITH_GRACILIS=yes; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1 (try --help)" >&2; exit 2 ;;
  esac
done

if command -v shasum >/dev/null 2>&1; then
  sha256() { shasum -a 256 "$1" | awk '{print $1}'; }
elif command -v sha256sum >/dev/null 2>&1; then
  sha256() { sha256sum "$1" | awk '{print $1}'; }
else
  echo "ERROR: neither shasum nor sha256sum is available." >&2
  exit 2
fi

mkdir -p "$DEST"
failed=0

# fetch NAME URL EXPECTED-SHA256 [browser]
fetch() {
  name=$1; url=$2; want=$3
  if [ "${4:-}" = browser ]; then set -- -A "$UA"; else set --; fi
  out="$DEST/$name"
  if [ -f "$out" ] && [ "$(sha256 "$out")" = "$want" ]; then
    echo "ok        $name (already present, checksum matches)"
    return 0
  fi
  printf 'fetching  %s ... ' "$name"
  if ! curl -fsSL "$@" -o "$out.part" "$url"; then
    echo "FAILED"
    echo "  the publisher did not serve $url" >&2
    failed=$((failed + 1))
    rm -f "$out.part"
    return 0
  fi
  got=$(sha256 "$out.part")
  if [ "$got" != "$want" ]; then
    echo "CHECKSUM MISMATCH"
    echo "  $url" >&2
    echo "  expected $want" >&2
    echo "  got      $got" >&2
    echo "  The publisher's file changed, or the download is truncated. Review" >&2
    echo "  the difference and re-pin deliberately; do NOT measure with it." >&2
    mv "$out.part" "$out.rejected"
    failed=$((failed + 1))
    return 0
  fi
  mv "$out.part" "$out"
  echo "ok ($got)"
}

fetch insolubles.pdf \
  https://books.openbookpublishers.com/10.11647/obp.0359.pdf \
  ca331c491e511fa28aab35216665bfed6454b24816af00f05072d7b636716b29 browser

fetch britannico.pdf \
  https://theses.hal.science/tel-01706755/document \
  096a4d994a6a9f05eab72c9e9ef304421dec918d4152b9f8e81f7ac32e2b5a5b

fetch derivas.pdf \
  https://theses.hal.science/tel-04929819/document \
  8bf36a3618d2bd53ab5beca070022847f3548a5a97f1d0cd264f56584e322499

fetch iacopone.pdf \
  https://theses.hal.science/tel-02905402/document \
  dd59c4991a90373c985002bb17e1140fb93bba65e055dc09ab1f1edb34988ca3

fetch blacasset.pdf \
  https://zenodo.org/api/records/11658375/files/Il_trovatore_Blacasset_web.pdf/content \
  93ada3b05918bbfc974f068a56c6e2ff879fda62632f1994743906306a1b700f

fetch pigna.pdf \
  https://bitesonline.it/wp-content/uploads/2025/03/Pigna-Gli-Heroici_web_2025-02-04.pdf \
  a3764856dd1ba2936d0dcb477d3119190b3822e541ecc18d9a24fe0cae816337

fetch susruta.pdf \
  https://hasp.ub.uni-heidelberg.de/catalog/download/1203/2074/105296 \
  34afb9846d8fcfe7438501793df2ccfbffc1e6f000135a65feb695266d509c30

# SUBSTITUTE. The measured file was a direct Brill.com download; Brill stamps
# the download date into every page footer, so those exact bytes cannot be
# fetched again by anyone. OAPEN hosts the same open-access book with a fixed
# stamp, and re-measuring the row against it reproduces every published figure
# except the apparatus character count (153,294 -> 153,622: 82 pages x the 4
# characters by which the stamp is formatted differently).
# If the irreplaceable measured copy is already here, it is LEFT ALONE.
MEASURED_SAIVISM_SHA=45501a52f2e7042ab085587195a44970f108a27405e47401e07a7539971a4829
if [ -f "$DEST/saivism.pdf" ] \
   && [ "$(sha256 "$DEST/saivism.pdf")" = "$MEASURED_SAIVISM_SHA" ]; then
  echo "keep      saivism.pdf (the measured Brill.com copy — not replaceable, left untouched)"
else
  fetch saivism.pdf \
    https://library.oapen.org/rest/bitstreams/624caef6-f13a-4f08-b6b0-d32483e262ca/retrieve \
    24d89e30b7893315557e2040005427237e555b03cefd7b1d6d6e24a372821ad4
fi

if [ "$WITH_GRACILIS" = yes ]; then
  echo
  echo "building  gracilis (LombardPress toolchain; needs tectonic, saxonche, git)"
  for binary in tectonic git curl; do
    command -v "$binary" >/dev/null 2>&1 || {
      echo "ERROR: $binary is not on PATH; the ninth edition cannot be built." >&2
      exit 2
    }
  done
  python3 -c 'import saxonche' 2>/dev/null || {
    echo 'ERROR: saxonche is not importable (pip install ".[golden]").' >&2
    exit 2
  }
  mkdir -p "$GRACILIS_DEST"
  here=$(cd "$(dirname "$0")" && pwd)
  PYTHONPATH="$here/../..:${PYTHONPATH:-}" python3 - "$GRACILIS_DEST" "$GRACILIS_TEI_COMMIT" <<'PY'
import sys
from tools.golden import plaoul_build_pdf as p

dest, commit = sys.argv[1], sys.argv[2]
p.TEI_RAW = ("https://raw.githubusercontent.com/scta-texts/graciliscommentary/"
             f"{commit}/pg-b1q{{n}}/pg-b1q{{n}}.xml")
sys.argv = ["plaoul_build_pdf.py", dest, "1"]
raise SystemExit(p.main())
PY
  got_tei=$(sha256 "$GRACILIS_DEST/lectio1.xml")
  got_pdf=$(sha256 "$GRACILIS_DEST/lectio1.pdf")
  [ "$got_tei" = "$GRACILIS_TEI_SHA" ] \
    && echo "ok        gracilis TEI ($got_tei)" \
    || { echo "MISMATCH  gracilis TEI: expected $GRACILIS_TEI_SHA, got $got_tei" >&2
         failed=$((failed + 1)); }
  if [ "$got_pdf" = "$GRACILIS_PDF_SHA" ]; then
    echo "ok        gracilis PDF ($got_pdf)"
  else
    echo "NOTE      gracilis PDF differs from the measured build:" >&2
    echo "            expected $GRACILIS_PDF_SHA" >&2
    echo "            got      $got_pdf" >&2
    echo "          The build is deterministic for a given tectonic; a different" >&2
    echo "          TeX toolchain legitimately produces different bytes. Re-derive" >&2
    echo "          the row rather than assuming the table still holds." >&2
  fi
fi

echo
echo "corpus in $DEST"
ls -la "$DEST"
cat <<'NOTE'

Two rows of docs/generalization.md are not plain downloads, and the document
says so:

  saivism   REVIEWER-LOCAL BYTES. The measured PDF was a Brill.com download
            whose per-download date stamp makes it unique to that download.
            The OAPEN copy fetched above is the same open-access book and
            reproduces the row's published figures; only the diagnostic
            apparatus-character count moves, 153,294 -> 153,622.

  gracilis  NOT PUBLISHED as a PDF at all. It is typeset locally from the SCTA
            TEI by the project's own LombardPress toolchain; pass
            --with-gracilis to build it (tectonic, saxonche, git, network).

Everything else is byte-identical to what was measured. Then:

  python3 tools/golden/generalize.py
NOTE

if [ "$failed" -gt 0 ]; then
  echo
  echo "$failed source(s) did not arrive intact — the corpus is INCOMPLETE." >&2
  exit 1
fi
