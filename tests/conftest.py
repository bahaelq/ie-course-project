"""Shared fixtures for dataset tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture
def isolated_data_dir(tmp_path: Path) -> Iterator[Path]:
    """Provide an isolated data directory with empty split structure."""
    for split in ("example_pool", "gold", "unlabeled"):
        (tmp_path / split / "texts").mkdir(parents=True)
        (tmp_path / split / "annotations").mkdir(parents=True)
        (tmp_path / split / "metadata.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "smoke_test").mkdir()
    return tmp_path


@pytest.fixture
def sample_job_ad_text() -> str:
    return "Wir suchen eine erfahrene Softwareentwicklerin für unser Team in Vollzeit."
