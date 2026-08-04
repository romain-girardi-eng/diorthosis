#!/usr/bin/env python3
"""Run or dry-run the variant-QA comparison over flat, TEI, and md-ce input.

The default ``--dry-run``-compatible path performs no network operation.  A
real run supports OpenAI-compatible chat-completions and Anthropic Messages
endpoints using only the Python standard library for HTTP.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import statistics
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from build_qa_dataset import (
  DEFAULT_SEED,
  DEFAULT_SIZE,
  AppRecord,
  load_apps,
  normalize_space,
  q,
  shown_reading,
  tokens,
  validate_dataset,
  visible_text,
)

CONDITIONS = ("flat", "structured-tei", "structured-md")
BOOK_PDF_NUMBER = {f"B{number:02d}": number + 60 for number in range(1, 28)}
SYSTEM_INSTRUCTION = """Answer the textual-criticism question using only the supplied context.
Return only the answer, with no explanation. For a witness or editor set, return identifiers
separated by commas and omit TEI '#wit-'/'#ed-' prefixes. For classification,
return exactly 'constituted text' or 'rejected variant'. For an omission,
return 'om.'."""


@dataclass(frozen=True)
class Fallback:
  app_ref: str
  locus: str
  constituted_context: str
  apparatus_line: str


@dataclass(frozen=True)
class FlatContext:
  text: str
  source: str
  page_index: int | None = None


def read_json(path: Path) -> Any:
  return json.loads(path.read_text(encoding="utf-8"))


def load_fallbacks(path: Path) -> dict[str, Fallback]:
  payload = read_json(path)
  if not isinstance(payload, list):
    raise ValueError(f"{path}: fallback must be a JSON list")
  out: dict[str, Fallback] = {}
  required = {"app_ref", "locus", "constituted_context", "apparatus_line"}
  for index, item in enumerate(payload):
    if not isinstance(item, dict) or set(item) != required:
      raise ValueError(f"{path}[{index}]: invalid fallback schema")
    fallback = Fallback(**item)
    if not all((fallback.app_ref, fallback.locus, fallback.constituted_context,
                fallback.apparatus_line)):
      raise ValueError(f"{path}[{index}]: empty fallback field")
    if fallback.app_ref in out:
      raise ValueError(f"{path}: duplicate fallback {fallback.app_ref}")
    out[fallback.app_ref] = fallback
  return out


def xml_id_fragment(value: str) -> str:
  return "".join(
    char if char.isascii() and char.isalnum() else f"u{ord(char):x}"
    for char in value
  )


def reading_attributes(source: ET.Element) -> dict[str, str]:
  attributes: dict[str, str] = {}
  witnesses = tokens(source.get("wit"))
  editors = tokens(source.get("source"))
  if witnesses:
    attributes["wit"] = " ".join(f"#wit-{xml_id_fragment(value)}" for value in witnesses)
  if editors:
    attributes["source"] = " ".join(f"#ed-{xml_id_fragment(value)}" for value in editors)
  if source.get("cert"):
    attributes["cert"] = source.get("cert", "")
  return attributes


def diorthosis_app_xml(record: AppRecord, fallback: Fallback) -> str:
  """Render source facts in diorthosis' canonical app/lem/rdg/verbatim shape."""
  element = ET.Element(q("app"), {"n": "eval"})
  source_lemma = record.element.find(q("lem"))
  assert source_lemma is not None
  lemma = ET.SubElement(element, q("lem"), reading_attributes(source_lemma))
  lemma.text = record.lemma
  for source_reading in record.element.findall(q("rdg")):
    reading = ET.SubElement(element, q("rdg"), reading_attributes(source_reading))
    text = visible_text(source_reading, skip=frozenset({"note"}))
    if text:
      reading.text = text
  note = ET.SubElement(element, q("note"), {"type": "verbatim"})
  note.text = fallback.apparatus_line
  ET.register_namespace("", "http://www.tei-c.org/ns/1.0")
  ET.indent(element, space="  ")
  return ET.tostring(element, encoding="unicode", short_empty_elements=True).strip()


def insert_marker(context: str, lemma: str) -> str:
  index = context.find(lemma)
  if index < 0:
    return context + " ⟦eval:1⟧"
  end = index + len(lemma)
  return context[:end] + "⟦eval:1⟧" + context[end:]


def structured_md(fallback: Fallback, record: AppRecord) -> str:
  marked = insert_marker(fallback.constituted_context, record.lemma)
  return "\n".join([
    f"## page {fallback.locus} (file index 0) [markers=1 entries=1 unresolved=0]",
    "",
    "### text [source=born_digital generative=false confidence=1.00 block=0]",
    "",
    marked,
    "",
    "### apparatus [source=born_digital generative=false confidence=1.00 block=1]",
    "",
    f"⟦eval:1⟧ {fallback.apparatus_line}",
  ])


def build_prompt(condition: str, context: str, question: str, app_ref: str) -> str:
  if condition not in CONDITIONS:
    raise ValueError(f"unknown condition: {condition}")
  labels = {
    "flat": "FLAT PRINTED-PAGE TRANSCRIPTION",
    "structured-tei": "STRUCTURED TEI APPARATUS",
    "structured-md": "STRUCTURED MD-CE PAGE SECTION",
  }
  if not context.strip():
    raise ValueError(f"{app_ref}/{condition}: empty context")
  return (
    f"{SYSTEM_INSTRUCTION}\n\n"
    f"Condition: {labels[condition]}\n"
    f"App reference: {app_ref}\n\n"
    f"CONTEXT\n{context}\n\n"
    f"QUESTION\n{question}\n\nANSWER\n"
  )


def token_estimate(text: str) -> int:
  """Provider-neutral deterministic heuristic, deliberately labeled an estimate."""
  return max(1, math.ceil(len(text.encode("utf-8")) / 4))


def page_text(page: Any) -> str:
  # regreek returns bands in reading order and preserves decoded line breaks.
  return "\n\n".join(band.text.rstrip() for band in page.bands if band.text.strip())


def search_normalize(value: str) -> str:
  value = unicodedata.normalize("NFKC", value).casefold()
  value = re.sub(r"-\s+", "", value)
  return "".join(char for char in value if char.isalnum())


def app_search_terms(record: AppRecord, fallback: Fallback) -> list[str]:
  terms = [record.lemma]
  terms.extend(shown_reading(rdg) for rdg in record.element.findall(q("rdg")))
  words = fallback.constituted_context.replace("…", "").split()
  lemma_words = record.lemma.split()
  if lemma_words:
    folded = [re.sub(r"\W+", "", word).casefold() for word in words]
    target = [re.sub(r"\W+", "", word).casefold() for word in lemma_words]
    width = len(target)
    position = next(
      (i for i in range(len(folded) - width + 1) if folded[i:i + width] == target),
      len(words) // 2,
    )
    # A printed verse/line number can fall immediately before the lemma and
    # break a wider cross-boundary phrase.  Include one phrase beginning at
    # the lemma as a page-location key as well as symmetric context windows.
    terms.append(" ".join(words[position:position + width + 5]))
    for radius in (3, 5):
      left = max(0, position - radius)
      right = min(len(words), position + width + radius)
      terms.append(" ".join(words[left:right]))
  unique: list[str] = []
  for term in terms:
    normalized = search_normalize(term)
    if len(normalized) >= 2 and normalized not in unique:
      unique.append(normalized)
  return unique


def best_page(pages: list[Any], record: AppRecord, fallback: Fallback,
              edition: str) -> Any | None:
  terms = app_search_terms(record, fallback)
  locus = fallback.locus.split(" ", 1)[-1]
  scored: list[tuple[float, int, Any]] = []
  for page in pages:
    raw = page_text(page)
    normalized = search_normalize(raw)
    score = 0.0
    for term in terms:
      if term in normalized:
        score += min(12.0, 1.0 + len(term) / 10)
    if edition == "sblgnt" and locus in normalize_space(raw):
      score += 20.0
    scored.append((score, -page.page, page))
  winner = max(scored, default=(0.0, 0, None))
  return winner[2] if winner[0] > 0 else None


def locus_start(locus: str) -> tuple[int, int] | None:
  match = re.match(r"(\d+):(\d+)", locus)
  return (int(match.group(1)), int(match.group(2))) if match else None


def sblgnt_locus_page(pages: list[Any], locus: str) -> Any | None:
  """Use each page's first printed chapter:verse coordinate as a boundary."""
  target = locus_start(locus)
  if target is None:
    return None
  starts: list[tuple[tuple[int, int], Any]] = []
  for page in pages:
    match = re.search(r"(?<!\d)(\d{1,2}):(\d{1,3})", page_text(page))
    if match:
      starts.append(((int(match.group(1)), int(match.group(2))), page))
  eligible = [(start, page) for start, page in starts if start <= target]
  return max(eligible, key=lambda item: (item[0], item[1].page))[1] if eligible else None


def balex_chapter_pages(pages: list[Any], locus: str) -> list[Any]:
  match = re.match(r"(\d+)(?:\.|$)", locus)
  if not match:
    return pages
  target = int(match.group(1))
  chapter_starts: dict[int, int] = {}
  for page in pages:
    # In the LDLT body a chapter opens as "33 1Caesar". Apparatus line
    # numbers use dashes or begin with words, so this shape stays specific.
    for found in re.finditer(r"(?:^|\n)\s*(\d{1,2})\s+1\D", page_text(page)):
      chapter = int(found.group(1))
      if 1 <= chapter <= 80:
        chapter_starts.setdefault(chapter, page.page)
  start = chapter_starts.get(target)
  if start is None:
    return pages
  next_starts = [page for chapter, page in chapter_starts.items() if chapter > target]
  end = min(next_starts, default=pages[-1].page + 1)
  # The next chapter can begin halfway down the same page on which the target
  # chapter ends, so that boundary page belongs to both candidate ranges.
  selected = [page for page in pages if start <= page.page <= end]
  return selected or pages


class PDFPages:
  def __init__(self, flat_source: str, balex_pdf: Path | None,
               sblgnt_pdf_dir: Path | None) -> None:
    self.flat_source = flat_source
    self.balex_pdf = balex_pdf
    self.sblgnt_pdf_dir = sblgnt_pdf_dir
    self.cache: dict[tuple[Path, tuple[int, ...] | None], list[Any]] = {}

  def extract(self, path: Path, pages: list[int] | None = None) -> list[Any]:
    key = (path, tuple(pages) if pages is not None else None)
    if key not in self.cache:
      try:
        from regreek.layers import layer_pages
      except ImportError as exc:  # pragma: no cover - project dependency
        raise RuntimeError("regreek is required to extract real PDF pages") from exc
      self.cache[key] = layer_pages(path, pages=pages)
    return self.cache[key]

  def sblgnt_pdf(self, book: str) -> Path | None:
    if self.sblgnt_pdf_dir is None:
      return None
    number = BOOK_PDF_NUMBER.get(book)
    if number is None:
      return None
    matches = sorted(self.sblgnt_pdf_dir.glob(f"{number:02d}-SBLGNT-*.pdf"))
    return matches[0] if matches else None

  def context(self, edition: str, record: AppRecord, fallback: Fallback) -> FlatContext:
    if self.flat_source == "fallback":
      return self.fallback_context(fallback)
    path: Path | None
    pages: list[Any]
    if edition == "balex":
      path = self.balex_pdf
      pages = self.extract(path, list(range(82, 172))) if path is not None else []
      pages = balex_chapter_pages(pages, fallback.locus)
    else:
      book = fallback.locus.split()[0]
      path = self.sblgnt_pdf(book)
      pages = self.extract(path) if path is not None else []
    if edition == "sblgnt" and pages:
      page = sblgnt_locus_page(pages, fallback.locus.split(" ", 1)[-1])
      if page is None:  # one-chapter books print verse-only page coordinates
        page = best_page(pages, record, fallback, edition)
    else:
      page = best_page(pages, record, fallback, edition) if pages else None
    if page is not None and path is not None:
      return FlatContext(page_text(page), f"pdf:{path}", page.page)
    if self.flat_source == "pdf":
      raise ValueError(f"{record.app_ref}: no matching real PDF page")
    return self.fallback_context(fallback)

  @staticmethod
  def fallback_context(fallback: Fallback) -> FlatContext:
    text = (
      f"{fallback.constituted_context}\n\n"
      f"APPARATUS\n{fallback.apparatus_line}"
    )
    return FlatContext(text, "tei-fallback")


def first_existing(paths: list[Path]) -> Path | None:
  return next((path for path in paths if path.is_file()), None)


def first_existing_dir(paths: list[Path]) -> Path | None:
  return next((path for path in paths if path.is_dir()), None)


def discover_balex_pdf(explicit: Path | None) -> Path | None:
  if explicit is not None:
    return explicit if explicit.is_file() else None
  env = os.environ.get("BALEX_PDF")
  candidates = ([Path(env)] if env else []) + [
    Path("/tmp/ldlt-balex.pdf"),
    Path("/private/tmp/ldlt-balex.pdf"),
    Path("/tmp/balex.pdf"),
    Path("/private/tmp/balex.pdf"),
  ]
  return first_existing(candidates)


def discover_sblgnt_pdf_dir(explicit: Path | None, root: Path) -> Path | None:
  if explicit is not None:
    return explicit if explicit.is_dir() else None
  env = os.environ.get("SBLGNT_PDF_DIR")
  candidates = ([Path(env)] if env else []) + [
    Path("/tmp/gold_verify/sblgnt_pdf"),
    Path("/private/tmp/gold_verify/sblgnt_pdf"),
    Path("/tmp/sblgnt_pdfs"),
    Path("/private/tmp/sblgnt_pdfs"),
    root / "tools/golden/data/sblgnt_pdfs",
  ]
  return first_existing_dir(candidates)


def normalize_answer(value: str) -> str:
  value = unicodedata.normalize("NFC", value).strip().strip("`\"'")
  return re.sub(r"\s+", " ", value).casefold()


def answer_set(value: str) -> set[str]:
  value = value.strip().removeprefix("[").removesuffix("]")
  fields = re.split(r"[,;\s]+", value)
  answer: set[str] = set()
  for field in fields:
    field = field.strip("[](){}\"'").removeprefix("#")
    field = re.sub(r"^(?:wit|ed)-", "", field, flags=re.IGNORECASE)
    if field:
      answer.add(normalize_answer(field))
  return answer


def score_answer(response: str, gold: str | list[str], question_type: str) -> bool:
  if isinstance(gold, list):
    expected = {normalize_answer(value.removeprefix("#")) for value in gold}
    return answer_set(response) == expected
  return normalize_answer(response) == normalize_answer(gold)


def bootstrap_ci(values: list[int], iterations: int, seed: int) -> tuple[float, float]:
  if not values:
    return (math.nan, math.nan)
  if len(values) == 1 or len(set(values)) == 1:
    mean = float(values[0])
    return (mean, mean)
  rng = random.Random(seed)
  means = [
    sum(values[rng.randrange(len(values))] for _ in values) / len(values)
    for _ in range(iterations)
  ]
  means.sort()
  low = means[int(0.025 * (iterations - 1))]
  high = means[int(0.975 * (iterations - 1))]
  return (low, high)


def summarize_scores(records: list[dict[str, Any]], iterations: int,
                     seed: int) -> dict[str, Any]:
  groups: dict[tuple[str, str], list[int]] = defaultdict(list)
  for record in records:
    groups[(record["condition"], "overall")].append(int(record["correct"]))
    groups[(record["condition"], record["type"])].append(int(record["correct"]))
  summary: dict[str, Any] = {}
  for (condition, question_type), values in sorted(groups.items()):
    low, high = bootstrap_ci(
      values, iterations, seed + sum(map(ord, condition + question_type))
    )
    summary.setdefault(condition, {})[question_type] = {
      "n": len(values),
      "correct": sum(values),
      "accuracy": sum(values) / len(values),
      "bootstrap_95_ci": [low, high],
    }
  return summary


def endpoint(base_url: str, suffix: str) -> str:
  base = base_url.rstrip("/")
  return base if base.endswith(suffix) else base + suffix


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str],
              timeout: float) -> dict[str, Any]:
  request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json", **headers},
    method="POST",
  )
  try:
    with urllib.request.urlopen(request, timeout=timeout) as response:
      result = json.loads(response.read().decode("utf-8"))
  except urllib.error.HTTPError as exc:
    detail = exc.read().decode("utf-8", errors="replace")
    raise RuntimeError(f"HTTP {exc.code} from model endpoint: {detail[:500]}") from exc
  if not isinstance(result, dict):
    raise RuntimeError("model endpoint returned a non-object JSON response")
  return result


def call_model(provider: str, prompt: str, model: str, api_key: str,
               base_url: str, max_tokens: int, timeout: float) -> str:
  if provider == "openai":
    payload = {
      "model": model,
      "messages": [{"role": "user", "content": prompt}],
      "temperature": 0,
      "max_tokens": max_tokens,
    }
    result = post_json(
      endpoint(base_url, "/chat/completions"), payload,
      {"Authorization": f"Bearer {api_key}"}, timeout,
    )
    try:
      return str(result["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
      raise RuntimeError("unrecognized OpenAI-compatible response schema") from exc
  payload = {
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0,
    "max_tokens": max_tokens,
  }
  result = post_json(
    endpoint(base_url, "/messages"), payload,
    {"x-api-key": api_key, "anthropic-version": "2023-06-01"}, timeout,
  )
  try:
    return "".join(
      str(block["text"]) for block in result["content"] if block.get("type") == "text"
    )
  except (KeyError, TypeError) as exc:
    raise RuntimeError("unrecognized Anthropic response schema") from exc


def provider_defaults(provider: str) -> tuple[str, str]:
  if provider == "anthropic":
    return (
      os.environ.get("ANTHROPIC_API_KEY", ""),
      os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
    )
  return (
    os.environ.get("OPENAI_API_KEY", ""),
    os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
  )


def parse_args() -> argparse.Namespace:
  root = Path(__file__).resolve().parents[2]
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--edition", choices=("balex", "sblgnt", "both"), default="both")
  parser.add_argument("--dataset-dir", type=Path, default=Path(__file__).parent / "data")
  parser.add_argument("--balex-tei", type=Path, default=root / "tools/golden/data/balex.xml")
  parser.add_argument("--sblgnt-tei", type=Path, default=root / "tools/golden/data/sblgnt.xml")
  parser.add_argument("--balex-pdf", type=Path)
  parser.add_argument("--sblgnt-pdf-dir", type=Path)
  parser.add_argument("--flat-source", choices=("auto", "pdf", "fallback"), default="auto")
  parser.add_argument("--conditions", default=",".join(CONDITIONS))
  parser.add_argument("--dry-run", action="store_true")
  parser.add_argument("--provider", choices=("openai", "anthropic"),
                      default=os.environ.get("EVAL_PROVIDER", "openai"))
  parser.add_argument("--model", default=os.environ.get("EVAL_MODEL", ""))
  parser.add_argument("--api-key", default="")
  parser.add_argument("--base-url", default="")
  parser.add_argument("--max-tokens", type=int, default=64)
  parser.add_argument("--timeout", type=float, default=120)
  parser.add_argument("--output", type=Path)
  parser.add_argument("--bootstrap-samples", type=int, default=10_000)
  parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
  parser.add_argument("--limit", type=int, help="development-only limit per edition")
  parser.add_argument("--show-prompts", type=int, default=0)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  conditions = tuple(part.strip() for part in args.conditions.split(",") if part.strip())
  invalid = set(conditions) - set(CONDITIONS)
  if invalid or not conditions:
    raise SystemExit(f"invalid --conditions: {', '.join(sorted(invalid)) or 'empty'}")
  if args.bootstrap_samples <= 0:
    raise SystemExit("--bootstrap-samples must be positive")
  editions = ("balex", "sblgnt") if args.edition == "both" else (args.edition,)
  tei_paths = {"balex": args.balex_tei, "sblgnt": args.sblgnt_tei}
  datasets: dict[str, list[dict[str, Any]]] = {}
  fallbacks: dict[str, dict[str, Fallback]] = {}
  records_by_edition: dict[str, dict[str, AppRecord]] = {}
  for edition in editions:
    dataset_path = args.dataset_dir / f"{edition}.json"
    fallback_path = args.dataset_dir / f"{edition}-flat-fallback.json"
    dataset = read_json(dataset_path)
    validate_dataset(dataset, edition, DEFAULT_SIZE)
    if args.limit is not None:
      if args.limit <= 0:
        raise SystemExit("--limit must be positive")
      dataset = dataset[:args.limit]
    datasets[edition] = dataset
    fallbacks[edition] = load_fallbacks(fallback_path)
    app_records, _tree = load_apps(tei_paths[edition], edition)
    records_by_edition[edition] = {record.app_ref: record for record in app_records}
    missing = {
      item["app_ref"] for item in dataset
      if item["app_ref"] not in fallbacks[edition]
      or item["app_ref"] not in records_by_edition[edition]
    }
    if missing:
      raise ValueError(f"{edition}: unresolved app refs: {sorted(missing)[:5]}")

  root = Path(__file__).resolve().parents[2]
  pdf_pages = PDFPages(
    args.flat_source,
    discover_balex_pdf(args.balex_pdf),
    discover_sblgnt_pdf_dir(args.sblgnt_pdf_dir, root),
  )
  prompts: list[dict[str, Any]] = []
  shown = 0
  for edition in editions:
    flat_cache: dict[str, FlatContext] = {}
    for item in datasets[edition]:
      app_ref = item["app_ref"]
      fallback = fallbacks[edition][app_ref]
      record = records_by_edition[edition][app_ref]
      if app_ref not in flat_cache:
        flat_cache[app_ref] = pdf_pages.context(edition, record, fallback)
      contexts = {
        "flat": flat_cache[app_ref].text,
        "structured-tei": (
          f"Locus: {fallback.locus}\nApp reference: {app_ref}\n"
          f"{diorthosis_app_xml(record, fallback)}"
        ),
        "structured-md": structured_md(fallback, record),
      }
      for condition in conditions:
        prompt = build_prompt(condition, contexts[condition], item["question"], app_ref)
        record_out = {
          "edition": edition,
          **item,
          "condition": condition,
          "prompt": prompt,
          "token_estimate": token_estimate(prompt),
          "flat_source": flat_cache[app_ref].source if condition == "flat" else None,
          "flat_page_index": flat_cache[app_ref].page_index if condition == "flat" else None,
        }
        prompts.append(record_out)
        if shown < args.show_prompts:
          print(f"--- {edition} {app_ref} {condition} ---")
          print(prompt)
          shown += 1

  expected = sum(len(datasets[edition]) for edition in editions) * len(conditions)
  if len(prompts) != expected:
    raise RuntimeError(f"built {len(prompts)} prompts, expected {expected}")

  if args.dry_run:
    for edition in editions:
      print(f"{edition}: {len(datasets[edition])} questions; prompt build PASS")
      for condition in conditions:
        subset = [p for p in prompts if p["edition"] == edition and p["condition"] == condition]
        estimates = [p["token_estimate"] for p in subset]
        source_counts = Counter(
          "pdf" if str(p["flat_source"]).startswith("pdf:") else "fallback"
          for p in subset if condition == "flat"
        )
        source_note = (
          "; flat sources " + ", ".join(f"{key}={value}" for key, value in source_counts.items())
          if condition == "flat" else ""
        )
        print(
          f"  {condition}: prompts={len(subset)}, estimated tokens "
          f"total={sum(estimates)}, mean={statistics.mean(estimates):.1f}, "
          f"max={max(estimates)}{source_note}"
        )
        fallback_refs = sorted({
          p["app_ref"] for p in subset
          if condition == "flat" and p["flat_source"] == "tei-fallback"
        })
        if fallback_refs:
          print(f"    fallback app refs: {', '.join(fallback_refs)}")
    print(f"DRY RUN PASS: {len(prompts)} prompts built; no model API called")
    return 0

  api_key_default, base_url_default = provider_defaults(args.provider)
  api_key = args.api_key or api_key_default
  base_url = args.base_url or base_url_default
  if not args.model:
    raise SystemExit("a model is required: pass --model or set EVAL_MODEL")
  if not api_key:
    env_name = "ANTHROPIC_API_KEY" if args.provider == "anthropic" else "OPENAI_API_KEY"
    raise SystemExit(f"an API key is required: pass --api-key or set {env_name}")

  scored: list[dict[str, Any]] = []
  for index, prompt_record in enumerate(prompts, start=1):
    response = call_model(
      args.provider, prompt_record["prompt"], args.model, api_key, base_url,
      args.max_tokens, args.timeout,
    )
    scored.append({
      **prompt_record,
      "response": response,
      "correct": score_answer(
        response, prompt_record["gold_answer"], prompt_record["type"]
      ),
    })
    print(f"[{index}/{len(prompts)}] {prompt_record['edition']} "
          f"{prompt_record['condition']} {prompt_record['app_ref']}")

  result = {
    "provider": args.provider,
    "model": args.model,
    "seed": args.seed,
    "bootstrap_samples": args.bootstrap_samples,
    "records": scored,
    "summary": summarize_scores(scored, args.bootstrap_samples, args.seed),
  }
  output = args.output or Path(__file__).parent / "results" / f"{args.provider}-{args.model}.json"
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  print(json.dumps(result["summary"], indent=2))
  print(f"wrote {output}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
