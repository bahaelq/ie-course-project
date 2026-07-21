#!/usr/bin/env python3
"""Validate example annotation files for the controlled job-ad example set."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EXAMPLES_DIR: Final[Path] = PROJECT_ROOT / "data" / "smoke_test"
GOLD_DIR: Final[Path] = EXAMPLES_DIR / "annotations"
ALLOWED_TYPES: Final[set[str]] = {
    "JOB_TITLE",
    "HARD_SKILL",
    "SOFT_SKILL",
    "EXPERIENCE",
    "EDUCATION",
    "LANGUAGE",
    "WORK_MODE",
}


def _find_all_occurrences(text: str, value: str) -> list[int]:
    return [match.start() for match in re.finditer(re.escape(value), text)]


def validate_annotations_data() -> tuple[bool, list[str], list[str], dict[str, int]]:
    text_files = sorted(EXAMPLES_DIR.glob("job_ad_*.txt"))
    if not text_files:
        return False, ["No example text files found"], [], {entity_type: 0 for entity_type in sorted(ALLOWED_TYPES)}

    errors: list[str] = []
    warnings: list[str] = []
    entity_counts: dict[str, int] = {entity_type: 0 for entity_type in sorted(ALLOWED_TYPES)}

    for text_file in text_files:
        stem = text_file.stem
        gold_file = GOLD_DIR / f"{stem}.json"
        if not gold_file.exists():
            errors.append(f"Missing gold file for {stem}")
            continue

        try:
            text = text_file.read_text(encoding="utf-8")
            payload = json.loads(gold_file.read_text(encoding="utf-8"))
        except UnicodeDecodeError as exc:
            errors.append(f"UTF-8 decode error in {text_file.name}: {exc}")
            continue
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON in {gold_file.name}: {exc}")
            continue

        if payload.get("id") != stem:
            errors.append(f"Unexpected id in {gold_file.name}: {payload.get('id')}")

        entities = payload.get("entities")
        if not isinstance(entities, list):
            errors.append(f"entities is not a list in {gold_file.name}")
            continue

        seen_annotations: set[tuple[str, str, int, int]] = set()
        span_type_by_range: dict[tuple[int, int], str] = {}

        for entity in entities:
            if not isinstance(entity, dict):
                errors.append(f"Invalid entity object in {gold_file.name}")
                continue

            entity_type = entity.get("type")
            if entity_type not in ALLOWED_TYPES:
                errors.append(f"Unexpected entity type in {gold_file.name}: {entity_type}")
                continue
            entity_counts[entity_type] += 1

            text_value = entity.get("text")
            start = entity.get("start")
            end = entity.get("end")
            if not isinstance(text_value, str) or not text_value:
                errors.append(f"Empty or invalid text in {gold_file.name}")
                continue
            if not isinstance(start, int) or not isinstance(end, int):
                errors.append(f"start/end must be integers in {gold_file.name}")
                continue
            if start < 0 or end < 0 or start >= end:
                errors.append(f"Invalid span range in {gold_file.name}: {start}, {end}")
                continue
            if not (0 <= start < len(text) and 0 <= end <= len(text)):
                errors.append(f"Span out of bounds in {gold_file.name}: {start}, {end}")
                continue
            if text[start:end] != text_value:
                errors.append(f"Text mismatch in {gold_file.name}: expected {text[start:end]!r}, got {text_value!r}")
                continue

            occurrence_positions = _find_all_occurrences(text, text_value)
            if len(occurrence_positions) > 1:
                errors.append(
                    f"Ambiguous text match in {gold_file.name}: {entity_type} '{text_value}' appears {len(occurrence_positions)} times"
                )

            annotation_key = (entity_type, text_value, start, end)
            if annotation_key in seen_annotations:
                errors.append(
                    f"Duplicate identical annotation in {gold_file.name}: {entity_type} '{text_value}'"
                )
            else:
                seen_annotations.add(annotation_key)

            span_key = (start, end)
            existing_type = span_type_by_range.get(span_key)
            if existing_type is not None and existing_type != entity_type:
                errors.append(
                    f"Identical span with different types in {gold_file.name}: {existing_type} vs {entity_type}"
                )
            else:
                span_type_by_range[span_key] = entity_type

        for left_index, left in enumerate(entities):
            if not isinstance(left, dict):
                continue
            left_start = left.get("start")
            left_end = left.get("end")
            if not isinstance(left_start, int) or not isinstance(left_end, int):
                continue
            for right in entities[left_index + 1 :]:
                if not isinstance(right, dict):
                    continue
                right_start = right.get("start")
                right_end = right.get("end")
                if not isinstance(right_start, int) or not isinstance(right_end, int):
                    continue
                if max(left_start, right_start) < min(left_end, right_end):
                    errors.append(
                        f"Overlapping spans in {gold_file.name}: {left.get('text')!r} and {right.get('text')!r}"
                    )

    for entity_type, count in entity_counts.items():
        if count < 2:
            warnings.append(f"Low count warning for {entity_type}: {count}")

    return not errors, errors, warnings, entity_counts


def validate_annotations() -> int:
    print("=== Example Annotation Validation ===")
    ok, errors, warnings, entity_counts = validate_annotations_data()
    if not ok:
        print("Validation failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Validation succeeded")
    print("Entity counts per type:")
    for entity_type in sorted(ALLOWED_TYPES):
        print(f"- {entity_type}: {entity_counts[entity_type]}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(validate_annotations())
