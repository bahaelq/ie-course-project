#!/usr/bin/env python3
"""Evaluate plain JSON and marker prompts on the five controlled example ads."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SRC_ROOT: Final[Path] = PROJECT_ROOT / "src"
for path in (str(PROJECT_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from ie_course.kisski_client import (
    collect_config,
    extract_json_payload,
    request_json,
    save_artifact,
    validate_marker_output,
)
from validate_example_annotations import validate_annotations_data

EXAMPLES_DIR: Final[Path] = PROJECT_ROOT / "data" / "smoke_test"
GOLD_DIR: Final[Path] = EXAMPLES_DIR / "annotations"
OUTPUT_DIR: Final[Path] = PROJECT_ROOT / "artifacts" / "prompt_baseline_evaluation"
ALLOWED_TYPES: Final[tuple[str, ...]] = (
    "JOB_TITLE",
    "HARD_SKILL",
    "SOFT_SKILL",
    "EXPERIENCE",
    "EDUCATION",
    "LANGUAGE",
    "WORK_MODE",
)


def load_examples() -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for text_path in sorted(EXAMPLES_DIR.glob("job_ad_*.txt")):
        stem = text_path.stem
        gold_path = GOLD_DIR / f"{stem}.json"
        examples.append(
            {
                "id": stem,
                "text": text_path.read_text(encoding="utf-8"),
                "gold": json.loads(gold_path.read_text(encoding="utf-8")),
            }
        )
    return examples


def build_plain_json_prompt(example_text: str) -> str:
    return (
        "You are a strict extractor for job advertisements. "
        "Return only valid JSON. "
        "Use exactly these entity types only: JOB_TITLE, HARD_SKILL, SOFT_SKILL, EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE. "
        "Return a JSON object with exactly these keys: JOB_TITLE, HARD_SKILL, SOFT_SKILL, EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE. "
        "Each value must be a list of strings taken verbatim from the text. "
        "Do not invent information or add extra categories. "
        f"Display: {example_text}"
    )


def build_marker_prompt(example_text: str) -> str:
    return (
        "You are a strict marker-based extractor for job advertisements. "
        "Return only the marked text. "
        "Use only these marker types: @@JOB_TITLE{...}##, @@HARD_SKILL{...}##, @@SOFT_SKILL{...}##, @@EXPERIENCE{...}##, @@EDUCATION{...}##, @@LANGUAGE{...}##, @@WORK_MODE{...}##. "
        "Do not output LOCATION or COMPANY. "
        "Keep the rest of the text fully intact and in the same order. "
        "Only mark text spans that appear exactly in the input. "
        "Do not invent information. "
        f"Display: {example_text}"
    )


def normalize_json_predictions(payload: Any, example_text: str) -> list[dict[str, Any]]:
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
            positions = [match.start() for match in re.finditer(re.escape(value), example_text)]
            if not positions:
                predictions.append({"type": entity_type, "text": value, "start": None, "end": None, "status": "hallucinated"})
                continue
            if len(positions) > 1:
                predictions.append({"type": entity_type, "text": value, "start": None, "end": None, "status": "ambiguous"})
                continue
            start = positions[0]
            predictions.append({"type": entity_type, "text": value, "start": start, "end": start + len(value), "status": "ok"})
    return predictions


def normalize_marker_predictions(content: str, example_text: str) -> list[dict[str, Any]]:
    valid, spans, error, _ = validate_marker_output(content, example_text)
    if not valid:
        return [{"type": "INVALID_OUTPUT", "text": content, "start": None, "end": None, "status": "invalid_output"}]
    predictions: list[dict[str, Any]] = []
    for item in spans:
        span_type = str(item["type"])
        span_text = str(item["content"])
        positions = [match.start() for match in re.finditer(re.escape(span_text), example_text)]
        if not positions:
            predictions.append({"type": span_type, "text": span_text, "start": None, "end": None, "status": "hallucinated"})
            continue
        if len(positions) > 1:
            predictions.append({"type": span_type, "text": span_text, "start": None, "end": None, "status": "ambiguous"})
            continue
        start = positions[0]
        predictions.append({"type": span_type, "text": span_text, "start": start, "end": start + len(span_text), "status": "ok"})
    return predictions


def build_gold_entities(gold_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": entity["type"],
            "text": entity["text"],
            "start": entity["start"],
            "end": entity["end"],
        }
        for entity in gold_payload.get("entities", [])
    ]


def compute_metrics(predictions: list[dict[str, Any]], gold_entities: list[dict[str, Any]]) -> dict[str, Any]:
    gold_keys = {(item["type"], item["start"], item["end"]): item for item in gold_entities}
    pred_keys = {(item["type"], item["start"], item["end"]): item for item in predictions if item.get("start") is not None and item.get("end") is not None}

    tp = 0
    fp = 0
    fn = 0
    for key in pred_keys:
        if key in gold_keys:
            tp += 1
        else:
            fp += 1
    for key in gold_keys:
        if key not in pred_keys:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def compute_metrics_by_type(predictions: list[dict[str, Any]], gold_entities: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    gold_by_type: dict[str, list[dict[str, Any]]] = {entity_type: [] for entity_type in ALLOWED_TYPES}
    for entity in gold_entities:
        gold_by_type[entity["type"]].append(entity)

    for entity_type in ALLOWED_TYPES:
        gold_items = gold_by_type[entity_type]
        pred_items = [item for item in predictions if item.get("type") == entity_type and item.get("start") is not None and item.get("end") is not None]
        gold_keys = {(item["type"], item["start"], item["end"]): item for item in gold_items}
        pred_keys = {(item["type"], item["start"], item["end"]): item for item in pred_items}
        tp = sum(1 for key in pred_keys if key in gold_keys)
        fp = len(pred_keys) - tp
        fn = len(gold_keys) - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        result[entity_type] = {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}
    return result


def compare_predictions_to_gold(example_id: str, prompt_name: str, predictions: list[dict[str, Any]], gold_entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for prediction in predictions:
        status = prediction.get("status")
        if status == "hallucinated":
            errors.append({"id": example_id, "prompt": prompt_name, "error_type": "hallucinated_entity", "type": prediction.get("type"), "text": prediction.get("text")})
        elif status == "ambiguous":
            errors.append({"id": example_id, "prompt": prompt_name, "error_type": "ambiguous_text_match", "type": prediction.get("type"), "text": prediction.get("text")})
        elif status == "invalid_output":
            errors.append({"id": example_id, "prompt": prompt_name, "error_type": "invalid_output", "type": prediction.get("type"), "text": prediction.get("text")})
            continue
        elif prediction.get("start") is None or prediction.get("end") is None:
            continue
        else:
            exact_match = any(
                prediction.get("type") == gold.get("type") and prediction.get("start") == gold.get("start") and prediction.get("end") == gold.get("end")
                for gold in gold_entities
            )
            if exact_match:
                continue
            same_text = [gold for gold in gold_entities if gold.get("text") == prediction.get("text")]
            same_type = [gold for gold in same_text if gold.get("type") == prediction.get("type")]
            if same_type:
                errors.append({"id": example_id, "prompt": prompt_name, "error_type": "wrong_boundary", "type": prediction.get("type"), "text": prediction.get("text")})
            elif same_text:
                errors.append({"id": example_id, "prompt": prompt_name, "error_type": "wrong_type", "type": prediction.get("type"), "text": prediction.get("text")})
            else:
                errors.append({"id": example_id, "prompt": prompt_name, "error_type": "hallucinated_entity", "type": prediction.get("type"), "text": prediction.get("text")})

    for gold in gold_entities:
        gold_key = (gold.get("type"), gold.get("start"), gold.get("end"))
        if not any(
            prediction.get("start") is not None and prediction.get("end") is not None and (prediction.get("type"), prediction.get("start"), prediction.get("end")) == gold_key
            for prediction in predictions
        ):
            errors.append({"id": example_id, "prompt": prompt_name, "error_type": "missed_entity", "type": gold.get("type"), "text": gold.get("text")})
    return errors


def run_evaluation() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    examples = load_examples()
    ok, validation_errors, warnings, _ = validate_annotations_data()
    if not ok:
        print("Annotation validation failed; stopping before API calls")
        for error in validation_errors:
            print(f"- {error}")
        return 1
    if warnings:
        print("Annotation validation warnings:")
        for warning in warnings:
            print(f"- {warning}")

    config, missing = collect_config()
    if missing:
        print("Missing configuration")
        return 1

    base_url = str(config["base_url"]).rstrip("/")
    api_key = str(config["api_key"])
    model_id = str(config["model"] or "")
    models_status, models_body, _ = request_json(f"{base_url}/models", api_key)
    if models_status >= 400 or models_body is None:
        print("Unable to reach /models endpoint")
        return 1
    available_models = [item.get("id") for item in models_body.get("data", []) if item.get("id")]
    if not available_models:
        print("No model IDs returned")
        return 1
    if not model_id:
        model_id = available_models[0]

    api_calls = 0
    predictions_json: list[dict[str, Any]] = []
    predictions_marker: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    per_example_results: list[dict[str, Any]] = []

    for example in examples:
        example_id = example["id"]
        example_text = example["text"]
        gold_entities = build_gold_entities(example["gold"])

        plain_prompt = build_plain_json_prompt(example_text)
        plain_payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "Return only JSON and nothing else."},
                {"role": "user", "content": plain_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 220,
            "response_format": {"type": "json_object"},
        }
        status, body, raw_text = request_json(f"{base_url}/chat/completions", api_key, plain_payload)
        api_calls += 1
        if status >= 400 or not body:
            errors.append({"id": example_id, "prompt": "json", "error_type": "invalid_output", "message": raw_text or "request failed"})
            predictions_json.append({"id": example_id, "predictions": []})
        else:
            content = body.get("choices", [{}])[0].get("message", {}).get("content")
            parsed, parse_error = extract_json_payload(content)
            if parse_error is not None:
                errors.append({"id": example_id, "prompt": "json", "error_type": "invalid_output", "message": parse_error})
                predictions_json.append({"id": example_id, "predictions": []})
            else:
                normalized = normalize_json_predictions(parsed, example_text)
                predictions_json.append({"id": example_id, "predictions": normalized})
                errors.extend(compare_predictions_to_gold(example_id, "json", normalized, gold_entities))

        marker_prompt = build_marker_prompt(example_text)
        marker_payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "Return only the marked text and nothing else."},
                {"role": "user", "content": marker_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 220,
        }
        status, body, raw_text = request_json(f"{base_url}/chat/completions", api_key, marker_payload)
        api_calls += 1
        if status >= 400 or not body:
            errors.append({"id": example_id, "prompt": "marker", "error_type": "invalid_output", "message": raw_text or "request failed"})
            predictions_marker.append({"id": example_id, "predictions": []})
        else:
            content = body.get("choices", [{}])[0].get("message", {}).get("content")
            normalized = normalize_marker_predictions(content, example_text)
            predictions_marker.append({"id": example_id, "predictions": normalized})
            errors.extend(compare_predictions_to_gold(example_id, "marker", normalized, gold_entities))

        plain_metrics = compute_metrics(
            [item for item in predictions_json[-1].get("predictions", []) if item.get("start") is not None and item.get("end") is not None],
            gold_entities,
        )
        marker_metrics = compute_metrics(
            [item for item in predictions_marker[-1].get("predictions", []) if item.get("start") is not None and item.get("end") is not None],
            gold_entities,
        )
        per_example_results.append({"id": example_id, "json": plain_metrics, "marker": marker_metrics})

    combined_gold_entities = [entity for example in examples for entity in build_gold_entities(example["gold"])]
    combined_json_predictions = [prediction for example in predictions_json for prediction in example.get("predictions", [])]
    combined_marker_predictions = [prediction for example in predictions_marker for prediction in example.get("predictions", [])]

    summary = {
        "api_calls": api_calls,
        "json": {
            "micro": compute_metrics(combined_json_predictions, combined_gold_entities),
            "by_type": compute_metrics_by_type(combined_json_predictions, combined_gold_entities),
            "per_example": {item["id"]: item["json"] for item in per_example_results},
        },
        "marker": {
            "micro": compute_metrics(combined_marker_predictions, combined_gold_entities),
            "by_type": compute_metrics_by_type(combined_marker_predictions, combined_gold_entities),
            "per_example": {item["id"]: item["marker"] for item in per_example_results},
        },
    }

    save_artifact(OUTPUT_DIR / "predictions_json.json", json.dumps(predictions_json, ensure_ascii=False, indent=2))
    save_artifact(OUTPUT_DIR / "predictions_marker.json", json.dumps(predictions_marker, ensure_ascii=False, indent=2))
    save_artifact(OUTPUT_DIR / "metrics.json", json.dumps(summary, ensure_ascii=False, indent=2))
    save_artifact(OUTPUT_DIR / "errors.json", json.dumps(errors, ensure_ascii=False, indent=2))

    summary_md = [
        "# Prompt Baseline Evaluation",
        "",
        f"- API calls: {api_calls}",
        "",
        "## JSON Prompt",
        f"- Micro precision: {summary['json']['micro']['precision']:.3f}",
        f"- Micro recall: {summary['json']['micro']['recall']:.3f}",
        f"- Micro F1: {summary['json']['micro']['f1']:.3f}",
        "",
        "## Marker Prompt",
        f"- Micro precision: {summary['marker']['micro']['precision']:.3f}",
        f"- Micro recall: {summary['marker']['micro']['recall']:.3f}",
        f"- Micro F1: {summary['marker']['micro']['f1']:.3f}",
        "",
        "## Per example",
    ]
    for example in examples:
        example_id = example["id"]
        metrics_json = next(item["json"] for item in per_example_results if item["id"] == example_id)
        metrics_marker = next(item["marker"] for item in per_example_results if item["id"] == example_id)
        summary_md.append(
            f"- {example_id}: JSON precision={metrics_json['precision']:.3f}, recall={metrics_json['recall']:.3f}, f1={metrics_json['f1']:.3f}; "
            f"Marker precision={metrics_marker['precision']:.3f}, recall={metrics_marker['recall']:.3f}, f1={metrics_marker['f1']:.3f}"
        )
    save_artifact(OUTPUT_DIR / "summary.md", "\n".join(summary_md) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(run_evaluation())
