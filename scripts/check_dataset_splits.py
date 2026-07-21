#!/usr/bin/env python3
"""Validate dataset split integrity across smoke_test, example_pool, gold, unlabeled."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"

ALLOWED_TYPES: Final[set[str]] = {
    "JOB_TITLE", "HARD_SKILL", "SOFT_SKILL",
    "EXPERIENCE", "EDUCATION", "LANGUAGE", "WORK_MODE",
}

ALLOWED_WRITE_SPLITS: Final[set[str]] = {"example_pool", "gold", "unlabeled"}
ALL_SPLITS: Final[list[str]] = ["smoke_test", "example_pool", "gold", "unlabeled"]
ANNOTATED_SPLITS: Final[set[str]] = {"smoke_test", "example_pool", "gold"}
DATE_RE: Final[re.Pattern] = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def get_text_ids(split: str) -> set[str]:
    text_dir = DATA_DIR / split / "texts"
    if text_dir.exists():
        return {p.stem for p in sorted(text_dir.glob("*.txt"))}
    if split == "smoke_test":
        return {p.stem for p in sorted((DATA_DIR / split).glob("*.txt"))}
    return set()


def get_annotation_ids(split: str) -> set[str]:
    ann_dir = DATA_DIR / split / "annotations"
    if ann_dir.exists():
        return {p.stem for p in sorted(ann_dir.glob("*.json"))}
    return set()


def get_text_files(split: str) -> list[Path]:
    texts_dir = DATA_DIR / split / "texts"
    if texts_dir.exists():
        return sorted(texts_dir.glob("*.txt"))
    if split == "smoke_test":
        return sorted((DATA_DIR / split).glob("*.txt"))
    return []


def get_annotation_files(split: str) -> list[Path]:
    ann_dir = DATA_DIR / split / "annotations"
    if ann_dir.exists():
        return sorted(ann_dir.glob("*.json"))
    return []


def validate_utf8(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"  Nicht UTF-8: {path.name}: {exc}")
    return errors


def validate_metadata(split: str) -> list[str]:
    errors: list[str] = []
    meta_path = DATA_DIR / split / "metadata.jsonl"
    if split not in ALLOWED_WRITE_SPLITS:
        return errors

    text_ids = get_text_ids(split)
    meta_ids: set[str] = set()

    if not meta_path.exists():
        errors.append(f"  metadata.jsonl fehlt in {split}/")
        return errors

    lines = meta_path.read_text(encoding="utf-8").strip().split("\n")
    if lines == [""]:
        lines = []

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"  metadata.jsonl Zeile {i}: ungültiges JSON: {exc}")
            continue

        if not isinstance(entry, dict):
            errors.append(f"  metadata.jsonl Zeile {i}: kein Objekt")
            continue

        eid = entry.get("id", "")
        if not isinstance(eid, str) or not eid:
            errors.append(f"  metadata.jsonl Zeile {i}: fehlende oder ungültige id")
            continue

        if eid in meta_ids:
            errors.append(f"  Doppelte ID in metadata.jsonl: {eid}")
        meta_ids.add(eid)

        esplit = entry.get("split", "")
        if esplit != split:
            errors.append(f"  metadata.jsonl Zeile {i}: split {esplit!r} != {split!r}")

        if eid not in text_ids:
            errors.append(f"  metadata.jsonl: ID {eid} hat keine Textdatei in {split}/")

        date_val = entry.get("retrieved_at", "")
        if date_val and not DATE_RE.match(str(date_val)):
            errors.append(f"  metadata.jsonl Zeile {i}: ungültiges Datum {date_val!r}")

        url = entry.get("source_url", "")
        if url:
            if not url.startswith("http://") and not url.startswith("https://"):
                errors.append(f"  metadata.jsonl Zeile {i}: ungültige URL {url!r}")

    # Jede Textdatei braucht genau eine Metadatenzeile
    for tid in sorted(text_ids):
        if tid not in meta_ids:
            errors.append(f"  Text {tid}.txt hat keine Metadaten in metadata.jsonl")

    return errors


def validate_annotation_structure(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"  Ungültiges JSON: {path.name}: {exc}"]

    if not isinstance(payload, dict):
        return [f"  Kein JSON-Objekt: {path.name}"]

    stem = path.stem
    if payload.get("id") != stem:
        errors.append(f"  ID-Mismatch in {path.name}: erwartet {stem!r}, erhalten {payload.get('id')!r}")

    entities = payload.get("entities")
    if not isinstance(entities, list):
        return [f"  'entities' ist keine Liste: {path.name}"]

    seen_annotations: set[tuple[str, str, int, int]] = set()
    span_type_by_range: dict[tuple[int, int], str] = {}

    for idx, entity in enumerate(entities):
        if not isinstance(entity, dict):
            errors.append(f"  Entity {idx} ist kein Dict: {path.name}")
            continue

        entity_type = entity.get("type")
        if entity_type not in ALLOWED_TYPES:
            errors.append(f"  Ungültiger Typ {entity_type!r} in {path.name}")
            continue

        text_value = entity.get("text")
        start = entity.get("start")
        end = entity.get("end")

        if not isinstance(text_value, str) or not text_value:
            errors.append(f"  Ungültiger text-Wert in Entity {idx}: {path.name}")
            continue
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append(f"  start/end müssen Integer sein in Entity {idx}: {path.name}")
            continue
        if start < 0 or end < 0 or start >= end:
            errors.append(f"  Ungültiger Span ({start}, {end}) in {path.name}")
            continue
        if not (0 <= start < len(text) and 0 <= end <= len(text)):
            errors.append(f"  Span außerhalb des Textes ({start}, {end}) in {path.name}")
            continue
        if text[start:end] != text_value:
            errors.append(f"  Text-Mismatch in {path.name}: erwartet {text[start:end]!r}, erhalten {text_value!r}")
            continue

        oc = [m.start() for m in re.finditer(re.escape(text_value), text)]
        if len(oc) > 1:
            errors.append(f"  Mehrdeutiger Text in {path.name}: {entity_type} {text_value!r} erscheint {len(oc)}-mal")

        key = (entity_type, text_value, start, end)
        if key in seen_annotations:
            errors.append(f"  Doppelte Annotation in {path.name}: {entity_type} {text_value!r}")
        seen_annotations.add(key)

        span_key = (start, end)
        existing = span_type_by_range.get(span_key)
        if existing is not None and existing != entity_type:
            errors.append(f"  Gleicher Span, verschiedene Typen in {path.name}: {existing} vs {entity_type}")
        span_type_by_range[span_key] = entity_type

    for i, left in enumerate(entities):
        if not isinstance(left, dict):
            continue
        ls, le = left.get("start"), left.get("end")
        if not isinstance(ls, int) or not isinstance(le, int):
            continue
        for right in entities[i + 1 :]:
            if not isinstance(right, dict):
                continue
            rs, re2 = right.get("start"), right.get("end")
            if not isinstance(rs, int) or not isinstance(re2, int):
                continue
            if max(ls, rs) < min(le, re2):
                errors.append(f"  Überlappende Spans in {path.name}: {left.get('text')!r} und {right.get('text')!r}")

    return errors


def check_split() -> int:
    all_errors: list[str] = []
    all_warnings: list[str] = []
    text_ids_by_split: dict[str, set[str]] = {}
    ann_ids_by_split: dict[str, set[str]] = {}
    text_hashes: dict[str, dict[str, str]] = {}
    urls_by_split: dict[str, dict[str, str]] = {}

    return_code = 0

    # ---- Collect data per split ----
    for split in ALL_SPLITS:
        split_dir = DATA_DIR / split
        if not split_dir.exists():
            all_warnings.append(f"Split {split}/ existiert nicht")
            text_ids_by_split[split] = set()
            ann_ids_by_split[split] = set()
            text_hashes[split] = {}
            urls_by_split[split] = {}
            continue

        text_ids: set[str] = set()
        ann_ids: set[str] = set()

        for text_path in get_text_files(split):
            stem = text_path.stem
            text_ids.add(stem)
            utf8_errors = validate_utf8(text_path)
            all_errors.extend(utf8_errors)
            h = hashlib.sha256(text_path.read_bytes()).hexdigest()
            text_hashes.setdefault(split, {})[stem] = h

        for ann_path in get_annotation_files(split):
            stem = ann_path.stem
            ann_ids.add(stem)
            utf8_errors = validate_utf8(ann_path)
            all_errors.extend(utf8_errors)

        text_ids_by_split[split] = text_ids
        ann_ids_by_split[split] = ann_ids

        # Collect URLs from metadata
        urls_by_split[split] = {}
        meta_path = DATA_DIR / split / "metadata.jsonl"
        if meta_path.exists():
            for line in meta_path.read_text(encoding="utf-8").strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(entry, dict):
                    eid = entry.get("id", "")
                    url = entry.get("source_url", "")
                    if url:
                        urls_by_split[split][url] = eid

    # ---- Cross-split checks ----

    # 1) Keine ID in mehr als einem Split
    id_to_split: dict[str, str] = {}
    for split in ALL_SPLITS:
        for sid in text_ids_by_split[split] | ann_ids_by_split[split]:
            if sid in id_to_split:
                all_errors.append(f"ID {sid!r} in mehreren Splits: {id_to_split[sid]} und {split}")
            else:
                id_to_split[sid] = split

    # 2) Keine identischen Texte in mehreren Splits
    for split_a in ALL_SPLITS:
        for stem_a, hash_a in text_hashes.get(split_a, {}).items():
            for split_b in ALL_SPLITS:
                if split_b <= split_a:
                    continue
                for stem_b, hash_b in text_hashes.get(split_b, {}).items():
                    if hash_a == hash_b:
                        all_errors.append(
                            f"Identischer Text in {split_a}/{stem_a}.txt und {split_b}/{stem_b}.txt"
                        )

    # 3) Keine identischen URLs in mehreren Splits
    for split_a in ALL_SPLITS:
        for url_a, eid_a in urls_by_split.get(split_a, {}).items():
            for split_b in ALL_SPLITS:
                if split_b <= split_a:
                    continue
                for url_b, eid_b in urls_by_split.get(split_b, {}).items():
                    if url_a == url_b:
                        all_errors.append(
                            f"Identische URL in {split_a}/{eid_a} und {split_b}/{eid_b}: {url_a}"
                        )

    # 4) Jede Annotation hat Textdatei
    for split in ALL_SPLITS:
        for aid in ann_ids_by_split[split]:
            text_path = DATA_DIR / split / "texts" / f"{aid}.txt"
            fallback = DATA_DIR / split / f"{aid}.txt"
            if not text_path.exists() and not fallback.exists():
                all_errors.append(f"Annotation {split}/{aid}.json hat keine Textdatei")

    # 5) Jeder Text in annotierten Splits hat Annotation
    for split in ANNOTATED_SPLITS:
        for tid in text_ids_by_split.get(split, set()):
            ann_path = DATA_DIR / split / "annotations" / f"{tid}.json"
            if not ann_path.exists():
                all_errors.append(f"Text {split}/{tid}.txt hat keine Annotation")

    # 6) Unlabeled hat keine Annotationen
    if ann_ids_by_split.get("unlabeled"):
        all_errors.append("unlabeled/annotations/ darf keine Dateien enthalten")

    # 7) Validierung der Annotationsstruktur
    for split in ALL_SPLITS:
        for ann_path in get_annotation_files(split):
            stem = ann_path.stem
            text_path = DATA_DIR / split / "texts" / f"{stem}.txt"
            if not text_path.exists():
                if split == "smoke_test":
                    text_path = DATA_DIR / split / f"{stem}.txt"
            if text_path.exists():
                try:
                    text_content = text_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    text_content = ""
            else:
                text_content = ""
            ann_errors = validate_annotation_structure(ann_path, text_content)
            all_errors.extend(ann_errors)

    # 8) Metadata-Validierung
    for split in ALLOWED_WRITE_SPLITS:
        meta_errors = validate_metadata(split)
        all_errors.extend(meta_errors)

    # ---- Output ----
    print("=" * 60)
    print("DATASET SPLIT VALIDATION")
    print("=" * 60)
    print()

    print("IDs per Split:")
    for split in ALL_SPLITS:
        tids = sorted(text_ids_by_split.get(split, set()))
        aids = sorted(ann_ids_by_split.get(split, set()))
        print(f"  {split}: {len(tids)} Texte, {len(aids)} Annotationen")
        if tids:
            print(f"    Texte: {', '.join(tids)}")

    print()
    if all_errors:
        print(f"FEHLER ({len(all_errors)}):")
        for e in all_errors:
            print(f"  - {e}")
        return_code = 1
    else:
        print("KEINE FEHLER")

    if all_warnings:
        print(f"\nWARNUNGEN ({len(all_warnings)}):")
        for w in all_warnings:
            print(f"  - {w}")

    return return_code


def main() -> int:
    return check_split()


if __name__ == "__main__":
    sys.exit(main())
