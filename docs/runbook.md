# Runbook

## Prerequisites

- Python 3.
- Ollama running locally at `http://localhost:11434`.
- Preferred model available locally: `qwen3.6:35b-a3b`.
- Fallback model available locally: `gpt-oss:20b`.

## Run

```bash
python3 src/main.py --rounds 30 --bootstrap-rounds 8 --model qwen3.6:35b-a3b --temperature 1.0
```

For a quick smoke test:

```bash
python3 src/main.py --rounds 8 --bootstrap-rounds 4 --model qwen3.6:35b-a3b --temperature 1.0
```

`--bootstrap-rounds` controls how many initial rounds use structured protocol-invention pressure. Remaining rounds use the `autonomous_exploration` phase.

## Outputs

- Raw transcripts: `logs/transcript_*.jsonl`
- Protocol snapshots: `results/protocol_state_*.json`
- Final report: `results/final_report.md`

## Replay

Print the latest transcript in a compact readable form:

```bash
python3 src/main.py --replay-latest
```

Show the latest final report:

```bash
python3 src/main.py --show-latest-report
```

## Notes

If the requested model fails, the client tries `gpt-oss:20b`. If both fail, the error is still logged as a malformed round so the unattended experiment can complete and report the failure.

The autonomous phase deliberately does not force JSON or a fixed protocol format. The evaluator uses heuristics to observe compactness, reuse, leakage, stability, and drift.

During autonomous exploration the prompts encourage lexicon continuity:

- Reuse known compact tokens where possible.
- Declare missing concepts with `<NEW meaning = token>`.
- Declare replacements with `<EVOLVE old_token -> new_token reason>`.

These markers are logged and reported when the model produces them, but the model is still allowed to redesign or abandon protocol families.
