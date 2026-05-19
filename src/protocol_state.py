"""State container for the evolving compact protocol."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


SYMBOL_RE = re.compile(r"[A-Za-z0-9_#@$%&*+=:;./\\|!?~-]{1,12}")


@dataclass
class ProtocolState:
    version: int = 0
    symbol_table: dict[str, str] = field(default_factory=dict)
    grammar_rules: list[str] = field(default_factory=list)
    compact_examples: list[dict[str, Any]] = field(default_factory=list)
    protocol_fragments: list[dict[str, Any]] = field(default_factory=list)
    protocol_usage_examples: list[dict[str, Any]] = field(default_factory=list)
    drift_observations: list[dict[str, Any]] = field(default_factory=list)
    change_log: list[dict[str, Any]] = field(default_factory=list)

    def known_symbols(self) -> set[str]:
        return set(self.symbol_table.values())

    def update_from_round(
        self,
        round_index: int,
        phase: str,
        architect_notes: str,
        model_response: str,
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        before = self.known_symbols()
        candidates = extract_symbols(model_response)

        new_symbols = sorted(symbol for symbol in candidates if symbol not in before)
        reused_symbols = sorted(symbol for symbol in candidates if symbol in before)

        for symbol in new_symbols:
            key = f"r{round_index}_{len(self.symbol_table) + 1}"
            self.symbol_table[key] = symbol

        compact = metrics.get("compact_phrase", "")
        natural = metrics.get("natural_phrase", "")
        if compact:
            self.compact_examples.append(
                {
                    "round": round_index,
                    "phase": phase,
                    "natural": natural,
                    "compact": compact,
                    "compression_ratio": metrics.get("compression_ratio", 0.0),
                    "usage_score": metrics.get("compact_language_usage_score", 0.0),
                }
            )

        fragments = extract_protocol_fragments(model_response)
        for fragment in fragments:
            self.protocol_fragments.append(
                {"round": round_index, "phase": phase, "fragment": fragment}
            )

        if metrics.get("compact_language_usage_score", 0.0) >= 0.25 and compact:
            self.protocol_usage_examples.append(
                {
                    "round": round_index,
                    "phase": phase,
                    "natural": natural,
                    "compact": compact,
                    "response_excerpt": model_response[:500],
                    "usage_score": metrics.get("compact_language_usage_score", 0.0),
                }
            )

        if (
            metrics.get("protocol_drift_score", 0.0) > 0.7
            or metrics.get("malformed_response_count", 0) > 0
            or "collapse" in model_response.lower()
            or "abandon" in model_response.lower()
        ):
            self.drift_observations.append(
                {
                    "round": round_index,
                    "phase": phase,
                    "compact": compact,
                    "drift": metrics.get("protocol_drift_score", 0.0),
                    "observation": metrics.get("research_observation", ""),
                    "response_excerpt": model_response[:500],
                }
            )

        self.version += 1
        change = {
            "round": round_index,
            "phase": phase,
            "version": self.version,
            "architect_notes_excerpt": architect_notes[:500],
            "new_symbols": new_symbols,
            "reused_symbols": reused_symbols,
            "symbol_count": len(self.symbol_table),
            "fragments": fragments,
            "metrics": metrics,
        }
        self.change_log.append(change)
        return change

    def best_examples(self, limit: int = 10) -> list[dict[str, Any]]:
        return sorted(
            self.compact_examples,
            key=lambda item: item.get("compression_ratio", 0.0),
            reverse=True,
        )[:limit]

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "symbol_table": self.symbol_table,
            "grammar_rules": self.grammar_rules,
            "compact_examples": self.compact_examples,
            "protocol_fragments": self.protocol_fragments,
            "protocol_usage_examples": self.protocol_usage_examples,
            "drift_observations": self.drift_observations,
            "change_log": self.change_log,
        }


def extract_symbols(text: str) -> set[str]:
    if text.strip().startswith("OLLAMA_ERROR:"):
        return set()
    symbols: set[str] = set()
    for match in SYMBOL_RE.findall(text):
        token = match.strip()
        if not token or len(token) > 12:
            continue
        if any(char.isdigit() for char in token) or not token.isalpha() or len(token) <= 3:
            symbols.add(token)
    return symbols


def extract_protocol_fragments(text: str, limit: int = 12) -> list[str]:
    if text.strip().startswith("OLLAMA_ERROR:"):
        return []
    fragments: list[str] = []
    for line in text.splitlines():
        normalized = line.strip().strip("-* ")
        if not normalized:
            continue
        lowered = normalized.lower()
        has_protocol_marker = any(marker in normalized for marker in ":=|#@$%&*/\\0123456789")
        names_rule = any(word in lowered for word in ("rule", "symbol", "grammar", "compact", "code", "protocol"))
        if has_protocol_marker or names_rule:
            fragments.append(normalized[:240])
        if len(fragments) >= limit:
            break
    return fragments
