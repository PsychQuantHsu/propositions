"""Tests for scripts/audit-symbols.py (Rule R1 detector).

Rule R1: working-file path leak in \\texttt{...}
- definite: analysis/X.py, manuscript/docs/Y.md, note (XXX).tex
- likely: other .tex or .sh in \\texttt{}
- suspicious: other extensions
- white-list: refs.bib (any .bib), comments (lines starting with %)
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "audit-symbols.py"


def run_audit(tex_content: str, tmp_path: Path) -> tuple[int, str, str]:
    """Write tex_content to tmp_path/main.tex, run audit-symbols.py, return (rc, stdout, stderr)."""
    manuscript_root = tmp_path / "manuscript"
    manuscript_root.mkdir()
    (manuscript_root / "main.tex").write_text(tex_content)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--manuscript-root", str(manuscript_root), "--report-format", "json"],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_baseline_findings(tmp_path):
    """Reproduce R1-detectable baseline findings + line 1264 violation.

    R1 catches:
    - analysis/verify_eta_fs.py + companion .md (2 inner \\texttt in one sentence)
    - note (Hsu 2024-02).tex × 3 (Q1/Q2/Q3 working note refs)
    - manuscript/docs/note-2024-02-audit.md (concurrent commit f52d8b0)
    = 6 R1 findings total.

    main_thm_ess × 2 are R2 territory (label leak in citation), tested separately.
    """
    tex = r"""
\begin{corollary}
Sympy substitution verifications for the extended formulas
are provided in \texttt{analysis/verify\_eta\_fs.py} (companion derivation
in \texttt{manuscript/docs/gc\_iverson\_eta\_fs.md}).
\end{corollary}

By the Pexider corollary \citep[\S 3.1]{Aczel1966}
(cf.\ \citet[Theorem~\texttt{main\_thm\_ess}]{DobleHsu2020}
which uses the same reduction).

Apply the theorem of \citet{DobleHsu2020} (\texttt{main\_thm\_ess}).

\item Q1 (working note, file
\texttt{note (Hsu 2024-02).tex}, line $\sim$173). The note ...

\item Q2 (working note, file
\texttt{note (Hsu 2024-02).tex}, line $\sim$269). The note ...

\item Q3 (working note, file
\texttt{note (Hsu 2024-02).tex}, line $\sim$265). The note ...

The audit available at \texttt{manuscript/docs/note-2024-02-audit.md}.
"""
    rc, stdout, _ = run_audit(tex, tmp_path)
    assert rc == 1, f"Expected exit 1 (findings present), got {rc}. stdout={stdout!r}"
    import json
    report = json.loads(stdout)
    definite_count = sum(1 for f in report["findings"] if f["severity"] == "definite")
    assert definite_count >= 6, f"Expected ≥6 R1 definite findings, got {definite_count}: {report['findings']}"


def test_post_fix_clean(tmp_path):
    """Post-fix manuscript (working-file refs removed) should produce zero findings."""
    tex = r"""
\begin{corollary}
Setting $f = \mathrm{id}_S$ in Theorem reduces the form.
\end{corollary}

By the Pexider corollary \citep[\S 3.1]{Aczel1966}
(cf.\ \citet[Theorem on $\eta = f(s)$ case]{DobleHsu2020}
which uses the same reduction).

Apply the theorem of \citet{DobleHsu2020}.
"""
    rc, stdout, _ = run_audit(tex, tmp_path)
    assert rc == 0, f"Expected exit 0 (clean), got {rc}. stdout={stdout!r}"


def test_white_list_bib(tmp_path):
    """\\bibliography{refs.bib} and \\cite{X} must NOT be flagged."""
    tex = r"""
Some content with citations \cite{Smith2020} and \citet{Jones2021}.
\bibliography{refs.bib}
"""
    rc, _, _ = run_audit(tex, tmp_path)
    assert rc == 0, f"Expected exit 0 (whitelist), got {rc}"


def test_comment_skipped(tmp_path):
    """\\texttt{...} on LaTeX comment lines (starting with %) must NOT be flagged."""
    tex = r"""
Normal content.
% \texttt{analysis/old_var.py}  — this is a comment, ignore
% TODO: remove \texttt{manuscript/docs/draft.md} reference later
"""
    rc, _, _ = run_audit(tex, tmp_path)
    assert rc == 0, f"Comments should be skipped, got rc={rc}"


def test_line_1264_pattern(tmp_path):
    """Specific regression test for the post-baseline-fix concurrent violation."""
    tex = r"""
The cross-reference audit available in
\texttt{manuscript/docs/note-2024-02-audit.md}.
"""
    rc, stdout, _ = run_audit(tex, tmp_path)
    assert rc == 1, f"Expected to flag manuscript/docs/*.md ref, got rc={rc}"
    import json
    report = json.loads(stdout)
    assert any("note-2024-02-audit.md" in f["match"] for f in report["findings"]), \
        f"Expected note-2024-02-audit.md in findings: {report['findings']}"


def test_prose_prefix_not_swallowed(tmp_path):
    """#50 F-Logic-H1: PATH_WITH_EXT_RE must NOT swallow preceding prose words.

    Old pattern `[\\w/.\\-\\\\() ]+\\.ext` matched 'See file foo.py' as one whole
    match. New anchored pattern must reject the prose prefix; only the path
    token (or nothing) should appear in match field.
    """
    tex = r"""
We refer to \texttt{See file foo.py} for details.
"""
    rc, stdout, _ = run_audit(tex, tmp_path)
    if rc == 1:
        import json
        report = json.loads(stdout)
        for f in report["findings"]:
            assert not f["match"].startswith("See "), \
                f"H1 regression: prose prefix in match: {f['match']!r}"


def test_biblatex_addbibresource_whitelisted(tmp_path):
    """#50 M2: biblatex \\addbibresource{X.bib} must whitelist X.bib in \\texttt{}."""
    tex = r"""
Bibliography via biblatex \addbibresource{refs.bib} command.
We cite something at \texttt{refs.bib} which should be whitelisted.
"""
    rc, stdout, _ = run_audit(tex, tmp_path)
    assert rc == 0, f"M2 regression: \\addbibresource biblatex form should whitelist refs.bib, got rc={rc}. stdout={stdout}"


def test_hyphen_subdir_paths_classified_definite(tmp_path):
    """#50 M1: classify_severity must catch hyphen + subdir Python paths as definite."""
    tex = r"""
See \texttt{analysis/sub/foo-bar.py} for details.
"""
    rc, stdout, _ = run_audit(tex, tmp_path)
    assert rc == 1, f"Expected exit 1 (definite finding), got {rc}"
    import json
    report = json.loads(stdout)
    definites = [f for f in report["findings"] if f["severity"] == "definite"]
    assert any("foo-bar.py" in f["match"] for f in definites), \
        f"M1 regression: hyphen/subdir path should be definite: {report['findings']}"


def test_bib_suffix_whitelist(tmp_path):
    """#50 L1: any .bib basename in \\texttt{} should be whitelisted (not just refs.bib)."""
    tex = r"""
We use \texttt{bibliography.bib} as the entry list.
"""
    rc, _, _ = run_audit(tex, tmp_path)
    assert rc == 0, f"L1 regression: .bib suffix whitelist failed, got rc={rc}"
