"""PAGE-XML ingestion — the OCR-agnostic path, PRImA flavour.

diorthosis never calls an OCR engine. It consumes the standard output formats
instead: kraken, eScriptorium, Transkribus, OCR-D and Calamari all export
PAGE (or ALTO/hOCR, see the sibling adapters). Whatever produced the file, its
text is **generative** — a recognition model's guess, not a decoding of a
character stream — and every block is permanently marked so.

Four refusals:

- **No layer classification.** ``TextRegion/@type`` exists ("paragraph",
  "heading", "footer", "page-number"…), but it is the producer's layout guess
  and its vocabulary does not name the registers of a critical edition (text /
  apparatus / translation). Blocks arrive as ``UNKNOWN``; the declared
  ``@type`` is copied verbatim into ``evidence`` so nothing is lost.
- **No reordering.** ``<ReadingOrder>`` may declare a sequence that differs
  from document order. Applying it would silently rewrite the page; the
  document order is kept and the declaration is reported in ``evidence``,
  for a human to act on.
- **No merged alternatives.** PAGE allows several ``TextEquiv`` per element,
  ranked by ``@index``. Only the primary one is read: concatenating ranked
  alternatives would produce a reading no engine ever proposed.
- **No rescaled confidence.** ``@conf`` is a ``ConfSimpleType``, fixed by the
  schema to [0, 1]. Unlike hOCR's ``x_wconf`` (spec'd 0-100, hence normalized
  by the sibling adapter), an out-of-range PAGE value is a producer bug and
  not another scale — guessing which would corrupt the number, so it is
  dropped and the block simply reports less evidence.

One PAGE file describes exactly one page (``PcGts`` → one ``Page``), so files
are ingested one per page, in order, as with ALTO. PAGE declares no printed
folio, so ``printed_page`` stays ``None``: the citable number must come from
elsewhere (the hOCR adapter has ``lpageno``; a born-digital PDF has the
printed number itself).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ..model import Block, Document, Layer, Page, Source


def _local(tag: str) -> str:
  return tag.rsplit("}", 1)[-1]


def _children(el: ET.Element, name: str) -> list[ET.Element]:
  return [c for c in el if _local(c.tag) == name]


def _descendants(el: ET.Element, name: str) -> list[ET.Element]:
  return [c for c in el.iter() if c is not el and _local(c.tag) == name]


def _conf(raw: str | None) -> float | None:
  """Read a ``@conf``; drop anything outside the schema's [0, 1] range."""
  if raw is None:
    return None
  try:
    value = float(raw)
  except ValueError:
    return None
  return value if 0.0 <= value <= 1.0 else None


def _index(equiv: ET.Element) -> int:
  try:
    return int(equiv.get("index") or 0)
  except ValueError:
    return 0


def _text_equiv(el: ET.Element) -> tuple[str, float | None]:
  """The element's primary ``TextEquiv``: its text and declared confidence.

  Lowest ``@index`` wins, first-in-document on a tie. ``Unicode`` is the
  schema's required carrier; ``PlainText`` is read only when it is absent.
  """
  equivs = _children(el, "TextEquiv")
  if not equivs:
    return "", None
  best = min(equivs, key=_index)
  for carrier in ("Unicode", "PlainText"):
    found = _children(best, carrier)
    if found:
      return (found[0].text or "").strip(), _conf(best.get("conf"))
  return "", _conf(best.get("conf"))


def _text_regions(el: ET.Element) -> list[ET.Element]:
  """Outermost ``TextRegion`` elements, in document order.

  PAGE permits a region to nest inside another. Only the outer one becomes a
  block — its lines are collected recursively, so nested content is kept
  without being emitted twice.
  """
  found: list[ET.Element] = []
  for child in el:
    if _local(child.tag) == "TextRegion":
      found.append(child)
    else:
      found.extend(_text_regions(child))
  return found


def _line_text(line: ET.Element, confs: list[float]) -> str:
  """One line's text, falling back to its ``Word`` children.

  Unlike ALTO (``<SP/>``) and hOCR (serialized whitespace), PAGE gives no
  separator between ``Word`` siblings: word boundaries *are* the element
  boundaries, so a single space is the format's own reading, not an
  invention. This path is used only when the line declares no ``TextEquiv``.
  """
  text, conf = _text_equiv(line)
  if conf is not None:
    confs.append(conf)
  if text:
    return text
  words = [_text_equiv(w) for w in _descendants(line, "Word")]
  confs.extend(c for _, c in words if c is not None)
  return " ".join(t for t, _ in words if t)


def ingest_pagexml(paths: list[str | Path]) -> Document:
  """Ingest one PAGE-XML file per page, in order."""
  doc = Document(
    source_name=Path(paths[0]).stem if paths else "pagexml", ingest="pagexml")
  for i, p in enumerate(paths):
    root = ET.parse(str(p)).getroot()
    if _local(root.tag) != "PcGts":
      raise ValueError(
        f"{p}: not PAGE-XML — root is <{_local(root.tag)}>, expected <PcGts>")
    sources = _children(root, "Page")
    if not sources:
      raise ValueError(f"{p}: PAGE-XML file declares no <Page>")
    src = sources[0]
    declared_order = bool(_children(src, "ReadingOrder"))
    page = Page(index=i, printed_page=None)
    for region in _text_regions(src):
      confs: list[float] = []
      lines = [t for ln in _descendants(region, "TextLine")
               if (t := _line_text(ln, confs))]
      if not lines:
        text, conf = _text_equiv(region)  # region-level TextEquiv
        if conf is not None:
          confs.append(conf)
        lines = [ln for ln in text.splitlines() if ln.strip()]
      if not lines:
        continue
      region_type = region.get("type")
      evidence = "PAGE-XML TextRegion"
      if region_type:
        evidence += f" (@type={region_type})"
      evidence += "; OCR output — text is generated, not decoded"
      if declared_order:
        evidence += "; ReadingOrder declared, not applied (document order kept)"
      page.blocks.append(Block(
        layer=Layer.UNKNOWN,
        text="\n".join(lines),
        source=Source.OCR,
        generative=True,
        confidence=(sum(confs) / len(confs)) if confs else 0.0,
        evidence=evidence,
      ))
    doc.pages.append(page)
  return doc
