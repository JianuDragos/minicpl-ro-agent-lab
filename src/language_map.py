"""Generate and validate complete MiniCPL compact language maps."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dictionary_2000 import (
    TARGET_ENTRY_COUNT_4000,
    TARGET_ENTRY_COUNT_8000,
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
SOURCE_FILENAME_8000 = "dictionary_8000_source.csv"
CSV_FILENAME_8000 = "language_map_8000.csv"
JSON_FILENAME_8000 = "language_map_8000.json"
MD_FILENAME_8000 = "language_map_8000.md"

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
    return generate_language_map(
        root=root,
        target_entry_count=TARGET_ENTRY_COUNT_4000,
        source_filename=SOURCE_FILENAME_4000,
        csv_filename=CSV_FILENAME_4000,
        json_filename=JSON_FILENAME_4000,
        md_filename=MD_FILENAME_4000,
    )


def generate_language_map_8000(root: Path) -> dict[str, Any]:
    return generate_language_map(
        root=root,
        target_entry_count=TARGET_ENTRY_COUNT_8000,
        source_filename=SOURCE_FILENAME_8000,
        csv_filename=CSV_FILENAME_8000,
        json_filename=JSON_FILENAME_8000,
        md_filename=MD_FILENAME_8000,
    )


def generate_language_map(
    root: Path,
    target_entry_count: int,
    source_filename: str,
    csv_filename: str,
    json_filename: str,
    md_filename: str,
) -> dict[str, Any]:
    source_path = root / "data" / source_filename
    concepts = read_source_concepts(source_path)
    if len(concepts) != target_entry_count:
        raise RuntimeError(
            f"{source_path} contains {len(concepts)} entries; expected {target_entry_count}."
        )
    dictionary_entries = assign_tokens(concepts)
    language_entries = [
        language_entry_from_dictionary_entry(entry) for entry in dictionary_entries
    ]

    results_dir = root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / csv_filename
    json_path = results_dir / json_filename
    md_path = results_dir / md_filename

    write_language_map_csv(csv_path, language_entries)
    write_language_map_json(json_path, language_entries, source_filename)
    md_path.write_text(language_map_markdown(language_entries), encoding="utf-8")
    validation = validate_language_map_entries(
        language_entries,
        expected_count=target_entry_count,
    )
    return {
        "source_path": source_path,
        "csv_path": csv_path,
        "json_path": json_path,
        "markdown_path": md_path,
        "validation": validation,
    }


def validate_language_map_4000(root: Path) -> dict[str, Any]:
    return validate_language_map_file(
        root=root,
        csv_filename=CSV_FILENAME_4000,
        expected_count=TARGET_ENTRY_COUNT_4000,
        generate_flag="--generate-language-map-4000",
    )


def validate_language_map_8000(root: Path) -> dict[str, Any]:
    return validate_language_map_file(
        root=root,
        csv_filename=CSV_FILENAME_8000,
        expected_count=TARGET_ENTRY_COUNT_8000,
        generate_flag="--generate-language-map-8000",
    )


def validate_language_map_file(
    root: Path,
    csv_filename: str,
    expected_count: int,
    generate_flag: str,
) -> dict[str, Any]:
    csv_path = root / "results" / csv_filename
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{csv_path} does not exist. Run {generate_flag} first."
        )
    return validate_language_map_entries(
        read_language_map_csv(csv_path),
        expected_count=expected_count,
    )


def read_source_concepts(path: Path) -> list[Concept]:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist. Create the source dictionary first.")
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
        writer = csv.DictWriter(handle, fieldnames=LANGUAGE_MAP_FIELDS, lineterminator="\n")
        writer.writeheader()
        for entry in entries:
            writer.writerow(asdict(entry))


def write_language_map_json(
    path: Path,
    entries: list[LanguageMapEntry],
    source_filename: str,
) -> None:
    payload = {
        "name": f"MiniCPL-Ro {len(entries)} compact language map",
        "source": source_filename,
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


def validate_language_map_entries(
    entries: list[LanguageMapEntry],
    expected_count: int = TARGET_ENTRY_COUNT_4000,
) -> dict[str, Any]:
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
    average_limit = 2.25 if expected_count <= TARGET_ENTRY_COUNT_4000 else 3.0
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
            len(entries) == expected_count
            and not duplicates
            and not missing_tokens
            and not human_like
            and max_token_length <= 3
            and average <= average_limit
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
    validation = validate_language_map_entries(entries, expected_count=len(entries))
    lines = [
        f"# MiniCPL-Ro {len(entries)} Compact Language Map",
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
