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
    source_vocabulary: list[dict[str, str]] = field(default_factory=list)
    vocabulary_entries_total: int = 0
    vocabulary_entries_tokenized: int = 0
    vocabulary_coverage_ratio: float = 0.0
    categories_covered: list[str] = field(default_factory=list)
    tokenized_vocabulary_entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    change_log: list[dict[str, Any]] = field(default_factory=list)
    _vocabulary_lookup: dict[str, dict[str, str]] = field(default_factory=dict, repr=False)

    def known_symbols(self) -> set[str]:
        return set(self.symbol_table.values())

    def configure_vocabulary(self, vocabulary: list[dict[str, str]]) -> None:
        self.source_vocabulary = [dict(row) for row in vocabulary]
        self.vocabulary_entries_total = len(self.source_vocabulary)
        self._vocabulary_lookup = {}
        for row in self.source_vocabulary:
            for key in vocabulary_lookup_keys(row):
                self._vocabulary_lookup[key] = row
        self._refresh_vocabulary_coverage()

    def update_from_round(
        self,
        round_index: int,
        phase: str,
        architect_notes: str,
        model_response: str,
        metrics: dict[str, Any],
        agent_a_lexicon_events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        before = self.known_symbols()
        candidates = extract_symbols(model_response)
        lexicon_events = normalize_seed_events(agent_a_lexicon_events or [])
        model_lexicon_events = parse_new_token_events(model_response)
        for event in model_lexicon_events:
            event["source"] = "agent_b"
        lexicon_events.extend(model_lexicon_events)
        evolution_events = parse_token_evolution_events(model_response)

        new_symbols = sorted(symbol for symbol in candidates if symbol not in before)
        reused_symbols = sorted(symbol for symbol in candidates if symbol in before)

        for symbol in new_symbols:
            key = f"r{round_index}_{len(self.symbol_table) + 1}"
            self.symbol_table[key] = symbol

        for event in lexicon_events:
            event.update({"round": round_index, "phase": phase})
            self._annotate_lexicon_event(event)
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

        if lexicon_events or evolution_events:
            self._refresh_vocabulary_coverage()

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
            "source_vocabulary": self.source_vocabulary,
            "vocabulary_entries_total": self.vocabulary_entries_total,
            "vocabulary_entries_tokenized": self.vocabulary_entries_tokenized,
            "vocabulary_coverage_ratio": self.vocabulary_coverage_ratio,
            "categories_covered": self.categories_covered,
            "tokenized_vocabulary_entries": self.tokenized_vocabulary_entries,
            "change_log": self.change_log,
        }

    def vocabulary_status(self) -> dict[str, Any]:
        return {
            "vocabulary_entries_total": self.vocabulary_entries_total,
            "vocabulary_entries_tokenized": self.vocabulary_entries_tokenized,
            "vocabulary_coverage_ratio": self.vocabulary_coverage_ratio,
            "categories_covered": self.categories_covered,
        }

    def _annotate_lexicon_event(self, event: dict[str, Any]) -> None:
        row = self._match_vocabulary_entry(event.get("meaning", ""))
        if not row:
            event.setdefault("category", "")
            event.setdefault("concept_id", "")
            return
        event["category"] = row.get("category", "")
        event["concept_id"] = row.get("concept_id", "")
        event["ro"] = row.get("ro", "")
        event["en"] = row.get("en", "")

    def _match_vocabulary_entry(self, meaning: str) -> dict[str, str] | None:
        normalized = normalize_meaning(meaning)
        if normalized in self._vocabulary_lookup:
            return self._vocabulary_lookup[normalized]
        parts = [normalize_meaning(part) for part in re.split(r"[/|,;]", meaning)]
        for part in parts:
            if part in self._vocabulary_lookup:
                return self._vocabulary_lookup[part]
        return None

    def _refresh_vocabulary_coverage(self) -> None:
        tokenized: dict[str, dict[str, Any]] = {}
        for event in self.lexicon_events:
            concept_id = event.get("concept_id", "")
            if concept_id:
                tokenized[concept_id] = event
        self.tokenized_vocabulary_entries = tokenized
        self.vocabulary_entries_tokenized = len(tokenized)
        self.vocabulary_coverage_ratio = (
            round(self.vocabulary_entries_tokenized / self.vocabulary_entries_total, 4)
            if self.vocabulary_entries_total
            else 0.0
        )
        self.categories_covered = sorted(
            {
                event.get("category", "")
                for event in tokenized.values()
                if event.get("category")
            }
        )


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


def normalize_seed_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for event in events:
        meaning = str(event.get("meaning", "")).strip()
        token = str(event.get("token", "")).strip()
        if not meaning or not token:
            continue
        normalized.append(
            {
                "meaning": meaning,
                "token": token,
                "raw": event.get("raw", f'<NEW "{meaning}" = {token}>'),
                "source": event.get("source", "agent_a"),
                "category": event.get("category", ""),
                "concept_id": event.get("concept_id", ""),
                "ro": event.get("ro", ""),
                "en": event.get("en", ""),
            }
        )
    return normalized


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


def normalize_meaning(value: str) -> str:
    cleaned = value.strip().strip("\"'`").lower()
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def vocabulary_lookup_keys(row: dict[str, str]) -> set[str]:
    ro = row.get("ro", "")
    en = row.get("en", "")
    concept_id = row.get("concept_id", "")
    keys = {
        normalize_meaning(ro),
        normalize_meaning(en),
        normalize_meaning(concept_id),
        normalize_meaning(f"{ro} / {en}"),
        normalize_meaning(f"{en} / {ro}"),
    }
    if en.lower().startswith("to "):
        keys.add(normalize_meaning(en[3:]))
    if "/" in ro or "/" in en:
        for part in re.split(r"[/|]", f"{ro}/{en}"):
            keys.add(normalize_meaning(part))
    return {key for key in keys if key}
