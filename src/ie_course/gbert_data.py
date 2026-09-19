"""Loading annotated job ad splits for GBERT evaluation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_annotated_split(split_dir: Path) -> list[dict[str, Any]]:
    texts_dir = split_dir / "texts"
    if not texts_dir.exists():
        texts_dir = split_dir
    ann_dir = split_dir / "annotations"

    examples: list[dict[str, Any]] = []
    for text_path in sorted(texts_dir.glob("job_ad_*.txt")):
        ann_path = ann_dir / f"{text_path.stem}.json"
        if not ann_path.exists():
            continue
        payload = json.loads(ann_path.read_text(encoding="utf-8"))
        examples.append(
            {
                "id": text_path.stem,
                "text": text_path.read_text(encoding="utf-8"),
                "entities": payload.get("entities", []),
            }
        )
    return examples
