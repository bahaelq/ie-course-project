#!/usr/bin/env python3
"""Weak labeling pipeline for unlabeled job ads with structural verification.

Data flow:
  data/unlabeled (read-only) -> LLM RAW OUTPUT -> PARSED WEAK LABEL -> AUTOMATED STRUCTURAL VALIDATION -> VERIFIED / REJECTED

Gold and example_pool are strictly read-only. No writes to data/gold, data/example_pool, data/smoke_test, data/unlabeled.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SRC_ROOT: Final[Path] = PROJECT_ROOT / "src"
for p in (str(PROJECT_ROOT), str(SRC_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Reuse existing logic where possible
from ie_course.kisski_client import collect_config, extract_json_payload, request_json, save_artifact
from ie_course.retrieval import build_tfidf_index, load_example_pool

# Reuse baseline helpers for parsing/metrics
import importlib.util
_BASELINE_SPEC = importlib.util.spec_from_file_location("evaluate_llm_baseline", PROJECT_ROOT / "scripts" / "evaluate_llm_baseline.py")
assert _BASELINE_SPEC and _BASELINE_SPEC.loader
_baseline = importlib.util.module_from_spec(_BASELINE_SPEC)
_BASELINE_SPEC.loader.exec_module(_baseline)

ALLOWED_TYPES: Final[tuple[str, ...]] = _baseline.ALLOWED_TYPES  # type: ignore
normalize_json_predictions = _baseline.normalize_json_predictions  # type: ignore
# For structural validation we reuse check_dataset_splits logic via import
import scripts.check_dataset_splits as check_mod  # type: ignore

# Constants
DEFAULT_K: Final[int] = 2
DEFAULT_TEMPERATURE: Final[float] = 0.0
DEFAULT_MODEL: Final[str] = "meta-llama-3.1-8b-instruct"
UNLABELED_DIR: Final[Path] = PROJECT_ROOT / "data" / "unlabeled"
UNLABELED_TEXTS: Final[Path] = UNLABELED_DIR / "texts"
EXAMPLE_POOL_DIR: Final[Path] = PROJECT_ROOT / "data" / "example_pool"
GOLD_DIR: Final[Path] = PROJECT_ROOT / "data" / "gold"
WEAK_BASE: Final[Path] = PROJECT_ROOT / "data" / "weak_labels"

# Status machine
ALLOWED_STATUSES: Final[set[str]] = {
    "pending",
    "api_running",
    "api_error",
    "api_success",
    "parse_error",
    "validation_failed",
    "weak_label_valid",
    "verified",
    "verification_failed",
    # for backward compat, also allow:
    "rejected",
}

RETRYABLE_CODES: Final[set[int]] = {429, 500, 502, 503, 504, 599}
# also retry on timeout/connection (handled via 599 from request_json)


def get_git_sha() -> str:
    try:
        import subprocess
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()[:12]
    except Exception:
        pass
    return "unknown"


def generate_run_id(k: int, temperature: float) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%S_%f")[:-3]
    rand = hashlib.sha256(os.urandom(8)).hexdigest()[:6]
    temp_str = f"{temperature:.1f}".replace(".", "_")
    return f"run_{ts}_k{k}_T{temp_str}_{rand}"


def check_input_guards(input_dir: Path) -> None:
    """Hard guard: input must be exactly data/unlabeled or data/unlabeled/texts and contain only unlabeled IDs."""
    resolved = input_dir.resolve()
    expected_texts = UNLABELED_TEXTS.resolve()
    expected_dir = UNLABELED_DIR.resolve()
    # Allow both data/unlabeled and data/unlabeled/texts
    if resolved != expected_dir and resolved != expected_texts:
        # Also allow if input_dir is a file inside texts? But spec says --input-dir, so dir only
        raise ValueError(f"Input-Split muss exakt 'unlabeled' sein. Erhalten: {input_dir} (erwartet {UNLABELED_DIR} oder {UNLABELED_TEXTS})")

    # Ensure gold/example_pool not used
    gold_resolved = GOLD_DIR.resolve()
    pool_resolved = EXAMPLE_POOL_DIR.resolve()
    if resolved == gold_resolved or resolved == pool_resolved:
        raise ValueError(f"Gold/ExamplePool darf niemals als Weak-Input verwendet werden: {input_dir}")

    # Check that input_dir is under weak allowed base (unlabeled)
    try:
        resolved.relative_to(expected_dir)
    except ValueError:
        raise ValueError(f"Input außerhalb data/unlabeled/texts: {input_dir}")

    # Also ensure not smoke_test
    smoke = (PROJECT_ROOT / "data" / "smoke_test").resolve()
    if resolved == smoke:
        raise ValueError(f"Smoke-Test darf nicht als Weak-Input verwendet werden: {input_dir}")


def load_unlabeled_examples(input_dir: Path, ids_filter: list[str] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """Load unlabeled texts, preserving IDs. Guarantees only unlabeled."""
    # Resolve actual texts dir
    if input_dir.resolve() == UNLABELED_DIR.resolve():
        texts_dir = UNLABELED_TEXTS
    else:
        texts_dir = input_dir
        # Also hard guard: must be under unlabeled/texts
        try:
            texts_dir.resolve().relative_to(UNLABELED_DIR.resolve())
        except ValueError:
            raise ValueError(f"Input-dir muss unter {UNLABELED_DIR} liegen: {input_dir}")

    if not texts_dir.exists():
        raise ValueError(f"Input texts dir not found: {texts_dir}")

    text_paths = sorted(texts_dir.glob("job_ad_*.txt"))
    if ids_filter:
        wanted = set(ids_filter)
        text_paths = [p for p in text_paths if p.stem in wanted]
        missing = wanted - {p.stem for p in text_paths}
        if missing:
            raise ValueError(f"IDs not found in {texts_dir}: {missing}")

    if limit is not None:
        text_paths = text_paths[:limit]

    examples: list[dict[str, Any]] = []
    for p in text_paths:
        # Ensure ID is in expected unlabeled range 1031-1080 but allow generically any unlabeled file
        # Still ensure not gold/pool
        stem = p.stem
        # Check that file is indeed under unlabeled (already)
        # Also ensure ID not in gold/pool to prevent leakage via ID collision
        # We will check leakage separately
        examples.append({"id": stem, "text": p.read_text(encoding="utf-8"), "path": p})
    return sorted(examples, key=lambda x: x["id"])


def load_pool_and_gold_for_leakage(pool_dir: Path, gold_dir: Path) -> tuple[set[str], set[str]]:
    pool_examples = load_example_pool(pool_dir)
    pool_ids = {ex["id"] for ex in pool_examples}
    # Load gold ids
    gold_ids: set[str] = set()
    texts_dir = gold_dir / "texts"
    if texts_dir.exists():
        for p in texts_dir.glob("job_ad_*.txt"):
            gold_ids.add(p.stem)
    else:
        for p in (gold_dir).glob("job_ad_*.txt"):
            gold_ids.add(p.stem)
    return pool_ids, gold_ids


def check_leakage(weak_ids: set[str], pool_ids: set[str], gold_ids: set[str]) -> None:
    if weak_ids & gold_ids:
        raise ValueError(f"Leakage: weak_input_ids ∩ gold_ids != ∅: {weak_ids & gold_ids}")
    if pool_ids & gold_ids:
        raise ValueError(f"Leakage: pool_ids ∩ gold_ids != ∅: {pool_ids & gold_ids}")
    if weak_ids & pool_ids:
        raise ValueError(f"Leakage: weak_input_ids ∩ pool_ids != ∅: {weak_ids & pool_ids}")


def build_fewshot_prompt_for_weak(example_text: str, fewshot_examples: list[dict[str, Any]]) -> str:
    """Few-shot JSON prompt v3 with explicit JOB_TITLE uniqueness and WORK_MODE rules."""
    parts = [
        "You are a strict extractor for job advertisements. "
        "Return only valid JSON. "
        "Use exactly these entity types only: JOB_TITLE, HARD_SKILL, SOFT_SKILL, EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE. "
        "Return a JSON object with exactly these keys: JOB_TITLE, HARD_SKILL, SOFT_SKILL, EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE. "
        "Each value must be a list of strings taken verbatim from the text, no paraphrasing, no normalization. "
        "Do not invent information. If no entity, return []. "
        "Every string must occur exactly as contiguous span in the input text. Do not invent punctuation or words. Copy the exact characters from the document. "
        "Rules: "
        "JOB_TITLE: Provide the full job title as a contiguous exact span. Must occur verbatim. Prefer the complete title from the header. Include \"(m/w/d)\" only if part of the actual title. Keep relevant suffixes (Backend, Intensivstation, Kindergarten, Lager) if they belong to the title. Do not add company/location like \"bei Firma\" or city. JOB_TITLE contains only the job title itself. Punctuation directly after the title is NOT part of JOB_TITLE – never include trailing \".\" \",\" \":\" \";\" even if the header line ends with it. Example: header \"Softwareentwickler Python (m/w/d) Backend.\" → JOB_TITLE must be \"Softwareentwickler Python (m/w/d) Backend\" without the period. Do not use a trailing dot or comma to make an otherwise duplicated title artificially unique. Do not optimize for the longest or globally unique string. The entity text must exactly match the semantic job title span, not an expanded span for parser uniqueness. If the title occurs multiple times, use the exact title as defined above and rely on header disambiguation – do not invent or keep punctuation to force uniqueness. Do not invent punctuation. If no occurrence matches the title definition, return [] for JOB_TITLE. Do not guess. "
        "WORK_MODE: only work model (Vollzeit, Teilzeit, Remote, Homeoffice, Hybrid, mobiles Arbeiten, Schichtarbeit); \"unbefristet\"/\"befristet\" is contract type, NOT WORK_MODE – never output \"unbefristet\" or \"befristet\" alone and never include it inside WORK_MODE (e.g., \"Teilzeit 30 Stunden pro Woche, unbefristet\" → \"Teilzeit 30 Stunden pro Woche\"). "
        "LANGUAGE: only language with explicit level per guidelines (e.g., Deutsch C1, Englisch B2); EDUCATION: only degree/qualification without trailing words like \"mit\"; EXPERIENCE: only concrete work experience; HARD_SKILL: technical skills only, not over-expanded; "
        "Boundaries: only the entity span, no trailing \"mit/bei/und/unbefristet\". "
        "Here are examples:"
    ]
    for ex in fewshot_examples:
        payload: dict[str, list[str]] = {t: [] for t in ALLOWED_TYPES}
        for ent in ex["gold"].get("entities", []):
            payload[ent["type"]].append(ent["text"])
        example_json = json.dumps(payload, ensure_ascii=False, indent=2)
        parts.append(f"\nExample text: {ex['text']}\nExample JSON: {example_json}")
    parts.append(f"\nNow extract from this text:\nDisplay: {example_text}")
    return "\n".join(parts)


def _is_header(start: int, text: str) -> bool:
    """Narrow header heuristic: start before first period and within 120 chars."""
    first_period = text.find(".")
    if first_period == -1:
        first_period = len(text)
    # First period+1 is header end (including period)
    in_header_period = start < first_period + 1
    in_header_120 = start < 120
    # Also ensure before first newline if present
    first_nl = text.find("\n")
    if first_nl != -1:
        in_header_nl = start < first_nl
    else:
        in_header_nl = True
    return in_header_period and in_header_120 and in_header_nl


def structural_validate(text: str, entities: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Validate 14 structural rules, return (ok, errors). Reuses check_dataset_splits logic conceptually."""
    errors: list[str] = []
    # Reuse allowed types
    allowed = set(ALLOWED_TYPES)
    seen: set[tuple[str, str, int, int]] = set()
    span_by_range: dict[tuple[int,int], str] = {}
    for idx, ent in enumerate(entities):
        if not isinstance(ent, dict):
            errors.append(f"Entity {idx} not a dict")
            continue
        typ = ent.get("type")
        if typ not in allowed:
            errors.append(f"Invalid type {typ!r} at {idx}")
            continue
        txt = ent.get("text")
        start = ent.get("start")
        end = ent.get("end")
        if not isinstance(txt, str) or not txt:
            errors.append(f"Empty or invalid text at {idx}")
            continue
        # Narrow WORK_MODE guard: contract type is not work model
        # Rejects standalone and any WORK_MODE containing unbefristet/befristet as word (e.g. "Teilzeit 30h, unbefristet")
        if typ == "WORK_MODE" and isinstance(txt, str) and re.search(r"\b(unbefristet|befristet)\b", txt, flags=re.IGNORECASE):
            errors.append(f"WORK_MODE must not be contract type {txt!r} at {idx}")
            continue
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append(f"start/end must be int at {idx}")
            continue
        if start < 0 or end < 0 or start >= end:
            errors.append(f"Invalid range {start},{end} at {idx}")
            continue
        if not (0 <= start < len(text) and 0 <= end <= len(text)):
            errors.append(f"Span out of bounds {start},{end} len={len(text)} at {idx}")
            continue
        if text[start:end] != txt:
            errors.append(f"text[start:end]!=text at {idx}: expected {text[start:end]!r} got {txt!r}")
            continue
        # Entity text must occur in document
        if txt not in text:
            errors.append(f"Entity text not in document at {idx}: {txt!r}")
            continue
        # Check uniqueness: 0->hallucinated (already), 1->ok, >1->ambiguous, but for JOB_TITLE allow header disambiguation
        occ = [m.start() for m in re.finditer(re.escape(txt), text)]
        if len(occ) > 1:
            # Hybrid disambiguation: only for JOB_TITLE, first occurrence in header
            if typ == "JOB_TITLE" and len(occ) > 1 and occ[0] == start and _is_header(start, text):
                # Accept first occurrence as header - not ambiguous
                pass
            else:
                errors.append(f"Ambiguous text {txt!r} appears {len(occ)} times at {idx}")
                continue
        key = (typ, txt, start, end)
        if key in seen:
            errors.append(f"Duplicate span {key} at {idx}")
            continue
        seen.add(key)
        span_key = (start, end)
        if span_key in span_by_range and span_by_range[span_key] != typ:
            errors.append(f"Same span different type {span_key}: {span_by_range[span_key]} vs {typ}")
            continue
        span_by_range[span_key] = typ

    # Overlaps
    for i in range(len(entities)):
        for j in range(i+1, len(entities)):
            a = entities[i]; b = entities[j]
            if not isinstance(a.get("start"), int) or not isinstance(a.get("end"), int): continue
            if not isinstance(b.get("start"), int) or not isinstance(b.get("end"), int): continue
            if max(a["start"], b["start"]) < min(a["end"], b["end"]):
                errors.append(f"Overlap {a.get('text')!r} and {b.get('text')!r}")

    # Additional: check no empty spans already, no unknown types already
    return (len(errors) == 0), errors


def parse_llm_output(text: str, raw_content: str) -> tuple[list[dict[str, Any]], str | None, str]:
    """Parse LLM JSON output into normalized entities. Returns (entities, error, status)."""
    # Use existing extract and normalize
    parsed, parse_err = extract_json_payload(raw_content)
    if parse_err is not None:
        return [], parse_err, "parse_error"
    if not isinstance(parsed, dict):
        return [], "Top-level JSON not a dict", "parse_error"
    # Validate schema via kisski_client
    from ie_course.kisski_client import validate_schema
    ok, msg = validate_schema(parsed)
    if not ok:
        return [], msg or "Schema invalid", "parse_error"
    # Check all 7 keys present (validate_schema already ensures)
    # Now normalize to entities with start/end
    normalized = normalize_json_predictions(parsed, text)  # type: ignore
    # Distinguish hallucinated/ambiguous etc. via status field
    # If any have status != ok, we treat as parse-level issues but still return entities that are ok
    # For structural validation we will pass only ok entities, but we need to know if there were hallucinated etc.
    # For now, return normalized list; caller will check statuses
    # If no ok entities but there were hallucinated/ambiguous, we still consider parse ok but validation will handle
    return normalized, None, "parsed"


def call_llm_with_retry(
    payload: dict[str, Any],
    base_url: str,
    api_key: str,
    max_retries: int = 3,
    backoff: float = 1.0,
    seed: int | None = None,
    mock_scenario: str | None = None,
) -> tuple[int, dict | None, str | None, list[dict[str, Any]]]:
    """Call LLM with exponential backoff and jitter. Returns (status, body, raw, attempts_log)."""
    attempts: list[dict[str, Any]] = []
    rng = random.Random(seed)
    for attempt in range(1, max_retries + 1):
        # Mock handling for tests
        if mock_scenario is not None:
            # Simulate mock scenarios without real API
            # For dry-run, caller should not call this at all
            # Here we provide mock responses based on scenario
            mock_res = get_mock_response(mock_scenario, attempt, payload)
            status, body, raw = mock_res
            attempts.append({"attempt": attempt, "status": status, "error": None if status < 400 else f"mock_{status}", "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()})
            if status < 400:
                return status, body, raw, attempts
            # else retry if retryable and not last attempt
            if status in RETRYABLE_CODES and attempt < max_retries:
                sleep = backoff * (2 ** (attempt - 1)) + rng.uniform(0, 0.5)
                time.sleep(sleep)
                continue
            else:
                return status, body, raw, attempts

        # Real call
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            status, body, raw = request_json(f"{base_url}/chat/completions", api_key, payload)
        except Exception as exc:  # pragma: no cover
            status, body, raw = 599, None, str(exc)

        attempts.append({"attempt": attempt, "status": status, "error": None if status < 400 else raw, "timestamp": ts})

        if status < 400:
            return status, body, raw, attempts

        # Check if retryable
        if status in RETRYABLE_CODES and attempt < max_retries:
            sleep = backoff * (2 ** (attempt - 1)) + rng.uniform(0, 0.5)
            time.sleep(sleep)
            continue
        else:
            # Not retryable or last attempt
            return status, body, raw, attempts

    # Should not reach here
    return status, body, raw, attempts


def get_mock_response(scenario: str, attempt: int, payload: dict[str, Any]) -> tuple[int, dict | None, str | None]:
    """Provide mock responses for tests. Scenarios: valid, invalid_json, hallucinated, ambiguous, unknown_type, overlap, duplicate, http500, timeout, success_after_retry."""
    # For generic valid scenario, return a minimal valid JSON
    base_content = {
        "JOB_TITLE": ["Data Scientist"],
        "HARD_SKILL": ["Python"],
        "SOFT_SKILL": [],
        "EXPERIENCE": [],
        "EDUCATION": [],
        "LANGUAGE": [],
        "WORK_MODE": ["Vollzeit"]
    }
    if scenario == "valid":
        body = {"choices": [{"message": {"content": json.dumps(base_content)}}]}
        return 200, body, None
    elif scenario == "invalid_json":
        body = {"choices": [{"message": {"content": "{ not json"}}]}
        return 200, body, None
    elif scenario == "hallucinated":
        hall = {**base_content, "HARD_SKILL": ["UnicornSkill"]}
        body = {"choices": [{"message": {"content": json.dumps(hall)}}]}
        return 200, body, None
    elif scenario == "ambiguous":
        # Text that appears multiple times – caller will test with text containing duplicate
        body = {"choices": [{"message": {"content": json.dumps(base_content)}}]}
        return 200, body, None
    elif scenario == "unknown_type":
        unk = {**base_content, "UNKNOWN_TYPE": ["foo"]}
        body = {"choices": [{"message": {"content": json.dumps(unk)}}]}
        return 200, body, None
    elif scenario == "overlap":
        body = {"choices": [{"message": {"content": json.dumps(base_content)}}]}
        return 200, body, None
    elif scenario == "duplicate":
        body = {"choices": [{"message": {"content": json.dumps(base_content)}}]}
        return 200, body, None
    elif scenario == "http500":
        return 500, None, "mock 500"
    elif scenario == "timeout":
        return 599, None, "mock timeout"
    elif scenario == "success_after_retry":
        if attempt == 1:
            return 500, None, "mock 500 first"
        else:
            body = {"choices": [{"message": {"content": json.dumps(base_content)}}]}
            return 200, body, None
    elif scenario == "long_job_title_ambiguous":
        # Text has title twice, candidate appears twice -> ambiguous
        amb = {
            "JOB_TITLE": ["Gesundheits- und Krankenpfleger (m/w/d) Intensivstation"],
            "HARD_SKILL": [],
            "SOFT_SKILL": [],
            "EXPERIENCE": [],
            "EDUCATION": [],
            "LANGUAGE": [],
            "WORK_MODE": []
        }
        body = {"choices": [{"message": {"content": json.dumps(amb)}}]}
        return 200, body, None
    elif scenario == "long_job_title_unique":
        uniq = {
            "JOB_TITLE": ["Gesundheits- und Krankenpfleger (m/w/d) Intensivstation."],
            "HARD_SKILL": [],
            "SOFT_SKILL": [],
            "EXPERIENCE": [],
            "EDUCATION": [],
            "LANGUAGE": [],
            "WORK_MODE": []
        }
        body = {"choices": [{"message": {"content": json.dumps(uniq)}}]}
        return 200, body, None
    elif scenario == "job_title_mwd":
        body = {"choices": [{"message": {"content": json.dumps({"JOB_TITLE": ["Softwareentwickler (m/w/d)"], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": []})}}]}
        return 200, body, None
    elif scenario == "work_mode_unbefristet":
        body = {"choices": [{"message": {"content": json.dumps({"JOB_TITLE": [], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": ["unbefristet"]})}}]}
        return 200, body, None
    elif scenario == "work_mode_correct":
        body = {"choices": [{"message": {"content": json.dumps({"JOB_TITLE": [], "HARD_SKILL": [], "SOFT_SKILL": [], "EXPERIENCE": [], "EDUCATION": [], "LANGUAGE": [], "WORK_MODE": ["Teilzeit 30 Stunden pro Woche"]})}}]}
        return 200, body, None
    else:
        body = {"choices": [{"message": {"content": json.dumps(base_content)}}]}
        return 200, body, None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Weak labeling pipeline for unlabeled job ads")
    parser.add_argument("--input-dir", type=Path, default=UNLABELED_DIR, help="Input dir (must be data/unlabeled)")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output run dir (default: data/weak_labels/run_<id>)")
    parser.add_argument("--ids", nargs="*", default=None, help="Specific IDs to process (e.g., job_ad_1031)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of docs")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="Top-k retrieval")
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE, help="Temperature")
    parser.add_argument("--model", type=str, default=None, help="Model id (default from .env)")
    parser.add_argument("--example-pool-dir", type=Path, default=EXAMPLE_POOL_DIR, help="Example pool dir")
    parser.add_argument("--dry-run", action="store_true", help="Dry run, no API calls")
    parser.add_argument("--resume", action="store_true", help="Resume existing run, skip verified")
    parser.add_argument("--retry-failed", action="store_true", help="Retry previously failed docs")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retries for API")
    parser.add_argument("--backoff", type=float, default=1.0, help="Base backoff seconds")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for jitter")
    parser.add_argument("--mock", type=str, default=None, help="Mock scenario for tests (valid, invalid_json, ...)")
    parser.add_argument("--gold-dir", type=Path, default=GOLD_DIR, help="Gold dir for leakage check (default data/gold)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Resolve input_dir early for guard
    input_dir = args.input_dir
    try:
        check_input_guards(input_dir)
    except ValueError as e:
        print(f"ERROR Input Guard: {e}", file=sys.stderr)
        return 1

    # Load unlabeled examples
    try:
        examples = load_unlabeled_examples(input_dir, ids_filter=args.ids, limit=args.limit)
    except ValueError as e:
        print(f"ERROR loading unlabeled: {e}", file=sys.stderr)
        return 1

    if not examples:
        print(f"No unlabeled examples found in {input_dir}", file=sys.stderr)
        return 1

    # Load pool and gold for leakage and retrieval
    pool_examples = load_example_pool(args.example_pool_dir)
    if not pool_examples:
        print(f"No example_pool examples in {args.example_pool_dir}", file=sys.stderr)
        return 1

    # Check that pool is annotated (already ensured by load_example_pool)
    # Leakage checks
    # Load gold ids
    gold_ids: set[str] = set()
    gold_texts_dir = args.gold_dir / "texts"
    if gold_texts_dir.exists():
        for p in gold_texts_dir.glob("job_ad_*.txt"):
            gold_ids.add(p.stem)
    else:
        for p in Path(args.gold_dir).glob("job_ad_*.txt"):
            gold_ids.add(p.stem)

    weak_ids = {ex["id"] for ex in examples}
    pool_ids = {ex["id"] for ex in pool_examples}
    try:
        check_leakage(weak_ids, pool_ids, gold_ids)
    except ValueError as e:
        print(f"ERROR Leakage: {e}", file=sys.stderr)
        return 1

    # Also ensure weak_input_ids ∩ pool_ids == ∅ already done, but also ensure no file is outside unlabeled
    for ex in examples:
        try:
            Path(ex["path"]).resolve().relative_to(UNLABELED_DIR.resolve())
        except ValueError:
            print(f"ERROR: Weak input file not under {UNLABELED_DIR}: {ex['path']}", file=sys.stderr)
            return 1
        # Also ensure not writing to gold/example_pool/unlabeled
        # Will be enforced at output stage

    # Retrieval
    from ie_course.retrieval import build_tfidf_index, retrieve_for_queries
    pool_texts = [ex["text"] for ex in pool_examples]
    pool_ids_list = [ex["id"] for ex in pool_examples]
    vectorizer, matrix = build_tfidf_index(pool_texts)
    query_texts = [ex["text"] for ex in examples]
    query_ids = [ex["id"] for ex in examples]
    retrieval = retrieve_for_queries(query_texts, query_ids, pool_texts, pool_ids_list, vectorizer, matrix, k=args.k, embedding_model="tfidf-sklearn")

    retrieval_map: dict[str, list[dict[str, Any]]] = {}
    pool_by_id = {ex["id"]: ex for ex in pool_examples}
    for entry in retrieval:
        qid = entry["query_id"]
        few = [pool_by_id[r["id"]] for r in entry["results"]]
        retrieval_map[qid] = few

    # Also ensure retrieval never returns gold
    for entry in retrieval:
        for r in entry["results"]:
            if r["id"] in gold_ids:
                print(f"ERROR: Retrieval returned gold id {r['id']} for query {entry['query_id']}", file=sys.stderr)
                return 1

    # Prepare output dir with run_id
    if args.output_dir is not None:
        out_dir = args.output_dir
        # If resuming, out_dir must exist and contain run_metadata
        if args.resume and not out_dir.exists():
            print(f"ERROR: --resume but output_dir does not exist: {out_dir}", file=sys.stderr)
            return 1
        # Guard: output must be under data/weak_labels
        try:
            out_dir.resolve().relative_to(WEAK_BASE.resolve())
        except ValueError:
            print(f"ERROR: Output must be under {WEAK_BASE}: {out_dir}", file=sys.stderr)
            return 1
        # Prevent writing to gold/example_pool/unlabeled
        for forbidden in [GOLD_DIR.resolve(), EXAMPLE_POOL_DIR.resolve(), UNLABELED_DIR.resolve()]:
            if out_dir.resolve() == forbidden or str(out_dir.resolve()).startswith(str(forbidden)):
                # Allow unlabeled/texts? No, weak output must not be there
                if out_dir.resolve() != WEAK_BASE.resolve() and str(out_dir.resolve()).startswith(str(WEAK_BASE.resolve())):
                    pass
                else:
                    print(f"ERROR: Output must not be under forbidden {forbidden}: {out_dir}", file=sys.stderr)
                    return 1
    else:
        # Generate new run_id
        if args.resume:
            print("ERROR: --resume requires --output-dir to be specified", file=sys.stderr)
            return 1
        run_id = generate_run_id(args.k, args.temperature)
        out_dir = WEAK_BASE / run_id

    # Dry-run: do not create output yet, just report
    if args.dry_run:
        print("DRY-RUN: No API calls, no outputs written.")
        print(f"Input: {input_dir} ({len(examples)} docs)")
        print(f"Pool: {args.example_pool_dir} ({len(pool_examples)} examples)")
        print(f"Gold: {args.gold_dir} ({len(gold_ids)} gold ids, leakage check passed)")
        print(f"k={args.k}, temperature={args.temperature}, model={args.model or 'from .env'}")
        print(f"Would create: {out_dir}")
        print(f"Retrieval would be computed for {len(retrieval)} queries")
        # Show one prompt example
        if examples:
            ex = examples[0]
            few = retrieval_map.get(ex["id"], [])
            prompt = build_fewshot_prompt_for_weak(ex["text"], few)
            print(f"Example prompt for {ex['id'][:30]}... len {len(prompt)}")
            print(f"Prompt would include {len(few)} few-shot examples: {[f['id'] for f in few]}")
        return 0

    # Real run: create dirs
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw_outputs"
    parsed_dir = out_dir / "parsed"
    verified_dir = out_dir / "verified"
    rejected_dir = out_dir / "rejected"
    for d in [raw_dir, parsed_dir, verified_dir, rejected_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Load existing state for resume
    status_path = out_dir / "status.jsonl"
    errors_path = out_dir / "errors.jsonl"
    existing_status: dict[str, dict[str, Any]] = {}
    if args.resume and status_path.exists():
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                j = json.loads(line)
                existing_status[j["id"]] = j
            except Exception:
                continue

    # Collect config
    from ie_course.kisski_client import collect_config
    config, missing = collect_config()
    model_id = args.model or config.get("model") or DEFAULT_MODEL
    base_url = (config.get("base_url") or "").rstrip("/") if not args.model else (args.model and config.get("base_url") or "")
    # Actually base_url from config
    base_url = str(config.get("base_url") or "").rstrip("/")
    api_key = str(config.get("api_key") or "")
    if args.model:
        model_id = args.model
    # For dry-run we already returned, for real we need API key unless mock
    if args.mock is None:
        if missing:
            print(f"Missing config: {', '.join(missing)}", file=sys.stderr)
            return 1
        if not api_key or not base_url:
            print("Missing API key or base URL", file=sys.stderr)
            return 1

    # Prepare run_metadata
    git_sha = get_git_sha()
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    run_id_str = out_dir.name
    # If output_dir was explicitly given, run_id is its name, else generated
    if args.output_dir is not None:
        run_id_str = out_dir.name

    # Write initial run_metadata (will be overwritten at end with final counts)
    run_metadata: dict[str, Any] = {
        "run_id": run_id_str,
        "timestamp": timestamp,
        "model": model_id,
        "temperature": args.temperature,
        "k": args.k,
        "embedding": {"type": "tfidf", "ngram_range": [1, 2], "max_features": 5000},
        "input_split": "unlabeled",
        "input_dir": str(input_dir),
        "input_ids": [ex["id"] for ex in examples],
        "pool_ids": sorted(pool_ids),
        "gold_ids": sorted(gold_ids),
        "prompt_version": "fewshot_json_v3",
        "git_sha": git_sha,
        "verification_level": "structural",
        "seed": args.seed,
        "max_retries": args.max_retries,
        "backoff": args.backoff,
    }
    save_artifact(out_dir / "run_metadata.json", json.dumps(run_metadata, ensure_ascii=False, indent=2))
    # Retrieval json
    save_artifact(out_dir / "retrieval.json", json.dumps(retrieval, ensure_ascii=False, indent=2))

    # Also create/update latest pointer
    latest_path = WEAK_BASE / "latest"
    # Try symlink, fallback to file
    try:
        if latest_path.is_symlink() or latest_path.exists():
            # Remove existing
            if latest_path.is_symlink():
                latest_path.unlink()
            elif latest_path.is_file():
                latest_path.unlink()
            elif latest_path.is_dir():
                # shouldn't happen
                pass
        latest_path.symlink_to(out_dir.name)
    except (OSError, NotImplementedError):
        # Fallback: write file containing run_id
        try:
            if latest_path.exists():
                latest_path.unlink()
        except Exception:
            pass
        latest_path.write_text(run_id_str, encoding="utf-8")

    # Process each example
    # Status tracking
    # If resume, skip verified
    to_process: list[dict[str, Any]] = []
    for ex in examples:
        sid = ex["id"]
        st = existing_status.get(sid, {}).get("status")
        if args.resume and st == "verified":
            continue
        if args.resume and not args.retry_failed and st in ("api_error", "parse_error", "validation_failed"):
            # If retry_failed not set, don't retry failed ones
            # Actually spec says --retry-failed controls retry of failed
            continue
        # Also if status is pending or missing, process
        to_process.append(ex)

    # If limit, already limited via load_unlabeled

    # Prepare status file appending
    # We will rewrite status.jsonl incrementally
    # First, if not resume, truncate
    if not args.resume or not status_path.exists():
        status_path.write_text("", encoding="utf-8")
        errors_path.write_text("", encoding="utf-8")
    else:
        # Keep existing, will append new statuses for processed docs (overwrite)
        # For simplicity, we will rewrite file: keep verified entries, remove those being reprocessed
        kept_lines = []
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            j = json.loads(line)
            if j["id"] not in {ex["id"] for ex in to_process}:
                kept_lines.append(line)
        status_path.write_text("\n".join(kept_lines) + ("\n" if kept_lines else ""), encoding="utf-8")

    total = len(examples)
    processed = 0
    for ex in to_process:
        sid = ex["id"]
        text = ex["text"]
        few = retrieval_map.get(sid, [])
        prompt = build_fewshot_prompt_for_weak(text, few)

        # Write status api_running
        status_entry = {"id": sid, "status": "api_running", "attempts": 0, "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "verification_level": "structural"}
        # Append to status (we will update later)
        # For api call
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "Return only JSON and nothing else."},
                {"role": "user", "content": prompt},
            ],
            "temperature": args.temperature,
            "max_tokens": 600,
            "response_format": {"type": "json_object"},
        }

        # Call with retry
        status_code, body, raw_text, attempts_log = call_llm_with_retry(
            payload, base_url, api_key,
            max_retries=args.max_retries,
            backoff=args.backoff,
            seed=args.seed,
            mock_scenario=args.mock,
        )

        # Log attempts to errors.jsonl if any failure
        for att in attempts_log:
            if att["status"] >= 400:
                err = {
                    "id": sid,
                    "stage": "api",
                    "error_type": f"http_{att['status']}",
                    "message": str(att["error"])[:500],
                    "attempt": att["attempt"],
                    "timestamp": att["timestamp"],
                }
                with open(errors_path, "a", encoding="utf-8") as ef:
                    ef.write(json.dumps(err, ensure_ascii=False) + "\n")

        if status_code >= 400 or body is None:
            # api_error
            status_entry = {"id": sid, "status": "api_error", "attempts": len(attempts_log), "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "verification_level": "structural"}
            with open(status_path, "a", encoding="utf-8") as sf:
                sf.write(json.dumps(status_entry, ensure_ascii=False) + "\n")
            # Also save raw empty?
            (raw_dir / f"{sid}.json.txt").write_text(raw_text or "", encoding="utf-8")
            continue

        # Save raw output
        content = body.get("choices", [{}])[0].get("message", {}).get("content") if body else raw_text
        if content is None:
            content = ""
        (raw_dir / f"{sid}.json.txt").write_text(content, encoding="utf-8")

        # Parse
        normalized, parse_err, parse_status = parse_llm_output(text, content)
        if parse_err is not None:
            # parse_error
            status_entry = {"id": sid, "status": "parse_error", "attempts": len(attempts_log), "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "verification_level": "structural"}
            with open(status_path, "a", encoding="utf-8") as sf:
                sf.write(json.dumps(status_entry, ensure_ascii=False) + "\n")
            err = {"id": sid, "stage": "parse", "error_type": "parse_error", "message": parse_err[:500], "attempt": len(attempts_log), "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
            with open(errors_path, "a", encoding="utf-8") as ef:
                ef.write(json.dumps(err, ensure_ascii=False) + "\n")
            # Save parsed as empty but also rejected?
            parsed_path = parsed_dir / f"{sid}.json"
            parsed_path.write_text(json.dumps({"id": sid, "entities": []}, ensure_ascii=False, indent=2), encoding="utf-8")
            rejected_path = rejected_dir / f"{sid}.json"
            rejected_path.write_text(json.dumps({"id": sid, "entities": [], "error": parse_err}, ensure_ascii=False, indent=2), encoding="utf-8")
            continue

        # Hybrid disambiguation for JOB_TITLE: if ambiguous but first occurrence is header, treat as ok with first start
        # This implements the narrow E) rule for JOB_TITLE only, keeping general >1 → ambiguous for other types
        disambiguated: list[dict[str, Any]] = []
        for e in normalized:
            if e.get("status") == "ambiguous" and e.get("type") == "JOB_TITLE":
                txt = e.get("text") or ""
                if txt:
                    occ = [m.start() for m in re.finditer(re.escape(txt), text)]
                    if len(occ) > 1 and occ[0] == min(occ):
                        # Check header
                        if _is_header(occ[0], text):
                            # Convert to ok with first occurrence
                            disambiguated.append({"type": e["type"], "text": txt, "start": occ[0], "end": occ[0] + len(txt), "status": "ok"})
                            # Log as disambiguated, not as error
                            err = {"id": sid, "stage": "parse", "error_type": "disambiguated_header", "message": f"{e.get('type')}:{txt} -> first header {occ[0]}", "attempt": len(attempts_log), "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
                            with open(errors_path, "a", encoding="utf-8") as ef:
                                ef.write(json.dumps(err, ensure_ascii=False) + "\n")
                            continue
            # Otherwise keep original handling
            disambiguated.append(e)
        normalized = disambiguated

        # Save parsed
        parsed_entities = [{"type": e["type"], "text": e["text"], "start": e["start"], "end": e["end"]} for e in normalized if e.get("status") == "ok"]
        # Also keep track of hallucinated etc. for errors (excluding those we just disambiguated)
        for e in normalized:
            if e.get("status") in ("hallucinated", "ambiguous"):
                err = {"id": sid, "stage": "parse", "error_type": e["status"], "message": f"{e.get('type')}:{e.get('text')}", "attempt": len(attempts_log), "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
                with open(errors_path, "a", encoding="utf-8") as ef:
                    ef.write(json.dumps(err, ensure_ascii=False) + "\n")
            elif e.get("status") == "rejected_marker":
                err = {"id": sid, "stage": "parse", "error_type": "rejected_marker", "message": f"{e.get('type')}:{e.get('text')}", "attempt": len(attempts_log), "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
                with open(errors_path, "a", encoding="utf-8") as ef:
                    ef.write(json.dumps(err, ensure_ascii=False) + "\n")

        parsed_payload = {"id": sid, "entities": parsed_entities}
        save_artifact(parsed_dir / f"{sid}.json", json.dumps(parsed_payload, ensure_ascii=False, indent=2))

        # Structural validation
        ok, val_errors = structural_validate(text, parsed_entities)
        if not ok:
            status_entry = {"id": sid, "status": "validation_failed", "attempts": len(attempts_log), "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "verification_level": "structural"}
            with open(status_path, "a", encoding="utf-8") as sf:
                sf.write(json.dumps(status_entry, ensure_ascii=False) + "\n")
            for ve in val_errors:
                err = {"id": sid, "stage": "validation", "error_type": "validation_failed", "message": ve[:500], "attempt": len(attempts_log), "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
                with open(errors_path, "a", encoding="utf-8") as ef:
                    ef.write(json.dumps(err, ensure_ascii=False) + "\n")
            rejected_path = rejected_dir / f"{sid}.json"
            save_artifact(rejected_path, json.dumps({"id": sid, "entities": parsed_entities, "errors": val_errors}, ensure_ascii=False, indent=2))
            continue

        # Verified
        status_entry = {"id": sid, "status": "verified", "attempts": len(attempts_log), "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "verification_level": "structural"}
        with open(status_path, "a", encoding="utf-8") as sf:
            sf.write(json.dumps(status_entry, ensure_ascii=False) + "\n")
        verified_path = verified_dir / f"{sid}.json"
        save_artifact(verified_path, json.dumps(parsed_payload, ensure_ascii=False, indent=2))

        processed += 1

    # Update run_metadata with final counts
    # Count statuses
    final_statuses: list[dict[str, Any]] = []
    if status_path.exists():
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                final_statuses.append(json.loads(line))
    counts = {s: 0 for s in ALLOWED_STATUSES}
    for st in final_statuses:
        counts[st.get("status", "unknown")] = counts.get(st.get("status"), 0) + 1
    run_metadata["counts"] = counts
    run_metadata["processed"] = processed
    run_metadata["total_input"] = total
    run_metadata["timestamp_end"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_artifact(out_dir / "run_metadata.json", json.dumps(run_metadata, ensure_ascii=False, indent=2))

    print(f"Weak labeling run {run_id_str} complete: {processed}/{total} processed, {counts.get('verified',0)} verified, {counts.get('validation_failed',0)} validation_failed, {counts.get('api_error',0)} api_error")
    return 0


if __name__ == "__main__":
    sys.exit(main())
