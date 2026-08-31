"""Tests for structural validation (C11, A4)."""
from pathlib import Path
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("weak_label", PROJECT_ROOT / "scripts" / "weak_label.py")
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

SAMPLE_TEXT = "Wir suchen Data Scientist mit Python in Vollzeit."

def test_valid_offset():
    ents = [{"type": "JOB_TITLE", "text": "Data Scientist", "start": 11, "end": 25}]
    ok, errs = mod.structural_validate(SAMPLE_TEXT, ents)
    assert ok and not errs

def test_offset_outside():
    ents = [{"type": "JOB_TITLE", "text": "Data Scientist", "start": 100, "end": 110}]
    ok, errs = mod.structural_validate(SAMPLE_TEXT, ents)
    assert not ok

def test_start_ge_end():
    ents = [{"type": "JOB_TITLE", "text": "Data", "start": 5, "end": 5}]
    ok, errs = mod.structural_validate(SAMPLE_TEXT, ents)
    assert not ok

def test_wrong_text_slice():
    ents = [{"type": "JOB_TITLE", "text": "Data", "start": 11, "end": 15}]  # Actually "Data" at 11-15 is correct, try wrong
    # Use start that doesn't match text
    ents2 = [{"type": "JOB_TITLE", "text": "WRONG", "start": 11, "end": 16}]
    ok, errs = mod.structural_validate(SAMPLE_TEXT, ents2)
    assert not ok

def test_umlaut():
    text = "Müller GmbH sucht Ärztin für Übernahme."
    ents = [{"type": "JOB_TITLE", "text": "Ärztin", "start": text.find("Ärztin"), "end": text.find("Ärztin")+len("Ärztin")}]
    ok, errs = mod.structural_validate(text, ents)
    assert ok

def test_overlap():
    text = "Wir suchen Data Scientist mit Python."
    ents = [
        {"type": "JOB_TITLE", "text": "Data Scientist", "start": text.find("Data Scientist"), "end": text.find("Data Scientist")+len("Data Scientist")},
        {"type": "HARD_SKILL", "text": "Data", "start": text.find("Data"), "end": text.find("Data")+4}
    ]
    ok, errs = mod.structural_validate(text, ents)
    assert not ok
    assert any("Overlap" in e for e in errs)

def test_duplicate_span():
    text = "Wir suchen Data Scientist."
    ents = [
        {"type": "JOB_TITLE", "text": "Data Scientist", "start": 11, "end": 25},
        {"type": "JOB_TITLE", "text": "Data Scientist", "start": 11, "end": 25}
    ]
    ok, errs = mod.structural_validate(text, ents)
    assert not ok

def test_invalid_type():
    text = "Wir suchen Data Scientist."
    ents = [{"type": "UNKNOWN", "text": "Data Scientist", "start": 11, "end": 25}]
    ok, errs = mod.structural_validate(text, ents)
    assert not ok
