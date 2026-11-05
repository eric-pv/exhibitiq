"""A3-08: the Skill's deterministic outputs are identical to the committed digests (any clean workspace)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "exhibitiq" / "scripts"))
import repro_check  # noqa: E402


def test_outputs_match_committed_digests():
    assert repro_check.main(["--check"]) == 0
