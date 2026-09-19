from __future__ import annotations

import re
from typing import Any, Final

ALLOWED_TYPES: Final[tuple[str, ...]] = (
    "JOB_TITLE",
    "HARD_SKILL",
    "SOFT_SKILL",
    "EXPERIENCE",
    "EDUCATION",
    "LANGUAGE",
    "WORK_MODE",
)


def build_structuring_prompt(text: str, candidates: list[dict[str, Any]]) -> str:

    if candidates:
        lines = "\n".join(f'- {c["type"]}: "{c["text"]}"' for c in candidates)
        candidate_block = (
            "A local NER model already proposed these candidate spans. They may be "
            "incomplete, too short/long, wrongly typed, or entirely wrong:\n" + lines
        )
    else:
        candidate_block = "The local NER model found no candidate spans."

    return (
        "You are a strict extractor for German job advertisements. "
        "Copy exact spans from the input text. "
        "Never paraphrase, shorten, expand or normalize spans. "
        "Return only valid JSON. "
        "Use exactly these entity types only: JOB_TITLE, HARD_SKILL, SOFT_SKILL, "
        "EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE. "
        "Return a JSON object with exactly these keys: JOB_TITLE, HARD_SKILL, "
        "SOFT_SKILL, EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE. "
        "Each value must be a list of strings taken verbatim from the text, "
        "character-for-character. "
        "If a span is 'Erfahrung im B2B-Verkauf', do not return 'Erfahrung' alone. "
        "If no span for a type, return empty list. "
        "Only the 7 allowed types, no LOCATION/COMPANY.\n\n"
        f"{candidate_block}\n\n"
        "Use the candidates as a starting point: keep the ones that are correct, fix "
        "spans that are cut off, drop wrong or hallucinated ones, and add any entities "
        "the candidates missed. Your answer must be grounded only in the text below.\n\n"
        f"Text: {text}"
    )


def normalize_json_predictions(payload: Any, example_text: str) -> list[dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return predictions
    for entity_type in ALLOWED_TYPES:
        values = payload.get(entity_type, [])
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str) or not value.strip():
                continue
            positions = [match.start() for match in re.finditer(re.escape(value), example_text)]
            if not positions:
                predictions.append(
                    {
                        "type": entity_type,
                        "text": value,
                        "start": None,
                        "end": None,
                        "status": "hallucinated",
                    }
                )
            elif len(positions) > 1:
                predictions.append(
                    {
                        "type": entity_type,
                        "text": value,
                        "start": None,
                        "end": None,
                        "status": "ambiguous",
                    }
                )
            else:
                start = positions[0]
                predictions.append(
                    {
                        "type": entity_type,
                        "text": value,
                        "start": start,
                        "end": start + len(value),
                        "status": "ok",
                    }
                )
    return predictions
