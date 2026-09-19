from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace (including newlines) to a single space."""
    return re.sub(r"\s+", " ", text).strip()


def sentence_tokenize(text: str) -> list[str]:
    """Split text into sentences using NLTK's Punkt tokenizer."""
    import nltk
    return nltk.sent_tokenize(text)


def load_text(path: str | Path) -> str:
    """Read a plain-text file, normalizing line endings."""
    return Path(path).read_text(encoding="utf-8").replace("\r\n", "\n")


def ents_to_dict(doc: Any) -> dict[str, list[str]]:
    """Convert a spaCy Doc's entities to a label→[surface forms] dict."""
    result: dict[str, list[str]] = {}
    for ent in doc.ents:
        result.setdefault(ent.label_, []).append(ent.text)
    return result


def span_f1(
    gold: list[tuple[int, int, str]],
    pred: list[tuple[int, int, str]],
) -> dict[str, float]:
    """Token-level span F1 for NER, given (start, end, label) tuples."""
    gold_set = set(gold)
    pred_set = set(pred)
    tp = len(gold_set & pred_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    recall = tp / len(gold_set) if gold_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def print_ents(doc: Any) -> None:
    """Pretty-print entities from a spaCy Doc using Rich."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Named Entities", show_lines=True)
    table.add_column("Text", style="cyan")
    table.add_column("Label", style="magenta")
    table.add_column("Start", justify="right")
    table.add_column("End", justify="right")
    for ent in doc.ents:
        table.add_row(ent.text, ent.label_, str(ent.start_char), str(ent.end_char))
    console.print(table)
