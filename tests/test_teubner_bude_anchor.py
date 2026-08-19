"""In-memory Teubner/Budé bands reach TEI without inventing lemma witnesses."""

from diorthosis.anchor import anchor_page
from diorthosis.conspectus import Registry
from diorthosis.model import Block, Document, Layer, Page, Source
from diorthosis.tei import TEI_NS, resolve_parsed, to_tei


def _registry() -> Registry:
  r = Registry()
  for s in ("A", "B", "M", "L", "V"):
    r.witnesses[s] = s
  return r


def _page(text: str, apparatus: str) -> Page:
  page = Page(index=0, printed_page="12")
  page.blocks.append(Block(
    layer=Layer.TEXT, text=text, source=Source.BORN_DIGITAL,
    generative=False, confidence=0.9,
  ))
  page.blocks.append(Block(
    layer=Layer.APPARATUS, text=apparatus, source=Source.BORN_DIGITAL,
    generative=False, confidence=0.9,
  ))
  return page


def test_teubner_negative_lemma_has_no_wit_in_tei() -> None:
  page = _page(
    "καὶ ὁ λόγος ἦν πρὸς τὸν θεόν",
    "12 λόγος] λέξις A : om. B",
  )
  registry = _registry()
  stats = anchor_page(page, registry)
  assert stats["entries"] == 1
  entry = page.blocks[1].entries[0]
  parsed = resolve_parsed(entry, registry)
  assert parsed is not None
  assert parsed.lemma == "λόγος"
  assert parsed.lemma_attribution.empty
  xml = to_tei(Document(source_name="teubner.pdf", pages=[page]),
              registry=registry)
  assert f"{{{TEI_NS}}}lem" in xml or "<lem" in xml
  assert 'wit="#wit-A"' in xml
  # the constituted reading is silent witnesses — not an invented cett.
  assert "cett" not in xml
  assert xml.count("<lem") == 1
  assert 'wit=' not in xml.split("<lem")[1].split(">")[0]


def test_plaoul_band_is_still_paragraph_not_teubner() -> None:
  page = _page(
    "est in Guillelmum",
    "18 est] om. R 20 in] om. R",
  )
  registry = _registry()
  registry.witnesses["R"] = "R"
  anchor_page(page, registry)
  entry = page.blocks[1].entries[0]
  assert entry.parsed_teubner is None
  assert entry.parsed_paragraph is not None


def test_bude_band_parses_two_loci() -> None:
  page = _page(
    "μυθῶδες ἐλεγχθήσεται ἐν ἀρχῇ",
    "5 μυθῶδες ABV : ἀσθενές L || 6 ἐλεγχθήσεται V : ἐλεχθήσεται A",
  )
  registry = _registry()
  stats = anchor_page(page, registry)
  assert stats["entries"] == 2
  first, second = page.blocks[1].entries
  assert first.parsed_bude is not None
  assert second.parsed_bude is not None
  assert resolve_parsed(first, registry).lemma == "μυθῶδες"
  assert resolve_parsed(first, registry).readings[0].text == "ἀσθενές"
