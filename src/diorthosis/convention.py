"""Shared evidence objects and measurements for convention gates.

A convention gate decides whether a WHOLE apparatus band belongs to one of
the implemented grammar families.  It does not parse an individual entry for
emission.  A refusal is evidence-bearing so downstream review and measurement
can distinguish an honest convention refusal from an entry-local parse miss.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GateDecision:
  grammar: str
  accepted: bool
  evidence: str

  @classmethod
  def accept(cls, grammar: str) -> GateDecision:
    return cls(grammar=grammar, accepted=True, evidence="")

  @classmethod
  def refuse(cls, grammar: str, reason: str) -> GateDecision:
    return cls(
      grammar=grammar,
      accepted=False,
      evidence=f"{grammar} convention gate refused band: {reason}",
    )


def token_count(text: str) -> int:
  """Whitespace-token count used by trial-parse consumption thresholds."""
  return len(text.split())


def unconsumed_token_ratio(entries: list[object]) -> float:
  """Share of trial-entry tokens whose entry parser refused.

  Trial entry objects share the ``raw`` and ``parsed`` attributes across the
  verse, line, and paragraph grammars.  The ratio is token-weighted: one long
  prose/tier fragment cannot hide behind many tiny successful entries.
  """
  total = sum(token_count(str(entry.raw)) for entry in entries)
  refused = sum(
    token_count(str(entry.raw)) for entry in entries
    if not bool(entry.parsed)
  )
  return refused / max(total, 1)
