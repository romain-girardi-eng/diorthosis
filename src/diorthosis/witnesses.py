"""Structured witness states declared by an edition's registry."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .conspectus import Registry

_LETTER = r"A-Za-zÀ-ÖØ-öø-ÿĀ-ŽΑ-Ωα-ωϘ-ϡ"
_COMPOUND = re.compile(rf"^([{_LETTER}])(ac|pc|mr|c|\*|[1-9])$")

_HAND_LABELS = {
  "ac": "before correction",
  "pc": "after correction / corrector",
  "c": "after correction / corrector",
  "mr": "later hand (manus recentior)",
  "*": "reading that prompted a correction",
}


def decompose(siglum: str, registry: Registry) -> tuple[str, str]:
  """Split a declared-base witness state without inferring missing bases."""
  match = _COMPOUND.fullmatch(siglum)
  if match is None:
    return siglum, ""
  base, hand = match.groups()
  if base not in registry.witnesses:
    return siglum, ""
  return base, hand


def hand_label(hand: str) -> str:
  """Return the stable English expansion of a witness hand state."""
  if re.fullmatch(r"[1-9]", hand):
    return f"hand {hand}"
  return _HAND_LABELS.get(hand, "")


def witness_table(
  registry: Registry, used_sigla: Iterable[str],
) -> list[dict[str, str]]:
  """Describe only used sigla while preserving undeclared ones honestly."""
  rows: list[dict[str, str]] = []
  for siglum in sorted(set(used_sigla)):
    base, hand = decompose(siglum, registry)
    description = registry.witnesses.get(siglum)
    if description is None:
      description = registry.witnesses.get(base, "")
    rows.append({
      "siglum": siglum,
      "base": base,
      "hand": hand,
      "hand_label": hand_label(hand),
      "description": description,
    })
  return rows


__all__ = ["decompose", "hand_label", "witness_table"]
