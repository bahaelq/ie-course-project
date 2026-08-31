"""Tests for JOB_TITLE v3 prompt and WORK_MODE guard."""
from pathlib import Path
import importlib.util
import json
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("weak_label", PROJECT_ROOT / "scripts" / "weak_label.py")
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

# Helper to find prompt
def get_prompt():
    return mod.build_fewshot_prompt_for_weak("dummy", [])

def test_prompt_version_is_v3():
    p = get_prompt()
    assert "unbefristet" in p.lower()
    # Check that prompt mentions unique span and not inventing punctuation
    assert "Do not invent punctuation" in p
    assert "unique" in p.lower()
    assert "verifiable" in p.lower() or "verbatim" in p.lower()

def test_unique_long_job_title():
    text = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation. Gesucht wird etwas anderes."
    cand = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation."
    start = text.find(cand)
    ents = [{"type": "JOB_TITLE", "text": cand, "start": start, "end": start+len(cand)}]
    ok, _ = mod.structural_validate(text, ents)
    assert ok

def test_job_title_with_mwd():
    text = "Wir suchen Softwareentwickler (m/w/d) für Berlin."
    cand = "Softwareentwickler (m/w/d)"
    start = text.find(cand)
    assert mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": start, "end": start+len(cand)}])[0]

def test_backend_suffix():
    text = "Softwareentwickler Python (m/w/d) Backend. Firma X."
    cand = "Softwareentwickler Python (m/w/d) Backend"
    # Need to ensure candidate appears once; add period to make unique
    text2 = "Softwareentwickler Python (m/w/d) Backend. Firma und Softwareentwickler Python (m/w/d) Backend bei Firma"
    cand_with_dot = "Softwareentwickler Python (m/w/d) Backend."
    start = text2.find(cand_with_dot)
    assert start != -1
    assert mod.structural_validate(text2, [{"type": "JOB_TITLE", "text": cand_with_dot, "start": start, "end": start+len(cand_with_dot)}])[0]

def test_intensivstation_suffix():
    text = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation. Klinikum."
    cand = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation"
    # This appears once if text only has header, but if we have duplicate without dot, it will be 1
    # Use text with single occurrence
    assert mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": text.find(cand), "end": text.find(cand)+len(cand)}])[0]

def test_kindergarten_suffix():
    text = "Erzieher (m/w/d) Kindergarten. Kita."
    cand = "Erzieher (m/w/d) Kindergarten"
    assert mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": text.find(cand), "end": text.find(cand)+len(cand)}])[0]

def test_lager_suffix():
    text = "Kommissionierer (m/w/d) Lager. Logistik."
    cand = "Kommissionierer (m/w/d) Lager"
    assert mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": text.find(cand), "end": text.find(cand)+len(cand)}])[0]

def test_identical_full_span_twice_ambiguous():
    text = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation. Gesucht wird ein Gesundheits- und Krankenpfleger (m/w/d) Intensivstation bei Klinikum."
    cand = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    raw = json.dumps({"JOB_TITLE": [cand], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, _, _ = mod.parse_llm_output(text, raw)
    assert ents[0]["status"] == "ambiguous"

def test_identical_full_span_three_times_ambiguous():
    text = "Titel X. Titel X. Titel X."
    cand = "Titel X"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 3
    raw = json.dumps({"JOB_TITLE": [cand], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, _, _ = mod.parse_llm_output(text, raw)
    assert ents[0]["status"] == "ambiguous"

def test_dot_makes_unique():
    text = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation. Gesucht wird ein Gesundheits- und Krankenpfleger (m/w/d) Intensivstation bei Klinikum."
    cand_dot = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation."
    occ = [m.start() for m in re.finditer(re.escape(cand_dot), text)]
    assert len(occ) == 1
    ents = [{"type": "JOB_TITLE", "text": cand_dot, "start": occ[0], "end": occ[0]+len(cand_dot)}]
    assert mod.structural_validate(text, ents)[0]

def test_invented_dot_not_ok():
    text = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation bei Klinikum"
    cand = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation."
    # cand with dot not in text
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 0
    raw = json.dumps({"JOB_TITLE": [cand], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, _, _ = mod.parse_llm_output(text, raw)
    assert ents[0]["status"] == "hallucinated"

def test_no_invented_word():
    text = "Wir suchen Data Scientist."
    cand = "Data Scientist Senior"
    raw = json.dumps({"JOB_TITLE": [cand], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, _, _ = mod.parse_llm_output(text, raw)
    assert ents[0]["status"] == "hallucinated"

def test_partial_does_not_create_ambiguity():
    text = "Softwareentwickler Python (m/w/d) Backend. Kenntnisse in Python."
    cand = "Softwareentwickler Python (m/w/d) Backend"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 1
    # Python appears twice, but should not affect candidate
    ents = [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}]
    assert mod.structural_validate(text, ents)[0]

def test_python_not_mixed_with_job_title():
    text = "Softwareentwickler Python (m/w/d) Backend. Kenntnisse in Python."
    raw = json.dumps({"JOB_TITLE": ["Softwareentwickler Python (m/w/d) Backend"], "HARD_SKILL": ["Python"], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, _, _ = mod.parse_llm_output(text, raw)
    job = [e for e in ents if e["type"]=="JOB_TITLE"][0]
    hard = [e for e in ents if e["type"]=="HARD_SKILL"][0]
    assert job["status"] == "ok"
    assert hard["status"] == "ambiguous"  # Python 2×

def test_different_candidates_not_mixed():
    text = "Wir suchen Data Scientist mit Python."
    raw = json.dumps({"JOB_TITLE": ["Data Scientist"], "HARD_SKILL": ["Python"], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, _, _ = mod.parse_llm_output(text, raw)
    assert all(e["status"]=="ok" for e in ents)

def test_umlaut():
    text = "Wir suchen Ärztin für Übernahme."
    cand = "Ärztin"
    start = text.find(cand)
    assert mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": start, "end": start+len(cand)}])[0]

def test_duplicate_full_candidate():
    text = "Wir suchen Data Scientist."
    cand = "Data Scientist"
    start = text.find(cand)
    ents = [
        {"type": "JOB_TITLE", "text": cand, "start": start, "end": start+len(cand)},
        {"type": "JOB_TITLE", "text": cand, "start": start, "end": start+len(cand)},
    ]
    ok, errs = mod.structural_validate(text, ents)
    assert not ok
    assert any("Duplicate" in e for e in errs)

def test_work_mode_unbefristet_rejected():
    text = "Wir bieten unbefristet."
    cand = "unbefristet"
    start = text.find(cand)
    ok, _ = mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])
    assert not ok

def test_work_mode_befristet_rejected():
    text = "Wir bieten befristet."
    cand = "befristet"
    start = text.find(cand)
    ok, _ = mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])
    assert not ok

def test_work_mode_vollzeit_ok():
    text = "Wir bieten Vollzeit."
    cand = "Vollzeit"
    start = text.find(cand)
    assert mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])[0]

def test_work_mode_teilzeit_ok():
    text = "Wir bieten Teilzeit 30 Stunden pro Woche."
    cand = "Teilzeit 30 Stunden pro Woche"
    start = text.find(cand)
    assert mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])[0]

def test_work_mode_hybrid_ok():
    text = "Wir bieten Hybrid möglich."
    cand = "Hybrid"
    start = text.find(cand)
    assert mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])[0]

def test_work_mode_remote_ok():
    text = "Wir bieten Remote Arbeit."
    cand = "Remote"
    start = text.find(cand)
    assert mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])[0]

def test_parser_keeps_ambiguous():
    text = "Titel X. Titel X."
    cand = "Titel X"
    raw = json.dumps({"JOB_TITLE": [cand], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents, _, _ = mod.parse_llm_output(text, raw)
    assert ents[0]["status"] == "ambiguous"
    # Ensure not converted to ok
    assert not any(e["status"]=="ok" and e["text"]==cand for e in ents)
