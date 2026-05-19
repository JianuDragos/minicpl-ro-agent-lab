# Experiment Design

MiniCPL-Ro Agent Lab is an autonomous research prototype for observing whether agents can converge on a compact machine-oriented protocol for Romanian and English concepts.

The experiment intentionally does not optimize for a readable human language. Each round pressures two roles:

- Agent A, implemented by Codex-authored prompt construction, acts as protocol architect.
- Agent B, implemented by a local Ollama model, mutates or compresses the protocol.

The arena records raw prompts, raw model responses, protocol changes, and approximate metrics. Malformed output, failed ideas, and strange protocol drift are preserved as research signal.

## Round Loop

1. Load seed vocabulary from `data/seed_vocabulary.csv`.
2. Load seed tasks from `data/seed_tasks.json`.
3. Build an Agent A pressure instruction using the current protocol state.
4. Send Agent B a prompt through `http://localhost:11434/api/generate`.
5. Always include `"think": false` in Ollama requests.
6. Read the useful model answer from the Ollama `response` field.
7. Extract a compact phrase heuristically.
8. Record metrics and update protocol state.
9. Append the full round record to `logs/transcript_*.jsonl`.

## Metrics

- Natural phrase length.
- Compact phrase length.
- Approximate compression ratio.
- Number of invented symbols.
- Number of reused symbols.
- Malformed response count.
- Protocol drift score.
- Novelty score.
- Best compact examples discovered.

These metrics are deliberately approximate. They observe behavior without forcing a single correct protocol.
