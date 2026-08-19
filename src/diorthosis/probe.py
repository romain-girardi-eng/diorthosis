"""Suggest the three flags a first ``build`` needs, from a page sample.

A born-digital edition is unusable without ``--pages``, ``--conspectus-page``
and ``--text-lang``. Those are the scholar's to declare; this module only
*proposes* them, from geometry already classified by regreek. A suggestion
is not a certification — ``build`` still has to succeed on its own.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

from .ingest.borndigital import ingest_pdf
from .model import Layer

_CONSPECTUS_HEAD = re.compile(
  r"sigl|conspectus|abr[eé]viations|manuscripts", re.I)


@dataclass
class PageHint:
  index: int
  layers: Counter[str]
  two_column: bool
  greek_body: bool
  latin_body: bool
  has_apparatus: bool


@dataclass
class ProbeReport:
  pdf: str
  page_count: int
  sampled: list[int]
  edition_pages: list[int]
  pages_spec: str | None
  conspectus_page: int | None
  text_lang: str
  two_column_pages: list[int]
  notes: list[str] = field(default_factory=list)

  @property
  def command(self) -> str:
    parts = ["diorthosis build", self.pdf]
    if self.pages_spec:
      parts.append(f"--pages {self.pages_spec}")
    if self.conspectus_page is not None:
      parts.append(f"--conspectus-page {self.conspectus_page}")
    if self.text_lang != "grc":
      parts.append(f"--text-lang {self.text_lang}")
    parts.append("-o out/")
    return " ".join(parts)


def count_pdf_pages(pdf_path: str | Path) -> int:
  with Path(pdf_path).open("rb") as fh:
    document = PDFDocument(PDFParser(fh))
    return sum(1 for _ in PDFPage.create_pages(document))


def sample_indices(page_count: int, max_pages: int) -> list[int]:
  """Spread a cheap sample: the opening, the close, and even mid-page hits."""
  if page_count <= 0:
    return []
  if page_count <= max_pages:
    return list(range(page_count))
  head_n = min(8, page_count)
  tail_n = min(4, page_count - head_n)
  head = list(range(head_n))
  tail = list(range(page_count - tail_n, page_count))
  taken = set(head + tail)
  budget = max_pages - len(taken)
  lo, hi = head_n, page_count - tail_n
  if budget <= 0 or hi <= lo:
    return sorted(taken)[:max_pages]
  step = (hi - lo) / (budget + 1)
  mid = [int(lo + i * step) for i in range(1, budget + 1)]
  return sorted(set(head + mid + tail))


def format_ranges(pages: list[int]) -> str:
  if not pages:
    return ""
  ordered = sorted(set(pages))
  runs: list[tuple[int, int]] = []
  start = prev = ordered[0]
  for page in ordered[1:]:
    if page == prev + 1:
      prev = page
      continue
    runs.append((start, prev))
    start = prev = page
  runs.append((start, prev))
  return ",".join(
    str(a) if a == b else f"{a}-{b}" for a, b in runs)


def cluster_edition(sampled: list[int], edition: set[int], max_gap: int
                    ) -> list[int]:
  """Fill small gaps between sampled edition-like pages.

  The fill is a suggestion, not a measurement: pages between two hits were
  not classified. ``max_gap`` is the largest unsampled stretch we will
  claim as edition-like.
  """
  hits = [p for p in sampled if p in edition]
  if not hits:
    return []
  filled: set[int] = set(hits)
  for a, b in zip(hits, hits[1:], strict=False):
    if 0 < b - a <= max_gap:
      filled.update(range(a, b + 1))
  return sorted(filled)


def _hint(page) -> PageHint:
  layers: Counter[str] = Counter(b.layer.value for b in page.blocks)
  evidence = " ".join(b.evidence for b in page.blocks)
  two_column = "two-column" in evidence
  greek = any(
    b.layer is Layer.TEXT and "Greek-script" in b.evidence
    for b in page.blocks)
  latin = any(
    b.layer is Layer.TRANSLATION
    or (b.layer is Layer.TEXT and "Latin-script" in b.evidence)
    for b in page.blocks)
  has_app = layers[Layer.APPARATUS.value] > 0 or layers[Layer.NOTES.value] > 0
  return PageHint(
    index=page.index,
    layers=layers,
    two_column=two_column,
    greek_body=greek,
    latin_body=latin and not greek,
    has_apparatus=has_app,
  )


def _is_edition(hint: PageHint) -> bool:
  body = hint.layers[Layer.TEXT.value] + hint.layers[Layer.TRANSLATION.value]
  return body > 0 and hint.has_apparatus


def _conspectus_on_pages(pdf_path: str, pages: list[int]) -> int | None:
  """First page in ``pages`` whose heading matches the conspectus locator."""
  from pdfminer.high_level import extract_pages
  from pdfminer.layout import LAParams

  if not pages:
    return None
  numbers = sorted(set(pages))
  for i, layout in enumerate(extract_pages(
      pdf_path, page_numbers=numbers, laparams=LAParams(all_texts=True))):
    bits: list[str] = []
    for el in layout:
      get_text = getattr(el, "get_text", None)
      if get_text is not None:
        bits.append(get_text())
    text = "".join(bits)
    if _CONSPECTUS_HEAD.search(text.split("\n", 3)[0] if text else "") or (
      _CONSPECTUS_HEAD.search(text[:200]) and ("=" in text or "[" in text)
    ):
      return numbers[i]
  return None


def probe_pdf(pdf_path: str | Path, pages: list[int] | None = None,
              max_pages: int = 24) -> ProbeReport:
  path = str(pdf_path)
  total = count_pdf_pages(path)
  sampled = pages if pages is not None else sample_indices(total, max_pages)
  doc = ingest_pdf(path, pages=sampled)
  hints = [_hint(page) for page in doc.pages]
  edition = {h.index for h in hints if _is_edition(h)}
  step = 8
  if len(sampled) >= 2:
    gaps = [b - a for a, b in zip(sampled, sampled[1:], strict=False) if b > a]
    if gaps:
      step = max(8, 2 * max(gaps))
  clustered = cluster_edition(sampled, edition, max_gap=step)
  greek = sum(1 for h in hints if h.greek_body)
  latin = sum(1 for h in hints if h.latin_body)
  text_lang = "la" if latin > greek else "grc"

  front = list(range(min(60, total)))
  conspectus = _conspectus_on_pages(path, front)

  notes: list[str] = []
  if pages is None and total > len(sampled):
    notes.append(
      f"sampled {len(sampled)} of {total} pages; inspect the edges of "
      f"the suggested --pages range before a full build")
  if not clustered:
    notes.append(
      "no sampled page carried both a body band and an apparatus/notes "
      "band — pass --pages yourself, or raise --max-pages")
  if conspectus is None:
    notes.append(
      "no conspectus heading in the first "
      f"{min(60, total)} pages — pass --conspectus-page or --sigla")

  return ProbeReport(
    pdf=Path(path).name,
    page_count=total,
    sampled=sampled,
    edition_pages=clustered,
    pages_spec=format_ranges(clustered) or None,
    conspectus_page=conspectus,
    text_lang=text_lang,
    two_column_pages=[h.index for h in hints if h.two_column],
    notes=notes,
  )


def render_report(report: ProbeReport) -> str:
  lines = [
    f"pdf: {report.pdf} ({report.page_count} pages)",
    f"sampled: {format_ranges(report.sampled) or 'none'}",
  ]
  if report.pages_spec:
    lines.append(f"edition-like pages: {report.pages_spec}")
  else:
    lines.append("edition-like pages: (none in the sample)")
  if report.conspectus_page is not None:
    lines.append(f"conspectus candidate: page {report.conspectus_page}")
  else:
    lines.append("conspectus candidate: (none found)")
  lines.append(f"suggested --text-lang: {report.text_lang}")
  if report.two_column_pages:
    lines.append(
      f"two-column pages: {format_ranges(report.two_column_pages)}")
  for note in report.notes:
    lines.append(f"note: {note}")
  lines.append(f"suggested: {report.command}")
  return "\n".join(lines)
