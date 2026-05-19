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
    change_log: list[dict[str, Any]] = field(default_factory=list)

    def known_symbols(self) -> set[str]:
        return set(self.symbol_table.values())

    def update_from_round(
        self,
        round_index: int,
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
                    "natural": natural,
                    "compact": compact,
                    "compression_ratio": metrics.get("compression_ratio", 0.0),
                }
            )

        self.version += 1
        change = {
            "round": round_index,
            "version": self.version,
            "architect_notes_excerpt": architect_notes[:500],
            "new_symbols": new_symbols,
            "reused_symbols": reused_symbols,
            "symbol_count": len(self.symbol_table),
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
            "change_log": self.change_log,
        }


def extract_symbols(text: str) -> set[str]:
    symbols: set[str] = set()
    for match in SYMBOL_RE.findall(text):
        token = match.strip()
        if not token or len(token) > 12:
            continue
        if any(char.isdigit() for char in token) or not token.isalpha() or len(token) <= 3:
            symbols.add(token)
    return symbols
