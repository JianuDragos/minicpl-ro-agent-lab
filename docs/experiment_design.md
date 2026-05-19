# Experiment Design

MiniCPL-Ro Agent Lab is an autonomous research prototype for observing whether agents can converge on a compact machine-oriented protocol for Romanian and English concepts.

The experiment intentionally does not optimize for a readable human language. Each round pressures two roles:

- Agent A, implemented by Codex-authored prompt construction, acts as protocol architect.
- Agent B, implemented by a local Ollama model, mutates or compresses the protocol.

The arena records raw prompts, raw model responses, protocol changes, and approximate metrics. Malformed output, failed ideas, and strange protocol drift are preserved as research signal.

## Phases

### bootstrap

The bootstrap phase gives Agent A structured pressure:

- compress this phrase
- invent shorter symbols
- preserve useful meaning
- propose reusable rules

This phase is meant to start protocol invention without locking the agents into one final format.

### autonomous_exploration

The autonomous exploration phase gives broader objective-driven prompts. Agent B may decide what to do next inside the language-design goal:

- invent new symbols, numeric codes, byte-like codes, or grammar rules
- compress words, phrases, or full meanings
- abandon failed protocol ideas
- merge protocol families
- create domain sub-languages
- use Romanian, English, symbols, IDs, or mixed forms
- communicate directly in the compact language
- explain less over time if a compact protocol stabilizes
- self-propose new language-design experiments

The agents cannot control the operating system or perform external actions. Their autonomy is limited to protocol design and protocol use inside the transcript.

## Lexicon Growth

After bootstrap, agents are encouraged to keep using compact tokens they have already created. When a concept is missing, they can declare it inline:

```text
<NEW "calculator" = C12>
<NEW "I need help" = H?>
```

If a shorter or more systematic token replaces an existing token, they can declare an evolution:

```text
<EVOLVE C12 -> C2 shorter>
<EVOLVE H? -> H because question mark is unnecessary>
```

The arena parses these literal markers and preserves them in protocol state as lexicon events, token evolution events, the current token map, deprecated tokens, and compact conversation examples. The markers are encouraged but not required; the creative rounds remain free-form.

## Round Loop

1. Load seed vocabulary from `data/seed_vocabulary.csv`.
2. Load seed tasks from `data/seed_tasks.json`.
3. Select `bootstrap` or `autonomous_exploration` from the round number.
4. Build an Agent A pressure instruction using the current protocol state and phase.
5. Send Agent B a prompt through `http://localhost:11434/api/generate`.
6. Always include `"think": false` in Ollama requests.
7. Read the useful model answer from the Ollama `response` field.
8. Extract a compact phrase heuristically when possible.
9. Record metrics and update protocol state.
10. Append the full round record to `logs/transcript_*.jsonl`.

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
- Phase.
- Compact-language usage score.
- Known symbol reuse rate.
- Natural-language leakage score.
- Protocol stability score.
- Average compact length.
- Best compression ratio so far.
- New token events count.
- Token evolution events count.
- Human-language fallback count.
- Compact protocol continuity score.
- Token reuse after creation score.
- Deprecated token reuse count.

These metrics are deliberately approximate. They observe behavior without forcing a single correct protocol.
