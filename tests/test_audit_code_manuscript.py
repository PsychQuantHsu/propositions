"""Tests for scripts/audit-code-manuscript.py (Rule R3 detector).

Rule R3: code↔manuscript symbol drift.
- Scan analysis/*.py AST: function names + module-level variable names
- Scan manuscript/docs/*.md backtick code: `X` references
- Diff:
  - code 有 manuscript 沒提 → FYI (could be stale code or private helper)
  - manuscript 提 code 沒有 → definite (dangling reference, broken)

Excluded paths: manuscript/docs/rounds/, legacy/, correspondence/, references/
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "audit-code-manuscript.py"


def run_audit(
    py_files: dict[str, str],
    md_files: dict[str, str],
    tmp_path: Path,
    tex_files: dict[str, str] | None = None,
    bib_files: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Set up analysis/ and manuscript/docs/, run audit, return (rc, stdout, stderr).

    Optional tex_files/bib_files create files at manuscript root (for R3 allowlist tests).
    """
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    for fname, content in py_files.items():
        (analysis / fname).write_text(content)
    manuscript = tmp_path / "manuscript"
    docs = manuscript / "docs"
    docs.mkdir(parents=True)
    for fname, content in md_files.items():
        (docs / fname).write_text(content)
    for fname, content in (tex_files or {}).items():
        (manuscript / fname).write_text(content)
    for fname, content in (bib_files or {}).items():
        (manuscript / fname).write_text(content)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manuscript-root", str(manuscript),
            "--code-root", str(analysis),
            "--report-format", "json",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_no_drift_baseline(tmp_path):
    """Matching code/manuscript symbols → zero finding."""
    py_files = {
        "checker.py": "def compute_score():\n    pass\n\ndef verify_invariant():\n    pass\n",
    }
    md_files = {
        "method.md": "The score is computed via `compute_score`. Validation uses `verify_invariant`.",
    }
    rc, stdout, _ = run_audit(py_files, md_files, tmp_path)
    assert rc == 0, f"Expected 0 (no drift), got {rc}. stdout={stdout!r}"


def test_dangling_manuscript_ref(tmp_path):
    """Manuscript references code that doesn't exist → definite finding."""
    py_files = {
        "checker.py": "def compute_score():\n    pass\n",
    }
    md_files = {
        "method.md": "Computed via `compute_score` and `nonexistent_helper`.",
    }
    rc, stdout, _ = run_audit(py_files, md_files, tmp_path)
    assert rc == 1, f"Expected 1 (dangling ref), got {rc}"
    import json
    report = json.loads(stdout)
    dangling = [f for f in report["findings"] if f["severity"] == "definite"]
    assert any("nonexistent_helper" in f["match"] for f in dangling), \
        f"Expected nonexistent_helper as dangling: {report['findings']}"


def test_latex_label_demoted_to_fyi(tmp_path):
    """LaTeX \\label{X} referenced as `X` in .md must NOT be definite (calibration fix for #42 F-R3-Cal)."""
    py_files = {"checker.py": "def actual_code():\n    pass\n"}
    tex_files = {
        "main.tex": r"\begin{theorem}\label{main_thm_ess}\nFoo\n\end{theorem}",
    }
    md_files = {
        "method.md": "See `main_thm_ess` for the theorem. Also `actual_code` exists.",
    }
    rc, stdout, _ = run_audit(py_files, md_files, tmp_path, tex_files=tex_files)
    # rc may be 1 if any FYI exists, but no definite finding for main_thm_ess
    import json
    report = json.loads(stdout)
    definites = [f for f in report["findings"] if f["severity"] == "definite"]
    assert not any("main_thm_ess" in f["match"] for f in definites), \
        f"main_thm_ess should be demoted to FYI (LaTeX label), got definite: {definites}"


def test_bib_key_demoted_to_fyi(tmp_path):
    """BibTeX @article{X,...} referenced as `X` in .md must NOT be definite."""
    py_files = {"checker.py": "def foo():\n    pass\n"}
    bib_files = {
        "refs.bib": "@article{Hsu2024Note, title={Note}}",
    }
    md_files = {
        "method.md": "Cited in `Hsu2024Note`.",
    }
    rc, stdout, _ = run_audit(py_files, md_files, tmp_path, bib_files=bib_files)
    import json
    report = json.loads(stdout)
    definites = [f for f in report["findings"] if f["severity"] == "definite"]
    assert not any("Hsu2024Note" in f["match"] for f in definites), \
        f"Hsu2024Note should be demoted to FYI (bib entry), got definite: {definites}"


def test_cite_key_demoted_to_fyi(tmp_path):
    """\\cite{X} key referenced as `X` in .md must NOT be definite."""
    py_files = {"checker.py": "def foo():\n    pass\n"}
    tex_files = {
        "main.tex": r"This is the result \citep{lem_Falmagne_Lundberg}.",
    }
    md_files = {
        "method.md": "Per `lem_Falmagne_Lundberg`.",
    }
    rc, stdout, _ = run_audit(py_files, md_files, tmp_path, tex_files=tex_files)
    import json
    report = json.loads(stdout)
    definites = [f for f in report["findings"] if f["severity"] == "definite"]
    assert not any("lem_Falmagne_Lundberg" in f["match"] for f in definites), \
        f"lem_Falmagne_Lundberg should be demoted to FYI (cite key), got definite: {definites}"


def test_tilde_fence_skipped(tmp_path):
    """#50 F-Logic-H4: ~~~ markdown fences must skip backtick refs inside.

    Old impl only recognized ```. Tilde-fenced code blocks (CommonMark spec)
    were treated as regular text, so `bar_baz` inside leaked as a manuscript
    reference and produced false dangling-symbol findings.
    """
    py_files = {"checker.py": "def actual_code():\n    pass\n"}
    md_files = {
        "method.md": (
            "Normal `actual_code` reference.\n"
            "\n"
            "~~~\n"
            "Inside tilde fence: `phantom_helper` and `nonexistent_thing`.\n"
            "~~~\n"
            "\n"
            "Back to normal text.\n"
        ),
    }
    rc, stdout, _ = run_audit(py_files, md_files, tmp_path)
    import json
    report = json.loads(stdout)
    definites = [f for f in report["findings"] if f["severity"] == "definite"]
    # phantom_helper and nonexistent_thing are inside ~~~ fence; must not flag
    leaked = [f for f in definites if f["match"] in ("phantom_helper", "nonexistent_thing")]
    assert not leaked, f"H4 regression: tilde-fenced backticks leaked: {leaked}"


def test_import_alias_captured(tmp_path):
    """#50 C3: AST extractor must capture import aliases.

    `from X import Y as Z` and `import X as Y` should add Z/Y to code symbols
    so manuscript references to aliased imports don't false-flag as dangling.
    """
    py_files = {
        "checker.py": (
            "from numpy import array as np_array\n"
            "import pandas as pd\n"
            "\n"
            "def native_func():\n"
            "    pass\n"
        ),
    }
    md_files = {
        "method.md": "We use `np_array` and `pd` and `native_func`.",
    }
    rc, stdout, _ = run_audit(py_files, md_files, tmp_path)
    import json
    report = json.loads(stdout)
    definites = [f for f in report["findings"] if f["severity"] == "definite"]
    leaked = [f for f in definites if f["match"] in ("np_array", "pd")]
    assert not leaked, f"C3 regression: import aliases not captured: {leaked}"
