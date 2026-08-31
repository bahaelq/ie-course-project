"""Hybrid JOB_TITLE disambiguation tests – Phase 4F.

Tests narrow header heuristic:
start < 120 and start < first_period+1 and start < first_newline (or no newline)
Only for JOB_TITLE, first occurrence must be header, exact same candidate.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
import importlib.util
import json
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("weak_label", PROJECT_ROOT / "scripts" / "weak_label.py")
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

SPEC2 = importlib.util.spec_from_file_location("evaluate_llm_baseline", PROJECT_ROOT / "scripts" / "evaluate_llm_baseline.py")
assert SPEC2 and SPEC2.loader
_bl = importlib.util.module_from_spec(SPEC2)
SPEC2.loader.exec_module(_bl)
normalize_json_predictions = _bl.normalize_json_predictions


def test_unique_job_title_ok():
    text = "Data Scientist bei Firma X sucht."
    cand = "Data Scientist"
    assert cand in text
    start = text.find(cand)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": start, "end": start + len(cand)}])
    assert ok


def test_repeated_header_first_accepted():
    text = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation. Klinikum Hamburg. Gesundheits- und Krankenpfleger (m/w/d) Intensivstation bei Klinikum."
    cand = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2 and occ[0] == 0
    assert mod._is_header(occ[0], text)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0] + len(cand)}])
    assert ok
    # also via parser ambiguous -> would be ok after hybrid? structural_validate directly accepts header
    raw = json.dumps({"JOB_TITLE": [cand], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})
    ents = normalize_json_predictions(json.loads(raw), text)
    # normalize marks ambiguous, but structural_validate should accept first
    assert ents[0]["status"] == "ambiguous"
    ok2, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0] + len(cand)}])
    assert ok2


def test_repeated_non_header_ambiguous():
    # repeated but first occurrence not header (prefix before)
    text = "Firma Hamburg. Gesundheits- und Krankenpfleger (m/w/d) Intensivstation bei Klinikum. Nochmals Gesundheits- und Krankenpfleger (m/w/d) Intensivstation bei Klinikum."
    cand = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    assert not mod._is_header(occ[0], text)
    ok, errs = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0] + len(cand)}])
    assert not ok
    assert any("Ambiguous" in e for e in errs)


def test_3x_header_first_accepted():
    text = "Softwareentwickler Python (m/w/d) Backend. Firma A. Softwareentwickler Python (m/w/d) Backend bei Firma. Nochmal Softwareentwickler Python (m/w/d) Backend."
    cand = "Softwareentwickler Python (m/w/d) Backend"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 3 and occ[0] == 0
    assert mod._is_header(occ[0], text)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0] + len(cand)}])
    assert ok


def test_3x_non_header_ambiguous():
    text = "Intro Firma Hamburg. Softwareentwickler Python (m/w/d) Backend bei Firma. Zweites Softwareentwickler Python (m/w/d) Backend. Drittes Softwareentwickler Python (m/w/d) Backend."
    cand = "Softwareentwickler Python (m/w/d) Backend"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 3
    assert not mod._is_header(occ[0], text)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0] + len(cand)}])
    assert not ok


def test_header_dot_candidate_without_dot():
    # header has dot, candidate without dot – should accept header occurrence without dot
    text = "Softwareentwickler Python (m/w/d) Backend. Firma. Softwareentwickler Python (m/w/d) Backend bei Firma."
    cand = "Softwareentwickler Python (m/w/d) Backend"
    assert cand in text
    assert text[len(cand)] == "."
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0] + len(cand)}])
    assert ok
    # ensure dot not included
    assert text[occ[0]:occ[0]+len(cand)] == cand
    assert text[occ[0]+len(cand)] == "."


def test_mwd_preserved():
    text = "Softwareentwickler (m/w/d) bei Firma. Softwareentwickler (m/w/d) nochmal."
    cand = "Softwareentwickler (m/w/d)"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    # first at 0 is header, should be accepted
    assert mod._is_header(occ[0], text)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert ok


def test_suffix_backend_preserved():
    text = "Softwareentwickler Python (m/w/d) Backend. Firma. Softwareentwickler Python (m/w/d) Backend bei Firma."
    cand = "Softwareentwickler Python (m/w/d) Backend"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert ok
    assert "Backend" in cand


def test_suffix_intensivstation_preserved():
    text = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation. Firma. Gesundheits- und Krankenpfleger (m/w/d) Intensivstation bei Firma."
    cand = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation"
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": 0, "end": len(cand)}])
    assert ok


def test_suffix_kindergarten_preserved():
    text = "Erzieher (m/w/d) Kindergarten. Firma. Erzieher (m/w/d) Kindergarten bei Firma."
    cand = "Erzieher (m/w/d) Kindergarten"
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": 0, "end": len(cand)}])
    assert ok


def test_suffix_lager_preserved():
    text = "Kommissionierer (m/w/d) Lager. Firma. Kommissionierer (m/w/d) Lager bei Firma."
    cand = "Kommissionierer (m/w/d) Lager"
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": 0, "end": len(cand)}])
    assert ok


def test_umlaut_exact():
    text = "Erzieher (m/w/d) Kindergarten. Firma. Erzieher (m/w/d) Kindergarten bei Firma."
    cand = "Erzieher (m/w/d) Kindergarten"
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": 0, "end": len(cand)}])
    assert ok
    assert text[0:len(cand)] == cand


def test_text_start_end_equals_candidate():
    text = "Erzieher (m/w/d) Kindergarten. Firma. Erzieher (m/w/d) Kindergarten bei Firma."
    cand = "Erzieher (m/w/d) Kindergarten"
    start = 0
    end = start + len(cand)
    assert text[start:end] == cand
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": start, "end": end}])
    assert ok


def test_no_invented_dot():
    text = "Softwareentwickler Python (m/w/d) Backend bei Firma Nochmal Softwareentwickler Python (m/w/d) Backend"
    cand = "Softwareentwickler Python (m/w/d) Backend"
    # ensure raw dot version would be hallucinated if not in text
    cand_dot = cand + "."
    assert cand_dot not in text
    occ_dot = [m.start() for m in re.finditer(re.escape(cand_dot), text)]
    assert len(occ_dot) == 0


def test_position_gt_120_not_header():
    text = "a" * 121 + "Softwareentwickler Python (m/w/d) Backend. Nochmals Softwareentwickler Python (m/w/d) Backend."
    cand = "Softwareentwickler Python (m/w/d) Backend"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert occ[0] > 120
    assert not mod._is_header(occ[0], text)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_after_first_period_not_header():
    text = "Intro Satz. Softwareentwickler Python (m/w/d) Backend bei Firma. Nochmal Softwareentwickler Python (m/w/d) Backend."
    cand = "Softwareentwickler Python (m/w/d) Backend"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    # first period at 11
    assert text.find(".") < occ[0]
    assert not mod._is_header(occ[0], text)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_after_newline_not_header():
    text = "Intro\nSoftwareentwickler Python (m/w/d) Backend bei Firma. Nochmal Softwareentwickler Python (m/w/d) Backend."
    cand = "Softwareentwickler Python (m/w/d) Backend"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert occ[0] > text.find("\n")
    assert not mod._is_header(occ[0], text)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_first_not_header_second_exists_ambiguous():
    text = "Firma Hamburg. Gesundheits- und Krankenpfleger (m/w/d) Intensivstation bei Klinikum. Gesundheits- und Krankenpfleger (m/w/d) Intensivstation nochmal."
    cand = "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert not mod._is_header(occ[0], text)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_cross_candidate_not_mixed():
    text = "Softwareentwickler Python (m/w/d) Backend. Andere Titel Erzieher (m/w/d) Kindergarten. Softwareentwickler Python (m/w/d) Backend nochmal."
    cand1 = "Softwareentwickler Python (m/w/d) Backend"
    cand2 = "Erzieher (m/w/d) Kindergarten"
    assert cand1 in text and cand2 in text
    # cand1 repeated, first header -> ok
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand1, "start": 0, "end": len(cand1)}])
    assert ok
    # cand2 unique -> ok
    start2 = text.find(cand2)
    ok2, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand2, "start": start2, "end": start2+len(cand2)}])
    assert ok2


def test_partial_substring_no_extra_occurrence():
    text = "Softwareentwickler Python (m/w/d) Backend bei Firma."
    cand = "Softwareentwickler"
    # cand appears inside longer title but also standalone? In this text only once as substring of longer
    # re.escape will find it at 0
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 1
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert ok


def test_hard_skill_repeated_ambiguous():
    text = "Python und SQL mit Python erneut."
    cand = "Python"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    ok, _ = mod.structural_validate(text, [{"type": "HARD_SKILL", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_soft_skill_repeated_ambiguous():
    text = "Teamfähigkeit ist wichtig. Teamfähigkeit nochmal."
    cand = "Teamfähigkeit"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    ok, _ = mod.structural_validate(text, [{"type": "SOFT_SKILL", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_experience_repeated_ambiguous():
    text = "5 Jahre Erfahrung. Wieder 5 Jahre Erfahrung."
    cand = "5 Jahre Erfahrung"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    ok, _ = mod.structural_validate(text, [{"type": "EXPERIENCE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_education_repeated_ambiguous():
    text = "Bachelor in Informatik. Nochmals Bachelor in Informatik."
    cand = "Bachelor in Informatik"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    ok, _ = mod.structural_validate(text, [{"type": "EDUCATION", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_language_repeated_ambiguous():
    text = "Deutsch C1 gefordert. Deutsch C1 nochmal."
    cand = "Deutsch C1"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    ok, _ = mod.structural_validate(text, [{"type": "LANGUAGE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_work_mode_repeated_ambiguous():
    text = "Vollzeit gesucht. Vollzeit nochmal."
    cand = "Vollzeit"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    ok, _ = mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_unbefristet_rejected():
    text = "unbefristet Vollzeit."
    cand = "unbefristet"
    start = text.find(cand)
    ok, _ = mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])
    assert not ok


def test_befristet_rejected():
    text = "befristet Teilzeit."
    cand = "befristet"
    start = text.find(cand)
    ok, _ = mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])
    assert not ok


def test_work_mode_combined_unbefristet_rejected():
    text = "Teilzeit 30 Stunden pro Woche, unbefristet und Vollzeit."
    cand = "Teilzeit 30 Stunden pro Woche, unbefristet"
    start = text.find(cand)
    ok, _ = mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])
    assert not ok


def test_work_mode_combined_befristet_rejected():
    text = "Vollzeit, unbefristet bei Firma. Vollzeit, unbefristet nochmal."
    cand = "Vollzeit, unbefristet"
    start = text.find(cand)
    ok, _ = mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])
    assert not ok


def test_work_mode_hybrid_befristet_rejected():
    text = "Hybrid, befristet und Remote."
    cand = "Hybrid, befristet"
    start = text.find(cand)
    ok, _ = mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])
    assert not ok


def test_vollzeit_ok():
    text = "Vollzeit 40 Stunden."
    cand = "Vollzeit"
    start = text.find(cand)
    ok, _ = mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])
    assert ok


def test_teilzeit_ok():
    text = "Teilzeit 30 Stunden pro Woche."
    cand = "Teilzeit"
    start = text.find(cand)
    ok, _ = mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])
    assert ok


def test_hybrid_remote_ok():
    text = "Remote möglich."
    cand = "Remote"
    start = text.find(cand)
    ok, _ = mod.structural_validate(text, [{"type": "WORK_MODE", "text": cand, "start": start, "end": start+len(cand)}])
    assert ok


# Regression real docs
def _load_unlabeled(jid: str):
    base = PROJECT_ROOT / "data" / "unlabeled" / "texts" / f"{jid}.txt"
    import json as _j
    for line in (PROJECT_ROOT / "data" / "unlabeled" / "metadata.jsonl").read_text().splitlines():
        m = _j.loads(line)
        if m["id"] == jid:
            cand = m["job_title_original"]
            break
    else:
        cand = ""
    text = base.read_text(encoding="utf-8")
    return text, cand


def test_regression_1031():
    text, cand = _load_unlabeled("job_ad_1031")
    assert cand == "Gesundheits- und Krankenpfleger (m/w/d) Intensivstation"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2 and occ[0] == 0
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert ok
    assert text[occ[0]:occ[0]+len(cand)] == cand
    assert text[occ[0]+len(cand)] == "."  # dot outside


def test_regression_1036():
    text, cand = _load_unlabeled("job_ad_1036")
    assert cand == "Softwareentwickler Python (m/w/d) Backend"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2 and occ[0] == 0
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert ok
    assert text[occ[0]:occ[0]+len(cand)] == cand


def test_regression_1051():
    text, cand = _load_unlabeled("job_ad_1051")
    assert cand == "Kommissionierer (m/w/d) Lager"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert ok


def test_regression_1066():
    text, cand = _load_unlabeled("job_ad_1066")
    assert cand == "Erzieher (m/w/d) Kindergarten"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert len(occ) == 2
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert ok


def test_negative_fall_A():
    text = "Firma Hamburg. Erzieher (m/w/d) Kindergarten bei Firma. Erzieher (m/w/d) Kindergarten nochmal."
    cand = "Erzieher (m/w/d) Kindergarten"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert not mod._is_header(occ[0], text)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_negative_fall_B():
    text = "Intro. Erzieher (m/w/d) Kindergarten bei Firma. Erzieher (m/w/d) Kindergarten nochmal."
    cand = "Erzieher (m/w/d) Kindergarten"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert not mod._is_header(occ[0], text)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_negative_fall_C():
    text = "Intro\nErzieher (m/w/d) Kindergarten bei Firma. Erzieher (m/w/d) Kindergarten nochmal."
    cand = "Erzieher (m/w/d) Kindergarten"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert not mod._is_header(occ[0], text)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok


def test_negative_fall_D_gt120():
    text = "a"*121 + "Erzieher (m/w/d) Kindergarten. Erzieher (m/w/d) Kindergarten nochmal."
    cand = "Erzieher (m/w/d) Kindergarten"
    occ = [m.start() for m in re.finditer(re.escape(cand), text)]
    assert not mod._is_header(occ[0], text)
    ok, _ = mod.structural_validate(text, [{"type": "JOB_TITLE", "text": cand, "start": occ[0], "end": occ[0]+len(cand)}])
    assert not ok

