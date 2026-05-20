"""CLI entry point for MiniCPL-Ro Agent Lab."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from agent_arena import AgentArena
from dictionary_2000 import (
    generate_dictionary_2000,
    generate_dictionary_4000,
    validate_dictionary_2000,
    validate_dictionary_4000,
    validation_report,
)
from dual_agent_arena import DualAgentArena
from language_map import (
    generate_language_map_4000,
    language_map_validation_report,
    validate_language_map_4000,
)
from report_generator import ReportGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the MiniCPL-Ro agent arena.")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--bootstrap-rounds", type=int, default=5)
    parser.add_argument("--lexicon-rounds", type=int, default=0)
    parser.add_argument("--model", default="qwen3.6:35b-a3b")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--replay-latest", action="store_true")
    parser.add_argument("--show-latest-report", action="store_true")
    parser.add_argument("--export-dictionary", action="store_true")
    parser.add_argument("--dual-agent", action="store_true")
    parser.add_argument("--debate-mode", action="store_true")
    parser.add_argument("--debate-turns-per-agent", type=int, default=10)
    parser.add_argument("--debate-target-new-entries", type=int, default=200)
    parser.add_argument("--phase-id", type=int, default=5)
    parser.add_argument("--receiver-test", action="store_true")
    parser.add_argument("--reward-mode", action="store_true")
    parser.add_argument("--strict-language-mode", action="store_true")
    parser.add_argument("--language-map", type=Path)
    parser.add_argument("--human-leak-penalty", type=int, default=100)
    parser.add_argument("--strict-retry-on-leak", action="store_true")
    parser.add_argument("--strict-max-retries", type=int, default=0)
    parser.add_argument("--show-phase", type=int)
    parser.add_argument("--show-rewards", action="store_true")
    parser.add_argument("--show-strict-language-report", action="store_true")
    parser.add_argument("--show-latest-qwen-prompt", action="store_true")
    parser.add_argument("--generate-dictionary-2000", action="store_true")
    parser.add_argument("--validate-dictionary-2000", action="store_true")
    parser.add_argument("--generate-dictionary-4000", action="store_true")
    parser.add_argument("--validate-dictionary-4000", action="store_true")
    parser.add_argument("--generate-language-map-4000", action="store_true")
    parser.add_argument("--validate-language-map-4000", action="store_true")
    parser.add_argument("--show-language-map-4000", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.replay_latest:
        return replay_latest(root)
    if args.show_latest_report:
        return show_latest_report(root)
    if args.export_dictionary:
        return export_dictionary(root)
    if args.show_phase is not None:
        return show_phase(root, args.show_phase)
    if args.show_rewards:
        return show_rewards(root)
    if args.show_strict_language_report:
        return show_strict_language_report(root)
    if args.show_latest_qwen_prompt:
        return show_latest_qwen_prompt(root)
    if args.generate_dictionary_2000:
        return generate_dictionary_2000_command(root)
    if args.validate_dictionary_2000:
        return validate_dictionary_2000_command(root)
    if args.generate_dictionary_4000:
        return generate_dictionary_4000_command(root)
    if args.validate_dictionary_4000:
        return validate_dictionary_4000_command(root)
    if args.generate_language_map_4000:
        return generate_language_map_4000_command(root)
    if args.validate_language_map_4000:
        return validate_language_map_4000_command(root)
    if args.show_language_map_4000:
        return show_language_map_4000(root)

    if args.dual_agent:
        if not args.debate_mode:
            print("--dual-agent currently requires --debate-mode.")
            return 1
        arena = DualAgentArena(
            model=args.model,
            temperature=args.temperature,
            phase_id=args.phase_id,
            debate_turns_per_agent=args.debate_turns_per_agent,
            debate_target_new_entries=args.debate_target_new_entries,
            receiver_test=args.receiver_test,
            reward_mode=args.reward_mode,
            ollama_url=args.ollama_url,
            root=root,
            strict_language_mode=args.strict_language_mode,
            language_map_path=args.language_map,
            human_leak_penalty=args.human_leak_penalty,
            strict_retry_on_leak=args.strict_retry_on_leak,
            strict_max_retries=args.strict_max_retries,
        )
        result = arena.run()
        reporter = ReportGenerator()
        if args.strict_language_mode:
            reporter.write_strict_language_report(result["markdown_path"], debate_result=result)
            reporter.write_strict_language_report(
                root / "results" / "final_report.md",
                debate_result=result,
            )
        else:
            reporter.write_debate_report(
                root / "results" / "final_report.md",
                debate_result=result,
            )
        print(f"Run ID: {result['run_id']}")
        print(f"Phase debate JSONL: {result['jsonl_path']}")
        print(f"Phase debate Markdown: {result['markdown_path']}")
        print(f"Protocol state: {result['protocol_state_path']}")
        print(f"Final report: {root / 'results' / 'final_report.md'}")
        return 0

    arena = AgentArena(
        model=args.model,
        temperature=args.temperature,
        rounds=args.rounds,
        bootstrap_rounds=args.bootstrap_rounds,
        lexicon_rounds=args.lexicon_rounds,
        ollama_url=args.ollama_url,
        root=root,
    )
    result = arena.run()

    config = {
        "model": args.model,
        "rounds": args.rounds,
        "bootstrap_rounds": args.bootstrap_rounds,
        "lexicon_rounds": args.lexicon_rounds,
        "temperature": args.temperature,
        "ollama_url": args.ollama_url,
        "transcript_path": str(result["transcript_path"]),
    }
    ReportGenerator().write_final_report(
        root / "results" / "final_report.md",
        config=config,
        rounds=result["rounds"],
        protocol_snapshot=result["protocol_snapshot"],
    )

    print(f"Run ID: {result['run_id']}")
    print(f"Transcript: {result['transcript_path']}")
    print(f"Protocol state: {result['protocol_state_path']}")
    print(f"Final report: {root / 'results' / 'final_report.md'}")
    return 0


def replay_latest(root: Path) -> int:
    debate = latest_debate_jsonl(root)
    transcripts = sorted((root / "logs").glob("transcript_*.jsonl"), key=lambda path: path.stat().st_mtime)
    if debate and (not transcripts or debate.stat().st_mtime >= transcripts[-1].stat().st_mtime):
        return replay_debate(debate)

    if not transcripts:
        print("No transcript files found in logs/.")
        return 1

    latest = transcripts[-1]
    print(f"Replay: {latest}")
    with latest.open("r", encoding="utf-8") as handle:
        for line in handle:
            event = json.loads(line)
            if event.get("event") != "round_completed":
                continue
            metrics = event.get("metrics", {})
            task = event.get("task", {})
            lexicon_batch = event.get("lexicon_batch", [])
            print("")
            print(f"Round: {event.get('round')}")
            print(f"Phase: {event.get('phase', metrics.get('phase', 'unknown'))}")
            print(f"Natural task: {task.get('phrase', '')}")
            if lexicon_batch:
                print(f"Lexicon batch: {format_lexicon_batch(lexicon_batch)}")
            print(f"Agent A: {excerpt(event.get('agent_a_message', ''))}")
            print(f"Agent B: {excerpt(event.get('agent_b_response', ''))}")
            print(f"Compact: {metrics.get('compact_phrase', '')}")
            print(f"NEW token events: {json.dumps(metrics.get('new_token_events', []), ensure_ascii=False)}")
            print(f"EVOLVE token events: {json.dumps(metrics.get('token_evolution_events', []), ensure_ascii=False)}")
            print(f"Compact continuity score: {metrics.get('compact_protocol_continuity_score', 0.0)}")
            print(f"Deprecated token reuse: {json.dumps(metrics.get('deprecated_tokens_reused', []), ensure_ascii=False)}")
            print(f"Metrics: {json.dumps(metrics, ensure_ascii=False, sort_keys=True)}")
    return 0


def replay_debate(path: Path) -> int:
    print(f"Replay debate: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            event = json.loads(line)
            event_type = event.get("event")
            if event_type == "debate_message":
                print("")
                print(f"Turn: {event.get('turn')}")
                print(f"Phase: {event.get('phase')}")
                print(f"Speaker: {event.get('speaker')}")
                print(f"Category: {event.get('active_vocabulary_category')}")
                print(f"Message: {excerpt(event.get('response', ''), limit=500)}")
                print(f"NEW token events: {json.dumps(event.get('new_events', []), ensure_ascii=False)}")
                print(f"EVOLVE token events: {json.dumps(event.get('evolve_events', []), ensure_ascii=False)}")
                print(f"Debate decision: {event.get('debate_decision', '')}")
                print(f"Dictionary size: {event.get('current_dictionary_size_after_turn', 0)}")
                print(f"Reward score: {event.get('reward_score', 0.0)}")
            elif event_type == "sender_receiver_test":
                print("")
                print(f"Sender original: {event.get('sender_original_sentence', '')}")
                print(f"Compact encoded: {event.get('sender_compact_sentence', '')}")
                print(f"Receiver decoded: {event.get('receiver_decoded_sentence', '')}")
                print(f"Compression ratio: {event.get('compression_ratio', 0.0)}")
                print(f"Decode success: {event.get('decode_success')}")
                print(f"Reward score: {event.get('final_reward_score', 0.0)}")
    return 0


def show_latest_report(root: Path) -> int:
    report = root / "results" / "final_report.md"
    if not report.exists():
        print("No results/final_report.md found.")
        return 1
    print(report.read_text(encoding="utf-8"), end="")
    return 0


def export_dictionary(root: Path) -> int:
    states = sorted((root / "results").glob("protocol_state_*.json"), key=lambda path: path.stat().st_mtime)
    if not states:
        print("No protocol state files found in results/.")
        return 1

    latest = states[-1]
    state = json.loads(latest.read_text(encoding="utf-8"))
    rows = dictionary_rows(state)
    output_dir = root / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "dictionary_latest.csv"
    md_path = output_dir / "dictionary_latest.md"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["meaning", "token", "round", "phase", "category"])
        writer.writeheader()
        writer.writerows(rows)

    md_path.write_text(dictionary_markdown(rows, latest), encoding="utf-8")
    print(f"Dictionary CSV: {csv_path}")
    print(f"Dictionary Markdown: {md_path}")
    print(f"Entries: {len(rows)}")
    return 0


def show_phase(root: Path, phase_id: int) -> int:
    paths = sorted(
        list((root / "results").glob(f"phase{phase_id}_debate_*.md"))
        + list((root / "results").glob(f"phase{phase_id}_strict_language_*.md")),
        key=lambda path: path.stat().st_mtime,
    )
    if not paths:
        print(f"No phase {phase_id} markdown files found.")
        return 1
    print(paths[-1].read_text(encoding="utf-8"), end="")
    return 0


def show_strict_language_report(root: Path) -> int:
    paths = sorted(
        (root / "results").glob("phase*_strict_language_*.md"),
        key=lambda path: path.stat().st_mtime,
    )
    if not paths:
        print("No strict language markdown files found.")
        return 1
    print(paths[-1].read_text(encoding="utf-8"), end="")
    return 0


def show_latest_qwen_prompt(root: Path) -> int:
    prompt_root = root / "results" / "qwen_prompts"
    paths = sorted(prompt_root.glob("*/*.txt"), key=lambda path: path.stat().st_mtime)
    if not paths:
        print("No saved Qwen prompts found in results/qwen_prompts/.")
        return 1
    latest = paths[-1]
    print(f"Qwen prompt: {latest}")
    print("")
    print(latest.read_text(encoding="utf-8"), end="")
    return 0


def show_rewards(root: Path) -> int:
    path = latest_debate_jsonl(root)
    if not path:
        print("No phase debate JSONL files found.")
        return 1
    print(f"Rewards: {path}")
    found = False
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            event = json.loads(line)
            if event.get("event") != "sender_receiver_test":
                continue
            found = True
            print(
                "Turn {turn}: reward={reward} ratio={ratio} decode={decode} compact={compact}".format(
                    turn=event.get("turn"),
                    reward=event.get("final_reward_score", 0.0),
                    ratio=event.get("compression_ratio", 0.0),
                    decode=event.get("decode_success_score", 0.0),
                    compact=event.get("sender_compact_sentence", ""),
                )
            )
    if not found:
        print("No sender/receiver reward records found.")
        return 1
    return 0


def latest_debate_jsonl(root: Path) -> Path | None:
    paths = sorted(
        list((root / "results").glob("phase*_debate_*.jsonl"))
        + list((root / "results").glob("phase*_strict_language_*.jsonl")),
        key=lambda path: path.stat().st_mtime,
    )
    return paths[-1] if paths else None


def generate_dictionary_2000_command(root: Path) -> int:
    result = generate_dictionary_2000(root)
    validation = result["validation"]
    print(f"Source data: {result['source_path']}")
    print(f"Dictionary CSV: {result['csv_path']}")
    print(f"Dictionary JSON: {result['json_path']}")
    print(f"Dictionary Markdown: {result['markdown_path']}")
    print("")
    print(validation_report(validation))
    return 0 if validation["valid"] else 1


def validate_dictionary_2000_command(root: Path) -> int:
    try:
        validation = validate_dictionary_2000(root)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1
    print(validation_report(validation))
    return 0 if validation["valid"] else 1


def generate_dictionary_4000_command(root: Path) -> int:
    result = generate_dictionary_4000(root)
    validation = result["validation"]
    print(f"Source data: {result['source_path']}")
    print(f"Dictionary CSV: {result['csv_path']}")
    print(f"Dictionary JSON: {result['json_path']}")
    print(f"Dictionary Markdown: {result['markdown_path']}")
    print("")
    print(validation_report(validation))
    return 0 if validation["valid"] else 1


def validate_dictionary_4000_command(root: Path) -> int:
    try:
        validation = validate_dictionary_4000(root)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1
    print(validation_report(validation))
    return 0 if validation["valid"] else 1


def generate_language_map_4000_command(root: Path) -> int:
    result = generate_language_map_4000(root)
    validation = result["validation"]
    print(f"Source data: {result['source_path']}")
    print(f"Language map CSV: {result['csv_path']}")
    print(f"Language map JSON: {result['json_path']}")
    print(f"Language map Markdown: {result['markdown_path']}")
    print("")
    print(language_map_validation_report(validation))
    return 0 if validation["valid"] else 1


def validate_language_map_4000_command(root: Path) -> int:
    try:
        validation = validate_language_map_4000(root)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1
    print(language_map_validation_report(validation))
    return 0 if validation["valid"] else 1


def show_language_map_4000(root: Path) -> int:
    try:
        validation = validate_language_map_4000(root)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    path = root / "results" / "language_map_4000.md"
    if not path.exists():
        print(f"{path} does not exist. Run --generate-language-map-4000 first.")
        return 1

    print(language_map_validation_report(validation))
    print("")
    print(path.read_text(encoding="utf-8"), end="")
    return 0 if validation["valid"] else 1


def dictionary_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    latest_by_meaning: dict[str, dict[str, Any]] = {}
    current_token_map = state.get("current_token_map", {})
    for event in state.get("lexicon_events", []):
        meaning = event.get("meaning", "")
        if not meaning:
            continue
        latest_by_meaning[meaning] = {
            "meaning": meaning,
            "token": current_token_map.get(meaning, event.get("token", "")),
            "round": event.get("round", ""),
            "phase": event.get("phase", ""),
            "category": event.get("category", "") or "unmatched",
        }
    return sorted(
        latest_by_meaning.values(),
        key=lambda row: (row["category"], str(row["meaning"])),
    )


def dictionary_markdown(rows: list[dict[str, Any]], source_path: Path) -> str:
    lines = [
        "# MiniCPL-Ro Dictionary Export",
        "",
        f"Source state: `{source_path}`",
        f"Entries: `{len(rows)}`",
        "",
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["category"], []).append(row)
    for category in sorted(grouped):
        lines.extend([f"## {category}", "", "| Meaning | Token | Round | Phase |", "|---|---:|---:|---|"])
        for row in grouped[category]:
            lines.append(
                f"| {row['meaning']} | `{row['token']}` | {row['round']} | {row['phase']} |"
            )
        lines.append("")
    return "\n".join(lines)


def format_lexicon_batch(batch: list[dict[str, Any]], limit: int = 20) -> str:
    items = [
        f"{item.get('category', '')}:{item.get('ro', '')}/{item.get('en', '')}"
        for item in batch[:limit]
    ]
    suffix = " ..." if len(batch) > limit else ""
    return "; ".join(items) + suffix


def excerpt(text: str, limit: int = 280) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
