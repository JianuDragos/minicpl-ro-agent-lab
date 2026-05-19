"""Observational metrics for MiniCPL-Ro protocol rounds."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

from protocol_state import (
    extract_symbols,
    parse_new_token_events,
    parse_token_evolution_events,
    tokens_used_in_text,
)


COMPACT_KEYS = ("compact", "encoding", "code", "protocol", "machine")
NATURAL_WORD_RE = re.compile(r"[A-Za-zăâîșțĂÂÎȘȚ]{4,}")
PROTOCOL_MARKER_RE = re.compile(r"[#@$%&*+=:;./\\|!?~0-9_-]")


class Evaluator:
    def evaluate(
        self,
        phase: str,
        natural_phrase: str,
        architect_message: str,
        model_response: str,
        previous_compact: str,
        known_symbols: set[str],
        current_token_map: dict[str, str] | None = None,
        deprecated_tokens: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        compact = self._extract_compact_phrase(model_response)
        is_transport_error = model_response.strip().startswith("OLLAMA_ERROR:")
        current_token_map = current_token_map or {}
        deprecated_tokens = deprecated_tokens or {}
        natural_len = len(natural_phrase)
        compact_len = len(compact)
        compression_ratio = (
            round(natural_len / compact_len, 4) if compact_len > 0 else 0.0
        )
        symbols = set() if is_transport_error else extract_symbols(model_response)
        invented = symbols - known_symbols
        reused = symbols & known_symbols
        malformed = 0 if compact else 1
        drift = self._drift(previous_compact, compact)
        novelty = self._novelty(compact, known_symbols)
        reuse_rate = round(len(reused) / len(symbols), 4) if symbols else 0.0
        leakage = 0.0 if is_transport_error else self._natural_language_leakage(model_response)
        compact_usage = 0.0 if is_transport_error else self._compact_language_usage(compact, model_response)
        stability = self._stability(drift, reuse_rate, malformed)
        new_token_events = [] if is_transport_error else parse_new_token_events(model_response)
        evolution_events = [] if is_transport_error else parse_token_evolution_events(model_response)
        known_tokens_used = tokens_used_in_text(model_response, set(current_token_map.values()))
        deprecated_used = tokens_used_in_text(model_response, set(deprecated_tokens.keys()))
        fallback_count = self._human_language_fallback_count(
            phase=phase,
            compact=compact,
            leakage=leakage,
            compact_usage=compact_usage,
            known_tokens_used=known_tokens_used,
            new_token_events=new_token_events,
            evolution_events=evolution_events,
        )
        token_reuse_score = (
            round(len(known_tokens_used) / len(set(current_token_map.values())), 4)
            if current_token_map
            else 0.0
        )
        continuity = self._continuity_score(
            compact_usage=compact_usage,
            token_reuse_score=token_reuse_score,
            leakage=leakage,
            fallback_count=fallback_count,
            new_token_events_count=len(new_token_events),
            evolution_events_count=len(evolution_events),
        )

        return {
            "phase": phase,
            "natural_phrase": natural_phrase,
            "compact_phrase": compact,
            "natural_phrase_length": natural_len,
            "compact_phrase_length": compact_len,
            "compression_ratio": compression_ratio,
            "invented_symbol_count": len(invented),
            "reused_symbol_count": len(reused),
            "invented_symbols": sorted(invented),
            "reused_symbols": sorted(reused),
            "malformed_response_count": malformed,
            "protocol_drift_score": drift,
            "novelty_score": novelty,
            "compact_language_usage_score": compact_usage,
            "known_symbol_reuse_rate": reuse_rate,
            "natural_language_leakage_score": leakage,
            "protocol_stability_score": stability,
            "new_token_events_count": len(new_token_events),
            "token_evolution_events_count": len(evolution_events),
            "human_language_fallback_count": fallback_count,
            "compact_protocol_continuity_score": continuity,
            "token_reuse_after_creation_score": token_reuse_score,
            "deprecated_token_reuse_count": len(deprecated_used),
            "new_token_events": new_token_events,
            "token_evolution_events": evolution_events,
            "known_tokens_used": sorted(known_tokens_used),
            "deprecated_tokens_reused": sorted(deprecated_used),
            "architect_message_length": len(architect_message),
            "model_response_length": len(model_response),
            "research_observation": self._observation(
                compact=compact,
                drift=drift,
                novelty=novelty,
                leakage=leakage,
                compact_usage=compact_usage,
                malformed=malformed,
            ),
        }

    def _extract_compact_phrase(self, text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return ""
        if stripped.startswith("OLLAMA_ERROR:"):
            return ""

        json_candidate = self._extract_json(stripped)
        if json_candidate:
            for key in COMPACT_KEYS:
                value = json_candidate.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        for line in stripped.splitlines():
            normalized = line.strip().strip("-* ")
            lowered = normalized.lower()
            if any(key in lowered for key in COMPACT_KEYS):
                parts = re.split(r"[:=]", normalized, maxsplit=1)
                if len(parts) == 2 and parts[1].strip():
                    return parts[1].strip().strip("`\"'")

        shortest = min(
            (line.strip() for line in stripped.splitlines() if line.strip()),
            key=len,
            default="",
        )
        return shortest[:200]

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _drift(self, previous: str, current: str) -> float:
        if not previous and not current:
            return 0.0
        if not previous or not current:
            return 1.0
        return round(1.0 - SequenceMatcher(None, previous, current).ratio(), 4)

    def _novelty(self, compact: str, known_symbols: set[str]) -> float:
        if not compact:
            return 0.0
        symbols = extract_symbols(compact)
        if not symbols:
            return 0.0
        return round(len(symbols - known_symbols) / len(symbols), 4)

    def _compact_language_usage(self, compact: str, text: str) -> float:
        if not text.strip():
            return 0.0
        compact_signal = len(PROTOCOL_MARKER_RE.findall(text))
        short_tokens = sum(1 for token in text.split() if len(token) <= 4)
        compact_bonus = min(1.0, len(compact) / max(1, len(text))) if compact else 0.0
        score = (compact_signal / max(1, len(text))) + (short_tokens / max(1, len(text.split())))
        return round(min(1.0, (score / 2.0) + compact_bonus), 4)

    def _natural_language_leakage(self, text: str) -> float:
        tokens = text.split()
        if not tokens:
            return 0.0
        natural_words = NATURAL_WORD_RE.findall(text)
        return round(min(1.0, len(natural_words) / len(tokens)), 4)

    def _stability(self, drift: float, reuse_rate: float, malformed: int) -> float:
        if malformed:
            return 0.0
        return round(max(0.0, min(1.0, (1.0 - drift) * 0.7 + reuse_rate * 0.3)), 4)

    def _observation(
        self,
        compact: str,
        drift: float,
        novelty: float,
        leakage: float,
        compact_usage: float,
        malformed: int,
    ) -> str:
        if malformed:
            return "No compact form extracted; preserve as malformed or exploratory output."
        if drift > 0.75 and novelty > 0.5:
            return "High drift with high novelty; possible redesign, branch, or collapse."
        if compact_usage > 0.6 and leakage < 0.5:
            return "Response appears to use compact protocol heavily."
        if leakage > 0.8:
            return "Response remains mostly natural-language explanation."
        if compact:
            return "Compact form extracted; behavior appears usable for comparison."
        return "Unexpected output preserved for review."

    def _human_language_fallback_count(
        self,
        phase: str,
        compact: str,
        leakage: float,
        compact_usage: float,
        known_tokens_used: set[str],
        new_token_events: list[dict[str, str]],
        evolution_events: list[dict[str, str]],
    ) -> int:
        if phase != "autonomous_exploration":
            return 0
        if new_token_events or evolution_events or known_tokens_used:
            return 0
        if not compact:
            return 1
        return 1 if leakage >= 0.75 and compact_usage < 0.25 else 0

    def _continuity_score(
        self,
        compact_usage: float,
        token_reuse_score: float,
        leakage: float,
        fallback_count: int,
        new_token_events_count: int,
        evolution_events_count: int,
    ) -> float:
        event_signal = min(0.2, 0.05 * (new_token_events_count + evolution_events_count))
        score = compact_usage * 0.45 + token_reuse_score * 0.35 + (1.0 - leakage) * 0.2
        if fallback_count:
            score *= 0.5
        return round(max(0.0, min(1.0, score + event_signal)), 4)
