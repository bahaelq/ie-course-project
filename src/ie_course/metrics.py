"""Shared entity-level Precision/Recall/F1, used by every extraction system.

Matching key is (document_id, entity_type, start, end): entities from different
documents with identical offsets must never match each other.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

ALLOWED_TYPES = ("JOB_TITLE", "HARD_SKILL", "SOFT_SKILL", "EXPERIENCE", "EDUCATION", "LANGUAGE", "WORK_MODE")

EntityKey = tuple[str, str, int, int]


def entity_key(doc_id: str, entity: dict[str, Any]) -> EntityKey:
    return (doc_id, entity["type"], entity["start"], entity["end"])


def _keys(entities_by_doc: dict[str, list[dict[str, Any]]]) -> set[EntityKey]:
    keys: set[EntityKey] = set()
    for doc_id, entities in entities_by_doc.items():
        for ent in entities:
            if ent.get("start") is None or ent.get("end") is None:
                continue
            keys.add(entity_key(doc_id, ent))
    return keys


def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def compute_prf(
    gold_by_doc: dict[str, list[dict[str, Any]]],
    pred_by_doc: dict[str, list[dict[str, Any]]],
) -> dict[str, float]:
    """Micro precision/recall/F1 over all documents, keyed by document identity.

    Every document referenced by either side is considered, so predictions for a
    document with no gold entities still count as false positives instead of being
    silently ignored.
    """
    gold_keys = _keys(gold_by_doc)
    pred_keys = _keys(pred_by_doc)
    tp = len(gold_keys & pred_keys)
    fp = len(pred_keys - gold_keys)
    fn = len(gold_keys - pred_keys)
    return _prf(tp, fp, fn)


def compute_prf_by_type(
    gold_by_doc: dict[str, list[dict[str, Any]]],
    pred_by_doc: dict[str, list[dict[str, Any]]],
    types: Iterable[str] = ALLOWED_TYPES,
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for entity_type in types:
        gold_subset = {
            doc_id: [e for e in ents if e["type"] == entity_type] for doc_id, ents in gold_by_doc.items()
        }
        pred_subset = {
            doc_id: [e for e in ents if e["type"] == entity_type] for doc_id, ents in pred_by_doc.items()
        }
        result[entity_type] = compute_prf(gold_subset, pred_subset)
    return result


def evaluate(
    gold_by_doc: dict[str, list[dict[str, Any]]],
    pred_by_doc: dict[str, list[dict[str, Any]]],
    types: Iterable[str] = ALLOWED_TYPES,
) -> dict[str, Any]:
    return {
        "micro": compute_prf(gold_by_doc, pred_by_doc),
        "by_type": compute_prf_by_type(gold_by_doc, pred_by_doc, types),
    }
