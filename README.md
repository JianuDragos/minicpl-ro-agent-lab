# MiniCPL-Ro Agent Lab

Experimental project where Codex and a local Ollama model collaborate to invent a compact machine-oriented language for Romanian/English concepts.

The goal is not correctness at first, but observation: what kind of protocol/language emerges when two agents are allowed to iterate with minimal human intervention.

## Current Architecture

- `src/main.py` is the CLI dispatcher.
- `src/agent_arena.py` runs the older simulated Agent A plus Qwen arena.
- `src/dual_agent_arena.py` runs the true Codex to Qwen dual-agent arena.
- `src/codex_client.py` calls Codex through `codex exec`.
- `src/ollama_client.py` calls Qwen through the local Ollama API.
- `src/protocol_state.py` stores token declarations, evolutions, rewards, and dialogue state.
- `src/evaluator.py` scores compression, token use, leakage, and sender/receiver behavior.
- `src/language_map.py` generates and validates the 4000-entry compact language map.
- `results/language_map_4000.csv` is the required compact language base for Phase 6.

## Manual Codex vs Scripted Codex

This repository has two Codex roles:

- Manual Codex is the coding assistant editing and testing this project.
- Scripted Codex is the experiment participant launched by `src/codex_client.py` with `codex exec`.

In Phase 5 and Phase 6, the Python controller prompts scripted Codex, captures its final message, then sends that message to Qwen through Ollama. The agents do not directly share process memory; they only receive the context that the controller includes in each prompt.

## Phase 6 Strict Sender/Receiver Mode

Phase 6 uses `results/language_map_4000.csv` as the required compact language. Codex acts as Sender and must emit a compact field first:

```text
<COMPACT>compact tokens only here</COMPACT>
<NEW human_meaning = compact_token> optional
<EVOLVE old_token -> new_token reason> optional
<NOTE>one short note if needed</NOTE>
```

Qwen acts as Receiver plus compact responder:

```text
<DECODE compact="..." meaning="human meaning here">
<REPLY compact="compact tokens only here">
```

Human language is allowed in decode meanings, source/original sentence fields, `<NEW>` human meanings, `<EVOLVE>` reasons, notes, and reports. Human words inside Codex `<COMPACT>` or Qwen `REPLY compact` are strict-mode leaks and receive the configured penalty.

Run a small Phase 6 check with:

```bash
python3 src/main.py --dual-agent --debate-mode --receiver-test --reward-mode --strict-language-mode --phase-id 6 --language-map results/language_map_4000.csv --human-leak-penalty 100 --strict-retry-on-leak --strict-max-retries 1 --debate-turns-per-agent 2 --model qwen3.6:35b-a3b --temperature 1.0
```

Useful inspection commands:

```bash
python3 src/main.py --validate-language-map-4000
python3 src/main.py --show-phase 6
python3 src/main.py --show-strict-language-report
python3 src/main.py --show-latest-qwen-prompt
```

## Known Limitation

The models only remember what the controller sends in the current prompt. Long-term continuity comes from files and protocol state that the controller reloads and summarizes each turn, not from persistent memory inside Codex or Qwen.
