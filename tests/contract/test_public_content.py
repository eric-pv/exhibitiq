"""A4-08: the repository is public (Eric 2026-11-05) — no tracked file may contain credentials.

Same patterns as site/scripts/security-check.mjs (which covers the built site); this covers every tracked file.
Test fixtures that intentionally contain fake tokens are listed in ALLOWED.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERNS = {
    "GitHub token": r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b",
    "Anthropic/OpenAI key": r"\bsk-(ant-)?[A-Za-z0-9_-]{20,}\b",
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "Google API key": r"\bAIza[0-9A-Za-z_-]{35}\b",
    "Slack token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}
ALLOWED = {"site/src/security.test.ts", "site/scripts/security-check.mjs", "tests/contract/test_public_content.py"}


def test_no_credentials_in_tracked_files():
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True).stdout.split()
    hits = []
    for f in files:
        # data/raw/**/snapshots/ are immutable copies of third-party public pages (raw evidence); a key a vendor
        # publishes in its own page (e.g. a browser Maps key) is not our credential and must not be edited out.
        if f in ALLOWED or ("/snapshots/" in f and f.startswith("data/raw/")):
            continue
        p = ROOT / f
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        hits += [f"{f}: {name}" for name, rx in PATTERNS.items() if re.search(rx, text)]
    assert hits == []
