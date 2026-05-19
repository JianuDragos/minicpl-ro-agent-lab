"""CLI entry point for MiniCPL-Ro Agent Lab."""

from __future__ import annotations

import argparse
from pathlib import Path

from agent_arena import AgentArena
from report_generator import ReportGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the MiniCPL-Ro agent arena.")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--model", default="qwen3.6:35b-a3b")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    arena = AgentArena(
        model=args.model,
        temperature=args.temperature,
        rounds=args.rounds,
        ollama_url=args.ollama_url,
        root=root,
    )
    result = arena.run()

    config = {
        "model": args.model,
        "rounds": args.rounds,
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


if __name__ == "__main__":
    raise SystemExit(main())
