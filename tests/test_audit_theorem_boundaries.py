"""Tests for scripts/audit-theorem-boundaries.py (#98).

Covers:
- T-A: parser inventory — expected 7 numbered envs in main.tex with locked line ranges
- T-B: cross-check `_stage2/theorem1.jsonl` — 81 props all within Theorem 1 env range (acceptance gate)
- T-C: cross-check `main.jsonl` non-crash (mismatch count surfaced, not asserted)
- T-D: `--format md` emits non-empty markdown table
"""
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "audit-theorem-boundaries.py"
MAIN_TEX = REPO_ROOT / "manuscript" / "main.tex"
STAGE2_THM1 = REPO_ROOT / "manuscript" / "propositions" / "_stage2" / "theorem1.jsonl"
MAIN_JSONL = REPO_ROOT / "manuscript" / "propositions" / "main.jsonl"


def run_audit(*args):
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def test_script_exists():
    """Audit script file is present."""
    assert SCRIPT.exists(), f"Missing {SCRIPT}"


def test_inventory_main_tex():
    """T-A — parser lists expected 7 numbered envs with locked line ranges.

    Locked baseline (verified by hand against manuscript/main.tex):
    - lem:affine-bijection: theorem env L285-L311, proof L313-L330
    - lem:affine-fechnerian-power-law: env L339-L360, proof L362-L449
    - thm:eta-s: env L469-L550, proof L560-L714 (corollary L552-L558 is sibling)
    - thm:gamma-g: env L719-L763, proof L765-L887
    - thm:mult-trans: env L892-L927, proof L929-L1038
    - thm:phil-general: env L1043-L1098, proof L1100-L1157
    - thm:main: env L1237-L1307, proof L1309-L1315
    """
    result = run_audit(str(MAIN_TEX), "--format", "json")
    assert result.returncode == 0, f"non-zero exit: {result.stderr}"
    envs = json.loads(result.stdout)

    expected = {
        "lem:affine-bijection": (285, 311),
        "lem:affine-fechnerian-power-law": (339, 360),
        "thm:eta-s": (469, 550),
        "thm:gamma-g": (719, 763),
        "thm:mult-trans": (892, 927),
        "thm:phil-general": (1043, 1098),
        "thm:main": (1237, 1307),
    }
    label_map = {e["label"]: (e["begin_line"], e["end_line"]) for e in envs if e.get("label")}
    for label, (start, end) in expected.items():
        assert label in label_map, f"label {label!r} missing from inventory"
        actual = label_map[label]
        assert actual == (start, end), f"{label}: expected ({start},{end}), got {actual}"


def test_crosscheck_stage2_theorem1():
    """T-B — _stage2/theorem1.jsonl 81 props all within Theorem 1 env range.

    Acceptance gate: mismatch_count == 0 (Theorem 1 cured via #97).
    """
    if not STAGE2_THM1.exists():
        return  # gracefully skip if stage2 absent
    result = run_audit(str(MAIN_TEX), "--jsonl", str(STAGE2_THM1))
    assert result.returncode == 0, (
        f"_stage2/theorem1.jsonl crosscheck FAILED (mismatches detected): {result.stdout}\n{result.stderr}"
    )


def test_crosscheck_main_jsonl_baseline_zero():
    """T-C / #115 M-3 — main.jsonl crosscheck baseline locked at exactly 0
    mismatches.

    Baseline established post-#113 (containing_block canonicalization) +
    post-#114 (location refresh): all 214 checked props (out of 321; 107
    non-env containing_blocks like sec:* / discussion / abstract are silently
    skipped) fall within their declared env line ranges.

    Why strict zero (not ``in (0, 1)``): if a future change introduces drift,
    we want the test to fire — not silently accept it. Per the project's
    ``manuscript-jsonl-sync`` rule, any main.tex edit that shifts prop
    locations must be resolved in the same PR; this test is that rule's
    machine enforcer.
    """
    if not MAIN_JSONL.exists():
        return
    result = run_audit(str(MAIN_TEX), "--jsonl", str(MAIN_JSONL))
    assert result.returncode == 0, (
        f"Baseline drift: expected returncode==0 (0 mismatches), got "
        f"{result.returncode}.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}\n"
        f"Per `manuscript-jsonl-sync` rule, drift must be resolved in the "
        f"same PR — investigate the offending props, refresh locations, "
        f"or update containing_block."
    )
    assert "mismatches=0" in result.stdout, (
        f"Expected 'mismatches=0' in summary line; got: {result.stdout}"
    )


def test_format_md_emits_table():
    """T-D — --format md output contains markdown table for baseline doc."""
    result = run_audit(str(MAIN_TEX), "--format", "md")
    assert result.returncode == 0
    out = result.stdout
    assert "| label " in out or "|label" in out, f"no markdown table header: {out[:200]}"
    assert "thm:eta-s" in out, "Theorem 1 label missing from md output"
    assert "thm:main" in out, "Theorem 5 label missing from md output"


# ---------- Path B regression guards (/idd-verify #98 cross-model findings) ----------


def test_same_line_label_captured(tmp_path):
    """T-E (Logic H-1 / Codex) — `\\begin{theorem}\\label{thm:foo}` on the
    same line MUST capture the label, not silently return None.
    """
    fixture_tex = tmp_path / "fixture.tex"
    fixture_tex.write_text(
        "Some intro\n"
        "\\begin{theorem}\\label{thm:sameline}\n"
        "Statement body\n"
        "\\end{theorem}\n"
    )
    result = run_audit(str(fixture_tex), "--format", "json")
    assert result.returncode == 0
    envs = json.loads(result.stdout)
    label_map = {e["label"]: (e["begin_line"], e["end_line"]) for e in envs if e.get("label")}
    assert "thm:sameline" in label_map, (
        f"same-line \\label was not captured: envs={envs}"
    )


def test_env_types_include_definition_remark_conjecture(tmp_path):
    """T-F (DA F1 / Codex) — script must detect definition, remark, conjecture
    envs declared via \\newtheorem in main.tex L26-L28.
    """
    fixture_tex = tmp_path / "fixture.tex"
    fixture_tex.write_text(
        "\\begin{definition}\\label{def:test}\nDef body\n\\end{definition}\n"
        "\\begin{remark}\\label{rem:test}\nRemark body\n\\end{remark}\n"
        "\\begin{conjecture}\\label{conj:test}\nConj body\n\\end{conjecture}\n"
    )
    result = run_audit(str(fixture_tex), "--format", "json")
    assert result.returncode == 0
    envs = json.loads(result.stdout)
    types_seen = {e["type"] for e in envs}
    assert "definition" in types_seen, f"definition env not detected: {types_seen}"
    assert "remark" in types_seen, f"remark env not detected: {types_seen}"
    assert "conjecture" in types_seen, f"conjecture env not detected: {types_seen}"


def test_crosscheck_summary_visible():
    """T-G (Codex M-3 escalated) — crosscheck output MUST include a
    [summary] line showing total, checked, skipped_unresolvable_cb, and
    mismatch counts so users can see how many props were silently bypassed.
    """
    if not MAIN_JSONL.exists():
        return
    result = run_audit(str(MAIN_TEX), "--jsonl", str(MAIN_JSONL))
    out = result.stdout
    assert "[summary]" in out, f"no [summary] line in output: {out[:300]}"
    assert "total=" in out and "checked=" in out and "skipped_unresolvable_cb=" in out, (
        f"summary line missing counters: {out[:300]}"
    )


# ---------- #100 Path B: parse_location + PROOF_TARGET_RE hardening ----------


def _load_audit_module():
    """Import audit-theorem-boundaries.py despite hyphenated filename."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("audit_theorem_boundaries", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_lib_parser():
    """Import scripts/_lib/latex_env_parser.py (shared module per #115 M-5)."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from _lib import latex_env_parser

    return latex_env_parser


def test_parse_location_rejects_inverted_range():
    """#100 Path B / #115 M-2: parse_location must reject inverted ranges
    (end < start) and zero/negative base, returning None rather than a
    coincidentally-passing tuple.

    Source of truth post-#115 M-5: scripts/_lib/latex_env_parser.py
    (audit-script re-exports via import).
    """
    parser = _load_lib_parser()
    assert parser.parse_location("main.tex:L10-L20") == (10, 20), "valid range"
    assert parser.parse_location("main.tex:L42") == (42, 42), "single line"
    assert parser.parse_location("main.tex:L20-L10") is None, "inverted range rejected"
    assert parser.parse_location("main.tex:L0") is None, "zero base rejected"
    assert parser.parse_location("garbage") is None, "non-match returns None"


def test_proof_target_re_captures_first_ref():
    """#100 Path B / #115 M-1: PROOF_TARGET_RE non-greedy prefix must capture
    the FIRST \\ref in a multi-ref proof title, not the last.

    Source of truth post-#115 M-5: scripts/_lib/latex_env_parser.py.
    """
    parser = _load_lib_parser()
    # Single ref — baseline
    m1 = parser.PROOF_TARGET_RE.search(
        r"\begin{proof}[Proof of Theorem~\ref{thm:eta-s}]"
    )
    assert m1 and m1.group(1) == "thm:eta-s"
    # Multi-ref — must bind to FIRST, not last
    m2 = parser.PROOF_TARGET_RE.search(
        r"\begin{proof}[Proof of Theorem~\ref{thm:a}, using Lemma~\ref{lem:b}]"
    )
    assert m2 and m2.group(1) == "thm:a", (
        f"non-greedy must capture first ref, got {m2.group(1) if m2 else None}"
    )


# ---------- #115 M-4: unmatched \begin warning ----------


def test_parse_envs_warns_on_unmatched_begin(tmp_path):
    """#115 M-4 — audit-script invocation (default warn_on_residue=True) must
    surface unmatched ``\\begin{theorem}`` to stderr when no matching
    ``\\end{theorem}`` is found.

    Previously the open_stack residue was silently dropped from the env
    inventory, masking real LaTeX errors (typo'd ``\\end``, mid-edit state).
    Non-blocking: parser still returns the matched inventory, exit 0.
    """
    fixture_tex = tmp_path / "dangling.tex"
    fixture_tex.write_text(
        "Intro paragraph\n"
        "\\begin{theorem}\n"
        "\\label{thm:dangling}\n"
        "Statement body without closing tag\n"
    )
    result = run_audit(str(fixture_tex), "--format", "json")
    # Parser is non-blocking: exit 0 with partial inventory + stderr warning
    assert result.returncode == 0, (
        f"unmatched begin should be non-blocking; got exit {result.returncode}"
    )
    assert "unmatched" in result.stderr, (
        f"stderr missing 'unmatched' warning: {result.stderr!r}"
    )
    assert "theorem" in result.stderr, (
        f"stderr warning missing env type 'theorem': {result.stderr!r}"
    )


# ---------- #115 M-5: shared module locked-down ----------


def test_audit_script_uses_shared_lib():
    """#115 M-5 — audit-theorem-boundaries.py must import the LaTeX env parser
    from scripts/_lib/, not maintain its own inline copies.

    Regression guard: if a future refactor re-introduces module-level
    BEGIN_RE / END_RE / parse_envs / parse_location / normalize_containing_block
    constants directly in audit-theorem-boundaries.py (instead of importing
    them), this assertion fires.
    """
    source = SCRIPT.read_text(encoding="utf-8")
    # Must import from _lib
    assert "from _lib.latex_env_parser import" in source, (
        "audit script must import shared parser from _lib; got source without "
        "expected import line"
    )
    # Must NOT have inline regex definitions
    assert "BEGIN_RE = re.compile" not in source, (
        "audit script has inline BEGIN_RE — re-introduces M-5 drift surface"
    )
    assert "PROOF_TARGET_RE = re.compile" not in source, (
        "audit script has inline PROOF_TARGET_RE — re-introduces drift"
    )
