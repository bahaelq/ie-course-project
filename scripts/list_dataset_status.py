#!/usr/bin/env python3
"""Show current dataset status per split."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"

SPLITS: Final[list[str]] = ["example_pool", "gold", "unlabeled", "smoke_test"]

TARGET_SIZES: Final[dict[str, str]] = {
    "example_pool": "15–20",
    "gold": "20–30",
    "unlabeled": "≥ 50",
    "smoke_test": "5 (fix, künstlich)",
}

TARGET_MIN: Final[dict[str, int]] = {
    "example_pool": 15,
    "gold": 20,
    "unlabeled": 50,
    "smoke_test": 5,
}

TARGET_MAX: Final[dict[str, int]] = {
    "example_pool": 20,
    "gold": 30,
    "unlabeled": 999_999,
    "smoke_test": 5,
}


def count_files(directory: Path, pattern: str) -> int:
    if not directory.exists():
        return 0
    return len(list(directory.glob(pattern)))


def main() -> int:
    print("=" * 60)
    print("DATASET STATUS")
    print("=" * 60)

    total_texts = 0
    total_ann = 0
    total_missing = 0

    for split in SPLITS:
        base = DATA_DIR / split

        if split == "smoke_test":
            texts = count_files(base, "*.txt")
            ann = count_files(base / "annotations", "*.json")
        else:
            texts = count_files(base / "texts", "*.txt")
            ann = count_files(base / "annotations", "*.json")

        missing = max(0, texts - ann)
        still_needed = max(0, TARGET_MIN[split] - texts)

        total_texts += texts
        total_ann += ann
        total_missing += missing

        print(f"\n{split}/")
        print(f"  Texte:        {texts}")
        print(f"  Annotationen: {ann}")
        print(f"  Fehlend:      {missing}")
        print(f"  Ziel:         {TARGET_SIZES[split]}")
        print(f"  Noch benötigt: {still_needed}")

    print(f"\n  Gesamt:")
    print(f"  Texte:        {total_texts}")
    print(f"  Annotationen: {total_ann}")
    print(f"  Fehlend:      {total_missing}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
