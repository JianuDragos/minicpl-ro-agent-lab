# Experiment Design

MiniCPL-Ro Agent Lab is an autonomous research prototype for observing whether agents can converge on a compact machine-oriented protocol for Romanian and English concepts.

The experiment intentionally does not optimize for a readable human language. The early arena pressures two simulated roles:

- Agent A, implemented by Codex-authored prompt construction, acts as protocol architect.
- Agent B, implemented by a local Ollama model, mutates or compresses the protocol.

Phase 5 and later can run a true dual-agent loop:

- Scripted Codex is launched through `codex exec` and acts as the Sender / language designer.
- Qwen is called through the local Ollama API and acts as Receiver plus compact responder.
- The Python controller is the mediator: it builds prompts, sends Codex output to Qwen, records responses, scores the turn, and writes JSONL/markdown reports.

Manual Codex, the coding assistant editing this repository, is separate from scripted Codex, the experiment participant invoked by `src/codex_client.py`.

The arena records raw prompts, raw model responses, protocol changes, and approximate metrics. Malformed output, failed ideas, and strange protocol drift are preserved as research signal.

## Phases

### bootstrap

The bootstrap phase gives Agent A structured pressure:

- compress this phrase
- invent shorter symbols
- preserve useful meaning
- propose reusable rules

This phase is meant to start protocol invention without locking the agents into one final format.

### lexicon_expansion

The lexicon expansion phase sits between bootstrap and autonomous exploration. Each round receives a batch of real vocabulary entries from `data/seed_vocabulary.csv` and asks Agent B to create compact tokens for actual Romanian/English concepts:

```text
<NEW "apă / water" = w>
<NEW "calculator / computer" = pc>
<NEW "a vrea / to want" = wn>
```

This phase exists because fully autonomous runs tend to invent meta-protocol tokens before they cover enough everyday concepts. Lexicon expansion preserves the same `<NEW>` and `<EVOLVE>` event format, but applies it to real seed vocabulary.

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

### phase5_dual_agent_debate

Phase 5 uses `src/dual_agent_arena.py` to alternate scripted Codex and Qwen. Codex proposes compact-language moves through `codex exec`; Qwen responds through Ollama. The controller updates `ProtocolState` from literal `<NEW>` and `<EVOLVE>` markers, runs optional sender/receiver tests, and writes phase reports under `results/`.

### phase6_strict_language

Phase 6 adds a fixed 4000-entry language base from `results/language_map_4000.csv`. Codex is the Sender and Qwen is the Receiver plus responder.

Codex must put the sender payload in a separated compact field:

```text
<COMPACT>compact tokens only here</COMPACT>
<NEW human_meaning = compact_token> optional
<EVOLVE old_token -> new_token reason> optional
<NOTE>one short note if needed</NOTE>
```

Only the content inside `<COMPACT>` is scored as the Codex compact message when that field exists. Human explanation outside `<COMPACT>`, inside `<NEW>`, inside `<EVOLVE>` reasons, and inside `<NOTE>` is not counted as compact leakage.

Qwen must decode and answer with:

```text
<DECODE compact="..." meaning="human meaning here">
<REPLY compact="compact tokens only here">
```

Human language is allowed in the `DECODE` meaning field. The `REPLY compact` field must use compact tokens from the map, newly declared tokens, or `STRICT_FAIL_NO_TOKEN` on decode failure.

Strict mode tracks separate Codex and Qwen metrics: compact-field leaks, retry behavior, token usage, decode success, responder compactness, and final reward after human-leak penalties.

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
3. Select `bootstrap`, `lexicon_expansion`, or `autonomous_exploration` from the round number.
4. Build an Agent A pressure instruction using the current protocol state and phase.
5. Send Agent B a prompt through `http://localhost:11434/api/generate`.
6. Always include `"think": false` in Ollama requests.
7. Read the useful model answer from the Ollama `response` field.
8. Extract a compact phrase heuristically when possible.
9. Record metrics and update protocol state.
10. Append the full round record to `logs/transcript_*.jsonl`.

## Dual-Agent Round Loop

1. Load the current protocol state and, in strict mode, preload `results/language_map_4000.csv`.
2. Build a Codex sender prompt from the active phase, category, recent events, language-map tokens, and previous Qwen message.
3. Run scripted Codex with `codex exec` and capture the final message.
4. In Phase 6, extract Codex `<COMPACT>`, score only that field for compact leakage, and retry once when configured if the field leaks human words or is missing.
5. Build a Qwen receiver prompt from Codex's compact message and decoder hints.
6. Run Qwen through Ollama.
7. In Phase 6, parse Qwen `<DECODE>` and `<REPLY compact>`, score decode quality separately from reply compactness, and retry the reply once when configured.
8. Update protocol state, sender/receiver rewards, JSONL logs, and markdown reports.

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
- Vocabulary entries total.
- Vocabulary entries tokenized.
- Vocabulary coverage ratio.
- Categories covered.

These metrics are deliberately approximate. They observe behavior without forcing a single correct protocol.

## Current Limitation

Codex and Qwen only remember what the controller sends in each prompt. The project maintains continuity by persisting protocol state, logs, language maps, prompts, and reports, then summarizing relevant context into the next turn. If the controller omits a past decision from the prompt, the models should be treated as not knowing it.
