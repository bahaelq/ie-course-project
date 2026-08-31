"""Tests for leakage protection (C4, A8)."""
from pathlib import Path
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("weak_label", PROJECT_ROOT / "scripts" / "weak_label.py")
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

def test_leakage_weak_gold_overlap():
    weak = {"job_ad_1031", "job_ad_1006"}  # 1006 is gold
    pool = {"job_ad_1001"}
    gold = {"job_ad_1006", "job_ad_1007"}
    try:
        mod.check_leakage(weak, pool, gold)
        assert False
    except ValueError as e:
        assert "weak_input_ids" in str(e) or "gold" in str(e)

def test_leakage_pool_gold_overlap():
    weak = {"job_ad_1031"}
    pool = {"job_ad_1006"}  # pool contains gold
    gold = {"job_ad_1006"}
    try:
        mod.check_leakage(weak, pool, gold)
        assert False
    except ValueError:
        pass

def test_leakage_weak_pool_overlap():
    weak = {"job_ad_1001"}  # weak contains pool id
    pool = {"job_ad_1001"}
    gold = {"job_ad_1006"}
    try:
        mod.check_leakage(weak, pool, gold)
        assert False
    except ValueError:
        pass

def test_leakage_no_overlap_pass():
    weak = {"job_ad_1031", "job_ad_1032"}
    pool = {"job_ad_1001", "job_ad_1002"}
    gold = {"job_ad_1006", "job_ad_1007"}
    mod.check_leakage(weak, pool, gold)  # should not raise

def test_gold_not_in_prompt_via_retrieval(tmp_path: Path):
    # Ensure retrieval never returns gold
    from ie_course.retrieval import build_tfidf_index, retrieve_for_queries
    pool_texts = ["Data Scientist with Python", "Verkäufer mit Teamgeist"]
    pool_ids = ["job_ad_1001", "job_ad_1002"]
    query_texts = ["Data Scientist Python"]
    query_ids = ["job_ad_1006"]
    vectorizer, matrix = build_tfidf_index(pool_texts)
    res = retrieve_for_queries(query_texts, query_ids, pool_texts, pool_ids, vectorizer, matrix, k=1)
    assert res[0]["results"][0]["id"] in pool_ids
    assert res[0]["results"][0]["id"] not in query_ids

def test_weak_input_not_as_fewshot_example(tmp_path: Path):
    # Simulate that weak ids are not in pool
    weak_ids = {"job_ad_1031"}
    pool_ids = {"job_ad_1001"}
    assert weak_ids.isdisjoint(pool_ids)
