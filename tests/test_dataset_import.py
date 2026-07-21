"""Tests for dataset import and split logic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

# Patch DATA_DIR before importing the script module
import importlib.util
import sys

SCRIPT_PATH = PROJECT_ROOT / "scripts" / "import_job_ad.py"
SPEC = importlib.util.spec_from_file_location("import_job_ad", SCRIPT_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
# Override DATA_DIR for testing
mod.DATA_DIR = PROJECT_ROOT  # will be overridden in tests via monkeypatch
SPEC.loader.exec_module(mod)

normalize_text = mod.normalize_text
text_content_key = mod.text_content_key
find_duplicate_id = mod.find_duplicate_id
find_duplicate_text = mod.find_duplicate_text
get_next_id = mod.get_next_id
do_import = mod.do_import


# ---- normalize_text ----

class TestNormalizeText:
    def test_strips_trailing_whitespace(self) -> None:
        assert normalize_text("Hallo Welt\n\n") == "Hallo Welt\n"

    def test_replaces_internal_newlines(self) -> None:
        assert normalize_text("Zeile 1\nZeile 2") == "Zeile 1 Zeile 2\n"

    def test_replaces_crlf(self) -> None:
        assert normalize_text("A\r\nB") == "A B\n"

    def test_replaces_cr(self) -> None:
        assert normalize_text("A\rB") == "A B\n"

    def test_empty_strips(self) -> None:
        assert normalize_text("   ") == "\n"

    def test_already_normalized(self) -> None:
        assert normalize_text("Ein Satz.") == "Ein Satz.\n"

    def test_multi_newline(self) -> None:
        assert normalize_text("A\n\n\nB") == "A B\n"


# ---- text_content_key ----

class TestTextContentKey:
    def test_ignores_trailing_newline(self) -> None:
        assert text_content_key("a\n") == text_content_key("a")

    def test_preserves_different_content(self) -> None:
        assert text_content_key("a") != text_content_key("b")


# ---- Duplicate detection ----

class TestFindDuplicateId:
    def test_returns_none_when_unique(self, monkeypatch: pytest.MonkeyPatch,
                                       tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        (tmp_path / "example_pool" / "texts").mkdir(parents=True)
        assert find_duplicate_id("job_ad_9999") is None

    def test_finds_existing_id(self, monkeypatch: pytest.MonkeyPatch,
                               tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        texts = tmp_path / "gold" / "texts"
        texts.mkdir(parents=True)
        (texts / "job_ad_1001.txt").write_text("test", encoding="utf-8")
        assert find_duplicate_id("job_ad_1001") == "gold"


class TestFindDuplicateText:
    def test_detects_identical_text(self, monkeypatch: pytest.MonkeyPatch,
                                    tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        texts = tmp_path / "example_pool" / "texts"
        texts.mkdir(parents=True)
        (texts / "job_ad_1001.txt").write_text("Hello World\n", encoding="utf-8")
        result = find_duplicate_text("Hello World\n")
        assert result is not None
        split, eid = result
        assert split == "example_pool"
        assert eid == "job_ad_1001"

    def test_ignores_different_text(self, monkeypatch: pytest.MonkeyPatch,
                                    tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        texts = tmp_path / "example_pool" / "texts"
        texts.mkdir(parents=True)
        (texts / "job_ad_1001.txt").write_text("Hello World\n", encoding="utf-8")
        assert find_duplicate_text("Goodbye World\n") is None

    def test_excludes_self(self, monkeypatch: pytest.MonkeyPatch,
                           tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        texts = tmp_path / "example_pool" / "texts"
        texts.mkdir(parents=True)
        (texts / "job_ad_1001.txt").write_text("Hello World\n", encoding="utf-8")
        result = find_duplicate_text("Hello World\n", exclude_split="example_pool",
                                     exclude_id="job_ad_1001")
        assert result is None


# ---- get_next_id ----

class TestGetNextId:
    def test_starts_at_1001(self, monkeypatch: pytest.MonkeyPatch,
                            tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        assert get_next_id() == "job_ad_1001"

    def test_increments_from_existing(self, monkeypatch: pytest.MonkeyPatch,
                                      tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        texts = tmp_path / "example_pool" / "texts"
        texts.mkdir(parents=True)
        (texts / "job_ad_1005.txt").write_text("test", encoding="utf-8")
        assert get_next_id() == "job_ad_1006"


# ---- Import flow ----

class TestImportFlow:
    def make_source(self, tmp_path: Path, content: str = "Test anzeige text.") -> Path:
        src = tmp_path / "source.txt"
        src.write_text(content, encoding="utf-8")
        return src

    def test_basic_import(self, monkeypatch: pytest.MonkeyPatch,
                          tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        src = self.make_source(tmp_path)
        (tmp_path / "example_pool" / "texts").mkdir(parents=True)
        (tmp_path / "example_pool" / "metadata.jsonl").write_text("", encoding="utf-8")

        class Args:
            input = str(src)
            split = "example_pool"
            id = "job_ad_2001"
            source_name = "Test"
            source_url = "https://example.com"
            retrieved_at = "2026-07-21"
            job_title = "Teststelle"
            company = "Firma"
            notes = "Import-Test"

        rc = do_import(Args)  # type: ignore
        assert rc == 0

        target = tmp_path / "example_pool" / "texts" / "job_ad_2001.txt"
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "Test anzeige text.\n"

        meta = (tmp_path / "example_pool" / "metadata.jsonl").read_text(encoding="utf-8").strip()
        entry = json.loads(meta)
        assert entry["id"] == "job_ad_2001"
        assert entry["split"] == "example_pool"

    def test_rejects_duplicate_id(self, monkeypatch: pytest.MonkeyPatch,
                                  tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        src = self.make_source(tmp_path)
        texts = tmp_path / "gold" / "texts"
        texts.mkdir(parents=True)
        (texts / "job_ad_3001.txt").write_text("existing", encoding="utf-8")

        class Args:
            input = str(src)
            split = "gold"
            id = "job_ad_3001"
            source_name = ""
            source_url = ""
            retrieved_at = ""
            job_title = ""
            company = ""
            notes = ""

        rc = do_import(Args)  # type: ignore
        assert rc == 1

    def test_rejects_duplicate_text(self, monkeypatch: pytest.MonkeyPatch,
                                    tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        existing_text = "Du hast mich schon.\n"
        texts = tmp_path / "example_pool" / "texts"
        texts.mkdir(parents=True)
        (texts / "job_ad_4001.txt").write_text(existing_text, encoding="utf-8")

        src = tmp_path / "new.txt"
        src.write_text(existing_text, encoding="utf-8")

        (tmp_path / "gold" / "texts").mkdir(parents=True)

        class Args:
            input = str(src)
            split = "gold"
            id = "job_ad_4002"
            source_name = ""
            source_url = ""
            retrieved_at = ""
            job_title = ""
            company = ""
            notes = ""

        rc = do_import(Args)  # type: ignore
        assert rc == 1

    def test_rejects_invalid_split(self, monkeypatch: pytest.MonkeyPatch,
                                   tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)

        class Args:
            split = "smoke_test"
            input = "/nonexistent"
            id = ""
            source_name = ""
            source_url = ""
            retrieved_at = ""
            job_title = ""
            company = ""
            notes = ""

        rc = do_import(Args)  # type: ignore
        assert rc == 1

    def test_rejects_empty_file(self, monkeypatch: pytest.MonkeyPatch,
                                tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        src = tmp_path / "empty.txt"
        src.write_text("   \n", encoding="utf-8")

        (tmp_path / "unlabeled" / "texts").mkdir(parents=True)

        class Args:
            input = str(src)
            split = "unlabeled"
            id = "job_ad_5001"
            source_name = ""
            source_url = ""
            retrieved_at = ""
            job_title = ""
            company = ""
            notes = ""

        rc = do_import(Args)  # type: ignore
        assert rc == 1

    def test_atomic_rollback_on_meta_failure(self, monkeypatch: pytest.MonkeyPatch,
                                             tmp_path: Path) -> None:
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        src = self.make_source(tmp_path)
        texts = tmp_path / "example_pool" / "texts"
        texts.mkdir(parents=True)

        # Make metadata.jsonl unwritable by replacing it with a directory
        meta = tmp_path / "example_pool" / "metadata.jsonl"
        meta.write_text("", encoding="utf-8")
        meta.unlink()
        meta.mkdir()

        class Args:
            input = str(src)
            split = "example_pool"
            id = "job_ad_6001"
            source_name = ""
            source_url = ""
            retrieved_at = ""
            job_title = ""
            company = ""
            notes = ""

        rc = do_import(Args)  # type: ignore
        assert rc == 1
        # Text file must NOT exist after rollback
        assert not (texts / "job_ad_6001.txt").exists()
