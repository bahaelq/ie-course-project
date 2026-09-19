"""Local inference: fine-tuned GBERT token-classification model -> entities.

No LLM API involved; runs fully offline once the model directory is on disk.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import torch


def load_model(model_dir: str | Path):
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForTokenClassification.from_pretrained(model_dir)
    model.eval()
    return model, tokenizer


def predict_entities(text: str, model, tokenizer, max_length: int = 512) -> list[dict[str, Any]]:
    encoding = tokenizer(
        text,
        return_offsets_mapping=True,
        truncation=True,
        max_length=max_length,
        return_tensors="pt",
    )
    offsets = encoding.pop("offset_mapping")[0].tolist()
    with torch.no_grad():
        logits = model(**encoding).logits[0]
    label_ids = logits.argmax(dim=-1).tolist()
    id2label = {int(k): v for k, v in model.config.id2label.items()}

    entities: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for label_id, (start, end) in zip(label_ids, offsets):
        if start == end: 
            continue
        label = id2label.get(label_id, "O")
        if label == "O":
            if current is not None:
                entities.append(current)
                current = None
            continue
        prefix, _, entity_type = label.partition("-")
        if prefix == "B" or current is None or current["type"] != entity_type:
            if current is not None:
                entities.append(current)
            current = {"type": entity_type, "start": start, "end": end}
        else:
            current["end"] = end
    if current is not None:
        entities.append(current)

    for ent in entities:
        ent["text"] = text[ent["start"] : ent["end"]]
    return entities
