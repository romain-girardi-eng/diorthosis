"""Declared OCR/PAGE/ALTO region names → layers, fail-closed."""

from diorthosis.ingest.declared import layer_from_declared_type
from diorthosis.model import Layer


def test_unambiguous_registers() -> None:
  assert layer_from_declared_type("apparatus") is Layer.APPARATUS
  assert layer_from_declared_type("critical-apparatus") is Layer.APPARATUS
  assert layer_from_declared_type("app_crit") is Layer.APPARATUS
  assert layer_from_declared_type("translation") is Layer.TRANSLATION
  assert layer_from_declared_type("heading") is Layer.HEADING
  assert layer_from_declared_type("page-number") is Layer.PAGE_NUMBER
  assert layer_from_declared_type("header") is Layer.RUNNING_HEAD
  assert layer_from_declared_type("running_head") is Layer.RUNNING_HEAD
  assert layer_from_declared_type("notes") is Layer.NOTES


def test_hocr_logical_classes_that_are_furniture() -> None:
  assert layer_from_declared_type("ocr_header") is Layer.RUNNING_HEAD
  assert layer_from_declared_type("ocr_pageno") is Layer.PAGE_NUMBER
  assert layer_from_declared_type("ocr_title") is Layer.HEADING


def test_layout_guesses_stay_unknown() -> None:
  assert layer_from_declared_type("paragraph") is Layer.UNKNOWN
  assert layer_from_declared_type("text") is Layer.UNKNOWN
  assert layer_from_declared_type("body") is Layer.UNKNOWN
  assert layer_from_declared_type("footer") is Layer.UNKNOWN
  assert layer_from_declared_type("ocr_footer") is Layer.UNKNOWN
  assert layer_from_declared_type("ocr_caption") is Layer.UNKNOWN
  assert layer_from_declared_type(None) is Layer.UNKNOWN
  assert layer_from_declared_type("") is Layer.UNKNOWN
