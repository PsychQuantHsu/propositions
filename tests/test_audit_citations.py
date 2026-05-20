"""Tests for scripts/audit-citations.py (Rule R2 + R2-bis detector).

Rule R2: citation label leak — \\citet[Theorem~\\texttt{snake_case_id}]{X}
Rule R2-bis: bib cross-check — \\cite{key} ↔ refs.bib @type{key, ...}
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "audit-citations.py"


def run_audit(tex_content: str, bib_content: str, tmp_path: Path) -> tuple[int, str, str]:
    """Write tex_content + bib_content to tmp_path/manuscript/, run audit, return (rc, stdout, stderr)."""
    manuscript_root = tmp_path / "manuscript"
    manuscript_root.mkdir()
    (manuscript_root / "main.tex").write_text(tex_content)
    (manuscript_root / "refs.bib").write_text(bib_content)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--manuscript-root", str(manuscript_root), "--report-format", "json"],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_label_leak_main_thm_ess(tmp_path):
    """\\citet[Theorem~\\texttt{main_thm_ess}]{DobleHsu2020} → R2 label leak."""
    tex = r"""
By the corollary \citep[\S 3.1]{Aczel1966}
(cf.\ \citet[Theorem~\texttt{main\_thm\_ess}]{DobleHsu2020}
which uses the same reduction).

Apply the theorem of \citet{DobleHsu2020} (\texttt{main\_thm\_ess}).
"""
    bib = "@article{Aczel1966, title={X}}\n@article{DobleHsu2020, title={Y}}\n"
    rc, stdout, _ = run_audit(tex, bib, tmp_path)
    assert rc == 1, f"Expected exit 1 (label leak), got {rc}. stdout={stdout!r}"
    import json
    report = json.loads(stdout)
    r2_findings = [f for f in report["findings"] if f["rule"] == "R2"]
    assert len(r2_findings) >= 2, f"Expected ≥2 R2 findings (2 main_thm_ess), got: {r2_findings}"


def test_legit_theorem_number_not_flagged(tmp_path):
    """\\citet[Theorem 3.1]{X} or [Theorem on $\\eta = f(s)$ case]{X} → NOT flagged."""
    tex = r"""
\citet[Theorem 3.1]{Smith2020}
\citet[Theorem on $\eta = f(s)$ case]{DobleHsu2020}
\citep[\S 3.1]{Aczel1966}
"""
    bib = "@article{Smith2020}\n@article{DobleHsu2020}\n@article{Aczel1966}\n"
    rc, stdout, _ = run_audit(tex, bib, tmp_path)
    assert rc == 0, f"Expected exit 0 (legit), got {rc}. stdout={stdout!r}"


def test_bib_orphan(tmp_path):
    """\\cite{Missing2020} but Missing2020 NOT in refs.bib → R2-bis flagged."""
    tex = r"""
Some claim with citation \cite{Missing2020}.
Another \citep{ExistingRef}.
"""
    bib = "@article{ExistingRef, title={X}}\n"
    rc, stdout, _ = run_audit(tex, bib, tmp_path)
    assert rc == 1, f"Expected exit 1 (orphan cite), got {rc}. stdout={stdout!r}"
    import json
    report = json.loads(stdout)
    orphan_findings = [f for f in report["findings"] if f["rule"] == "R2-bis" and "Missing2020" in f["match"]]
    assert len(orphan_findings) >= 1, f"Expected Missing2020 orphan: {report['findings']}"


def test_inline_comment_cite_stripped(tmp_path):
    """#50 F-Logic-H2: cite key inside inline % comment must NOT be counted.

    LaTeX rule: % outside math/verbatim, not preceded by backslash, comments to EOL.
    cite{wrong} in an inline comment is NOT a real citation.
    """
    tex = r"""
Real cite \cite{RealRef} % see also \cite{LeakedRef} for older version
"""
    bib = "@article{RealRef, title={X}}\n"
    rc, stdout, _ = run_audit(tex, bib, tmp_path)
    import json
    report = json.loads(stdout)
    # LeakedRef should NOT appear as missing-entry definite finding (it's in a comment)
    missing = [f for f in report["findings"] if f["rule"] == "R2-bis" and f["severity"] == "definite"]
    assert not any("LeakedRef" in f["match"] for f in missing), \
        f"H2 regression: comment cite leaked as missing entry: {missing}"


def test_biblatex_cite_commands_recognized(tmp_path):
    """#50 M6: biblatex \\footcite, \\parencite, \\textcite must be recognized as cites."""
    tex = r"""
Standard \cite{A}. Biblatex \footcite{B} and \parencite{C} and \textcite{D}.
\nocite{E} and \autocite{F}.
"""
    bib = (
        "@article{A, title={X}}\n"
        "@article{B, title={X}}\n"
        "@article{C, title={X}}\n"
        "@article{D, title={X}}\n"
        "@article{E, title={X}}\n"
        "@article{F, title={X}}\n"
    )
    rc, stdout, _ = run_audit(tex, bib, tmp_path)
    assert rc == 0, f"M6 regression: biblatex cite commands not recognized. stdout={stdout}"


def test_digit_suffix_label_leak(tmp_path):
    """#50 M4: identifiers with digits (e.g. mse_l1, exact_var_2) must match label leak."""
    tex = r"""
\citet[Theorem~\texttt{exact\_var\_2}]{Smith2020}
"""
    bib = "@article{Smith2020, title={X}}\n"
    rc, stdout, _ = run_audit(tex, bib, tmp_path)
    assert rc == 1, f"M4 regression: digit-suffix identifier not detected. stdout={stdout}"
    import json
    report = json.loads(stdout)
    r2 = [f for f in report["findings"] if f["rule"] == "R2"]
    assert any("exact" in f["match"] for f in r2), \
        f"M4 regression: exact_var_2 not flagged: {r2}"


def test_split_cite_keys_with_spaces(tmp_path):
    """#50 F4: missing cite key in \\cite{A, Missing} must report correct line, not 0."""
    tex = r"""
Line 1.
Line 2.
Real cite \cite{A, Missing} here on line 4.
"""
    bib = "@article{A, title={X}}\n"
    rc, stdout, _ = run_audit(tex, bib, tmp_path)
    import json
    report = json.loads(stdout)
    missing_finding = [f for f in report["findings"] if "Missing" in f.get("match", "")]
    assert missing_finding, f"Missing not detected: {report['findings']}"
    # F4 fix: line should be the actual line (≥1), not 0
    assert missing_finding[0]["line"] > 0, \
        f"F4 regression: Missing key line lookup returned 0 (should strip whitespace): {missing_finding}"
