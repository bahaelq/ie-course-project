#!/usr/bin/env python3
"""Minimal retrieval for few-shot IE: TF-IDF + cosine, deterministic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:  # pragma: no cover
    TfidfVectorizer = None  # type: ignore
    cosine_similarity = None  # type: ignore


def load_example_pool(example_pool_dir: Path) -> list[dict[str, Any]]:
    texts_dir = example_pool_dir / "texts"
    ann_dir = example_pool_dir / "annotations"
    if not texts_dir.exists():
        return []
    examples: list[dict[str, Any]] = []
    for text_path in sorted(texts_dir.glob("job_ad_*.txt")):
        stem = text_path.stem
        gold_path = ann_dir / f"{stem}.json"
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


def load_gold_texts(gold_dir: Path) -> list[dict[str, Any]]:
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
        gold = json.loads(gold_path.read_text(encoding="utf-8")) if gold_path.exists() else {"id": stem, "entities": []}
        examples.append({"id": stem, "text": text_path.read_text(encoding="utf-8"), "gold": gold})
    return sorted(examples, key=lambda x: x["id"])


def build_tfidf_index(example_texts: list[str]):
    if TfidfVectorizer is None:
        raise RuntimeError("scikit-learn not available")
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=5000, lowercase=True)
    matrix = vectorizer.fit_transform(example_texts)
    return vectorizer, matrix


def retrieve_for_queries(
    query_texts: list[str],
    query_ids: list[str],
    example_texts: list[str],
    example_ids: list[str],
    vectorizer: Any,
    example_matrix: Any,
    k: int = 2,
    embedding_model: str = "tfidf-sklearn",
) -> list[dict[str, Any]]:
    if not example_texts:
        return []
    query_matrix = vectorizer.transform(query_texts)
    sims = cosine_similarity(query_matrix, example_matrix)
    results: list[dict[str, Any]] = []
    for qi, qid in enumerate(query_ids):
        scores = sims[qi]
        # deterministic: sort by (-score, example_id)
        ranked = sorted(range(len(example_ids)), key=lambda i: (-scores[i], example_ids[i]))
        topk_idx = ranked[: min(k, len(example_ids))]
        topk = [
            {"rank": r + 1, "id": example_ids[idx], "score": float(scores[idx])}
            for r, idx in enumerate(topk_idx)
        ]
        results.append(
            {
                "query_id": qid,
                "k": k,
                "embedding_model": embedding_model,
                "results": topk,
            }
        )
    return results


def retrieve_top_k(
    gold_dir: Path,
    example_pool_dir: Path,
    k: int = 2,
    embedding_model: str = "tfidf-sklearn",
) -> list[dict[str, Any]]:
    gold_examples = load_gold_texts(gold_dir)
    pool_examples = load_example_pool(example_pool_dir)
    if not pool_examples:
        return []
    # Ensure no overlap: gold ids must not be in pool
    pool_ids = {ex["id"] for ex in pool_examples}
    for gex in gold_examples:
        if gex["id"] in pool_ids:
            raise ValueError(f"Gold id {gex['id']} also in example_pool — retrieval leakage")
    example_texts = [ex["text"] for ex in pool_examples]
    example_ids = [ex["id"] for ex in pool_examples]
    query_texts = [ex["text"] for ex in gold_examples]
    query_ids = [ex["id"] for ex in gold_examples]
    vectorizer, matrix = build_tfidf_index(example_texts)
    return retrieve_for_queries(query_texts, query_ids, example_texts, example_ids, vectorizer, matrix, k=k, embedding_model=embedding_model)
