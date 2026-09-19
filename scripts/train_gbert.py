"""Fine-tune deepset/gbert-base for job-ad entity tagging (BIO) and save it to artifacts/gbert_model."""
import random
import sys
from pathlib import Path

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ie_course.gbert_data import load_annotated_split

MODEL_NAME = "deepset/gbert-base"
TRAIN_DIR = ROOT / "data" / "example_pool"
OUT_DIR = ROOT / "artifacts" / "gbert_model"
TYPES = ["JOB_TITLE", "HARD_SKILL", "SOFT_SKILL", "EXPERIENCE", "EDUCATION", "LANGUAGE", "WORK_MODE"]
LABELS = ["O"] + [f"{p}-{t}" for t in TYPES for p in ("B", "I")]
EPOCHS, BATCH_SIZE, LR, MAX_LEN, SEED = 15, 8, 5e-5, 256, 42


def encode(example, tokenizer):
    enc = tokenizer(example["text"], return_offsets_mapping=True, truncation=True, max_length=MAX_LEN)
    labels = []
    for start, end in enc.pop("offset_mapping"):
        label = "O"
        if start != end:  # skip special tokens
            for ent in example["entities"]:
                if start < ent["end"] and end > ent["start"]:
                    label = ("B-" if start <= ent["start"] else "I-") + ent["type"]
                    break
        labels.append(LABELS.index(label) if start != end else -100)
    enc["labels"] = labels
    return dict(enc)


def batches(items, tokenizer):
    for i in range(0, len(items), BATCH_SIZE):
        chunk = items[i : i + BATCH_SIZE]
        padded = tokenizer.pad([{k: v for k, v in c.items() if k != "labels"} for c in chunk], return_tensors="pt")
        width = padded["input_ids"].shape[1]
        padded["labels"] = torch.tensor([c["labels"] + [-100] * (width - len(c["labels"])) for c in chunk])
        yield padded


def main():
    random.seed(SEED)
    torch.manual_seed(SEED)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForTokenClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(LABELS),
        id2label=dict(enumerate(LABELS)),
        label2id={l: i for i, l in enumerate(LABELS)},
    ).to(device)

    data = [encode(e, tokenizer) for e in load_annotated_split(TRAIN_DIR)]
    print(f"{len(data)} training examples, device={device}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)
    model.train()
    for epoch in range(EPOCHS):
        random.shuffle(data)
        total = 0.0
        for batch in batches(data, tokenizer):
            loss = model(**batch.to(device)).loss
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            total += loss.item()
        print(f"epoch {epoch + 1}/{EPOCHS}  loss {total:.4f}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(OUT_DIR, safe_serialization=True)
    tokenizer.save_pretrained(OUT_DIR)
    print(f"saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
