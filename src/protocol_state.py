"""State container for the evolving compact protocol."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


SYMBOL_RE = re.compile(r"[A-Za-z0-9_#@$%&*+=:;./\\|!?~-]{1,12}")
NEW_EVENT_RE = re.compile(r"<NEW\s+(.+?)\s*=\s*([^\s>]+)\s*>", re.IGNORECASE)
EVOLVE_EVENT_RE = re.compile(r"<EVOLVE\s+([^\s>]+)\s*->\s*([^\s>]+)(?:\s+([^>]*?))?>", re.IGNORECASE)


@dataclass
class ProtocolState:
    version: int = 0
    symbol_table: dict[str, str] = field(default_factory=dict)
    grammar_rules: list[str] = field(default_factory=list)
    compact_examples: list[dict[str, Any]] = field(default_factory=list)
    protocol_fragments: list[dict[str, Any]] = field(default_factory=list)
    protocol_usage_examples: list[dict[str, Any]] = field(default_factory=list)
    drift_observations: list[dict[str, Any]] = field(default_factory=list)
    lexicon_events: list[dict[str, Any]] = field(default_factory=list)
    token_evolution_events: list[dict[str, Any]] = field(default_factory=list)
    current_token_map: dict[str, str] = field(default_factory=dict)
    deprecated_tokens: dict[str, dict[str, Any]] = field(default_factory=dict)
    compact_conversation_examples: list[dict[str, Any]] = field(default_factory=list)
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
        lexicon_events = parse_new_token_events(model_response)
        evolution_events = parse_token_evolution_events(model_response)

        new_symbols = sorted(symbol for symbol in candidates if symbol not in before)
        reused_symbols = sorted(symbol for symbol in candidates if symbol in before)

        for symbol in new_symbols:
            key = f"r{round_index}_{len(self.symbol_table) + 1}"
            self.symbol_table[key] = symbol

        for event in lexicon_events:
            event.update({"round": round_index, "phase": phase})
            self.lexicon_events.append(event)
            self.current_token_map[event["meaning"]] = event["token"]
            self.symbol_table[f"lex_{round_index}_{len(self.lexicon_events)}"] = event["token"]

        for event in evolution_events:
            event.update({"round": round_index, "phase": phase})
            self.token_evolution_events.append(event)
            self.deprecated_tokens[event["old_token"]] = {
                "new_token": event["new_token"],
                "reason": event["reason"],
                "round": round_index,
                "phase": phase,
            }
            for meaning, token in list(self.current_token_map.items()):
                if token == event["old_token"]:
                    self.current_token_map[meaning] = event["new_token"]
            self.symbol_table[f"evo_{round_index}_{len(self.token_evolution_events)}"] = event["new_token"]

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

        if phase == "autonomous_exploration" and compact:
            reused_known_tokens = tokens_used_in_text(model_response, set(self.current_token_map.values()))
            if (
                metrics.get("compact_protocol_continuity_score", 0.0) >= 0.25
                or reused_known_tokens
                or lexicon_events
                or evolution_events
            ):
                self.compact_conversation_examples.append(
                    {
                        "round": round_index,
                        "phase": phase,
                        "natural": natural,
                        "compact": compact,
                        "known_tokens_used": sorted(reused_known_tokens),
                        "new_events": lexicon_events,
                        "evolution_events": evolution_events,
                        "continuity_score": metrics.get("compact_protocol_continuity_score", 0.0),
                        "response_excerpt": model_response[:700],
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
            "lexicon_events": lexicon_events,
            "token_evolution_events": evolution_events,
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
            "lexicon_events": self.lexicon_events,
            "token_evolution_events": self.token_evolution_events,
            "current_token_map": self.current_token_map,
            "deprecated_tokens": self.deprecated_tokens,
            "compact_conversation_examples": self.compact_conversation_examples,
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


def parse_new_token_events(text: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    if text.strip().startswith("OLLAMA_ERROR:"):
        return events
    for match in NEW_EVENT_RE.finditer(text):
        meaning = match.group(1).strip().strip("\"'`")
        token = match.group(2).strip().strip("\"'`")
        if meaning and token:
            events.append({"meaning": meaning, "token": token, "raw": match.group(0)})
    return events


def parse_token_evolution_events(text: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    if text.strip().startswith("OLLAMA_ERROR:"):
        return events
    for match in EVOLVE_EVENT_RE.finditer(text):
        old_token = match.group(1).strip().strip("\"'`")
        new_token = match.group(2).strip().strip("\"'`")
        reason = (match.group(3) or "").strip()
        if old_token and new_token:
            events.append(
                {
                    "old_token": old_token,
                    "new_token": new_token,
                    "reason": reason,
                    "raw": match.group(0),
                }
            )
    return events


def tokens_used_in_text(text: str, tokens: set[str]) -> set[str]:
    used: set[str] = set()
    if not text or not tokens:
        return used
    for token in tokens:
        if token and token in text:
            used.add(token)
    return used
