"""Tests for weak labeling input guards (C3)."""
from pathlib import Path
import importlib.util
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("weak_label", PROJECT_ROOT / "scripts" / "weak_label.py")
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

def test_input_guard_rejects_gold(tmp_path: Path):
    # Simulate gold as input – should fail
    # Create a fake gold dir structure
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    try:
        mod.check_input_guards(gold_dir)
        assert False, "Should have raised for gold"
    except ValueError as e:
        assert "unlabeled" in str(e).lower() or "Gold" in str(e) or "Input-Split" in str(e)

def test_input_guard_rejects_example_pool(tmp_path: Path):
    pool_dir = tmp_path / "example_pool"
    pool_dir.mkdir()
    try:
        # Need to patch PROJECT_ROOT to make guard think this is the real pool
        # Instead test with actual path that is not unlabeled
        mod.check_input_guards(pool_dir)
        assert False, "Should have raised for pool"
    except ValueError as e:
        assert "unlabeled" in str(e).lower()

def test_input_guard_rejects_arbitrary(tmp_path: Path):
    other = tmp_path / "other"
    other.mkdir()
    try:
        mod.check_input_guards(other)
        assert False
    except ValueError:
        pass

def test_input_guard_accepts_unlabeled():
    # Real unlabeled dir should pass
    mod.check_input_guards(PROJECT_ROOT / "data" / "unlabeled")
    mod.check_input_guards(PROJECT_ROOT / "data" / "unlabeled" / "texts")

def test_input_guard_rejects_file_outside_unlabeled(tmp_path: Path):
    # Create a file outside unlabeled and try to load
    # The guard in load_unlabeled_examples checks path under unlabeled
    try:
        mod.load_unlabeled_examples(tmp_path)
        assert False
    except ValueError:
        pass
