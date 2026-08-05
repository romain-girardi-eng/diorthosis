#!/usr/bin/env python3
"""Measure diorthosis v0.7 on unseen born-digital critical editions.

The configured PDFs live outside the repository because they are reviewer-
supplied inputs.  This driver deliberately performs no tuning: it runs the
public CLI build, validates both emitted views, re-ingests the same pages only
to count layers/grammars, and prints Markdown tables plus deterministic manual-
review samples.

Usage:
  python tools/golden/generalize.py
  python tools/golden/generalize.py --only insolubles --samples 5
  python tools/golden/generalize.py --workdir /tmp/diorthosis-generalize-v07
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from diorthosis.anchor import anchor_page  # noqa: E402
from diorthosis.cli import _parse_pages  # noqa: E402
from diorthosis.conspectus import bootstrap_registry  # noqa: E402
from diorthosis.ingest import ingest_pdf  # noqa: E402
from diorthosis.model import Layer  # noqa: E402
from diorthosis.overrides import entry_keys  # noqa: E402
from diorthosis.tei import resolve_parsed  # noqa: E402

logging.getLogger("pdfminer.pdfpage").setLevel(logging.ERROR)


def _csv_pages(*groups: range) -> str:
  return ",".join(str(page) for group in groups for page in group)


@dataclass(frozen=True)
class Edition:
  slug: str
  edition: str
  pdf: Path
  pages: str
  page_label: str
  language: str
  convention: str
  text_lang: str = "la"
  conspectus_page: int | None = None
  sigla: tuple[str, ...] = ()
  limitation: str = ""
  fabrication_check: str = "pending manual sample"


EDITIONS = (
  Edition(
    slug="insolubles",
    edition="Walter Segrave, Insolubilia (2024)",
    pdf=Path("/tmp/gen10/insolubles.pdf"),
    pages=_csv_pages(range(30, 149, 2)),
    page_label="30,32,...,148 (Latin pages)",
    language="Scholastic Latin",
    convention="paragraphed line + ] (reledmac)",
    conspectus_page=25,
    sigla=("E4", "E8", "O"),
    fabrication_check="PASS (5/5 faithful; all || bands refused)",
  ),
  Edition(
    slug="britannico",
    edition="Giovanni Britannico, Persius commentary (2017 thesis)",
    pdf=Path("/tmp/gen10/britannico.pdf"),
    pages="160-433",
    page_label="160-433",
    language="Humanist Latin",
    convention="two-tier vv.ll./Fontes; locus lemma : reading",
    sigla=("a", "b", "c"),
    fabrication_check="N/A (0 parsed; wholesale refusal)",
  ),
  Edition(
    slug="derivas",
    edition="Herodian, Books I-II (2024 thesis)",
    pdf=Path("/tmp/gen10/derivas.pdf"),
    pages=_csv_pages(range(378, 433, 2), range(452, 507, 2)),
    page_label="378,380,...,432; 452,454,...,506",
    language="Ancient Greek",
    convention="Budé-style locus + colon; run-in readings with ||",
    text_lang="grc",
    conspectus_page=376,
    sigla=("A", "B", "V", "G", "F", "L", "Io"),
    fabrication_check="N/A (0 parsed; wholesale refusal)",
  ),
  Edition(
    slug="iacopone",
    edition="Iacopone da Todi, Laudario (2020 thesis)",
    pdf=Path("/tmp/gen10/iacopone.pdf"),
    pages="122-126,142-165,174-176,188-189,209-215,226-227,247-250,265-266",
    page_label="eight critical-text runs, 122-266",
    language="Medieval Italian",
    convention="three-tier negative apparatus; locus lemma] variants",
    sigla=(
      "As", "Be", "H", "Ch", "Sp", "Va", "Vb", "Ch’", "B", "Ash’",
      "Lc", "Cs", "Mga", "G", "L", "M", "Br", "N", "Ox’", "Pd’",
      "P", "Pr", "O", "A", "A’", "Ve", "S", "F", "Ma", "Mb", "BON",
      "TRES",
    ),
    limitation="Italian is measured through --text-lang la",
    fabrication_check="N/A (0 parsed; wholesale refusal)",
  ),
  Edition(
    slug="blacasset",
    edition="Blacasset, Occitan poems (2024 monograph)",
    pdf=Path("/tmp/gen10/blacasset.pdf"),
    pages="115-262",
    page_label="115-262 (Testi section)",
    language="Occitan",
    convention="stanza/verse lemma] variants; | within readings",
    conspectus_page=267,
    sigla=(
      "a1", "A", "B", "C", "D-Da-Dc", "E", "f", "F", "G", "H",
      "I", "K", "L", "M", "N", "O", "P", "Q", "S", "T", "U",
      "V", "VeAg", "W",
    ),
    limitation="Occitan is measured through --text-lang la",
    fabrication_check="N/A (0 parsed; wholesale refusal)",
  ),
  Edition(
    slug="pigna",
    edition="G. B. Pigna, Gli Heroici (2025 edition)",
    pdf=Path("/tmp/gen10/pigna.pdf"),
    pages="44-127",
    page_label="44-127",
    language="16th-century Italian",
    convention="no critical apparatus; explanatory footnotes only",
    limitation="Italian is measured through --text-lang la; copy flag ignored by pdfminer",
    fabrication_check="N/A (0 parsed; wholesale refusal)",
  ),
  Edition(
    slug="saivism",
    edition="Bisschop, Universal Śaivism (2018)",
    pdf=Path("/tmp/gen10/saivism.pdf"),
    pages="72-153",
    page_label="72-153",
    language="Sanskrit (IAST)",
    convention="multi-tier pada/line lemma] compact composite sigla",
    sigla=(
      "N7K7o", "N8K2", "N1K2", "N4C5", "N5K8", "B9C9", "Ś6S7",
      "P3T2", "P7T2", "EN",
    ),
    limitation="Sanskrit IAST is measured through --text-lang la",
    fabrication_check="N/A (0 parsed; wholesale refusal)",
  ),
  Edition(
    slug="susruta",
    edition="Suśrutasaṃhitā 1.16 (HASP)",
    pdf=Path("/tmp/gen10/susruta.pdf"),
    pages="58-67",
    page_label="58-67",
    language="Sanskrit (Devanagari)",
    convention="stacked MS/Su1938 apparatus; Devanagari locus lemma]",
    sigla=("K", "N", "H", "A"),
    limitation="Sanskrit is measured through --text-lang la; script is Devanagari",
    fabrication_check="N/A (0 parsed; wholesale refusal)",
  ),
  Edition(
    slug="gracilis",
    edition="Petrus Gracilis, b1q1 (same-toolchain unseen content)",
    pdf=Path("/tmp/gracilis_generalization/lectio1.pdf"),
    pages="0-10",
    page_label="0-10",
    language="Scholastic Latin",
    convention="LombardPress double reledmac apparatus",
    limitation="optional locally typeset case; the PDF prints no conspectus",
    fabrication_check="N/A (0 parsed; wholesale refusal)",
  ),
)


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
  return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def _grammar(entry, parsed) -> str:
  if parsed is None:
    return "refused"
  if entry.parsed_override is not None:
    return "override"
  if entry.parsed_verse is not None:
    return "verse"
  if entry.parsed_line is not None:
    return "line"
  if entry.parsed_paragraph is not None:
    return "paragraph"
  return "marker"


def _parsed_dict(parsed) -> dict:
  return {
    "lemma": parsed.lemma,
    "lemma_wits": list(parsed.lemma_attribution.witnesses),
    "lemma_editors": list(parsed.lemma_attribution.editors),
    "readings": [
      {
        "text": reading.text,
        "wits": list(reading.attribution.witnesses),
        "editors": list(reading.attribution.editors),
        "qualifiers": list(reading.attribution.qualifiers),
      }
      for reading in parsed.readings
    ],
    "comments": list(parsed.comments),
  }


def _check_output(command: str, *paths: Path) -> tuple[str, str]:
  result = _run([sys.executable, "-m", "diorthosis.cli", command,
                 *(str(path) for path in paths)], cwd=REPO / "src")
  verdict = "PASS" if result.returncode == 0 else "FAIL"
  detail = (result.stdout + result.stderr).strip().replace("\n", " | ")
  return verdict, detail[-1000:]


def measure(edition: Edition, workdir: Path, sample_size: int) -> dict:
  result: dict = {
    "edition": edition,
    "error": "",
    "samples": [],
  }
  if not edition.pdf.exists():
    result["error"] = f"missing input: {edition.pdf}"
    return result

  out = workdir / edition.slug / "out"
  out.mkdir(parents=True, exist_ok=True)
  command = [
    sys.executable, "-m", "diorthosis.cli", "build", str(edition.pdf),
    "--pages", edition.pages, "--text-lang", edition.text_lang,
    "--title", edition.edition, "-o", str(out),
    # this harness MEASURES what the tool does on unseen conventions, so a
    # build the tool refuses to certify is a row of the table, not a missing
    # row: blacasset's tagged PDF duplicates folios and its md-ce fails I7,
    # which is exactly the kind of result the generalization study exists to
    # publish. The refusal itself is reported in the validate column.
    "--ignore-self-check",
  ]
  if edition.conspectus_page is not None:
    command += ["--conspectus-page", str(edition.conspectus_page)]
  if edition.sigla:
    command += ["--sigla", ",".join(edition.sigla)]

  started = time.perf_counter()
  build = _run(command, cwd=REPO / "src")
  result["build_seconds"] = time.perf_counter() - started
  result["build_returncode"] = build.returncode
  result["build_log"] = (build.stdout + build.stderr).strip()
  if build.returncode != 0:
    result["error"] = "CLI build failed"
    return result

  stem = edition.pdf.stem[:60] or "edition"
  md_path = out / f"{stem}.md"
  tei_path = out / f"{stem}.tei.xml"
  result["validate"], result["validate_log"] = _check_output("validate", md_path)
  result["roundtrip"], result["roundtrip_log"] = _check_output(
    "roundtrip", md_path, tei_path)

  try:
    doc = ingest_pdf(
      edition.pdf, pages=_parse_pages(edition.pages), text_lang=edition.text_lang)
    registry, conspectus_note = bootstrap_registry(
      str(edition.pdf), edition.conspectus_page)
    for siglum in edition.sigla:
      registry.witnesses.setdefault(siglum, "manual --sigla from printed front matter")
    result["conspectus_note"] = conspectus_note or "no conspectus parsed"

    layer_blocks: Counter[str] = Counter()
    layer_pages: dict[str, set[int]] = {}
    layer_chars: Counter[str] = Counter()
    anchor_totals: Counter[str] = Counter()
    parsed_by: Counter[str] = Counter()
    refusal_evidence: Counter[str] = Counter()
    parsed_entries: list[dict] = []
    for page in doc.pages:
      for block in page.blocks:
        key = block.layer.value
        layer_blocks[key] += 1
        layer_pages.setdefault(key, set()).add(page.index)
        layer_chars[key] += len(block.text)
      anchor_totals.update(anchor_page(page, registry))
      for key, entry in entry_keys(page):
        parsed = resolve_parsed(entry, registry)
        grammar = _grammar(entry, parsed)
        parsed_by[grammar] += 1
        if parsed is None and entry.refusal_evidence:
          refusal_evidence[entry.refusal_evidence] += 1
        if parsed is not None:
          parsed_entries.append({
            "key": key,
            "page": page.index,
            "grammar": grammar,
            "source_slice": entry.source_slice,
            "parsed": _parsed_dict(parsed),
          })

    seed = int.from_bytes(
      hashlib.sha256(f"diorthosis-v0.7:{edition.slug}".encode()).digest()[:8],
      "big",
    )
    rng = random.Random(seed)
    sample = rng.sample(parsed_entries, min(sample_size, len(parsed_entries)))
    result.update({
      "pages": len(doc.pages),
      "layer_blocks": dict(sorted(layer_blocks.items())),
      "layer_pages": {key: len(value) for key, value in sorted(layer_pages.items())},
      "layer_chars": dict(sorted(layer_chars.items())),
      "entries": anchor_totals["entries"],
      "anchored": anchor_totals["anchored"],
      "unanchored": anchor_totals["unanchored"],
      "ambiguous": anchor_totals["ambiguous"],
      "parsed_by": dict(sorted(parsed_by.items())),
      "parsed": len(parsed_entries),
      "refused": parsed_by["refused"],
      "refusal_evidence": dict(sorted(refusal_evidence.items())),
      "samples": sorted(sample, key=lambda item: (item["page"], item["key"])),
    })
  except Exception as exc:  # noqa: BLE001 - one failed edition must remain visible
    result["error"] = f"measurement failed: {type(exc).__name__}: {exc}"
  return result


def _pct(numerator: int, denominator: int) -> str:
  return f"{100 * numerator / denominator:.1f}%" if denominator else "n/a"


def _parsed_cell(result: dict) -> str:
  total = result["entries"]
  breakdown = ", ".join(
    f"{grammar} {count}" for grammar, count in result["parsed_by"].items()
    if grammar != "refused" and count
  ) or "none"
  return f"{_pct(result['parsed'], total)} ({breakdown})"


def _cell(value: object) -> str:
  return str(value).replace("|", r"\|").replace("\n", " ")


def markdown(results: list[dict]) -> str:
  lines = [
    "| Edition | Language | Convention family | PDF pages (0-based) | Pages | "
    "Entries | Parsed % (by grammar) | Refused % | Anchored % | "
    "Fabrication check | Notes |",
    "|---|---|---|---:|---:|---:|---|---:|---:|---|---|",
  ]
  for result in results:
    edition = result["edition"]
    if result["error"]:
      lines.append(
        f"| {_cell(edition.edition)} | {_cell(edition.language)} | "
        f"{_cell(edition.convention)} | {_cell(edition.page_label)} | "
        f"- | - | - | - | - | not run | "
        f"**{result['error']}** |")
      continue
    notes = edition.limitation
    lines.append(
      f"| {_cell(edition.edition)} | {_cell(edition.language)} | "
      f"{_cell(edition.convention)} | {_cell(edition.page_label)} | "
      f"{result['pages']} | {result['entries']} | "
      f"{_parsed_cell(result)} | {_pct(result['refused'], result['entries'])} | "
      f"{_pct(result['anchored'], result['entries'])} | "
      f"{_cell(edition.fabrication_check)} | {_cell(notes)} |")

  lines += [
    "",
    "| Edition | Layer blocks | Layer pages | Apparatus chars | "
    "Anchored / unanchored / ambiguous | Validate | Roundtrip | CLI build wall |",
    "|---|---|---|---:|---:|---|---|---:|",
  ]
  for result in results:
    edition = result["edition"]
    if result["error"]:
      lines.append(
        f"| {edition.slug} | - | - | - | - | - | - | "
        f"{result.get('build_seconds', 0):.2f}s |")
      continue
    blocks = ", ".join(f"{key}={value}" for key, value in result["layer_blocks"].items())
    pages = ", ".join(f"{key}={value}" for key, value in result["layer_pages"].items())
    app_chars = result["layer_chars"].get(Layer.APPARATUS.value, 0)
    lines.append(
      f"| {edition.slug} | {blocks} | {pages} | {app_chars} | "
      f"{result['anchored']} / {result['unanchored']} / {result['ambiguous']} | "
      f"{result['validate']} | {result['roundtrip']} | "
      f"{result['build_seconds']:.2f}s |")
  lines += [
    "",
    "| Edition | Observable convention-gate refusal evidence (entries) |",
    "|---|---|",
  ]
  for result in results:
    edition = result["edition"]
    if result["error"]:
      lines.append(f"| {edition.slug} | - |")
      continue
    evidence = "; ".join(
      f"{reason} ({count})"
      for reason, count in result["refusal_evidence"].items()
    ) or "none"
    lines.append(f"| {edition.slug} | {_cell(evidence)} |")
  return "\n".join(lines)


def sample_markdown(results: list[dict]) -> str:
  lines = [
    "## Deterministic fabrication-check samples",
    "",
    "These are review material, not automated correctness claims. Compare each "
    "parsed object with `source_slice` and the rendered PDF page.",
  ]
  for result in results:
    lines += ["", f"### {result['edition'].slug}", ""]
    if result["error"]:
      lines.append(f"No sample: {result['error']}")
      continue
    if not result["samples"] and result["parsed"]:
      lines.append("Sampling disabled (`--samples 0`).")
      continue
    if not result["samples"]:
      lines.append("No parsed entries; there is no structure to sample.")
      continue
    for sample in result["samples"]:
      lines += [
        f"- `{sample['key']}` ({sample['grammar']})",
        "",
        "  Source slice:",
        "",
        "  ```text",
        *[f"  {line}" for line in sample["source_slice"].splitlines()],
        "  ```",
        "",
        "  Parsed:",
        "",
        "  ```json",
        *[f"  {line}" for line in json.dumps(
          sample["parsed"], ensure_ascii=False, indent=2).splitlines()],
        "  ```",
      ]
  return "\n".join(lines)


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--only", action="append", default=[], metavar="SLUG")
  parser.add_argument(
    "--workdir", type=Path, default=Path("/tmp/diorthosis-generalize-v07"))
  parser.add_argument("--samples", type=int, default=5)
  args = parser.parse_args()
  if args.samples < 0:
    parser.error("--samples must be non-negative")
  unknown = set(args.only) - {edition.slug for edition in EDITIONS}
  if unknown:
    parser.error(f"unknown --only slug(s): {', '.join(sorted(unknown))}")

  selected = [edition for edition in EDITIONS
              if not args.only or edition.slug in args.only]
  args.workdir.mkdir(parents=True, exist_ok=True)
  results = []
  for edition in selected:
    print(f"measuring {edition.slug}...", file=sys.stderr, flush=True)
    results.append(measure(edition, args.workdir, args.samples))
  print(markdown(results))
  print()
  print(sample_markdown(results))
  return 1 if any(result["error"] for result in results) else 0


if __name__ == "__main__":
  raise SystemExit(main())
