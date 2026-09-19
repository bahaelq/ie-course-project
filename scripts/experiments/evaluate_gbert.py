from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SRC_ROOT: Final[Path] = PROJECT_ROOT / "src"
for p in (str(PROJECT_ROOT), str(SRC_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from ie_course.gbert_data import load_annotated_split
from ie_course.gbert_infer import load_model, predict_entities
from ie_course.metrics import evaluate


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model-dir", type=Path, default=PROJECT_ROOT / "artifacts" / "gbert_model")
    parser.add_argument("--split-dir", type=Path, default=None, help="Override split directory")
    parser.add_argument("--split", choices=["gold", "example_pool", "smoke_test"], default="gold")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--max-length", type=int, default=256)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    split_dir = args.split_dir or (PROJECT_ROOT / "data" / args.split)
    output_dir = args.output_dir or (PROJECT_ROOT / "artifacts" / f"gbert_eval_{args.split}")

    examples = load_annotated_split(split_dir)
    if not examples:
        print(f"No annotated examples found in {split_dir}")
        return 1

    model, tokenizer = load_model(args.model_dir)

    gold_by_doc: dict[str, list[dict]] = {}
    pred_by_doc: dict[str, list[dict]] = {}
    predictions_out = []
    for example in examples:
        doc_id = example["id"]
        gold_by_doc[doc_id] = example["entities"]
        preds = predict_entities(example["text"], model, tokenizer, max_length=args.max_length)
        pred_by_doc[doc_id] = preds
        predictions_out.append({"id": doc_id, "predictions": preds})

    metrics = evaluate(gold_by_doc, pred_by_doc)
    metrics["config"] = {"model_dir": str(args.model_dir), "split": args.split, "split_dir": str(split_dir), "examples": len(examples)}

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "predictions.json").write_text(json.dumps(predictions_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics["micro"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
