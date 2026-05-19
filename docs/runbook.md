# Runbook

## Prerequisites

- Python 3.
- Ollama running locally at `http://localhost:11434`.
- Preferred model available locally: `qwen3.6:35b-a3b`.
- Fallback model available locally: `gpt-oss:20b`.

## Run

```bash
python3 src/main.py --rounds 20 --model qwen3.6:35b-a3b --temperature 1.0
```

For a quick smoke test:

```bash
python3 src/main.py --rounds 5 --model qwen3.6:35b-a3b --temperature 1.0
```

## Outputs

- Raw transcripts: `logs/transcript_*.jsonl`
- Protocol snapshots: `results/protocol_state_*.json`
- Final report: `results/final_report.md`

## Notes

If the requested model fails, the client tries `gpt-oss:20b`. If both fail, the error is still logged as a malformed round so the unattended experiment can complete and report the failure.
