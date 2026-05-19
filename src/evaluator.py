"""Observational metrics for MiniCPL-Ro protocol rounds."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

from protocol_state import extract_symbols


COMPACT_KEYS = ("compact", "encoding", "code", "protocol", "machine")


class Evaluator:
    def evaluate(
        self,
        natural_phrase: str,
        architect_message: str,
        model_response: str,
        previous_compact: str,
        known_symbols: set[str],
    ) -> dict[str, Any]:
        compact = self._extract_compact_phrase(model_response)
        natural_len = len(natural_phrase)
        compact_len = len(compact)
        compression_ratio = (
            round(natural_len / compact_len, 4) if compact_len > 0 else 0.0
        )
        symbols = extract_symbols(model_response)
        invented = symbols - known_symbols
        reused = symbols & known_symbols
        malformed = 0 if compact else 1
        drift = self._drift(previous_compact, compact)
        novelty = self._novelty(compact, known_symbols)

        return {
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
            "architect_message_length": len(architect_message),
            "model_response_length": len(model_response),
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
