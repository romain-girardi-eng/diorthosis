#!/usr/bin/env python3
"""Typeset a scholar-encoded apparatus into a born-digital critical-edition
PDF — deterministically — and emit the matching ground truth.

The golden pipeline:

    scholar TEI --(adapter)--> edition JSON --(this)--> .tex + golden.json
                                                          |
                                              tectonic -> PDF
                                                          |
                                       diorthosis build -> TEI + md
                                                          |
                                check_golden.py: TEI vs golden.json == 0 errors

The apparatus CONTENT (lemmas, readings, witness sigla, editors) flows
unchanged from the scholars' encoding; only the SERIALIZATION to a printed
convention is ours (Paradosis/SC style: per-page numeric superscript
markers, ``N Lemma : reading SIGLA`` band at the foot). Pagination is
composed HERE, never left to TeX (``\\newpage`` after a fixed number of
sentences), so the per-page ground truth is exact by construction.

Edition JSON (the neutral input an adapter produces from a scholar TEI):

    {
      "title": str,
      "language": "grc" | "la",
      "witnesses": {siglum: description, ...},      # -> conspectus page
      "sentences": [
        {"text": "words of the constituted text ...",
         "apps": [                                   # 0+ apparatus entries,
           {"lemma": str,                            #   marker goes after the
            "lemma_wits": [..], "lemma_editors": [..],   # lemma's last word
            "readings": [
              {"text": str,                          # "" = omission (om.)
               "wits": [..], "editors": [..],
               "note": str}                          # free trailing note
            ]}
         ]}
      ]
    }
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

FIRST_FOLIO = 24

# Adaptive pagination budget, in estimated printed lines. The page must
# hold text + rule + band WITHOUT TeX ever breaking it itself: an
# overflowing band would spill onto phantom pages the golden knows nothing
# about (a failure mode that produced 56 PDF pages for 31 golden ones).
_PAGE_LINE_BUDGET = 23
_TEXT_WORDS_PER_LINE = 10
_BAND_CHARS_PER_LINE = 58


def _est_text_lines(sentence: dict) -> int:
  return max(1, -(-len(sentence["text"].split()) // _TEXT_WORDS_PER_LINE))


def _est_band_lines(sentence: dict) -> int:
  total = 0
  for app in sentence.get("apps", []):
    total += max(1, -(-len(band_entry(99, app)) // _BAND_CHARS_PER_LINE))
  return total


def _split_oversized(s: dict) -> list[dict]:
  """A single sentence whose text+band exceed one page would force TeX to
  break the page itself — split it at word boundaries, each app following
  the chunk that contains its lemma's last word."""
  if _est_text_lines(s) + _est_band_lines(s) <= _PAGE_LINE_BUDGET:
    return [s]
  words = s["text"].split()
  step = max(20, (_PAGE_LINE_BUDGET // 3) * _TEXT_WORDS_PER_LINE)
  chunks = [" ".join(words[i:i + step]) for i in range(0, len(words), step)]
  out = [{"text": c, "apps": []} for c in chunks]
  for app in s.get("apps", []):
    last = app["lemma"].split()[-1]
    target = next((o for o in out if last in o["text"]), out[0])
    target["apps"].append(app)
  return out


def paginate(sentences: list[dict]) -> list[list[dict]]:
  pages: list[list[dict]] = []
  cur: list[dict] = []
  used = 0
  for big in sentences:
    for s in _split_oversized(big):
      cost = _est_text_lines(s) + _est_band_lines(s)
      if cur and used + cost > _PAGE_LINE_BUDGET:
        pages.append(cur)
        cur, used = [], 0
      cur.append(s)
      used += cost
  if cur:
    pages.append(cur)
  return pages

_TEX_SPECIALS = {
  "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
  "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
  "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def tex_escape(s: str) -> str:
  return "".join(_TEX_SPECIALS.get(c, c) for c in s)


def _cap(s: str) -> str:
  """Capitalize the first LETTER, the way printed bands open their entries —
  skipping any leading editorial bracket ("<ab> incendio" -> "<Ab> incendio")."""
  for i, c in enumerate(s):
    if c.isalpha():
      return s[:i] + c.upper() + s[i + 1:]
  return s


def band_entry(n: int, app: dict) -> str:
  """One printed apparatus entry, Paradosis/SC convention."""
  parts: list[str] = []
  lemma_side = _cap(app["lemma"].strip())
  attrib = " ".join([*app.get("lemma_wits", []), *app.get("lemma_editors", [])])
  if attrib:
    lemma_side += f" {attrib}"
  parts.append(lemma_side)
  for r in app.get("readings", []):
    side = r.get("text", "").strip() or "om."
    ra = " ".join([*r.get("wits", []), *r.get("editors", [])])
    if ra:
      side += f" {ra}"
    if r.get("note"):
      side += f" {r['note'].strip()}"
    parts.append(side)
  return f"{n} " + " : ".join(parts)


def build(edition: dict, out_tex: Path, out_golden: Path) -> None:
  pages = paginate(edition["sentences"])

  golden: dict = {
    "title": edition["title"],
    "language": edition.get("language", "grc"),
    "witnesses": edition.get("witnesses", {}),
    "conspectus_pdf_page": 0,
    "pages": [],
  }
  body: list[str] = []

  # conspectus siglorum page(s) — tests the registry bootstrap end to end;
  # real editions declare their editores too, so the cited editors get a
  # section — the registry must come from the document, not from us.
  # Paginated HERE (a long editores list overflows a single page, and
  # TeX-broken pages would desynchronize the page-count guard).
  decl_lines: list[str] = [r"\noindent\textsc{Sigles}\par\bigskip"]
  for siglum, desc in edition.get("witnesses", {}).items():
    decl_lines.append(rf"\noindent {tex_escape(siglum)} = {tex_escape(desc)}\par")
  editors = edition.get("editors", [])
  if editors:
    decl_lines.append(r"\bigskip\noindent\textsc{Editores}\par\bigskip")
    for ed in editors:
      decl_lines.append(rf"\noindent {tex_escape(ed)} = {tex_escape(ed)}\par")
  conspectus_pages = 0
  cur_cost = 0
  cur_lines: list[str] = []
  for line in decl_lines:
    cost = max(1, -(-len(line) // 70))   # long descriptions wrap
    if cur_lines and cur_cost + cost > _PAGE_LINE_BUDGET:
      body.extend(cur_lines)
      body.append(r"\thispagestyle{empty}\newpage")
      conspectus_pages += 1
      cur_lines, cur_cost = [], 0
    cur_lines.append(line)
    cur_cost += cost
  if cur_lines:
    body.extend(cur_lines)
    body.append(r"\thispagestyle{empty}\newpage")
    conspectus_pages += 1
  golden["conspectus_pdf_pages"] = conspectus_pages

  dropped = 0
  for pi, page_sentences in enumerate(pages):
    folio = FIRST_FOLIO + pi
    marker = 0
    text_parts: list[str] = []
    band: list[str] = []
    entries_golden: list[dict] = []
    for s in page_sentences:
      text = s["text"].strip()
      # locate every app's marker position FIRST (an app attached to the
      # wrong sentence by the adapter is DROPPED AND COUNTED, never
      # guessed), then emit in position order
      placed: list[tuple[int, dict]] = []
      cursor = 0
      for app in s.get("apps", []):
        lemma = app["lemma"].strip()
        idx = _find_lemma_end(text, lemma, cursor)
        if idx is None:
          idx = _find_lemma_end(text, lemma, 0)
        if idx is None:
          dropped += 1
          continue
        placed.append((idx, app))
        cursor = idx
      placed.sort(key=lambda t: t[0])
      # two markers at one position would print adjacent digits ("¹²")
      # that extract as a single false marker — keep the first, count the rest
      deduped: list[tuple[int, dict]] = []
      for idx, app in placed:
        if deduped and idx == deduped[-1][0]:
          dropped += 1
          continue
        deduped.append((idx, app))
      placed = deduped

      pieces: list[str] = []
      pos = 0
      for idx, app in placed:
        marker += 1
        lemma = app["lemma"].strip()
        pieces.append(tex_escape(text[pos:idx]))
        pieces.append(rf"\textsuperscript{{{marker}}}")
        pos = idx
        raw = band_entry(marker, app)
        band.append(raw)
        entries_golden.append({
          "n": str(marker),
          "lemma": _cap(lemma),
          "lemma_wits": app.get("lemma_wits", []),
          "lemma_editors": app.get("lemma_editors", []),
          "readings": [
            {"text": r.get("text", "").strip(),
             "wits": r.get("wits", []), "editors": r.get("editors", []),
             "note": r.get("note", "")}
            for r in app.get("readings", [])
          ],
          "anchor_word": lemma.split()[-1],
          "band": raw,
        })
      pieces.append(tex_escape(text[pos:]))
      text_parts.append("".join(pieces))

    golden["pages"].append({
      "printed_page": str(folio),
      "entries": entries_golden,
      "text": " ".join(s["text"].strip() for s in page_sentences),
    })

    body.append(rf"\setcounter{{page}}{{{folio}}}")
    body.append(r"\noindent " + " ".join(text_parts) + r"\par")
    body.append(r"\vfill")
    if band:
      # one entry per printed line — the SC convention; wrapped continuation
      # lines never open with number-then-capital, so the boundary survives
      body.append(r"\noindent\rule{25mm}{0.4pt}\par\smallskip")
      body.append(r"{\footnotesize\setlength{\parskip}{0pt}")
      for b in band:
        body.append(r"\noindent " + tex_escape(b) + r"\par")
      body.append("}")
    body.append(r"\newpage")

  tex = "\n".join([
    r"\documentclass[11pt]{article}",
    r"\usepackage{fontspec}",
    r"\setmainfont{Times New Roman}",
    r"\usepackage{geometry}",
    r"\geometry{paperwidth=155mm, paperheight=235mm, margin=20mm}",
    r"\pagestyle{plain}",
    r"\setlength{\parindent}{0pt}",
    r"\begin{document}",
    *body,
    r"\end{document}",
    "",
  ])
  out_tex.write_text(unicodedata.normalize("NFC", tex), encoding="utf-8")
  out_golden.write_text(
    json.dumps(golden, ensure_ascii=False, indent=1), encoding="utf-8")
  napps = sum(len(p["entries"]) for p in golden["pages"])
  note = f", {dropped} apps dropped (unlocatable/duplicate position)" if dropped else ""
  print(f"typeset: {len(pages)} pages, {napps} apparatus entries{note} -> "
        f"{out_tex.name}, {out_golden.name}")


def _find_lemma_end(text: str, lemma: str, start: int) -> int | None:
  """Offset just after the lemma's last word in ``text`` (>= start).

  Word-boundary matching is load-bearing: a bare ``find`` once matched the
  lemma ``se`` inside ``posse`` and physically typeset the marker mid-word.
  The full lemma sequence is preferred; the last word alone is the fallback.
  """
  seq = re.compile(
    r"(?<![\w])" + r"\s+".join(re.escape(w) for w in lemma.split())
    + r"(?![\w])")
  m = seq.search(text, start)
  if m:
    return m.end()
  last = re.compile(r"(?<![\w])" + re.escape(lemma.split()[-1]) + r"(?![\w])")
  m = last.search(text, start)
  return m.end() if m else None


def main() -> int:
  if len(sys.argv) != 3:
    print("usage: typeset_golden.py edition.json outdir/", file=sys.stderr)
    return 2
  edition = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
  outdir = Path(sys.argv[2])
  outdir.mkdir(parents=True, exist_ok=True)
  stem = re.sub(r"[^A-Za-z0-9_-]+", "_", edition["title"])[:40]
  build(edition, outdir / f"{stem}.tex", outdir / f"{stem}.golden.json")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
