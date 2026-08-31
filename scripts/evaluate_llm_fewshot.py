#!/usr/bin/env python3
"""kNN few-shot evaluation (JSON + Marker) using example_pool retrieval."""

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

from ie_course.kisski_client import collect_config, extract_json_payload, request_json, save_artifact
from ie_course.retrieval import load_example_pool

# Reuse baseline helpers via importlib to avoid circular import
import importlib.util

_BASELINE_SPEC = importlib.util.spec_from_file_location("evaluate_llm_baseline", PROJECT_ROOT / "scripts" / "evaluate_llm_baseline.py")
assert _BASELINE_SPEC and _BASELINE_SPEC.loader
_baseline_mod = importlib.util.module_from_spec(_BASELINE_SPEC)
_BASELINE_SPEC.loader.exec_module(_baseline_mod)

ALLOWED_TYPES = _baseline_mod.ALLOWED_TYPES
build_gold_entities = _baseline_mod.build_gold_entities
compare_predictions_to_gold = _baseline_mod.compare_predictions_to_gold
compute_metrics = _baseline_mod.compute_metrics
compute_metrics_by_type = _baseline_mod.compute_metrics_by_type
normalize_json_predictions = _baseline_mod.normalize_json_predictions
normalize_marker_predictions = _baseline_mod.normalize_marker_predictions

DEFAULT_K: Final[int] = 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Few-shot kNN evaluation (JSON + Marker) on gold")
    parser.add_argument("--split", choices=["gold", "smoke_test"], default="gold", help="Test split (default: gold)")
    parser.add_argument("--gold-dir", type=Path, default=None, help="Gold dir (default: data/gold or data/smoke_test)")
    parser.add_argument("--example-pool-dir", type=Path, default=None, help="Example pool dir (default: data/example_pool)")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output dir (default: artifacts/llm_fewshot_gold)")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="Top-k examples (default: 2)")
    parser.add_argument("--embedding-model", type=str, default="tfidf-sklearn", help="Embedding model name for retrieval.json")
    parser.add_argument("--model", type=str, default=None, help="Override model id")
    parser.add_argument("--base-url", type=str, default=None, help="Override base URL")
    parser.add_argument("--api-key", type=str, default=None, help="Override API key")
    return parser.parse_args(argv)


def resolve_dirs(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    if args.gold_dir is not None:
        gold_dir = args.gold_dir
    else:
        gold_dir = PROJECT_ROOT / ("data/gold" if args.split == "gold" else "data/smoke_test")
    if args.example_pool_dir is not None:
        pool_dir = args.example_pool_dir
    else:
        pool_dir = PROJECT_ROOT / "data/example_pool"
    if args.output_dir is not None:
        out_dir = args.output_dir
    else:
        out_dir = PROJECT_ROOT / ("artifacts/llm_fewshot_gold" if args.split == "gold" else "artifacts/llm_fewshot_smoke")
    return gold_dir, pool_dir, out_dir


def load_gold_examples(gold_dir: Path) -> list[dict[str, Any]]:
    texts_dir = gold_dir / "texts"
    ann_dir = gold_dir / "annotations"
    if texts_dir.exists():
        text_paths = sorted(texts_dir.glob("job_ad_*.txt"))
    else:
        text_paths = sorted(gold_dir.glob("job_ad_*.txt"))
        ann_dir = gold_dir / "annotations"
    examples: list[dict[str, Any]] = []
    for text_path in text_paths:
        stem = text_path.stem
        gold_path = ann_dir / f"{stem}.json" if ann_dir.exists() else gold_dir / "annotations" / f"{stem}.json"
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


def build_gold_json_example(example: dict[str, Any]) -> str:
    # Return JSON object string for example
    payload: dict[str, list[str]] = {t: [] for t in ALLOWED_TYPES}
    for ent in example["gold"].get("entities", []):
        payload[ent["type"]].append(ent["text"])
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_gold_marked_example(example: dict[str, Any]) -> str:
    text = example["text"]
    entities = sorted(example["gold"].get("entities", []), key=lambda x: x["start"], reverse=True)
    marked = text
    for ent in entities:
        start, end = ent["start"], ent["end"]
        # Validate slice
        if marked[start:end] != ent["text"] and text[start:end] != ent["text"]:
            continue
        # Insert markers from end to start to keep offsets
        marked = marked[:start] + f"@@{ent['type']}{{{ent['text']}}}##" + marked[end:]
    return marked


def build_fewshot_json_prompt(example_text: str, fewshot_examples: list[dict[str, Any]]) -> str:
    parts = [
        "You are a strict extractor for job advertisements. "
        "Return only valid JSON. "
        "Use exactly these entity types only: JOB_TITLE, HARD_SKILL, SOFT_SKILL, EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE. "
        "Return a JSON object with exactly these keys: JOB_TITLE, HARD_SKILL, SOFT_SKILL, EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE. "
        "Each value must be a list of strings taken verbatim from the text. "
        "Do not invent information or add extra categories. "
        "Here are examples:"
    ]
    for ex in fewshot_examples:
        parts.append(f"\nExample text: {ex['text']}\nExample JSON: {build_gold_json_example(ex)}")
    parts.append(f"\nNow extract from this text:\nDisplay: {example_text}")
    return "\n".join(parts)


def build_fewshot_marker_prompt(example_text: str, fewshot_examples: list[dict[str, Any]]) -> str:
    parts = [
        "You are a strict marker-based extractor for job advertisements. "
        "Return only the complete input text. "
        "Do not change any word, punctuation, whitespace, or line breaks. "
        "Do not delete anything. "
        "Do not add anything except the markers. "
        "Use only these marker types: @@JOB_TITLE{...}##, @@HARD_SKILL{...}##, @@SOFT_SKILL{...}##, @@EXPERIENCE{...}##, @@EDUCATION{...}##, @@LANGUAGE{...}##, @@WORK_MODE{...}##. "
        "The content inside each marker must be exactly the original span text from the input. "
        "Here are examples:"
    ]
    for ex in fewshot_examples:
        marked = build_gold_marked_example(ex)
        parts.append(f"\nExample input:\n{ex['text']}\nExample output:\n{marked}")
    parts.append(
        "Example:\nOriginal:\nWir suchen einen Data Scientist mit Python und SQL in Vollzeit.\n\n"
        "Output:\nWir suchen einen @@JOB_TITLE{Data Scientist}## mit @@HARD_SKILL{Python}## und @@HARD_SKILL{SQL}## in @@WORK_MODE{Vollzeit}##.\n\n"
        f"Input:\n{example_text}"
    )
    return "\n".join(parts)


def collect_runtime_config(args: argparse.Namespace):
    from ie_course.kisski_client import collect_config

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
    if args.model is not None or args.base_url is not None or args.api_key is not None:
        missing = []
        if not config.get("api_key"):
            missing.append("KISSKI_API_KEY")
        if not config.get("base_url"):
            missing.append("KISSKI_BASE_URL")
    return config, missing


def run_evaluation(args: argparse.Namespace) -> int:
    gold_dir, pool_dir, output_dir = resolve_dirs(args)
    k = args.k
    # Load pools
    pool_examples = load_example_pool(pool_dir)
    gold_examples = load_gold_examples(gold_dir)
    if not pool_examples:
        print(f"No example_pool examples in {pool_dir}")
        return 1
    if not gold_examples:
        print(f"No gold examples in {gold_dir}")
        return 1
    # Leakage check
    pool_ids = {ex["id"] for ex in pool_examples}
    for gex in gold_examples:
        if gex["id"] in pool_ids:
            print(f"Leakage: gold id {gex['id']} also in example_pool")
            return 1

    # Retrieval
    from ie_course.retrieval import retrieve_for_queries, build_tfidf_index

    pool_texts = [ex["text"] for ex in pool_examples]
    pool_ids_list = [ex["id"] for ex in pool_examples]
    vectorizer, matrix = build_tfidf_index(pool_texts)
    query_texts = [ex["text"] for ex in gold_examples]
    query_ids = [ex["id"] for ex in gold_examples]
    retrieval = retrieve_for_queries(query_texts, query_ids, pool_texts, pool_ids_list, vectorizer, matrix, k=k, embedding_model=args.embedding_model)

    # Map retrieval to examples
    pool_by_id = {ex["id"]: ex for ex in pool_examples}
    retrieval_map: dict[str, list[dict[str, Any]]] = {}
    for entry in retrieval:
        qid = entry["query_id"]
        few = [pool_by_id[r["id"]] for r in entry["results"]]
        retrieval_map[qid] = few

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
    if not model_id:
        from ie_course.kisski_client import request_json

        status, body, _ = request_json(f"{base_url}/models", api_key)
        if status >= 400 or not body:
            print("Unable to reach /models")
            return 1
        available = [item.get("id") for item in body.get("data", []) if item.get("id")]
        if not available:
            print("No model IDs")
            return 1
        model_id = available[0]

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw_outputs"
    raw_dir.mkdir(parents=True, exist_ok=True)

    from ie_course.kisski_client import extract_json_payload, request_json

    predictions_json: list[dict[str, Any]] = []
    predictions_marker: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    per_example: list[dict[str, Any]] = []
    api_calls = 0

    for example in gold_examples:
        example_id = example["id"]
        example_text = example["text"]
        gold_entities = [{"type": e["type"], "text": e["text"], "start": e["start"], "end": e["end"]} for e in example["gold"].get("entities", [])]
        few = retrieval_map.get(example_id, [])

        # JSON few-shot
        json_prompt = build_fewshot_json_prompt(example_text, few)
        json_payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "Return only JSON and nothing else."},
                {"role": "user", "content": json_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 600,
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
                norm = normalize_json_predictions(parsed, example_text)  # type: ignore
                predictions_json.append({"id": example_id, "predictions": norm})
                errors.extend(compare_predictions_to_gold(example_id, "json", norm, gold_entities))

        # Marker few-shot
        marker_prompt = build_fewshot_marker_prompt(example_text, few)
        marker_payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "Return only the marked text and nothing else."},
                {"role": "user", "content": marker_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 1200,
        }
        status, body, raw_text = request_json(f"{base_url}/chat/completions", api_key, marker_payload)
        api_calls += 1
        (raw_dir / f"{example_id}_marker.txt").write_text((body.get("choices", [{}])[0].get("message", {}).get("content") if body else raw_text) or "", encoding="utf-8")
        if status >= 400 or not body:
            errors.append({"id": example_id, "prompt": "marker", "error_type": "invalid_output", "type": "INVALID", "text": raw_text or "request failed"})
            predictions_marker.append({"id": example_id, "predictions": []})
        else:
            content = body.get("choices", [{}])[0].get("message", {}).get("content")
            norm = normalize_marker_predictions(content, example_text)  # type: ignore
            predictions_marker.append({"id": example_id, "predictions": norm})
            errors.extend(compare_predictions_to_gold(example_id, "marker", norm, gold_entities))

        json_metrics = compute_metrics([p for p in predictions_json[-1].get("predictions", []) if p.get("start") is not None], gold_entities)
        marker_metrics = compute_metrics([p for p in predictions_marker[-1].get("predictions", []) if p.get("start") is not None], gold_entities)
        per_example.append({"id": example_id, "json": json_metrics, "marker": marker_metrics})

    combined_gold = [e for ex in gold_examples for e in [{"type": x["type"], "text": x["text"], "start": x["start"], "end": x["end"]} for x in ex["gold"].get("entities", [])]]
    combined_json = [p for ex in predictions_json for p in ex.get("predictions", [])]
    combined_marker = [p for ex in predictions_marker for p in ex.get("predictions", [])]

    metrics = {
        "config": {"split": args.split, "gold_dir": str(gold_dir), "example_pool_dir": str(pool_dir), "model": model_id, "base_url": base_url, "temperature": 0.0, "k": k, "embedding_model": args.embedding_model},
        "counts": {"examples": len(gold_examples), "api_calls": api_calls, "k": k},
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
    save_artifact(output_dir / "retrieval.json", json.dumps(retrieval, ensure_ascii=False, indent=2))

    # Try to load baseline for comparison
    baseline_path = PROJECT_ROOT / ("artifacts/llm_baseline_gold/metrics.json" if args.split == "gold" else "artifacts/llm_baseline_smoke/metrics.json")
    baseline = None
    if baseline_path.exists():
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        except Exception:
            baseline = None

    summary_lines = [
        f"# LLM Few-Shot Evaluation ({args.split}, k={k})",
        "",
        f"- Split: {args.split}",
        f"- Gold dir: {gold_dir}",
        f"- Example pool: {pool_dir} ({len(pool_examples)} examples)",
        f"- Model: {model_id}",
        f"- Base URL: {base_url}",
        "- Temperature: 0.0",
        f"- Embedding: {args.embedding_model}",
        f"- Examples: {len(gold_examples)} ({', '.join(ex['id'] for ex in gold_examples)})",
        f"- API calls: {api_calls}",
        "",
        "## Retrieval",
    ]
    for entry in retrieval:
        ids_scores = ", ".join(f"{r['id']} ({r['score']:.3f})" for r in entry["results"])
        summary_lines.append(f"- {entry['query_id']}: {ids_scores}")
    summary_lines.extend(
        [
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
    )
    for item in per_example:
        summary_lines.append(f"- {item['id']}: JSON F1={item['json']['f1']:.3f} Marker F1={item['marker']['f1']:.3f}")
    # Comparison if baseline exists
    if baseline is not None:
        b_json_f1 = baseline.get("json", {}).get("micro", {}).get("f1", 0.0)
        b_marker_f1 = baseline.get("marker", {}).get("micro", {}).get("f1", 0.0)
        delta_json = metrics["json"]["micro"]["f1"] - b_json_f1
        delta_marker = metrics["marker"]["micro"]["f1"] - b_marker_f1
        summary_lines.extend(
            [
                "",
                "## Comparison to Baseline",
                f"- Baseline JSON F1: {b_json_f1:.3f} Few-Shot JSON F1: {metrics['json']['micro']['f1']:.3f} Delta: {delta_json:+.3f}",
                f"- Baseline Marker F1: {b_marker_f1:.3f} Few-Shot Marker F1: {metrics['marker']['micro']['f1']:.3f} Delta: {delta_marker:+.3f}",
                f"- JSON Precision delta: {metrics['json']['micro']['precision'] - baseline['json']['micro']['precision']:+.3f} Recall delta: {metrics['json']['micro']['recall'] - baseline['json']['micro']['recall']:+.3f}",
                f"- Marker Precision delta: {metrics['marker']['micro']['precision'] - baseline['marker']['micro']['precision']:+.3f} Recall delta: {metrics['marker']['micro']['recall'] - baseline['marker']['micro']['recall']:+.3f}",
                "",
                "### By-type F1 delta (Few-Shot - Baseline)",
                "| Type | JSON ΔF1 | Marker ΔF1 |",
                "|------|----------|------------|",
            ]
        )
        for t in ALLOWED_TYPES:
            b_j = baseline.get("json", {}).get("by_type", {}).get(t, {}).get("f1", 0.0)
            f_j = metrics["json"]["by_type"].get(t, {}).get("f1", 0.0)
            b_m = baseline.get("marker", {}).get("by_type", {}).get(t, {}).get("f1", 0.0)
            f_m = metrics["marker"]["by_type"].get(t, {}).get("f1", 0.0)
            summary_lines.append(f"| {t} | {f_j - b_j:+.3f} | {f_m - b_m:+.3f} |")
    else:
        summary_lines.extend(["", "## Comparison to Baseline", "- No baseline metrics found, comparison skipped"])

    summary_lines.extend(["", "## Errors", f"- Total errors: {len(errors)}"])
    save_artifact(output_dir / "summary.md", "\n".join(summary_lines) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_evaluation(args)


if __name__ == "__main__":
    sys.exit(main())
