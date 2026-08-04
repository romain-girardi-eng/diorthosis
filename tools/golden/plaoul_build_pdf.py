#!/usr/bin/env python3
"""Build the OFFICIAL-toolchain PDF of a Petrus Plaoul lectio — the third
real-backtesting golden.

The Plaoul Commentary (ed. Jeffrey C. Witt, scta-texts/plaoulcommentary,
CC BY-NC-ND per repo readme — check before redistribution; the TEI is the
scholarly truth) carries ~6,300 <app> entries across lectio1-30, collated
against four witnesses (R V S SV). No published PDF exists, but the
project's own print toolchain does: lombardpress/lbp-print-xslt
(critical.xslt 1.0.0) -> reledmac LaTeX -> PDF. This script runs THAT
toolchain, unmodified except for three environment patches:

  1. the stylesheet hardcodes two absolute paths on the editor's machine
     (lombardpress-lists/workscited.xml — cloned from GitHub — and
     sourceTitleMaps/graciliscommentary.xml — never published anywhere,
     even the editor's own runs of OTHER texts would resolve titles
     against the wrong map; replaced by an empty map, which degrades the
     sources INDEX only, never the apparatus);
  2. ``\\usepackage{etex}`` is dropped: it breaks the register allocator
     of any LaTeX kernel newer than 2015 ("No room for a new \\count" in
     reledmac) — the .tex's own comment says it was a mactex-2015 fix;
  3. SOURCE_DATE_EPOCH, already pinned before this reproducibility pass, fixes
     the draft-crop timestamp.

All three GitHub repositories are pinned to commits resolved on 2026-08-04.
To re-pin, review the upstream diffs before updating the commit constants.

The resulting page shows reledmac's standard paragraphed DOUBLE
apparatus: fontium on top ("56-57 I Ad Corinthios 13:12"), variants
below ("79 contemptum] contentum V 79 fecit] om. R SV S") — the "N
lemma] rdg SIG" convention, distinct from the DLL's "∥ … | …" style.

Usage: plaoul_build_pdf.py <workdir> [lectio-number ...]
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

XSLT_REPO = "https://github.com/lombardpress/lbp-print-xslt"
XSLT_COMMIT = "8a862e5e1a5af02569b151c75e29ae81fd38500c"
LISTS_REPO = "https://github.com/lombardpress/lombardpress-lists"
LISTS_COMMIT = "5eefd538006c3c17c2d57119d5018ab9b5f4f05b"
TEI_COMMIT = "bd7096f7c68691daabf9ee093bcef5924d3135cc"
TEI_RAW = ("https://raw.githubusercontent.com/scta-texts/plaoulcommentary/"
           f"{TEI_COMMIT}/lectio{{n}}/lectio{{n}}.xml")

STUB = '<?xml version="1.0"?>\n<map xmlns="http://scta.info/ns/source-title-map"/>\n'


def sh(*cmd: str, **kw) -> None:
  r = subprocess.run(cmd, capture_output=True, text=True, **kw)
  if r.returncode != 0:
    sys.exit(f"FAILED: {' '.join(cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")


def clone_at(repo: str, commit: str, destination: Path) -> None:
  sh("git", "clone", "-q", repo, str(destination))
  sh("git", "-C", str(destination), "checkout", "-q", "--detach", commit)


def main() -> int:
  work = Path(sys.argv[1]).resolve()
  lectios = [int(a) for a in sys.argv[2:]] or [1]
  work.mkdir(parents=True, exist_ok=True)

  xslt_dir = work / "lbp-print-xslt"
  lists_dir = work / "lombardpress-lists"
  if not xslt_dir.exists():
    clone_at(XSLT_REPO, XSLT_COMMIT, xslt_dir)
  else:
    sh("git", "-C", str(xslt_dir), "checkout", "-q", "--detach", XSLT_COMMIT)
  if not lists_dir.exists():
    clone_at(LISTS_REPO, LISTS_COMMIT, lists_dir)
  else:
    sh("git", "-C", str(lists_dir), "checkout", "-q", "--detach", LISTS_COMMIT)
  stub = work / "sourceTitleMaps-stub.xml"
  stub.write_text(STUB, encoding="utf-8")

  xslt_src = (xslt_dir / "1.0.0" / "critical.xslt").read_text(encoding="utf-8")
  xslt_src = xslt_src.replace(
    "/Users/jcwitt/Projects/lombardpress/lombardpress-lists", str(lists_dir))
  xslt_src = re.sub(
    r"/Users/jcwitt/Projects/lombardpress/sourceTitleMaps/\S+?\.xml",
    str(stub), xslt_src)
  xslt_local = work / "critical-local.xslt"
  xslt_local.write_text(xslt_src, encoding="utf-8")

  from saxonche import PySaxonProcessor
  env = dict(os.environ, SOURCE_DATE_EPOCH="1700000000")
  for n in lectios:
    tei = work / f"lectio{n}.xml"
    sh("curl", "-fsSL", "-o", str(tei), TEI_RAW.format(n=n))
    with PySaxonProcessor(license=False) as proc:
      xp = proc.new_xslt30_processor()
      exe = xp.compile_stylesheet(stylesheet_file=str(xslt_local))
      tex = exe.transform_to_string(source_file=str(tei))
    tex = tex.replace("\\usepackage{etex}",
                      "% \\usepackage{etex} % breaks the modern allocator")
    (work / f"lectio{n}.tex").write_text(tex, encoding="utf-8")
    r = subprocess.run(
      ["tectonic", "-X", "compile", f"lectio{n}.tex"],
      cwd=work, capture_output=True, text=True, env=env)
    if r.returncode != 0:
      sys.exit(f"tectonic failed on lectio{n}:\n{r.stderr[-2000:]}")
    print(f"lectio{n}: {tei.stat().st_size} B TEI -> "
          f"{(work / f'lectio{n}.pdf').stat().st_size} B PDF")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
