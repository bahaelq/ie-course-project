#!/usr/bin/env python3
"""Run a marker-only evaluation with an updated prompt and write results to a new artifact directory."""

from __future__ import annotations

import argparse
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

from ie_course.kisski_client import collect_config, request_json, save_artifact, validate_marker_output

EXAMPLES_DIR: Final[Path] = PROJECT_ROOT / "data" / "smoke_test"
GOLD_DIR: Final[Path] = EXAMPLES_DIR / "annotations"
OUTPUT_DIR: Final[Path] = PROJECT_ROOT / "artifacts" / "prompt_baseline_evaluation_v2"
ALLOWED_TYPES: Final[tuple[str, ...]] = (
    "JOB_TITLE",
    "HARD_SKILL",
    "SOFT_SKILL",
    "EXPERIENCE",
    "EDUCATION",
    "LANGUAGE",
    "WORK_MODE",
)


def load_examples(job_ids: list[str] | None = None) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    selected = set(job_ids or [])
    for text_path in sorted(EXAMPLES_DIR.glob("job_ad_*.txt")):
        stem = text_path.stem
        if selected and stem not in selected:
            continue
        gold_path = GOLD_DIR / f"{stem}.json"
        examples.append(
            {
                "id": stem,
                "text": text_path.read_text(encoding="utf-8"),
                "gold": json.loads(gold_path.read_text(encoding="utf-8")),
            }
        )
    return examples


def build_marker_prompt(example_text: str) -> str:
    return (
        "You are a strict marker-based extractor for job advertisements. "
        "Return only the complete input text. "
        "Do not change any word, punctuation, whitespace, or line breaks. "
        "Do not delete anything. "
        "Do not add anything except the markers. "
        "Use only these marker types: @@JOB_TITLE{...}##, @@HARD_SKILL{...}##, @@SOFT_SKILL{...}##, @@EXPERIENCE{...}##, @@EDUCATION{...}##, @@LANGUAGE{...}##, @@WORK_MODE{...}##. "
        "The content inside each marker must be exactly the original span text from the input. "
        "Wrap recognized spans exclusively with @@TYPE{original text span}##. "
        "Do not output any explanation, JSON, or Markdown code block. "
        "Do not merge separate spans into one marker. "
        "Do not create composite HARD_SKILL spans like @@HARD_SKILL{Python, SQL}## when the gold standard treats them as separate entities. "
        "Do not create composite WORK_MODE spans like @@WORK_MODE{Vollzeit und remote möglich}## when the gold standard treats them as separate entities. "
        "Mark exactly the intended annotation span. Do not shorten boundaries. "
        "Do not use the wrong entity type. For example, 'Verwaltung von Dokumenten' alone is not a HARD_SKILL if the gold span is EXPERIENCE, and 'Erfahrung' alone is not the correct span if the gold span is 'Erfahrung im B2B-Verkauf'. "
        "Example:\n"
        "Original:\n"
        "Wir suchen einen Data Scientist mit Python und SQL in Vollzeit.\n\n"
        "Output:\n"
        "Wir suchen einen @@JOB_TITLE{Data Scientist}## mit @@HARD_SKILL{Python}## und @@HARD_SKILL{SQL}## in @@WORK_MODE{Vollzeit}##.\n\n"
        "Input:\n"
        f"{example_text}"
    )


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


def normalize_marker_predictions(content: str, example_text: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    valid, spans, error, text_without_syntax = validate_marker_output(content, example_text)
    if not valid:
        return (
            [{"type": "INVALID_OUTPUT", "text": content, "start": None, "end": None, "status": "invalid_output"}],
            {"valid": False, "error": error, "text_without_syntax": text_without_syntax},
        )

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
    return predictions, {"valid": True, "error": None, "text_without_syntax": text_without_syntax}


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
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


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


def compare_predictions_to_gold(example_id: str, predictions: list[dict[str, Any]], gold_entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for prediction in predictions:
        status = prediction.get("status")
        if status == "invalid_output":
            errors.append({"id": example_id, "error_type": "invalid_output", "type": prediction.get("type"), "text": prediction.get("text")})
            continue
        if status == "hallucinated":
            errors.append({"id": example_id, "error_type": "hallucinated_entity", "type": prediction.get("type"), "text": prediction.get("text")})
            continue
        if status == "ambiguous":
            errors.append({"id": example_id, "error_type": "ambiguous_text_match", "type": prediction.get("type"), "text": prediction.get("text")})
            continue
        if prediction.get("start") is None or prediction.get("end") is None:
            continue
        exact_match = any(
            prediction.get("type") == gold.get("type") and prediction.get("start") == gold.get("start") and prediction.get("end") == gold.get("end")
            for gold in gold_entities
        )
        if exact_match:
            continue
        same_text = [gold for gold in gold_entities if gold.get("text") == prediction.get("text")]
        same_type = [gold for gold in same_text if gold.get("type") == prediction.get("type")]
        if same_type:
            errors.append({"id": example_id, "error_type": "wrong_boundary", "type": prediction.get("type"), "text": prediction.get("text")})
        elif same_text:
            errors.append({"id": example_id, "error_type": "wrong_type", "type": prediction.get("type"), "text": prediction.get("text")})
        else:
            errors.append({"id": example_id, "error_type": "hallucinated_entity", "type": prediction.get("type"), "text": prediction.get("text")})

    for gold in gold_entities:
        gold_key = (gold.get("type"), gold.get("start"), gold.get("end"))
        if not any(
            prediction.get("start") is not None and prediction.get("end") is not None and (prediction.get("type"), prediction.get("start"), prediction.get("end")) == gold_key
            for prediction in predictions
        ):
            errors.append({"id": example_id, "error_type": "missed_entity", "type": gold.get("type"), "text": gold.get("text")})
    return errors


def run_evaluation(job_ids: list[str] | None = None) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    examples = load_examples(job_ids)
    if not examples:
        print("No examples matched the requested job IDs")
        return 1

    config, missing = collect_config()
    if missing:
        print("Missing configuration")
        return 1
    base_url = str(config["base_url"] or "").rstrip("/")
    api_key = str(config["api_key"])
    model_id = str(config["model"] or "")
    if not api_key or not model_id or not base_url:
        print("Missing API key, model, or base URL configuration")
        return 1

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    per_example_metrics: list[dict[str, Any]] = []

    for example in examples:
        example_id = example["id"]
        example_text = example["text"]
        gold_entities = build_gold_entities(example["gold"])
        prompt = build_marker_prompt(example_text)
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "Return only the marked text and nothing else."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 260,
        }
        status, body, raw_text = request_json(f"{base_url}/chat/completions", api_key, payload)
        if status >= 400 or not body:
            errors.append({"id": example_id, "error_type": "request_failed", "message": raw_text or "request failed"})
            results.append({"id": example_id, "predictions": [], "raw_output": "", "validation": {"valid": False, "error": raw_text or "request failed"}})
            continue
        content = body.get("choices", [{}])[0].get("message", {}).get("content")
        predictions, validation = normalize_marker_predictions(content, example_text)
        errors.extend(compare_predictions_to_gold(example_id, predictions, gold_entities))
        metrics = compute_metrics([item for item in predictions if item.get("start") is not None and item.get("end") is not None], gold_entities)
        per_example_metrics.append({"id": example_id, "metrics": metrics})
        results.append({"id": example_id, "predictions": predictions, "raw_output": content, "validation": validation})

    combined_predictions = [prediction for item in results for prediction in item.get("predictions", [])]
    combined_gold_entities = [entity for example in examples for entity in build_gold_entities(example["gold"])]
    summary = {
        "micro": compute_metrics(combined_predictions, combined_gold_entities),
        "by_type": compute_metrics_by_type(combined_predictions, combined_gold_entities),
        "per_example": {item["id"]: item["metrics"] for item in per_example_metrics},
    }

    save_artifact(OUTPUT_DIR / "predictions_marker.json", json.dumps(results, ensure_ascii=False, indent=2))
    save_artifact(OUTPUT_DIR / "errors.json", json.dumps(errors, ensure_ascii=False, indent=2))
    save_artifact(OUTPUT_DIR / "metrics.json", json.dumps(summary, ensure_ascii=False, indent=2))
    summary_md = [
        "# Marker Prompt Evaluation v2",
        "",
        "## Summary",
        f"- Examples: {', '.join(example['id'] for example in examples)}",
        f"- Micro precision: {summary['micro']['precision']:.3f}",
        f"- Micro recall: {summary['micro']['recall']:.3f}",
        f"- Micro F1: {summary['micro']['f1']:.3f}",
        "",
        "## Invalid format outputs",
    ]
    invalid_outputs = [item for item in results if not item.get("validation", {}).get("valid", True)]
    for item in invalid_outputs:
        summary_md.append(f"- {item['id']}: {item['validation'].get('error')}")
    summary_md.extend(["", "## Errors"])
    for error in errors:
        summary_md.append(f"- {error['id']}: {error['error_type']} -> {error.get('text')}")
    save_artifact(OUTPUT_DIR / "summary.md", "\n".join(summary_md) + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the updated marker prompt evaluation")
    parser.add_argument("--job-id", dest="job_ids", action="append", help="Evaluate a single example by job id")
    args = parser.parse_args()
    return run_evaluation(args.job_ids)


if __name__ == "__main__":
    sys.exit(main())
