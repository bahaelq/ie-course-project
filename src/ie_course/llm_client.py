#!/usr/bin/env python3
"""Shared helpers for OpenAI-compatible language model APIs."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Final

from dotenv import dotenv_values


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return current


PROJECT_ROOT: Final[Path] = find_project_root(Path(__file__).resolve())
ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"
ARTIFACT_DIR: Final[Path] = PROJECT_ROOT / "artifacts" / "llm_test"
DEFAULT_EXAMPLE_DISPLAY: Final[str] = "Working student in data science, 20 hours per week, Berlin."
CHAT_AI_BASE_URL: Final[str] = "https://chat-ai.academiccloud.de/v1"
OPENAI_BASE_URL: Final[str] = "https://api.openai.com/v1"


def collect_config() -> tuple[dict[str, str | None], list[str]]:
    pyproject_file = PROJECT_ROOT / "pyproject.toml"
    if not pyproject_file.exists():
        return {}, ["pyproject"]

    values = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}

    def setting(name: str) -> str | None:
        value = os.environ.get(name, values.get(name) or "").strip()
        return value or None

    provider = (setting("AI_PROVIDER") or "openai").lower()
    if provider == "academiccloud":
        config = {
            "provider": provider,
            "api_key": setting("CHAT_AI_API_KEY"),
            "base_url": CHAT_AI_BASE_URL,
            "model": setting("CHAT_AI_MODEL"),
        }
    elif provider == "openai":
        config = {
            "provider": provider,
            "api_key": setting("OPENAI_API_KEY"),
            "base_url": OPENAI_BASE_URL,
            "model": setting("OPENAI_MODEL"),
        }
    else:
        return {"provider": provider}, ["AI_PROVIDER (openai or academiccloud)"]

    missing = missing_config(config)
    if not ENV_FILE.exists() and not any(
        os.environ.get(name) for name in ("OPENAI_API_KEY", "CHAT_AI_API_KEY")
    ):
        return config, ["env"]
    return config, missing


def missing_config(config: dict[str, str | None]) -> list[str]:
    provider = config.get("provider") or "openai"
    names = {
        "openai": ("OPENAI_API_KEY", "OPENAI_MODEL"),
        "academiccloud": ("CHAT_AI_API_KEY", "CHAT_AI_MODEL"),
    }
    if provider not in names:
        return ["AI_PROVIDER (openai or academiccloud)"]
    api_key_name, model_name = names[provider]
    return [
        name
        for name, value in (
            (api_key_name, config.get("api_key")),
            (model_name, config.get("model")),
            ("base_url", config.get("base_url")),
        )
        if not value
    ]


def configured_client(
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> tuple[dict[str, str | None], list[str]]:
    config, missing = collect_config()
    overrides = {"model": model, "base_url": base_url, "api_key": api_key}
    if any(value is not None for value in overrides.values()):
        config.update({name: value for name, value in overrides.items() if value is not None})
        missing = missing_config(config)
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
    except Exception as exc:  
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
