"""True Codex <-> Qwen debate arena for Phase V experiments."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_arena import token_candidate, unique_token
from codex_client import CodexClient, CodexResult
from evaluator import Evaluator
from language_map import LanguageMapEntry, read_language_map_csv
from ollama_client import OllamaClient, OllamaResult
from protocol_state import ProtocolState


DEBATE_CATEGORIES = [
    "pronouns",
    "verbs",
    "objects",
    "emotions",
    "questions",
    "time",
    "actions",
    "software/project terms",
    "phrase macros",
    "grammar/compression markers",
]

TEST_SENTENCES = [
    "salut, ce faci?",
    "vreau apă",
    "am nevoie de calculator",
    "poți să mă ajuți?",
    "explică proiectul",
    "I need help",
    "I want food",
    "create compact code for this sentence",
    "update the token map",
    "continue the experiment",
]

DEBATE_PHASE_TEMPLATE = "phase{phase_id}_debate"
STRICT_PHASE_TEMPLATE = "phase{phase_id}_strict_language"
WORD_RE = re.compile(r"[\wăâîșțĂÂÎȘȚ]+", re.UNICODE)
HUMAN_WORD_RE = re.compile(r"[A-Za-zăâîșțĂÂÎȘȚ]+", re.UNICODE)
NEW_OR_EVOLVE_RE = re.compile(r"<(?:NEW|EVOLVE)\b[^>]*>", re.IGNORECASE | re.DOTALL)
SEND_OR_RECV_RE = re.compile(r"<(?:SEND|RECV)\b[^>]*>", re.IGNORECASE | re.DOTALL)
COMPACT_ATTR_RE = re.compile(r'\bcompact="([^"]*)"', re.IGNORECASE)


class DualAgentArena:
    def __init__(
        self,
        model: str,
        temperature: float,
        phase_id: int,
        debate_turns_per_agent: int,
        debate_target_new_entries: int,
        receiver_test: bool,
        reward_mode: bool,
        ollama_url: str,
        root: Path,
        strict_language_mode: bool = False,
        language_map_path: Path | None = None,
        human_leak_penalty: int = 0,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.phase_id = phase_id
        self.strict_language_mode = strict_language_mode
        self.phase_name = (
            STRICT_PHASE_TEMPLATE.format(phase_id=phase_id)
            if strict_language_mode
            else DEBATE_PHASE_TEMPLATE.format(phase_id=phase_id)
        )
        self.debate_turns_per_agent = max(1, debate_turns_per_agent)
        self.debate_target_new_entries = max(0, debate_target_new_entries)
        self.receiver_test = receiver_test
        self.reward_mode = reward_mode
        self.ollama_url = ollama_url
        self.root = root
        self.language_map_path = self._resolve_language_map_path(language_map_path)
        self.human_leak_penalty = max(0, human_leak_penalty)
        self.ollama = OllamaClient(base_url=ollama_url, timeout_seconds=240)
        self.codex = CodexClient(root=root, timeout_seconds=600)
        self.evaluator = Evaluator()
        self.vocabulary = self._load_vocabulary(root / "data" / "seed_vocabulary.csv")
        self.tasks = self._load_tasks(root / "data" / "seed_tasks.json")
        self.language_map_entries = (
            read_language_map_csv(self.language_map_path) if strict_language_mode else []
        )
        self.language_entries_by_category = self._language_entries_by_category()
        self.language_token_set = {
            entry.compact_token for entry in self.language_map_entries if entry.compact_token
        }
        self.language_token_to_entry = {
            entry.compact_token: entry for entry in self.language_map_entries if entry.compact_token
        }
        self.protocol = (
            self._strict_language_protocol()
            if strict_language_mode
            else self._load_latest_protocol_state()
        )
        self.start_dictionary_size = len(self.protocol.current_token_map)
        self.previous_compact = ""
        self.message_index = len(self.protocol.change_log) + 1

    def run(self) -> dict[str, Any]:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        results_dir = self.root / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        output_prefix = (
            f"phase{self.phase_id}_strict_language"
            if self.strict_language_mode
            else f"phase{self.phase_id}_debate"
        )
        jsonl_path = results_dir / f"{output_prefix}_{run_id}.jsonl"
        md_path = results_dir / f"{output_prefix}_{run_id}.md"
        state_path = results_dir / f"protocol_state_{output_prefix}_{run_id}.json"
        codex_output_dir = results_dir / "codex_messages" / run_id
        codex_output_dir.mkdir(parents=True, exist_ok=True)

        records: list[dict[str, Any]] = []
        tests: list[dict[str, Any]] = []
        last_qwen_message = ""
        last_test: dict[str, Any] | None = None

        md_path.write_text(self._markdown_header(run_id), encoding="utf-8")
        with jsonl_path.open("w", encoding="utf-8") as jsonl:
            self._write_jsonl(
                jsonl,
                {
                    "event": "debate_started",
                    "run_id": run_id,
                    "phase_id": self.phase_id,
                    "phase": self.phase_name,
                    "model": self.model,
                    "temperature": self.temperature,
                    "target_new_entries": self.debate_target_new_entries,
                    "start_dictionary_size": self.start_dictionary_size,
                    "receiver_test": self.receiver_test,
                    "reward_mode": self.reward_mode,
                    "strict_language_mode": self.strict_language_mode,
                    "language_map_path": str(self.language_map_path) if self.strict_language_mode else "",
                    "human_leak_penalty": self.human_leak_penalty,
                    "language_map_entry_count": len(self.language_map_entries),
                },
            )

            for turn in range(1, self.debate_turns_per_agent + 1):
                if self._target_reached():
                    break

                category = DEBATE_CATEGORIES[(turn - 1) % len(DEBATE_CATEGORIES)]
                vocabulary_batch = self._vocabulary_batch(category, limit=24)
                context = self._build_context(
                    turn=turn,
                    category=category,
                    vocabulary_batch=vocabulary_batch,
                    last_message=last_qwen_message,
                    last_test=last_test,
                )

                codex_prompt = self._build_agent_prompt(
                    speaker="Codex",
                    other_agent="Qwen",
                    turn=turn,
                    category=category,
                    vocabulary_batch=vocabulary_batch,
                    context=context,
                    last_message=last_qwen_message,
                )
                codex_output_path = codex_output_dir / f"codex_turn_{turn:03d}.txt"
                codex_result = self.codex.exec(codex_prompt, codex_output_path)
                codex_response = (
                    codex_result.response
                    if codex_result.ok
                    else f"CODEX_ERROR: {codex_result.error or codex_result.stderr}"
                )
                codex_update = self._apply_agent_message(
                    speaker="Codex",
                    response=codex_response,
                    turn=turn,
                    category=category,
                    context=context,
                )

                qwen_prompt = self._build_agent_prompt(
                    speaker="Qwen",
                    other_agent="Codex",
                    turn=turn,
                    category=category,
                    vocabulary_batch=vocabulary_batch,
                    context=context,
                    last_message=codex_response,
                )
                qwen_result = self.ollama.generate(
                    qwen_prompt,
                    model=self.model,
                    temperature=self.temperature,
                    fallback=True,
                )
                qwen_response = (
                    qwen_result.response
                    if qwen_result.ok
                    else f"OLLAMA_ERROR: {qwen_result.error}"
                )
                qwen_update = self._apply_agent_message(
                    speaker="Qwen",
                    response=qwen_response,
                    turn=turn,
                    category=category,
                    context=qwen_prompt,
                )

                strict_turn_penalty = (
                    codex_update["metrics"].get("human_leak_penalty_total", 0)
                    + qwen_update["metrics"].get("human_leak_penalty_total", 0)
                )
                test_result = (
                    self._run_sender_receiver_test(
                        turn,
                        strict_turn_penalty=strict_turn_penalty,
                    )
                    if self.receiver_test
                    else None
                )
                if test_result:
                    tests.append(test_result)
                    self.protocol.sender_receiver_tests.append(test_result)
                    if self.reward_mode:
                        self.protocol.reward_history.append(
                            {
                                "turn": turn,
                                "phase": self.phase_name,
                                "final_reward_score": test_result.get("final_reward_score", 0.0),
                                "base_final_reward_score": test_result.get("base_final_reward_score", test_result.get("final_reward_score", 0.0)),
                                "human_leak_penalty_total": test_result.get("human_leak_penalty_total", 0.0),
                                "compression_ratio": test_result.get("compression_ratio", 0.0),
                                "decode_success_score": test_result.get("decode_success_score", 0.0),
                            }
                        )

                codex_record = self._message_record(
                    run_id=run_id,
                    turn=turn,
                    speaker="Codex",
                    response=codex_response,
                    update=codex_update,
                    category=category,
                    result=codex_result,
                    test_result=test_result,
                )
                qwen_record = self._message_record(
                    run_id=run_id,
                    turn=turn,
                    speaker="Qwen",
                    response=qwen_response,
                    update=qwen_update,
                    category=category,
                    result=qwen_result,
                    test_result=test_result,
                )
                for record in (codex_record, qwen_record):
                    records.append(record)
                    self.protocol.debate_records.append(record)
                    self._write_jsonl(jsonl, record)
                if test_result:
                    self._write_jsonl(jsonl, test_result)

                self._append_markdown_turn(
                    md_path=md_path,
                    turn=turn,
                    category=category,
                    codex_record=codex_record,
                    qwen_record=qwen_record,
                    test_result=test_result,
                )
                last_qwen_message = qwen_response
                last_test = test_result

            snapshot = self.protocol.snapshot()
            state_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            self._write_jsonl(
                jsonl,
                {
                    "event": "debate_finished",
                    "run_id": run_id,
                    "phase_id": self.phase_id,
                    "phase": self.phase_name,
                    "turns_completed": len({record["turn"] for record in records}),
                    "start_dictionary_size": self.start_dictionary_size,
                    "final_dictionary_size": len(self.protocol.current_token_map),
                    "new_entries_created": self._new_entries_created(),
                    "target_new_entries": self.debate_target_new_entries,
                    "protocol_state_path": str(state_path),
                    "strict_language_mode": self.strict_language_mode,
                    "language_map_path": str(self.language_map_path) if self.strict_language_mode else "",
                    "human_leak_penalty": self.human_leak_penalty,
                },
            )

        return {
            "run_id": run_id,
            "phase_id": self.phase_id,
            "phase": self.phase_name,
            "jsonl_path": jsonl_path,
            "markdown_path": md_path,
            "protocol_state_path": state_path,
            "records": records,
            "tests": tests,
            "protocol_snapshot": self.protocol.snapshot(),
            "start_dictionary_size": self.start_dictionary_size,
            "final_dictionary_size": len(self.protocol.current_token_map),
            "new_entries_created": self._new_entries_created(),
            "target_new_entries": self.debate_target_new_entries,
            "model": self.model,
            "temperature": self.temperature,
            "ollama_url": self.ollama_url,
            "strict_language_mode": self.strict_language_mode,
            "language_map_path": str(self.language_map_path) if self.strict_language_mode else "",
            "human_leak_penalty": self.human_leak_penalty,
            "language_map_entry_count": len(self.language_map_entries),
        }

    def _apply_agent_message(
        self,
        speaker: str,
        response: str,
        turn: int,
        category: str,
        context: str,
    ) -> dict[str, Any]:
        metrics = self.evaluator.evaluate(
            phase=self.phase_name,
            natural_phrase=f"debate category: {category}",
            architect_message=context,
            model_response=response,
            previous_compact=self.previous_compact,
            known_symbols=self.protocol.known_symbols(),
            current_token_map=self.protocol.current_token_map,
            deprecated_tokens=self.protocol.deprecated_tokens,
        )
        if self.strict_language_mode:
            metrics.update(self._strict_language_metrics(response))
        self.previous_compact = metrics.get("compact_phrase", self.previous_compact)
        change = self.protocol.update_from_round(
            round_index=self.message_index,
            phase=self.phase_name,
            architect_notes=context,
            model_response=response,
            metrics=metrics,
            model_event_source=speaker.lower(),
        )
        self.message_index += 1
        return {"metrics": metrics, "change": change}

    def _message_record(
        self,
        run_id: str,
        turn: int,
        speaker: str,
        response: str,
        update: dict[str, Any],
        category: str,
        result: CodexResult | OllamaResult,
        test_result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        decisions = debate_decisions(response)
        record = {
            "event": "debate_message",
            "run_id": run_id,
            "phase_id": self.phase_id,
            "phase": self.phase_name,
            "turn": turn,
            "speaker": speaker,
            "active_vocabulary_category": category,
            "compact_message": first_nonempty_line(response),
            "human_explanation_sentence": human_explanation_sentence(response),
            "response": response,
            "new_events": update["change"].get("lexicon_events", []),
            "evolve_events": update["change"].get("token_evolution_events", []),
            "tokens_accepted": decisions["accepted"],
            "tokens_rejected_or_challenged": decisions["challenged"],
            "debate_decision": decisions["summary"],
            "current_dictionary_size_after_turn": len(self.protocol.current_token_map),
            "metrics": update["metrics"],
            "sender_original_sentence": "",
            "sender_compact_sentence": "",
            "receiver_decoded_sentence": "",
            "reward_score": 0.0,
            "compression_ratio": 0.0,
            "decode_success": False,
        }
        if self.strict_language_mode:
            strict_metrics = strict_record_metrics(update["metrics"])
            record.update(strict_metrics)
        if isinstance(result, CodexResult):
            record.update(
                {
                    "codex_ok": result.ok,
                    "codex_output_path": str(result.output_path),
                    "codex_error": result.error,
                    "codex_command": result.command,
                }
            )
        else:
            record.update(
                {
                    "ollama_ok": result.ok,
                    "model_used": result.model,
                    "ollama_error": result.error,
                }
            )
        if test_result:
            record.update(
                {
                    "sender_original_sentence": test_result.get("sender_original_sentence", ""),
                    "sender_compact_sentence": test_result.get("sender_compact_sentence", ""),
                    "receiver_decoded_sentence": test_result.get("receiver_decoded_sentence", ""),
                    "reward_score": test_result.get("final_reward_score", 0.0),
                    "compression_ratio": test_result.get("compression_ratio", 0.0),
                    "decode_success": test_result.get("decode_success", False),
                }
            )
        return record

    def _run_sender_receiver_test(
        self,
        turn: int,
        strict_turn_penalty: float = 0.0,
    ) -> dict[str, Any]:
        original = TEST_SENTENCES[(turn - 1) % len(TEST_SENTENCES)]
        compact, matched_tokens = self._compress_sentence(original)
        decoded = self._decode_compact(compact)
        reward = (
            self.evaluator.score_sender_receiver(
                original=original,
                compact=compact,
                decoded=decoded,
                current_token_map=self.protocol.current_token_map,
            )
            if self.reward_mode
            else {}
        )
        if self.strict_language_mode and reward:
            base_reward = reward.get("final_reward_score", 0.0)
            reward["base_final_reward_score"] = base_reward
            reward["human_leak_penalty_total"] = round(strict_turn_penalty, 4)
            reward["final_reward_score"] = round(base_reward - strict_turn_penalty, 4)
            reward["strict_language_reward"] = reward["final_reward_score"]
        decode_success = reward.get("decode_success_score", 0.0) >= 0.5 if reward else bool(decoded)
        return {
            "event": "sender_receiver_test",
            "phase_id": self.phase_id,
            "phase": self.phase_name,
            "turn": turn,
            "sender_original_sentence": original,
            "sender_compact_sentence": compact,
            "receiver_decoded_sentence": decoded,
            "send_line": f'<SEND original="{escape_attr(original)}" compact="{escape_attr(compact)}">',
            "recv_line": f'<RECV compact="{escape_attr(compact)}" decoded="{escape_attr(decoded)}">',
            "matched_tokens": matched_tokens,
            "decode_success": decode_success,
            **reward,
        }

    def _compress_sentence(self, sentence: str) -> tuple[str, list[dict[str, str]]]:
        normalized = normalize_surface(sentence)
        candidates = self._token_candidates()
        parts: list[str] = []
        matched: list[dict[str, str]] = []
        position = 0
        while position < len(normalized):
            if normalized[position].isspace():
                position += 1
                continue
            best = None
            for candidate in candidates:
                phrase = candidate["phrase"]
                if not normalized.startswith(phrase, position):
                    continue
                end = position + len(phrase)
                if end < len(normalized) and not normalized[end].isspace():
                    continue
                best = candidate
                break
            if best:
                parts.append(best["token"])
                matched.append(
                    {
                        "phrase": best["phrase"],
                        "meaning": best["meaning"],
                        "token": best["token"],
                    }
                )
                position += len(best["phrase"])
                continue
            word_match = WORD_RE.match(normalized, position)
            if word_match:
                parts.append(word_match.group(0))
                position = word_match.end()
            else:
                position += 1
        return " ".join(parts) if parts else normalized, matched

    def _decode_compact(self, compact: str) -> str:
        reverse: dict[str, list[str]] = {}
        for meaning, token in self.protocol.current_token_map.items():
            reverse.setdefault(token, []).append(meaning)
        decoded_parts: list[str] = []
        for part in compact.split():
            meanings = reverse.get(part)
            if meanings:
                decoded_parts.append(meanings[0])
            else:
                decoded_parts.append(part)
        return " ".join(decoded_parts)

    def _token_candidates(self) -> list[dict[str, str]]:
        latest_events: dict[str, dict[str, Any]] = {}
        for event in self.protocol.lexicon_events:
            latest_events[event.get("meaning", "")] = event

        candidates: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for meaning, token in self.protocol.current_token_map.items():
            event = latest_events.get(meaning, {})
            phrases = meaning_variants(meaning)
            for key in ("ro", "en"):
                if event.get(key):
                    phrases.add(normalize_surface(str(event[key])))
            for phrase in phrases:
                if not phrase:
                    continue
                item = (phrase, token)
                if item in seen:
                    continue
                seen.add(item)
                candidates.append({"phrase": phrase, "token": token, "meaning": meaning})
        return sorted(candidates, key=lambda item: len(item["phrase"]), reverse=True)

    def _build_agent_prompt(
        self,
        speaker: str,
        other_agent: str,
        turn: int,
        category: str,
        vocabulary_batch: list[dict[str, str]],
        context: str,
        last_message: str,
    ) -> str:
        if self.strict_language_mode:
            return self._build_strict_language_prompt(
                speaker=speaker,
                other_agent=other_agent,
                turn=turn,
                category=category,
                vocabulary_batch=vocabulary_batch,
                context=context,
                last_message=last_message,
            )

        return f"""You are Agent {speaker} in MiniCPL-Ro Phase {self.phase_id}.
Your dialogue partner is {other_agent}. This is a language/protocol design debate only.
Do not run commands, edit files, browse, request external actions, or control the operating system.
Return only your debate message.

Main objective: create a very token-efficient machine-oriented language/protocol for Romanian/English concepts.
Current turn: {turn}
Active vocabulary category: {category}
Target new dictionary entries remaining: {max(0, self.debate_target_new_entries - self._new_entries_created())}

Required debate behavior:
- Put a compact-language message first.
- Debate one category at a time; this turn focuses on {category}.
- Create compact tokens with <NEW meaning = token>.
- Improve tokens with <EVOLVE old_token -> new_token reason>.
- Prefer one-character tokens for very common meanings, two-character tokens for common meanings, and three-character tokens only when needed.
- Challenge inefficient, duplicate, or too-readable tokens when you find better ones.
- Agree when a token is already efficient enough.
- Use normal Romanian/English mainly inside <NEW ... = ...> declarations or one short reason sentence.
- After a token exists, prefer using it instead of the normal word.
- Include at least 6 useful <NEW> or <EVOLVE> events when possible.
- Suggested sender/receiver syntax when useful: <SEND original="..." compact="..."> and <RECV compact="..." decoded="...">.

Vocabulary batch for this category:
{format_vocabulary_batch(vocabulary_batch)}

Compact context:
{context}

Previous message from {other_agent}:
{excerpt(last_message, 1800) if last_message else "No previous message for this turn."}
"""

    def _build_strict_language_prompt(
        self,
        speaker: str,
        other_agent: str,
        turn: int,
        category: str,
        vocabulary_batch: list[dict[str, str]],
        context: str,
        last_message: str,
    ) -> str:
        return f"""You are Agent {speaker} in MiniCPL-Ro Phase {self.phase_id} strict compact-language mode.
Your dialogue partner is {other_agent}. This is a language/protocol design debate only.
Do not run commands, edit files, browse, request external actions, or control the operating system.
Return only your debate message.

STRICT LANGUAGE MODE IS ACTIVE.
Required language base: {self.language_map_path}
Human leak penalty: -{self.human_leak_penalty} per leaked human word.

Hard rules:
- Put a compact-language message first.
- Compact messages must primarily use compact_token values from the 4000-entry language map.
- Separate compact tokens with spaces so the observer can score token use.
- Do not write normal English or Romanian in compact messages.
- Human language is allowed only inside original/source sentence fields, receiver decoded output fields, <NEW human_meaning = compact_token>, and <EVOLVE old_token -> new_token reason>.
- If a needed meaning is missing, create it with <NEW human_meaning = compact_token>.
- If a token is inefficient, evolve it with <EVOLVE old_token -> new_token reason>.
- Phrase macros are allowed with <NEW human_phrase = compact_token>, then use the compact token afterward.
- Keep decode ability: use <SEND original="..." compact="..."> and <RECV compact="..." decoded="..."> only when useful.
- Outside allowed event fields, avoid prose. Prefer compact tokens only.

Active category: {category}
Turn: {turn}
Target new dictionary entries remaining: {max(0, self.debate_target_new_entries - self._new_entries_created())}

Core language-map tokens:
{self._strict_core_token_lines(limit=80)}

Focused language-map tokens for this turn:
{format_vocabulary_batch(vocabulary_batch)}

Compact context:
{context}

Previous message from {other_agent}:
{excerpt(last_message, 1800) if last_message else "No previous message for this turn."}
"""

    def _build_context(
        self,
        turn: int,
        category: str,
        vocabulary_batch: list[dict[str, str]],
        last_message: str,
        last_test: dict[str, Any] | None,
    ) -> str:
        recent_changes = self.protocol.change_log[-4:]
        recent_events: list[str] = []
        for change in recent_changes:
            for event in change.get("lexicon_events", [])[-4:]:
                recent_events.append(event.get("raw", ""))
            for event in change.get("token_evolution_events", [])[-4:]:
                recent_events.append(event.get("raw", ""))
        return "\n".join(
            [
                f"phase_id={self.phase_id}",
                f"phase={self.phase_name}",
                f"turn={turn}",
                f"target_new_entries={self.debate_target_new_entries}",
                f"new_entries_created={self._new_entries_created()}",
                f"current_dictionary_size={len(self.protocol.current_token_map)}",
                f"start_dictionary_size={self.start_dictionary_size}",
                f"active_vocabulary_category={category}",
                f"strict_language_mode={self.strict_language_mode}",
                f"language_map_path={self.language_map_path if self.strict_language_mode else ''}",
                f"human_leak_penalty={self.human_leak_penalty if self.strict_language_mode else 0}",
                f"token_map_summary={self._token_map_summary(limit=80)}",
                f"vocabulary_batch={json.dumps(vocabulary_batch, ensure_ascii=False)}",
                f"strict_language_batch={self._strict_batch_summary(vocabulary_batch) if self.strict_language_mode else ''}",
                f"recent_new_or_evolve_events={json.dumps(recent_events[-20:], ensure_ascii=False)}",
                f"last_sender_receiver_test={json.dumps(last_test or {}, ensure_ascii=False)}",
                f"last_message_excerpt={excerpt(last_message, 1200)}",
            ]
        )

    def _token_map_summary(self, limit: int) -> str:
        items = list(self.protocol.current_token_map.items())
        if not items:
            return "empty"
        shown = [f"{meaning}={token}" for meaning, token in items[-limit:]]
        suffix = f"; ... {len(items) - limit} older entries omitted" if len(items) > limit else ""
        return "; ".join(shown) + suffix

    def _vocabulary_batch(self, category: str, limit: int) -> list[dict[str, str]]:
        if self.strict_language_mode:
            return self._strict_language_batch(category, limit)

        normalized_category = category.lower()
        if normalized_category == "phrase macros":
            return self._phrase_macro_batch(limit)
        if normalized_category == "grammar/compression markers":
            return [
                {
                    "category": category,
                    "ro": "marker",
                    "en": label,
                    "concept_id": f"grammar_{index:03d}",
                }
                for index, label in enumerate(
                    [
                        "subject marker",
                        "object marker",
                        "want relation",
                        "need relation",
                        "question marker",
                        "past marker",
                        "future marker",
                        "negation marker",
                        "plural marker",
                        "decode marker",
                    ],
                    start=1,
                )
            ][:limit]

        rows = [
            row
            for row in self.vocabulary
            if row.get("category", "").lower() == normalized_category
        ]
        if not rows and normalized_category == "software/project terms":
            rows = [
                row
                for row in self.vocabulary
                if row.get("category", "").lower() in {"software/project terms", "software"}
            ]
        if not rows:
            rows = self.vocabulary
        untokenized = [
            row
            for row in rows
            if f"{row.get('ro', '')} / {row.get('en', '')}" not in self.protocol.current_token_map
        ]
        selected = (untokenized or rows)[:limit]
        used = set(self.protocol.current_token_map.values())
        enriched: list[dict[str, str]] = []
        for row in selected:
            item = dict(row)
            item["suggested_token"] = unique_token(token_candidate(item), used)
            used.add(item["suggested_token"])
            enriched.append(item)
        return enriched

    def _strict_language_batch(self, category: str, limit: int) -> list[dict[str, str]]:
        normalized_category = category.lower()
        if normalized_category == "phrase macros":
            normalized_category = "common_phrases"
        rows = self.language_entries_by_category.get(normalized_category, [])
        if not rows:
            rows = self.language_map_entries
        selected = rows[:limit]
        return [
            {
                "category": entry.category,
                "ro": entry.ro,
                "en": entry.en,
                "concept_id": entry.id,
                "meaning": entry.meaning,
                "compact_token": entry.compact_token,
                "source_rank": str(entry.source_rank),
            }
            for entry in selected
        ]

    def _phrase_macro_batch(self, limit: int) -> list[dict[str, str]]:
        rows = []
        for task in self.tasks[:limit]:
            rows.append(
                {
                    "category": "phrase macros",
                    "ro": task.get("phrase", ""),
                    "en": task.get("intent", ""),
                    "concept_id": task.get("id", ""),
                    "suggested_token": task.get("intent", "x")[:3].lower(),
                }
            )
        return rows

    def _strict_core_token_lines(self, limit: int) -> str:
        if not self.language_map_entries:
            return "No language-map entries loaded."
        lines = []
        for entry in self.language_map_entries[:limit]:
            lines.append(
                f'- {entry.source_rank} | {entry.category} | "{entry.ro} / {entry.en}" = {entry.compact_token}'
            )
        return "\n".join(lines)

    def _strict_batch_summary(self, batch: list[dict[str, str]]) -> str:
        if not batch:
            return "No focused strict language batch."
        return "; ".join(
            f"{item.get('meaning', '')}={item.get('compact_token', '')}"
            for item in batch[:40]
        )

    def _resolve_language_map_path(self, path: Path | None) -> Path:
        if path is None:
            return self.root / "results" / "language_map_4000.csv"
        return path if path.is_absolute() else self.root / path

    def _language_entries_by_category(self) -> dict[str, list[LanguageMapEntry]]:
        grouped: dict[str, list[LanguageMapEntry]] = {}
        for entry in self.language_map_entries:
            grouped.setdefault(entry.category.lower(), []).append(entry)
        return grouped

    def _strict_language_protocol(self) -> ProtocolState:
        protocol = ProtocolState()
        protocol.configure_vocabulary(self.vocabulary)
        for entry in self.language_map_entries:
            event = {
                "meaning": entry.meaning,
                "token": entry.compact_token,
                "raw": f'<NEW "{entry.meaning}" = {entry.compact_token}>',
                "source": "language_map_4000",
                "category": entry.category,
                "concept_id": entry.id,
                "ro": entry.ro,
                "en": entry.en,
                "round": 0,
                "phase": self.phase_name,
            }
            protocol.lexicon_events.append(event)
            protocol.current_token_map[entry.meaning] = entry.compact_token
            protocol.symbol_table[f"lm_{entry.source_rank}"] = entry.compact_token
        protocol.version = 1
        return protocol

    def _strict_language_metrics(self, response: str) -> dict[str, Any]:
        strict_text = strict_scored_text(response)
        allowed_tokens = (
            self.language_token_set
            | set(self.protocol.current_token_map.values())
            | strict_declared_tokens(response)
        )
        atoms = strict_atoms(strict_text)
        known_atoms = [atom for atom in atoms if atom in allowed_tokens]
        unknown_atoms = [atom for atom in atoms if atom not in allowed_tokens]
        leaked_words = [
            word
            for word in HUMAN_WORD_RE.findall(strict_text)
            if word not in allowed_tokens
        ]
        total_atoms = len(known_atoms) + len(unknown_atoms)
        usage_rate = round(len(known_atoms) / total_atoms, 4) if total_atoms else 0.0
        leak_penalty_total = len(leaked_words) * self.human_leak_penalty
        leakage_factor = max(0.0, 1.0 - (len(leaked_words) / max(1, total_atoms)))
        compliance = round(usage_rate * leakage_factor, 4)
        return {
            "human_words_leaked_count": len(leaked_words),
            "human_words_leaked": leaked_words[:50],
            "human_leak_penalty_total": leak_penalty_total,
            "dictionary_token_usage_rate": usage_rate,
            "dictionary_tokens_used_count": len(known_atoms),
            "unknown_token_count": len(unknown_atoms),
            "unknown_tokens": unknown_atoms[:50],
            "strict_language_compliance_score": compliance,
            "strict_language_reward": -leak_penalty_total,
        }

    def _load_latest_protocol_state(self) -> ProtocolState:
        protocol = ProtocolState()
        protocol.configure_vocabulary(self.vocabulary)
        states = sorted(
            (self.root / "results").glob("protocol_state_*.json"),
            key=lambda path: path.stat().st_mtime,
        )
        if not states:
            return protocol
        latest = states[-1]
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return protocol
        for key, value in data.items():
            if key.startswith("_"):
                continue
            if hasattr(protocol, key):
                setattr(protocol, key, value)
        protocol.configure_vocabulary(data.get("source_vocabulary") or self.vocabulary)
        return protocol

    def _load_vocabulary(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def _load_tasks(self, path: Path) -> list[dict[str, Any]]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _target_reached(self) -> bool:
        return (
            self.debate_target_new_entries > 0
            and self._new_entries_created() >= self.debate_target_new_entries
        )

    def _new_entries_created(self) -> int:
        return max(0, len(self.protocol.current_token_map) - self.start_dictionary_size)

    def _write_jsonl(self, handle: Any, event: dict[str, Any]) -> None:
        payload = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        handle.flush()

    def _markdown_header(self, run_id: str) -> str:
        title = (
            f"# Phase {self.phase_id} Strict Language"
            if self.strict_language_mode
            else f"# Phase {self.phase_id} Debate"
        )
        return "\n".join(
            [
                title,
                "",
                f"- Run ID: `{run_id}`",
                f"- Phase: `{self.phase_name}`",
                f"- Model: `{self.model}`",
                f"- Target new entries: `{self.debate_target_new_entries}`",
                f"- Starting dictionary size: `{self.start_dictionary_size}`",
                f"- Strict language mode: `{self.strict_language_mode}`",
                f"- Language map: `{self.language_map_path if self.strict_language_mode else ''}`",
                f"- Human leak penalty: `{self.human_leak_penalty if self.strict_language_mode else 0}`",
                "",
            ]
        )

    def _append_markdown_turn(
        self,
        md_path: Path,
        turn: int,
        category: str,
        codex_record: dict[str, Any],
        qwen_record: dict[str, Any],
        test_result: dict[str, Any] | None,
    ) -> None:
        lines = [
            f"## Turn {turn}: {category}",
            "",
            "### Codex",
            f"Compact: `{escape_backticks(codex_record.get('compact_message', ''))}`",
            "",
            "```text",
            codex_record.get("response", ""),
            "```",
            f"NEW events: `{len(codex_record.get('new_events', []))}`",
            f"EVOLVE events: `{len(codex_record.get('evolve_events', []))}`",
            f"Decision: {codex_record.get('debate_decision', '')}",
            strict_markdown_metrics(codex_record),
            "",
            "### Qwen",
            f"Compact: `{escape_backticks(qwen_record.get('compact_message', ''))}`",
            "",
            "```text",
            qwen_record.get("response", ""),
            "```",
            f"NEW events: `{len(qwen_record.get('new_events', []))}`",
            f"EVOLVE events: `{len(qwen_record.get('evolve_events', []))}`",
            f"Decision: {qwen_record.get('debate_decision', '')}",
            strict_markdown_metrics(qwen_record),
            "",
            f"Dictionary size after turn: `{qwen_record.get('current_dictionary_size_after_turn', 0)}`",
            "",
        ]
        if test_result:
            lines.extend(
                [
                    "### Sender/Receiver Test",
                    f"- Sender original: `{test_result.get('sender_original_sentence', '')}`",
                    f"- Sender compact: `{test_result.get('sender_compact_sentence', '')}`",
                    f"- Receiver decoded: `{test_result.get('receiver_decoded_sentence', '')}`",
                    f"- Compression ratio: `{test_result.get('compression_ratio', 0.0)}`",
                    f"- Decode success: `{test_result.get('decode_success')}`",
                    f"- Base reward score: `{test_result.get('base_final_reward_score', test_result.get('final_reward_score', 0.0))}`",
                    f"- Human leak penalty total: `{test_result.get('human_leak_penalty_total', 0.0)}`",
                    f"- Reward score: `{test_result.get('final_reward_score', 0.0)}`",
                    "",
                ]
            )
        with md_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


def normalize_surface(value: str) -> str:
    lowered = value.strip().lower()
    cleaned = re.sub(r"[^\wăâîșțĂÂÎȘȚ]+", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


def meaning_variants(meaning: str) -> set[str]:
    variants = {normalize_surface(meaning)}
    for part in re.split(r"[/|,;]", meaning):
        normalized = normalize_surface(part)
        if normalized:
            variants.add(normalized)
            if normalized.startswith("to "):
                variants.add(normalized[3:])
            if normalized.startswith("a "):
                variants.add(normalized[2:])
    return {variant for variant in variants if variant}


def format_vocabulary_batch(batch: list[dict[str, str]]) -> str:
    if not batch:
        return "No focused vocabulary batch available."
    lines = []
    for item in batch:
        suggested = item.get("suggested_token", "")
        compact = item.get("compact_token", "")
        suffix_parts = []
        if suggested:
            suffix_parts.append(f"suggested={suggested}")
        if compact:
            suffix_parts.append(f"compact_token={compact}")
        suffix = f" {' '.join(suffix_parts)}" if suffix_parts else ""
        lines.append(
            f'- {item.get("category", "")} | {item.get("concept_id", "")} | '
            f'"{item.get("ro", "")} / {item.get("en", "")}"{suffix}'
        )
    return "\n".join(lines)


def strict_scored_text(text: str) -> str:
    compact_parts = COMPACT_ATTR_RE.findall(text)
    cleaned = SEND_OR_RECV_RE.sub(" ", text)
    cleaned = NEW_OR_EVOLVE_RE.sub(" ", cleaned)
    return " ".join(compact_parts + [cleaned])


def strict_declared_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for tag in NEW_OR_EVOLVE_RE.findall(text):
        new_match = re.search(r"=\s*([^\s>]+)", tag)
        if new_match:
            tokens.add(new_match.group(1).strip())
        evolve_match = re.search(r"->\s*([^\s>]+)", tag)
        if evolve_match:
            tokens.add(evolve_match.group(1).strip())
    return tokens


def strict_atoms(text: str) -> list[str]:
    atoms: list[str] = []
    for raw in re.split(r"\s+", text.strip()):
        atom = raw.strip().strip("`\"'()[]{}")
        if not atom:
            continue
        if atom in {"|", "->", "=", ":", ";", ",", ".", "-"}:
            continue
        atoms.append(atom)
    return atoms


def strict_record_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    list_keys = {"human_words_leaked", "unknown_tokens"}
    keys = (
        "human_words_leaked_count",
        "human_words_leaked",
        "human_leak_penalty_total",
        "dictionary_token_usage_rate",
        "dictionary_tokens_used_count",
        "unknown_token_count",
        "unknown_tokens",
        "strict_language_compliance_score",
        "strict_language_reward",
    )
    return {key: metrics.get(key, [] if key in list_keys else 0) for key in keys}


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:500]
    return ""


def human_explanation_sentence(text: str) -> str:
    for line in text.splitlines()[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("<NEW") or stripped.startswith("<EVOLVE"):
            continue
        words = stripped.split()
        if len(words) >= 6:
            return stripped[:300]
    return ""


def debate_decisions(text: str) -> dict[str, Any]:
    accepted: list[str] = []
    challenged: list[str] = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(word in lowered for word in ("agree", "accept", "keep", "ok")):
            accepted.append(line.strip()[:240])
        if any(word in lowered for word in ("challenge", "reject", "disagree", "inefficient", "too long")):
            challenged.append(line.strip()[:240])
    if challenged and accepted:
        summary = "mixed agreement and challenge"
    elif challenged:
        summary = "challenge"
    elif accepted:
        summary = "agreement"
    else:
        summary = "implicit proposal"
    return {"accepted": accepted[:8], "challenged": challenged[:8], "summary": summary}


def escape_attr(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;")


def escape_backticks(value: str) -> str:
    return value.replace("`", "'")


def strict_markdown_metrics(record: dict[str, Any]) -> str:
    if "human_words_leaked_count" not in record:
        return ""
    return "\n".join(
        [
            f"Human leaks: `{record.get('human_words_leaked_count', 0)}`",
            f"Leak penalty: `{record.get('human_leak_penalty_total', 0)}`",
            f"Dictionary token usage: `{record.get('dictionary_token_usage_rate', 0.0)}`",
            f"Unknown tokens: `{record.get('unknown_token_count', 0)}`",
            f"Strict compliance: `{record.get('strict_language_compliance_score', 0.0)}`",
        ]
    )


def excerpt(text: str, limit: int = 500) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."
