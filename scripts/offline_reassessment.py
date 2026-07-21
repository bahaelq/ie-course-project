#!/usr/bin/env python3
"""Offline reassessment: corrected text-faithfulness + exact-match evaluation."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ie_course.kisski_client import normalize_trailing_file_newline, strip_marker_syntax

EVAL_DIR = PROJECT_ROOT / "artifacts" / "prompt_baseline_evaluation"
GOLD_DIR = PROJECT_ROOT / "data" / "smoke_test" / "annotations"
TEXT_DIR = PROJECT_ROOT / "data" / "smoke_test"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "prompt_baseline_offline_reassessment"

JOB_IDS = ["job_ad_001", "job_ad_002", "job_ad_003", "job_ad_004", "job_ad_005"]
ENTITY_TYPES = ["JOB_TITLE", "HARD_SKILL", "SOFT_SKILL", "EXPERIENCE", "EDUCATION", "LANGUAGE", "WORK_MODE"]


def load_gold(job_id: str) -> list[dict]:
    with open(GOLD_DIR / f"{job_id}.json") as f:
        return json.load(f)["entities"]


def load_text(job_id: str) -> str:
    return (TEXT_DIR / f"{job_id}.txt").read_text(encoding="utf-8")


def load_predictions(prompt_type: str) -> list[dict]:
    with open(EVAL_DIR / f"predictions_{prompt_type}.json") as f:
        return json.load(f)


def extract_marker_spans(text: str) -> list[dict]:
    pattern = re.compile(r"@@(?P<type>[A-Z_]+)\{(?P<content>.*?)\}##")
    return [
        {"type": m.group("type"), "content": m.group("content"), "start": m.start(), "end": m.end()}
        for m in pattern.finditer(text)
    ]


def find_original_positions(original_text: str, content: str) -> tuple[int | None, int | None]:
    pos = original_text.find(content)
    if pos == -1:
        return None, None
    return pos, pos + len(content)


def process_marker_predictions(raw_preds: list[dict], original_text: str) -> tuple[list[dict] | None, str | None]:
    if not raw_preds:
        return [], None

    raw_text = raw_preds[0].get("text", "")
    if not raw_text:
        return [], "empty_output"

    # text fidelity check (corrected: trailing newline tolerance)
    stripped = strip_marker_syntax(raw_text)
    orig_norm = normalize_trailing_file_newline(original_text)
    stripped_norm = normalize_trailing_file_newline(stripped)
    if stripped_norm != orig_norm:
        diff_idx = 0
        for i, (a, b) in enumerate(zip(stripped_norm, orig_norm)):
            if a != b:
                diff_idx = i
                break
        return None, f"text_fidelity_mismatch (first diff at {diff_idx})"

    spans = extract_marker_spans(raw_text)
    if not spans:
        return [], "no_markers"

    result = []
    for span in spans:
        t = span["type"]
        content = span["content"]
        start, end = find_original_positions(original_text, content)
        result.append({
            "type": t,
            "text": content,
            "start": start,
            "end": end,
            "status": "ok",
        })
    return result, None


def process_json_predictions(raw_preds: list[dict], original_text: str) -> list[dict]:
    return raw_preds


def exact_match(gold: list[dict], preds: list[dict]) -> tuple[list[tuple], list[int], list[int], list[bool], list[bool]]:
    gold_matched = [False] * len(gold)
    pred_matched = [False] * len(preds)
    tp_list: list[tuple[int, int]] = []

    for pi, pred in enumerate(preds):
        for gi, g in enumerate(gold):
            if not gold_matched[gi] and not pred_matched[pi]:
                if (pred["type"] == g["type"]
                        and pred["start"] == g["start"]
                        and pred["end"] == g["end"]):
                    gold_matched[gi] = True
                    pred_matched[pi] = True
                    tp_list.append((pi, gi))
                    break

    fp_list = [pi for pi, m in enumerate(pred_matched) if not m]
    fn_list = [gi for gi, m in enumerate(gold_matched) if not m]
    return tp_list, fp_list, fn_list, gold_matched, pred_matched


def classify_fp(pred: dict, gold: list[dict]) -> str:
    ps = pred.get("start")
    pe = pred.get("end")
    pt = pred["type"]
    ptext = pred.get("text", "")

    # 1) same span, different type
    for g in gold:
        if ps == g["start"] and pe == g["end"] and pt != g["type"]:
            return "wrong_type"

    # 2) same type + overlapping span
    if ps is not None and pe is not None:
        for g in gold:
            if pt == g["type"]:
                gs, ge = g["start"], g["end"]
                if ps < ge and gs < pe:
                    if ps != gs or pe != ge:
                        return "wrong_boundary"
                gtext = g.get("text", "")
                if ptext and gtext and (ptext in gtext or gtext in ptext):
                    return "wrong_boundary"

    # 3) any overlapping span (regardless of type)
    if ps is not None and pe is not None:
        for g in gold:
            gs, ge = g["start"], g["end"]
            if ps < ge and gs < pe:
                return "wrong_type"

    # 4) nothing related
    return "hallucinated_entity"


def compute_metrics(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * tp) / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}


def evaluate_prompt(prompt_type: str):
    predictions = load_predictions(prompt_type)
    by_type: dict[str, dict] = {t: {"tp": 0, "fp": 0, "fn": 0} for t in ENTITY_TYPES}
    per_doc: dict[str, dict] = {}
    all_errors: list[dict] = []
    pred_output: list[dict] = []

    micro_tp = 0
    micro_fp = 0
    micro_fn = 0
    invalid_count = 0

    for job_data in predictions:
        job_id = job_data["id"]
        gold = load_gold(job_id)
        original_text = load_text(job_id)
        raw_preds = job_data["predictions"]

        if prompt_type == "marker":
            processed, err = process_marker_predictions(raw_preds, original_text)
            if processed is None:
                invalid_count += 1
                pred_output.append({"id": job_id, "predictions": raw_preds, "validation_error": err})
                for gi in range(len(gold)):
                    g = gold[gi]
                    by_type[g["type"]]["fn"] += 1
                    all_errors.append({"id": job_id, "prompt": prompt_type, "error_type": "invalid_output",
                                       "type": g["type"], "text": g["text"], "start": g["start"], "end": g["end"]})
                micro_fn += len(gold)
                per_doc[job_id] = compute_metrics(0, 0, len(gold))
                continue
            preds = processed
        else:
            preds = process_json_predictions(raw_preds, original_text)

        tp_list, fp_list, fn_list, gold_matched, pred_matched = exact_match(gold, preds)
        tp = len(tp_list)
        fp = len(fp_list)
        fn = len(fn_list)

        micro_tp += tp
        micro_fp += fp
        micro_fn += fn

        for pi, _ in tp_list:
            by_type[preds[pi]["type"]]["tp"] += 1
        for pi in fp_list:
            by_type[preds[pi]["type"]]["fp"] += 1
            err_type = classify_fp(preds[pi], gold)
            all_errors.append({"id": job_id, "prompt": prompt_type, "error_type": err_type,
                               "type": preds[pi]["type"], "text": preds[pi]["text"],
                               "start": preds[pi]["start"], "end": preds[pi]["end"]})
        for gi in fn_list:
            by_type[gold[gi]["type"]]["fn"] += 1
            all_errors.append({"id": job_id, "prompt": prompt_type, "error_type": "missed_entity",
                               "type": gold[gi]["type"], "text": gold[gi]["text"],
                               "start": gold[gi]["start"], "end": gold[gi]["end"]})

        per_doc[job_id] = compute_metrics(tp, fp, fn)

        pred_entry = {"id": job_id, "predictions": preds}
        if prompt_type == "marker":
            pred_entry["raw_marker_output"] = raw_preds[0].get("text", "")
            pred_entry["text_fidelity_valid"] = True
        pred_output.append(pred_entry)

    return {
        "micro": compute_metrics(micro_tp, micro_fp, micro_fn),
        "by_type": {t: compute_metrics(by_type[t]["tp"], by_type[t]["fp"], by_type[t]["fn"])
                     for t in ENTITY_TYPES},
        "per_document": per_doc,
        "errors": all_errors,
        "predictions": pred_output,
        "invalid_outputs": invalid_count,
    }


def main():
    json_result = evaluate_prompt("json")
    marker_result = evaluate_prompt("marker")

    micro_json = json_result["micro"]
    micro_marker = marker_result["micro"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # metrics.json
    metrics = {
        "json": {
            "micro": micro_json,
            "by_type": json_result["by_type"],
            "per_document": json_result["per_document"],
        },
        "marker": {
            "micro": micro_marker,
            "by_type": marker_result["by_type"],
            "per_document": marker_result["per_document"],
        },
    }
    (OUTPUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")

    # predictions_json.json
    (OUTPUT_DIR / "predictions_json.json").write_text(
        json.dumps(json_result["predictions"], indent=2, ensure_ascii=False) + "\n")

    # predictions_marker.json
    (OUTPUT_DIR / "predictions_marker.json").write_text(
        json.dumps(marker_result["predictions"], indent=2, ensure_ascii=False) + "\n")

    # errors.json
    all_errors = json_result["errors"] + marker_result["errors"]
    (OUTPUT_DIR / "errors.json").write_text(json.dumps(all_errors, indent=2, ensure_ascii=False) + "\n")

    # per_document_metrics.json
    per_doc = {}
    for jid in JOB_IDS:
        per_doc[jid] = {
            "json": json_result["per_document"].get(jid, compute_metrics(0, 0, 0)),
            "marker": marker_result["per_document"].get(jid, compute_metrics(0, 0, 0)),
        }
    (OUTPUT_DIR / "per_document_metrics.json").write_text(json.dumps(per_doc, indent=2, ensure_ascii=False) + "\n")

    # summary.md
    invalid_total = json_result["invalid_outputs"] + marker_result["invalid_outputs"]

    error_counts: dict[str, int] = defaultdict(int)
    for e in all_errors:
        error_counts[e["error_type"]] += 1
    top_errors = sorted(error_counts.items(), key=lambda x: -x[1])

    summary_lines = [
        "# Prompt Baseline Offline Reassessment",
        "",
        "## Hinweise",
        "- Technischer Smoke Test auf fünf künstlichen Anzeigen",
        "- Noch keine belastbare wissenschaftliche Evaluation",
        "- Alte Marker-F1 von 0,000 entstand durch einen Validierungsfehler",
        "  (Texttreueprüfung scheiterte an abschließendem Newline-Zeichen)",
        "- Korrigierte Texttreueprüfung ignoriert genau einen abschließenden \\n oder \\r\\n",
        "",
        "## Ergebnisse",
        "",
        "### JSON Prompt",
        f"- Micro Precision: {micro_json['precision']:.4f}",
        f"- Micro Recall: {micro_json['recall']:.4f}",
        f"- Micro F1: {micro_json['f1']:.4f}",
        f"- TP: {micro_json['tp']}, FP: {micro_json['fp']}, FN: {micro_json['fn']}",
        "",
        "### Marker Prompt",
        f"- Micro Precision: {micro_marker['precision']:.4f}",
        f"- Micro Recall: {micro_marker['recall']:.4f}",
        f"- Micro F1: {micro_marker['f1']:.4f}",
        f"- TP: {micro_marker['tp']}, FP: {micro_marker['fp']}, FN: {micro_marker['fn']}",
        "",
        "### F1 pro Entitätstyp",
        "| Typ | JSON F1 | Marker F1 |",
        "|-----|---------|-----------|",
    ]
    for t in ENTITY_TYPES:
        jf1 = json_result["by_type"][t]["f1"]
        mf1 = marker_result["by_type"][t]["f1"]
        summary_lines.append(f"| {t} | {jf1:.4f} | {mf1:.4f} |")

    summary_lines.extend([
        "",
        "### F1 pro Anzeige",
        "| Anzeige | JSON F1 | Marker F1 |",
        "|---------|---------|-----------|",
    ])
    for jid in JOB_IDS:
        jf1 = json_result["per_document"].get(jid, compute_metrics(0, 0, 0))["f1"]
        mf1 = marker_result["per_document"].get(jid, compute_metrics(0, 0, 0))["f1"]
        summary_lines.append(f"| {jid} | {jf1:.4f} | {mf1:.4f} |")

    summary_lines.extend([
        "",
        f"### Ungültige Ausgaben insgesamt: {invalid_total}",
        "",
        "### Häufigste Fehlerkategorien",
    ])
    for cat, cnt in top_errors:
        summary_lines.append(f"- {cat}: {cnt}")

    summary_lines.extend([
        "",
        "### Neu erstellte / geänderte Dateien",
        "- artifacts/prompt_baseline_offline_reassessment/metrics.json",
        "- artifacts/prompt_baseline_offline_reassessment/predictions_json.json",
        "- artifacts/prompt_baseline_offline_reassessment/predictions_marker.json",
        "- artifacts/prompt_baseline_offline_reassessment/errors.json",
        "- artifacts/prompt_baseline_offline_reassessment/per_document_metrics.json",
        "- artifacts/prompt_baseline_offline_reassessment/summary.md",
        "- scripts/offline_reassessment.py",
    ])

    (OUTPUT_DIR / "summary.md").write_text("\n".join(summary_lines) + "\n")

    # Print summary to stdout
    print("=" * 60)
    print("OFFLINE REASSESSMENT COMPLETE")
    print("=" * 60)
    print(f"\nJSON Micro-F1: {micro_json['f1']:.4f}")
    print(f"Marker Micro-F1: {micro_marker['f1']:.4f}")
    print(f"\nF1 per type:")
    for t in ENTITY_TYPES:
        jf1 = json_result["by_type"][t]["f1"]
        mf1 = marker_result["by_type"][t]["f1"]
        print(f"  {t:20s}  JSON={jf1:.4f}  Marker={mf1:.4f}")
    print(f"\nF1 per document:")
    for jid in JOB_IDS:
        jf1 = json_result["per_document"].get(jid, {"f1": 0.0})["f1"]
        mf1 = marker_result["per_document"].get(jid, {"f1": 0.0})["f1"]
        print(f"  {jid:15s}  JSON={jf1:.4f}  Marker={mf1:.4f}")
    print(f"\nInvalid outputs: {invalid_total}")
    print(f"\nTop error categories:")
    for cat, cnt in top_errors:
        print(f"  {cat}: {cnt}")
    print(f"\nFiles written to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
