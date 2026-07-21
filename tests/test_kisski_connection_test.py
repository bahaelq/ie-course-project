import importlib.util
import sys
from pathlib import Path

from ie_course import kisski_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MODULE_PATH = PROJECT_ROOT / "scripts" / "kisski_connection_test.py"
SPEC = importlib.util.spec_from_file_location("kisski_connection_test", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

collect_config = module.collect_config


def test_collect_config_reports_missing_api_key(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KISSKI_BASE_URL=https://example.test/v1\n", encoding="utf-8")
    monkeypatch.setattr(kisski_client, "ENV_FILE", env_file)
    monkeypatch.delenv("KISSKI_API_KEY", raising=False)
    monkeypatch.delenv("KISSKI_BASE_URL", raising=False)

    config, missing = collect_config()

    assert "KISSKI_API_KEY" in missing
    assert config["api_key"] is None or config["api_key"] == ""


def test_collect_config_reports_missing_base_url(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KISSKI_API_KEY=secret\n", encoding="utf-8")
    monkeypatch.setattr(kisski_client, "ENV_FILE", env_file)
    monkeypatch.delenv("KISSKI_API_KEY", raising=False)
    monkeypatch.delenv("KISSKI_BASE_URL", raising=False)

    config, missing = collect_config()

    assert "KISSKI_BASE_URL" in missing
    assert config["base_url"] is None or config["base_url"] == ""


def test_collect_config_model_is_optional(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KISSKI_API_KEY=secret\nKISSKI_BASE_URL=https://example.test/v1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kisski_client, "ENV_FILE", env_file)
    monkeypatch.delenv("KISSKI_API_KEY", raising=False)
    monkeypatch.delenv("KISSKI_BASE_URL", raising=False)

    config, missing = collect_config()

    assert "KISSKI_MODEL" not in missing
    assert config["model"] is None or config["model"] == ""


def test_collect_config_loads_values(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KISSKI_API_KEY=test-key\nKISSKI_BASE_URL=https://example.test/v1\nKISSKI_MODEL=demo\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kisski_client, "ENV_FILE", env_file)
    monkeypatch.delenv("KISSKI_API_KEY", raising=False)
    monkeypatch.delenv("KISSKI_BASE_URL", raising=False)

    config, missing = collect_config()

    assert config["api_key"] == "test-key"
    assert config["base_url"] == "https://example.test/v1"
    assert config["model"] == "demo"
    assert missing == []


def test_collect_config_missing_env_file(monkeypatch) -> None:
    monkeypatch.setattr(kisski_client, "ENV_FILE", Path("/nonexistent/.env"))

    config, missing = collect_config()

    assert "pyproject" not in missing
    assert "env" in missing
