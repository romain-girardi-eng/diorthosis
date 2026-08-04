#!/usr/bin/env python3
"""Adapter: a scholar's TEI edition (parallel-segmentation apparatus) into
the neutral edition JSON that typeset_golden.py consumes.

The scholars' encoding is the ground truth; this adapter only re-serializes
it. Every <app> whose shape the adapter cannot represent faithfully is
SKIPPED AND COUNTED — never approximated — so the golden never contains a
guess. Skipped shapes (reported): empty or missing <lem>, nested <app>,
<rdgGrp>, lemma text not locatable in its sentence after normalization.

Usage: tei_to_edition.py scholar.xml out_edition.json [--max-sentences N]
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from lxml import etree

TEI = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def q(tag: str) -> str:
  return f"{{{TEI}}}{tag}"


def norm_space(s: str) -> str:
  return re.sub(r"\s+", " ", s)


def tight(s: str) -> str:
  """Attach detached punctuation (token-per-element encodings put spaces
  around it: ``Ἀβραάμ .`` -> ``Ἀβραάμ.``), and drop the NT in-text anchor
  sigla (⸀⸂⸃⸄⸅…, U+2E00-2E0F): they mark spans in the SOURCE edition's own
  convention and are not printed inside a numeric-marker band."""
  s = re.sub(r"[⸀-⸏]", "", s)
  # NT double brackets (interpolations) transliterate to the plain-text
  # convention — they are also md-ce's reserved delimiters (I4)
  s = s.replace("⟦", "[[").replace("⟧", "]]")
  return norm_space(re.sub(r"\s+([,.;·:!?])", r"\1", s)).strip()


# Leiden-convention rendering of editorial elements: this is how a PRINTED
# edition serializes them, and the tool's grammar treats bracketed material
# as text (never as attribution) — exactly the printed semantics.
_DECOR = {"surplus": ("{", "}"), "supplied": ("<", ">")}


def text_of(el: etree._Element, skip: set[str] = frozenset()) -> str:
  """Flattened text of an element, skipping listed local tags entirely."""
  parts: list[str] = []

  def walk(e: etree._Element) -> None:
    if not isinstance(e.tag, str):     # comments / processing instructions
      if e.tail:
        parts.append(e.tail)
      return
    local = etree.QName(e).localname
    if local in skip:
      if e.tail:
        parts.append(e.tail)
      return
    open_, close = _DECOR.get(local, ("", ""))
    parts.append(open_)
    if e.text:
      parts.append(e.text)
    for c in e:
      walk(c)
    parts.append(close)
    if e.tail:
      parts.append(e.tail)

  if el.text:
    parts.append(el.text)
  for c in el:
    walk(c)
  return norm_space("".join(parts))


_BIB_YEAR = re.compile(r"\d{4}.*$")
# the optional second lowercase letter is a SUPERSCRIPT distinguisher in
# print (Nᵘ, Eᵃ, Pˣ — flat forms Nu, Ea, Px)
_SIGLUM_SHAPE = re.compile(r"^[A-Za-zΑ-Ωα-ωϘ-ϡ][a-z]?[0-9]?\*?$")


def editor_name(tok: str) -> str:
  """A printable editor name from an LDLT bibliographic id: the PRINTED
  edition says ``Kübler``, the TEI's @source says ``Kübler1896a``."""
  return _BIB_YEAR.sub("", tok)


def wit_tokens(el: etree._Element, attr: str, id_to_sig: dict[str, str]) -> list[str]:
  raw = el.get(attr) or ""
  out = []
  for tok in raw.split():
    tok = tok.removeprefix("#")
    out.append(id_to_sig.get(tok, tok))
  return list(dict.fromkeys(out))


def split_attribution(wits: list[str], editors: list[str]) -> tuple[list[str], list[str]]:
  """Witness tokens that are not siglum-shaped (``ed. pr.``) belong on the
  editor side of a printed band; bibliographic years come off editor ids."""
  real_wits = [w for w in wits if _SIGLUM_SHAPE.match(w)]
  spilled = [w for w in wits if not _SIGLUM_SHAPE.match(w)]
  eds = [editor_name(e) for e in editors] + spilled
  return real_wits, eds


def load_witnesses(root: etree._Element) -> tuple[dict[str, str], dict[str, str]]:
  """(siglum -> description, xml:id -> siglum) from the <listWit>."""
  witnesses: dict[str, str] = {}
  id_to_sig: dict[str, str] = {}
  for wit in root.iter(q("witness")):
    xid = wit.get(XML_ID) or ""
    abbr = wit.find(q("abbr"))
    # the FULL abbr content: a superscript siglum letter is a child
    # element ("N<hi rend='superscript'>u</hi>" = Nᵘ, flat form "Nu") —
    # glued ONLY for that shape; "ed. pr." keeps its spaces
    siglum = (norm_space(text_of(abbr)) if abbr is not None else "") or xid
    if re.fullmatch(r"[A-ZΑ-Ω] [a-z0-9*]", siglum):
      siglum = siglum.replace(" ", "")
    # a witness may nest a whole family <listWit>: its own description is
    # only what is NOT inside the nested list
    desc = text_of(wit, skip={"abbr", "listWit", "witness"})
    if not siglum:
      continue
    witnesses[siglum] = desc or siglum
    if xid:
      id_to_sig[xid] = siglum
  # a consensus family may be declared as a listWit carrying its own
  # xml:id (α = "Pietro's first version") — cited like any witness
  for lw in root.iter(q("listWit")):
    xid = lw.get(XML_ID) or ""
    if xid and xid not in id_to_sig:
      head = lw.find(q("head"))
      desc = norm_space(text_of(head)) if head is not None else xid
      witnesses[xid] = desc or xid
      id_to_sig[xid] = xid
  return witnesses, id_to_sig


def convert(path: Path, max_sentences: int | None) -> dict:
  root = etree.parse(str(path)).getroot()
  title_el = root.find(f".//{q('titleStmt')}/{q('title')}")
  title = norm_space(title_el.text or "") if title_el is not None else path.stem

  witnesses, id_to_sig = load_witnesses(root)
  body = root.find(f".//{q('body')}")
  if body is None:
    raise SystemExit("no <body>")

  source_apps = list(root.iter(q("app")))
  xml_ids = Counter(app.get(XML_ID) or "" for app in source_apps)
  ledger: list[dict] = []
  ledger_by_path: dict[str, dict] = {}
  for i, app in enumerate(source_apps):
    xid = app.get(XML_ID) or ""
    source_id = xid if xid and xml_ids[xid] == 1 else f"app-{i:05d}"
    record = {"id": source_id, "xml_id": xid, "state": "pending", "reason": ""}
    ledger.append(record)
    ledger_by_path[root.getroottree().getpath(app)] = record

  def ledger_record(app: etree._Element) -> dict:
    return ledger_by_path[root.getroottree().getpath(app)]

  def exclude(app: etree._Element, reason: str) -> None:
    record = ledger_record(app)
    if record["state"] == "pending":
      record.update(state="excluded", reason=reason)

  def exclude_subtree(app: etree._Element, reason: str) -> None:
    exclude(app, reason)
    for desc in app.iterdescendants(q("app")):
      exclude(desc, reason)

  stream: list[dict] = []   # {"t": text} or {"app": {...}} in reading order

  def emit_text(s: str | None) -> None:
    if s:
      stream.append({"t": s})

  def visit(el: etree._Element) -> None:
    emit_text(el.text)
    for child in el:
      if not isinstance(child.tag, str):
        emit_text(child.tail)
        continue
      local = etree.QName(child).localname
      if local == "app":
        handle_app(child)
      elif local in ("note", "teiHeader", "back"):
        pass  # editorial notes are not constituted text
      else:
        visit(child)
      emit_text(child.tail)

  def handle_app(app: etree._Element) -> None:
    nested = any(
      isinstance(d.tag, str) and etree.QName(d).localname == "app"
      for d in app.iterdescendants())
    if nested:
      exclude_subtree(app, "nested_app_subtree")
      lem = app.find(q("lem"))
      emit_text(text_of(lem, skip={"note", "app", "rdg"}) if lem is not None else None)
      return
    if app.find(q("rdgGrp")) is not None:
      exclude_subtree(app, "rdggrp_subtree")
      lem = app.find(q("lem"))
      emit_text(text_of(lem, skip={"note"}) if lem is not None else None)
      return
    lem = app.find(q("lem"))
    lem_text = (tight(text_of(lem, skip={"note"})).strip()
                if lem is not None else "")
    if not lem_text.strip():
      exclude(app, "no_lem")
      return
    if "…" in lem_text or "..." in lem_text:
      # a discontinuous span lemma cannot carry ONE typeset marker position
      exclude(app, "discontinuous_span")
      emit_text(lem_text)
      return
    if not lem_text[0].isalpha():
      # punctuation-variant lemmas (SBLGNT: "; προφήτην ἰδεῖν") are not
      # representable in the marker convention we typeset
      exclude(app, "punctuation_lemma")
      emit_text(lem_text)
      return
    readings = []
    for rdg in app.findall(q("rdg")):
      r_wits, r_eds = split_attribution(
        wit_tokens(rdg, "wit", id_to_sig),
        wit_tokens(rdg, "source", id_to_sig)
        or wit_tokens(rdg, "resp", id_to_sig))
      r_text = tight(text_of(rdg, skip={"note"})).strip()
      # digit-bearing parentheticals are apparatus commentary, on both
      # sides of the comparison: printed in the band, excluded from the
      # structured reading (mirrors the parser's convention)
      notes = re.findall(r"\([^)]*\d[^)]*\)", r_text)
      r_text = norm_space(re.sub(r"\([^)]*\d[^)]*\)", " ", r_text)).strip()
      readings.append({
        "text": r_text,
        "wits": r_wits,
        "editors": r_eds,
        "note": " ".join(notes),
      })
    l_wits, l_eds = split_attribution(
      wit_tokens(lem, "wit", id_to_sig),
      wit_tokens(lem, "source", id_to_sig))
    emit_text(lem_text)
    stream.append({"app": {
      "source_id": ledger_record(app)["id"],
      "lemma": lem_text,
      "lemma_wits": l_wits,
      "lemma_editors": l_eds,
      "readings": readings,
    }})

  visit(body)

  # regroup the stream into sentences with their apps
  sentences: list[dict] = []
  buf = ""
  apps: list[dict] = []

  def flush(text_raw: str) -> None:
    nonlocal apps
    text = tight(norm_space(text_raw).strip())
    if text:
      kept = []
      for a in apps:
        if a["lemma"].split()[-1] in text:
          kept.append(a)
        else:
          record = next(r for r in ledger if r["id"] == a["source_id"])
          record.update(state="excluded", reason="sentence_unlocatable")
      sentences.append({"text": text, "apps": kept})
      apps = []

  # the scan runs over the ACCUMULATED buffer, not per-chunk: token-level
  # encodings deliver "·" and the following space in different chunks, and
  # a per-chunk scan never sees the boundary (observed: 46 sentences for
  # the whole NT)
  SENT_END = re.compile(r"[.;·!?]\s")
  for item in stream:
    if "t" in item:
      buf += item["t"]
      while True:
        m = SENT_END.search(buf)
        if m is None:
          break
        flush(buf[: m.end() - 1])
        buf = buf[m.end() - 1:].lstrip(" \t")
      continue
    apps.append(item["app"])
  flush(buf)

  if max_sentences:
    sentences = sentences[:max_sentences]

  emitted_ids = {
    app["source_id"] for sentence in sentences for app in sentence["apps"]
  }
  candidate_ids = {
    item["app"]["source_id"] for item in stream if "app" in item
  }
  for record in ledger:
    if record["id"] in emitted_ids:
      record.update(state="emitted", reason="")
    elif record["state"] == "pending" and record["id"] in candidate_ids:
      record.update(state="excluded", reason="max_sentences")
    elif record["state"] == "pending":
      record.update(state="excluded", reason="outside_constituted_body")

  lang = "grc" if any(
    "Ͱ" <= c <= "Ͽ" or "ἀ" <= c <= "῿"
    for s in sentences[:20] for c in s["text"][:200]
  ) else "la"
  cited: set[str] = set()
  for s in sentences:
    for a in s["apps"]:
      cited.update(a["lemma_editors"])
      for r in a["readings"]:
        cited.update(r["editors"])
  editors = sorted(cited)
  napps = sum(len(s["apps"]) for s in sentences)
  skipped = Counter(
    record["reason"] for record in ledger if record["state"] == "excluded")
  print(f"{path.name}: {len(sentences)} sentences, {napps} apps kept, "
        f"{len(editors)} editors cited, source={len(ledger)}, "
        f"excluded={dict(sorted(skipped.items()))}")
  return {
    "title": title,
    "language": lang,
    "witnesses": witnesses,
    "editors": editors,
    "source_total": len(ledger),
    "ledger": ledger,
    "sentences": sentences,
  }


def main() -> int:
  if len(sys.argv) < 3:
    print(__doc__, file=sys.stderr)
    return 2
  max_s = None
  if "--max-sentences" in sys.argv:
    max_s = int(sys.argv[sys.argv.index("--max-sentences") + 1])
  edition = convert(Path(sys.argv[1]), max_s)
  out = Path(sys.argv[2])
  out.write_text(json.dumps(edition, ensure_ascii=False, indent=1),
                 encoding="utf-8")
  nfc = unicodedata.normalize("NFC", out.read_text(encoding="utf-8"))
  out.write_text(nfc, encoding="utf-8")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
