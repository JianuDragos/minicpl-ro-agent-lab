"""Small Ollama API client for MiniCPL-Ro experiments."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class OllamaResult:
    model: str
    response: str
    raw: dict[str, Any]
    ok: bool
    error: str | None = None


class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout_seconds: int = 180,
        fallback_model: str = "gpt-oss:20b",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.fallback_model = fallback_model

    def generate(
        self,
        prompt: str,
        model: str,
        temperature: float = 1.0,
        fallback: bool = True,
    ) -> OllamaResult:
        result = self._generate_once(prompt, model, temperature)
        if result.ok or not fallback or model == self.fallback_model:
            return result

        fallback_result = self._generate_once(prompt, self.fallback_model, temperature)
        if not fallback_result.ok:
            fallback_result.error = (
                f"primary failed: {result.error}; fallback failed: {fallback_result.error}"
            )
        return fallback_result

    def _generate_once(
        self,
        prompt: str,
        model: str,
        temperature: float,
    ) -> OllamaResult:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": temperature},
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw_body)
            model_response = str(parsed.get("response", ""))
            return OllamaResult(model=model, response=model_response, raw=parsed, ok=True)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            return OllamaResult(
                model=model,
                response="",
                raw={"request": payload},
                ok=False,
                error=str(exc),
            )
