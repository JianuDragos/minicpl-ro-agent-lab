"""Generate and validate complete MiniCPL compact language maps."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dictionary_2000 import (
    TARGET_ENTRY_COUNT_4000,
    Concept,
    DictionaryEntry,
    assign_tokens,
    escape_table,
    is_human_language_like_token,
    token_matches_meaning,
)


SOURCE_FILENAME_4000 = "dictionary_4000_source.csv"
CSV_FILENAME_4000 = "language_map_4000.csv"
JSON_FILENAME_4000 = "language_map_4000.json"
MD_FILENAME_4000 = "language_map_4000.md"

LANGUAGE_MAP_FIELDS = [
    "id",
    "category",
    "ro",
    "en",
    "meaning",
    "compact_token",
    "frequency_rank",
    "source_rank",
    "token_length",
    "source",
    "notes",
]


@dataclass(frozen=True)
class LanguageMapEntry:
    id: str
    category: str
    ro: str
    en: str
    meaning: str
    compact_token: str
    frequency_rank: int
    source_rank: int
    token_length: int
    source: str
    notes: str = ""


def generate_language_map_4000(root: Path) -> dict[str, Any]:
    source_path = root / "data" / SOURCE_FILENAME_4000
    concepts = read_source_concepts(source_path)
    if len(concepts) != TARGET_ENTRY_COUNT_4000:
        raise RuntimeError(
            f"{source_path} contains {len(concepts)} entries; expected {TARGET_ENTRY_COUNT_4000}."
        )
    dictionary_entries = assign_tokens(concepts)
    language_entries = [
        language_entry_from_dictionary_entry(entry) for entry in dictionary_entries
    ]

    results_dir = root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / CSV_FILENAME_4000
    json_path = results_dir / JSON_FILENAME_4000
    md_path = results_dir / MD_FILENAME_4000

    write_language_map_csv(csv_path, language_entries)
    write_language_map_json(json_path, language_entries)
    md_path.write_text(language_map_markdown(language_entries), encoding="utf-8")
    validation = validate_language_map_entries(language_entries)
    return {
        "source_path": source_path,
        "csv_path": csv_path,
        "json_path": json_path,
        "markdown_path": md_path,
        "validation": validation,
    }


def validate_language_map_4000(root: Path) -> dict[str, Any]:
    csv_path = root / "results" / CSV_FILENAME_4000
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{csv_path} does not exist. Run --generate-language-map-4000 first."
        )
    return validate_language_map_entries(read_language_map_csv(csv_path))


def read_source_concepts(path: Path) -> list[Concept]:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist. Run --generate-dictionary-4000 first.")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        Concept(
            entry_id=row["entry_id"],
            category=row["category"],
            ro=row["ro"],
            en=row["en"],
            meaning=row["meaning"],
            rank=int(row["rank"] or 0),
            source=row["source"],
            notes=row.get("notes", ""),
        )
        for row in rows
    ]


def language_entry_from_dictionary_entry(entry: DictionaryEntry) -> LanguageMapEntry:
    return LanguageMapEntry(
        id=entry.entry_id,
        category=entry.category,
        ro=entry.ro,
        en=entry.en,
        meaning=entry.meaning,
        compact_token=entry.token,
        frequency_rank=entry.rank,
        source_rank=entry.rank,
        token_length=entry.token_length,
        source=entry.source,
        notes=entry.notes,
    )


def write_language_map_csv(path: Path, entries: list[LanguageMapEntry]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LANGUAGE_MAP_FIELDS)
        writer.writeheader()
        for entry in entries:
            writer.writerow(asdict(entry))


def write_language_map_json(path: Path, entries: list[LanguageMapEntry]) -> None:
    payload = {
        "name": "MiniCPL-Ro 4000 compact language map",
        "source": SOURCE_FILENAME_4000,
        "entry_count": len(entries),
        "schema": LANGUAGE_MAP_FIELDS,
        "token_policy": {
            "ultra_common": "1 character",
            "common": "2 characters",
            "fallback": "3 characters only if unavoidable",
            "duplicates": "not allowed",
            "human_language_like_tokens": "not allowed",
        },
        "entries": [asdict(entry) for entry in entries],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_language_map_csv(path: Path) -> list[LanguageMapEntry]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        LanguageMapEntry(
            id=row["id"],
            category=row["category"],
            ro=row["ro"],
            en=row["en"],
            meaning=row["meaning"],
            compact_token=row["compact_token"],
            frequency_rank=int(row["frequency_rank"] or 0),
            source_rank=int(row["source_rank"] or 0),
            token_length=int(row["token_length"] or 0),
            source=row["source"],
            notes=row.get("notes", ""),
        )
        for row in rows
    ]


def validate_language_map_entries(entries: list[LanguageMapEntry]) -> dict[str, Any]:
    token_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    missing_tokens: list[dict[str, Any]] = []
    human_like: list[dict[str, Any]] = []
    total_token_length = 0
    max_token_length = 0

    for entry in entries:
        token = entry.compact_token
        token_counts[token] = token_counts.get(token, 0) + 1
        category_counts[entry.category] = category_counts.get(entry.category, 0) + 1
        total_token_length += len(token)
        max_token_length = max(max_token_length, len(token))
        if not token:
            missing_tokens.append(asdict(entry))
        if language_map_token_is_human_like(entry):
            human_like.append(asdict(entry))

    duplicates = {
        token: count
        for token, count in token_counts.items()
        if token and count > 1
    }
    average = round(total_token_length / len(entries), 4) if entries else 0.0
    return {
        "total_entries": len(entries),
        "duplicate_compact_tokens": duplicates,
        "duplicate_compact_token_count": len(duplicates),
        "missing_compact_tokens": missing_tokens,
        "missing_compact_token_count": len(missing_tokens),
        "average_token_length": average,
        "max_token_length": max_token_length,
        "human_language_like_tokens": human_like[:50],
        "human_language_like_token_count": len(human_like),
        "category_coverage": dict(sorted(category_counts.items())),
        "valid": (
            len(entries) == TARGET_ENTRY_COUNT_4000
            and not duplicates
            and not missing_tokens
            and not human_like
            and max_token_length <= 3
            and average <= 2.25
        ),
    }


def language_map_token_is_human_like(entry: LanguageMapEntry) -> bool:
    if is_human_language_like_token(entry.compact_token):
        return True
    dictionary_entry = DictionaryEntry(
        entry_id=entry.id,
        category=entry.category,
        ro=entry.ro,
        en=entry.en,
        meaning=entry.meaning,
        token=entry.compact_token,
        token_length=entry.token_length,
        rank=entry.source_rank,
        source=entry.source,
        notes=entry.notes,
    )
    return token_matches_meaning(dictionary_entry)


def language_map_validation_report(validation: dict[str, Any]) -> str:
    lines = [
        f"Total entries: {validation['total_entries']}",
        f"Duplicate compact tokens: {validation['duplicate_compact_token_count']}",
        f"Missing compact tokens: {validation['missing_compact_token_count']}",
        f"Average token length: {validation['average_token_length']}",
        f"Max token length: {validation['max_token_length']}",
        f"Human-language-like tokens: {validation['human_language_like_token_count']}",
        "Category coverage:",
    ]
    for category, count in validation["category_coverage"].items():
        lines.append(f"  - {category}: {count}")
    if validation["duplicate_compact_tokens"]:
        lines.append("Duplicate compact token details:")
        for token, count in validation["duplicate_compact_tokens"].items():
            lines.append(f"  - {token}: {count}")
    if validation["missing_compact_tokens"]:
        lines.append("Missing compact token examples:")
        for item in validation["missing_compact_tokens"][:10]:
            lines.append(f"  - {item['meaning']}")
    if validation["human_language_like_tokens"]:
        lines.append("Human-language-like token examples:")
        for item in validation["human_language_like_tokens"][:10]:
            lines.append(f"  - {item['meaning']} = {item['compact_token']}")
    lines.append(f"Valid: {validation['valid']}")
    return "\n".join(lines)


def language_map_markdown(entries: list[LanguageMapEntry]) -> str:
    validation = validate_language_map_entries(entries)
    lines = [
        "# MiniCPL-Ro 4000 Compact Language Map",
        "",
        f"Entries: `{validation['total_entries']}`",
        f"Average token length: `{validation['average_token_length']}`",
        f"Max token length: `{validation['max_token_length']}`",
        f"Duplicate compact tokens: `{validation['duplicate_compact_token_count']}`",
        f"Missing compact tokens: `{validation['missing_compact_token_count']}`",
        f"Human-language-like tokens: `{validation['human_language_like_token_count']}`",
        f"Valid: `{validation['valid']}`",
        "",
        "## Category Coverage",
        "",
        "| Category | Entries |",
        "|---|---:|",
    ]
    for category, count in validation["category_coverage"].items():
        lines.append(f"| {escape_table(category)} | {count} |")

    lines.extend(
        [
            "",
            "## Full Map",
            "",
            "| Rank | ID | Category | Romanian | English | Compact Token | Source |",
            "|---:|---|---|---|---|---:|---|",
        ]
    )
    for entry in entries:
        lines.append(
            f"| {entry.source_rank} | {escape_table(entry.id)} | "
            f"{escape_table(entry.category)} | {escape_table(entry.ro)} | "
            f"{escape_table(entry.en)} | `{escape_table(entry.compact_token)}` | "
            f"{escape_table(entry.source)} |"
        )
    return "\n".join(lines) + "\n"
