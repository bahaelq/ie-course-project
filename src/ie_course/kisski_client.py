#!/usr/bin/env python3
"""Shared helpers for KISSKI-compatible API tests."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Final

from dotenv import load_dotenv


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return current


PROJECT_ROOT: Final[Path] = find_project_root(Path(__file__).resolve())
ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"
ARTIFACT_DIR: Final[Path] = PROJECT_ROOT / "artifacts" / "kisski_test"
DEFAULT_EXAMPLE_DISPLAY: Final[str] = "Werkstudent (m/w/d) für Data Science, 20 Stunden pro Woche, Berlin."
MARKER_ALLOWED_TYPES: Final[tuple[str, ...]] = (
    "JOB_TITLE",
    "HARD_SKILL",
    "SOFT_SKILL",
    "EXPERIENCE",
    "EDUCATION",
    "LANGUAGE",
    "WORK_MODE",
)
EXPECTED_GOLD_SPANS: Final[dict[str, tuple[str, ...]]] = {
    "JOB_TITLE": ("Werkstudent (m/w/d) für Data Science",),
    "WORK_MODE": ("20 Stunden pro Woche",),
}


def collect_config() -> tuple[dict[str, str | None], list[str]]:
    pyproject_file = PROJECT_ROOT / "pyproject.toml"
    if not pyproject_file.exists():
        return {}, ["pyproject"]

    if not ENV_FILE.exists():
        return {}, ["env"]

    load_dotenv(dotenv_path=ENV_FILE)

    config = {
        "api_key": os.getenv("KISSKI_API_KEY", "").strip() or None,
        "base_url": os.getenv("KISSKI_BASE_URL", "").strip() or None,
        "model": os.getenv("KISSKI_MODEL", "").strip() or None,
    }

    missing = [
        key_name
        for key_name, value in (
            ("KISSKI_API_KEY", config["api_key"]),
            ("KISSKI_BASE_URL", config["base_url"]),
        )
        if not value
    ]
    return config, missing


def request_json(url: str, api_key: str, payload: dict | None = None) -> tuple[int, dict | None, str | None]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            body = response.read().decode("utf-8")
            status = response.getcode()
            try:
                return status, json.loads(body), None
            except json.JSONDecodeError:
                return status, None, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body), None
        except json.JSONDecodeError:
            return exc.code, None, body
    except Exception as exc:  # pragma: no cover - network/API errors are runtime dependent
        return 599, None, str(exc)


def save_artifact(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def add_repo_root_to_path() -> None:
    repo_root = str(PROJECT_ROOT)
    src_root = str(PROJECT_ROOT / "src")
    for path in (repo_root, src_root):
        if path not in sys.path:
            sys.path.insert(0, path)


def extract_json_payload(raw_text: str | None) -> tuple[dict | list | None, str | None]:
    if raw_text is None:
        return None, "No content returned"

    text = raw_text.strip()
    if not text:
        return None, "Empty content"

    cleaned_text = text
    if cleaned_text.startswith("```"):
        cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
    if cleaned_text.startswith("json"):
        cleaned_text = cleaned_text[4:].strip()

    try:
        return json.loads(cleaned_text), None
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc}"


def validate_schema(parsed_output: object) -> tuple[bool, str | None]:
    if not isinstance(parsed_output, dict):
        return False, "Top-level JSON must be an object"

    expected_keys = [
        "JOB_TITLE",
        "HARD_SKILL",
        "SOFT_SKILL",
        "EXPERIENCE",
        "EDUCATION",
        "LANGUAGE",
        "WORK_MODE",
    ]
    actual_keys = sorted(parsed_output.keys())
    expected_set = set(expected_keys)
    actual_set = set(parsed_output.keys())

    if actual_keys != sorted(expected_keys):
        missing = [key for key in expected_keys if key not in parsed_output]
        unknown = [key for key in parsed_output if key not in expected_set]
        if missing:
            return False, f"Missing keys: {', '.join(missing)}"
        if unknown:
            return False, f"Unknown keys: {', '.join(unknown)}"
        return False, "Key set does not match the required schema"

    for key in expected_keys:
        value = parsed_output[key]
        if not isinstance(value, list):
            return False, f"Key '{key}' must be a list"
        for item in value:
            if not isinstance(item, str):
                return False, f"Key '{key}' contains a non-string entry"

    return True, None


def normalize_trailing_file_newline(text: str) -> str:
    """Normalize only a trailing file newline for text-fidelity comparisons.

    The trailing newline often comes from storing the original TXT file on disk and is
    not part of the semantic model response. This helper intentionally does not alter
    any other whitespace, punctuation, or Unicode content.
    """

    if text.endswith("\r\n"):
        return text[:-2]
    if text.endswith("\n"):
        return text[:-1]
    return text


def strip_marker_syntax(text: str) -> str:
    without_prefix = re.sub(r"@@[A-Z_]+\{", "", text)
    return re.sub(r"\}##", "", without_prefix)


def extract_marker_spans(text: str) -> list[dict[str, object]]:
    pattern = re.compile(r"@@(?P<type>[A-Z_]+)\{(?P<content>.*?)\}##")
    return [
        {
            "type": match.group("type"),
            "content": match.group("content"),
            "start": match.start(),
            "end": match.end(),
        }
        for match in pattern.finditer(text)
    ]


def validate_marker_output(text: str, original_text: str) -> tuple[bool, list[dict[str, object]], str | None, str | None]:
    pattern = re.compile(r"@@(?P<type>[A-Z_]+)\{(?P<content>.*?)\}##")
    matches = list(pattern.finditer(text))

    if not matches:
        return False, [], "No markers found", None

    errors: list[str] = []
    spans: list[dict[str, object]] = []
    for match in matches:
        marker_type = match.group("type")
        content = match.group("content")
        full_match = match.group(0)

        if marker_type not in MARKER_ALLOWED_TYPES:
            errors.append(f"Unknown marker type: {marker_type}")
            continue
        if not content.strip():
            errors.append(f"Empty content for marker type: {marker_type}")
            continue
        if "@@" in content or "##" in content:
            errors.append(f"Nested marker syntax in content for {marker_type}")
            continue
        if not full_match.startswith("@@") or not full_match.endswith("##"):
            errors.append(f"Incorrect marker syntax for {marker_type}")
            continue
        if content not in original_text:
            errors.append(f"Marked content not found in original text for {marker_type}: {content}")
            continue
        spans.append({
            "type": marker_type,
            "content": content,
            "start": match.start(),
            "end": match.end(),
        })

    if errors:
        return False, spans, "; ".join(errors), None

    text_without_syntax = strip_marker_syntax(text)
    if normalize_trailing_file_newline(text_without_syntax) != normalize_trailing_file_newline(original_text):
        return False, spans, "Text fidelity mismatch after removing marker syntax", text_without_syntax

    for index, span in enumerate(spans):
        content = str(span["content"])
        content_positions = [match.start() for match in re.finditer(re.escape(content), original_text)]
        if not content_positions:
            return False, spans, f"Marked content not found in original text: {content}", None
        start = content_positions[0]
        end = start + len(content)
        for other_span in spans[index + 1 :]:
            other_content = str(other_span["content"])
            other_positions = [match.start() for match in re.finditer(re.escape(other_content), original_text)]
            if not other_positions:
                continue
            other_start = other_positions[0]
            other_end = other_start + len(other_content)
            if start < other_end and other_start < end:
                return False, spans, f"Overlapping spans detected: {content} and {other_content}", None

    return True, spans, None, text_without_syntax


def summarize_gold_span_report(found_spans: list[dict[str, object]], expected_spans: dict[str, tuple[str, ...]]) -> tuple[list[str], list[str], list[str]]:
    found_expected: list[str] = []
    missing_expected: list[str] = []
    unexpected: list[str] = []

    expected_pairs = [(label, span) for label, spans in expected_spans.items() for span in spans]
    found_pairs = [(str(span["type"]), str(span["content"])) for span in found_spans]

    for label, expected_span in expected_pairs:
        if (label, expected_span) in found_pairs:
            found_expected.append(f"{label}: {expected_span}")
        else:
            missing_expected.append(f"{label}: {expected_span}")

    for label, content in found_pairs:
        if not any(label == expected_label and content == expected_span for expected_label, expected_span in expected_pairs):
            unexpected.append(f"{label}: {content}")

    return found_expected, missing_expected, unexpected
