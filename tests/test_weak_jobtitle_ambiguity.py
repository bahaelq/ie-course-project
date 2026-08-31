"""Tests for JOB_TITLE ambiguity and WORK_MODE guard (Phase 4B)."""
from pathlib import Path
import importlib.util
import json
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("weak_label", PROJECT_ROOT / "scripts" / "weak_label.py")
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

SAMPLE_TEXT_1031 = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation. Klinikum Hamburg Altona Hamburg, Hamburg. Gesundheits- und Krankenpfleger (m/w/d) Intensivstation bei Klinikum Hamburg Altona Hamburg."
SAMPLE_TEXT_1036 = "Softwareentwickler Python (m/w/d) Backend. HanseCode GmbH Hamburg, Hamburg. Softwareentwickler Python (m/w/d) Backend bei HanseCode GmbH Hamburg."

def test_unique_long_job_title_with_repeated_substring():
    # Full unique title with period should be ok (only once)
    text = SAMPLE_TEXT_1031
    candidate = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation."
    occ = [m.start() for m in re.finditer(re.escape(candidate), text)]
    assert len(occ) == 1
    ents = [{"type": "JOB_TITLE", "text": candidate, "start": occ[0], "end": occ[0]+len(candidate)}]
    ok, errs = mod.structural_validate(text, ents)
    assert ok

def test_job_title_with_mw_d():
    text = "Wir suchen Softwareentwickler (m/w/d) für Berlin."
    cand = "Softwareentwickler (m/w/d)"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 1
    ents = [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}]
    ok, errs = mod.structural_validate(text, ents)
    assert ok

def test_job_title_with_suffix():
    text = SAMPLE_TEXT_1036
    cand = "Softwareentwickler Python (m/w/d) Backend."
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 1
    ents = [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}]
    ok, errs = mod.structural_validate(text, ents)
    assert ok

def test_repeated_full_job_title_is_ambiguous():
    # With hybrid header disambiguation, a JOB_TITLE whose first occurrence is in header should be accepted
    text = SAMPLE_TEXT_1031
    cand = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    # Parser still returns ambiguous (hybrid is applied at weak_label main level, not inside parse_llm_output)
    # So parse_llm_output should still mark as ambiguous
    raw = json.dumps({"JOB_TITLE": [cand], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, err, status = mod.parse_llm_output(text, raw)
    amb = [e for e in ents if e["status"] == "ambiguous"]
    assert len(amb) == 1
    # Structural validation with hybrid should now accept first header occurrence
    ents2 = [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}]
    ok, errs = mod.structural_validate(text, ents2)
    # With header hybrid, this should be ok (first is header)
    assert ok, f"Expected header disambiguation to be ok, got errs {errs}"

def test_partial_substring_does_not_create_ambiguity():
    # Full candidate appears once, substring "Python" appears twice, but should not affect full candidate
    text = "Softwareentwickler Python (m/w/d) Backend. Kenntnisse in Python erforderlich."
    cand = "Softwareentwickler Python (m/w/d) Backend"
    occ_full = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ_full) == 1
    occ_sub = [m.start() for m in re.finditer(re.escape("Python"), text)]
    assert len(occ_sub) == 2
    ents = [{"type": "JOB_TITLE", "text": cand, "start": occ_full[0], "end": occ_full[0]+len(cand)}]
    ok, errs = mod.structural_validate(text, ents)
    assert ok

def test_hallucinated_job_title():
    text = "Wir suchen Data Scientist."
    cand = "Unicorn"
    raw = json.dumps({"JOB_TITLE": [cand], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, err, status = mod.parse_llm_output(text, raw)
    hall = [e for e in ents if e["status"] == "hallucinated"]
    assert len(hall) == 1

def test_work_mode_rejects_unbefristet():
    text = "Wir bieten Teilzeit 30 Stunden pro Woche, unbefristet."
    cand = "unbefristet"
    # Find position
    start = text.find(cand)
    ents = [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}]
    ok, errs = mod.structural_validate(text, ents)
    assert not ok
    assert any("unbefristet" in e.lower() for e in errs)

def test_work_mode_accepts_vollzeit():
    text = "Wir bieten Vollzeit in Berlin."
    cand = "Vollzeit"
    start = text.find(cand)
    ents = [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}]
    ok, errs = mod.structural_validate(text, ents)
    assert ok

def test_work_mode_accepts_hybrid():
    text = "Wir bieten Hybrid möglich."
    cand = "Hybrid"
    start = text.find(cand)
    ents = [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}]
    ok, errs = mod.structural_validate(text, ents)
    assert ok

def test_work_mode_accepts_remote():
    text = "Wir bieten Remote Arbeit."
    cand = "Remote"
    start = text.find(cand)
    ents = [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}]
    ok, errs = mod.structural_validate(text, ents)
    assert ok

def test_education_boundary():
    text = "Du bringst eine abgeschlossene Ausbildung als Pflegefachfrau/-mann mit."
    cand = "abgeschlossene Ausbildung als Pflegefachfrau/-mann mit"
    start = text.find(cand)
    # This has trailing " mit" – should be considered wrong boundary, but structural will pass as it's exact substring
    # However guidelines say boundary without "mit" is correct. Our test here checks that " mit" version is still structurally valid (since it occurs exactly), but prompt should avoid it.
    # For now, we test that the correct without "mit" is valid
    correct = "abgeschlossene Ausbildung als Pflegefachfrau/-mann"
    start2 = text.find(correct)
    ents = [{"type": "EDUCATION", "text": correct, "start": start2, "end": start2+len(correct)}]
    ok, errs = mod.structural_validate(text, ents)
    assert ok

def test_umlaut_exact_span():
    text = "Wir suchen Ärztin für Übernahme."
    cand = "Ärztin"
    start = text.find(cand)
    ents = [{"type": "JOB_TITLE", "text": cand, "start": start, "end": start+len(cand)}]
    ok, errs = mod.structural_validate(text, ents)
    assert ok

def test_duplicate_full_span():
    text = "Wir suchen Data Scientist."
    cand = "Data Scientist"
    start = text.find(cand)
    ents = [
        {"type": "JOB_TITLE", "text": cand, "start": start, "end": start+len(cand)},
        {"type": "JOB_TITLE", "text": cand, "start": start, "end": start+len(cand)},
    ]
    ok, errs = mod.structural_validate(text, ents)
    assert not ok

def test_parser_does_not_mix_entity_candidates():
    # JOB_TITLE candidate appears once, HARD_SKILL Python appears twice, but should not affect JOB_TITLE
    text = "Softwareentwickler Python (m/w/d) Backend. Kenntnisse in Python."
    cand_job = "Softwareentwickler Python (m/w/d) Backend"
    cand_hard = "Python"
    start_job = text.find(cand_job)
    # Only JOB_TITLE should be ok, Python ambiguous
    raw_job = json.dumps({"JOB_TITLE": [cand_job], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents_job, _, _ = mod.parse_llm_output(text, raw_job)
    assert any(e["status"]=="ok" and e["type"]=="JOB_TITLE" for e in ents_job)
    raw_hard = json.dumps({"JOB_TITLE": [], "HARD_SKILL": [cand_hard], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents_hard, _, _ = mod.parse_llm_output(text, raw_hard)
    # Python appears twice -> ambiguous
    assert any(e["status"]=="ambiguous" for e in ents_hard)

def test_repeated_full_job_title_is_ambiguous_via_parser():
    # Ensure parser marks repeated full title as ambiguous, not ok
    text = SAMPLE_TEXT_1031
    cand = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation"
    raw = json.dumps({"JOB_TITLE": [cand], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, _, _ = mod.parse_llm_output(text, raw)
    assert ents[0]["status"] == "ambiguous"

def test_partial_substring_not_counted():
    text = "Wir suchen Data Scientist mit Python."
    # LLM returns correct full title, substring Python inside title should not cause ambiguity for title
    raw = json.dumps({"JOB_TITLE": ["Data Scientist"], "HARD_SKILL": ["Python"], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, _, _ = mod.parse_llm_output(text, raw)
    job_ok = [e for e in ents if e["type"]=="JOB_TITLE" and e["status"]=="ok"]
    assert len(job_ok)==1
