#!/usr/bin/env python3
"""Minimal connection test for a KISSKI-compatible chat AI endpoint."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (str(PROJECT_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from ie_course.kisski_client import (
    collect_config,
    request_json,
)


def run_connection_test() -> int:
    print("=== Connection Test ===")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Expected .env path: {PROJECT_ROOT / '.env'}")
    print(f".env exists: {'yes' if (PROJECT_ROOT / '.env').exists() else 'no'}")

    config, missing = collect_config()
    if missing:
        print("HTTP status: n/a")
        print("Exit code: 1")
        print("Error: missing required values in .env")
        return 1

    base_url = str(config["base_url"]).rstrip("/")
    api_key = str(config["api_key"])

    models_url = f"{base_url}/models"
    status, response_body, response_text = request_json(models_url, api_key)
    print(f"HTTP status: {status}")

    if status >= 400 or response_body is None:
        print("Exit code: 3")
        print("Error: /models request failed")
        if response_text:
            print(response_text)
        return 3

    available_models = [item.get("id") for item in response_body.get("data", []) if item.get("id")]
    if not available_models:
        print("Exit code: 4")
        print("Error: no model IDs returned")
        return 4

    print("Used model ID: ", available_models[0])
    print("Exit code: 0")
    return 0


if __name__ == "__main__":
    sys.exit(run_connection_test())
