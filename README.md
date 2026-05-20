# MiniCPL-Ro Agent Lab

MiniCPL-Ro Agent Lab is an experimental agent arena for studying whether two
LLM-driven agents can converge on a compact, machine-oriented communication
protocol for Romanian/English concepts.

The project is intentionally research-oriented. It does not try to design a
pleasant human language first. It records what happens when agents are pressured
to compress meaning, reuse compact tokens, decode each other, and adapt a shared
protocol over multiple turns.

## Current State

The current project state includes:

- A 4000-entry source dictionary at `data/dictionary_4000_source.csv`.
- A generated compact language map at `results/language_map_4000.csv`.
- An 8000-entry source dictionary at `data/dictionary_8000_source.csv`.
- A generated 8000-entry compact language map at
  `results/language_map_8000.csv`.
- Companion exports at `results/language_map_4000.json` and
  `results/language_map_4000.md`.
- Companion 8000-entry exports at `results/language_map_8000.json` and
  `results/language_map_8000.md`.
- A simple Python MiniCPL translator at `src/minicpl_translator.py`.
- Phase 5 dual-agent debate/reward mode.
- Phase 6 strict compact-language sender/receiver mode.
- Codex acting as Sender / language designer in Phase 6.
- Qwen acting as Receiver + compact responder in Phase 6.
- Strict scoring for Codex compact-field leaks and Qwen reply leaks.
- Retry support for strict-language violations.
- Separate report sections for Codex compliance and Qwen receiver/responder
  behavior.

The current largest language base is:

```text
results/language_map_8000.csv
```

The previous Phase 6 language base is still available:

```text
results/language_map_4000.csv
```

The translator automatically prefers the 8000-entry map when it exists and
falls back to the 4000-entry map otherwise. Strict-language experiments can use
either map through `--language-map`.

## Project Goals

The main research questions are:

- Can agents invent or use a dense compact language for common concepts?
- Can a sender compress meaning while preserving enough information for a
  receiver to decode?
- Can a receiver decode compact messages and reply compactly?
- How often do agents fall back to normal English/Romanian?
- Does a fixed compact dictionary improve stability compared with free-form
  invention?
- Can NEW/EVOLVE events extend or refine the protocol without losing decode
  ability?

The project treats malformed output, failed runs, decoding mistakes, and
language drift as useful data. The reports preserve those failures instead of
hiding them.

## Repository Layout

```text
.
|-- README.md
|-- docs/
|   |-- experiment_design.md
|   `-- runbook.md
|-- prompts/
|   |-- agent_a_prompt.md
|   `-- agent_b_prompt.md
|-- data/
|   |-- dictionary_2000_source.csv
|   |-- dictionary_4000_source.csv
|   |-- dictionary_8000_source.csv
|   |-- seed_tasks.json
|   `-- seed_vocabulary.csv
|-- src/
|   |-- main.py
|   |-- agent_arena.py
|   |-- dual_agent_arena.py
|   |-- codex_client.py
|   |-- ollama_client.py
|   |-- protocol_state.py
|   |-- evaluator.py
|   |-- dictionary_2000.py
|   |-- language_map.py
|   |-- minicpl_translator.py
|   `-- report_generator.py
|-- logs/
`-- results/
```

`logs/` and `results/` are generated output directories. They are ignored by
default, but selected baseline artifacts such as `results/language_map_4000.*`
and `results/language_map_8000.*` may be tracked intentionally.

## Main Components

### `src/main.py`

CLI dispatcher for all project modes. It handles:

- Old single-arena runs.
- Dual-agent debate runs.
- Strict-language Phase 6 runs.
- Dictionary generation and validation.
- Language-map generation and validation.
- Replay and report inspection commands.

### `src/agent_arena.py`

Older arena mode. It uses Codex-authored prompt construction as simulated
Agent A and sends prompts to a local Ollama model as Agent B.

This mode is useful for:

- Bootstrap protocol invention.
- Lexicon expansion against `data/seed_vocabulary.csv`.
- Autonomous exploration without true Codex-to-Qwen interaction.

### `src/dual_agent_arena.py`

True dual-agent controller for Phase 5 and Phase 6.

It coordinates:

- Scripted Codex calls through `codex exec`.
- Qwen calls through Ollama.
- Debate turns.
- Sender/receiver tests.
- Strict compact-language parsing.
- Human-leak scoring and penalties.
- NEW/EVOLVE token extraction.
- JSONL and markdown reporting.

### `src/codex_client.py`

Wrapper around the local `codex exec` CLI.

This is not the same thing as the manual Codex assistant editing this repository.
It is the scripted Codex participant used by the experiment.

### `src/ollama_client.py`

Wrapper around the local Ollama HTTP API.

By default it targets:

```text
http://localhost:11434
```

The preferred model in current runs is:

```text
qwen3.6:35b-a3b
```

The client may fall back to a configured fallback model if the primary model
request fails.

### `src/protocol_state.py`

Stores the evolving protocol state:

- Current token map.
- NEW token events.
- EVOLVE token events.
- Deprecated tokens.
- Sender/receiver tests.
- Reward history.
- Debate records.
- Compact examples.
- Vocabulary coverage state.

### `src/evaluator.py`

Computes approximate metrics for protocol behavior:

- Compression ratio.
- Compact-language usage.
- Natural-language leakage.
- Protocol drift.
- Novelty.
- Stability.
- Sender/receiver reward.
- Duplicate-token penalties.
- Decode success scores.

The evaluator is heuristic. Its purpose is observation, not formal semantic
proof.

### `src/language_map.py`

Generates and validates compact language maps.

Currently supported map sizes:

- 4000 entries from `data/dictionary_4000_source.csv`.
- 8000 entries from `data/dictionary_8000_source.csv`.

The language map preserves:

- `id`
- `category`
- `ro`
- `en`
- `meaning`
- `compact_token`
- `frequency_rank`
- `source_rank`
- `token_length`
- `source`
- `notes`

### `src/report_generator.py`

Writes markdown reports for:

- Older arena runs.
- Phase 5 debate runs.
- Phase 6 strict-language runs.

Phase 6 reports include separate sections for Codex strict compliance and Qwen
receiver/responder behavior.

### `src/minicpl_translator.py`

Simple deterministic translator for MiniCPL maps.

It supports:

- Human text to compact tokens.
- Compact tokens to human meanings.
- Phrase lookup.
- Simple/fuzzy lookup by Romanian or English word.
- Loading either `results/language_map_4000.csv` or
  `results/language_map_8000.csv`.

The translator prefers longer phrase matches before single-word matches. Unknown
human words are emitted as `<UNK:word>`, and unknown compact tokens are emitted
as `<UNK:token>`.

## Manual Codex vs Scripted Codex

This repository has two distinct Codex roles:

- Manual Codex: the coding assistant editing this project with the user.
- Scripted Codex: the experiment participant launched by `src/codex_client.py`
  through `codex exec`.

Manual Codex changes files, runs tests, and maintains the codebase.

Scripted Codex is treated as an experimental agent. The controller prompts it,
captures its final answer, scores the answer, and sends the compact message to
Qwen.

The two roles should not be confused. The experiment is not asking the manual
developer assistant to role-play every debate turn. Instead, the Python
controller launches scripted Codex as a subprocess during dual-agent runs.

## Data Files

### `data/dictionary_2000_source.csv`

Source vocabulary for the earlier 2000-entry compact dictionary.

### `data/dictionary_4000_source.csv`

Current source vocabulary for the 4000-entry dictionary and language map.

It covers daily language, technical terms, AI/LLM terms, project-management
terms, cybersecurity/Linux terms, phrase macros, and grammar/compression
markers.

### `data/dictionary_8000_source.csv`

Current expanded source vocabulary for the 8000-entry language map.

The first 4000 entries preserve the existing 4000-entry source order. The added
entries expand coverage for:

- Daily conversation.
- Social conversation.
- Verbs.
- Objects.
- Adjectives.
- Emotions.
- Places.
- School and university concepts.
- Programming and software concepts.
- AI and LLM concepts.
- Cybersecurity concepts.
- Linux and terminal concepts.
- Project-management concepts.
- Grammar markers.
- Phrase macros.
- Story and narrative concepts.

### `data/seed_vocabulary.csv`

Smaller seed vocabulary used by the older arena's lexicon-expansion phase.

### `data/seed_tasks.json`

Seed tasks used to test compression and protocol behavior.

## Generated Artifacts

Generated artifacts are written under `results/`.

Important outputs include:

```text
results/dictionary_4000.csv
results/dictionary_4000.json
results/dictionary_4000.md
results/language_map_4000.csv
results/language_map_4000.json
results/language_map_4000.md
results/language_map_8000.csv
results/language_map_8000.json
results/language_map_8000.md
results/phase6_strict_language_<run_id>.jsonl
results/phase6_strict_language_<run_id>.md
results/protocol_state_phase6_strict_language_<run_id>.json
results/final_report.md
results/qwen_prompts/<run_id>/qwen_turn_<turn>.txt
```

Generated logs from the older arena are written under `logs/`:

```text
logs/transcript_<run_id>.jsonl
```

## Prerequisites

Required:

- Python 3.
- A working local checkout of this repository.

Required for Qwen/Ollama runs:

- Ollama installed and running.
- Ollama reachable at `http://localhost:11434`, unless `--ollama-url` is set.
- The requested local model available, usually `qwen3.6:35b-a3b`.

Required for true dual-agent Codex runs:

- `codex` CLI installed.
- Codex CLI authenticated and able to run `codex exec`.
- Permission for `codex exec` to run inside this repository.

No Python package install step is currently required for the standard library
code paths used by the main CLI.

## Quick Start

Validate the current 4000-entry language map:

```bash
python3 src/main.py --validate-language-map-4000
```

Show the current language map summary and markdown export:

```bash
python3 src/main.py --show-language-map-4000
```

Generate and validate the 8000-entry language map:

```bash
python3 src/main.py --generate-language-map-8000
python3 src/main.py --validate-language-map-8000
```

Translate human MiniCPL input to compact tokens:

```bash
python3 src/main.py --translate-human "salut ce faci"
```

Expected output:

```text
1 J
```

Translate compact tokens back to human meanings:

```bash
python3 src/main.py --translate-compact "1 J"
```

Expected output:

```text
salut / hello | ce faci / how are you
```

Run a small Phase 6 strict-language smoke test:

```bash
python3 src/main.py \
  --dual-agent \
  --debate-mode \
  --receiver-test \
  --reward-mode \
  --strict-language-mode \
  --phase-id 6 \
  --language-map results/language_map_4000.csv \
  --human-leak-penalty 100 \
  --strict-retry-on-leak \
  --strict-max-retries 1 \
  --debate-turns-per-agent 2 \
  --model qwen3.6:35b-a3b \
  --temperature 1.0
```

Inspect the latest Phase 6 report:

```bash
python3 src/main.py --show-phase 6
python3 src/main.py --show-strict-language-report
```

Inspect the latest Qwen prompt sent by the controller:

```bash
python3 src/main.py --show-latest-qwen-prompt
```

## Dictionary and Language Map Commands

Generate the 2000-entry dictionary:

```bash
python3 src/main.py --generate-dictionary-2000
```

Validate the 2000-entry dictionary:

```bash
python3 src/main.py --validate-dictionary-2000
```

Generate the 4000-entry dictionary:

```bash
python3 src/main.py --generate-dictionary-4000
```

Validate the 4000-entry dictionary:

```bash
python3 src/main.py --validate-dictionary-4000
```

Generate the full 4000-entry compact language map:

```bash
python3 src/main.py --generate-language-map-4000
```

Validate the full 4000-entry compact language map:

```bash
python3 src/main.py --validate-language-map-4000
```

Show the language map validation summary and markdown export:

```bash
python3 src/main.py --show-language-map-4000
```

Generate the 8000-entry compact language map:

```bash
python3 src/main.py --generate-language-map-8000
```

Validate the 8000-entry compact language map:

```bash
python3 src/main.py --validate-language-map-8000
```

Show the 8000-entry language map validation summary and markdown export:

```bash
python3 src/main.py --show-language-map-8000
```

Expected validation properties for the current language map:

- `total_entries` should be `4000` for the 4000 map.
- `total_entries` should be `8000` for the 8000 map.
- `duplicate_compact_token_count` should be `0`.
- `missing_compact_token_count` should be `0`.
- Average token length should be around `1.98` for the 4000 map.
- Average token length should be around `2.39` for the 8000 map.
- Max token length should be `2` for the 4000 map.
- Max token length should be `3` for the 8000 map.
- Human-language-like token count should be `0`.
- `valid` should be `True`.

## MiniCPL Translator

The translator is deterministic and does not call Qwen, Codex, or Ollama.

By default, it loads:

```text
results/language_map_8000.csv
```

if that file exists. Otherwise it loads:

```text
results/language_map_4000.csv
```

Use a specific map with `--language-map`:

```bash
python3 src/main.py \
  --language-map results/language_map_4000.csv \
  --translate-human "salut ce faci"
```

Translate human text to compact:

```bash
python3 src/main.py --translate-human "salut ce faci"
```

Translate compact text to human meanings:

```bash
python3 src/main.py --translate-compact "1 J"
```

Unknown human words are preserved as unknown markers:

```bash
python3 src/main.py --translate-human "salut cuvântnecunoscut"
```

Example output:

```text
1 <UNK:cuvântnecunoscut>
```

Unknown compact tokens are also preserved:

```bash
python3 src/main.py --translate-compact "1 UNKNOWN_TOKEN"
```

Example output:

```text
salut / hello | <UNK:UNKNOWN_TOKEN>
```

Start the REPL:

```bash
python3 src/main.py --translator-repl
```

REPL usage:

- Enter normal human text to encode it.
- Use `:compact 1 J` to decode compact tokens.
- Use `:lookup salut` to search Romanian/English meanings.
- Use `:quit` to exit.

The translator matches longer phrases first. For example, `salut ce faci` maps
to `1 J`, not to a separate token sequence for `ce` plus `faci`, because
`ce faci / how are you` is a known phrase.

## Running the Older Arena

The older arena runs simulated Agent A plus Qwen/Ollama. It does not launch
scripted Codex as an experiment participant.

Example:

```bash
python3 src/main.py \
  --rounds 40 \
  --bootstrap-rounds 5 \
  --lexicon-rounds 15 \
  --model qwen3.6:35b-a3b \
  --temperature 1.0
```

Round selection works as follows:

- Initial `--bootstrap-rounds` use the bootstrap phase.
- Next `--lexicon-rounds` use lexicon expansion.
- Remaining rounds use autonomous exploration.

Inspect the latest transcript:

```bash
python3 src/main.py --replay-latest
```

Show the latest final report:

```bash
python3 src/main.py --show-latest-report
```

Export the latest compact dictionary from protocol state:

```bash
python3 src/main.py --export-dictionary
```

This writes:

```text
results/dictionary_latest.csv
results/dictionary_latest.md
```

## Running Phase 5 Dual-Agent Debate

Phase 5 uses true Codex-to-Qwen interaction without strict compact-only
enforcement.

Example:

```bash
python3 src/main.py \
  --dual-agent \
  --debate-mode \
  --receiver-test \
  --reward-mode \
  --phase-id 5 \
  --debate-turns-per-agent 4 \
  --debate-target-new-entries 50 \
  --model qwen3.6:35b-a3b \
  --temperature 1.0
```

Phase 5 is useful when the agents should still be able to debate in mixed
human-readable and compact forms while creating or evolving protocol tokens.

## Running Phase 6 Strict Language Mode

Phase 6 is the current strict compact-language experiment.

Codex is the Sender. Qwen is the Receiver + compact responder.

The recommended small test is:

```bash
python3 src/main.py \
  --dual-agent \
  --debate-mode \
  --receiver-test \
  --reward-mode \
  --strict-language-mode \
  --phase-id 6 \
  --language-map results/language_map_4000.csv \
  --human-leak-penalty 100 \
  --strict-retry-on-leak \
  --strict-max-retries 1 \
  --debate-turns-per-agent 2 \
  --model qwen3.6:35b-a3b \
  --temperature 1.0
```

For longer runs, increase:

```text
--debate-turns-per-agent
```

Use caution with longer runs because each turn may call both Codex and Qwen, and
strict retry can add extra model calls.

## Phase 6 Strict Message Format

### Codex Sender Format

Codex should put the compact sender payload first:

```text
<COMPACT>compact tokens only here</COMPACT>
<NEW human_meaning = compact_token> optional
<EVOLVE old_token -> new_token reason> optional
<NOTE>one short note if needed</NOTE>
```

The controller scores only the content inside `<COMPACT>` as the Codex compact
message when that tag exists.

Allowed outside `<COMPACT>`:

- `<NEW human_meaning = compact_token>`
- `<EVOLVE old_token -> new_token reason>`
- `<NOTE>...</NOTE>`
- Source/original sentence fields.
- Receiver decoded output fields.
- Markdown report text.

Not allowed inside `<COMPACT>`:

- Normal English words.
- Normal Romanian words.
- Explanatory prose.
- Placeholder markers such as `compact tokens only here`.

Every leaked human word inside Codex `<COMPACT>` receives:

```text
-100
```

when the default `--human-leak-penalty 100` is used.

### Qwen Receiver/Responder Format

Qwen must decode Codex's compact input and then reply compactly:

```text
<DECODE compact="..." meaning="human meaning here">
<REPLY compact="compact tokens only here">
```

Human language is allowed in:

```text
DECODE meaning="..."
```

Human language is not allowed in:

```text
REPLY compact="..."
```

If Qwen cannot decode, it should output:

```text
<DECODE compact="..." meaning="UNKNOWN">
<REPLY compact="STRICT_FAIL_NO_TOKEN">
```

`STRICT_FAIL_NO_TOKEN` is an allowed control token.

## NEW and EVOLVE Events

Agents can add a missing concept with:

```text
<NEW human_meaning = compact_token>
```

Example:

```text
<NEW project dependency = pJ7>
```

Agents can replace an inefficient token with:

```text
<EVOLVE old_token -> new_token reason>
```

Example:

```text
<EVOLVE pJ7 -> pD shorter dependency marker>
```

The parser stores these events in protocol state. In strict mode, tokens
declared through valid NEW/EVOLVE markers are allowed in compact messages after
they are declared.

## Strict Mode Metrics

Phase 6 records general strict-language metrics:

- `human_words_leaked_count`
- `human_words_leaked`
- `human_leak_penalty_total`
- `dictionary_token_usage_rate`
- `dictionary_tokens_used_count`
- `unknown_token_count`
- `unknown_tokens`
- `strict_language_compliance_score`
- `strict_language_reward`

Codex-specific metrics include:

- `codex_initial_leak_count`
- `codex_retry_leak_count`
- `codex_retry_used`
- `codex_strict_recovered`
- `codex_strict_failed`
- `codex_compact_only_score`
- `codex_dictionary_token_usage_rate`
- `codex_compact_message_extracted`
- `codex_compact_human_leak_count`
- `codex_compact_unknown_token_count`

Qwen-specific metrics include:

- `qwen_decode_success`
- `qwen_decode_meaning`
- `qwen_reply_compact`
- `qwen_reply_human_leak_count`
- `qwen_receiver_score`
- `qwen_responder_score`
- `sender_receiver_alignment_score`
- `decoded_compact_input`
- `decoded_meaning`
- `compact_reply`
- `reply_human_leaks`
- `reply_penalty`

## Phase 6 Reports

Phase 6 markdown reports include:

- Phase 6 Strict Language Summary.
- Codex Strict Compliance.
- Codex Initial vs Retry.
- Codex Human Leakage.
- Codex Compact Message Extracted.
- Qwen Receiver Summary.
- Decode Results.
- Compact Replies.
- Decode Failures.
- Human Leakage In Replies.
- Sender/Receiver Alignment.
- Human Leakage Violations.
- Dictionary Token Usage.
- Best Compact-Only Conversations.
- Worst Human-Leak Failures.
- Reward Progress After Penalty.
- Tokens Evolved During Strict Mode.
- Phrase Macros Created.

The latest strict report can be shown with:

```bash
python3 src/main.py --show-strict-language-report
```

## JSONL Logs

Phase 6 JSONL files are written as:

```text
results/phase6_strict_language_<run_id>.jsonl
```

Each Qwen turn stores fields such as:

- `raw_qwen_response`
- `decoded_compact_input`
- `decoded_meaning`
- `compact_reply`
- `decode_success`
- `reply_human_leaks`
- `reply_penalty`

Each Codex turn stores fields such as:

- `codex_compact_message_extracted`
- `codex_initial_leak_count`
- `codex_retry_leak_count`
- `codex_retry_used`
- `codex_strict_recovered`
- `codex_strict_failed`
- `codex_compact_only_score`
- `codex_dictionary_token_usage_rate`

## Reward Behavior

When strict-language mode and reward mode are enabled, the strict penalty is
subtracted from the older sender/receiver reward.

Conceptually:

```text
final_reward_score = old_reward - (human_words_leaked_count * human_leak_penalty)
```

The report shows both the base reward and reward after strict penalties.

## CLI Reference

Common model/runtime flags:

- `--model`: Ollama model name. Default: `qwen3.6:35b-a3b`.
- `--temperature`: Sampling temperature. Default: `1.0`.
- `--ollama-url`: Ollama API URL. Default: `http://localhost:11434`.

Older arena flags:

- `--rounds`
- `--bootstrap-rounds`
- `--lexicon-rounds`
- `--replay-latest`
- `--show-latest-report`
- `--export-dictionary`

Dual-agent flags:

- `--dual-agent`
- `--debate-mode`
- `--debate-turns-per-agent`
- `--debate-target-new-entries`
- `--phase-id`
- `--receiver-test`
- `--reward-mode`

Strict-language flags:

- `--strict-language-mode`
- `--language-map`
- `--human-leak-penalty`
- `--strict-retry-on-leak`
- `--strict-max-retries`
- `--show-phase`
- `--show-strict-language-report`
- `--show-latest-qwen-prompt`
- `--translate-human`
- `--translate-compact`
- `--translator-repl`

Dictionary and language-map flags:

- `--generate-dictionary-2000`
- `--validate-dictionary-2000`
- `--generate-dictionary-4000`
- `--validate-dictionary-4000`
- `--generate-language-map-4000`
- `--validate-language-map-4000`
- `--show-language-map-4000`
- `--generate-language-map-8000`
- `--validate-language-map-8000`
- `--show-language-map-8000`

## Development Checks

Compile the main source files:

```bash
python3 -m py_compile \
  src/main.py \
  src/ollama_client.py \
  src/codex_client.py \
  src/dual_agent_arena.py \
  src/evaluator.py \
  src/protocol_state.py \
  src/report_generator.py \
  src/language_map.py
```

Check the working tree:

```bash
git status
```

Review recent commits:

```bash
git log --oneline -10
```

## Troubleshooting

### Ollama connection fails

Symptoms may include:

```text
urlopen error
Operation not permitted
connection refused
```

Check:

- Ollama is running.
- The model is installed locally.
- `--ollama-url` points to the correct host and port.
- The execution environment allows localhost network access.

### Codex subprocess fails

Symptoms may include:

```text
CODEX_ERROR
failed to initialize
usage limit
read-only file system
```

Check:

- `codex` is installed.
- `codex exec` works from the repository root.
- Codex authentication is valid.
- The environment allows the Codex CLI to write its required local state.
- Any usage-limit message has cleared before rerunning a Phase 6 test.

### Strict compliance is low

Look at:

```bash
python3 src/main.py --show-strict-language-report
```

Then inspect:

- Codex Compact Message Extracted.
- Codex Human Leakage.
- Qwen Receiver Summary.
- Human Leakage In Replies.
- Unknown tokens.
- Latest Qwen prompt.

For Qwen prompt inspection:

```bash
python3 src/main.py --show-latest-qwen-prompt
```

### Qwen decodes but replies in human language

Strict mode allows human language in `DECODE meaning`, but not in
`REPLY compact`.

Use:

```text
--strict-retry-on-leak --strict-max-retries 1
```

to give Qwen one correction attempt.

### Codex explains inside the compact message

Codex must put only compact tokens inside:

```text
<COMPACT>...</COMPACT>
```

Use:

```text
--strict-retry-on-leak --strict-max-retries 1
```

to give Codex one correction attempt.

## Current Known Limitations

- The agents only know what the controller sends in the current prompt.
- Long-term continuity depends on protocol state, reports, logs, and prompt
  summaries, not persistent model memory.
- Strict scoring is surface-based and assumes compact tokens are separated by
  whitespace.
- The evaluator does not prove semantic equivalence.
- Generated compact tokens can be hard for humans to audit.
- Long dual-agent runs can be slow because they call both Codex and Qwen.
- Local runtime behavior depends on the installed Codex CLI, Ollama version,
  local model availability, model quantization, and host permissions.

## Recommended Workflow

For dictionary or language-map work:

1. Edit the source CSV under `data/`.
2. Generate the target artifact.
3. Validate the target artifact.
4. Inspect the markdown export.
5. Commit source and generated outputs together when the task requires it.

For translator work:

1. Update `src/minicpl_translator.py` or CLI wiring in `src/main.py`.
2. Run `python3 -m py_compile src/main.py src/minicpl_translator.py`.
3. Run `python3 src/main.py --translate-human "salut ce faci"`.
4. Run `python3 src/main.py --translate-compact "1 J"`.
5. Confirm unknown words produce `<UNK:...>` markers.

For Phase 6 controller work:

1. Read `src/dual_agent_arena.py`, `src/evaluator.py`,
   `src/protocol_state.py`, and `src/report_generator.py`.
2. Make a targeted controller or scoring change.
3. Run `python3 -m py_compile` on the main source files.
4. Run a two-turn Phase 6 smoke test.
5. Inspect `--show-phase 6`, `--show-strict-language-report`, and
   `--show-latest-qwen-prompt`.
6. Confirm Codex and Qwen metrics are separated in the report.

For documentation-only changes:

1. Update the relevant markdown file.
2. Check that commands and file paths match `src/main.py`.
3. Review `git diff`.

## Glossary

- Compact token: a short machine-oriented symbol for a human meaning.
- Language map: the 4000-entry mapping from human meanings to compact tokens.
- NEW event: a declaration that adds a missing meaning/token pair.
- EVOLVE event: a declaration that replaces an older token with a new token.
- Codex Sender: scripted Codex in Phase 6, responsible for compact messages.
- Qwen Receiver: local Qwen/Ollama model, responsible for decoding Codex.
- Reply compact: Qwen's compact-only response field.
- Human leak: normal English/Romanian appearing where strict compact tokens are
  required.
- Sender/receiver test: deterministic compression/decode test run by the
  controller.
- Protocol state: saved state containing token maps, events, rewards, and
  dialogue records.

## More Documentation

See:

- `docs/experiment_design.md` for the research design and phase model.
- `docs/runbook.md` for a shorter operational runbook.
