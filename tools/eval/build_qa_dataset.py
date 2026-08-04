#!/usr/bin/env python3
"""Build deterministic, template-only variant-QA datasets from scholar TEI.

No model is involved.  Every question is derived from one ``<app>`` and
retains a stable document-order reference back to that element.

The source TEI is fetch-at-use data populated by ``tools/golden/fetch_sources.sh``.
By default this script writes 150 questions per edition plus compact flat-text
fallback contexts used by ``run_eval.py`` when the corresponding PDF is absent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TEI = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
NS = {"tei": TEI}
QUESTION_TYPES = (
  "witness_of_reading",
  "reading_of_witness",
  "lemma_vs_variant",
  "editor_attribution",
  "count",
)
APPLICABLE_TYPES = {
  "balex": QUESTION_TYPES,
  # SBLGNT records comparison editions in @wit and has no editor @source.
  "sblgnt": tuple(t for t in QUESTION_TYPES if t != "editor_attribution"),
}
DEFAULT_SEED = 20260804
DEFAULT_SIZE = 150
MAX_CONTEXT_WORDS = 72


def q(tag: str) -> str:
  return f"{{{TEI}}}{tag}"


def normalize_space(value: str) -> str:
  return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


_DECORATION = {"supplied": ("<", ">"), "surplus": ("{", "}")}


def visible_text(element: ET.Element | None, *, skip: frozenset[str] = frozenset()) -> str:
  """Flatten TEI content using the same small Leiden conventions as print."""
  if element is None:
    return ""
  parts: list[str] = []

  def walk(node: ET.Element) -> None:
    local = node.tag.rsplit("}", 1)[-1]
    if local in skip:
      if node.tail:
        parts.append(node.tail)
      return
    opening, closing = _DECORATION.get(local, ("", ""))
    parts.append(opening)
    if node.text:
      parts.append(node.text)
    for child in node:
      walk(child)
    parts.append(closing)
    if node.tail:
      parts.append(node.tail)

  # The element's tail belongs to its parent and is not part of its value.
  saved_tail = element.tail
  element.tail = None
  try:
    walk(element)
  finally:
    element.tail = saved_tail
  text = normalize_space("".join(parts))
  text = re.sub(r"\s+([,.;·:!?])", r"\1", text)
  return text.strip()


def tokens(attribute: str | None) -> tuple[str, ...]:
  if not attribute:
    return ()
  return tuple(dict.fromkeys(token.removeprefix("#") for token in attribute.split()))


def shown_reading(element: ET.Element) -> str:
  return visible_text(element, skip=frozenset({"note"})) or "om."


def normalized_reading(value: str) -> str:
  return normalize_space(value).casefold()


def locus_for(app: ET.Element, parents: dict[ET.Element, ET.Element], edition: str) -> str:
  if edition == "sblgnt":
    book = ""
    node: ET.Element | None = app
    while node is not None:
      if node.tag == q("div") and node.get("type") == "book":
        book = node.get(XML_ID, "")
        break
      node = parents.get(node)
    loc = app.get("loc", "unlocated")
    return normalize_space(f"{book} {loc}")

  chapter = ""
  segment = ""
  node = app
  while node is not None:
    if node.tag == q("seg") and not segment:
      segment = node.get("n", "")
    if node.tag == q("p") and not chapter:
      chapter = node.get("n", "")
    node = parents.get(node)
  return ".".join(part for part in (chapter, segment) if part) or "unlocated"


def constituted_text(element: ET.Element) -> str:
  """Flatten a passage, choosing only each app's constituted lemma."""
  parts: list[str] = []

  def walk(node: ET.Element) -> None:
    local = node.tag.rsplit("}", 1)[-1]
    if local in {"note", "rdg", "rdgGrp"}:
      if node.tail:
        parts.append(node.tail)
      return
    if local == "app":
      lemma = node.find(q("lem"))
      if lemma is not None:
        parts.append(visible_text(lemma, skip=frozenset({"note"})))
      if node.tail:
        parts.append(node.tail)
      return
    if node.text:
      parts.append(node.text)
    for child in node:
      walk(child)
    if node.tail:
      parts.append(node.tail)

  saved_tail = element.tail
  element.tail = None
  try:
    walk(element)
  finally:
    element.tail = saved_tail
  text = normalize_space("".join(parts))
  return re.sub(r"\s+([,.;·:!?])", r"\1", text)


def compact_excerpt(text: str, needle: str, maximum: int = MAX_CONTEXT_WORDS) -> str:
  words = text.split()
  if len(words) <= maximum:
    return text
  needle_words = needle.split()
  folded = [re.sub(r"\W+", "", word).casefold() for word in words]
  target = [re.sub(r"\W+", "", word).casefold() for word in needle_words]
  start = 0
  if target:
    width = len(target)
    start = next(
      (i for i in range(len(folded) - width + 1) if folded[i:i + width] == target),
      0,
    )
  left = max(0, start - maximum // 2)
  right = min(len(words), left + maximum)
  left = max(0, right - maximum)
  excerpt = " ".join(words[left:right])
  if left:
    excerpt = "… " + excerpt
  if right < len(words):
    excerpt += " …"
  return excerpt


def attribution_suffix(element: ET.Element) -> str:
  values = [*tokens(element.get("wit")), *tokens(element.get("source"))]
  return (" " + " ".join(values)) if values else ""


def apparatus_line(app: ET.Element) -> str:
  """Lossless-for-QA flat rendering of one short TEI apparatus excerpt."""
  lemma = app.find(q("lem"))
  if lemma is None:
    return ""
  left = visible_text(lemma, skip=frozenset({"note"})) + attribution_suffix(lemma)
  readings = [shown_reading(rdg) + attribution_suffix(rdg) for rdg in app.findall(q("rdg"))]
  line = left + (" ] " + "; ".join(readings) if readings else "")
  notes = [visible_text(note) for note in app.findall(q("note"))]
  notes = [note for note in notes if note]
  if notes:
    line += " " + " ".join(notes)
  return normalize_space(line)


@dataclass(frozen=True)
class AppRecord:
  app_ref: str
  locus: str
  element: ET.Element
  parent_context: str
  lemma: str


def load_apps(path: Path, edition: str) -> tuple[list[AppRecord], ET.ElementTree]:
  tree = ET.parse(path)
  root = tree.getroot()
  parents = {child: parent for parent in root.iter() for child in parent}
  records: list[AppRecord] = []
  for index, app in enumerate(root.iter(q("app"))):
    # Nested apparatuses and grouped readings do not expose one unambiguous
    # flat set of direct lemma/readings, so they are honestly excluded.
    if app.find(f".//{q('app')}") is not None or app.find(q("rdgGrp")) is not None:
      continue
    lemma_element = app.find(q("lem"))
    lemma = visible_text(lemma_element, skip=frozenset({"note"}))
    readings = app.findall(q("rdg"))
    if not lemma or not readings:
      continue
    context_parent = parents.get(app)
    while context_parent is not None and context_parent.tag not in {q("seg"), q("p")}:
      context_parent = parents.get(context_parent)
    context = constituted_text(context_parent) if context_parent is not None else lemma
    records.append(AppRecord(
      app_ref=f"{edition}:app-{index:05d}",
      locus=locus_for(app, parents, edition),
      element=app,
      parent_context=compact_excerpt(context, lemma),
      lemma=lemma,
    ))
  return records, tree


def make_question(question: str, gold_answer: str | list[str], record: AppRecord,
                  question_type: str) -> dict[str, Any]:
  return {
    "question": question,
    "gold_answer": gold_answer,
    "app_ref": record.app_ref,
    "type": question_type,
  }


def candidates(records: list[AppRecord], edition: str) -> dict[str, list[dict[str, Any]]]:
  out: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for record in records:
    app = record.element
    lemma = app.find(q("lem"))
    assert lemma is not None
    readings = [(lemma, record.lemma), *(
      (rdg, shown_reading(rdg)) for rdg in app.findall(q("rdg"))
    )]

    # Collapse identical displayed readings within an app; their TEI @wit
    # sets jointly answer the witness question.
    by_reading: dict[str, dict[str, Any]] = {}
    for element, text in readings:
      key = normalized_reading(text)
      item = by_reading.setdefault(key, {"text": text, "wits": [], "sources": []})
      item["wits"].extend(tokens(element.get("wit")))
      item["sources"].extend(tokens(element.get("source")))
    for item in by_reading.values():
      wits = list(dict.fromkeys(item["wits"]))
      if wits:
        out["witness_of_reading"].append(make_question(
          f"Which witnesses transmit reading {item['text']} at {record.locus}?",
          wits,
          record,
          "witness_of_reading",
        ))

    # Ask only when this app assigns W to exactly one displayed reading.
    witness_readings: dict[str, list[str]] = defaultdict(list)
    for element, text in readings:
      for witness in tokens(element.get("wit")):
        if normalized_reading(text) not in {
          normalized_reading(value) for value in witness_readings[witness]
        }:
          witness_readings[witness].append(text)
    for witness, values in witness_readings.items():
      if len(values) == 1:
        out["reading_of_witness"].append(make_question(
          f"What does witness {witness} read for lemma {record.lemma} at {record.locus}?",
          values[0],
          record,
          "reading_of_witness",
        ))

    out["lemma_vs_variant"].append(make_question(
      f"Is {record.lemma} the constituted text or a rejected variant at {record.locus}?",
      "constituted text",
      record,
      "lemma_vs_variant",
    ))
    lemma_key = normalized_reading(record.lemma)
    seen_variants: set[str] = set()
    for rdg in app.findall(q("rdg")):
      text = shown_reading(rdg)
      key = normalized_reading(text)
      if key == lemma_key or key in seen_variants:
        continue
      seen_variants.add(key)
      out["lemma_vs_variant"].append(make_question(
        f"Is {text} the constituted text or a rejected variant at {record.locus}?",
        "rejected variant",
        record,
        "lemma_vs_variant",
      ))

    if edition == "balex":
      for item in by_reading.values():
        sources = list(dict.fromkeys(item["sources"]))
        if sources:
          out["editor_attribution"].append(make_question(
            f"Which editor proposed {item['text']} at {record.locus}?",
            sources,
            record,
            "editor_attribution",
          ))

    out["count"].append(make_question(
      f"How many variant readings are recorded for lemma {record.lemma} at {record.locus}?",
      str(len(app.findall(q("rdg")))),
      record,
      "count",
    ))
  return out


def allocation(total: int, types: tuple[str, ...]) -> dict[str, int]:
  base, extra = divmod(total, len(types))
  return {question_type: base + (index < extra) for index, question_type in enumerate(types)}


def edition_rng(seed: int, edition: str) -> random.Random:
  digest = hashlib.sha256(f"{seed}:{edition}".encode()).digest()
  return random.Random(int.from_bytes(digest[:8], "big"))


def sample_questions(all_candidates: dict[str, list[dict[str, Any]]], edition: str,
                     total: int, seed: int) -> list[dict[str, Any]]:
  rng = edition_rng(seed, edition)
  selected: list[dict[str, Any]] = []
  required = allocation(total, APPLICABLE_TYPES[edition])
  for question_type, amount in required.items():
    pool = all_candidates[question_type]
    if len(pool) < amount:
      raise ValueError(
        f"{edition}: need {amount} {question_type} candidates, found {len(pool)}"
      )
    selected.extend(rng.sample(pool, amount))
  rng.shuffle(selected)
  return selected


def validate_dataset(data: Any, edition: str, expected_size: int) -> Counter[str]:
  if not isinstance(data, list) or len(data) != expected_size:
    raise ValueError(f"{edition}: expected a list of {expected_size} questions")
  expected_keys = {"question", "gold_answer", "app_ref", "type"}
  counts: Counter[str] = Counter()
  for index, item in enumerate(data):
    if not isinstance(item, dict) or set(item) != expected_keys:
      raise ValueError(f"{edition}[{index}]: keys must be {sorted(expected_keys)}")
    if item["type"] not in APPLICABLE_TYPES[edition]:
      raise ValueError(f"{edition}[{index}]: invalid type {item['type']!r}")
    for key in ("question", "app_ref", "type"):
      if not isinstance(item[key], str) or not item[key].strip():
        raise ValueError(f"{edition}[{index}].{key} must be a non-empty string")
    gold = item["gold_answer"]
    if isinstance(gold, list):
      if not gold or not all(isinstance(value, str) and value for value in gold):
        raise ValueError(f"{edition}[{index}].gold_answer has an invalid set")
    elif not isinstance(gold, str) or not gold:
      raise ValueError(f"{edition}[{index}].gold_answer must be string or string list")
    counts[item["type"]] += 1
  target = allocation(expected_size, APPLICABLE_TYPES[edition])
  if dict(counts) != target:
    raise ValueError(f"{edition}: unbalanced type counts {dict(counts)} != {target}")
  return counts


def write_json(path: Path, payload: Any) -> None:
  path.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
    encoding="utf-8",
  )


def divergence_loci(path: Path, edition: str) -> set[str]:
  """Conservatively exclude adjudicated print/TEI disagreements from QA."""
  if not path.is_file():
    return set()
  payload = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(payload, dict):
    raise ValueError(f"{path}: typed divergences must be a JSON object")
  loci: set[str] = set()
  for key, item in payload.items():
    if not isinstance(item, dict):
      raise ValueError(f"{path}: divergence {key!r} is not an object")
    book = item.get("book")
    locus = item.get("locus")
    if not isinstance(book, str) or not isinstance(locus, str):
      raise ValueError(f"{path}: divergence {key!r} has no typed book/locus")
    loci.add(locus if edition == "balex" else f"{book} {locus}")
  return loci


def build_edition(path: Path, edition: str, output_dir: Path, size: int,
                  seed: int, excluded_loci: set[str]) -> Counter[str]:
  records, _tree = load_apps(path, edition)
  records = [record for record in records if record.locus not in excluded_loci]
  by_ref = {record.app_ref: record for record in records}
  dataset = sample_questions(candidates(records, edition), edition, size, seed)
  counts = validate_dataset(dataset, edition, size)
  fallbacks = []
  for app_ref in sorted({item["app_ref"] for item in dataset}):
    record = by_ref[app_ref]
    fallbacks.append({
      "app_ref": app_ref,
      "locus": record.locus,
      "constituted_context": record.parent_context,
      "apparatus_line": apparatus_line(record.element),
    })
  write_json(output_dir / f"{edition}.json", dataset)
  write_json(output_dir / f"{edition}-flat-fallback.json", fallbacks)
  return counts


def parse_args() -> argparse.Namespace:
  root = Path(__file__).resolve().parents[2]
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
  parser.add_argument("--questions-per-edition", type=int, default=DEFAULT_SIZE)
  parser.add_argument("--balex", type=Path, default=root / "tools/golden/data/balex.xml")
  parser.add_argument("--sblgnt", type=Path, default=root / "tools/golden/data/sblgnt.xml")
  parser.add_argument(
    "--balex-divergences", type=Path,
    default=root / "tools/golden/balex_known_divergences.json",
  )
  parser.add_argument(
    "--sblgnt-divergences", type=Path,
    default=root / "tools/golden/sblgnt_known_divergences.json",
  )
  parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "data")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  if args.questions_per_edition <= 0:
    raise SystemExit("--questions-per-edition must be positive")
  missing = [path for path in (args.balex, args.sblgnt) if not path.is_file()]
  if missing:
    paths = ", ".join(str(path) for path in missing)
    raise SystemExit(
      f"missing fetch-at-use TEI: {paths}; run tools/golden/fetch_sources.sh first"
    )
  args.output_dir.mkdir(parents=True, exist_ok=True)
  divergence_paths = {
    "balex": args.balex_divergences,
    "sblgnt": args.sblgnt_divergences,
  }
  for edition, path in (("balex", args.balex), ("sblgnt", args.sblgnt)):
    excluded = divergence_loci(divergence_paths[edition], edition)
    counts = build_edition(
      path, edition, args.output_dir, args.questions_per_edition, args.seed, excluded
    )
    rendered = ", ".join(f"{key}={counts[key]}" for key in APPLICABLE_TYPES[edition])
    print(
      f"{edition}: {sum(counts.values())} questions ({rendered}); "
      f"excluded typed-divergence loci={len(excluded)}"
    )
  print(f"seed={args.seed}; wrote datasets and short flat fallbacks to {args.output_dir}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
