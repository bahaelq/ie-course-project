#!/usr/bin/env python3
"""Unified LLM baseline evaluation (JSON + Marker) for gold or smoke_test splits."""

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

from ie_course.kisski_client import (
    collect_config,
    extract_json_payload,
    request_json,
    save_artifact,
    validate_marker_output,
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reproducible LLM baseline (JSON + Marker) on gold or smoke_test")
    parser.add_argument("--split", choices=["gold", "smoke_test"], default="gold", help="Dataset split to evaluate (default: gold)")
    parser.add_argument("--gold-dir", type=Path, default=None, help="Path to gold dir (default: data/gold or data/smoke_test per --split)")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output dir (default: artifacts/llm_baseline_gold or artifacts/llm_baseline_smoke)")
    parser.add_argument("--model", type=str, default=None, help="Override model id (default: from .env KISSKI_MODEL)")
    parser.add_argument("--base-url", type=str, default=None, help="Override base URL (default: from .env)")
    parser.add_argument("--api-key", type=str, default=None, help="Override API key (default: from .env)")
    parser.add_argument("--json-prompt", choices=["default", "strict"], default="default", help="JSON prompt variant (default: strict exact-span copy)")
    return parser.parse_args(argv)


def resolve_dirs(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.gold_dir is not None:
        gold_dir = args.gold_dir
    else:
        gold_dir = PROJECT_ROOT / ("data/gold" if args.split == "gold" else "data/smoke_test")
    if args.output_dir is not None:
        output_dir = args.output_dir
    else:
        output_dir = PROJECT_ROOT / ("artifacts/llm_baseline_gold" if args.split == "gold" else "artifacts/llm_baseline_smoke")
    return gold_dir, output_dir


def load_examples(gold_dir: Path) -> list[dict[str, Any]]:
    # gold_dir may be data/gold (with texts/ + annotations/) or data/smoke_test (with *.txt at top level)
    texts_dir = gold_dir / "texts"
    ann_dir = gold_dir / "annotations"
    if texts_dir.exists():
        text_paths = sorted(texts_dir.glob("job_ad_*.txt"))
        gold_paths = {p.stem: ann_dir / f"{p.stem}.json" for p in text_paths}
    else:
        # smoke_test layout: texts at gold_dir/*.txt, annotations at gold_dir/annotations/
        text_paths = sorted(gold_dir.glob("job_ad_*.txt"))
        gold_paths = {p.stem: gold_dir / "annotations" / f"{p.stem}.json" for p in text_paths}
    examples: list[dict[str, Any]] = []
    for text_path in text_paths:
        stem = text_path.stem
        gold_path = gold_paths[stem]
        if not gold_path.exists():
            continue
        examples.append(
            {
                "id": stem,
                "text": text_path.read_text(encoding="utf-8"),
                "gold": json.loads(gold_path.read_text(encoding="utf-8")),
            }
        )
    return sorted(examples, key=lambda x: x["id"])


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


def build_strict_json_prompt(example_text: str) -> str:
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


def build_marker_prompt(example_text: str) -> str:
    # Reuse v2 prompt with explicit instructions and example
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
    # Partial validation: keep valid markers, reject unknown/malformed individually
    # Extract raw markers via regex, filter per-marker instead of all-or-nothing
    import re as _re

    pattern = _re.compile(r"@@(?P<type>[A-Z_]+)\{(?P<content>.*?)\}##", re.DOTALL)
    raw_spans = list(pattern.finditer(content))
    if not raw_spans:
        return [{"type": "INVALID_OUTPUT", "text": content, "start": None, "end": None, "status": "invalid_output"}]

    predictions: list[dict[str, Any]] = []
    # Track rejected markers for error reporting via special status
    for match in raw_spans:
        span_type = match.group("type")
        span_text = match.group("content")
        # 1. Unknown/forbidden types -> rejected, not valid prediction
        if span_type not in ALLOWED_TYPES:
            predictions.append({"type": span_type, "text": span_text, "start": None, "end": None, "status": "rejected_marker"})
            continue
        # 2. Empty content -> rejected
        if not span_text.strip():
            predictions.append({"type": span_type, "text": span_text, "start": None, "end": None, "status": "rejected_marker"})
            continue
        # 3. Nested syntax
        if "@@" in span_text or "##" in span_text:
            predictions.append({"type": span_type, "text": span_text, "start": None, "end": None, "status": "rejected_marker"})
            continue
        # 4. Content not in original -> hallucinated (as before)
        if span_text not in example_text:
            predictions.append({"type": span_type, "text": span_text, "start": None, "end": None, "status": "hallucinated"})
            continue
        positions = [m.start() for m in _re.finditer(_re.escape(span_text), example_text)]
        if not positions:
            predictions.append({"type": span_type, "text": span_text, "start": None, "end": None, "status": "hallucinated"})
            continue
        if len(positions) > 1:
            predictions.append({"type": span_type, "text": span_text, "start": None, "end": None, "status": "ambiguous"})
            continue
        start = positions[0]
        predictions.append({"type": span_type, "text": span_text, "start": start, "end": start + len(span_text), "status": "ok"})

    # If all were rejected and no valid/ok/hallucinated/ambiguous, still return rejected list (not invalid_output)
    # Only return invalid_output when no markers at all (handled above)
    # Overlap handling: keep as before, but do not discard all - overlapping valid spans are kept,
    # validator's overlap check is not applied here; overlapping will be counted as FP via exact-match
    return predictions


def build_gold_entities(gold_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"type": entity["type"], "text": entity["text"], "start": entity["start"], "end": entity["end"]}
        for entity in gold_payload.get("entities", [])
    ]


def compute_metrics(predictions: list[dict[str, Any]], gold_entities: list[dict[str, Any]]) -> dict[str, Any]:
    gold_keys = {(item["type"], item["start"], item["end"]): item for item in gold_entities}
    pred_keys = {(item["type"], item["start"], item["end"]): item for item in predictions if item.get("start") is not None and item.get("end") is not None}
    tp = sum(1 for k in pred_keys if k in gold_keys)
    fp = len(pred_keys) - tp
    fn = len(gold_keys) - tp
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


def compare_predictions_to_gold(example_id: str, prompt_name: str, predictions: list[dict[str, Any]], gold_entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for prediction in predictions:
        status = prediction.get("status")
        if status == "rejected_marker":
            errors.append({"id": example_id, "prompt": prompt_name, "error_type": "rejected_marker", "type": prediction.get("type"), "text": prediction.get("text")})
            continue
        elif status == "hallucinated":
            errors.append({"id": example_id, "prompt": prompt_name, "error_type": "hallucinated", "type": prediction.get("type"), "text": prediction.get("text")})
        elif status == "ambiguous":
            errors.append({"id": example_id, "prompt": prompt_name, "error_type": "hallucinated", "type": prediction.get("type"), "text": prediction.get("text")})
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
                errors.append({"id": example_id, "prompt": prompt_name, "error_type": "hallucinated", "type": prediction.get("type"), "text": prediction.get("text")})
    for gold in gold_entities:
        gold_key = (gold.get("type"), gold.get("start"), gold.get("end"))
        if not any(
            prediction.get("start") is not None and prediction.get("end") is not None and (prediction.get("type"), prediction.get("start"), prediction.get("end")) == gold_key
            for prediction in predictions
        ):
            errors.append({"id": example_id, "prompt": prompt_name, "error_type": "missed", "type": gold.get("type"), "text": gold.get("text")})
    return errors


def collect_runtime_config(args: argparse.Namespace) -> tuple[dict[str, str | None], list[str]]:
    # Allow CLI overrides for testing without .env
    if args.api_key and args.base_url:
        cfg = {"api_key": args.api_key, "base_url": args.base_url, "model": args.model}
        missing = []
        if not cfg["api_key"]:
            missing.append("KISSKI_API_KEY")
        if not cfg["base_url"]:
            missing.append("KISSKI_BASE_URL")
        return cfg, missing
    config, missing = collect_config()
    if args.model is not None:
        config["model"] = args.model
    if args.base_url is not None:
        config["base_url"] = args.base_url
    if args.api_key is not None:
        config["api_key"] = args.api_key
    # re-evaluate missing after overrides
    if args.model is not None or args.base_url is not None or args.api_key is not None:
        missing = []
        if not config.get("api_key"):
            missing.append("KISSKI_API_KEY")
        if not config.get("base_url"):
            missing.append("KISSKI_BASE_URL")
    return config, missing


def run_evaluation(args: argparse.Namespace) -> int:
    gold_dir, output_dir = resolve_dirs(args)
    examples = load_examples(gold_dir)
    if not examples:
        print(f"No examples found in {gold_dir}")
        return 1

    config, missing = collect_runtime_config(args)
    if missing:
        print(f"Missing configuration: {', '.join(missing)}")
        return 1
    base_url = str(config.get("base_url") or "").rstrip("/")
    api_key = str(config.get("api_key") or "")
    model_id = str(config.get("model") or "")
    if not api_key or not base_url:
        print("Missing API key or base URL")
        return 1
    # Model may be empty and will be resolved via /models
    if not model_id:
        status, body, _ = request_json(f"{base_url}/models", api_key)
        if status >= 400 or not body:
            print("Unable to reach /models endpoint")
            return 1
        available = [item.get("id") for item in body.get("data", []) if item.get("id")]
        if not available:
            print("No model IDs returned")
            return 1
        model_id = available[0]

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw_outputs"
    raw_dir.mkdir(parents=True, exist_ok=True)

    predictions_json: list[dict[str, Any]] = []
    predictions_marker: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    per_example: list[dict[str, Any]] = []
    api_calls = 0

    for example in examples:
        example_id = example["id"]
        example_text = example["text"]
        gold_entities = build_gold_entities(example["gold"])

        # JSON prompt (variant)
        if getattr(args, "json_prompt", "default") == "strict":
            json_prompt = build_strict_json_prompt(example_text)
        else:
            json_prompt = build_plain_json_prompt(example_text)
        json_payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "Return only JSON and nothing else."},
                {"role": "user", "content": json_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 400,
            "response_format": {"type": "json_object"},
        }
        status, body, raw_text = request_json(f"{base_url}/chat/completions", api_key, json_payload)
        api_calls += 1
        (raw_dir / f"{example_id}_json.txt").write_text((body.get("choices", [{}])[0].get("message", {}).get("content") if body else raw_text) or "", encoding="utf-8")
        if status >= 400 or not body:
            errors.append({"id": example_id, "prompt": "json", "error_type": "invalid_output", "type": "INVALID", "text": raw_text or "request failed"})
            predictions_json.append({"id": example_id, "predictions": []})
        else:
            content = body.get("choices", [{}])[0].get("message", {}).get("content")
            parsed, parse_err = extract_json_payload(content)
            if parse_err is not None:
                errors.append({"id": example_id, "prompt": "json", "error_type": "invalid_output", "type": "INVALID", "text": parse_err})
                predictions_json.append({"id": example_id, "predictions": []})
            else:
                norm = normalize_json_predictions(parsed, example_text)
                predictions_json.append({"id": example_id, "predictions": norm})
                errors.extend(compare_predictions_to_gold(example_id, "json", norm, gold_entities))

        # Marker prompt v2
        marker_prompt = build_marker_prompt(example_text)
        marker_payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "Return only the marked text and nothing else."},
                {"role": "user", "content": marker_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 800,
        }
        status, body, raw_text = request_json(f"{base_url}/chat/completions", api_key, marker_payload)
        api_calls += 1
        (raw_dir / f"{example_id}_marker.txt").write_text((body.get("choices", [{}])[0].get("message", {}).get("content") if body else raw_text) or "", encoding="utf-8")
        if status >= 400 or not body:
            errors.append({"id": example_id, "prompt": "marker", "error_type": "invalid_output", "type": "INVALID", "text": raw_text or "request failed"})
            predictions_marker.append({"id": example_id, "predictions": []})
        else:
            content = body.get("choices", [{}])[0].get("message", {}).get("content")
            norm = normalize_marker_predictions(content, example_text)
            predictions_marker.append({"id": example_id, "predictions": norm})
            errors.extend(compare_predictions_to_gold(example_id, "marker", norm, gold_entities))

        # per-example metrics
        json_metrics = compute_metrics([p for p in predictions_json[-1].get("predictions", []) if p.get("start") is not None], gold_entities)
        marker_metrics = compute_metrics([p for p in predictions_marker[-1].get("predictions", []) if p.get("start") is not None], gold_entities)
        per_example.append({"id": example_id, "json": json_metrics, "marker": marker_metrics})

    combined_gold = [entity for ex in examples for entity in build_gold_entities(ex["gold"])]
    combined_json = [p for ex in predictions_json for p in ex.get("predictions", [])]
    combined_marker = [p for ex in predictions_marker for p in ex.get("predictions", [])]

    metrics = {
        "config": {"split": args.split, "gold_dir": str(gold_dir), "model": model_id, "base_url": base_url, "temperature": 0.0, "json_prompt": getattr(args, "json_prompt", "default")},
        "counts": {"examples": len(examples), "api_calls": api_calls},
        "json": {
            "micro": compute_metrics(combined_json, combined_gold),
            "by_type": compute_metrics_by_type(combined_json, combined_gold),
            "per_example": {item["id"]: item["json"] for item in per_example},
        },
        "marker": {
            "micro": compute_metrics(combined_marker, combined_gold),
            "by_type": compute_metrics_by_type(combined_marker, combined_gold),
            "per_example": {item["id"]: item["marker"] for item in per_example},
        },
    }

    save_artifact(output_dir / "predictions_json.json", json.dumps(predictions_json, ensure_ascii=False, indent=2))
    save_artifact(output_dir / "predictions_marker.json", json.dumps(predictions_marker, ensure_ascii=False, indent=2))
    save_artifact(output_dir / "metrics.json", json.dumps(metrics, ensure_ascii=False, indent=2))
    save_artifact(output_dir / "errors.json", json.dumps(errors, ensure_ascii=False, indent=2))

    summary_lines = [
        f"# LLM Baseline Evaluation ({args.split})",
        "",
        f"- Split: {args.split}",
        f"- Gold dir: {gold_dir}",
        f"- Model: {model_id}",
        f"- Base URL: {base_url}",
        "- Temperature: 0.0",
        f"- Examples: {len(examples)} ({', '.join(ex['id'] for ex in examples)})",
        f"- API calls: {api_calls}",
        "",
        "## JSON Prompt",
        f"- Micro precision: {metrics['json']['micro']['precision']:.3f}",
        f"- Micro recall: {metrics['json']['micro']['recall']:.3f}",
        f"- Micro F1: {metrics['json']['micro']['f1']:.3f}",
        "",
        "## Marker Prompt",
        f"- Micro precision: {metrics['marker']['micro']['precision']:.3f}",
        f"- Micro recall: {metrics['marker']['micro']['recall']:.3f}",
        f"- Micro F1: {metrics['marker']['micro']['f1']:.3f}",
        "",
        "## Per example",
    ]
    for item in per_example:
        summary_lines.append(
            f"- {item['id']}: JSON F1={item['json']['f1']:.3f} Marker F1={item['marker']['f1']:.3f}"
        )
    summary_lines.extend(["", "## Errors", f"- Total errors: {len(errors)}"])
    save_artifact(output_dir / "summary.md", "\n".join(summary_lines) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_evaluation(args)


if __name__ == "__main__":
    sys.exit(main())
