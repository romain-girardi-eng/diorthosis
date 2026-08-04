"""Round-trip checks compare the Markdown and TEI views of one document."""

from __future__ import annotations

from pathlib import Path

from diorthosis.cli import main
from diorthosis.conspectus import Registry
from diorthosis.md import to_markdown
from diorthosis.model import (
  Anchor,
  ApparatusEntry,
  Block,
  Document,
  Layer,
  Page,
  Source,
)
from diorthosis.roundtrip import check_roundtrip
from diorthosis.tei import to_tei


def _block(layer: Layer, text: str) -> Block:
  return Block(
    layer=layer,
    text=text,
    source=Source.BORN_DIGITAL,
    generative=False,
    confidence=0.9,
  )


def _document() -> tuple[Document, Registry]:
  doc = Document(source_name="ed.pdf", ingest="borndigital")
  page = Page(index=3, printed_page="294")
  apparatus = _block(Layer.APPARATUS, "")
  apparatus.entries = [
    ApparatusEntry(
      raw="1 Beta : delta A",
      anchor=Anchor(
        kind="marker",
        value="1",
        block_index=0,
        char_offset=11,
        digit_start=10,
        digit_end=11,
      ),
    ),
    ApparatusEntry(raw="2 prose note the grammar refuses"),
  ]
  page.blocks = [
    _block(Layer.TEXT, "alpha beta1 gamma"),
    apparatus,
    _block(Layer.TRANSLATION, "Alpha translated into English."),
    _block(Layer.NOTES, "A short editorial note."),
  ]
  doc.pages = [page]

  registry = Registry()
  registry.witnesses["A"] = "codex A"
  return doc, registry


def _write_outputs(tmp_path: Path) -> tuple[Path, Path]:
  doc, registry = _document()
  md_path = tmp_path / "ed.md"
  tei_path = tmp_path / "ed.tei.xml"
  md_path.write_text(
    to_markdown(doc, tei_name=tei_path.name),
    encoding="utf-8",
  )
  tei_path.write_text(to_tei(doc, registry=registry), encoding="utf-8")
  return md_path, tei_path


def test_roundtrip_accepts_matching_outputs(tmp_path: Path) -> None:
  md_path, tei_path = _write_outputs(tmp_path)

  assert check_roundtrip(md_path, tei_path) == []


def test_roundtrip_detects_missing_apparatus_entry(tmp_path: Path) -> None:
  md_path, tei_path = _write_outputs(tmp_path)
  content = md_path.read_text(encoding="utf-8")
  entry = "2 prose note the grammar refuses\n"
  assert content.count(entry) == 1
  md_path.write_text(content.replace(entry, "", 1), encoding="utf-8")

  assert check_roundtrip(md_path, tei_path)


def test_roundtrip_detects_changed_folio(tmp_path: Path) -> None:
  md_path, tei_path = _write_outputs(tmp_path)
  content = md_path.read_text(encoding="utf-8")
  page_header = "## page 294 (file index 3)"
  assert content.count(page_header) == 1
  md_path.write_text(
    content.replace(page_header, "## page 295 (file index 3)", 1),
    encoding="utf-8",
  )

  assert check_roundtrip(md_path, tei_path)


def test_roundtrip_cli_success(tmp_path: Path, capsys) -> None:
  md_path, tei_path = _write_outputs(tmp_path)

  assert main(["roundtrip", str(md_path), str(tei_path)]) == 0
  captured = capsys.readouterr()
  assert captured.out == "OK: md-ce and TEI carry the same content\n"
  assert captured.err == ""


def test_roundtrip_preserves_refs_like_source_lines(tmp_path: Path) -> None:
  text = _block(Layer.TEXT, "*refs: text source line*")
  text.inline_refs = ["A"]
  apparatus = _block(Layer.APPARATUS, "")
  apparatus.entries = [ApparatusEntry(raw="*refs: apparatus source line*")]
  page = Page(
    index=4,
    printed_page="295",
    blocks=[
      text,
      apparatus,
      _block(Layer.TRANSLATION, "*refs: translation source line*"),
      _block(Layer.NOTES, "*refs: notes source line*"),
    ],
  )
  doc = Document(source_name="refs.pdf", pages=[page], ingest="borndigital")
  md_path = tmp_path / "refs.md"
  tei_path = tmp_path / "refs.tei.xml"
  md_path.write_text(to_markdown(doc), encoding="utf-8")
  tei_path.write_text(to_tei(doc), encoding="utf-8")

  assert check_roundtrip(md_path, tei_path) == []
