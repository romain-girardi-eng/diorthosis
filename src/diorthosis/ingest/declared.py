"""Honor a producer's *unambiguous* region name as a layer.

OCR engines and PAGE/ALTO/hOCR exporters label regions. Most labels are
layout guesses (``paragraph``, ``footer``, ``ocr_caption``) and have no
mapping onto a critical edition's registers — those stay ``UNKNOWN``.
A few names *are* the registers, or page furniture, and refusing them
leaves every OCR block unclassified even when the scholar already tagged
the apparatus.

This module is the one place that mapping lives. It is fail-closed:
anything not on the allow-list is ``UNKNOWN``. ``paragraph``, ``text``,
``body`` and ``footer`` are deliberately absent — they are layout, not
registers, and existing fixtures pin that refusal.
"""

from __future__ import annotations

import re

from ..model import Layer

_SEP = re.compile(r"[\s_\-]+")

# Normalized key → layer. Keys are lower-case, separators collapsed to '-'.
_HONOR: dict[str, Layer] = {
  "apparatus": Layer.APPARATUS,
  "critical-apparatus": Layer.APPARATUS,
  "app-crit": Layer.APPARATUS,
  "appcrit": Layer.APPARATUS,
  "translation": Layer.TRANSLATION,
  "facing-translation": Layer.TRANSLATION,
  "heading": Layer.HEADING,
  "title": Layer.HEADING,
  "ocr-title": Layer.HEADING,
  "page-number": Layer.PAGE_NUMBER,
  "pageno": Layer.PAGE_NUMBER,
  "ocr-pageno": Layer.PAGE_NUMBER,
  "folio": Layer.PAGE_NUMBER,
  "header": Layer.RUNNING_HEAD,
  "running-head": Layer.RUNNING_HEAD,
  "ocr-header": Layer.RUNNING_HEAD,
  "notes": Layer.NOTES,
}


def _normalize(name: str) -> str:
  token = _SEP.sub("-", name.strip().lower()).strip("-")
  if token.startswith("ocr-") and token not in _HONOR:
    bare = token[4:]
    if bare in _HONOR:
      return bare
  return token


def layer_from_declared_type(name: str | None) -> Layer:
  """Map a producer label onto a layer, or ``UNKNOWN`` if it is not sure."""
  if not name:
    return Layer.UNKNOWN
  return _HONOR.get(_normalize(name), Layer.UNKNOWN)
