"""BIO alignment from character spans to token labels."""
from __future__ import annotations

from typing import List, Dict

ALLOWED_TYPES = ("JOB_TITLE","HARD_SKILL","SOFT_SKILL","EXPERIENCE","EDUCATION","LANGUAGE","WORK_MODE")
LABEL_LIST = ["O"] + [f"{p}-{t}" for t in ALLOWED_TYPES for p in ("B","I")]
LABEL2ID = {l:i for i,l in enumerate(LABEL_LIST)}
ID2LABEL = {i:l for l,i in LABEL2ID.items()}

def validate_entity(text: str, ent: Dict) -> bool:
    s,e,t = ent.get("start"), ent.get("end"), ent.get("text")
    if not isinstance(s,int) or not isinstance(e,int) or not isinstance(t,str): return False
    if s<0 or e<0 or s>=e: return False
    if not (0 <= s < len(text) and 0 <= e <= len(text)): return False
    if text[s:e] != t: return False
    return True

def align_labels(text: str, entities: List[Dict], tokenizer, max_length=512):
    """Align character spans to BIO labels using offset_mapping."""
    # validate
    for ent in entities:
        if not validate_entity(text, ent):
            raise ValueError(f"Invalid span {ent}")
        # check overlaps
    # sort entities by start
    ents = sorted(entities, key=lambda x: x["start"])
    # check overlaps
    for i in range(len(ents)):
        for j in range(i+1, len(ents)):
            if max(ents[i]["start"], ents[j]["start"]) < min(ents[i]["end"], ents[j]["end"]):
                raise ValueError(f"Overlap {ents[i]} {ents[j]}")
    enc = tokenizer(text, return_offsets_mapping=True, truncation=True, max_length=max_length, add_special_tokens=True)
    offsets = enc["offset_mapping"]
    input_ids = enc["input_ids"]
    labels = []
    for idx, (s,e) in enumerate(offsets):
        # special tokens have (0,0) or None
        if s==0 and e==0:
            labels.append(-100)
            continue
        # find entity containing token
        lab = "O"
        for ent in ents:
            es, ee, typ = ent["start"], ent["end"], ent["type"]
            # token inside entity if token start >= es and token end <= ee and token not empty
            # need overlap logic: token is part of entity if offsets overlap significantly
            # simplest: token start >= es and token start < ee
            if s >= es and s < ee:
                if s == es:
                    lab = f"B-{typ}"
                else:
                    lab = f"I-{typ}"
                break
            # also case token straddles entity start? but tokenizer offsets are precise
        # ensure punctuation outside entity stays O (already)
        labels.append(LABEL2ID[lab])
    return {"input_ids": input_ids, "labels": labels, "attention_mask": enc["attention_mask"]}

def decode_bio(labels, tokenizer, input_ids):
    """Decode for debugging – not used in training."""
    toks = tokenizer.convert_ids_to_tokens(input_ids)
    return list(zip(toks, [ID2LABEL.get(l, "O") if l!=-100 else "IGN" for l in labels]))
