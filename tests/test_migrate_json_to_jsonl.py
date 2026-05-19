"""Tests for scripts/migrate-json-to-jsonl.py.

Focused on #86 defense-in-depth path validation: input must be inside repo
and have .json suffix, to prevent shell-access attackers from pivoting
--delete-input into arbitrary-file delete via /etc/passwd.json or
../../etc/X.json.

Real-world exploitability is low (shell access required), but the guard is
cheap to add and gates CI scenarios where the migration script might be
invoked via untrusted args.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "migrate-json-to-jsonl.py"


def test_rejects_input_outside_repo_returns_exit_2(tmp_path):
    """#86: input file outside repo root MUST be rejected with exit 2 (parse error)
    BEFORE migrate() runs — defense against /etc/passwd.json style pivots."""
    # tmp_path is outside the repo (pytest's tmpdir lives in /private/var or similar)
    outside_file = tmp_path / "evil.json"
    outside_file.write_text(json.dumps({"propositions": []}))

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(outside_file)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, (
        f"expected exit 2 for outside-repo input, got {result.returncode}: "
        f"stderr={result.stderr!r}"
    )
    assert "must be inside repo" in result.stderr, (
        f"expected 'must be inside repo' error: {result.stderr}"
    )


def test_rejects_non_json_suffix_returns_exit_2(tmp_path):
    """#86: input file without .json suffix MUST be rejected with exit 2."""
    # Create a file inside the repo with wrong suffix
    inside_file = REPO_ROOT / "tests" / "_test_artifact_86_wrong_suffix.txt"
    try:
        inside_file.write_text(json.dumps({"propositions": []}))
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(inside_file)],
            capture_output=True, text=True,
        )
        assert result.returncode == 2, (
            f"expected exit 2 for non-.json suffix, got {result.returncode}: "
            f"stderr={result.stderr!r}"
        )
        assert "must have .json suffix" in result.stderr, (
            f"expected 'must have .json suffix' error: {result.stderr}"
        )
    finally:
        inside_file.unlink(missing_ok=True)


def test_rejects_traversal_input_returns_exit_2(tmp_path):
    """#86: traversal path like ../../etc/X.json MUST be rejected — Path.resolve()
    canonicalizes to absolute outside-repo path, then is_relative_to fails."""
    # Construct a traversal-style path that resolves outside the repo
    traversal = REPO_ROOT / ".." / ".." / "etc" / "X.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(traversal)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, (
        f"expected exit 2 for traversal input, got {result.returncode}: "
        f"stderr={result.stderr!r}"
    )
    assert "must be inside repo" in result.stderr


def test_accepts_valid_input_inside_repo(tmp_path):
    """#86: input inside repo with .json suffix MUST pass path validation
    and proceed to migration (does NOT regress happy-path behavior)."""
    inside_file = REPO_ROOT / "tests" / "_test_artifact_86_valid.json"
    out_jsonl = REPO_ROOT / "tests" / "_test_artifact_86_valid.jsonl"
    out_meta = REPO_ROOT / "tests" / "_test_artifact_86_valid_meta.json"
    try:
        inside_file.write_text(json.dumps({
            "propositions": [
                {"id": "P001", "text": "claim", "location": "main.tex:L1",
                 "containing_block": "t", "claim_type": "claim",
                 "asserts": ["a"], "cites": []},
            ],
            "schema_version": "1.1",
        }))
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(inside_file),
             "--jsonl-out", str(out_jsonl),
             "--meta-out", str(out_meta)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"valid inside-repo .json should succeed: {result.returncode}: "
            f"stderr={result.stderr!r}"
        )
        assert out_jsonl.exists(), "expected jsonl output"
        assert out_meta.exists(), "expected meta output"
    finally:
        for p in (inside_file, out_jsonl, out_meta):
            p.unlink(missing_ok=True)
