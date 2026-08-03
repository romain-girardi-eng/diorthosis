"""ALTO ingestion: OCR-agnostic, permanently marked generative."""

from __future__ import annotations

from diorthosis.ingest import ingest_alto
from diorthosis.model import Layer, Source

ALTO = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
  <Layout><Page><PrintSpace>
    <TextBlock ID="b1">
      <TextLine>
        <String CONTENT="καὶ" WC="0.98"/><SP/><String CONTENT="ὁ" WC="0.91"/>
        <SP/><String CONTENT="λόγος" WC="0.95"/>
      </TextLine>
    </TextBlock>
  </PrintSpace></Page></Layout>
</alto>
"""


def test_alto_blocks_are_generative_with_confidence(tmp_path) -> None:
  f = tmp_path / "p1.xml"
  f.write_text(ALTO, encoding="utf-8")
  doc = ingest_alto([f])
  assert doc.ingest == "alto"
  assert doc.any_generative
  [block] = doc.pages[0].blocks
  assert block.layer is Layer.UNKNOWN     # no layer guessing on OCR input
  assert block.source is Source.OCR and block.generative
  assert block.text == "καὶ ὁ λόγος"
  assert 0.9 < block.confidence < 1.0
