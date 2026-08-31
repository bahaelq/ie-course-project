"""Tests for parsing (C10, A4)."""
from pathlib import Path
import importlib.util
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("weak_label", PROJECT_ROOT / "scripts" / "weak_label.py")
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

SAMPLE_TEXT = "Wir suchen Data Scientist mit Python in Vollzeit in Berlin."

def test_valid_json():
    raw = json.dumps({"JOB_TITLE": ["Data Scientist"], "HARD_SKILL": ["Python"], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": ["Vollzeit"]})
    ents, err, status = mod.parse_llm_output(SAMPLE_TEXT, raw)
    assert err is None
    # Should have 3 ok entities
    ok = [e for e in ents if e["status"] == "ok"]
    assert len(ok) == 3

def test_invalid_json():
    raw = "{ not json"
    ents, err, status = mod.parse_llm_output(SAMPLE_TEXT, raw)
    assert err is not None
    assert status == "parse_error"

def test_markdown_wrapper():
    raw = "```json\n" + json.dumps({"JOB_TITLE": ["Data Scientist"], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []}) + "\n```"
    ents, err, status = mod.parse_llm_output(SAMPLE_TEXT, raw)
    assert err is None

def test_unknown_type():
    raw = json.dumps({"JOB_TITLE": [], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": [], "UNKNOWN_TYPE": ["foo"]})
    ents, err, status = mod.parse_llm_output(SAMPLE_TEXT, raw)
    # validate_schema should fail
    assert err is not None

def test_missing_type():
    raw = json.dumps({"JOB_TITLE": ["Data Scientist"]})  # missing other keys
    ents, err, status = mod.parse_llm_output(SAMPLE_TEXT, raw)
    assert err is not None

def test_hallucinated():
    raw = json.dumps({"JOB_TITLE": ["Unicorn"], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, err, status = mod.parse_llm_output(SAMPLE_TEXT, raw)
    # Unicorn not in text -> hallucinated
    hall = [e for e in ents if e["status"] == "hallucinated"]
    assert len(hall) == 1

def test_ambiguous():
    # Text with duplicate word
    text = "Python und Python sind gefragt."
    raw = json.dumps({"JOB_TITLE": [], "HARD_SKILL": ["Python"], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, err, status = mod.parse_llm_output(text, raw)
    amb = [e for e in ents if e["status"] == "ambiguous"]
    assert len(amb) == 1

def test_empty_span():
    raw = json.dumps({"JOB_TITLE": [""], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, err, status = mod.parse_llm_output(SAMPLE_TEXT, raw)
    # Empty should be hallucinated or parse error? Our normalize will check positions empty -> hallucinated
    # At least not ok
    ok = [e for e in ents if e["status"] == "ok"]
    assert len(ok) == 0
