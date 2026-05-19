"""Tests for scripts/refresh-prop-locations.py.

Covers the silent-failure regressions in the proposition location-refresh
tool (issue #123):

  - markup-heavy prop.text whose first chars span a source-wrap boundary
  - coordinate-system drift between the search space and the line map
    (the original fix's BLOCKING bug — verified here with a >150-line fixture)
  - empty prop.text slipping past the containment check
  - anchor failures surfacing loudly + gating the exit code
  - multi-line props getting a correct L{start}-L{end} range
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "refresh-prop-locations.py"


def _write_pair(tmp_path: Path, props: list[dict], tex: str) -> tuple[Path, Path]:
    """Materialize a JSONL + tex pair under tmp_path. `props` may be 1+ dicts."""
    jsonl = tmp_path / "props.jsonl"
    tex_path = tmp_path / "main.tex"
    with jsonl.open("w") as fp:
        for p in props:
            fp.write(json.dumps(p, ensure_ascii=False) + "\n")
    tex_path.write_text(tex)
    return jsonl, tex_path


def _run(jsonl: Path, tex: Path, dry_run: bool = False):
    cmd = [sys.executable, str(SCRIPT), "--jsonl", str(jsonl), "--tex", str(tex)]
    if dry_run:
        cmd.append("--dry-run")
    return subprocess.run(cmd, capture_output=True, text=True)


def _prop(suffix: str, text: str, location: str) -> dict:
    return {
        "id": f"01910b9c-d4f0-7000-8000-0000000000{suffix}",
        "text": text,
        "location": location,
    }


def _read_props(jsonl: Path) -> list[dict]:
    return [json.loads(ln) for ln in jsonl.read_text().splitlines() if ln.strip()]


# --------------------------------------------------------------------------
# 1. Plain-text prop, no markup, no wrap
# --------------------------------------------------------------------------
def test_plain_prop_location_refresh_after_shift(tmp_path: Path):
    """Plain-text prop whose tex location shifts → location field updates."""
    prop_text = "The cat sat on the mat without further explanation."
    prop = _prop("01", prop_text, "main.tex:L3")
    tex = "\n" * 10 + prop_text + "\n"  # prop content lands on L11
    jsonl, tex_path = _write_pair(tmp_path, [prop], tex)

    result = _run(jsonl, tex_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert _read_props(jsonl)[0]["location"] == "main.tex:L11", (
        f"got {_read_props(jsonl)[0]['location']!r}; stderr: {result.stderr}"
    )


# --------------------------------------------------------------------------
# 2. Markup-heavy prop with source-wrap (the original #123 bug-of-record)
# --------------------------------------------------------------------------
def test_markup_heavy_source_wrap_regression(tmp_path: Path):
    """Markup-heavy prop whose first 60 chars span a tex source-wrap boundary.

    The pre-#123 raw-substring anchor searched `prop_text[:60]` line-by-line;
    that slice can't appear on any single line when the source wraps inside it.
    The normalized algorithm collapses the wrap and locates it correctly.
    """
    prop_text = (
        "When Theorem~\\ref{thm:main} is invoked, we further assume that "
        "all conditions hold."
    )
    tex_lines = [
        "Some opening paragraph.",                              # L1
        "",                                                     # L2
        "Another paragraph.",                                   # L3
        "",                                                     # L4
        "When Theorem~\\ref{thm:main} is invoked, we further",  # L5
        "assume that all conditions hold.",                     # L6
        "",                                                     # L7
        "Trailing text.",                                       # L8
    ]
    tex = "\n".join(tex_lines) + "\n"
    prop = _prop("02", prop_text, "main.tex:L99")  # stale location
    jsonl, tex_path = _write_pair(tmp_path, [prop], tex)

    result = _run(jsonl, tex_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    new_loc = _read_props(jsonl)[0]["location"]
    assert new_loc == "main.tex:L5-L6", (
        f"expected L5-L6 (the prop wraps across both lines); "
        f"got {new_loc!r}; stderr: {result.stderr}"
    )
    assert "anchor failed: 0" in result.stderr, result.stderr


# --------------------------------------------------------------------------
# 3. R1 fail — prop text genuinely absent from tex
# --------------------------------------------------------------------------
def test_r1_fail_text_absent_from_tex(tmp_path: Path):
    """Prop whose normalized text doesn't appear in tex → exit 1, match_failed."""
    prop = _prop("03", "This sentence does not appear anywhere in the tex.", "main.tex:L1")
    tex = "Completely unrelated content.\nNothing matches the prop.\n"
    jsonl, tex_path = _write_pair(tmp_path, [prop], tex)

    result = _run(jsonl, tex_path)
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "R1 match failed: 1" in result.stderr, result.stderr
    assert "anchor failed: 0" in result.stderr, result.stderr


# --------------------------------------------------------------------------
# 4. Coordinate-drift regression — the original fix's BLOCKING bug (#123 F1)
# --------------------------------------------------------------------------
def test_coordinate_drift_long_fixture(tmp_path: Path):
    """A >150-line fixture pinning exact line numbers at varying depths.

    The first #123 fix searched in WHOLE-TEXT normalized coordinates but
    accumulated the line map PER-LINE. `normalize_for_match` collapses
    cross-line whitespace, so the two coordinate systems drifted ~1 char/line —
    a prop ~150 lines deep was mis-located by several lines. An 8-line fixture
    is too short to surface that. This fixture is deliberately long and mixes
    blank lines, comment lines, and a source-wrapped prop so any reintroduced
    drift shifts the deep-prop assertions.
    """
    lines: list[str] = []
    for i in range(9):
        lines.append(f"Filler prose paragraph line {i} with realistic word count here.")
    lines.append("")                                              # L10 blank
    lines.append("PROPALPHA is a uniquely identifiable shallow sentence in the file.")  # L11
    lines.append("")                                              # L12
    lines.append("% a latex comment line that normalization strips entirely")  # L13
    for i in range(60):
        lines.append(f"More filler content on padding line {i} keeping the file long.")
    # next index: L14 .. L73 are padding (60 lines)
    lines.append("")                                              # L74 blank
    lines.append("PROPBETA opens the sentence on this physical line and then it")  # L75
    lines.append("continues onto the following physical line before it finally ends.")  # L76
    lines.append("")                                              # L77
    for i in range(70):
        lines.append(f"Yet more padding filler line {i} pushing the depth down.")
    # L78 .. L147 padding (70 lines)
    lines.append("")                                              # L148 blank
    lines.append("PROPGAMMA sits very deep in the file at a known fixed line number.")  # L149
    lines.append("")                                              # L150
    tex = "\n".join(lines) + "\n"

    # Sanity: confirm the marker line numbers (1-indexed) match expectations.
    assert lines[10].startswith("PROPALPHA"), lines[10]
    assert lines[74].startswith("PROPBETA"), lines[74]
    assert lines[148].startswith("PROPGAMMA"), lines[148]

    props = [
        _prop("11", "PROPALPHA is a uniquely identifiable shallow sentence in the file.",
              "main.tex:L1"),
        _prop("12", "PROPBETA opens the sentence on this physical line and then it "
                    "continues onto the following physical line before it finally ends.",
              "main.tex:L1"),
        _prop("13", "PROPGAMMA sits very deep in the file at a known fixed line number.",
              "main.tex:L1"),
    ]
    jsonl, tex_path = _write_pair(tmp_path, props, tex)

    result = _run(jsonl, tex_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    by_id = {p["id"][-2:]: p["location"] for p in _read_props(jsonl)}
    assert by_id["11"] == "main.tex:L11", f"PROPALPHA: {by_id['11']!r}\n{result.stderr}"
    # PROPBETA wraps L75-L76 — exact multi-line span, no coordinate drift
    assert by_id["12"] == "main.tex:L75-L76", f"PROPBETA: {by_id['12']!r}\n{result.stderr}"
    assert by_id["13"] == "main.tex:L149", f"PROPGAMMA: {by_id['13']!r}\n{result.stderr}"


# --------------------------------------------------------------------------
# 5. Empty / whitespace-only prop.text (#123 F3)
# --------------------------------------------------------------------------
def test_empty_prop_text_is_match_failed(tmp_path: Path):
    """Empty prop.text must be match_failed, not silently relocated to L1.

    `"" in anystring` is always True, so an empty prop would slip past a naive
    containment check and be confidently rewritten.
    """
    prop = _prop("05", "", "main.tex:L42")
    tex = "Some real content here.\nMore content.\n"
    jsonl, tex_path = _write_pair(tmp_path, [prop], tex)

    result = _run(jsonl, tex_path)
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "R1 match failed: 1" in result.stderr, result.stderr
    # location must be left untouched, NOT rewritten to L1
    assert _read_props(jsonl)[0]["location"] == "main.tex:L42", (
        f"empty prop's location was modified: {_read_props(jsonl)[0]['location']!r}"
    )


# --------------------------------------------------------------------------
# 6. Label-prefixed prop anchors under the windowed locator
#    (#137 inverts the pre-#137 per-line anchor_failed limitation)
# --------------------------------------------------------------------------
def test_label_prefixed_prop_anchors(tmp_path: Path):
    """A prop whose second tex line starts with a ``Word:`` label is correctly
    anchored by the windowed locator (#137).

    The label-strip regex in `normalize_for_match` is anchored at start-of-string.
    The pre-#137 per-line search space normalized each line on its own, so
    ``Marker:`` at the start of L4 got stripped per-line — the prop (transcribed
    verbatim, still containing ``Marker:``) then missed the per-line search
    space and counted as ``anchor_failed``. The windowed locator normalizes each
    candidate window as one multi-line string: ``Marker:`` sits mid-window, the
    start-anchored strip does not fire, and the prop anchors to its real span.
    """
    prop_text = "This first line has no ending period Marker: and the rest here."
    tex_lines = [
        "Opening paragraph one.",                          # L1
        "",                                                # L2
        "This first line has no ending period",            # L3
        "Marker: and the rest here.",                      # L4
        "",                                                # L5
        "Closing paragraph.",                              # L6
    ]
    tex = "\n".join(tex_lines) + "\n"
    prop = _prop("06", prop_text, "main.tex:L3")
    jsonl, tex_path = _write_pair(tmp_path, [prop], tex)

    result = _run(jsonl, tex_path)
    assert result.returncode == 0, (
        f"label-prefixed prop must anchor cleanly (exit 0); got {result.returncode}; "
        f"stderr: {result.stderr}"
    )
    assert "anchor failed: 0" in result.stderr, result.stderr
    assert "R1 match failed: 0" in result.stderr, result.stderr
    assert _read_props(jsonl)[0]["location"] == "main.tex:L3-L4", (
        f"prop wraps L3-L4; got {_read_props(jsonl)[0]['location']!r}; "
        f"stderr: {result.stderr}"
    )


# --------------------------------------------------------------------------
# 7. claimed_start disambiguation when the prop text appears twice (#123 F4)
# --------------------------------------------------------------------------
def test_claimed_start_disambiguates_duplicate_text(tmp_path: Path):
    """When the prop's text occurs twice, the occurrence nearest claimed_start
    wins. Also exercises a small claimed_start (L0-adjacent) being honored as a
    real anchor rather than treated as absent."""
    dup = "Hence the result follows immediately."
    tex_lines = [dup] + [""] * 0  # placeholder; build precisely below
    tex_lines = [
        dup,            # L1
        "Padding.",     # L2
        "Padding.",     # L3
        dup,            # L4
        "Padding.",     # L5
    ]
    tex = "\n".join(tex_lines) + "\n"

    # claimed at L4 → should resolve to L4 (nearer copy), not L1
    prop = _prop("07", dup, "main.tex:L4")
    jsonl, tex_path = _write_pair(tmp_path, [prop], tex)
    result = _run(jsonl, tex_path)
    assert result.returncode == 0, result.stderr
    assert _read_props(jsonl)[0]["location"] == "main.tex:L4", (
        f"claimed_start=L4 should pick the L4 copy; "
        f"got {_read_props(jsonl)[0]['location']!r}; stderr: {result.stderr}"
    )

    # claimed at L1 → should resolve to L1 (nearer copy)
    prop2 = _prop("08", dup, "main.tex:L1")
    jsonl2, tex_path2 = _write_pair(tmp_path, [prop2], tex)
    result2 = _run(jsonl2, tex_path2)
    assert result2.returncode == 0, result2.stderr
    assert _read_props(jsonl2)[0]["location"] == "main.tex:L1", (
        f"claimed_start=L1 should pick the L1 copy; "
        f"got {_read_props(jsonl2)[0]['location']!r}; stderr: {result2.stderr}"
    )


# --------------------------------------------------------------------------
# 8. emph macro spanning a source-wrap boundary anchors under the windowed
#    locator (#137 inverts the pre-#137 per-line anchor_failed limitation)
# --------------------------------------------------------------------------
def test_emph_macro_spanning_line_anchors(tmp_path: Path):
    """A `\\emph{...}` whose braces span a tex source-wrap boundary anchors
    correctly under the windowed locator (#137).

    This was the real-world cause of the residual anchor failures on `main.tex`.
    The pre-#137 per-line search space saw `\\emph{sensitivity` (no closing
    brace) on L3 and `function}` on L4, could not strip the macro per-line, and
    counted the prop as `anchor_failed`. The windowed locator normalizes each
    candidate window as one multi-line string — the `\\emph{...}` regex's
    `[^}]*` matches across the newline inside the window — so the macro strips
    cleanly and the prop resolves to its real L3-L4 span.
    """
    prop_text = "the \\emph{sensitivity function} is defined on the domain."
    tex_lines = [
        "Opening paragraph one here.",              # L1
        "",                                         # L2
        "We now introduce the \\emph{sensitivity",  # L3
        "function} is defined on the domain.",      # L4
        "",                                         # L5
        "Closing paragraph.",                       # L6
    ]
    tex = "\n".join(tex_lines) + "\n"
    prop = _prop("09", prop_text, "main.tex:L3")
    jsonl, tex_path = _write_pair(tmp_path, [prop], tex)

    result = _run(jsonl, tex_path)
    assert result.returncode == 0, (
        f"emph spanning a wrap must anchor cleanly (exit 0); got {result.returncode}; "
        f"stderr: {result.stderr}"
    )
    assert "anchor failed: 0" in result.stderr, result.stderr
    assert "R1 match failed: 0" in result.stderr, result.stderr
    assert _read_props(jsonl)[0]["location"] == "main.tex:L3-L4", (
        f"prop wraps L3-L4; got {_read_props(jsonl)[0]['location']!r}; "
        f"stderr: {result.stderr}"
    )


# --------------------------------------------------------------------------
# 9. Display-math block: a prop spanning a \[ ... \] block locates correctly
#    (the bare \[ / \] delimiter lines normalize to empty and are skipped)
# --------------------------------------------------------------------------
def test_display_math_block_prop_locates(tmp_path: Path):
    """A prop spanning a `\\[ ... \\]` display-math block resolves to the real
    span. The bare `\\[` / `\\]` delimiter lines normalize to empty and are
    skipped by build_line_search_space, so they neither break the match nor
    inflate the line range."""
    prop_text = "The mapping satisfies P_x(y) = F(u(y) - v(x)) for all admissible pairs."
    tex_lines = [
        "Intro line.",                                  # L1
        "",                                             # L2
        "The mapping satisfies",                        # L3
        "\\[",                                          # L4 — normalizes to ""
        "  P_x(y) = F(u(y) - v(x))",                    # L5
        "\\]",                                          # L6 — normalizes to ""
        "for all admissible pairs.",                    # L7
        "",                                             # L8
        "Done.",                                        # L9
    ]
    tex = "\n".join(tex_lines) + "\n"
    prop = _prop("0a", prop_text, "main.tex:L1")
    jsonl, tex_path = _write_pair(tmp_path, [prop], tex)

    result = _run(jsonl, tex_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    new_loc = _read_props(jsonl)[0]["location"]
    # span runs from the first content line (L3) to the last (L7)
    assert new_loc == "main.tex:L3-L7", (
        f"expected L3-L7 across the display-math block; "
        f"got {new_loc!r}; stderr: {result.stderr}"
    )
    assert "anchor failed: 0" in result.stderr, result.stderr


# --------------------------------------------------------------------------
# 10. F-DA-1 regression — a prior line ending in ". " must not produce a
#     spurious earlier anchor (the windowed locator does no head-check)
# --------------------------------------------------------------------------
def test_fda1_prior_sentence_boundary_no_spurious_anchor(tmp_path: Path):
    """#133 F-DA-1: a normalized head-check produced a spurious *earlier* start
    line when the preceding line ended with a ``. `` sentence boundary. The
    windowed locator matches the whole prop against each window — no head-check,
    no prefix slice — so a prior ``. `` line cannot pull the anchor earlier.
    """
    tex_lines = [
        "An earlier sentence ends here. ",                                     # L1
        "The target proposition begins on this line and is uniquely worded.",  # L2
        "A trailing sentence follows afterward.",                              # L3
    ]
    tex = "\n".join(tex_lines) + "\n"
    prop = _prop(
        "14",
        "The target proposition begins on this line and is uniquely worded.",
        "main.tex:L99",  # stale
    )
    jsonl, tex_path = _write_pair(tmp_path, [prop], tex)

    result = _run(jsonl, tex_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert _read_props(jsonl)[0]["location"] == "main.tex:L2", (
        f"must anchor to L2, never a spurious earlier line; "
        f"got {_read_props(jsonl)[0]['location']!r}; stderr: {result.stderr}"
    )


# --------------------------------------------------------------------------
# 11. F-DA-2 regression — a shared \ref{} prefix on two lines must not cause a
#     truncated-prefix collision (the windowed locator matches whole-prop text)
# --------------------------------------------------------------------------
def test_fda2_shared_ref_prefix_no_collision(tmp_path: Path):
    """#133 F-DA-2: a raw-prefix matcher accepted a truncated prefix that
    collided with an unrelated line sharing the same ``\\ref{}`` opening. The
    windowed locator matches the whole normalized prop, so a shared prefix on
    another line cannot capture the anchor — only the line carrying the full
    matching text wins.
    """
    tex_lines = [
        "Theorem~\\ref{thm:key} establishes the base case directly.",            # L1
        "",                                                                      # L2
        "Theorem~\\ref{thm:key} establishes the inductive step in full here.",    # L3
        "",                                                                      # L4
        "Closing remark.",                                                       # L5
    ]
    tex = "\n".join(tex_lines) + "\n"
    prop = _prop(
        "15",
        "Theorem~\\ref{thm:key} establishes the inductive step in full here.",
        "main.tex:L99",  # stale
    )
    jsonl, tex_path = _write_pair(tmp_path, [prop], tex)

    result = _run(jsonl, tex_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert _read_props(jsonl)[0]["location"] == "main.tex:L3", (
        f"shared \\ref prefix must not collide; expected L3; "
        f"got {_read_props(jsonl)[0]['location']!r}; stderr: {result.stderr}"
    )


# --------------------------------------------------------------------------
# 12. F-DA-3 regression — a prop deep after many blank/comment lines must
#     anchor to the exact content line, never a blank line (no bisect, no
#     non-monotonic offset map)
# --------------------------------------------------------------------------
def test_fda3_deep_prop_anchors_to_content_line(tmp_path: Path):
    """#133 F-DA-3: a non-monotonic ``prefix_lens`` made ``bisect`` map a match
    to a blank line. The windowed locator builds no offset map and never
    bisects — it anchors to the exact content line regardless of how many
    blank / comment lines precede it.
    """
    lines = ["Opening line."]                                  # L1
    for i in range(19):                                        # L2..L20
        lines.append("" if i % 2 == 0 else f"% latex comment line {i}")
    lines.append(
        "PROPDELTA is the uniquely worded target proposition sitting deep here."
    )                                                          # L21
    lines.append("")                                           # L22
    tex = "\n".join(lines) + "\n"
    assert lines[20].startswith("PROPDELTA"), lines[20]  # sanity: 1-indexed L21

    prop = _prop(
        "16",
        "PROPDELTA is the uniquely worded target proposition sitting deep here.",
        "main.tex:L1",  # stale
    )
    jsonl, tex_path = _write_pair(tmp_path, [prop], tex)

    result = _run(jsonl, tex_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert _read_props(jsonl)[0]["location"] == "main.tex:L21", (
        f"deep prop must anchor to the exact content line L21, never a blank; "
        f"got {_read_props(jsonl)[0]['location']!r}; stderr: {result.stderr}"
    )
