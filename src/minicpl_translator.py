"""Simple MiniCPL compact-language translator."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


WORD_RE = re.compile(r"[\wăâîșțĂÂÎȘȚ]+", re.UNICODE)


@dataclass(frozen=True)
class TranslatorEntry:
    id: str
    category: str
    ro: str
    en: str
    meaning: str
    compact_token: str


class MiniCPLTranslator:
    def __init__(self, language_map_path: Path) -> None:
        self.language_map_path = language_map_path
        self.entries = read_entries(language_map_path)
        self.token_to_entry = {
            entry.compact_token: entry
            for entry in self.entries
            if entry.compact_token
        }
        self.phrase_to_entry: dict[tuple[str, ...], TranslatorEntry] = {}
        self.lookup_text_to_entries: dict[str, list[TranslatorEntry]] = {}
        self._build_phrase_indexes()

    def human_to_compact(self, text: str) -> str:
        words = normalized_words(text)
        if not words:
            return ""
        output: list[str] = []
        position = 0
        max_phrase_length = max((len(key) for key in self.phrase_to_entry), default=1)
        while position < len(words):
            match = self._longest_phrase_match(words, position, max_phrase_length)
            if match:
                entry, length = match
                output.append(entry.compact_token)
                position += length
                continue
            output.append(f"<UNK:{words[position]}>")
            position += 1
        return " ".join(output)

    def compact_to_human(self, text: str) -> str:
        parts = [part for part in text.split() if part.strip()]
        decoded: list[str] = []
        for part in parts:
            entry = self.token_to_entry.get(part)
            decoded.append(entry.meaning if entry else f"<UNK:{part}>")
        return " | ".join(decoded)

    def phrase_lookup(self, phrase: str) -> TranslatorEntry | None:
        words = tuple(normalized_words(phrase))
        if not words:
            return None
        return self.phrase_to_entry.get(words)

    def fuzzy_lookup(self, query: str, limit: int = 10) -> list[TranslatorEntry]:
        normalized_query = normalize(query)
        if not normalized_query:
            return []
        exact = self.lookup_text_to_entries.get(normalized_query, [])
        results: list[TranslatorEntry] = list(exact)
        seen = {entry.id for entry in results}
        for entry in self.entries:
            haystack = " ".join(
                [
                    normalize(entry.ro),
                    normalize(entry.en),
                    normalize(entry.meaning),
                    entry.compact_token,
                ]
            )
            if normalized_query in haystack and entry.id not in seen:
                results.append(entry)
                seen.add(entry.id)
            if len(results) >= limit:
                break
        return results[:limit]

    def repl(self) -> None:
        print(f"MiniCPL translator map: {self.language_map_path}")
        print("Enter human text to encode.")
        print("Use ':compact TOKENS' to decode compact text.")
        print("Use ':lookup WORD' to search Romanian/English meanings.")
        print("Use ':quit' to exit.")
        while True:
            try:
                line = input("minicpl> ").strip()
            except EOFError:
                print("")
                return
            if not line:
                continue
            if line in {":q", ":quit", "quit", "exit"}:
                return
            if line.startswith(":compact "):
                print(self.compact_to_human(line.removeprefix(":compact ").strip()))
                continue
            if line.startswith(":lookup "):
                query = line.removeprefix(":lookup ").strip()
                matches = self.fuzzy_lookup(query)
                if not matches:
                    print("No matches.")
                    continue
                for entry in matches:
                    print(
                        f"{entry.compact_token}\t{entry.meaning}\t"
                        f"{entry.category}\t{entry.id}"
                    )
                continue
            print(self.human_to_compact(line))

    def _build_phrase_indexes(self) -> None:
        for entry in self.entries:
            for phrase in entry_phrases(entry):
                words = tuple(normalized_words(phrase))
                if not words:
                    continue
                self.phrase_to_entry.setdefault(words, entry)
                self.lookup_text_to_entries.setdefault(" ".join(words), []).append(entry)

    def _longest_phrase_match(
        self,
        words: list[str],
        position: int,
        max_phrase_length: int,
    ) -> tuple[TranslatorEntry, int] | None:
        remaining = len(words) - position
        for length in range(min(max_phrase_length, remaining), 0, -1):
            candidate = tuple(words[position : position + length])
            entry = self.phrase_to_entry.get(candidate)
            if entry:
                return entry, length
        return None


def default_language_map_path(root: Path) -> Path:
    map_8000 = root / "results" / "language_map_8000.csv"
    if map_8000.exists():
        return map_8000
    return root / "results" / "language_map_4000.csv"


def read_entries(path: Path) -> list[TranslatorEntry]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist. Generate or choose a language map first."
        )
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        TranslatorEntry(
            id=row["id"],
            category=row["category"],
            ro=row["ro"],
            en=row["en"],
            meaning=row["meaning"],
            compact_token=row["compact_token"],
        )
        for row in rows
    ]


def entry_phrases(entry: TranslatorEntry) -> set[str]:
    phrases = {entry.ro, entry.en, entry.meaning}
    if "/" in entry.meaning:
        for part in entry.meaning.split("/"):
            phrases.add(part.strip())
    return {phrase for phrase in phrases if phrase}


def normalize(value: str) -> str:
    words = normalized_words(value)
    return " ".join(words)


def normalized_words(value: str) -> list[str]:
    return [match.group(0).lower() for match in WORD_RE.finditer(value)]
