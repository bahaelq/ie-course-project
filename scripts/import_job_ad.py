#!/usr/bin/env python3
"""Controlled import of a local job-ad text file into a dataset split."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"

ALLOWED_SPLITS: Final[set[str]] = {"example_pool", "gold", "unlabeled"}


def normalize_text(text: str) -> str:
    """Normalize line endings and ensure exactly one trailing newline.
    
    - \r\n → \n
    - \r → \n
    - Internal newlines → space (text becomes a single flow line)
    - Strip trailing whitespace, add exactly one \n
    """
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = re.sub(r"\n+", " ", text)
    text = text.strip()
    return text + "\n"


def text_content_key(text: str) -> str:
    """Canonical form for duplicate detection (ignores trailing newline)."""
    return text.rstrip("\n")


def find_duplicate_id(new_id: str, exclude_split: str | None = None) -> str | None:
    for split in ALLOWED_SPLITS:
        if split == exclude_split:
            continue
        target = DATA_DIR / split / "texts" / f"{new_id}.txt"
        if target.exists():
            return split
    return None


def find_duplicate_text(text: str, exclude_split: str | None = None,
                       exclude_id: str | None = None) -> tuple[str, str] | None:
    new_key = text_content_key(text)
    for split in ALLOWED_SPLITS:
        texts_dir = DATA_DIR / split / "texts"
        if not texts_dir.exists():
            continue
        for p in texts_dir.glob("*.txt"):
            if split == exclude_split and p.stem == exclude_id:
                continue
            existing = p.read_text(encoding="utf-8")
            if text_content_key(existing) == new_key:
                return split, p.stem
    return None


def get_next_id() -> str:
    existing: list[int] = []
    for split in ALLOWED_SPLITS:
        texts_dir = DATA_DIR / split / "texts"
        if not texts_dir.exists():
            continue
        for p in texts_dir.glob("job_ad_*.txt"):
            m = re.match(r"job_ad_(\d+)", p.stem)
            if m:
                existing.append(int(m.group(1)))
    if not existing:
        return "job_ad_1001"
    return f"job_ad_{max(existing) + 1}"


def do_import(args: argparse.Namespace) -> int:
    if args.split not in ALLOWED_SPLITS:
        print(f"Fehler: Ungültiger Split '{args.split}'. Erlaubt: {', '.join(sorted(ALLOWED_SPLITS))}")
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Fehler: Eingabedatei nicht gefunden: {input_path}")
        return 1

    # Read + UTF-8 check
    try:
        raw = input_path.read_bytes()
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        print(f"Fehler: Kein gültiges UTF-8: {exc}")
        return 1

    if not text.strip():
        print("Fehler: Datei ist leer")
        return 1

    # Auto-ID if not provided
    ad_id: str = args.id if args.id else get_next_id()

    # Validate ID format
    if not re.match(r"^job_ad_\d+$", ad_id):
        print(f"Fehler: ID '{ad_id}' entspricht nicht dem Muster job_ad_XXXX")
        return 1

    # Duplicate ID check (across all splits)
    dup_split = find_duplicate_id(ad_id)
    if dup_split:
        print(f"Fehler: ID '{ad_id}' existiert bereits in Split '{dup_split}'")
        return 1

    # Duplicate text check
    dup = find_duplicate_text(text, exclude_split=args.split, exclude_id=ad_id)
    if dup:
        print(f"Fehler: Identischer Text bereits vorhanden in Split '{dup[0]}' als '{dup[1]}'")
        return 1

    # Normalize
    normalized = normalize_text(text)

    # Ensure target directory
    texts_dir = DATA_DIR / args.split / "texts"
    texts_dir.mkdir(parents=True, exist_ok=True)
    target_path = texts_dir / f"{ad_id}.txt"

    if target_path.exists():
        print(f"Fehler: Zieldatei existiert bereits: {target_path}")
        return 1

    # Build metadata
    metadata = {
        "id": ad_id,
        "split": args.split,
        "source_name": args.source_name,
        "source_url": args.source_url,
        "retrieved_at": args.retrieved_at or "",
        "job_title_original": args.job_title or "",
        "company_anonymized": args.company or "",
        "notes": args.notes or "",
    }

    # Write text file
    target_path.write_text(normalized, encoding="utf-8")

    # Append metadata (atomic: roll back text file on failure)
    try:
        meta_path = DATA_DIR / args.split / "metadata.jsonl"
        with open(meta_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
    except Exception as exc:
        target_path.unlink()
        print(f"Fehler: Metadaten konnten nicht geschrieben werden: {exc}")
        print("Textdatei wurde zurückgesetzt.")
        return 1

    print(f"Import erfolgreich: {ad_id} -> data/{args.split}/")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import a local TXT job ad into a dataset split"
    )
    parser.add_argument("--input", required=True, help="Pfad zur TXT-Quelldatei")
    parser.add_argument("--split", required=True,
                        choices=sorted(ALLOWED_SPLITS),
                        help="Ziel-Split")
    parser.add_argument("--id", default="",
                        help="Eindeutige ID (auto: job_ad_1001++)")
    parser.add_argument("--source-name", default="",
                        help="Name der Quelle (z.B. StepStone)")
    parser.add_argument("--source-url", default="",
                        help="URL der Anzeige")
    parser.add_argument("--retrieved-at", default="",
                        help="Abrufdatum YYYY-MM-DD")
    parser.add_argument("--job-title", default="",
                        help="Originale Stellenbezeichnung")
    parser.add_argument("--company", default="",
                        help="Unternehmen (anonymisiert)")
    parser.add_argument("--notes", default="",
                        help="Optionale Notizen")
    args = parser.parse_args()
    return do_import(args)


if __name__ == "__main__":
    sys.exit(main())
