"""Agent arena coordinating Codex-authored prompts and local Ollama responses."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluator import Evaluator
from ollama_client import OllamaClient
from protocol_state import ProtocolState


class AgentArena:
    def __init__(
        self,
        model: str,
        temperature: float,
        rounds: int,
        ollama_url: str,
        root: Path,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.rounds = rounds
        self.root = root
        self.ollama_url = ollama_url
        self.ollama = OllamaClient(base_url=ollama_url)
        self.evaluator = Evaluator()
        self.protocol = ProtocolState()
        self.vocabulary = self._load_vocabulary(root / "data" / "seed_vocabulary.csv")
        self.tasks = self._load_tasks(root / "data" / "seed_tasks.json")
        self.agent_a_prompt = (root / "prompts" / "agent_a_prompt.md").read_text(
            encoding="utf-8"
        )
        self.agent_b_prompt = (root / "prompts" / "agent_b_prompt.md").read_text(
            encoding="utf-8"
        )

    def run(self) -> dict[str, Any]:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log_path = self.root / "logs" / f"transcript_{run_id}.jsonl"
        state_path = self.root / "results" / f"protocol_state_{run_id}.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        round_records: list[dict[str, Any]] = []
        previous_compact = ""

        with log_path.open("w", encoding="utf-8") as transcript:
            self._write_event(
                transcript,
                {
                    "event": "run_started",
                    "run_id": run_id,
                    "model": self.model,
                    "temperature": self.temperature,
                    "rounds": self.rounds,
                    "ollama_url": self.ollama_url,
                    "vocabulary_size": len(self.vocabulary),
                    "task_count": len(self.tasks),
                },
            )

            for round_index in range(1, self.rounds + 1):
                task = self.tasks[(round_index - 1) % len(self.tasks)]
                architect_message = self._build_agent_a_message(round_index, task)
                model_prompt = self._build_agent_b_message(round_index, task, architect_message)
                result = self.ollama.generate(
                    model_prompt,
                    model=self.model,
                    temperature=self.temperature,
                    fallback=True,
                )
                response_text = result.response if result.ok else f"OLLAMA_ERROR: {result.error}"

                metrics = self.evaluator.evaluate(
                    natural_phrase=task["phrase"],
                    architect_message=architect_message,
                    model_response=response_text,
                    previous_compact=previous_compact,
                    known_symbols=self.protocol.known_symbols(),
                )
                previous_compact = metrics.get("compact_phrase", previous_compact)
                change = self.protocol.update_from_round(
                    round_index=round_index,
                    architect_notes=architect_message,
                    model_response=response_text,
                    metrics=metrics,
                )

                record = {
                    "event": "round_completed",
                    "round": round_index,
                    "task": task,
                    "agent_a_message": architect_message,
                    "agent_b_prompt": model_prompt,
                    "agent_b_response": response_text,
                    "model_used": result.model,
                    "ollama_ok": result.ok,
                    "ollama_error": result.error,
                    "metrics": metrics,
                    "protocol_change": change,
                    "raw_ollama": result.raw,
                }
                round_records.append(record)
                self._write_event(transcript, record)

            snapshot = self.protocol.snapshot()
            state_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            self._write_event(
                transcript,
                {
                    "event": "run_finished",
                    "run_id": run_id,
                    "protocol_state_path": str(state_path),
                },
            )

        return {
            "run_id": run_id,
            "transcript_path": log_path,
            "protocol_state_path": state_path,
            "rounds": round_records,
            "protocol_snapshot": self.protocol.snapshot(),
        }

    def _build_agent_a_message(self, round_index: int, task: dict[str, Any]) -> str:
        categories = ", ".join(sorted({item["category"] for item in self.vocabulary}))
        known = json.dumps(self.protocol.snapshot(), ensure_ascii=False)[:4000]
        return self.agent_a_prompt.format(
            round=round_index,
            task=json.dumps(task, ensure_ascii=False),
            categories=categories,
            known_protocol=known,
        )

    def _build_agent_b_message(
        self,
        round_index: int,
        task: dict[str, Any],
        architect_message: str,
    ) -> str:
        sample_vocab = self.vocabulary[:30]
        return self.agent_b_prompt.format(
            round=round_index,
            task=json.dumps(task, ensure_ascii=False),
            architect_message=architect_message,
            vocabulary=json.dumps(sample_vocab, ensure_ascii=False),
            protocol=json.dumps(self.protocol.snapshot(), ensure_ascii=False)[:6000],
        )

    def _load_vocabulary(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def _load_tasks(self, path: Path) -> list[dict[str, Any]]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_event(self, handle: Any, event: dict[str, Any]) -> None:
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        handle.flush()
