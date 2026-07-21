#!/usr/bin/env python3
"""Plain JSON extraction baseline test."""

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
    collect_config,
    extract_json_payload,
    request_json,
    save_artifact,
    validate_schema,
)


def run_json_extraction_test() -> int:
    print("=== JSON Extraction Test ===")
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
    prompt = (
        "You are a strict extractor for job advertisements. "
        "Return only valid JSON. "
        "Do not explain anything. "
        "Do not use markdown. "
        "Do not include reasoning. "
        "Use exactly these entity types only: JOB_TITLE, HARD_SKILL, SOFT_SKILL, EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE. "
        "Do not output LOCATION. "
        "Class definitions: "
        "JOB_TITLE = the written job title or position; "
        "HARD_SKILL = technical skills, tools, programming languages, and methods; "
        "SOFT_SKILL = personal, social, and organizational skills; "
        "EXPERIENCE = required work experience or duration of prior experience, e.g. 'mindestens 2 Jahre Berufserfahrung'; "
        "EDUCATION = degree, training, or field of study; "
        "LANGUAGE = required language skills and proficiency levels; "
        "WORK_MODE = remote, hybrid, onsite, full-time, part-time, student job, and concrete weekly hours. "
        "Important: '20 Stunden pro Woche' must be classified as WORK_MODE, not EXPERIENCE. "
        "Return exactly this JSON object structure with all seven keys and empty lists for absent values: "
        '{"JOB_TITLE": [], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []}. '
        "All values must be lists of strings taken verbatim from the text. "
        "Do not invent information, do not omit categories, and do not add any extra categories. "
        f"Display: {example_display}"
    )

    chat_payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "You return only JSON and nothing else."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 120,
        "response_format": {"type": "json_object"},
    }
    chat_status, chat_body, chat_text = request_json(f"{base_url}/chat/completions", api_key, chat_payload)
    print(f"Used model ID: {model_id}")
    print(f"Chat HTTP status: {chat_status}")

    artifact_dir = ARTIFACT_DIR / "json_test"
    save_artifact(artifact_dir / "input_text.txt", example_display)
    save_artifact(artifact_dir / "prompt.txt", prompt)
    raw_response_text = chat_text if chat_text is not None else json.dumps(chat_body, ensure_ascii=False, indent=2)
    save_artifact(artifact_dir / "raw_model_response.txt", raw_response_text)

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

    parsed_output, parse_error = extract_json_payload(content)
    if parse_error is not None:
        print("Exit code: 5")
        print(f"Error: {parse_error}")
        return 5

    schema_valid, schema_error = validate_schema(parsed_output)
    if not schema_valid:
        print("Exit code: 5")
        print(f"Schema error: {schema_error}")
        return 5

    save_artifact(artifact_dir / "parsed_output.json", json.dumps(parsed_output, ensure_ascii=False, indent=2))
    print("Exit code: 0")
    print("Valid JSON:")
    print(json.dumps(parsed_output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run_json_extraction_test())
