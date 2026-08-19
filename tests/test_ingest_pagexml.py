"""PAGE-XML ingestion: OCR-agnostic, permanently marked generative."""

from __future__ import annotations

import pytest

from diorthosis.ingest import ingest_pagexml
from diorthosis.model import Layer, Source

PAGE = """<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">
  <Metadata><Creator>kraken</Creator></Metadata>
  <Page imageFilename="p188.png" imageWidth="2481" imageHeight="3508">
    <ReadingOrder>
      <OrderedGroup id="ro_0"><RegionRefIndexed index="0" regionRef="r_1"/></OrderedGroup>
    </ReadingOrder>
    <TextRegion id="r_1" type="paragraph">
      <Coords points="300,400 2100,400 2100,700 300,700"/>
      <TextLine id="l_1">
        <Coords points="300,400 2100,400 2100,460 300,460"/>
        <TextEquiv index="0" conf="0.96"><Unicode>καὶ ὁ λόγος</Unicode></TextEquiv>
        <TextEquiv index="1" conf="0.20"><Unicode>καὶ ὁ νόμος</Unicode></TextEquiv>
      </TextLine>
      <TextLine id="l_2">
        <Coords points="300,480 2100,480 2100,540 300,540"/>
        <TextEquiv conf="0.90"><Unicode>ἐστίν</Unicode></TextEquiv>
      </TextLine>
    </TextRegion>
  </Page>
</PcGts>
"""

# A line with no TextEquiv of its own, and a @conf outside ConfSimpleType's
# [0, 1] range (a producer writing percentages).
WORD_PAGE = """<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">
  <Page imageFilename="p1.png" imageWidth="10" imageHeight="10">
    <TextRegion id="r_1">
      <TextLine id="l_1">
        <Word id="w_1"><TextEquiv conf="88"><Unicode>Πρόλογος</Unicode></TextEquiv></Word>
        <Word id="w_2"><TextEquiv><Unicode>αὄ</Unicode></TextEquiv></Word>
      </TextLine>
    </TextRegion>
  </Page>
</PcGts>
"""


def _write(tmp_path, name: str, text: str):
  f = tmp_path / name
  f.write_text(text, encoding="utf-8")
  return f


def test_pagexml_blocks_are_generative_with_confidence(tmp_path) -> None:
  doc = ingest_pagexml([_write(tmp_path, "p1.xml", PAGE)])
  assert doc.ingest == "pagexml"
  assert doc.any_generative
  [block] = doc.pages[0].blocks
  assert block.layer is Layer.UNKNOWN     # @type=paragraph is not a register
  assert block.source is Source.OCR and block.generative
  assert block.text == "καὶ ὁ λόγος\nἐστίν"
  assert block.confidence == pytest.approx(0.93)   # mean(0.96, 0.90)


def test_ranked_alternatives_are_not_merged(tmp_path) -> None:
  doc = ingest_pagexml([_write(tmp_path, "p1.xml", PAGE)])
  [block] = doc.pages[0].blocks
  assert "νόμος" not in block.text        # index=1 alternative never read


def test_declared_type_and_reading_order_are_reported_not_applied(tmp_path) -> None:
  doc = ingest_pagexml([_write(tmp_path, "p1.xml", PAGE)])
  [block] = doc.pages[0].blocks
  assert "@type=paragraph" in block.evidence
  assert "ReadingOrder declared, not applied" in block.evidence
  assert doc.pages[0].printed_page is None   # PAGE declares no printed folio


def test_word_fallback_and_out_of_range_conf_is_dropped(tmp_path) -> None:
  doc = ingest_pagexml([_write(tmp_path, "p1.xml", WORD_PAGE)])
  [block] = doc.pages[0].blocks
  assert block.text == "Πρόλογος αὄ"
  assert block.confidence == 0.0          # conf=88 is not ConfSimpleType


def test_declared_apparatus_type_is_honored(tmp_path) -> None:
  xml = PAGE.replace('type="paragraph"', 'type="apparatus"')
  doc = ingest_pagexml([_write(tmp_path, "p1.xml", xml)])
  [block] = doc.pages[0].blocks
  assert block.layer is Layer.APPARATUS
  assert "@type=apparatus" in block.evidence


def test_non_page_input_is_refused(tmp_path) -> None:
  alto = '<?xml version="1.0"?><alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"/>'
  with pytest.raises(ValueError, match="not PAGE-XML"):
    ingest_pagexml([_write(tmp_path, "p1.xml", alto)])
