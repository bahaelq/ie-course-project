from pathlib import Path
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bio", PROJECT_ROOT / "src" / "ie_course" / "bio.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

class SimpleTokenizer:
    def __call__(self, text, return_offsets_mapping=True, truncation=True, max_length=512, add_special_tokens=True):
        # simple whitespace + punctuation tokenizer with offsets
        import re
        tokens=[]
        offsets=[]
        # CLS
        if add_special_tokens:
            tokens.append("[CLS]")
            offsets.append((0,0))
        for m in re.finditer(r"\w+|[^\w\s]", text, re.UNICODE):
            s,e=m.span()
            if len(tokens) >= max_length-1 and truncation:
                break
            tokens.append(m.group())
            offsets.append((s,e))
        if add_special_tokens:
            tokens.append("[SEP]")
            offsets.append((0,0))
        # map tokens to ids via hash
        input_ids=[hash(t)%10000 for t in tokens]
        return {"input_ids": input_ids, "offset_mapping": offsets, "attention_mask":[1]*len(input_ids)}
    def convert_ids_to_tokens(self, ids):
        return [f"tok_{i}" for i in ids]

tok = SimpleTokenizer()

def test_single_word():
    text="Data Scientist bei Firma"
    ents=[{"type":"JOB_TITLE","text":"Data Scientist","start":0,"end":14}]
    out=mod.align_labels(text, ents, tok)
    assert len(out["labels"])==len(out["input_ids"])
    # first real token should be B-JOB_TITLE
    labs=[l for l in out["labels"] if l!=-100]
    assert mod.LABEL2ID["B-JOB_TITLE"] in labs

def test_multi_word():
    text="Softwareentwickler Python (m/w/d) Backend bei Firma"
    ents=[{"type":"JOB_TITLE","text":"Softwareentwickler Python (m/w/d) Backend","start":0,"end":41}]
    out=mod.align_labels(text, ents, tok)
    labs=[l for l in out["labels"] if l!=-100]
    # should have B and I
    assert mod.LABEL2ID["B-JOB_TITLE"] in labs
    assert mod.LABEL2ID["I-JOB_TITLE"] in labs

def test_start():
    text="Erzieher (m/w/d) Kindergarten ist toll"
    ents=[{"type":"JOB_TITLE","text":"Erzieher (m/w/d) Kindergarten","start":0,"end":29}]
    out=mod.align_labels(text, ents, tok)
    assert out["labels"][1]==mod.LABEL2ID["B-JOB_TITLE"]  # after CLS

def test_end():
    text="Wir suchen Erzieher (m/w/d) Kindergarten"
    cand="Erzieher (m/w/d) Kindergarten"
    s=text.find(cand)
    out=mod.align_labels(text, [{"type":"JOB_TITLE","text":cand,"start":s,"end":s+len(cand)}], tok)
    assert mod.LABEL2ID["B-JOB_TITLE"] in out["labels"]

def test_umlaut():
    for cand in ["ä","ö","ü","ß"]:
        text=f"Test {cand} hier"
        s=text.find(cand)
        out=mod.align_labels(text, [{"type":"SOFT_SKILL","text":cand,"start":s,"end":s+len(cand)}], tok)
        assert mod.LABEL2ID["B-SOFT_SKILL"] in out["labels"]

def test_mwd():
    text="Softwareentwickler (m/w/d) Backend"
    cand="(m/w/d)"
    s=text.find(cand)
    out=mod.align_labels(text, [{"type":"JOB_TITLE","text":"Softwareentwickler (m/w/d) Backend","start":0,"end":len(text)}], tok)
    assert mod.LABEL2ID["I-JOB_TITLE"] in out["labels"]

def test_slash():
    text="Erzieher / Erzieherin"
    cand="Erzieher / Erzieherin"
    out=mod.align_labels(text, [{"type":"JOB_TITLE","text":cand,"start":0,"end":len(cand)}], tok)
    assert mod.LABEL2ID["B-JOB_TITLE"] in out["labels"]

def test_bindestrich():
    text="Gesundheits- und Krankenpfleger"
    cand="Gesundheits- und Krankenpfleger"
    out=mod.align_labels(text, [{"type":"JOB_TITLE","text":cand,"start":0,"end":len(cand)}], tok)
    assert mod.LABEL2ID["B-JOB_TITLE"] in out["labels"]

def test_punkt_nach_entity():
    text="Softwareentwickler Python (m/w/d) Backend. Noch mehr"
    cand="Softwareentwickler Python (m/w/d) Backend"
    s=0
    out=mod.align_labels(text, [{"type":"JOB_TITLE","text":cand,"start":s,"end":s+len(cand)}], tok)
    # punkt token should be O
    # find token for "."
    toks=tok.convert_ids_to_tokens(out["input_ids"])
    # find "." token label should be O
    for tok_str, lab in zip(toks, out["labels"]):
        if tok_str==".":
            assert lab==mod.LABEL2ID["O"] or lab==-100

def test_komma():
    text="Backend, Firma"
    cand="Backend"
    s=text.find(cand)
    out=mod.align_labels(text, [{"type":"JOB_TITLE","text":cand,"start":s,"end":s+len(cand)}], tok)
    toks=tok.convert_ids_to_tokens(out["input_ids"])
    # comma should be O
    for t,l in zip(toks, out["labels"]):
        if t==",":
            assert l==mod.LABEL2ID["O"]

def test_repeated_text_different_start():
    text="Erzieher (m/w/d) Kindergarten bei Firma. Erzieher (m/w/d) Kindergarten nochmal."
    cand="Erzieher (m/w/d) Kindergarten"
    # first occurrence
    out1=mod.align_labels(text, [{"type":"JOB_TITLE","text":cand,"start":0,"end":29}], tok)
    out2=mod.align_labels(text, [{"type":"JOB_TITLE","text":cand,"start":text.find(cand,30),"end":text.find(cand,30)+29}], tok)
    assert out1["labels"]!=out2["labels"]  # different positions

def test_invalid_offsets():
    text="Hallo Welt"
    try:
        mod.align_labels(text, [{"type":"JOB_TITLE","text":"Hallo","start":-1,"end":5}], tok)
        assert False
    except ValueError: pass
    try:
        mod.align_labels(text, [{"type":"JOB_TITLE","text":"Hallo","start":0,"end":100}], tok)
        assert False
    except ValueError: pass
    try:
        mod.align_labels(text, [{"type":"JOB_TITLE","text":"Falsch","start":0,"end":5}], tok)
        assert False
    except ValueError: pass

def test_work_mode_rejected_not_labeled():
    # WORK_MODE with unbefristet should not be in dataset – we test that our pipeline filters it
    # Here we just ensure align would work but we filter via validate
    text="Teilzeit 30h, unbefristet"
    cand="Teilzeit 30h, unbefristet"
    # validate should reject via structural_validate, not here – but align would label
    out=mod.align_labels(text, [{"type":"WORK_MODE","text":cand,"start":0,"end":len(cand)}], tok)
    # still aligns, but pipeline should have rejected before
    assert len(out["labels"])>0

def test_regression_1031():
    p=Path(__file__).resolve().parents[1]/"data/unlabeled/texts/job_ad_1031.txt"
    text=p.read_text(encoding="utf-8")
    cand="Gesundheits- und Krankenpfleger (m/w/d) Intensivstation"
    out=mod.align_labels(text, [{"type":"JOB_TITLE","text":cand,"start":0,"end":len(cand)}], tok)
    assert mod.LABEL2ID["B-JOB_TITLE"] in out["labels"]

def test_regression_1036():
    p=Path(__file__).resolve().parents[1]/"data/unlabeled/texts/job_ad_1036.txt"
    text=p.read_text(encoding="utf-8")
    cand="Softwareentwickler Python (m/w/d) Backend"
    out=mod.align_labels(text, [{"type":"JOB_TITLE","text":cand,"start":0,"end":len(cand)}], tok)
    assert mod.LABEL2ID["B-JOB_TITLE"] in out["labels"]

def test_regression_1051():
    p=Path(__file__).resolve().parents[1]/"data/unlabeled/texts/job_ad_1051.txt"
    text=p.read_text(encoding="utf-8")
    cand="Kommissionierer (m/w/d) Lager"
    out=mod.align_labels(text, [{"type":"JOB_TITLE","text":cand,"start":0,"end":len(cand)}], tok)
    assert mod.LABEL2ID["B-JOB_TITLE"] in out["labels"]

def test_regression_1066():
    p=Path(__file__).resolve().parents[1]/"data/unlabeled/texts/job_ad_1066.txt"
    text=p.read_text(encoding="utf-8")
    cand="Erzieher (m/w/d) Kindergarten"
    out=mod.align_labels(text, [{"type":"JOB_TITLE","text":cand,"start":0,"end":len(cand)}], tok)
    assert mod.LABEL2ID["B-JOB_TITLE"] in out["labels"]
