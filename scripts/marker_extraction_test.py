#!/usr/bin/env python3
"""Marker-based GPT-NER extraction test."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (str(PROJECT_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from ie_course.kisski_client import (
    ARTIFACT_DIR,
    DEFAULT_EXAMPLE_DISPLAY,
    EXPECTED_GOLD_SPANS,
    collect_config,
    request_json,
    save_artifact,
    summarize_gold_span_report,
    validate_marker_output,
)


def run_marker_extraction_test() -> int:
    print("=== Marker Extraction Test ===")
    config, missing = collect_config()
    if missing:
        print("HTTP status: n/a")
        print("Exit code: 1")
        print("Error: missing required values in .env")
        return 1

    base_url = str(config["base_url"]).rstrip("/")
    api_key = str(config["api_key"])
    model_id = str(config["model"] or "")

    models_status, models_body, models_text = request_json(f"{base_url}/models", api_key)
    print(f"HTTP status: {models_status}")
    if models_status >= 400 or models_body is None:
        print("Exit code: 3")
        print("Error: /models request failed")
        return 3

    available_models = [item.get("id") for item in models_body.get("data", []) if item.get("id")]
    if not available_models:
        print("Exit code: 4")
        print("Error: no model IDs returned")
        return 4
    if not model_id:
        model_id = available_models[0]

    example_display = DEFAULT_EXAMPLE_DISPLAY
    marker_prompt = (
        "You are a strict marker-based extractor for job advertisements. "
        "Return only the marked text. "
        "Do not explain anything. "
        "Do not use markdown. "
        "Do not include JSON. "
        "Use only these marker types: @@JOB_TITLE{...}##, @@HARD_SKILL{...}##, @@SOFT_SKILL{...}##, @@EXPERIENCE{...}##, @@EDUCATION{...}##, @@LANGUAGE{...}##, @@WORK_MODE{...}##. "
        "Do not output LOCATION or COMPANY. "
        "Keep the rest of the text fully intact and in the same order. "
        "Only mark text spans that appear exactly in the input. "
        "Do not invent information. "
        "Do not create overlapping or nested markers. "
        "Work-time expressions such as '20 Stunden pro Woche', 'Vollzeit', 'Teilzeit', 'Werkstudent', 'Remote', and 'Hybrid' belong to WORK_MODE when they appear as their own text spans. "
        "For this controlled example, the output must contain exactly these two markers and no others: "
        "@@JOB_TITLE{Werkstudent (m/w/d) für Data Science}## and @@WORK_MODE{20 Stunden pro Woche}##. "
        "Leave 'Berlin.' unmarked. Preserve every other character, whitespace, punctuation, and order exactly. "
        f"Display: {example_display}"
    )

    chat_payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "Return only the marked text and nothing else."},
            {"role": "user", "content": marker_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 200,
    }
    chat_status, chat_body, chat_text = request_json(f"{base_url}/chat/completions", api_key, chat_payload)
    print(f"Used model ID: {model_id}")
    print(f"Chat HTTP status: {chat_status}")

    marker_artifact_dir = ARTIFACT_DIR / "marker_test"
    save_artifact(marker_artifact_dir / "input_text.txt", example_display)
    save_artifact(marker_artifact_dir / "marker_prompt.txt", marker_prompt)
    raw_response_text = chat_text if chat_text is not None else json.dumps(chat_body, ensure_ascii=False, indent=2)
    save_artifact(marker_artifact_dir / "raw_model_response.txt", raw_response_text)

    if chat_status >= 400 or not chat_body:
        print("Exit code: 5")
        print("Error: chat completion request failed")
        return 5

    choices = chat_body.get("choices")
    if not isinstance(choices, list) or not choices:
        print("Exit code: 5")
        print("Error: invalid chat completion response")
        return 5
    message = choices[0].get("message")
    if not isinstance(message, dict):
        print("Exit code: 5")
        print("Error: invalid chat completion response")
        return 5
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        print("Exit code: 5")
        print("Error: empty message content")
        return 5

    validation_ok, spans, validation_error, text_without_syntax = validate_marker_output(content, example_display)
    if not validation_ok:
        save_artifact(marker_artifact_dir / "marked_text.txt", content)
        print("Exit code: 5")
        print(f"Validation error: {validation_error}")
        print("Text fidelity error:")
        print(text_without_syntax)
        print("Marked text:")
        print(content)
        return 5

    found_expected, missing_expected, unexpected = summarize_gold_span_report(spans, EXPECTED_GOLD_SPANS)
    save_artifact(marker_artifact_dir / "marked_text.txt", content)
    print("Marker output:")
    print(content)
    print("Found expected spans:")
    for item in found_expected:
        print(f"- {item}")
    print("Missing expected spans:")
    for item in missing_expected:
        print(f"- {item}")
    print("Unexpected spans:")
    for item in unexpected:
        print(f"- {item}")

    if missing_expected or unexpected:
        print("Exit code: 5")
        return 5

    print("Exit code: 0")
    return 0


if __name__ == "__main__":
    sys.exit(run_marker_extraction_test())
