"""CLI entry point for MiniCPL-Ro Agent Lab."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_arena import AgentArena
from report_generator import ReportGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the MiniCPL-Ro agent arena.")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--bootstrap-rounds", type=int, default=5)
    parser.add_argument("--model", default="qwen3.6:35b-a3b")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--replay-latest", action="store_true")
    parser.add_argument("--show-latest-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.replay_latest:
        return replay_latest(root)
    if args.show_latest_report:
        return show_latest_report(root)

    arena = AgentArena(
        model=args.model,
        temperature=args.temperature,
        rounds=args.rounds,
        bootstrap_rounds=args.bootstrap_rounds,
        ollama_url=args.ollama_url,
        root=root,
    )
    result = arena.run()

    config = {
        "model": args.model,
        "rounds": args.rounds,
        "bootstrap_rounds": args.bootstrap_rounds,
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
            print("")
            print(f"Round: {event.get('round')}")
            print(f"Phase: {event.get('phase', metrics.get('phase', 'unknown'))}")
            print(f"Natural task: {task.get('phrase', '')}")
            print(f"Agent A: {excerpt(event.get('agent_a_message', ''))}")
            print(f"Agent B: {excerpt(event.get('agent_b_response', ''))}")
            print(f"Compact: {metrics.get('compact_phrase', '')}")
            print(f"Metrics: {json.dumps(metrics, ensure_ascii=False, sort_keys=True)}")
    return 0


def show_latest_report(root: Path) -> int:
    report = root / "results" / "final_report.md"
    if not report.exists():
        print("No results/final_report.md found.")
        return 1
    print(report.read_text(encoding="utf-8"), end="")
    return 0


def excerpt(text: str, limit: int = 280) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
