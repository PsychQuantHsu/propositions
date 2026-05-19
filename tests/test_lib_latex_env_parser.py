"""Tests for ``scripts/_lib/latex_env_parser.py`` (#115 M-5 dedup module).

This module is the single source of truth previously inline-copied across:
- ``scripts/audit-theorem-boundaries.py`` (#98)
- ``scripts/validate-propositions.py`` R9 section (#100)

These tests lock the dedup contract and exercise the shared API surface
(``parse_envs``, ``parse_location``, ``normalize_containing_block``,
``build_associated``).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _lib import latex_env_parser as parser  # noqa: E402


# ---------- public API surface ----------


def test_module_exports_required_names():
    """#115 M-5 — locks the public surface both audit-script + validator R9
    depend on. Removing or renaming any of these is a breaking change.
    """
    required = [
        "ENV_TYPES",
        "BEGIN_RE",
        "END_RE",
        "LABEL_RE",
        "PROOF_TARGET_RE",
        "LOC_RE",
        "TYPE_PREFIX_RE",
        "parse_envs",
        "normalize_containing_block",
        "parse_location",
        "build_associated",
    ]
    for name in required:
        assert hasattr(parser, name), f"missing required symbol: {name}"


def test_env_types_is_8_type_tuple():
    """ENV_TYPES must cover 7 declared envs + proof = 8 total."""
    assert len(parser.ENV_TYPES) == 8
    assert set(parser.ENV_TYPES) == {
        "theorem", "lemma", "proposition", "corollary",
        "definition", "remark", "conjecture",
        "proof",
    }


def test_type_prefix_re_covers_7_envs_dp1():
    """#115 M-5 DP1 — TYPE_PREFIX_RE unified to 7-type superset (was 4-type
    in audit-script pre-dedup; 7-type matches validator R9's prior form).

    Verifies forward-compat: ``definition:`` / ``remark:`` / ``conjecture:``
    prefixes strip cleanly even though no current prop uses them.
    """
    for typ in ("theorem", "lemma", "proposition", "corollary",
                "proof", "definition", "remark", "conjecture"):
        assert parser.TYPE_PREFIX_RE.match(f"{typ}:foo"), (
            f"TYPE_PREFIX_RE must match leading '{typ}:'"
        )
    # Non-env prefix must NOT match
    assert not parser.TYPE_PREFIX_RE.match("sec:foo"), (
        "sec: must NOT match (it's a section anchor, not an env prefix)"
    )


# ---------- parse_location ----------


def test_parse_location_basic():
    assert parser.parse_location("main.tex:L100") == (100, 100)
    assert parser.parse_location("main.tex:L100-L120") == (100, 120)


def test_parse_location_rejects_inverted_range():
    """#100 Path B / #115 M-2 — end < start returns None."""
    assert parser.parse_location("main.tex:L20-L10") is None


def test_parse_location_rejects_zero_base():
    """#100 Path B / #115 M-2 — start < 1 returns None."""
    assert parser.parse_location("main.tex:L0") is None
    assert parser.parse_location("main.tex:L0-L5") is None


def test_parse_location_rejects_garbage():
    assert parser.parse_location("garbage") is None
    assert parser.parse_location("") is None
    assert parser.parse_location(None) is None  # type: ignore[arg-type]


# ---------- normalize_containing_block ----------


def test_normalize_strips_type_prefix():
    """#113 type-prefix stripping (pre-canonicalization legacy support)."""
    assert parser.normalize_containing_block("theorem:thm:eta-s") == "thm:eta-s"
    assert parser.normalize_containing_block("lemma:lem:foo") == "lem:foo"
    assert parser.normalize_containing_block("proof:p:bar") == "p:bar"
    # DP1 7-type coverage
    assert parser.normalize_containing_block("definition:def:foo") == "def:foo"
    assert parser.normalize_containing_block("remark:rem:foo") == "rem:foo"
    assert parser.normalize_containing_block("conjecture:conj:foo") == "conj:foo"


def test_normalize_strips_sub_path():
    """Sub-paths like /proof/step1 are stripped to the segment before /."""
    assert parser.normalize_containing_block(
        "theorem:thm:eta-s/proof/s1"
    ) == "thm:eta-s"
    assert parser.normalize_containing_block(
        "thm:gamma-g/proof/step2b"
    ) == "thm:gamma-g"


def test_normalize_pass_through_when_no_prefix():
    """Canonical post-#113 form is bare label."""
    assert parser.normalize_containing_block("thm:main") == "thm:main"
    assert parser.normalize_containing_block("lem:affine-bijection") == "lem:affine-bijection"


# ---------- PROOF_TARGET_RE ----------


def test_proof_target_re_single_ref():
    m = parser.PROOF_TARGET_RE.search(
        r"\begin{proof}[Proof of Theorem~\ref{thm:eta-s}]"
    )
    assert m and m.group(1) == "thm:eta-s"


def test_proof_target_re_captures_first_ref_not_last():
    """#100 Path B / #115 M-1 — non-greedy must capture FIRST ref in multi-ref
    proof title, not the last.
    """
    m = parser.PROOF_TARGET_RE.search(
        r"\begin{proof}[Proof of Theorem~\ref{thm:a}, using Lemma~\ref{lem:b}]"
    )
    assert m and m.group(1) == "thm:a"


# ---------- parse_envs ----------


def test_parse_envs_basic(capfd):
    tex = (
        "Intro\n"
        "\\begin{theorem}\\label{thm:foo}\n"
        "Statement\n"
        "\\end{theorem}\n"
        "\\begin{proof}[Proof of Theorem~\\ref{thm:foo}]\n"
        "Proof body\n"
        "\\end{proof}\n"
    )
    envs = parser.parse_envs(tex, warn_on_residue=False)
    # No stderr warning (matched)
    err = capfd.readouterr().err
    assert err == "", f"clean fixture should not warn: {err!r}"
    types = [e["type"] for e in envs]
    assert types == ["theorem", "proof"]
    assert envs[0]["label"] == "thm:foo"
    assert envs[1]["proof_target"] == "thm:foo"


def test_parse_envs_warns_on_unmatched_begin_default_true(capfd):
    """#115 M-4 — default warn_on_residue=True surfaces dangling begin."""
    tex = (
        "\\begin{theorem}\n"
        "\\label{thm:dangling}\n"
        "Body but no end\n"
    )
    envs = parser.parse_envs(tex)  # default warn_on_residue=True
    err = capfd.readouterr().err
    assert "unmatched" in err
    assert "theorem" in err
    # Non-blocking: function still returns (empty) inventory
    assert envs == []


def test_parse_envs_silent_when_warn_on_residue_false(capfd):
    """#115 M-4 — validator R9 opt-out keeps stderr clean."""
    tex = (
        "\\begin{theorem}\n"
        "\\label{thm:dangling}\n"
        "Body but no end\n"
    )
    envs = parser.parse_envs(tex, warn_on_residue=False)
    err = capfd.readouterr().err
    assert err == "", f"warn_on_residue=False should be silent; got: {err!r}"
    assert envs == []  # still drops residue from inventory


# ---------- build_associated ----------


def test_build_associated_explicit_binding():
    """Proof env with [Proof of Theorem~\\ref{thm:foo}] binds to thm:foo."""
    tex = (
        "\\begin{theorem}\\label{thm:foo}\nStatement\n\\end{theorem}\n"
        "\\begin{theorem}\\label{thm:bar}\nOther\n\\end{theorem}\n"
        "\\begin{proof}[Proof of Theorem~\\ref{thm:foo}]\nBody\n\\end{proof}\n"
    )
    envs = parser.parse_envs(tex, warn_on_residue=False)
    assoc = parser.build_associated(envs)
    # thm:foo gets its statement + the explicit-bound proof
    assert len(assoc["thm:foo"]) == 2
    types = [e["type"] for e in assoc["thm:foo"]]
    assert types == ["theorem", "proof"]
    # thm:bar gets only its statement (no proof bound)
    assert len(assoc["thm:bar"]) == 1


def test_build_associated_proximity_fallback():
    """Proof without explicit binding attaches to most-recent statement
    within 12 lines.
    """
    tex_lines = [
        "\\begin{theorem}\\label{thm:foo}",
        "Statement L2",
        "\\end{theorem}",
        "",  # gap
        "\\begin{proof}",  # no [Proof of...] argument
        "Body L6",
        "\\end{proof}",
    ]
    tex = "\n".join(tex_lines) + "\n"
    envs = parser.parse_envs(tex, warn_on_residue=False)
    assoc = parser.build_associated(envs)
    assert len(assoc["thm:foo"]) == 2  # statement + proximity-bound proof
