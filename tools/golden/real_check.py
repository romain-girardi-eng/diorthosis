#!/usr/bin/env python3
"""Real-PDF evidence using the exact structured path emitted by the CLI.

Coverage still measures the printed layers.  Structural claims are stricter:
``anchor_page`` chooses the line/verse/paragraph grammar and
``resolve_parsed`` supplies precisely the structure the TEI emitter sees.
Candidates are never forgiven by a shared word elsewhere in the edition.

Usage:
  real_check.py scholar.xml real.pdf --pages A-B [--text-lang la]
    [--conspectus-page N] [--max-apps N]
    [--min-text-coverage PCT] [--min-band-coverage PCT]
    [--max-contamination N] [--max-false-structures N]
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from lxml import etree

from diorthosis.anchor import anchor_page
from diorthosis.conspectus import bootstrap_registry
from diorthosis.ingest import ingest_pdf
from diorthosis.model import Layer
from diorthosis.tei import resolve_parsed

TEI = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
CONTAMINATION_RADIUS = 100


def fold(s: str) -> str:
  s = unicodedata.normalize("NFKC", s)
  s = re.sub(r"[⸀-⸏⟦⟧∥|◊]", " ", s)
  s = s.translate(str.maketrans("", "", "[]{}⟨⟩〈〉†"))
  s = re.sub(r"(?<=\S)-\s+", "", s)
  d = unicodedata.normalize("NFD", s)
  out = "".join(c for c in d if not unicodedata.combining(c)).lower()
  # elision apostrophes drop entirely: the extracted band carries U+2019
  # while the TEI's koronis arrives combining and is eaten by the NFD
  # filter — one side kept "κατ'", the other "κατ" (reviewed, Mt 12:14)
  out = out.replace("ς", "σ").replace("ʼ", "").replace("’", "").replace("'", "")
  out = re.sub(r"[,.;·:!?…]+", " ", out)
  return re.sub(r"\s+", " ", out).strip()


def exact_match(needle: str, haystack: str) -> re.Match | None:
  """Exact folded phrase containment, word-bounded at both ends."""
  if not needle:
    return None
  return re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack)


def exact_in(needle: str, haystack: str) -> bool:
  return exact_match(needle, haystack) is not None


def lemma_window(text: str, lemma: str,
                 radius: int = CONTAMINATION_RADIUS) -> tuple[str, int, int] | None:
  """Return the bounded text window around one uniquely located lemma."""
  hits = list(re.finditer(r"(?<!\w)" + re.escape(lemma) + r"(?!\w)", text))
  if len(hits) != 1:
    return None
  hit = hits[0]
  start = max(0, hit.start() - radius)
  end = min(len(text), hit.end() + radius)
  return text[start:end], start, end


def canon_locus(value: str) -> str:
  return value.replace("–", "-").strip()


def tei_apps(path: Path) -> list[dict]:
  root = etree.parse(str(path)).getroot()
  apps = []
  current_book = ""
  current_loc = ""
  for el in root.iter():
    if not isinstance(el.tag, str):
      continue
    xid = el.get(XML_ID) or ""
    milestone = re.match(r"(B\d+)K(\d+)V(\d+)$", xid)
    if milestone:
      current_book = milestone.group(1)
      current_loc = f"{milestone.group(2)}:{milestone.group(3)}"
    if el.tag != f"{TEI}app":
      continue
    if any(isinstance(d.tag, str) and d.tag == f"{TEI}app"
           for d in el.iterdescendants()):
      continue
    lem = el.find(f"{TEI}lem")
    if lem is None:
      continue
    lemma = fold(" ".join(lem.itertext()))
    if not lemma:
      continue
    lem_id = lem.get(XML_ID) or ""
    loc_match = re.match(r"lem-([\d.]+)-", lem_id)
    loc = canon_locus(
      el.get("loc") or current_loc or (loc_match.group(1) if loc_match else ""))
    readings = [fold(" ".join(r.itertext()))
                for r in el.findall(f"{TEI}rdg")]
    apps.append({
      "book": current_book,
      "loc": loc,
      "lemma": lemma,
      "readings": [r for r in readings if r != lemma],
    })
  return apps


def tei_source_text(path: Path) -> str:
  """The scholars' CONSTITUTED text, folded: body with every <rdg> and
  <note> removed (the <lem> stays — it IS text). The contamination
  arbiter: a rejected-reading sequence found near its lemma in the
  EXTRACTED text is only a leak if it occurs NOWHERE in this text —
  variants share their lemma's vocabulary and transpose neighbour
  wording, so bare presence near the lemma convicts legitimate text
  (reviewed on balex 7.1 'casum' and Mt 5:32/5:31)."""
  root = etree.parse(str(path)).getroot()
  body = root.find(f".//{TEI}text/{TEI}body")
  if body is None:
    return ""
  for tag in ("rdg", "note"):
    for el in body.iter(f"{TEI}{tag}"):
      el.getparent().remove(el)
  return fold(" ".join(body.itertext()))


def arg_value(name: str, default=None):
  return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def candidate_locus(entry) -> tuple[str, str]:
  if entry.parsed_verse is not None:
    return "verse", entry.parsed_verse.loc
  if entry.parsed_line is not None:
    return "line", entry.parsed_line.line
  if entry.parsed_paragraph is not None:
    return "paragraph", entry.parsed_paragraph.line
  return "generic", entry.anchor.value if entry.anchor is not None else ""


def main() -> int:
  source_path = Path(sys.argv[1])
  pdf = sys.argv[2]
  pages = None
  if (spec := arg_value("--pages")) is not None:
    a, b = spec.split("-")
    pages = list(range(int(a), int(b) + 1))
  text_lang = arg_value("--text-lang", "grc")
  conspectus = arg_value("--conspectus-page")
  conspectus_page = int(conspectus) if conspectus is not None else None

  apps = tei_apps(source_path)
  source_text = tei_source_text(source_path)
  if (max_apps := arg_value("--max-apps")) is not None:
    apps = apps[:int(max_apps)]
  print(f"TEI ground truth: {len(apps)} leaf apps")

  doc = ingest_pdf(pdf, pages=pages, text_lang=text_lang)
  registry, registry_note = bootstrap_registry(pdf, conspectus_page)
  if registry_note:
    print(registry_note)
  layer_counts: Counter[str] = Counter()
  candidates: list[dict] = []
  entries_total = 0
  page_text: dict[int, str] = {}
  page_band: dict[int, str] = {}
  for page in doc.pages:
    anchor_page(page, registry)
    page_text[page.index] = fold("\n".join(
      block.text for block in page.blocks
      if block.layer in (Layer.TEXT, Layer.HEADING)))
    page_band[page.index] = fold("\n".join(
      block.text for block in page.blocks if block.layer is Layer.APPARATUS))
    for block in page.blocks:
      layer_counts[block.layer.value] += 1
      if block.layer is not Layer.APPARATUS:
        continue
      for entry in block.entries or []:
        entries_total += 1
        parsed = resolve_parsed(entry, registry)
        if parsed is None:
          continue
        grammar, locus = candidate_locus(entry)
        candidates.append({
          "page": page.index,
          "page_label": page.printed_page or f"pdf:{page.index}",
          "grammar": grammar,
          "locus": canon_locus(locus),
          "lemma": fold(parsed.lemma),
        })

  text_all = fold("\n".join(page_text.values()))
  band_all = fold("\n".join(page_band.values()))
  print(f"layers: {dict(layer_counts)}")
  print(f"text chars: {len(text_all)} | band chars: {len(band_all)} | "
        f"split entries: {entries_total} | production <app> candidates: "
        f"{len(candidates)}")

  text_hit = sum(1 for app in apps if exact_in(app["lemma"], text_all))

  window_size = 8000
  pos = 0
  band_hit = 0
  band_misses: list[str] = []
  for app in apps:
    segment = band_all[pos:pos + window_size]
    keys: list[str] = []
    for key in (app["lemma"], *(app["readings"][:1])):
      if not key:
        continue
      keys.append(key)
      words = key.split()
      if len(words) >= 3:
        keys.append(f"{words[0]} {words[-1]}")
      if len(words) == 1:
        keys.append(key + key)
    hits = [m.start() for key in keys
            if (m := re.search(r"(?<!\w)" + re.escape(key), segment))]
    if hits:
      band_hit += 1
      pos += min(hits)
    elif len(band_misses) < 8:
      band_misses.append(
        f"loc={app['loc']!r} lemma={app['lemma'][:40]!r}")

  # Assign a source locus to a page only from an exact folded lemma hit.
  # Ambiguity is reported and skipped; choosing a convenient recurrence
  # would recreate the old one-shared-word global forgiveness.
  source_pages: dict[int, int] = {}
  page_skip_apps: Counter[str] = Counter()
  verse_pages: dict[str, set[int]] = defaultdict(set)
  for candidate in candidates:
    if candidate["grammar"] == "verse":
      verse_pages[candidate["locus"]].add(candidate["page"])
  for i, app in enumerate(apps):
    locus_pages = verse_pages.get(app["loc"], set()) if app["book"] else set()
    if len(locus_pages) == 1:
      source_pages[i] = next(iter(locus_pages))
      continue
    hits = [page for page, text in page_text.items()
            if exact_in(app["lemma"], text)]
    if len(hits) == 1:
      source_pages[i] = hits[0]
    elif not hits:
      page_skip_apps["lemma absent from selected page text"] += 1
    else:
      page_skip_apps["lemma occurs on multiple selected pages"] += 1

  length_hist: Counter[int] = Counter(
    len(reading.split()) for app in apps for reading in app["readings"])
  contamination = 0
  contamination_evidence: list[dict] = []
  contamination_examined = 0
  contamination_skips: Counter[str] = Counter()
  for i, app in enumerate(apps):
    readings = app["readings"]
    if i not in source_pages:
      reason = ("source app has no unique page locus: "
                + ("lemma absent" if not any(
                  exact_in(app["lemma"], text) for text in page_text.values())
                   else "lemma page-ambiguous"))
      contamination_skips[reason] += len(readings)
      continue
    page = source_pages[i]
    text = page_text[page]
    located = lemma_window(text, app["lemma"])
    if located is None:
      contamination_skips[
        "source lemma occurrence is not unique within its page"] += len(readings)
      continue
    local, window_start, window_end = located
    for reading in readings:
      words = len(reading.split())
      contamination_examined += 1
      reading_hit = exact_match(reading, local)
      if reading_hit is not None and exact_in(reading, source_text):
        contamination_skips[
          "sequence occurs in the scholars' constituted text (legitimate)"] += 1
        continue
      if reading_hit is not None:
        contamination += 1
        marked = (local[:reading_hit.start()] + "⟪"
                  + local[reading_hit.start():reading_hit.end()] + "⟫"
                  + local[reading_hit.end():])
        contamination_evidence.append({
          "page": page,
          "loc": app["loc"],
          "words": words,
          "lemma": app["lemma"],
          "reading": reading,
          "window": marked,
          "window_start": window_start,
          "window_end": window_end,
        })

  source_at_page: dict[int, list[dict]] = defaultdict(list)
  for i, page in source_pages.items():
    source_at_page[page].append(apps[i])
  false_structures: list[dict] = []
  structure_examined = 0
  structure_skips: Counter[str] = Counter()
  for candidate in candidates:
    page_apps = source_at_page.get(candidate["page"], [])
    if candidate["grammar"] == "verse":
      # the verse IS the locus: a page filter here dropped genuine source
      # apps whose one-word lemma is page-ambiguous, then convicted the
      # candidate for not matching what was left (reviewed: Mt 19:24)
      locus_apps = [app for app in apps if app["loc"] == candidate["locus"]]
      if not locus_apps:
        structure_skips[
          "no source app at the candidate's verse locus"] += 1
        continue
      structure_examined += 1
      # containment, not equality: the print may carry ONE long elliptic
      # lemma where the TEI splits several short apps (Mt 12:14, 21:44) —
      # a print/TEI divergence, not a fabricated structure
      cand = candidate["lemma"]
      if not any(app["lemma"] == cand or app["lemma"] in cand
                 or cand in app["lemma"] for app in locus_apps):
        false_structures.append(candidate)
      continue
    if not page_apps:
      structure_skips["no source app has a unique locus on candidate page"] += 1
      continue
    structure_examined += 1
    if any(app["lemma"] == candidate["lemma"] for app in page_apps):
      continue
    same_lemma = [i for i, app in enumerate(apps)
                  if app["lemma"] == candidate["lemma"]]
    if same_lemma and any(i not in source_pages for i in same_lemma):
      structure_examined -= 1
      structure_skips[
        "exact source lemma exists but has no unique page locus"] += 1
    elif candidate["grammar"] in ("line", "paragraph"):
      # conventions with a DEDICATED structured harness (line_check.py,
      # plaoul_check.py: global-order alignment + elliptic-lemma logic)
      # are judged there with strictly more information; this naive
      # page/lemma match convicted 21 legitimate long-lemma balex entries
      # that line_check proves correct (563 = 0/0). Defer, count, move on.
      structure_examined -= 1
      structure_skips[
        "deferred to the convention's structured harness"] += 1
    else:
      false_structures.append(candidate)

  total = len(apps)
  denom = total or 1
  text_pct = 100 * text_hit / denom
  band_pct = 100 * band_hit / denom
  print(f"\ntext coverage    : {text_hit}/{total} = {text_pct:.1f} % "
        "(exact folded TEI lemma in selected TEXT)")
  print(f"band coverage    : {band_hit}/{total} = {band_pct:.1f} % "
        "(bounded in-order exact folded alignment)")
  print(f"source page loci : {len(source_pages)}/{total} assigned | "
        f"{total - len(source_pages)} skipped {dict(page_skip_apps)}")
  print(f"contamination    : {contamination}/{contamination_examined} examined "
        f"rejected readings | {sum(contamination_skips.values())} skipped "
        f"{dict(contamination_skips)} | lemma window ±{CONTAMINATION_RADIUS} chars")
  print(f"reading lengths  : {dict(sorted(length_hist.items()))}")
  for evidence in contamination_evidence:
    print(f"   HIT p{evidence['page']} {evidence['loc']} "
          f"({evidence['words']} words) lemma={evidence['lemma']!r} "
          f"reading={evidence['reading']!r}")
    print(f"       window[{evidence['window_start']}:{evidence['window_end']}]="
          f"{evidence['window']!r}")
  print(f"false structures : {len(false_structures)}/{structure_examined} examined "
        f"production candidates | {sum(structure_skips.values())} skipped "
        f"{dict(structure_skips)}")
  for candidate in false_structures:
    print(f"   e.g. p{candidate['page_label']} {candidate['grammar']} "
          f"{candidate['locus']}: {candidate['lemma'][:60]!r}")
  if band_misses:
    print("unaligned sample:")
    for miss in band_misses:
      print(f"   {miss}")

  max_contam = int(arg_value("--max-contamination", "0"))
  max_false = int(arg_value("--max-false-structures", "0"))
  failures = []
  if contamination > max_contam:
    failures.append(f"contamination {contamination} > declared limit {max_contam}")
  if len(false_structures) > max_false:
    failures.append(
      f"false structures {len(false_structures)} > declared limit {max_false}")
  if (minimum := arg_value("--min-text-coverage")) is not None \
     and text_pct < float(minimum):
    failures.append(f"text coverage {text_pct:.1f} < declared limit {minimum}")
  if (minimum := arg_value("--min-band-coverage")) is not None \
     and band_pct < float(minimum):
    failures.append(f"band coverage {band_pct:.1f} < declared limit {minimum}")
  if failures:
    for failure in failures:
      print(f"ERROR LIMIT: {failure}")
    return 1
  print("PASS: all declared real-PDF limits hold")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
