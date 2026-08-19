"""hOCR ingestion: OCR-agnostic, permanently marked generative."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from diorthosis.ingest import ingest_hocr
from diorthosis.model import Layer, Source

# Tesseract shape (ocr_page > ocr_carea > ocr_par > ocr_line > ocrx_word),
# but serialized HTML5: the unclosed <meta> and the &nbsp; are what a strict
# XML parser chokes on — see test_hocr_is_html_not_xml.
HOCR = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
 "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
 <head>
  <meta charset="utf-8">
  <meta name='ocr-system' content='tesseract 5.3.4'>
  <meta name='ocr-capabilities' content='ocr_page ocr_carea ocr_par ocr_line ocrx_word'>
 </head>
 <body>
  <div class='ocr_page' id='page_1'
       title='image "p188.png"; bbox 0 0 2481 3508; ppageno 0; lpageno 188'>
   <div class='ocr_carea' id='block_1_1' title="bbox 300 400 2100 700">
    <p class='ocr_par' id='par_1_1' lang='grc' title="bbox 300 400 2100 700">
     <span class='ocr_line' id='line_1_1' title="bbox 300 400 2100 460; x_size 40">
      <span class='ocrx_word' id='word_1_1_1' title='bbox 300 400 500 460; x_wconf 96'>καὶ</span>
      <span class='ocrx_word' id='word_1_1_2' title='bbox 520 400 560 460; x_wconf 88'>ὁ</span>
      <span class='ocrx_word' id='word_1_1_3' title='bbox 580 400 900 460; x_wconf 94'>λόγος</span>
     </span>
     <span class='ocr_line' id='line_1_2' title="bbox 300 480 2100 540">
      <span class='ocrx_word' id='w_1_2_1'
            title='bbox 300 480 700 540; x_wconf 92'>&nbsp;ἐστίν</span>
     </span>
    </p>
   </div>
  </div>
 </body>
</html>
"""

# kraken shape: no ocr_carea, no ocr_par, no word confidences — and a logical
# class the engine did declare.
FLAT_HOCR = """<html><body>
 <div class='ocr_page' title='bbox 0 0 100 100'>
  <span class='ocr_line ocr_header' title='bbox 1 1 99 9'>Πρόλογος</span>
 </div>
</body></html>
"""


def _write(tmp_path, name: str, text: str):
  f = tmp_path / name
  f.write_text(text, encoding="utf-8")
  return f


def test_hocr_blocks_are_generative_with_confidence(tmp_path) -> None:
  doc = ingest_hocr([_write(tmp_path, "p1.html", HOCR)])
  assert doc.ingest == "hocr"
  assert doc.any_generative
  [block] = doc.pages[0].blocks
  assert block.layer is Layer.UNKNOWN     # no layer guessing on OCR input
  assert block.source is Source.OCR and block.generative
  assert block.text == "καὶ ὁ λόγος\nἐστίν"
  # x_wconf is the spec's 0-100 scale: 96/88/94/92 → 0.925, not 92.5
  assert 0.9 < block.confidence < 1.0


def test_lpageno_is_the_citable_folio(tmp_path) -> None:
  doc = ingest_hocr([_write(tmp_path, "p1.html", HOCR)])
  # lpageno is the number printed on the page; ppageno 0 is the scan index
  assert doc.pages[0].printed_page == "188"


def test_hocr_is_html_not_xml(tmp_path) -> None:
  # The reason this adapter does not use xml.etree, as ALTO does.
  with pytest.raises(ET.ParseError):
    ET.fromstring(HOCR)
  assert ingest_hocr([_write(tmp_path, "p1.html", HOCR)]).pages[0].blocks


def test_flat_hocr_still_yields_a_block_and_claims_no_confidence(tmp_path) -> None:
  doc = ingest_hocr([_write(tmp_path, "p1.html", FLAT_HOCR)])
  [block] = doc.pages[0].blocks
  assert block.text == "Πρόλογος"
  assert block.confidence == 0.0          # no x_wconf: nothing claimed
  assert block.layer is Layer.RUNNING_HEAD  # ocr_header is page furniture
  assert "ocr_header" in block.evidence
  assert "honored as running_head" in block.evidence


def test_non_hocr_input_is_refused(tmp_path) -> None:
  f = _write(tmp_path, "p1.html", "<html><body><p>plain text</p></body></html>")
  with pytest.raises(ValueError, match="not hOCR"):
    ingest_hocr([f])
