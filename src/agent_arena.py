"""Agent arena coordinating Codex-authored prompts and local Ollama responses."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluator import Evaluator
from ollama_client import OllamaClient
from protocol_state import ProtocolState

LEXICON_BATCH_SIZE = 15


class AgentArena:
    def __init__(
        self,
        model: str,
        temperature: float,
        rounds: int,
        bootstrap_rounds: int,
        lexicon_rounds: int,
        ollama_url: str,
        root: Path,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.rounds = rounds
        self.bootstrap_rounds = max(0, min(bootstrap_rounds, rounds))
        self.lexicon_rounds = max(0, min(lexicon_rounds, rounds - self.bootstrap_rounds))
        self.root = root
        self.ollama_url = ollama_url
        self.ollama = OllamaClient(base_url=ollama_url)
        self.evaluator = Evaluator()
        self.protocol = ProtocolState()
        self.vocabulary = self._load_vocabulary(root / "data" / "seed_vocabulary.csv")
        self.protocol.configure_vocabulary(self.vocabulary)
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
                    "bootstrap_rounds": self.bootstrap_rounds,
                    "lexicon_rounds": self.lexicon_rounds,
                    "ollama_url": self.ollama_url,
                    "vocabulary_size": len(self.vocabulary),
                    "task_count": len(self.tasks),
                },
            )

            for round_index in range(1, self.rounds + 1):
                phase = self._phase_for_round(round_index)
                task = self.tasks[(round_index - 1) % len(self.tasks)]
                lexicon_batch = self._lexicon_batch_for_round(round_index, phase)
                agent_a_lexicon_events = self._agent_a_lexicon_events(lexicon_batch)
                architect_message = self._build_agent_a_message(
                    round_index,
                    phase,
                    task,
                    lexicon_batch,
                    agent_a_lexicon_events,
                )
                model_prompt = self._build_agent_b_message(
                    round_index,
                    phase,
                    task,
                    lexicon_batch,
                    agent_a_lexicon_events,
                    architect_message,
                )
                result = self.ollama.generate(
                    model_prompt,
                    model=self.model,
                    temperature=self.temperature,
                    fallback=True,
                )
                response_text = result.response if result.ok else f"OLLAMA_ERROR: {result.error}"

                metrics = self.evaluator.evaluate(
                    phase=phase,
                    natural_phrase=task["phrase"],
                    architect_message=architect_message,
                    model_response=response_text,
                    previous_compact=previous_compact,
                    known_symbols=self.protocol.known_symbols(),
                    current_token_map=self.protocol.current_token_map,
                    deprecated_tokens=self.protocol.deprecated_tokens,
                )
                self._add_rolling_metrics(metrics, round_records)
                previous_compact = metrics.get("compact_phrase", previous_compact)
                change = self.protocol.update_from_round(
                    round_index=round_index,
                    phase=phase,
                    architect_notes=architect_message,
                    model_response=response_text,
                    metrics=metrics,
                    agent_a_lexicon_events=agent_a_lexicon_events,
                )

                record = {
                    "event": "round_completed",
                    "round": round_index,
                    "phase": phase,
                    "task": task,
                    "lexicon_batch": lexicon_batch,
                    "agent_a_lexicon_events": agent_a_lexicon_events,
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

    def _phase_for_round(self, round_index: int) -> str:
        if round_index <= self.bootstrap_rounds:
            return "bootstrap"
        if round_index <= self.bootstrap_rounds + self.lexicon_rounds:
            return "lexicon_expansion"
        return "autonomous_exploration"

    def _build_agent_a_message(
        self,
        round_index: int,
        phase: str,
        task: dict[str, Any],
        lexicon_batch: list[dict[str, str]],
        agent_a_lexicon_events: list[dict[str, Any]],
    ) -> str:
        categories = ", ".join(sorted({item["category"] for item in self.vocabulary}))
        known = json.dumps(self.protocol.snapshot(), ensure_ascii=False)[:4000]
        lexicon_status = json.dumps(self.protocol.vocabulary_status(), ensure_ascii=False)
        if phase == "bootstrap":
            phase_guidance = (
                "Bootstrap phase. Give structured pressure: compress the task phrase, "
                "invent shorter symbols, preserve useful meaning, and propose reusable rules."
            )
        elif phase == "lexicon_expansion":
            phase_guidance = (
                "Lexicon expansion phase. Focus Agent B on the vocabulary batch. Ask it to create "
                "one exact <NEW \"ro / en\" = token> declaration for every batch entry before any "
                "optional notes. Prefer 1-character tokens for very common concepts, 2-character "
                "tokens for common concepts, and 3-character tokens only when needed. Avoid duplicate "
                "tokens unless intentionally overloaded. Use <EVOLVE old -> new reason> when improving a token."
            )
        else:
            phase_guidance = (
                "Autonomous exploration phase. Give a broad objective-driven prompt. "
                "Prefer existing compact tokens from the current token map. If a needed concept "
                "is missing, ask Agent B to declare it with <NEW meaning = token> and continue "
                "in compact protocol. If a shorter or more systematic token appears, allow "
                "<EVOLVE old_token -> new_token reason>. Do not force a fixed format; let Agent B "
                "refine, abandon, merge, redesign, create sub-languages, or communicate directly "
                "in the compact protocol."
            )
        return self.agent_a_prompt.format(
            round=round_index,
            phase=phase,
            phase_guidance=phase_guidance,
            task=json.dumps(task, ensure_ascii=False),
            categories=categories,
            lexicon_batch=json.dumps(lexicon_batch, ensure_ascii=False),
            lexicon_batch_lines=format_lexicon_batch_lines(lexicon_batch),
            lexicon_suggestions=format_lexicon_events(agent_a_lexicon_events),
            lexicon_status=lexicon_status,
            known_protocol=known,
        )

    def _build_agent_b_message(
        self,
        round_index: int,
        phase: str,
        task: dict[str, Any],
        lexicon_batch: list[dict[str, str]],
        agent_a_lexicon_events: list[dict[str, Any]],
        architect_message: str,
    ) -> str:
        sample_vocab = self.vocabulary[:30]
        if phase == "bootstrap":
            phase_guidance = (
                "Bootstrap: produce a compact candidate and any reusable symbols/rules. "
                "A named compact/code/encoding line is helpful for measurement."
            )
        elif phase == "lexicon_expansion":
            phase_guidance = (
                "Lexicon expansion: create compact tokens for the vocabulary batch, not only meta-protocol ideas. "
                "For every batch entry, emit a literal line like <NEW \"apă / water\" = w> using the exact "
                "Romanian / English text shown in the batch. Use very short tokens, avoid accidental duplicates, "
                "and use <EVOLVE old -> new reason> if a better token replaces an earlier one. Keep explanation "
                "short; the token events are the main output."
            )
        else:
            phase_guidance = (
                "Autonomous exploration: pursue token efficiency freely inside the protocol-design experiment. "
                "Prefer existing compact tokens after they exist. If a concept is missing, create it "
                "with <NEW normal_word_or_meaning = compact_token> and then continue in compact protocol. "
                "If a better token appears, use <EVOLVE old_token -> new_token reason>. You may answer "
                "mostly in compact language, redesign it, merge protocol families, or self-propose the "
                "next experiment. No external actions are allowed."
            )
        return self.agent_b_prompt.format(
            round=round_index,
            phase=phase,
            phase_guidance=phase_guidance,
            task=json.dumps(task, ensure_ascii=False),
            architect_message=architect_message,
            vocabulary=json.dumps(sample_vocab, ensure_ascii=False),
            lexicon_batch=json.dumps(lexicon_batch, ensure_ascii=False),
            lexicon_batch_lines=format_lexicon_batch_lines(lexicon_batch),
            lexicon_suggestions=format_lexicon_events(agent_a_lexicon_events),
            lexicon_status=json.dumps(self.protocol.vocabulary_status(), ensure_ascii=False),
            protocol=json.dumps(self.protocol.snapshot(), ensure_ascii=False)[:6000],
        )

    def _lexicon_batch_for_round(
        self,
        round_index: int,
        phase: str,
    ) -> list[dict[str, str]]:
        if phase != "lexicon_expansion" or not self.vocabulary:
            return []
        lexicon_round_index = round_index - self.bootstrap_rounds - 1
        start = (lexicon_round_index * LEXICON_BATCH_SIZE) % len(self.vocabulary)
        return [
            self.vocabulary[(start + offset) % len(self.vocabulary)]
            for offset in range(min(LEXICON_BATCH_SIZE, len(self.vocabulary)))
        ]

    def _agent_a_lexicon_events(self, lexicon_batch: list[dict[str, str]]) -> list[dict[str, Any]]:
        if not lexicon_batch:
            return []
        used_tokens = set(self.protocol.current_token_map.values())
        events: list[dict[str, Any]] = []
        for item in lexicon_batch:
            meaning = f"{item.get('ro', '')} / {item.get('en', '')}"
            token = unique_token(token_candidate(item), used_tokens)
            used_tokens.add(token)
            events.append(
                {
                    "meaning": meaning,
                    "token": token,
                    "raw": f'<NEW "{meaning}" = {token}>',
                    "source": "agent_a",
                    "category": item.get("category", ""),
                    "concept_id": item.get("concept_id", ""),
                    "ro": item.get("ro", ""),
                    "en": item.get("en", ""),
                }
            )
        return events

    def _add_rolling_metrics(
        self,
        metrics: dict[str, Any],
        previous_records: list[dict[str, Any]],
    ) -> None:
        previous_metrics = [record["metrics"] for record in previous_records]
        compact_lengths = [
            item.get("compact_phrase_length", 0)
            for item in previous_metrics
            if item.get("compact_phrase_length", 0) > 0
        ]
        if metrics.get("compact_phrase_length", 0) > 0:
            compact_lengths.append(metrics["compact_phrase_length"])

        ratios = [item.get("compression_ratio", 0.0) for item in previous_metrics]
        ratios.append(metrics.get("compression_ratio", 0.0))

        metrics["average_compact_length"] = (
            round(sum(compact_lengths) / len(compact_lengths), 4)
            if compact_lengths
            else 0.0
        )
        metrics["best_compression_ratio_so_far"] = round(max(ratios, default=0.0), 4)

    def _load_vocabulary(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def _load_tasks(self, path: Path) -> list[dict[str, Any]]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_event(self, handle: Any, event: dict[str, Any]) -> None:
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        handle.flush()


def format_lexicon_batch_lines(batch: list[dict[str, str]]) -> str:
    if not batch:
        return "No lexicon batch for this phase."
    return "\n".join(
        f"- {item.get('category', '')} | {item.get('concept_id', '')} | "
        f"\"{item.get('ro', '')} / {item.get('en', '')}\""
        for item in batch
    )


def format_lexicon_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No Agent A lexicon token targets for this phase."
    return "\n".join(event["raw"] for event in events)


def token_candidate(item: dict[str, str]) -> str:
    ro = item.get("ro", "")
    en = item.get("en", "")
    common = {
        "eu / i": "i",
        "tu / you": "u",
        "apă / water": "w",
        "mâncare / food": "f",
        "salut / hello": "h",
        "a vrea / to want": "wn",
        "a avea nevoie / to need": "nd",
        "calculator / computer": "pc",
        "ajutor / help": "hp",
    }
    key = f"{ro} / {en}".lower()
    if key in common:
        return common[key]

    source = en[3:] if en.lower().startswith("to ") else en
    slug = ascii_slug(source or ro)
    words = [word for word in slug.split("_") if word]
    if len(words) > 1:
        candidate = "".join(word[0] for word in words[:3])
    else:
        word = words[0] if words else "x"
        consonants = "".join(char for char in word if char not in "aeiou")
        candidate = (consonants or word)[:2]
    return candidate[:3] or "x"


def unique_token(candidate: str, used_tokens: set[str]) -> str:
    token = sanitize_token(candidate)
    if token not in used_tokens:
        return token
    for suffix in "123456789abcdefghijklmnopqrstuvwxyz":
        next_token = sanitize_token(f"{token}{suffix}")
        if next_token not in used_tokens:
            return next_token
    index = 1
    while True:
        next_token = sanitize_token(f"{token}{index}")
        if next_token not in used_tokens:
            return next_token
        index += 1


def sanitize_token(token: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_?]", "", token)
    return cleaned[:4] or "x"


def ascii_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = re.sub(r"[^A-Za-z0-9]+", "_", ascii_value.lower()).strip("_")
    return ascii_value or "x"
