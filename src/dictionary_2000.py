"""Generate and validate compact MiniCPL dictionaries."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


TARGET_ENTRY_COUNT = 2000
TARGET_ENTRY_COUNT_4000 = 4000
SOURCE_FILENAME = "dictionary_2000_source.csv"
CSV_FILENAME = "dictionary_2000.csv"
JSON_FILENAME = "dictionary_2000.json"
MD_FILENAME = "dictionary_2000.md"
SOURCE_FILENAME_4000 = "dictionary_4000_source.csv"
CSV_FILENAME_4000 = "dictionary_4000.csv"
JSON_FILENAME_4000 = "dictionary_4000.json"
MD_FILENAME_4000 = "dictionary_4000.md"

ENTRY_FIELDS = [
    "entry_id",
    "category",
    "ro",
    "en",
    "meaning",
    "token",
    "token_length",
    "rank",
    "source",
    "notes",
]

SOURCE_FIELDS = ["entry_id", "category", "ro", "en", "meaning", "rank", "source", "notes"]

TOKEN_ALPHABET = (
    "0123456789"
    "BCDFGHJKLMNPQRSTVWXYZ"
    "bcdfghjklmnpqrstvwxyz"
    "!#$%&*+./:;=?@^_~"
)
TOKEN_MAX_LENGTH = 3
ULTRA_COMMON_TOKENS = {
    ("eu", "I"): "@",
    ("tu", "you"): "U",
    ("a fi", "to be"): "=",
    ("a avea", "to have"): "H",
    ("a vrea", "to want"): "W",
    ("a avea nevoie", "to need"): "N",
    ("nu", "no/not"): "!",
    ("și", "and"): "&",
    ("sau", "or"): "/",
    ("ce", "what"): "?",
    ("acum", "now"): "T",
    ("apă", "water"): "0",
    ("mâncare", "food"): "F",
    ("ajutor", "help"): "+",
    ("calculator", "computer"): "P",
    ("protocol", "protocol"): "p",
    ("agent", "agent"): "G",
    ("întrebare", "question"): "Q",
    ("răspuns", "answer"): "]",
}

HUMAN_WORDS = {
    "a",
    "am",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "ce",
    "da",
    "de",
    "do",
    "el",
    "en",
    "eu",
    "go",
    "he",
    "hi",
    "i",
    "in",
    "is",
    "it",
    "la",
    "me",
    "my",
    "no",
    "nu",
    "of",
    "on",
    "or",
    "pa",
    "ro",
    "sa",
    "se",
    "she",
    "to",
    "tu",
    "up",
    "us",
    "we",
    "you",
}


@dataclass(frozen=True)
class Concept:
    entry_id: str
    category: str
    ro: str
    en: str
    meaning: str
    rank: int
    source: str
    notes: str = ""


@dataclass(frozen=True)
class DictionaryEntry:
    entry_id: str
    category: str
    ro: str
    en: str
    meaning: str
    token: str
    token_length: int
    rank: int
    source: str
    notes: str = ""


def generate_dictionary_2000(root: Path) -> dict[str, Any]:
    return generate_dictionary(
        root=root,
        target_entry_count=TARGET_ENTRY_COUNT,
        source_filename=SOURCE_FILENAME,
        csv_filename=CSV_FILENAME,
        json_filename=JSON_FILENAME,
        md_filename=MD_FILENAME,
    )


def generate_dictionary_4000(root: Path) -> dict[str, Any]:
    return generate_dictionary(
        root=root,
        target_entry_count=TARGET_ENTRY_COUNT_4000,
        source_filename=SOURCE_FILENAME_4000,
        csv_filename=CSV_FILENAME_4000,
        json_filename=JSON_FILENAME_4000,
        md_filename=MD_FILENAME_4000,
    )


def generate_dictionary(
    root: Path,
    target_entry_count: int,
    source_filename: str,
    csv_filename: str,
    json_filename: str,
    md_filename: str,
) -> dict[str, Any]:
    concepts = build_concepts(root)
    if len(concepts) < target_entry_count:
        raise RuntimeError(
            f"Only {len(concepts)} concepts available; need {target_entry_count}."
        )
    selected = concepts[:target_entry_count]
    entries = assign_tokens(selected)
    data_dir = root / "data"
    results_dir = root / "results"
    data_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    source_path = data_dir / source_filename
    csv_path = results_dir / csv_filename
    json_path = results_dir / json_filename
    md_path = results_dir / md_filename

    write_source_csv(source_path, selected)
    write_entries_csv(csv_path, entries)
    write_entries_json(json_path, entries, target_entry_count)
    md_path.write_text(dictionary_markdown(entries, target_entry_count), encoding="utf-8")
    validation = validate_entries(entries, expected_count=target_entry_count)
    return {
        "source_path": source_path,
        "csv_path": csv_path,
        "json_path": json_path,
        "markdown_path": md_path,
        "validation": validation,
    }


def validate_dictionary_2000(root: Path) -> dict[str, Any]:
    return validate_dictionary_file(
        root=root,
        csv_filename=CSV_FILENAME,
        expected_count=TARGET_ENTRY_COUNT,
    )


def validate_dictionary_4000(root: Path) -> dict[str, Any]:
    return validate_dictionary_file(
        root=root,
        csv_filename=CSV_FILENAME_4000,
        expected_count=TARGET_ENTRY_COUNT_4000,
    )


def validate_dictionary_file(
    root: Path,
    csv_filename: str,
    expected_count: int,
) -> dict[str, Any]:
    csv_path = root / "results" / csv_filename
    if not csv_path.exists():
        flag = csv_filename.replace(".csv", "").replace("_", "-")
        raise FileNotFoundError(f"{csv_path} does not exist. Run --generate-{flag} first.")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    entries = [
        DictionaryEntry(
            entry_id=row["entry_id"],
            category=row["category"],
            ro=row["ro"],
            en=row["en"],
            meaning=row["meaning"],
            token=row["token"],
            token_length=int(row["token_length"] or 0),
            rank=int(row["rank"] or 0),
            source=row["source"],
            notes=row.get("notes", ""),
        )
        for row in rows
    ]
    return validate_entries(entries, expected_count=expected_count)


def build_concepts(root: Path) -> list[Concept]:
    builder = ConceptBuilder()
    builder.add_seed_vocabulary(root / "data" / "seed_vocabulary.csv")
    builder.add_pairs("connectors", CONNECTORS, source="curated_connector")
    builder.add_pairs("negation", NEGATION, source="curated_negation")
    builder.add_pairs("grammar_markers", GRAMMAR_MARKERS, source="curated_grammar")
    builder.add_pairs("requests", REQUESTS, source="curated_request")
    builder.add_pairs("basic_conversation", BASIC_CONVERSATION, source="curated_conversation")
    builder.add_pairs("objects", COMMON_OBJECTS, source="curated_object")
    builder.add_pairs("people", PEOPLE, source="curated_people")
    builder.add_pairs("places", PLACES, source="curated_place")
    builder.add_pairs("verbs", EXTRA_VERBS, source="curated_verb")
    builder.add_pairs("emotions", EXTRA_EMOTIONS, source="curated_emotion")
    builder.add_pairs("time", EXTRA_TIME, source="curated_time")
    builder.add_pairs("actions", EXTRA_ACTIONS, source="curated_action")
    builder.add_pairs("software/project terms", SOFTWARE_TERMS, source="curated_software")
    builder.add_pairs("questions", QUESTION_FORMS, source="curated_question")
    builder.add_pairs("common_phrases", COMMON_PHRASES, source="curated_phrase")
    builder.add_template_entries()
    builder.add_4000_expansion_entries()
    return builder.concepts


def assign_tokens(concepts: list[Concept]) -> list[DictionaryEntry]:
    reserved = set(ULTRA_COMMON_TOKENS.values())
    used: set[str] = set()
    token_iter = token_stream()
    entries: list[DictionaryEntry] = []
    for concept in concepts:
        fixed = ULTRA_COMMON_TOKENS.get((concept.ro, concept.en))
        token = (
            fixed
            if fixed and fixed not in used
            else next_unique_token(token_iter, used | reserved)
        )
        used.add(token)
        entries.append(
            DictionaryEntry(
                entry_id=concept.entry_id,
                category=concept.category,
                ro=concept.ro,
                en=concept.en,
                meaning=concept.meaning,
                token=token,
                token_length=len(token),
                rank=concept.rank,
                source=concept.source,
                notes=concept.notes,
            )
        )
    return entries


def token_stream() -> Iterable[str]:
    for char in TOKEN_ALPHABET:
        if not is_human_language_like_token(char):
            yield char
    for left in TOKEN_ALPHABET:
        for right in TOKEN_ALPHABET:
            token = left + right
            if not is_human_language_like_token(token):
                yield token
    for left in TOKEN_ALPHABET:
        for mid in TOKEN_ALPHABET:
            for right in TOKEN_ALPHABET:
                token = left + mid + right
                if not is_human_language_like_token(token):
                    yield token


def next_unique_token(tokens: Iterable[str], used: set[str]) -> str:
    for token in tokens:
        if token not in used:
            return token
    raise RuntimeError("Token space exhausted.")


class ConceptBuilder:
    def __init__(self) -> None:
        self.concepts: list[Concept] = []
        self._seen: set[str] = set()

    def add_seed_vocabulary(self, path: Path) -> None:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                self.add(
                    category=row.get("category", "seed"),
                    ro=row.get("ro", ""),
                    en=row.get("en", ""),
                    source="seed_vocabulary",
                    entry_id=row.get("concept_id", ""),
                )

    def add_pairs(
        self,
        category: str,
        pairs: list[tuple[str, str]],
        source: str,
    ) -> None:
        for ro, en in pairs:
            self.add(category=category, ro=ro, en=en, source=source)

    def add_template_entries(self) -> None:
        high_value_objects = COMMON_OBJECTS[:90] + SOFTWARE_TERMS[:60] + PLACES[:35]
        useful_verbs = EXTRA_VERBS[:90] + EXTRA_ACTIONS[:50]
        software_targets = SOFTWARE_TERMS[:90]
        people_targets = PEOPLE[:35]
        time_targets = EXTRA_TIME[:40]

        for ro, en in high_value_objects:
            self.add("common_phrases", f"vreau {ro}", f"I want {en}", "template_want")
            self.add("requests", f"am nevoie de {ro}", f"I need {en}", "template_need")
            self.add("questions", f"unde este {ro}?", f"where is {en}?", "template_where")

        for ro, en in useful_verbs:
            self.add("requests", f"poți să {ro}?", f"can you {en}?", "template_can_you")
            self.add("negation", f"nu {ro}", f"do not {en}", "template_negation")
            self.add("actions", f"trebuie să {ro}", f"must {en}", "template_must")

        for ro, en in software_targets:
            self.add("software/project terms", f"deschide {ro}", f"open {en}", "template_open")
            self.add("software/project terms", f"actualizează {ro}", f"update {en}", "template_update")
            self.add("software/project terms", f"șterge {ro}", f"delete {en}", "template_delete")
            self.add("software/project terms", f"verifică {ro}", f"check {en}", "template_check")
            self.add("software/project terms", f"generează {ro}", f"generate {en}", "template_generate")

        for ro, en in people_targets:
            self.add("basic_conversation", f"salut {ro}", f"hello {en}", "template_greeting")
            self.add("requests", f"ajută {ro}", f"help {en}", "template_help_person")

        for ro, en in time_targets:
            self.add("time", f"rulează {ro}", f"run {en}", "template_time_run")
            self.add("time", f"trimite {ro}", f"send {en}", "template_time_send")

        for ro_action, en_action in EXTRA_ACTIONS[:45]:
            for ro_obj, en_obj in SOFTWARE_TERMS[:12]:
                self.add(
                    "software/project terms",
                    f"{ro_action} {ro_obj}",
                    f"{en_action} {en_obj}",
                    "template_action_software",
                )

    def add_4000_expansion_entries(self) -> None:
        pair_groups = [
            ("daily_conversation", DAILY_CONVERSATION_EXTRA, "curated_daily_4000"),
            ("emotions", ADVANCED_EMOTIONS, "curated_emotion_4000"),
            ("adjectives", ADJECTIVES_EXTRA, "curated_adjective_4000"),
            ("places", PLACES_EXTRA, "curated_place_4000"),
            ("objects", OBJECTS_EXTRA, "curated_object_4000"),
            ("school/university words", SCHOOL_UNIVERSITY_TERMS, "curated_school_4000"),
            ("programming/software terms", PROGRAMMING_EXTRA_TERMS, "curated_programming_4000"),
            ("AI/LLM terms", AI_LLM_TERMS, "curated_ai_4000"),
            ("project-management terms", PROJECT_MANAGEMENT_TERMS, "curated_project_4000"),
            ("cybersecurity/Linux terms", CYBER_LINUX_TERMS, "curated_cyber_linux_4000"),
            ("grammar/compression markers", GRAMMAR_COMPRESSION_EXTRA, "curated_grammar_4000"),
        ]
        for category, pairs, source in pair_groups:
            self.add_pairs(category, pairs, source=source)
        self.add_4000_template_entries()

    def add_4000_template_entries(self) -> None:
        explanation_targets = (
            SCHOOL_UNIVERSITY_TERMS[:45]
            + PROGRAMMING_EXTRA_TERMS[:55]
            + AI_LLM_TERMS[:55]
            + CYBER_LINUX_TERMS[:55]
            + PROJECT_MANAGEMENT_TERMS[:45]
        )
        for ro, en in explanation_targets:
            self.add("common_phrases", f"explică {ro}", f"explain {en}", "template_4000_explain")
            self.add("common_phrases", f"rezumă {ro}", f"summarize {en}", "template_4000_summarize")
            self.add("questions", f"cum folosesc {ro}?", f"how do I use {en}?", "template_4000_use_question")
            self.add("requests", f"verifică {ro}", f"check {en}", "template_4000_check")

        project_targets = PROJECT_MANAGEMENT_TERMS[:45] + SOFTWARE_TERMS[:35] + AI_LLM_TERMS[:25]
        for ro, en in project_targets:
            self.add(
                "project-management terms",
                f"prioritizează {ro}",
                f"prioritize {en}",
                "template_4000_prioritize",
            )
            self.add(
                "project-management terms",
                f"blochează {ro}",
                f"block {en}",
                "template_4000_block",
            )
            self.add(
                "project-management terms",
                f"deblochează {ro}",
                f"unblock {en}",
                "template_4000_unblock",
            )

        cyber_targets = CYBER_LINUX_TERMS[:60] + PROGRAMMING_EXTRA_TERMS[:30]
        for ro, en in cyber_targets:
            self.add(
                "cybersecurity/Linux terms",
                f"scanează {ro}",
                f"scan {en}",
                "template_4000_scan",
            )
            self.add(
                "cybersecurity/Linux terms",
                f"protejează {ro}",
                f"protect {en}",
                "template_4000_protect",
            )
            self.add(
                "cybersecurity/Linux terms",
                f"permite {ro}",
                f"allow {en}",
                "template_4000_allow",
            )

        school_targets = SCHOOL_UNIVERSITY_TERMS[:50]
        for ro, en in school_targets:
            self.add("school/university words", f"învață {ro}", f"learn {en}", "template_4000_learn")
            self.add("school/university words", f"predă {ro}", f"teach {en}", "template_4000_teach")
            self.add("school/university words", f"examen la {ro}", f"exam in {en}", "template_4000_exam")

    def add(
        self,
        category: str,
        ro: str,
        en: str,
        source: str,
        entry_id: str = "",
        notes: str = "",
    ) -> None:
        ro = clean_text(ro)
        en = clean_text(en)
        if not ro or not en:
            return
        key = f"{normalize(ro)}|{normalize(en)}"
        if key in self._seen:
            return
        self._seen.add(key)
        next_index = len(self.concepts) + 1
        self.concepts.append(
            Concept(
                entry_id=entry_id or f"d2000_{next_index:04d}",
                category=category,
                ro=ro,
                en=en,
                meaning=f"{ro} / {en}",
                rank=next_index,
                source=source,
                notes=notes,
            )
        )


def write_source_csv(path: Path, concepts: list[Concept]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_FIELDS)
        writer.writeheader()
        for concept in concepts:
            writer.writerow({field: getattr(concept, field) for field in SOURCE_FIELDS})


def write_entries_csv(path: Path, entries: list[DictionaryEntry]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ENTRY_FIELDS)
        writer.writeheader()
        for entry in entries:
            writer.writerow({field: getattr(entry, field) for field in ENTRY_FIELDS})


def write_entries_json(
    path: Path,
    entries: list[DictionaryEntry],
    target_entry_count: int,
) -> None:
    payload = {
        "name": f"MiniCPL-Ro {target_entry_count} compact dictionary",
        "entry_count": len(entries),
        "token_policy": {
            "ultra_common": "1 character",
            "common": "2 characters",
            "fallback": "3 characters only if needed",
            "alphabet": TOKEN_ALPHABET,
            "duplicates": "not allowed unless explicitly documented; generator emits unique tokens",
        },
        "entries": [asdict(entry) for entry in entries],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def dictionary_markdown(entries: list[DictionaryEntry], expected_count: int) -> str:
    validation = validate_entries(entries, expected_count=expected_count)
    lines = [
        f"# MiniCPL-Ro {expected_count} Compact Dictionary",
        "",
        f"Entries: `{validation['total_entries']}`",
        f"Average token length: `{validation['average_token_length']}`",
        f"Max token length: `{validation['max_token_length']}`",
        f"Duplicate tokens: `{validation['duplicate_token_count']}`",
        f"Human-language-like tokens: `{validation['human_language_like_token_count']}`",
        "",
        "## Category Coverage",
        "",
        "| Category | Entries |",
        "|---|---:|",
    ]
    for category, count in sorted(validation["category_coverage"].items()):
        lines.append(f"| {escape_table(category)} | {count} |")

    grouped: dict[str, list[DictionaryEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.category, []).append(entry)

    for category in sorted(grouped):
        lines.extend(
            [
                "",
                f"## {category}",
                "",
                "| Rank | Romanian | English | Token | Source |",
                "|---:|---|---|---:|---|",
            ]
        )
        for entry in grouped[category]:
            lines.append(
                f"| {entry.rank} | {escape_table(entry.ro)} | {escape_table(entry.en)} | "
                f"`{escape_table(entry.token)}` | {escape_table(entry.source)} |"
            )
    return "\n".join(lines) + "\n"


def validate_entries(
    entries: list[DictionaryEntry],
    expected_count: int = TARGET_ENTRY_COUNT,
) -> dict[str, Any]:
    token_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    missing_tokens: list[dict[str, str]] = []
    human_like: list[dict[str, str]] = []
    max_token_length = 0
    total_token_length = 0

    for entry in entries:
        token_counts[entry.token] = token_counts.get(entry.token, 0) + 1
        category_counts[entry.category] = category_counts.get(entry.category, 0) + 1
        max_token_length = max(max_token_length, len(entry.token))
        total_token_length += len(entry.token)
        if not entry.token:
            missing_tokens.append(asdict(entry))
        if is_human_language_like_token(entry.token) or token_matches_meaning(entry):
            human_like.append(asdict(entry))

    duplicates = {
        token: count
        for token, count in token_counts.items()
        if token and count > 1
    }
    average = round(total_token_length / len(entries), 4) if entries else 0.0
    return {
        "total_entries": len(entries),
        "duplicate_tokens": duplicates,
        "duplicate_token_count": len(duplicates),
        "average_token_length": average,
        "max_token_length": max_token_length,
        "category_coverage": dict(sorted(category_counts.items())),
        "human_language_like_tokens": human_like[:50],
        "human_language_like_token_count": len(human_like),
        "entries_without_compact_tokens": missing_tokens,
        "entries_without_compact_tokens_count": len(missing_tokens),
        "expected_entries": expected_count,
        "valid": (
            len(entries) == expected_count
            and not duplicates
            and not missing_tokens
            and max_token_length <= TOKEN_MAX_LENGTH
            and average <= 2.25
        ),
    }


def validation_report(validation: dict[str, Any]) -> str:
    lines = [
        f"Total entries: {validation['total_entries']}",
        f"Duplicate tokens: {validation['duplicate_token_count']}",
        f"Average token length: {validation['average_token_length']}",
        f"Max token length: {validation['max_token_length']}",
        f"Human-language-like tokens: {validation['human_language_like_token_count']}",
        f"Entries without compact tokens: {validation['entries_without_compact_tokens_count']}",
        "Category coverage:",
    ]
    for category, count in validation["category_coverage"].items():
        lines.append(f"  - {category}: {count}")
    if validation["duplicate_tokens"]:
        lines.append("Duplicate token details:")
        for token, count in validation["duplicate_tokens"].items():
            lines.append(f"  - {token}: {count}")
    if validation["human_language_like_tokens"]:
        lines.append("Human-language-like token examples:")
        for item in validation["human_language_like_tokens"][:10]:
            lines.append(f"  - {item['meaning']} = {item['token']}")
    lines.append(f"Valid: {validation['valid']}")
    return "\n".join(lines)


def is_human_language_like_token(token: str) -> bool:
    lowered = token.lower()
    if lowered in HUMAN_WORDS:
        return True
    if len(token) >= 3 and token.isalpha():
        return True
    return bool(re.search(r"[aeiouăâîșțAEIOUĂÂÎȘȚ]", token) and len(token) >= 2 and token.isalpha())


def token_matches_meaning(entry: DictionaryEntry) -> bool:
    lowered = entry.token.lower()
    if len(lowered) <= 1:
        return False
    ro_words = set(re.findall(r"[a-zăâîșț]+", entry.ro.lower()))
    en_words = set(re.findall(r"[a-z]+", entry.en.lower()))
    return lowered in ro_words or lowered in en_words


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def normalize(value: str) -> str:
    return clean_text(value).lower()


def escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


CONNECTORS = [
    ("și", "and"),
    ("sau", "or"),
    ("dar", "but"),
    ("însă", "however"),
    ("deci", "therefore"),
    ("pentru că", "because"),
    ("fiindcă", "since"),
    ("dacă", "if"),
    ("atunci", "then"),
    ("altfel", "otherwise"),
    ("când", "when"),
    ("în timp ce", "while"),
    ("după ce", "after"),
    ("înainte să", "before"),
    ("cu", "with"),
    ("fără", "without"),
    ("prin", "through"),
    ("între", "between"),
    ("peste", "over"),
    ("sub", "under"),
    ("lângă", "near"),
    ("în", "in"),
    ("pe", "on"),
    ("la", "at"),
    ("din", "from"),
    ("către", "toward"),
    ("despre", "about"),
    ("pentru", "for"),
    ("ca", "as"),
    ("precum", "like"),
    ("nici", "nor"),
    ("totuși", "still"),
    ("apoi", "next"),
    ("întâi", "first"),
    ("în final", "finally"),
    ("de asemenea", "also"),
    ("mai ales", "especially"),
    ("în schimb", "instead"),
    ("chiar dacă", "even if"),
    ("numai dacă", "only if"),
]

NEGATION = [
    ("nu", "no/not"),
    ("niciodată", "never"),
    ("nimic", "nothing"),
    ("nimeni", "nobody"),
    ("niciunul", "none"),
    ("fără rezultat", "no result"),
    ("nu pot", "cannot"),
    ("nu vreau", "do not want"),
    ("nu am nevoie", "do not need"),
    ("nu este", "is not"),
    ("nu există", "does not exist"),
    ("nu găsesc", "do not find"),
    ("nu funcționează", "does not work"),
    ("nu înțeleg", "do not understand"),
    ("nu știu", "do not know"),
    ("nu încă", "not yet"),
    ("nu acum", "not now"),
    ("nu aici", "not here"),
    ("nu acolo", "not there"),
    ("greșit", "wrong"),
]

GRAMMAR_MARKERS = [
    ("subiect", "subject"),
    ("obiect", "object"),
    ("verb", "verb"),
    ("nume", "noun"),
    ("adjectiv", "adjective"),
    ("adverb", "adverb"),
    ("plural", "plural"),
    ("singular", "singular"),
    ("trecut", "past"),
    ("prezent", "present"),
    ("viitor", "future"),
    ("condițional", "conditional"),
    ("imperativ", "imperative"),
    ("întrebare", "question"),
    ("răspuns", "answer"),
    ("negație", "negation"),
    ("afirmație", "affirmation"),
    ("agent", "agent"),
    ("pacient", "patient"),
    ("loc", "location"),
    ("timp", "time"),
    ("cauză", "cause"),
    ("scop", "purpose"),
    ("mod", "manner"),
    ("cantitate", "quantity"),
    ("calitate", "quality"),
    ("definit", "definite"),
    ("nedefinit", "indefinite"),
    ("comparativ", "comparative"),
    ("superlativ", "superlative"),
    ("posesiv", "possessive"),
    ("reflexiv", "reflexive"),
    ("reciproc", "reciprocal"),
    ("listă", "list"),
    ("grup", "group"),
    ("relație", "relation"),
    ("atribut", "attribute"),
    ("valoare", "value"),
    ("cheie", "key"),
    ("cod", "code"),
]

REQUESTS = [
    ("te rog", "please"),
    ("ajută-mă", "help me"),
    ("poți să ajuți?", "can you help?"),
    ("am nevoie de ajutor", "I need help"),
    ("arată-mi", "show me"),
    ("spune-mi", "tell me"),
    ("explică-mi", "explain to me"),
    ("trimite-mi", "send me"),
    ("dă-mi", "give me"),
    ("caută pentru mine", "search for me"),
    ("verifică pentru mine", "check for me"),
    ("fă asta", "do this"),
    ("continuă", "continue"),
    ("oprește", "stop"),
    ("începe", "start"),
    ("repetă", "repeat"),
    ("scrie asta", "write this"),
    ("citește asta", "read this"),
    ("salvează asta", "save this"),
    ("deschide asta", "open this"),
]

BASIC_CONVERSATION = [
    ("salut", "hello"),
    ("bună", "hi"),
    ("ce faci?", "how are you?"),
    ("sunt bine", "I am fine"),
    ("mulțumesc", "thank you"),
    ("cu plăcere", "you are welcome"),
    ("scuze", "sorry"),
    ("nu-i nimic", "it is okay"),
    ("da", "yes"),
    ("nu", "no"),
    ("poate", "maybe"),
    ("sigur", "sure"),
    ("bine", "okay"),
    ("gata", "done"),
    ("înțeleg", "I understand"),
    ("nu înțeleg", "I do not understand"),
    ("mai spune", "say more"),
    ("mai scurt", "shorter"),
    ("mai clar", "clearer"),
    ("foarte bine", "very good"),
]

COMMON_OBJECTS = [
    ("apă", "water"),
    ("mâncare", "food"),
    ("pâine", "bread"),
    ("cafea", "coffee"),
    ("ceai", "tea"),
    ("lapte", "milk"),
    ("ou", "egg"),
    ("carne", "meat"),
    ("fruct", "fruit"),
    ("legumă", "vegetable"),
    ("măr", "apple"),
    ("banană", "banana"),
    ("orez", "rice"),
    ("supă", "soup"),
    ("sare", "salt"),
    ("zahăr", "sugar"),
    ("farfurie", "plate"),
    ("pahar", "glass"),
    ("sticlă", "bottle"),
    ("casă", "house"),
    ("cameră", "room"),
    ("ușă", "door"),
    ("fereastră", "window"),
    ("masă", "table"),
    ("scaun", "chair"),
    ("pat", "bed"),
    ("lampă", "lamp"),
    ("cheie", "key"),
    ("geantă", "bag"),
    ("carte", "book"),
    ("hârtie", "paper"),
    ("stilou", "pen"),
    ("creion", "pencil"),
    ("telefon", "phone"),
    ("calculator", "computer"),
    ("ecran", "screen"),
    ("tastatură", "keyboard"),
    ("mouse", "mouse"),
    ("cablu", "cable"),
    ("baterie", "battery"),
    ("mașină", "car"),
    ("autobuz", "bus"),
    ("tren", "train"),
    ("bicicletă", "bicycle"),
    ("bilet", "ticket"),
    ("hartă", "map"),
    ("drum", "road"),
    ("stradă", "street"),
    ("pod", "bridge"),
    ("bani", "money"),
    ("card", "card"),
    ("factură", "bill"),
    ("preț", "price"),
    ("magazin", "shop"),
    ("medicament", "medicine"),
    ("doctor", "doctor"),
    ("spital", "hospital"),
    ("problemă", "problem"),
    ("soluție", "solution"),
    ("idee", "idea"),
    ("plan", "plan"),
    ("listă", "list"),
    ("mesaj", "message"),
    ("imagine", "image"),
    ("sunet", "sound"),
    ("video", "video"),
    ("fișier", "file"),
    ("dosar", "folder"),
    ("parolă", "password"),
    ("cont", "account"),
    ("nume", "name"),
    ("număr", "number"),
    ("adresă", "address"),
    ("limbaj", "language"),
    ("simbol", "symbol"),
    ("regulă", "rule"),
    ("exemplu", "example"),
    ("raport", "report"),
    ("proiect", "project"),
    ("experiment", "experiment"),
    ("rezultat", "result"),
    ("date", "data"),
    ("text", "text"),
    ("cod", "code"),
    ("token", "token"),
    ("dicționar", "dictionary"),
    ("model", "model"),
    ("agent", "agent"),
    ("prompt", "prompt"),
    ("răspuns", "response"),
    ("jurnal", "log"),
    ("transcriere", "transcript"),
    ("metrică", "metric"),
    ("compresie", "compression"),
    ("eroare", "error"),
    ("test", "test"),
]

PEOPLE = [
    ("om", "person"),
    ("femeie", "woman"),
    ("bărbat", "man"),
    ("copil", "child"),
    ("prieten", "friend"),
    ("familie", "family"),
    ("mamă", "mother"),
    ("tată", "father"),
    ("soră", "sister"),
    ("frate", "brother"),
    ("profesor", "teacher"),
    ("student", "student"),
    ("client", "client"),
    ("utilizator", "user"),
    ("operator", "operator"),
    ("administrator", "administrator"),
    ("dezvoltator", "developer"),
    ("cercetător", "researcher"),
    ("autor", "author"),
    ("cititor", "reader"),
    ("vorbitor", "speaker"),
    ("ascultător", "listener"),
    ("expeditor", "sender"),
    ("destinatar", "receiver"),
    ("echipă", "team"),
    ("grup", "group"),
    ("lider", "leader"),
    ("membru", "member"),
    ("oaspete", "guest"),
    ("gazdă", "host"),
    ("partener", "partner"),
    ("coleg", "colleague"),
    ("șef", "boss"),
    ("asistent", "assistant"),
    ("agent local", "local agent"),
]

PLACES = [
    ("aici", "here"),
    ("acolo", "there"),
    ("acasă", "home"),
    ("birou", "office"),
    ("școală", "school"),
    ("oraș", "city"),
    ("sat", "village"),
    ("țară", "country"),
    ("lume", "world"),
    ("internet", "internet"),
    ("server", "server"),
    ("browser", "browser"),
    ("terminal", "terminal"),
    ("folder de lucru", "workspace"),
    ("repozitoriu", "repository"),
    ("ramură", "branch"),
    ("director", "directory"),
    ("cale", "path"),
    ("pagină", "page"),
    ("fereastră", "window"),
    ("ecran principal", "main screen"),
    ("meniu", "menu"),
    ("panou", "panel"),
    ("tabel", "table"),
    ("listă", "list"),
    ("formular", "form"),
    ("bază de date", "database"),
    ("rețea", "network"),
    ("nor", "cloud"),
    ("sistem", "system"),
    ("proces", "process"),
    ("memorie", "memory"),
    ("disc", "disk"),
    ("coadă", "queue"),
    ("stivă", "stack"),
]

EXTRA_VERBS = [
    ("a vedea", "to see"),
    ("a ști", "to know"),
    ("a spune", "to say"),
    ("a întreba", "to ask"),
    ("a răspunde", "to answer"),
    ("a scrie", "to write"),
    ("a citi", "to read"),
    ("a crea", "to create"),
    ("a șterge", "to delete"),
    ("a salva", "to save"),
    ("a încărca", "to load"),
    ("a trimite", "to send"),
    ("a primi", "to receive"),
    ("a explica", "to explain"),
    ("a comprima", "to compress"),
    ("a codifica", "to encode"),
    ("a decodifica", "to decode"),
    ("a traduce", "to translate"),
    ("a testa", "to test"),
    ("a verifica", "to check"),
    ("a repara", "to fix"),
    ("a porni", "to start"),
    ("a opri", "to stop"),
    ("a continua", "to continue"),
    ("a repeta", "to repeat"),
    ("a schimba", "to change"),
    ("a alege", "to choose"),
    ("a compara", "to compare"),
    ("a măsura", "to measure"),
    ("a reduce", "to reduce"),
    ("a scurta", "to shorten"),
    ("a mări", "to increase"),
    ("a micșora", "to decrease"),
    ("a păstra", "to preserve"),
    ("a pierde", "to lose"),
    ("a câștiga", "to gain"),
    ("a folosi", "to use"),
    ("a învăța", "to learn"),
    ("a observa", "to observe"),
    ("a nota", "to record"),
    ("a calcula", "to calculate"),
    ("a rula", "to run"),
    ("a executa", "to execute"),
    ("a deschide", "to open"),
    ("a închide", "to close"),
    ("a copia", "to copy"),
    ("a lipi", "to paste"),
    ("a muta", "to move"),
    ("a îmbina", "to merge"),
    ("a împărți", "to split"),
    ("a sorta", "to sort"),
    ("a filtra", "to filter"),
    ("a căuta", "to search"),
    ("a găsi", "to find"),
    ("a construi", "to build"),
    ("a proiecta", "to design"),
    ("a planifica", "to plan"),
    ("a raporta", "to report"),
    ("a evalua", "to evaluate"),
    ("a valida", "to validate"),
    ("a genera", "to generate"),
    ("a exporta", "to export"),
    ("a importa", "to import"),
    ("a actualiza", "to update"),
    ("a sincroniza", "to sync"),
    ("a instala", "to install"),
    ("a porni din nou", "to restart"),
    ("a asculta", "to listen"),
    ("a vorbi", "to speak"),
    ("a aștepta", "to wait"),
    ("a termina", "to finish"),
    ("a începe", "to begin"),
    ("a permite", "to allow"),
    ("a interzice", "to forbid"),
    ("a accepta", "to accept"),
    ("a respinge", "to reject"),
    ("a confirma", "to confirm"),
    ("a nega", "to deny"),
    ("a conecta", "to connect"),
    ("a deconecta", "to disconnect"),
    ("a proteja", "to protect"),
    ("a partaja", "to share"),
    ("a curăța", "to clean"),
    ("a descrie", "to describe"),
    ("a rezuma", "to summarize"),
    ("a detalia", "to detail"),
    ("a prioritiza", "to prioritize"),
    ("a clasa", "to rank"),
    ("a eticheta", "to label"),
    ("a grupa", "to group"),
    ("a lega", "to link"),
    ("a debloca", "to unlock"),
]

EXTRA_EMOTIONS = [
    ("fericit", "happy"),
    ("trist", "sad"),
    ("obosit", "tired"),
    ("curios", "curious"),
    ("confuz", "confused"),
    ("calm", "calm"),
    ("îngrijorat", "worried"),
    ("furios", "angry"),
    ("uimit", "surprised"),
    ("interesat", "interested"),
    ("plictisit", "bored"),
    ("mulțumit", "satisfied"),
    ("nesigur", "uncertain"),
    ("motivat", "motivated"),
    ("atent", "focused"),
    ("grăbit", "rushed"),
    ("relaxat", "relaxed"),
    ("stresat", "stressed"),
    ("optimist", "optimistic"),
    ("pesimist", "pessimistic"),
]

EXTRA_TIME = [
    ("acum", "now"),
    ("azi", "today"),
    ("mâine", "tomorrow"),
    ("ieri", "yesterday"),
    ("dimineață", "morning"),
    ("seară", "evening"),
    ("noapte", "night"),
    ("oră", "hour"),
    ("minut", "minute"),
    ("secundă", "second"),
    ("săptămână", "week"),
    ("lună", "month"),
    ("an", "year"),
    ("devreme", "early"),
    ("târziu", "late"),
    ("înainte", "before"),
    ("după", "after"),
    ("repede", "fast"),
    ("lent", "slow"),
    ("final", "end"),
    ("în curând", "soon"),
    ("mai târziu", "later"),
    ("imediat", "immediately"),
    ("mereu", "always"),
    ("des", "often"),
    ("rar", "rarely"),
    ("uneori", "sometimes"),
    ("niciodată", "never"),
    ("data viitoare", "next time"),
    ("ultima dată", "last time"),
    ("în fiecare zi", "every day"),
    ("în fiecare săptămână", "every week"),
    ("în fiecare lună", "every month"),
    ("în trecut", "in the past"),
    ("în viitor", "in the future"),
    ("termen limită", "deadline"),
    ("durată", "duration"),
    ("interval", "interval"),
    ("moment", "moment"),
    ("program", "schedule"),
]

EXTRA_ACTIONS = [
    ("pornește", "start"),
    ("oprește", "stop"),
    ("rulează", "run"),
    ("testează", "test"),
    ("repară", "fix"),
    ("analizează", "analyze"),
    ("compară", "compare"),
    ("alege", "choose"),
    ("redu", "reduce"),
    ("scurtează", "shorten"),
    ("păstrează", "preserve"),
    ("schimbă", "change"),
    ("mută", "move"),
    ("copiază", "copy"),
    ("lipește", "paste"),
    ("caută", "search"),
    ("găsește", "find"),
    ("deschide", "open"),
    ("închide", "close"),
    ("actualizează", "update"),
    ("îmbină", "merge"),
    ("împarte", "split"),
    ("sortează", "sort"),
    ("filtrează", "filter"),
    ("validează", "validate"),
    ("exportă", "export"),
    ("importă", "import"),
    ("generează", "generate"),
    ("trimite", "send"),
    ("primește", "receive"),
    ("notează", "record"),
    ("salvează", "save"),
    ("încarcă", "load"),
    ("șterge", "delete"),
    ("curăță", "clean"),
    ("depanare", "debug"),
    ("compilează", "compile"),
    ("instalează", "install"),
    ("sincronizează", "sync"),
    ("publică", "publish"),
    ("revizuiește", "review"),
    ("măsoară", "measure"),
    ("optimizează", "optimize"),
    ("observă", "observe"),
    ("documentează", "document"),
    ("etichetează", "label"),
    ("prioritizează", "prioritize"),
    ("grupează", "group"),
    ("listează", "list"),
    ("afișează", "display"),
]

SOFTWARE_TERMS = [
    ("fișier", "file"),
    ("dosar", "folder"),
    ("cale", "path"),
    ("linie", "line"),
    ("coloană", "column"),
    ("funcție", "function"),
    ("clasă", "class"),
    ("modul", "module"),
    ("pachet", "package"),
    ("bibliotecă", "library"),
    ("script", "script"),
    ("comandă", "command"),
    ("argument", "argument"),
    ("opțiune", "option"),
    ("configurație", "configuration"),
    ("variabilă", "variable"),
    ("valoare", "value"),
    ("cheie", "key"),
    ("obiect", "object"),
    ("listă", "list"),
    ("dicționar", "dictionary"),
    ("șir", "string"),
    ("număr întreg", "integer"),
    ("boolean", "boolean"),
    ("eroare", "error"),
    ("excepție", "exception"),
    ("jurnal", "log"),
    ("test", "test"),
    ("validare", "validation"),
    ("rezultat", "result"),
    ("raport", "report"),
    ("model", "model"),
    ("agent", "agent"),
    ("prompt", "prompt"),
    ("răspuns", "response"),
    ("token", "token"),
    ("protocol", "protocol"),
    ("stare", "state"),
    ("rundă", "round"),
    ("metrică", "metric"),
    ("scor", "score"),
    ("recompensă", "reward"),
    ("compresie", "compression"),
    ("decodare", "decoding"),
    ("codificare", "encoding"),
    ("lexicon", "lexicon"),
    ("gramatică", "grammar"),
    ("simbol", "symbol"),
    ("hartă de tokenuri", "token map"),
    ("dicționar compact", "compact dictionary"),
    ("intrare", "entry"),
    ("ieșire", "output"),
    ("intrare utilizator", "user input"),
    ("interfață", "interface"),
    ("terminal", "terminal"),
    ("proces", "process"),
    ("thread", "thread"),
    ("server", "server"),
    ("client", "client"),
    ("api", "api"),
    ("cerere", "request"),
    ("răspuns api", "api response"),
    ("json", "json"),
    ("csv", "csv"),
    ("markdown", "markdown"),
    ("repozitoriu", "repository"),
    ("ramură", "branch"),
    ("commit", "commit"),
    ("diferență", "diff"),
    ("patch", "patch"),
    ("cerere pull", "pull request"),
    ("revizuire", "review"),
    ("documentație", "documentation"),
    ("dependință", "dependency"),
    ("mediu", "environment"),
    ("sandbox", "sandbox"),
    ("permisiune", "permission"),
    ("cache", "cache"),
    ("memorie", "memory"),
    ("bază de date", "database"),
    ("schemă", "schema"),
    ("tabel", "table"),
    ("rând", "row"),
    ("coloană de date", "data column"),
    ("index", "index"),
    ("căutare", "search"),
    ("filtru", "filter"),
    ("sortare", "sort"),
    ("îmbinare", "merge"),
    ("sincronizare", "sync"),
]

QUESTION_FORMS = [
    ("ce", "what"),
    ("cine", "who"),
    ("unde", "where"),
    ("când", "when"),
    ("de ce", "why"),
    ("cum", "how"),
    ("cât", "how much"),
    ("care", "which"),
    ("este?", "is it?"),
    ("poți?", "can you?"),
    ("ai?", "do you have?"),
    ("vrei?", "do you want?"),
    ("înțelegi?", "do you understand?"),
    ("funcționează?", "does it work?"),
    ("continuăm?", "do we continue?"),
    ("ce înseamnă?", "what does it mean?"),
    ("unde este fișierul?", "where is the file?"),
    ("cât de scurt?", "how short?"),
    ("ce token folosim?", "what token do we use?"),
    ("care este scorul?", "what is the score?"),
]

COMMON_PHRASES = [
    ("vreau apă", "I want water"),
    ("vreau mâncare", "I want food"),
    ("am nevoie de ajutor", "I need help"),
    ("am nevoie de calculator", "I need computer"),
    ("poți să mă ajuți?", "can you help me?"),
    ("explică proiectul", "explain the project"),
    ("comprimă sensul", "compress the meaning"),
    ("inventează cod scurt", "invent short code"),
    ("actualizează harta", "update the map"),
    ("continuă experimentul", "continue the experiment"),
    ("salvează raportul", "save the report"),
    ("exportă dicționarul", "export the dictionary"),
    ("verifică tokenurile", "check the tokens"),
    ("evită duplicatele", "avoid duplicates"),
    ("folosește protocolul", "use the protocol"),
    ("creează token nou", "create new token"),
    ("evoluează token vechi", "evolve old token"),
    ("arată rezultatul", "show the result"),
    ("trimite mesajul", "send the message"),
    ("primește răspunsul", "receive the answer"),
]

DAILY_CONVERSATION_EXTRA = [
    ("bună ziua", "good day"),
    ("ne auzim mai târziu", "talk later"),
    ("revin imediat", "I will be right back"),
    ("am o întrebare", "I have a question"),
    ("nu sunt sigur", "I am not sure"),
    ("ai dreptate", "you are right"),
    ("nu contează", "never mind"),
    ("se poate", "it is possible"),
    ("nu se poate", "it is not possible"),
    ("am terminat", "I finished"),
    ("mai încerc", "I will try again"),
    ("trimite-mi detalii", "send me details"),
    ("spune-mi pașii", "tell me the steps"),
    ("arată exemplul", "show the example"),
    ("fără grabă", "no rush"),
    ("este urgent", "it is urgent"),
    ("sunt disponibil", "I am available"),
    ("nu sunt disponibil", "I am not available"),
    ("am uitat", "I forgot"),
    ("îmi amintesc", "I remember"),
    ("nu am timp", "I have no time"),
    ("am timp", "I have time"),
    ("este clar", "it is clear"),
    ("nu este clar", "it is not clear"),
    ("hai să continuăm", "let us continue"),
    ("hai să oprim", "let us stop"),
    ("confirm primirea", "confirm receipt"),
    ("aștept răspunsul", "I await the response"),
    ("verific acum", "checking now"),
    ("am verificat", "I checked"),
]

ADVANCED_EMOTIONS = [
    ("încrezător", "confident"),
    ("rușinat", "ashamed"),
    ("recunoscător", "grateful"),
    ("dezamăgit", "disappointed"),
    ("încântat", "delighted"),
    ("speriat", "afraid"),
    ("frustrat", "frustrated"),
    ("nerăbdător", "impatient"),
    ("răbdător", "patient"),
    ("hotărât", "determined"),
    ("ezitant", "hesitant"),
    ("sceptic", "skeptical"),
    ("încurajat", "encouraged"),
    ("descurajat", "discouraged"),
    ("ușurat", "relieved"),
    ("tensionat", "tense"),
    ("sigur pe sine", "self assured"),
    ("copleșit", "overwhelmed"),
    ("inspirat", "inspired"),
    ("epuizat", "exhausted"),
    ("neliniștit", "uneasy"),
    ("mulțumit de rezultat", "happy with result"),
    ("nemulțumit de rezultat", "unhappy with result"),
    ("dornic să învăț", "eager to learn"),
    ("prudent", "cautious"),
]

ADJECTIVES_EXTRA = [
    ("mic", "small"),
    ("mare", "large"),
    ("scurt", "short"),
    ("lung", "long"),
    ("nou", "new"),
    ("vechi", "old"),
    ("rapid", "quick"),
    ("încet", "slow"),
    ("simplu", "simple"),
    ("complex", "complex"),
    ("clar", "clear"),
    ("neclar", "unclear"),
    ("sigur", "safe"),
    ("nesigur", "unsafe"),
    ("util", "useful"),
    ("inutil", "useless"),
    ("corect", "correct"),
    ("incorect", "incorrect"),
    ("complet", "complete"),
    ("incomplet", "incomplete"),
    ("stabil", "stable"),
    ("instabil", "unstable"),
    ("ieftin", "cheap"),
    ("scump", "expensive"),
    ("ușor", "easy"),
    ("greu", "hard"),
    ("vizibil", "visible"),
    ("ascuns", "hidden"),
    ("activ", "active"),
    ("inactiv", "inactive"),
    ("public", "public"),
    ("privat", "private"),
    ("automat", "automatic"),
    ("manual", "manual"),
    ("sincron", "synchronous"),
    ("asincron", "asynchronous"),
    ("local", "local"),
    ("global", "global"),
    ("temporar", "temporary"),
    ("permanent", "permanent"),
    ("critic", "critical"),
    ("opțional", "optional"),
    ("obligatoriu", "required"),
    ("valid", "valid"),
    ("invalid", "invalid"),
    ("compact", "compact"),
    ("redundant", "redundant"),
    ("ambiguu", "ambiguous"),
    ("precis", "precise"),
    ("aproximativ", "approximate"),
]

PLACES_EXTRA = [
    ("sală de clasă", "classroom"),
    ("laborator", "laboratory"),
    ("bibliotecă", "library"),
    ("campus", "campus"),
    ("amfiteatru", "lecture hall"),
    ("secretariat", "administration office"),
    ("cantină", "cafeteria"),
    ("cămin", "dormitory"),
    ("sală de ședințe", "meeting room"),
    ("centru de date", "data center"),
    ("mașină virtuală", "virtual machine"),
    ("container", "container"),
    ("nod", "node"),
    ("cluster", "cluster"),
    ("depozit de cod", "code repository"),
    ("registru", "registry"),
    ("canal", "channel"),
    ("spațiu de nume", "namespace"),
    ("mediu de test", "test environment"),
    ("mediu de producție", "production environment"),
    ("zonă sigură", "safe zone"),
    ("zonă izolată", "isolated zone"),
    ("subrețea", "subnet"),
    ("gateway", "gateway"),
    ("punct final", "endpoint"),
]

OBJECTS_EXTRA = [
    ("caiet", "notebook"),
    ("manual", "textbook"),
    ("marker", "marker"),
    ("tablă", "board"),
    ("proiector", "projector"),
    ("rucsac", "backpack"),
    ("formular de înscriere", "enrollment form"),
    ("legitimație", "identity card"),
    ("certificat", "certificate"),
    ("diplomă", "diploma"),
    ("grafic", "chart"),
    ("diagramă", "diagram"),
    ("matrice", "matrix"),
    ("vector", "vector"),
    ("set de date", "dataset"),
    ("model de date", "data model"),
    ("cheie api", "api key"),
    ("token de acces", "access token"),
    ("parolă temporară", "temporary password"),
    ("copie de rezervă", "backup"),
    ("arhivă", "archive"),
    ("imprimantă", "printer"),
    ("router", "router"),
    ("comutator de rețea", "network switch"),
    ("senzor", "sensor"),
    ("jurnal de sistem", "system log"),
    ("fișier de configurare", "configuration file"),
    ("imagine container", "container image"),
    ("cheie ssh", "ssh key"),
    ("certificat tls", "tls certificate"),
]

SCHOOL_UNIVERSITY_TERMS = [
    ("lecție", "lesson"),
    ("curs", "course"),
    ("seminar", "seminar"),
    ("laborator didactic", "teaching lab"),
    ("temă", "homework"),
    ("proiect de curs", "course project"),
    ("examen", "exam"),
    ("test grilă", "quiz"),
    ("notă", "grade"),
    ("credit", "credit"),
    ("profesor universitar", "professor"),
    ("asistent universitar", "teaching assistant"),
    ("student masterand", "graduate student"),
    ("student doctorand", "doctoral student"),
    ("programă", "syllabus"),
    ("bibliografie", "bibliography"),
    ("lucrare", "paper"),
    ("teză", "thesis"),
    ("disertație", "dissertation"),
    ("prezentare", "presentation"),
    ("absență", "absence"),
    ("prezență", "attendance"),
    ("orar", "timetable"),
    ("sesiune", "exam session"),
    ("admitere", "admission"),
    ("înscriere", "enrollment"),
    ("bursă", "scholarship"),
    ("facultate", "faculty"),
    ("departament", "department"),
    ("disciplină", "subject"),
    ("matematică", "mathematics"),
    ("informatică", "computer science"),
    ("fizică", "physics"),
    ("chimie", "chemistry"),
    ("biologie", "biology"),
    ("istorie", "history"),
    ("lingvistică", "linguistics"),
    ("logică", "logic"),
    ("statistică", "statistics"),
    ("algoritmi", "algorithms"),
    ("structuri de date", "data structures"),
    ("baze de date", "databases"),
    ("sisteme de operare", "operating systems"),
    ("rețele de calculatoare", "computer networks"),
    ("inginerie software", "software engineering"),
    ("inteligență artificială", "artificial intelligence"),
    ("învățare automată", "machine learning"),
    ("etică academică", "academic ethics"),
    ("plagiat", "plagiarism"),
    ("recenzie academică", "academic review"),
]

PROGRAMMING_EXTRA_TERMS = [
    ("tip de date", "data type"),
    ("operator", "operator"),
    ("expresie", "expression"),
    ("instrucțiune", "statement"),
    ("buclă", "loop"),
    ("condiție", "condition"),
    ("apel de funcție", "function call"),
    ("parametru", "parameter"),
    ("valoare returnată", "return value"),
    ("stivă de apeluri", "call stack"),
    ("heap", "heap"),
    ("pointer", "pointer"),
    ("referință", "reference"),
    ("interfață api", "api interface"),
    ("endpoint api", "api endpoint"),
    ("serializare", "serialization"),
    ("deserializare", "deserialization"),
    ("parser", "parser"),
    ("compilator", "compiler"),
    ("interpretor", "interpreter"),
    ("runtime", "runtime"),
    ("thread pool", "thread pool"),
    ("blocare", "lock"),
    ("semafor", "semaphore"),
    ("tranzacție", "transaction"),
    ("migrare", "migration"),
    ("indexare", "indexing"),
    ("interogare", "query"),
    ("schemă json", "json schema"),
    ("test unitar", "unit test"),
    ("test de integrare", "integration test"),
    ("test end-to-end", "end to end test"),
    ("acoperire de test", "test coverage"),
    ("stub", "stub"),
    ("mock", "mock"),
    ("fixture", "fixture"),
    ("lint", "lint"),
    ("formatter", "formatter"),
    ("refactorizare", "refactor"),
    ("regresie", "regression"),
    ("ramură principală", "main branch"),
    ("etichetă git", "git tag"),
    ("conflict de merge", "merge conflict"),
    ("pipeline ci", "ci pipeline"),
    ("artefact build", "build artifact"),
    ("variabilă de mediu", "environment variable"),
    ("secret", "secret"),
    ("containerizare", "containerization"),
    ("orchestrare", "orchestration"),
    ("observabilitate", "observability"),
    ("telemetrie", "telemetry"),
    ("trasare", "tracing"),
    ("metrici de sistem", "system metrics"),
    ("alertă", "alert"),
    ("incident", "incident"),
]

AI_LLM_TERMS = [
    ("model lingvistic mare", "large language model"),
    ("fereastră de context", "context window"),
    ("tokenizare", "tokenization"),
    ("token de intrare", "input token"),
    ("token de ieșire", "output token"),
    ("prompt de sistem", "system prompt"),
    ("prompt de utilizator", "user prompt"),
    ("mesaj asistent", "assistant message"),
    ("raționament", "reasoning"),
    ("temperatură model", "model temperature"),
    ("top p", "top p"),
    ("eșantionare", "sampling"),
    ("halucinație", "hallucination"),
    ("ancorare", "grounding"),
    ("recuperare de informații", "retrieval"),
    ("rag", "retrieval augmented generation"),
    ("embedding", "embedding"),
    ("spațiu vectorial", "vector space"),
    ("bază vectorială", "vector database"),
    ("similaritate cosinus", "cosine similarity"),
    ("reranker", "reranker"),
    ("clasificator", "classifier"),
    ("etichetare automată", "automatic labeling"),
    ("rezumat automat", "automatic summary"),
    ("agent autonom", "autonomous agent"),
    ("planificator", "planner"),
    ("apel de instrument", "tool call"),
    ("schemă de instrument", "tool schema"),
    ("ieșire structurată", "structured output"),
    ("evaluare model", "model evaluation"),
    ("set de evaluare", "evaluation set"),
    ("scor de calitate", "quality score"),
    ("alucinație detectată", "detected hallucination"),
    ("politică de siguranță", "safety policy"),
    ("filtru de conținut", "content filter"),
    ("aliniere", "alignment"),
    ("reglaj fin", "fine tuning"),
    ("distilare", "distillation"),
    ("inferență", "inference"),
    ("latență de inferență", "inference latency"),
    ("cost pe token", "cost per token"),
    ("memorie de conversație", "conversation memory"),
    ("lanț de prompturi", "prompt chain"),
    ("exemplu few-shot", "few shot example"),
    ("zero-shot", "zero shot"),
    ("funcție de recompensă", "reward function"),
    ("agent evaluator", "evaluator agent"),
    ("decodor semantic", "semantic decoder"),
    ("compresie semantică", "semantic compression"),
    ("protocol emergent", "emergent protocol"),
]

PROJECT_MANAGEMENT_TERMS = [
    ("obiectiv", "objective"),
    ("jalon", "milestone"),
    ("livrabil", "deliverable"),
    ("sarcină blocată", "blocked task"),
    ("dependință de proiect", "project dependency"),
    ("risc", "risk"),
    ("mitigare", "mitigation"),
    ("prioritate", "priority"),
    ("estimare", "estimate"),
    ("efort", "effort"),
    ("termen", "due date"),
    ("proprietar", "owner"),
    ("responsabil", "responsible person"),
    ("parte interesată", "stakeholder"),
    ("cerință", "requirement"),
    ("criteriu de acceptare", "acceptance criterion"),
    ("roadmap", "roadmap"),
    ("sprint", "sprint"),
    ("backlog", "backlog"),
    ("ticket", "ticket"),
    ("epic", "epic"),
    ("poveste utilizator", "user story"),
    ("ședință zilnică", "daily standup"),
    ("retro", "retrospective"),
    ("revizuire sprint", "sprint review"),
    ("notă de decizie", "decision note"),
    ("schimbare de scop", "scope change"),
    ("blocaj", "blocker"),
    ("raport de stare", "status report"),
    ("indicator cheie", "key indicator"),
    ("capacitate", "capacity"),
    ("alocare", "allocation"),
    ("calendar proiect", "project calendar"),
    ("flux de lucru", "workflow"),
    ("aprobare", "approval"),
    ("escaladare", "escalation"),
    ("lecție învățată", "lesson learned"),
    ("ipoteză", "assumption"),
    ("constrângere", "constraint"),
    ("decizie deschisă", "open decision"),
    ("problemă deschisă", "open issue"),
    ("următorul pas", "next step"),
    ("plan de lansare", "release plan"),
    ("notă de lansare", "release note"),
    ("criteriu de succes", "success criterion"),
]

CYBER_LINUX_TERMS = [
    ("utilizator linux", "linux user"),
    ("grup linux", "linux group"),
    ("permisiuni fișier", "file permissions"),
    ("proprietar fișier", "file owner"),
    ("shell", "shell"),
    ("bash", "bash"),
    ("proces linux", "linux process"),
    ("daemon", "daemon"),
    ("serviciu systemd", "systemd service"),
    ("jurnal systemd", "systemd journal"),
    ("cale absolută", "absolute path"),
    ("cale relativă", "relative path"),
    ("director home", "home directory"),
    ("director temporar", "temporary directory"),
    ("link simbolic", "symbolic link"),
    ("pachet deb", "deb package"),
    ("manager de pachete", "package manager"),
    ("actualizare sistem", "system update"),
    ("port", "port"),
    ("socket", "socket"),
    ("firewall", "firewall"),
    ("regulă firewall", "firewall rule"),
    ("adresă ip", "ip address"),
    ("dns", "dns"),
    ("tls", "tls"),
    ("cheie publică", "public key"),
    ("cheie privată", "private key"),
    ("hash", "hash"),
    ("semnătură", "signature"),
    ("criptare", "encryption"),
    ("decriptare", "decryption"),
    ("vulnerabilitate", "vulnerability"),
    ("exploit", "exploit"),
    ("patch de securitate", "security patch"),
    ("scanare porturi", "port scan"),
    ("autentificare", "authentication"),
    ("autorizare", "authorization"),
    ("sesiune", "session"),
    ("cookie", "cookie"),
    ("csrf", "csrf"),
    ("xss", "xss"),
    ("injecție sql", "sql injection"),
    ("forță brută", "brute force"),
    ("rată limitată", "rate limit"),
    ("listă de control acces", "access control list"),
    ("principiu minim privilegiu", "least privilege"),
    ("audit", "audit"),
    ("log de securitate", "security log"),
    ("incident de securitate", "security incident"),
    ("copie sigură", "secure copy"),
    ("tunel ssh", "ssh tunnel"),
    ("container linux", "linux container"),
    ("capabilitate linux", "linux capability"),
    ("spațiu de nume linux", "linux namespace"),
    ("cgroup", "cgroup"),
    ("montare", "mount"),
]

GRAMMAR_COMPRESSION_EXTRA = [
    ("separator de câmp", "field separator"),
    ("separator de listă", "list separator"),
    ("marcator de început", "start marker"),
    ("marcator de sfârșit", "end marker"),
    ("marcator de rol", "role marker"),
    ("marcator de timp", "time marker"),
    ("marcator de loc", "location marker"),
    ("marcator de scop", "purpose marker"),
    ("marcator de cauză", "cause marker"),
    ("marcator de stare", "state marker"),
    ("marcator de eroare", "error marker"),
    ("marcator de confirmare", "confirmation marker"),
    ("marcator de ambiguitate", "ambiguity marker"),
    ("marcator de compunere", "composition marker"),
    ("marcator de comprimare", "compression marker"),
    ("marcator de decomprimare", "decompression marker"),
    ("cod de categorie", "category code"),
    ("cod de domeniu", "domain code"),
    ("cod de relație", "relation code"),
    ("cod de acțiune", "action code"),
    ("cod de entitate", "entity code"),
    ("cod de proprietate", "property code"),
    ("cod de valoare", "value code"),
    ("cod de întrebare", "question code"),
    ("cod de negare", "negation code"),
    ("cod de plural", "plural code"),
    ("regulă de scurtare", "shortening rule"),
    ("regulă de reutilizare", "reuse rule"),
    ("regulă de evitare duplicat", "duplicate avoidance rule"),
    ("regulă de evoluție token", "token evolution rule"),
]
