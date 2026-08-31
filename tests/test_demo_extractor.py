"""Tests für die Demo-UI Parsing-Logik – offline, ohne KISSKI-API.

Prüft, dass die Demo ausschließlich vorhandene Pipeline-Logik wiederverwendet
und keine falschen Spans erzeugt.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for p in (str(PROJECT_ROOT), str(SRC_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Import Demo-Extractor
import importlib.util

spec = importlib.util.spec_from_file_location("demo_extractor", PROJECT_ROOT / "demo" / "extractor.py")
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore

normalize = mod.normalize_json_predictions  # type: ignore
group_by_type = mod.group_by_type  # type: ignore
build_result = mod.build_result_payload  # type: ignore
extract = mod.extract_job_ad  # type: ignore
get_status = mod.get_config_status  # type: ignore


def test_normalize_ok():
    text = "Wir suchen einen Softwareentwickler mit Python und SQL in Vollzeit."
    payload = {
        "JOB_TITLE": ["Softwareentwickler"],
        "HARD_SKILL": ["Python", "SQL"],
        "SOFT_SKILL": [],
        "EXPERIENCE": [],
        "EDUCATION": [],
        "LANGUAGE": [],
        "WORK_MODE": ["Vollzeit"],
    }
    preds = normalize(payload, text)
    ok = [p for p in preds if p["status"] == "ok"]
    assert len(ok) == 4
    assert all(p["start"] is not None for p in ok)
    # Prüfe exakteOffsets
    for p in ok:
        assert text[p["start"] : p["end"]] == p["text"]


def test_normalize_hallucinated():
    text = "Hallo Welt"
    payload = {
        "JOB_TITLE": ["NichtImText"],
        "HARD_SKILL": ["Python"],
        "SOFT_SKILL": [],
        "EXPERIENCE": [],
        "EDUCATION": [],
        "LANGUAGE": [],
        "WORK_MODE": [],
    }
    preds = normalize(payload, text)
    assert all(p["status"] == "hallucinated" for p in preds)
    assert all(p["start"] is None for p in preds)


def test_normalize_ambiguous():
    text = "Python und Python sind gefragt. Python ist toll."
    payload = {
        "JOB_TITLE": [],
        "HARD_SKILL": ["Python"],
        "SOFT_SKILL": [],
        "EXPERIENCE": [],
        "EDUCATION": [],
        "LANGUAGE": [],
        "WORK_MODE": [],
    }
    preds = normalize(payload, text)
    # Python kommt 3x vor -> ambiguous
    assert preds[0]["status"] == "ambiguous"
    assert preds[0]["start"] is None


def test_group_by_type():
    preds = [
        {"type": "JOB_TITLE", "text": "A", "start": 0, "end": 1, "status": "ok"},
        {"type": "HARD_SKILL", "text": "B", "start": 2, "end": 3, "status": "ok"},
        {"type": "HARD_SKILL", "text": "C", "start": None, "end": None, "status": "hallucinated"},
    ]
    grouped = group_by_type(preds)
    assert grouped["JOB_TITLE"] == ["A"]
    assert grouped["HARD_SKILL"] == ["B"]  # halluziniert nicht gezählt
    assert grouped["SOFT_SKILL"] == []


def test_build_result_payload_sort_and_meta():
    text = "Softwareentwickler Python Vollzeit"
    parsed = {
        "JOB_TITLE": ["Softwareentwickler"],
        "HARD_SKILL": ["Python"],
        "SOFT_SKILL": [],
        "EXPERIENCE": [],
        "EDUCATION": [],
        "LANGUAGE": [],
        "WORK_MODE": ["Vollzeit"],
    }
    preds = normalize(parsed, text)
    result = build_result(text, parsed, preds, "test-model")
    assert result["meta"]["model"] == "test-model"
    assert result["meta"]["spans_ok"] == 3
    # Spans sortiert nach start
    starts = [s["start"] for s in result["spans"]]
    assert starts == sorted(starts)
    # JSON geordnet nach ALLOWED_TYPES
    assert list(result["json"].keys()) == list(mod.ALLOWED_TYPES)  # type: ignore


def test_extract_validation_empty():
    res, err, diag = extract("   ")
    assert res is None
    assert err is not None
    assert "Bitte geben Sie" in err


def test_extract_validation_short():
    res, err, diag = extract("zu kurz")
    assert res is None
    assert "zu kurz" in err


def test_extract_validation_too_long():
    res, err, diag = extract("a" * 20001)
    assert res is None
    assert "zu lang" in err


def test_get_config_status_no_secret(tmp_path, monkeypatch):
    # Isoliere ENV, damit echte .env nicht global polluted – nutze monkeypatch.setenv
    # statt Datei, damit load_dotenv (override=False) nicht leaked.
    from ie_course import kisski_client as kc
    import os

    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")  # leere Datei, kein Leak
    monkeypatch.setattr(kc, "ENV_FILE", env_file)
    # Setze Config via monkeypatch (wird korrekt restored)
    monkeypatch.setenv("KISSKI_API_KEY", "dummy-key-123")
    monkeypatch.setenv("KISSKI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("KISSKI_MODEL", "dummy-model")

    status = get_status()
    # Darf niemals Key enthalten
    assert "has_key" in status
    assert status.get("api_key") is None
    assert status.get("KISSKI_API_KEY") is None
    # base_url nur gekürzt, kein Plain-Key
    if status.get("base_url"):
        assert "…" in status["base_url"] or len(status["base_url"]) <= 45
    # has_key sollte True sein wegen dummy-key
    assert status["has_key"] is True
    assert status["configured"] is True
    # Sicherstellen, dass nach Test kein Leak bleibt – wird von monkeypatch restored
    # Extra: lösche manuell falls load_dotenv doch gesetzt hat (sollte nicht)
    os.environ.pop("KISSKI_API_KEY", None)
    os.environ.pop("KISSKI_BASE_URL", None)
    os.environ.pop("KISSKI_MODEL", None)


def test_no_traceback_on_invalid_json(tmp_path, monkeypatch):
    # extractor.extract sollte nie Traceback an UI geben, nur Fehlermeldung
    # Isoliere ENV damit echte .env nicht leaked
    from ie_course import kisski_client as kc

    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(kc, "ENV_FILE", env_file)
    monkeypatch.delenv("KISSKI_API_KEY", raising=False)
    monkeypatch.delenv("KISSKI_BASE_URL", raising=False)
    monkeypatch.delenv("KISSKI_MODEL", raising=False)
    # Auch demo_extractor nutzt kc.ENV_FILE – sicherstellen dass es das tmp ist
    # (kc ist bereits gepatched)

    res, err, diag = extract(
        "Wir suchen einen Softwareentwickler (m/w/d) mit Python in Vollzeit und Deutsch C1.",
        api_key_override="",
        base_url_override="",
    )
    assert res is None
    # Fehlermeldung muss user-lesbar sein, kein Traceback
    assert err is not None
    assert "Traceback" not in err
    assert "API-Konfiguration" in err or "fehlt" in err


# --- Truncation / max_tokens Tests (Demo-Schicht) ---

def _isolate_env(tmp_path, monkeypatch):
    """Hilfsfunktion um ENV-Leak zu verhindern (real .env nicht laden)."""
    from ie_course import kisski_client as kc

    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(kc, "ENV_FILE", env_file)
    monkeypatch.delenv("KISSKI_API_KEY", raising=False)
    monkeypatch.delenv("KISSKI_BASE_URL", raising=False)
    monkeypatch.delenv("KISSKI_MODEL", raising=False)


def test_truncation_retry_success(tmp_path, monkeypatch):
    """finish_reason length beim ersten Call -> genau ein Retry mit 2000, dann Erfolg."""
    _isolate_env(tmp_path, monkeypatch)
    calls = []

    def fake_request_json(url, api_key, payload=None):
        calls.append(payload.get("max_tokens") if payload else None)
        # Erster Call: truncated
        if len(calls) == 1:
            assert payload["max_tokens"] == 1500
            return (
                200,
                {
                    "choices": [
                        {
                            "message": {"content": '{"JOB_TITLE": ["Unterminated'},
                            "finish_reason": "length",
                        }
                    ]
                },
                None,
            )
        # Zweiter Call: Erfolg mit stop
        assert payload["max_tokens"] == 2000
        valid_json = '{"JOB_TITLE": ["Softwareentwickler"], "HARD_SKILL": ["Python"], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": ["Vollzeit"]}'
        return (
            200,
            {
                "choices": [
                    {
                        "message": {"content": valid_json},
                        "finish_reason": "stop",
                    }
                ]
            },
            None,
        )

    monkeypatch.setattr(mod, "request_json", fake_request_json)

    text = "Wir suchen einen Softwareentwickler (m/w/d) mit Python in Vollzeit. " * 5
    # muss >20 Zeichen sein, aber wird im Test via fake API beantwortet
    res, err, diag = extract(
        text,
        api_key_override="dummy-key",
        base_url_override="https://example.test/v1",
        model_override="dummy-model",
    )
    assert err is None, f"erwartet Erfolg nach Retry, bekam err={err}"
    assert res is not None
    assert res["json"]["JOB_TITLE"] == ["Softwareentwickler"]
    assert calls == [1500, 2000]


def test_truncation_retry_still_truncated(tmp_path, monkeypatch):
    """Beide Calls length -> verständliche Fehlermeldung, kein Teilresultat."""
    _isolate_env(tmp_path, monkeypatch)

    def fake_request_json(url, api_key, payload=None):
        return (
            200,
            {
                "choices": [
                    {
                        "message": {"content": '{"JOB_TITLE": ["Unterminated'},
                        "finish_reason": "length",
                    }
                ]
            },
            None,
        )

    monkeypatch.setattr(mod, "request_json", fake_request_json)

    text = "Wir suchen einen Softwareentwickler (m/w/d) mit Python in Vollzeit und sehr viel mehr Text " * 10
    res, err, diag = extract(
        text,
        api_key_override="dummy-key",
        base_url_override="https://example.test/v1",
        model_override="dummy-model",
    )
    assert res is None
    assert err is not None
    assert "abgeschnitten" in err.lower()
    assert "token-limit" in err.lower() or "kürzen" in err.lower()
    # niemals Teilresultat
    assert diag is not None


def test_no_retry_on_regular_parse_error(tmp_path, monkeypatch):
    """Echter JSON-Fehler ohne length -> kein Retry, kein zweiter API-Call."""
    _isolate_env(tmp_path, monkeypatch)
    calls = []

    def fake_request_json(url, api_key, payload=None):
        calls.append(1)
        # finish_reason stop, aber Inhalt ist kein gültiges JSON (z.B. Text statt JSON)
        return (
            200,
            {
                "choices": [
                    {
                        "message": {"content": "Ich bin kein JSON, sondern Text."},
                        "finish_reason": "stop",
                    }
                ]
            },
            None,
        )

    monkeypatch.setattr(mod, "request_json", fake_request_json)

    text = "Wir suchen einen Softwareentwickler (m/w/d) mit Python in Vollzeit und viel Text " * 3
    res, err, diag = extract(
        text,
        api_key_override="dummy-key",
        base_url_override="https://example.test/v1",
        model_override="dummy-model",
    )
    assert res is None
    assert err is not None
    assert "kein gültiges json" in err.lower()
    assert len(calls) == 1  # kein Retry


def test_max_tokens_initial_is_1500(tmp_path, monkeypatch):
    """Sicherstellen, dass Demo mit 1500 startet (nicht mehr 700)."""
    _isolate_env(tmp_path, monkeypatch)
    captured = {}

    def fake_request_json(url, api_key, payload=None):
        captured["max_tokens"] = payload.get("max_tokens")
        valid = '{"JOB_TITLE": [], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []}'
        return (
            200,
            {"choices": [{"message": {"content": valid}, "finish_reason": "stop"}]},
            None,
        )

    monkeypatch.setattr(mod, "request_json", fake_request_json)

    text = "Wir suchen einen Softwareentwickler (m/w/d) mit Python in Vollzeit. " * 2
    res, err, diag = extract(
        text,
        api_key_override="k",
        base_url_override="https://example.test/v1",
        model_override="m",
    )
    assert err is None
    assert captured["max_tokens"] == 1500
