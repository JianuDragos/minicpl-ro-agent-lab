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
        best = sorted(
            protocol_snapshot.get("compact_examples", []),
            key=lambda item: item.get("compression_ratio", 0.0),
            reverse=True,
        )[:10]
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
            f"- Temperature: `{config['temperature']}`",
            f"- Ollama URL: `{config['ollama_url']}`",
            f"- Transcript: `{config['transcript_path']}`",
            "",
            "## Compression Results",
            f"- Average compression ratio: `{safe_mean(ratios):.4f}`",
            f"- Best compression ratio: `{max(ratios, default=0.0):.4f}`",
            f"- Average drift score: `{safe_mean(drift):.4f}`",
            f"- Average novelty score: `{safe_mean(novelty):.4f}`",
            f"- Malformed response count: `{malformed}`",
            f"- Known symbol count: `{len(protocol_snapshot.get('symbol_table', {}))}`",
            "",
            "## Best Compact Protocol Examples",
        ]

        if best:
            for item in best:
                body.append(
                    f"- Round {item['round']}: `{item['natural']}` -> `{item['compact']}` "
                    f"(ratio `{item['compression_ratio']}`)"
                )
        else:
            body.append("- No compact examples were extracted.")

        body.extend(["", "## Unusual Protocol Behavior"])
        if unusual:
            for item in unusual:
                metrics_item = item["metrics"]
                body.append(
                    f"- Round {item['round']}: malformed `{metrics_item.get('malformed_response_count')}`, "
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
                "- Ollama model behavior depends on local model availability, quantization, and runtime settings.",
                "- A compact protocol can become hard for humans to audit, which is expected in this prototype.",
                "",
                "## Next Steps",
                "- Add semantic reconstruction tests where another model decodes compact outputs.",
                "- Compare multiple local models across identical seed tasks.",
                "- Track protocol families over longer runs and cluster recurring symbol systems.",
                "- Add replay mode for previously captured transcripts.",
            ]
        )

        output_path.write_text("\n".join(body) + "\n", encoding="utf-8")


def safe_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0
