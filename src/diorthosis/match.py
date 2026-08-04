"""Text-matching conventions shared by anchoring, evaluation and TEI emission.

These encode the *editorial conventions* observed on real editions — how the
printed page and the apparatus refer to the same words differently:

- accent-, case- and sigma-form folding (removing editorial brackets can
  strand a final sigma mid-word: Ὥς<τε> → Ὥςτε must equal Ὥστε);
- editorial bracket characters ( <>, [], ⟨⟩ ) mark insertions in the text
  and expansions in the apparatus — the brackets go, their content stays;
- inline witness references ([fol. 97 v° : A]) and glued verse numbers
  ((11)Αἴτησον) live in the TEXT side only and are removed as spans;
- words hyphenated around an inline reference or a line break rejoin;
- a glued ellipsis in a lemma (Ὅτι ...σωθήσεσθαι) separates a range.

Every rule carries its motivating example; none is speculative.
"""

from __future__ import annotations

import re
import unicodedata

_BRACKET_CHARS = "<>[]⟨⟩"
_INLINE_REF_SPAN = re.compile(r"\[[^\]]*\]")
_GLUED_VERSE = re.compile(r"\(\d+\)")
_GLUED_REF_PAREN = re.compile(r"\([^)]*\d[^)]*\)")
_HYPHEN_JOIN = re.compile(r"(?<=\S)-\s*-?\s*(?=\S)")
_HYPHEN_EOL = re.compile(r"(?<=\S)-\n\s*")


def fold(s: str) -> str:
  """Accent-, case- and sigma-form-insensitive comparison form."""
  d = unicodedata.normalize("NFD", s)
  return "".join(
    c for c in d if not unicodedata.combining(c)
  ).lower().replace("ς", "σ")


def norm_lemma(s: str) -> str:
  """Comparison form of an apparatus lemma."""
  s = s.replace("...", " ").replace("…", " ")
  return s.translate(str.maketrans("", "", _BRACKET_CHARS + "()"))


def norm_text(s: str) -> str:
  """Comparison form of a stretch of constituted text."""
  s = _INLINE_REF_SPAN.sub(" ", s)
  s = _GLUED_REF_PAREN.sub(" ", s)
  s = _HYPHEN_JOIN.sub("", s)
  s = _HYPHEN_EOL.sub("", s)
  return s.translate(str.maketrans("", "", "<>⟨⟩"))


_WORD_STRIP = ".,·;:!»«()-"


def text_words(before: str) -> list[str]:
  """Folded, normalized words of a text stretch, in order."""
  ws = [w.strip(_WORD_STRIP) for w in fold(norm_text(before)).split()]
  return [w for w in ws if w]


def lemma_words(lemma: str) -> list[str]:
  ws = [w for w in fold(norm_lemma(lemma)).replace(",", " ").split() if w]
  return ws


def is_range_lemma(lemma: str) -> bool:
  return bool(re.search(r"\.\.\.|…|[−–]", lemma))


def lemma_matches_before(lemma: str, before: str) -> bool:
  """Does the lemma correspond to the text immediately before its marker?

  Conventions accepted, each observed on the reference edition:
  full-sequence match; on multi-word/range lemmas the marker may follow any
  quoted word; on a range the marker may sit shortly after the span start;
  on a single-word lemma the marker may trail the clause by a word or two.
  """
  lw = lemma_words(lemma)
  if not lw:
    return False
  tw = text_words(before)
  if not tw:
    return False
  if tw[-len(lw):] == lw:
    return True
  rng = is_range_lemma(lemma)
  if len(lw) > 1 or rng:
    if tw[-1] in lw:
      return True
    return bool(rng and lw[0] in tw[-8:])
  return lw[0] in tw[-8:]


def locate_lemma_start(lemma: str, text: str, end_offset: int) -> int | None:
  """Character offset in ``text`` where the lemma begins, searching backwards
  from the marker at ``end_offset`` — or None when it cannot be established
  with confidence. Used to place the start anchor of a double-end-point
  apparatus link; None simply means the <app> carries only its end anchor.
  """
  lw = lemma_words(lemma)
  if not lw:
    return None

  # Work on source-offset-bearing tokens. Splitting only on whitespace made
  # ``similiter.Et`` one token and ``nat-\n\nuram`` two, while taking the last
  # occurrence of the lemma's first word shortened repeated lemmata such as
  # ``Ἠλὶ ἠλὶ`` to the second word. This treats punctuation as a boundary and
  # joins only explicit line-break hyphenation while retaining source offsets.
  window_start = max(0, end_offset - 1200)
  window = text[window_start:end_offset]
  masked = list(window)
  for rx in (_INLINE_REF_SPAN, _GLUED_REF_PAREN):
    for m in rx.finditer(window):
      masked[m.start():m.end()] = " " * (m.end() - m.start())
  searchable = "".join(masked)
  word_rx = re.compile(
    r"[^\W\d_]+(?:-\s+(?:\d{1,3}\s+)?[^\W\d_]+)*",
    flags=re.UNICODE,
  )
  tokens: list[tuple[str, int, int]] = []
  for m in word_rx.finditer(searchable):
    value = fold(re.sub(r"-\s+(?:\d{1,3}\s+)?", "", m.group(0)))
    if value:
      tokens.append((value, window_start + m.start(), window_start + m.end()))

  # The lemma ends at the printed marker/line/verse anchor, so only the token
  # sequence ending there is admissible. Requiring the complete sequence is
  # fail-closed: when the full start cannot be established, omit ``@from``
  # instead of manufacturing a plausible short span.
  if len(tokens) < len(lw):
    return None
  for stop in range(len(tokens), len(lw) - 1, -1):
    candidate = tokens[stop - len(lw):stop]
    if [token[0] for token in candidate] != lw:
      continue
    tail = text[candidate[-1][2]:end_offset]
    if not re.search(r"[^\W\d_]", tail, flags=re.UNICODE):
      return candidate[0][1]
  return None
