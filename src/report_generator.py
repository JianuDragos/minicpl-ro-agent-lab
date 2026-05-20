"""Markdown report generation for MiniCPL-Ro experiments."""

from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any


class ReportGenerator:
    def write_final_report(
        self,
        output_path: Path,
        config: dict[str, Any],
        rounds: list[dict[str, Any]],
        protocol_snapshot: dict[str, Any],
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metrics = [item["metrics"] for item in rounds]
        malformed = sum(item.get("malformed_response_count", 0) for item in metrics)
        ratios = [item.get("compression_ratio", 0.0) for item in metrics]
        drift = [item.get("protocol_drift_score", 0.0) for item in metrics]
        novelty = [item.get("novelty_score", 0.0) for item in metrics]
        stability = [item.get("protocol_stability_score", 0.0) for item in metrics]
        compact_usage = [item.get("compact_language_usage_score", 0.0) for item in metrics]
        leakage = [item.get("natural_language_leakage_score", 0.0) for item in metrics]
        continuity = [item.get("compact_protocol_continuity_score", 0.0) for item in metrics]
        fallbacks = [item.get("human_language_fallback_count", 0) for item in metrics]
        deprecated_reuse = [item.get("deprecated_token_reuse_count", 0) for item in metrics]
        best = sorted(
            protocol_snapshot.get("compact_examples", []),
            key=lambda item: item.get("compression_ratio", 0.0),
            reverse=True,
        )[:10]
        lexicon_events = protocol_snapshot.get("lexicon_events", [])
        evolution_events = protocol_snapshot.get("token_evolution_events", [])
        deprecated_tokens = protocol_snapshot.get("deprecated_tokens", {})
        dictionary = dictionary_rows(protocol_snapshot)
        real_word_dictionary = [row for row in dictionary if row.get("category") != "unmatched"]
        duplicate_tokens = duplicate_token_rows(dictionary)
        untokenized = untokenized_vocabulary(protocol_snapshot)
        compact_conversations = sorted(
            protocol_snapshot.get("compact_conversation_examples", []),
            key=lambda item: item.get("continuity_score", 0.0),
            reverse=True,
        )[:8]
        fragments = select_fragments(protocol_snapshot.get("protocol_fragments", []), limit=12)
        usage_examples = sorted(
            protocol_snapshot.get("protocol_usage_examples", []),
            key=lambda item: item.get("usage_score", 0.0),
            reverse=True,
        )[:8]
        if not usage_examples:
            usage_examples = sorted(
                protocol_snapshot.get("compact_examples", []),
                key=lambda item: item.get("usage_score", 0.0),
                reverse=True,
            )[:8]
        drift_observations = protocol_snapshot.get("drift_observations", [])[:8]
        unusual = [
            item
            for item in rounds
            if item["metrics"].get("malformed_response_count", 0)
            or item["metrics"].get("novelty_score", 0.0) > 0.75
            or item["metrics"].get("protocol_drift_score", 0.0) > 0.75
        ][:10]

        body = [
            "# MiniCPL-Ro Final Report",
            "",
            "## Experiment Configuration",
            f"- Model requested: `{config['model']}`",
            f"- Model actually used in final round: `{rounds[-1]['model_used'] if rounds else 'n/a'}`",
            f"- Rounds: `{config['rounds']}`",
            f"- Bootstrap rounds: `{config.get('bootstrap_rounds', 0)}`",
            f"- Lexicon expansion rounds: `{config.get('lexicon_rounds', 0)}`",
            f"- Temperature: `{config['temperature']}`",
            f"- Ollama URL: `{config['ollama_url']}`",
            f"- Transcript: `{config['transcript_path']}`",
            "",
            "## Bootstrap Phase Summary",
            phase_summary(rounds, "bootstrap"),
            "",
            "## Autonomous Exploration Phase Summary",
            phase_summary(rounds, "autonomous_exploration"),
            "",
            "## Lexicon Expansion Phase Summary",
            phase_summary(rounds, "lexicon_expansion"),
            "",
            "## Compression Results",
            f"- Average compression ratio: `{safe_mean(ratios):.4f}`",
            f"- Best compression ratio: `{max(ratios, default=0.0):.4f}`",
            f"- Average drift score: `{safe_mean(drift):.4f}`",
            f"- Average novelty score: `{safe_mean(novelty):.4f}`",
            f"- Average compact-language usage score: `{safe_mean(compact_usage):.4f}`",
            f"- Average natural-language leakage score: `{safe_mean(leakage):.4f}`",
            f"- Average protocol stability score: `{safe_mean(stability):.4f}`",
            f"- Malformed response count: `{malformed}`",
            f"- Known symbol count: `{len(protocol_snapshot.get('symbol_table', {}))}`",
            "",
            "## Protocol Stability",
            stability_summary(stability, drift),
            "",
            "## Lexicon Growth Summary",
            f"- New token events: `{len(lexicon_events)}`",
            f"- Current token map size: `{len(protocol_snapshot.get('current_token_map', {}))}`",
            f"- Token evolution events: `{len(evolution_events)}`",
            f"- Deprecated token count: `{len(deprecated_tokens)}`",
            "",
            "## Vocabulary Coverage",
            f"- Vocabulary entries total: `{protocol_snapshot.get('vocabulary_entries_total', 0)}`",
            f"- Vocabulary entries tokenized: `{protocol_snapshot.get('vocabulary_entries_tokenized', 0)}`",
            f"- Vocabulary coverage ratio: `{protocol_snapshot.get('vocabulary_coverage_ratio', 0.0):.4f}`",
            f"- Categories covered: `{', '.join(protocol_snapshot.get('categories_covered', [])) or 'none'}`",
            "",
            "## Tokens By Category",
            tokens_by_category_table(real_word_dictionary),
            "",
            "## Shortest Tokens",
            token_table(sorted(real_word_dictionary, key=lambda row: (len(row['token']), row['token']))[:20]),
            "",
            "## Longest Tokens",
            token_table(sorted(real_word_dictionary, key=lambda row: (len(row['token']), row['token']), reverse=True)[:20]),
            "",
            "## Duplicate Tokens",
            duplicate_token_table(duplicate_tokens),
            "",
            "## Untokenized Vocabulary",
            untokenized_vocabulary_section(untokenized),
            "",
            "## Real Word Dictionary",
            token_table(real_word_dictionary[:120]),
            "",
            "## Token Evolution Summary",
            token_evolution_summary(evolution_events),
            "",
            "## Compact-Language Continuity",
            continuity_summary(continuity, fallbacks, deprecated_reuse),
            "",
            "## New Tokens Created",
        ]

        if lexicon_events:
            for item in lexicon_events[:20]:
                body.append(
                    f"- Round {item.get('round')} ({item.get('phase')}): "
                    f"`{item.get('meaning')}` = `{item.get('token')}`"
                )
        else:
            body.append("- No `<NEW ... = ...>` token events were captured.")

        body.extend(["", "## Tokens Evolved"])
        if evolution_events:
            for item in evolution_events[:20]:
                body.append(
                    f"- Round {item.get('round')} ({item.get('phase')}): "
                    f"`{item.get('old_token')}` -> `{item.get('new_token')}` "
                    f"({item.get('reason', '')})"
                )
        else:
            body.append("- No `<EVOLVE ... -> ...>` token events were captured.")

        body.extend(["", "## Deprecated Tokens Reused"])
        deprecated_reuse_rows = deprecated_reuse_examples(rounds)
        if deprecated_reuse_rows:
            for row in deprecated_reuse_rows[:12]:
                body.append(
                    f"- Round {row['round']} ({row['phase']}): "
                    f"`{', '.join(row['tokens'])}`"
                )
        else:
            body.append("- No deprecated token reuse was detected.")

        body.extend(["", "## Best Compact Conversations"])
        if compact_conversations:
            for item in compact_conversations:
                body.append(
                    f"- Round {item.get('round')} ({item.get('phase')}): "
                    f"`{item.get('compact')}` continuity `{item.get('continuity_score')}`, "
                    f"known tokens `{', '.join(item.get('known_tokens_used', []))}`"
                )
        else:
            body.append("- No compact conversation examples were captured.")

        body.extend(
            [
                "",
                "## Observations: Did The Agents Keep Using The Language Or Fall Back To Human Language?",
                language_continuity_observation(continuity, fallbacks, leakage),
                "",
            "## Invented Protocol Fragments",
            ]
        )

        if fragments:
            for item in fragments:
                body.append(f"- Round {item['round']} ({item['phase']}): `{item['fragment']}`")
        else:
            body.append("- No protocol fragments were extracted.")

        body.extend(["", "## Direct Protocol Usage Examples"])
        if usage_examples:
            for item in usage_examples:
                body.append(
                    f"- Round {item['round']} ({item['phase']}): `{item['natural']}` -> "
                    f"`{item['compact']}` (usage `{item.get('usage_score', 0.0)}`)"
                )
        else:
            body.append("- No high compact-language usage examples were detected.")

        body.extend(
            [
                "",
                "## Drift Or Collapse Examples",
            ]
        )
        if drift_observations:
            for item in drift_observations:
                body.append(
                    f"- Round {item['round']} ({item['phase']}): drift `{item['drift']}`, "
                    f"compact `{item['compact']}`, observation `{item['observation']}`"
                )
        else:
            body.append("- No obvious drift or collapse examples were detected.")

        body.extend(
            [
                "",
            "## Best Compact Protocol Examples",
            ]
        )

        if best:
            for item in best:
                body.append(
                    f"- Round {item['round']} ({item.get('phase', 'unknown')}): "
                    f"`{item['natural']}` -> `{item['compact']}` "
                    f"(ratio `{item['compression_ratio']}`)"
                )
        else:
            body.append("- No compact examples were extracted.")

        body.extend(["", "## Unusual Protocol Behavior"])
        if unusual:
            for item in unusual:
                metrics_item = item["metrics"]
                body.append(
                    f"- Round {item['round']} ({item.get('phase', metrics_item.get('phase', 'unknown'))}): "
                    f"malformed `{metrics_item.get('malformed_response_count')}`, "
                    f"drift `{metrics_item.get('protocol_drift_score')}`, "
                    f"novelty `{metrics_item.get('novelty_score')}`, "
                    f"compact `{metrics_item.get('compact_phrase', '')}`"
                )
        else:
            body.append("- No high-drift, high-novelty, or malformed rounds were detected.")

        body.extend(
            [
                "",
                "## Limitations",
                "- Metrics are approximate and observe surface-form compression, not semantic correctness.",
                "- The evaluator extracts compact phrases heuristically and may misidentify useful model output.",
                "- Compact-language usage and leakage scores are surface signals, not judgments of quality.",
                "- `<NEW>` and `<EVOLVE>` parsing is literal and may miss informal token declarations.",
                "- Ollama model behavior depends on local model availability, quantization, and runtime settings.",
                "- A compact protocol can become hard for humans to audit, which is expected in this prototype.",
                "",
                "## Next Steps",
                "- Add semantic reconstruction tests where another model decodes compact outputs.",
                "- Compare multiple local models across identical seed tasks.",
                "- Track protocol families over longer runs and cluster recurring symbol systems.",
                "- Add decode/reconstruction rounds to test whether compact forms preserve meaning.",
                "- Add targeted prompts that ask agents to replay old tasks using only the current token map.",
            ]
        )

        output_path.write_text("\n".join(body) + "\n", encoding="utf-8")


def safe_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


def dictionary_rows(protocol_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    latest_by_meaning: dict[str, dict[str, Any]] = {}
    current_token_map = protocol_snapshot.get("current_token_map", {})
    for event in protocol_snapshot.get("lexicon_events", []):
        meaning = event.get("meaning", "")
        if not meaning:
            continue
        latest_by_meaning[meaning] = {
            "meaning": meaning,
            "token": current_token_map.get(meaning, event.get("token", "")),
            "round": event.get("round", ""),
            "phase": event.get("phase", ""),
            "category": event.get("category", "") or "unmatched",
            "concept_id": event.get("concept_id", ""),
        }
    return sorted(
        latest_by_meaning.values(),
        key=lambda row: (row["category"], str(row["meaning"])),
    )


def tokens_by_category_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "- No vocabulary-backed tokens were captured."
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    lines = ["| Category | Tokenized entries |", "|---|---:|"]
    for category, count in sorted(counts.items()):
        lines.append(f"| {escape_table(category)} | {count} |")
    return "\n".join(lines)


def token_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "- No tokens to show."
    lines = ["| Meaning | Token | Category | Round | Phase |", "|---|---:|---|---:|---|"]
    for row in rows:
        lines.append(
            f"| {escape_table(str(row.get('meaning', '')))} | `{escape_table(str(row.get('token', '')))}` | "
            f"{escape_table(str(row.get('category', '')))} | {row.get('round', '')} | {row.get('phase', '')} |"
        )
    return "\n".join(lines)


def duplicate_token_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_token: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        token = row.get("token", "")
        if token:
            by_token.setdefault(token, []).append(row)
    return {
        token: token_rows
        for token, token_rows in by_token.items()
        if len(token_rows) > 1
    }


def duplicate_token_table(duplicates: dict[str, list[dict[str, Any]]]) -> str:
    if not duplicates:
        return "- No duplicate tokens were detected."
    lines = ["| Token | Meanings |", "|---:|---|"]
    for token, rows in sorted(duplicates.items(), key=lambda item: item[0]):
        meanings = ", ".join(escape_table(str(row.get("meaning", ""))) for row in rows)
        lines.append(f"| `{escape_table(token)}` | {meanings} |")
    return "\n".join(lines)


def untokenized_vocabulary(protocol_snapshot: dict[str, Any]) -> list[dict[str, str]]:
    tokenized_ids = set(protocol_snapshot.get("tokenized_vocabulary_entries", {}).keys())
    return [
        row
        for row in protocol_snapshot.get("source_vocabulary", [])
        if row.get("concept_id") not in tokenized_ids
    ]


def untokenized_vocabulary_section(rows: list[dict[str, str]], limit: int = 40) -> str:
    if not rows:
        return "- All vocabulary entries have matching token events."
    lines = [f"- Untokenized entries remaining: `{len(rows)}`", "", "| Category | Romanian | English |", "|---|---|---|"]
    for row in rows[:limit]:
        lines.append(
            f"| {escape_table(row.get('category', ''))} | "
            f"{escape_table(row.get('ro', ''))} | {escape_table(row.get('en', ''))} |"
        )
    if len(rows) > limit:
        lines.append(f"| ... | ... | {len(rows) - limit} more |")
    return "\n".join(lines)


def escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def select_fragments(fragments: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(fragments) <= limit:
        return fragments
    selected: list[dict[str, Any]] = []
    seen_rounds: set[int] = set()
    for fragment in fragments:
        round_index = fragment.get("round")
        if round_index in seen_rounds:
            continue
        selected.append(fragment)
        seen_rounds.add(round_index)
        if len(selected) >= limit:
            return selected
    for fragment in fragments:
        if fragment in selected:
            continue
        selected.append(fragment)
        if len(selected) >= limit:
            break
    return selected


def phase_summary(rounds: list[dict[str, Any]], phase: str) -> str:
    selected = [item for item in rounds if item.get("phase") == phase]
    if not selected:
        return "- No rounds in this phase."
    metrics = [item["metrics"] for item in selected]
    return "\n".join(
        [
            f"- Rounds: `{len(selected)}`",
            f"- Average compression ratio: `{safe_mean([m.get('compression_ratio', 0.0) for m in metrics]):.4f}`",
            f"- Average compact length: `{safe_mean([m.get('compact_phrase_length', 0.0) for m in metrics]):.4f}`",
            f"- Average compact-language usage score: `{safe_mean([m.get('compact_language_usage_score', 0.0) for m in metrics]):.4f}`",
            f"- Average stability score: `{safe_mean([m.get('protocol_stability_score', 0.0) for m in metrics]):.4f}`",
            f"- Malformed responses: `{sum(m.get('malformed_response_count', 0) for m in metrics)}`",
        ]
    )


def stability_summary(stability: list[float], drift: list[float]) -> str:
    stability_avg = safe_mean(stability)
    drift_avg = safe_mean(drift)
    if stability_avg >= 0.65 and drift_avg < 0.4:
        verdict = "more stable"
    elif stability_avg <= 0.35 or drift_avg > 0.65:
        verdict = "more chaotic"
    else:
        verdict = "mixed"
    return (
        f"- Overall tendency: `{verdict}`\n"
        f"- Average stability: `{stability_avg:.4f}`\n"
        f"- Average drift: `{drift_avg:.4f}`"
    )


def token_evolution_summary(events: list[dict[str, Any]]) -> str:
    if not events:
        return "- No token evolutions were captured."
    reasons = [event.get("reason", "") for event in events if event.get("reason")]
    reason_text = "; ".join(reasons[:5]) if reasons else "No reasons supplied."
    return "\n".join(
        [
            f"- Evolutions captured: `{len(events)}`",
            f"- Recent reasons: {reason_text}",
        ]
    )


def continuity_summary(
    continuity: list[float],
    fallbacks: list[int],
    deprecated_reuse: list[int],
) -> str:
    return "\n".join(
        [
            f"- Average compact continuity score: `{safe_mean(continuity):.4f}`",
            f"- Human-language fallback count: `{sum(fallbacks)}`",
            f"- Deprecated token reuse count: `{sum(deprecated_reuse)}`",
        ]
    )


def deprecated_reuse_examples(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for item in rounds:
        tokens = item.get("metrics", {}).get("deprecated_tokens_reused", [])
        if tokens:
            examples.append(
                {
                    "round": item.get("round"),
                    "phase": item.get("phase"),
                    "tokens": tokens,
                }
            )
    return examples


def language_continuity_observation(
    continuity: list[float],
    fallbacks: list[int],
    leakage: list[float],
) -> str:
    continuity_avg = safe_mean(continuity)
    fallback_count = sum(fallbacks)
    leakage_avg = safe_mean(leakage)
    if continuity_avg >= 0.5 and fallback_count == 0:
        tendency = "agents mostly kept using compact protocol signals"
    elif fallback_count > 0 or leakage_avg > 0.75:
        tendency = "agents often fell back to human-language explanation"
    else:
        tendency = "agents mixed compact protocol with human-language scaffolding"
    return (
        f"- Tendency: `{tendency}`\n"
        f"- Average continuity: `{continuity_avg:.4f}`\n"
        f"- Average natural-language leakage: `{leakage_avg:.4f}`\n"
        f"- Fallback rounds: `{fallback_count}`"
    )
