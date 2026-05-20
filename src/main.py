"""CLI entry point for MiniCPL-Ro Agent Lab."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from agent_arena import AgentArena
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
    transcripts = sorted((root / "logs").glob("transcript_*.jsonl"))
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


def show_latest_report(root: Path) -> int:
    report = root / "results" / "final_report.md"
    if not report.exists():
        print("No results/final_report.md found.")
        return 1
    print(report.read_text(encoding="utf-8"), end="")
    return 0


def export_dictionary(root: Path) -> int:
    states = sorted((root / "results").glob("protocol_state_*.json"))
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
