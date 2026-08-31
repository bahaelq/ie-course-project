"""Wiederverwendung der bestehenden Information-Extraction-Pipeline für die Demo-UI.

Diese Datei bindet ausschließlich vorhandene Logik an:
- ie_course.kisski_client.collect_config, request_json, extract_json_payload, validate_schema
- Prompt-Logik und Normalisierung aus scripts/evaluate_llm_baseline.py (strict JSON)
Keine neue Extraction-Pipeline, keine Änderung an Gold/Weak/Datasets.

Die UI verwendet exakt dieselben Entity-Typen und dasselbe JSON-Schema,
wie die Evaluation: 7 Keys, Listen von exakten Spans.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Final

# Projekt-Root finden (wie in kisski_client)
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SRC_ROOT: Final[Path] = PROJECT_ROOT / "src"
for p in (str(PROJECT_ROOT), str(SRC_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from ie_course.kisski_client import (  # noqa: E402
    collect_config,
    extract_json_payload,
    request_json,
    validate_schema,
)

ALLOWED_TYPES: Final[tuple[str, ...]] = (
    "JOB_TITLE",
    "HARD_SKILL",
    "SOFT_SKILL",
    "EXPERIENCE",
    "EDUCATION",
    "LANGUAGE",
    "WORK_MODE",
)

# ---------------------------------------------------------------------------
# Prompt – identisch zu evaluate_llm_baseline.build_strict_json_prompt
# ---------------------------------------------------------------------------

def build_strict_json_prompt(example_text: str) -> str:
    """Strenger JSON-Prompt: exakte Spans, kein Paraphrasieren, nur 7 Typen."""
    return (
        "You are a strict extractor for job advertisements. "
        "Copy exact spans from the input text. Never paraphrase, shorten, expand or normalize spans. "
        "Return only valid JSON. "
        "Use exactly these entity types only: JOB_TITLE, HARD_SKILL, SOFT_SKILL, EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE. "
        "Return a JSON object with exactly these keys: JOB_TITLE, HARD_SKILL, SOFT_SKILL, EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE. "
        "Each value must be a list of strings taken verbatim from the text, character-for-character. "
        "If a span is 'Erfahrung im B2B-Verkauf', do not return 'Erfahrung' alone. "
        "If no span for a type, return empty list. "
        "Only the 7 allowed types, no LOCATION/COMPANY. "
        f"Display: {example_text}"
    )


# ---------------------------------------------------------------------------
# Normalisierung – identisch zu evaluate_llm_baseline.normalize_json_predictions
# ---------------------------------------------------------------------------

def normalize_json_predictions(payload: Any, example_text: str) -> list[dict[str, Any]]:
    """Wandelt JSON-Liste in Spans mit start/end um. Halluziniert/ambigu markieren."""
    predictions: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return predictions
    for entity_type in ALLOWED_TYPES:
        values = payload.get(entity_type, [])
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            if not value.strip():
                continue
            positions = [m.start() for m in re.finditer(re.escape(value), example_text)]
            if not positions:
                predictions.append(
                    {"type": entity_type, "text": value, "start": None, "end": None, "status": "hallucinated"}
                )
                continue
            if len(positions) > 1:
                # Bei >1 Vorkommen als ambiguous, außer Frontend kann disambiguieren;
                # wir lassen es als ambiguous, damit Highlighting nicht fälschlich markiert.
                predictions.append(
                    {"type": entity_type, "text": value, "start": None, "end": None, "status": "ambiguous"}
                )
                continue
            start = positions[0]
            predictions.append(
                {"type": entity_type, "text": value, "start": start, "end": start + len(value), "status": "ok"}
            )
    return predictions


def group_by_type(predictions: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Gruppiert ok-Predictions je Typ für die Chip-Ansicht."""
    grouped: dict[str, list[str]] = {t: [] for t in ALLOWED_TYPES}
    for p in predictions:
        if p.get("status") == "ok":
            grouped[p["type"]].append(p["text"])
    return grouped


def build_result_payload(
    text: str,
    parsed: dict[str, Any],
    predictions: list[dict[str, Any]],
    model: str,
) -> dict[str, Any]:
    """Baut das finale Ergebnis, das die UI als JSON anzeigt."""
    grouped = group_by_type(predictions)
    # Spans nur mit ok-Status für Highlighting
    spans = [
        {"type": p["type"], "text": p["text"], "start": p["start"], "end": p["end"]}
        for p in predictions
        if p.get("status") == "ok" and p.get("start") is not None
    ]
    # Sort spans by start for Highlighting
    spans.sort(key=lambda s: s["start"] or 0)

    # Vollständiges JSON wie von Pipeline erzeugt (geordnet)
    ordered_json = {k: parsed.get(k, []) if isinstance(parsed, dict) else [] for k in ALLOWED_TYPES}

    return {
        "entities": grouped,
        "spans": spans,
        "json": ordered_json,
        "meta": {
            "model": model,
            "chars": len(text),
            "spans_ok": len(spans),
            "spans_hallucinated": sum(1 for p in predictions if p.get("status") == "hallucinated"),
            "spans_ambiguous": sum(1 for p in predictions if p.get("status") == "ambiguous"),
        },
    }


# ---------------------------------------------------------------------------
# Hauptfunktion: KISSKI-Aufruf mit vorhandener Client-Logik
# ---------------------------------------------------------------------------

def extract_job_ad(
    text: str,
    *,
    model_override: str | None = None,
    base_url_override: str | None = None,
    api_key_override: str | None = None,
) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None]:
    """Führt die Extraction aus. Returns (result_payload, error_message, diagnostics).

    Nutzt exakt die in scripts/evaluate_llm_baseline.py verwendete Request-Logik.
    """
    cleaned = text.strip()
    if not cleaned:
        return None, "Bitte geben Sie eine Stellenanzeige ein.", None
    if len(cleaned) < 20:
        return None, "Die Eingabe ist zu kurz. Bitte fügen Sie eine vollständige Stellenanzeige ein (mind. 20 Zeichen).", None
    if len(cleaned) > 20000:
        return None, "Die Eingabe ist zu lang (max. 20.000 Zeichen). Bitte kürzen Sie den Text.", None

    # Config laden – wiederverwendet collect_config aus kisski_client
    config, missing = collect_config()
    # Overrides für Tests/Demo
    if model_override is not None:
        config["model"] = model_override
    if base_url_override is not None:
        config["base_url"] = base_url_override
    if api_key_override is not None:
        config["api_key"] = api_key_override
    # Nach Overrides fehlende erneut prüfen
    if base_url_override is not None or api_key_override is not None or model_override is not None:
        missing = []
        if not config.get("api_key"):
            missing.append("KISSKI_API_KEY")
        if not config.get("base_url"):
            missing.append("KISSKI_BASE_URL")
    if missing:
        return None, (
            "API-Konfiguration fehlt: " + ", ".join(missing) +
            ". Bitte .env mit KISSKI_API_KEY und KISSKI_BASE_URL einrichten (siehe .env.example)."
        ), {"missing": missing}

    base_url = str(config.get("base_url") or "").rstrip("/")
    api_key = str(config.get("api_key") or "")
    model_id = str(config.get("model") or "")

    if not api_key or not base_url:
        return None, "API-Konfiguration unvollständig. Bitte .env prüfen.", {"base_url": base_url}

    # Modell-Auflösung wie in evaluate_llm_baseline
    if not model_id:
        status, body, _raw = request_json(f"{base_url}/models", api_key)
        if status >= 400 or not body:
            return None, "Konnte Modell-Liste nicht abrufen. Bitte KISSKI_BASE_URL prüfen.", {"status": status}
        available = [item.get("id") for item in body.get("data", []) if item.get("id")]
        if not available:
            return None, "Keine Modelle von KISSKI zurückgegeben.", None
        model_id = available[0]

    prompt = build_strict_json_prompt(cleaned)

    # Token-Limits: 1500 für Demo (Evaluation nutzt 400/600 für kurze Gold-Texte,
    # Demo muss aber lange PDF-Uploads bis 8 MB abdecken; 1500 ist konservativ
    # sicher für 95% der Fälle, 2000 als einmaliger Retry für Extremfälle).
    INITIAL_MAX_TOKENS = 1500
    RETRY_MAX_TOKENS = 2000

    def _build_payload(max_tokens: int) -> dict[str, Any]:
        return {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "Return only JSON and nothing else."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

    def _call_with_http_retry(payload_dict: dict[str, Any]) -> tuple[int, dict | None, str | None]:
        """HTTP-Retry nur für transiente Fehler (429/500...), nicht für JSON-Truncation."""
        RETRYABLE = {429, 500, 502, 503, 504, 599}
        max_retries = 2
        import time as _time
        import random as _random

        rng = _random.Random()
        status_local, body_local, raw_local = 599, None, None  # type: ignore
        for attempt in range(1, max_retries + 1):
            status_local, body_local, raw_local = request_json(
                f"{base_url}/chat/completions", api_key, payload_dict
            )
            if status_local < 400 and body_local is not None:
                break
            if status_local not in RETRYABLE or attempt == max_retries:
                break
            sleep = 0.8 * (2 ** (attempt - 1)) + rng.uniform(0, 0.4)
            _time.sleep(sleep)
        return status_local, body_local, raw_local

    def _finish_reason(body_dict: dict | None) -> str | None:
        try:
            return body_dict.get("choices", [{}])[0].get("finish_reason")  # type: ignore
        except Exception:
            return None

    # Erster Versuch mit INITIAL_MAX_TOKENS
    payload = _build_payload(INITIAL_MAX_TOKENS)
    status, body, raw_text = _call_with_http_retry(payload)

    if status >= 400 or body is None:
        if status == 599:
            return None, f"Netzwerk-/Timeout-Fehler ({status}). Bitte erneut versuchen.", {"status": status, "raw": raw_text}
        if status in (401, 403):
            return None, "Authentifizierung fehlgeschlagen. Bitte KISSKI_API_KEY prüfen.", {"status": status}
        if status == 429:
            return None, "Rate Limit erreicht (429). Bitte kurz warten und erneut versuchen.", {"status": status}
        return None, f"API-Fehler ({status}). Bitte später erneut versuchen.", {"status": status, "raw": raw_text}

    # Prüfe truncation via finish_reason vor JSON-Parsing – genau ein Retry mit höherem Limit
    finish = _finish_reason(body)
    if finish == "length":
        # Ein einziger sicherer Retry mit RETRY_MAX_TOKENS, kein endlos-Loop, keine Reparatur
        payload_retry = _build_payload(RETRY_MAX_TOKENS)
        status_r, body_r, raw_r = _call_with_http_retry(payload_retry)
        if status_r >= 400 or body_r is None:
            if status_r == 599:
                return None, f"Netzwerk-/Timeout-Fehler ({status_r}). Bitte erneut versuchen.", {"status": status_r, "raw": raw_r}
            if status_r in (401, 403):
                return None, "Authentifizierung fehlgeschlagen. Bitte KISSKI_API_KEY prüfen.", {"status": status_r}
            if status_r == 429:
                return None, "Rate Limit erreicht (429). Bitte kurz warten und erneut versuchen.", {"status": status_r}
            return None, f"API-Fehler ({status_r}). Bitte später erneut versuchen.", {"status": status_r, "raw": raw_r}
        # Wenn auch Retry wieder truncated, ehrlich abbrechen – niemals Teilresultate zeigen
        finish_retry = _finish_reason(body_r)
        if finish_retry == "length":
            return (
                None,
                "Die Modell-Antwort wurde abgeschnitten (Token-Limit erreicht). Bitte kürzen Sie die Stellenanzeige oder versuchen Sie es erneut.",
                {"finish_reason": "length", "max_tokens": RETRY_MAX_TOKENS, "raw_content": (body_r.get("choices", [{}])[0].get("message", {}).get("content") or "")[:2000]},
            )
        # Retry erfolgreich (finish != length) → verwende Retry-Body
        status, body, raw_text = status_r, body_r, raw_r

    content = body.get("choices", [{}])[0].get("message", {}).get("content") if body else None
    if content is None or not str(content).strip():
        return None, "Leere Antwort vom Modell erhalten.", {"body": body}

    parsed, parse_err = extract_json_payload(content)
    if parse_err is not None:
        # Nur bei Truncation (finish==length) hätten wir bereits retry gemacht.
        # Für alle anderen Parse-Fehler (z.B. echter Modell-Fehler) kein erneuter API-Call,
        # keine automatische JSON-Reparatur, niemals Teilresultate.
        # Wenn Parse-Fehler nach Retry trotzdem "Unterminated string" enthält und finish war length,
        # gib verständliche Meldung statt technischem Detail.
        finish_now = _finish_reason(body)
        if finish_now == "length" or "Unterminated string" in parse_err:
            # Falls wir hier landen, war es Truncation ohne erfolgreichen Retry (z.B. finish fehlte initial)
            # Keine zweite Retry-Schleife – direkt verständliche Meldung
            if finish_now == "length":
                return (
                    None,
                    "Die Modell-Antwort wurde abgeschnitten (Token-Limit erreicht). Bitte kürzen Sie die Stellenanzeige oder versuchen Sie es erneut.",
                    {"finish_reason": finish_now, "raw_content": content[:2000]},
                )
        return None, f"Modell-Antwort war kein gültiges JSON: {parse_err}", {"raw_content": content[:2000]}

    ok, schema_err = validate_schema(parsed)
    if not ok:
        return None, f"Schema-Fehler: {schema_err}", {"parsed": parsed}

    predictions = normalize_json_predictions(parsed, cleaned)
    result = build_result_payload(cleaned, parsed, predictions, model_id)
    # Für Copy: formatted JSON string
    result["_raw_content"] = content
    return result, None, {"status": status, "model": model_id}


def get_config_status() -> dict[str, Any]:
    """Für /api/config – zeigt ob KISSKI erreichbar ist, ohne Secrets zu leaken."""
    config, missing = collect_config()
    return {
        "configured": len(missing) == 0,
        "missing": missing,
        "base_url": (str(config.get("base_url"))[:40] + "…" if config.get("base_url") else None),
        "model": config.get("model"),
        "has_key": bool(config.get("api_key")),
    }
