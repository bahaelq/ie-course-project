from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from ie_course.gbert_infer import load_model, predict_entities
from ie_course.llm_client import (
    collect_config,
    configured_client,
    extract_json_payload,
    request_json,
    validate_schema,
)
from ie_course.strict_json import (
    ALLOWED_TYPES,
    build_structuring_prompt,
    normalize_json_predictions,
)

GBERT_MODEL_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "gbert_model"


@lru_cache(maxsize=1)
def _load_gbert():
    return load_model(GBERT_MODEL_DIR)


def gbert_candidates(text: str) -> list[dict[str, Any]]:
    """Local GBERT pass: fast, free, but noisy. Feeds the LLM, isn't the final answer."""
    if not (GBERT_MODEL_DIR / "model.safetensors").exists():
        return []
    model, tokenizer = _load_gbert()
    return predict_entities(text, model, tokenizer)


def group_by_type(predictions: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Group ok predictions by type for the chip view."""
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
    candidate_count: int,
) -> dict[str, Any]:
    """Build the final result displayed by the UI."""
    grouped = group_by_type(predictions)
    spans = [
        {"type": p["type"], "text": p["text"], "start": p["start"], "end": p["end"]}
        for p in predictions
        if p.get("status") == "ok" and p.get("start") is not None
    ]
    spans.sort(key=lambda s: s["start"] or 0)

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
            "gbert_candidates": candidate_count,
        },
    }


def _request_error(status: int, key_name: str) -> tuple[None, str, dict[str, Any]]:
    if status == 599:
        return None, "Network or timeout error. Please try again.", {"status": status}
    if status in (401, 403):
        return None, f"Authentication failed. Please check {key_name}.", {"status": status}
    if status == 429:
        return None, "Rate limit reached (429). Please wait briefly and try again.", {"status": status}
    return None, f"API error ({status}). Please try again later.", {"status": status}


def extract_job_ad(
    text: str,
    *,
    model_override: str | None = None,
    base_url_override: str | None = None,
    api_key_override: str | None = None,
) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None]:
    """Extraction pipeline: GBERT proposes candidate spans, the LLM verifies and
    structures them into the final JSON. Returns (result_payload, error, diagnostics).
    """
    cleaned = text.strip()
    if not cleaned:
        return None, "Please enter a job ad.", None
    if len(cleaned) < 20:
        return None, "The input is too short (minimum 20 characters).", None
    if len(cleaned) > 20000:
        return None, "The input is too long (maximum 20,000 characters).", None

    config, missing = configured_client(
        model=model_override, base_url=base_url_override, api_key=api_key_override
    )
    provider = config.get("provider") or "openai"
    key_name = "CHAT_AI_API_KEY" if provider == "academiccloud" else "OPENAI_API_KEY"
    if missing:
        return (
            None,
            "API configuration is missing: " + ", ".join(missing) + ". Set up .env from .env.example.",
            {"missing": missing},
        )

    base_url = str(config.get("base_url") or "").rstrip("/")
    api_key = str(config.get("api_key") or "")
    model_id = str(config.get("model") or "")
    if not api_key or not base_url:
        return None, "API configuration is incomplete. Please check .env.", {"base_url": base_url}

    candidates = gbert_candidates(cleaned)
    prompt = build_structuring_prompt(cleaned, candidates)

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "Return only JSON and nothing else."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }
    status, body, raw_text = request_json(f"{base_url}/chat/completions", api_key, payload)
    if status >= 400 or body is None:
        return _request_error(status, key_name)

    content = body.get("choices", [{}])[0].get("message", {}).get("content")
    if not content or not str(content).strip():
        return None, "Received an empty response from the model.", {"body": body}

    parsed, parse_err = extract_json_payload(content)
    if parse_err is not None:
        return None, f"Model response was not valid JSON: {parse_err}", {"raw_content": content[:2000]}

    ok, schema_err = validate_schema(parsed)
    if not ok:
        return None, f"Schema error: {schema_err}", {"parsed": parsed}

    predictions = normalize_json_predictions(parsed, cleaned)
    result = build_result_payload(cleaned, parsed, predictions, model_id, len(candidates))
    result["_raw_content"] = content
    return result, None, {"status": status, "model": model_id, "gbert_candidates": len(candidates)}


def match_cv_to_job(cv_text: str, job_text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Ask the LLM whether a candidate's CV fits a job ad.

    Returns ({"fit": bool, "reason": str}, None) on success, or (None, error_message).
    """
    config, missing = configured_client()
    if missing:
        return None, "API configuration is missing: " + ", ".join(missing) + ". Set up .env from .env.example."

    base_url = str(config.get("base_url") or "").rstrip("/")
    api_key = str(config.get("api_key") or "")
    model_id = str(config.get("model") or "")

    prompt = (
        "Compare the candidate's skills and experience in the CV against the "
        "requirements of the job ad. Respond only with JSON in this format: "
        '{"fit": true or false, "reason": "one to two short sentences in English"}.\n\n'
        f"Job ad:\n{job_text}\n\nCV:\n{cv_text}"
    )
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "Return only JSON and nothing else."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    status, body, _raw_text = request_json(f"{base_url}/chat/completions", api_key, payload)
    if status >= 400 or body is None:
        return None, f"API error ({status}). Please try again later."

    content = body.get("choices", [{}])[0].get("message", {}).get("content")
    parsed, parse_err = extract_json_payload(content)
    if parse_err is not None or not isinstance(parsed, dict):
        return None, "Model response was not valid JSON."

    return {"fit": bool(parsed.get("fit")), "reason": str(parsed.get("reason", "")).strip()}, None


def get_config_status() -> dict[str, Any]:
    """Show configuration status without secrets."""
    config, missing = collect_config()
    return {
        "configured": len(missing) == 0,
        "provider": config.get("provider"),
        "missing": missing,
        "base_url": (str(config.get("base_url"))[:40] + "…" if config.get("base_url") else None),
        "model": config.get("model"),
        "has_key": bool(config.get("api_key")),
        "gbert_available": (GBERT_MODEL_DIR / "model.safetensors").exists(),
    }
