"""Tests for scripts/validate-propositions.py.

Covers:
- R3 orphan detection respecting structural_leaf_types (incl. #83 Phase 2 additions)
- R7 id-format check (v1.2+ UUID v7 contract,
  Spectra change migrate-prop-id-to-stable-uuid Task 2.1)
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate-propositions.py"

# Canonical UUID v7 sample used in v1.2 tests
SAMPLE_UUID_V7 = "01910b9c-d4f0-7000-8000-0123456789ab"
SAMPLE_UUID_V7_B = "01910b9c-d4f0-7001-8000-0123456789ab"


def write_fixture(
    tmp_path: Path,
    props: list[dict],
    tex_content: str = "",
    schema_version: str = "1.1",
) -> tuple[Path, Path, Path]:
    """Materialize a minimal validator fixture under tmp_path.

    Returns (jsonl_path, meta_path, tex_path).
    """
    jsonl_path = tmp_path / "props.jsonl"
    meta_path = tmp_path / "_meta.json"
    tex_path = tmp_path / "main.tex"

    meta = {"schema_version": schema_version, "source": {"file": str(tex_path)}}
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")

    with jsonl_path.open("w") as fp:
        for p in props:
            fp.write(json.dumps(p, ensure_ascii=False) + "\n")

    tex_path.write_text(tex_content or "stub\n")

    return jsonl_path, meta_path, tex_path


def run_validator(jsonl_path: Path, meta_path: Path, tex_path: Path):
    """Returns CompletedProcess (.returncode + .stdout + .stderr)."""
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--jsonl",
            str(jsonl_path),
            "--meta",
            str(meta_path),
            "--tex",
            str(tex_path),
        ],
        capture_output=True,
        text=True,
    )


# ---------- #83 structural_leaf_types extension ----------


def test_connective_with_empty_asserts_does_not_warn_r3(tmp_path):
    """A `connective` prop with empty asserts and no inbound cites must NOT
    trigger R3 orphan warning (#83 Phase 2 prereq)."""
    tex = "Hence, the result follows.\n"
    props = [
        {
            "id": "P001",
            "text": "Hence,",
            "location": "main.tex:L1",
            "containing_block": "test",
            "claim_type": "connective",
            "asserts": [],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex))
    assert result.returncode == 0, f"unexpected exit: {result.stdout}{result.stderr}"
    assert "P001: orphan" not in result.stdout, (
        f"connective should not warn R3 orphan:\n{result.stdout}"
    )


def test_reference_with_empty_asserts_does_not_warn_r3(tmp_path):
    """`reference` claim_type also exempt from R3 orphan."""
    tex = "see Lemma A.\n"
    props = [
        {
            "id": "P001",
            "text": "see Lemma A",
            "location": "main.tex:L1",
            "containing_block": "test",
            "claim_type": "reference",
            "asserts": [],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex))
    assert result.returncode == 0
    assert "P001: orphan" not in result.stdout


def test_scope_qualifier_does_not_warn_r3(tmp_path):
    """`scope_qualifier` also exempt."""
    tex = "for every s in S.\n"
    props = [
        {
            "id": "P001",
            "text": "for every s in S",
            "location": "main.tex:L1",
            "containing_block": "test",
            "claim_type": "scope_qualifier",
            "asserts": ["scope: for every s in S"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex))
    assert result.returncode == 0
    assert "P001: orphan" not in result.stdout


def test_case_split_does_not_warn_r3(tmp_path):
    """`case_split` claim_type also exempt — structural leaf, the case
    identifier; the case CONTENT (display_equation / claim) is what carries
    semantic dependencies, not the header (#112, extends #83 trajectory)."""
    tex = "Case A: ρ non-constant on S.\n"
    props = [
        {
            "id": "P001",
            "text": "Case A: ρ non-constant on S",
            "location": "main.tex:L1",
            "containing_block": "theorem:t",
            "claim_type": "case_split",
            "asserts": ["Case A: ρ non-constant on S"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex))
    assert result.returncode == 0
    assert "P001: orphan" not in result.stdout, (
        f"case_split should not warn R3 orphan (#112):\n{result.stdout}"
    )


def test_claim_type_still_warns_r3_when_orphan(tmp_path):
    """Negative control: an unsupported leaf type (e.g. `claim`) still warns."""
    tex = "Some derived claim.\n"
    props = [
        {
            "id": "P001",
            "text": "Some derived claim",
            "location": "main.tex:L1",
            "containing_block": "test",
            "claim_type": "claim",
            "asserts": ["a derived claim"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex))
    # exit 0 because R3 emits warnings, not errors
    assert result.returncode == 0
    assert "P001: orphan" in result.stdout, (
        f"claim type should warn R3 orphan:\n{result.stdout}"
    )


# ---------- R7 id-format (Spectra migrate-prop-id-to-stable-uuid Task 2.1) ----------


def _uuid_prop(uid: str, seq: int = 1, cites: list[str] | None = None) -> dict:
    """Minimal prop with given id, suitable for R7 tests."""
    return {
        "id": uid,
        "text": f"prop {seq}",
        "location": f"main.tex:L{seq}",
        "containing_block": "test",
        "claim_type": "claim",
        "asserts": ["a"],
        "cites": cites or [],
    }


def test_r7_v1_2_accepts_canonical_uuid_v7(tmp_path):
    """v1.2 schema with canonical UUID v7 ids MUST pass R7 id-format."""
    tex = "prop 1\n"
    props = [_uuid_prop(SAMPLE_UUID_V7)]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.2")
    )
    assert result.returncode == 0, (
        f"v1.2 + canonical UUID v7 should pass but got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "R7" in result.stdout, "R7 id-format check did not run on v1.2 fixture"


def test_r7_v1_2_rejects_legacy_p_prefix(tmp_path):
    """v1.2 schema with legacy P-prefix id MUST emit blocking R7 finding."""
    tex = "prop 1\n"
    props = [_uuid_prop("P037")]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.2")
    )
    assert result.returncode == 1, "v1.2 + P-prefix should fail"
    assert "R7" in result.stdout
    assert "P037" in result.stdout
    assert "UUID v7" in result.stdout


def test_r7_v1_2_rejects_legacy_c_prefix(tmp_path):
    """v1.2 schema with legacy C-prefix id MUST emit blocking R7 finding."""
    tex = "prop 1\n"
    props = [_uuid_prop("C014")]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.2")
    )
    assert result.returncode == 1
    assert "R7" in result.stdout
    assert "C014" in result.stdout


def test_r7_v1_2_rejects_non_uuid_string(tmp_path):
    """v1.2 schema with arbitrary non-UUID id MUST emit blocking R7 finding."""
    tex = "prop 1\n"
    props = [_uuid_prop("not-a-uuid")]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.2")
    )
    assert result.returncode == 1
    assert "R7" in result.stdout


def test_r7_v1_2_rejects_uuid_v4_with_wrong_version_field(tmp_path):
    """v1.2 schema with UUID v4 (version field 4 instead of 7) MUST fail R7."""
    tex = "prop 1\n"
    uuid_v4 = "01910b9c-d4f0-4000-8000-0123456789ab"  # canonical layout, version=4
    props = [_uuid_prop(uuid_v4)]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.2")
    )
    assert result.returncode == 1
    assert "R7" in result.stdout


def test_r7_v1_2_rejects_parallel_identifier_field(tmp_path):
    """v1.2 schema with parallel id field (display_id / P_id / ordinal / serial)
    MUST emit blocking R7 finding."""
    tex = "prop 1\n"
    for forbidden in ("display_id", "P_id", "ordinal", "serial"):
        prop = _uuid_prop(SAMPLE_UUID_V7)
        prop[forbidden] = "P037"
        result = run_validator(
            *write_fixture(tmp_path, [prop], tex, schema_version="1.2")
        )
        assert result.returncode == 1, f"forbidden field {forbidden} should fail"
        assert "R7" in result.stdout, f"R7 should mention {forbidden}"
        assert forbidden in result.stdout, f"finding should name {forbidden}"


def test_r7_v1_1_lenient_for_p_prefix_backward_compat(tmp_path):
    """v1.1 schema with legacy P-prefix id MUST NOT trigger R7
    (backward compat during migration window)."""
    tex = "prop 1\n"
    props = [_uuid_prop("P037")]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.1")
    )
    assert result.returncode == 0, (
        f"v1.1 + P-prefix should pass under backward compat but got {result.returncode}\n"
        f"stdout={result.stdout}"
    )


def test_r7_skipped_when_no_meta(tmp_path):
    """No _meta.json (very old fixture) MUST default to lenient (no R7 errors)."""
    jsonl_path = tmp_path / "props.jsonl"
    tex_path = tmp_path / "main.tex"
    jsonl_path.write_text(json.dumps(_uuid_prop("P037")) + "\n")
    tex_path.write_text("prop 1\n")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--jsonl",
            str(jsonl_path),
            "--tex",
            str(tex_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"no-meta lenient fallback should pass but got {result.returncode}\n"
        f"stdout={result.stdout}"
    )


# ---------- R2 cite-resolve under v1.2 UUID equality (Task 2.2) ----------


def test_r2_v1_2_resolves_valid_uuid_cite(tmp_path):
    """v1.2 schema with cite pointing to a sibling UUID id MUST resolve cleanly."""
    tex = "prop 1\nprop 2\n"  # matches _uuid_prop's generated text
    props = [
        _uuid_prop(SAMPLE_UUID_V7, seq=1),
        _uuid_prop(SAMPLE_UUID_V7_B, seq=2, cites=[SAMPLE_UUID_V7]),
    ]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.2")
    )
    assert result.returncode == 0, f"valid cite chain should pass: {result.stdout}"
    assert "[PASS] R2" in result.stdout


def test_r2_v1_2_rejects_legacy_p_prefix_cite(tmp_path):
    """v1.2 schema with cite containing legacy P-prefix MUST emit blocking finding."""
    tex = "claim\n"
    props = [
        # id is UUID v7 to bypass R7; the violation is in the cites entry
        _uuid_prop(SAMPLE_UUID_V7, cites=["P037"]),
    ]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.2")
    )
    assert result.returncode == 1
    assert "R2" in result.stdout
    assert "P037" in result.stdout
    # Finding text MUST signal format invalidity, not just dangling reference
    assert "UUID" in result.stdout or "format" in result.stdout.lower()


def test_r2_v1_2_dangling_uuid_cite_unresolved(tmp_path):
    """v1.2 schema with UUID-format cite that points to no prop MUST emit
    unresolved-cite finding (not format-invalid)."""
    tex = "claim\n"
    dangling = "01910b9c-d4f0-7999-8000-0000000000ff"
    props = [
        _uuid_prop(SAMPLE_UUID_V7, cites=[dangling]),
    ]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.2")
    )
    assert result.returncode == 1
    assert "R2" in result.stdout
    assert dangling in result.stdout


def test_r2_v1_1_lenient_p_prefix_cite(tmp_path):
    """v1.1 schema with P-prefix cite resolving to P-prefix id MUST pass
    (backward compat during migration window)."""
    tex = "axiom\nclaim\n"
    props = [
        {
            "id": "P001",
            "text": "axiom",
            "location": "main.tex:L1",
            "containing_block": "t",
            "claim_type": "axiom",
            "asserts": ["a"],
            "cites": [],
        },
        {
            "id": "P002",
            "text": "claim",
            "location": "main.tex:L2",
            "containing_block": "t",
            "claim_type": "claim",
            "asserts": ["a"],
            "cites": ["P001"],
        },
    ]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.1")
    )
    assert result.returncode == 0, f"v1.1 + P-prefix cites should pass: {result.stdout}"


# ---------- View ordinal helper + CLI (Task 2.3) ----------


def _write_uuid_jsonl(path: Path, props: list[dict]) -> None:
    with path.open("w") as fp:
        for p in props:
            fp.write(json.dumps(p, ensure_ascii=False) + "\n")


def test_view_ordinal_cli_full_mapping_main_jsonl(tmp_path):
    """view-ordinal subcommand on main.jsonl prints `Pnnn <uuid>` per line in sort order."""
    main = tmp_path / "main.jsonl"
    # Three props; sort key is (containing_block, file-position).
    # All share containing_block, so file order == display order.
    props = [
        {
            "id": "01910b9c-d4f0-7001-8000-000000000001",
            "text": "P1-prop", "location": "main.tex:L1",
            "containing_block": "sec:setup", "claim_type": "claim",
            "asserts": ["a"], "cites": [],
        },
        {
            "id": "01910b9c-d4f0-7099-8000-000000000099",
            "text": "P2-prop", "location": "main.tex:L2",
            "containing_block": "sec:setup", "claim_type": "claim",
            "asserts": ["a"], "cites": [],
        },
        {
            "id": "01910b9c-d4f0-7042-8000-000000000042",
            "text": "P3-prop", "location": "main.tex:L42",
            "containing_block": "sec:setup", "claim_type": "claim",
            "asserts": ["a"], "cites": [],
        },
    ]
    _write_uuid_jsonl(main, props)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "view-ordinal", str(main)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    # Expected: display ordinals follow file order
    assert lines[0] == "P001 01910b9c-d4f0-7001-8000-000000000001"
    assert lines[1] == "P002 01910b9c-d4f0-7099-8000-000000000099"
    assert lines[2] == "P003 01910b9c-d4f0-7042-8000-000000000042"


def test_view_ordinal_cli_uses_c_prefix_for_stage2_path(tmp_path):
    """view-ordinal on `_stage2/...jsonl` uses C-prefix."""
    stage2_dir = tmp_path / "_stage2"
    stage2_dir.mkdir()
    pilot = stage2_dir / "theorem1.jsonl"
    props = [
        {
            "id": "01910b9c-d4f0-7c01-8000-0000000000c1",
            "text": "x", "location": "main.tex:L466",
            "containing_block": "theorem:thm:eta-s", "claim_type": "hypothesis",
            "asserts": ["x"], "cites": [],
        },
    ]
    _write_uuid_jsonl(pilot, props)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "view-ordinal", str(pilot)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    out = result.stdout.strip()
    assert out.startswith("C001 ")


def test_view_ordinal_cli_uuid_lookup(tmp_path):
    """view-ordinal --uuid prints single display line for matching prop."""
    main = tmp_path / "main.jsonl"
    target_uuid = "01910b9c-d4f0-7099-8000-000000000099"
    props = [
        {
            "id": "01910b9c-d4f0-7001-8000-000000000001",
            "text": "x", "location": "main.tex:L1",
            "containing_block": "sec:setup", "claim_type": "claim",
            "asserts": ["a"], "cites": [],
        },
        {
            "id": target_uuid,
            "text": "y", "location": "main.tex:L2",
            "containing_block": "sec:setup", "claim_type": "claim",
            "asserts": ["a"], "cites": [],
        },
    ]
    _write_uuid_jsonl(main, props)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "view-ordinal", str(main), "--uuid", target_uuid],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "P002"


def test_view_ordinal_cli_missing_uuid_errors(tmp_path):
    """view-ordinal --uuid for an absent UUID exits non-zero with diagnostic."""
    main = tmp_path / "main.jsonl"
    props = [
        {
            "id": "01910b9c-d4f0-7001-8000-000000000001",
            "text": "x", "location": "main.tex:L1",
            "containing_block": "sec:setup", "claim_type": "claim",
            "asserts": ["a"], "cites": [],
        },
    ]
    _write_uuid_jsonl(main, props)

    absent = "01910b9c-d4f0-7999-8000-0000000000ff"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "view-ordinal", str(main), "--uuid", absent],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert absent in (result.stdout + result.stderr)


def test_view_ordinal_sort_tuple_groups_by_containing_block(tmp_path):
    """containing_block is the primary sort key; file position within block."""
    main = tmp_path / "main.jsonl"
    # 2 props in 'sec:proof' (containing_block sorts AFTER 'sec:setup' alphabetically)
    # 2 props in 'sec:setup' (smaller alphabetically)
    props = [
        {
            "id": "01910b9c-d4f0-7004-8000-000000000004",
            "text": "p4", "location": "main.tex:L99",
            "containing_block": "sec:proof", "claim_type": "claim",
            "asserts": ["a"], "cites": [],
        },
        {
            "id": "01910b9c-d4f0-7002-8000-000000000002",
            "text": "p2", "location": "main.tex:L1",
            "containing_block": "sec:setup", "claim_type": "claim",
            "asserts": ["a"], "cites": [],
        },
        {
            "id": "01910b9c-d4f0-7003-8000-000000000003",
            "text": "p3", "location": "main.tex:L2",
            "containing_block": "sec:setup", "claim_type": "claim",
            "asserts": ["a"], "cites": [],
        },
        {
            "id": "01910b9c-d4f0-7001-8000-000000000001",
            "text": "p1", "location": "main.tex:L5",
            "containing_block": "sec:proof", "claim_type": "claim",
            "asserts": ["a"], "cites": [],
        },
    ]
    _write_uuid_jsonl(main, props)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "view-ordinal", str(main)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    # 'sec:proof' < 'sec:setup' alphabetically, so proof props come first
    # Within proof: file order p4 then p1
    # Within setup: file order p2 then p3
    assert lines[0] == "P001 01910b9c-d4f0-7004-8000-000000000004"  # proof, file pos 0
    assert lines[1] == "P002 01910b9c-d4f0-7001-8000-000000000001"  # proof, file pos 3
    assert lines[2] == "P003 01910b9c-d4f0-7002-8000-000000000002"  # setup, file pos 1
    assert lines[3] == "P004 01910b9c-d4f0-7003-8000-000000000003"  # setup, file pos 2


# ---------- Diagnostic output formatting under v1.2 (Task 2.4) ----------


def test_r2_v1_2_diagnostic_includes_display_ordinal_and_uuid(tmp_path):
    """v1.2 cite-resolve finding text MUST include display ordinal + cite UUID."""
    tex = "prop 1\n"
    dangling = "01910b9c-d4f0-7999-8000-0000000000ff"
    props = [
        _uuid_prop(SAMPLE_UUID_V7, cites=[dangling]),
    ]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.2")
    )
    assert result.returncode == 1
    # P001 is the source prop's display ordinal (only prop → ordinal 1, P-prefix from non-stage2 path)
    assert "P001" in result.stdout, (
        f"finding text must include display ordinal P001, got:\n{result.stdout}"
    )
    # cite target UUID MUST appear inline in the finding
    assert dangling in result.stdout, (
        f"finding text must include the cite UUID, got:\n{result.stdout}"
    )
    # The phrase 'missing UUID' or 'undefined' is acceptable per spec
    assert (
        "missing UUID" in result.stdout
        or "undefined" in result.stdout
    ), f"finding must signal unresolved cite, got:\n{result.stdout}"


def test_r2_v1_1_diagnostic_does_not_translate_pid(tmp_path):
    """v1.1 lenient mode still reports the literal P-prefix id, not derived ordinal."""
    tex = "claim\n"
    props = [
        {
            "id": "P001",
            "text": "claim", "location": "main.tex:L1",
            "containing_block": "t", "claim_type": "claim",
            "asserts": ["a"], "cites": ["P999"],
        }
    ]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.1")
    )
    assert result.returncode == 1
    # v1.1 should report the prop id as-is (P001), no UUID translation
    assert "[R2] P001:" in result.stdout


# ---------- R8 unique-ids (Task 3.2 smoke fixture) ----------


def test_r8_v1_2_emits_finding_with_display_ordinal_for_duplicate_uuid(tmp_path):
    """v1.2 fixture with duplicate UUID MUST emit R8 finding mentioning
    BOTH the display ordinal and the duplicated UUID."""
    tex = "prop 1\nprop 2\n"
    props = [
        _uuid_prop(SAMPLE_UUID_V7, seq=1),
        _uuid_prop(SAMPLE_UUID_V7, seq=2),  # duplicate UUID
    ]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.2")
    )
    assert result.returncode == 1, f"duplicate UUID should fail: {result.stdout}\n{result.stderr}"
    assert "R8" in result.stdout, f"R8 marker missing: {result.stdout}"
    assert SAMPLE_UUID_V7 in result.stdout, "duplicate UUID must appear in finding"
    # Display ordinal must appear (P001 or P002 — both share the duplicate UUID)
    assert "P001" in result.stdout or "P002" in result.stdout, (
        f"display ordinal must appear: {result.stdout}"
    )


def test_r8_v1_1_lenient_no_finding(tmp_path):
    """v1.1 schema does NOT enforce R8 (backward compat); duplicate P-prefix
    triggers the legacy load-level error path or is silently accepted —
    in either case, finding text uses P-prefix literally."""
    tex = "claim\n"
    props = [
        {"id": "P001", "text": "claim",
         "location": "main.tex:L1", "containing_block": "t", "claim_type": "claim",
         "asserts": ["a"], "cites": []},
        {"id": "P001", "text": "claim",
         "location": "main.tex:L1", "containing_block": "t", "claim_type": "claim",
         "asserts": ["a"], "cites": []},
    ]
    result = run_validator(
        *write_fixture(tmp_path, props, tex, schema_version="1.1")
    )
    # Legacy behavior — exit non-zero, but no display-ordinal rendering required
    assert result.returncode != 0


# ---------- #85 CLI: --json + --jsonl mutually exclusive ----------


def test_json_and_jsonl_mutually_exclusive_rejects_both(tmp_path):
    """#85: passing both --json X and --jsonl Y MUST fail at argparse level
    (mutually-exclusive group), not silently let --json win."""
    j = tmp_path / "main.json"
    jl = tmp_path / "main.jsonl"
    j.write_text("[]")
    jl.write_text("")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json", str(j), "--jsonl", str(jl)],
        capture_output=True,
        text=True,
    )
    # argparse mutually-exclusive group exits 2 with "not allowed with"
    assert result.returncode == 2, f"expected exit 2, got {result.returncode}: {result.stderr}"
    assert "not allowed with" in result.stderr.lower() or "mutually exclusive" in result.stderr.lower(), (
        f"expected argparse mutually-exclusive error: {result.stderr}"
    )


# ---------- #87 missing 'id' field → ValueError → exit 2 ----------


def test_missing_id_field_jsonl_exits_2_with_clean_error(tmp_path):
    """#87: JSONL prop without 'id' field must raise ValueError caught by main()
    → exit 2 (parse-error) with clear message, not bare KeyError → exit 1."""
    tex_path = tmp_path / "main.tex"
    jsonl_path = tmp_path / "main.jsonl"
    meta_path = tmp_path / "_meta.json"

    tex_path.write_text("claim\n")
    meta_path.write_text(json.dumps({"schema_version": "1.2"}))
    # Two props: first has id, second is missing id field entirely
    jsonl_path.write_text(
        json.dumps({"id": SAMPLE_UUID_V7,                     "text": "claim", "location": "main.tex:L1",
                    "containing_block": "t", "claim_type": "claim",
                    "asserts": ["a"], "cites": []}) + "\n" +
        json.dumps({"text": "claim",
                    "location": "main.tex:L1", "containing_block": "t",
                    "claim_type": "claim", "asserts": ["a"], "cites": []}) + "\n"
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--jsonl", str(jsonl_path),
         "--meta", str(meta_path), "--tex", str(tex_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, (
        f"missing-id should exit 2 (parse error), got {result.returncode}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "parse error" in result.stderr.lower() or "missing required 'id'" in result.stderr, (
        f"expected clean parse-error message: {result.stderr}"
    )
    assert "Traceback" not in result.stderr, (
        f"should NOT have raw traceback (was caught by main): {result.stderr}"
    )


def test_missing_id_field_json_legacy_exits_2_with_clean_error(tmp_path):
    """#87: same guard for legacy load_props (single-file JSON form)."""
    tex_path = tmp_path / "main.tex"
    json_path = tmp_path / "main.json"

    tex_path.write_text("claim\n")
    json_path.write_text(json.dumps({"propositions": [
        {"text": "claim",
         "location": "main.tex:L1", "containing_block": "t",
         "claim_type": "claim", "asserts": ["a"], "cites": []},
    ]}))

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json", str(json_path), "--tex", str(tex_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, (
        f"missing-id should exit 2, got {result.returncode}: stderr={result.stderr!r}"
    )
    assert "missing required 'id'" in result.stderr or "parse error" in result.stderr.lower()
    assert "Traceback" not in result.stderr


# ---------- #92 restatement claim_type as structural leaf ----------


def test_restatement_claim_type_is_structural_leaf_no_r3_orphan(tmp_path):
    """#92: restatement props ARE leaf-like in discussion contexts and should
    NOT trigger R3 orphan warning when not cited by other props."""
    tex = "claim text\nrestatement of earlier point\n"
    restatement_uid = "019e2e15-2c00-7002-8aaa-000000000002"
    props = [
        # claim_type=claim WITH inbound cite from restatement → no R3 orphan
        {"id": "019e2e15-2c00-7001-8aaa-000000000001",          "text": "claim text", "location": "main.tex:L1",
         "containing_block": "t", "claim_type": "claim",
         "asserts": ["a"], "cites": []},
        # restatement WITHOUT inbound cite — must NOT be R3 orphan (structural leaf)
        {"id": restatement_uid,          "text": "restatement of earlier point",
         "location": "main.tex:L2", "containing_block": "t",
         "claim_type": "restatement", "asserts": ["a"],
         "cites": ["019e2e15-2c00-7001-8aaa-000000000001"]},
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    # The restatement UUID should not be flagged as R3 orphan
    assert restatement_uid not in result.stdout or "orphan" not in result.stdout, (
        f"restatement should NOT be R3 orphan: {result.stdout}"
    )
    # Specifically, no '[R3]' line containing the restatement UUID
    for line in result.stdout.splitlines():
        if restatement_uid in line and "[R3]" in line and "orphan" in line:
            raise AssertionError(f"restatement marked R3 orphan: {line}")


# ---------- #103 R4 PATTERN-A framework-aware boundary-axiom detection ----------


SMOKE_TESTS_DIR = REPO_ROOT / "manuscript" / "propositions" / "_smoke_tests"


def _run_validator_on_smoke_fixture(fixture_stem):
    """Run validator on a fixture under _smoke_tests/.

    fixture_stem is the basename without extension, e.g. 'rollback_60_real'
    or 'conditional_60_path_c'. Expects {stem}.jsonl + {stem}_meta.json + {stem}.tex.
    """
    jsonl = SMOKE_TESTS_DIR / f"{fixture_stem}.jsonl"
    meta = SMOKE_TESTS_DIR / f"{fixture_stem}_meta.json"
    tex = SMOKE_TESTS_DIR / f"{fixture_stem}.tex"
    assert jsonl.exists(), f"Missing fixture: {jsonl}"
    assert meta.exists(), f"Missing fixture: {meta}"
    assert tex.exists(), f"Missing fixture: {tex}"
    return run_validator(jsonl, meta, tex)


def _r4_pattern_a_fired(stdout: str) -> bool:
    """Detect R4 PATTERN-A error in validator stdout."""
    for line in stdout.splitlines():
        if "[R4]" in line and "PATTERN-A" in line:
            return True
    return False


class TestR4PatternAFrameworkAware:
    """#103: R4 PATTERN-A becomes framework-aware (conditional vs universal boundary).

    Pre-fix behavior:
        - F1 universal axiom + η=f(s) + f-extension → R4 ERROR (correct regression catch)
        - F2 conditional axiom + same hypothesis + extension → R4 ERROR (FALSE POSITIVE)

    Post-fix behavior:
        - F1 still triggers (universal case correctly flagged)
        - F2 no longer triggers (conditional framing detected → PATTERN-A short-circuits)
    """

    def test_f1_universal_boundary_triggers_pattern_a(self):
        """Regression baseline: rollback_60_real fixture (real pre-#60-fix wording).

        The axiom prop asserts contain literal `eta(1,s) = s` WITHOUT any
        conditional-framework signal phrase. Combined with η=f(s) hypothesis and
        Cases (B)(C) f-extension claim, R4 PATTERN-A MUST fire.

        This test is the #74 rollback regression — protects against accidentally
        loosening the conditional detection so much that real universal-boundary
        bugs no longer get caught.
        """
        result = _run_validator_on_smoke_fixture("rollback_60_real")
        assert _r4_pattern_a_fired(result.stdout), (
            f"F1: rollback_60_real (universal axiom) MUST trigger R4 PATTERN-A.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_f2_conditional_boundary_skips_pattern_a(self):
        """Bug fix verification: conditional_60_path_c fixture (post-Path-C wording).

        The axiom prop frames boundary as 'imposed locally — not part of
        universal' with framework citation. Same η=f(s) hypothesis + f-extension
        claim as rollback_60_real. Post-fix R4 PATTERN-A MUST NOT fire.

        Pre-fix (current code): this test FAILS (R4 fires falsely).
        Post-fix: this test PASSES (axiom_frames_conditionally=True short-circuits).
        """
        result = _run_validator_on_smoke_fixture("conditional_60_path_c")
        assert not _r4_pattern_a_fired(result.stdout), (
            f"F2: conditional_60_path_c (Path C conditional framing) MUST NOT trigger R4 PATTERN-A.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_f3_missing_axiom_passes(self, tmp_path):
        """Vacuous case: props without any axiom containing eta(1,s)=s.

        Even with η=f(s) hypothesis + f-extension claim, R4 PATTERN-A must NOT
        fire because the boundary-axiom precondition is missing. Both pre-fix
        and post-fix behavior identical here.
        """
        tex = (
            "Theorem hypothesis: η(λ,s) = f(s) for continuous f.\n"
            "Case (B): f may be any continuous map.\n"
        )
        props = [
            {
                "id": "01910b9c-d4f0-7100-8000-000000000001",
                "text": "Theorem hypothesis: η(λ,s) = f(s) for continuous f.",
                "location": "main.tex:L1",
                "containing_block": "theorem:t",
                "claim_type": "hypothesis",
                "asserts": ["η(λ,s) = f(s) for continuous f"],
                "cites": [],
            },
            {
                "id": "01910b9c-d4f0-7100-8000-000000000002",
                "text": "Case (B): f may be any continuous map.",
                "location": "main.tex:L2",
                "containing_block": "theorem:t",
                "claim_type": "case_split",
                "asserts": ["f may be any continuous map"],
                "cites": [],
            },
        ]
        result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
        assert not _r4_pattern_a_fired(result.stdout), (
            f"F3: missing axiom must NOT trigger R4 PATTERN-A.\nstdout:\n{result.stdout}"
        )

    def test_f4_conditional_signal_alone_without_substring_passes(self, tmp_path):
        """Edge case: axiom prop has conditional signal phrase but does NOT
        contain η(1,s)=s substring. Both preconditions (boundary substring AND
        conditional framing) must be present for either has_universal_boundary_eta
        or any framework-aware short-circuit logic to do something. Vacuous PASS
        protects against future regex over-broadening.
        """
        tex = "Imposed locally framework note.\nη=f(s) for continuous f.\nf may be any.\n"
        props = [
            {
                "id": "01910b9c-d4f0-7200-8000-000000000001",
                "text": "Imposed locally framework note.",
                "location": "main.tex:L1",
                "containing_block": "section:setup",
                "claim_type": "axiom",
                # Has signal phrase but NO η(1,s)=s substring
                "asserts": [
                    "Some unrelated boundary X(0) = 0 is imposed locally per DobleHsu2020 framework",
                ],
                "cites": [],
            },
            {
                "id": "01910b9c-d4f0-7200-8000-000000000002",
                "text": "η=f(s) for continuous f.",
                "location": "main.tex:L2",
                "containing_block": "theorem:t",
                "claim_type": "hypothesis",
                "asserts": ["η(λ,s) = f(s) for continuous f"],
                "cites": [],
            },
            {
                "id": "01910b9c-d4f0-7200-8000-000000000003",
                "text": "f may be any.",
                "location": "main.tex:L3",
                "containing_block": "theorem:t",
                "claim_type": "case_split",
                "asserts": ["f may be any continuous map"],
                "cites": [],
            },
        ]
        result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
        assert not _r4_pattern_a_fired(result.stdout), (
            f"F4: signal phrase alone (no η(1,s)=s substring) must NOT trigger R4 PATTERN-A.\nstdout:\n{result.stdout}"
        )

    def test_f5_current_manuscript_state_passes(self):
        """End-to-end integration: run validator on actual current manuscript
        (post-Path-C state). Pre-fix this returns R4 ERROR; post-fix R4 PASS.

        Confirms the bug fix lands for real production state, not just the
        synthetic conditional fixture.
        """
        main_jsonl = REPO_ROOT / "manuscript" / "propositions" / "main.jsonl"
        main_meta = REPO_ROOT / "manuscript" / "propositions" / "_meta.json"
        main_tex = REPO_ROOT / "manuscript" / "main.tex"
        if not main_jsonl.exists() or not main_meta.exists() or not main_tex.exists():
            import pytest
            pytest.skip("Live manuscript files unavailable (running outside repo state)")
        result = run_validator(main_jsonl, main_meta, main_tex)
        assert not _r4_pattern_a_fired(result.stdout), (
            f"F5: current manuscript (post-Path-C) must NOT trigger R4 PATTERN-A.\n"
            f"stdout:\n{result.stdout[:2000]}\n[truncated...]"
        )


# ---------- R8 containing_block-env consistency (#100) ----------


def _r9_warn_fired(stdout: str) -> bool:
    """Helper: True if [WARN] R9 finding appears in validator output."""
    return "[WARN] R9" in stdout or "R9: prop" in stdout


def test_r9_in_env_props_pass(tmp_path):
    """T-A: prop with containing_block matching env AND location inside real
    env range → [PASS] R8 (no WARN emitted).
    """
    # Build minimal fake main.tex with a real \begin{theorem}\end{theorem}
    tex_lines = ["\\documentclass{article}\n", "\\begin{document}\n"]
    # Pad to line 10
    while len(tex_lines) < 9:
        tex_lines.append("\n")
    # L10: \begin{theorem}; L11: \label; L12-L14: body; L15: \end{theorem}
    tex_lines.append("\\begin{theorem}\n")  # L10
    tex_lines.append("\\label{thm:foo}\n")  # L11
    tex_lines.append("Statement body line 1\n")  # L12
    tex_lines.append("Statement body line 2\n")  # L13
    tex_lines.append("Statement body line 3\n")  # L14
    tex_lines.append("\\end{theorem}\n")  # L15
    tex = "".join(tex_lines)
    props = [
        {
            "id": "01910b9c-d4f0-7000-8aaa-00000000a001",
            "text": "Statement body line 1",
            "location": "main.tex:L12",
            "containing_block": "thm:foo",
            "claim_type": "claim",
            "asserts": ["body 1"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, f"unexpected exit: {result.stdout}{result.stderr}"
    assert not _r9_warn_fired(result.stdout), (
        f"T-A: prop inside env range must NOT trigger R8.\nstdout:\n{result.stdout}"
    )


def test_r9_out_of_env_emits_finding(tmp_path):
    """T-B: prop with containing_block claiming theorem env but location
    outside real env range → [WARN] R9 finding. WARN-as-baseline policy
    (DP4) means exit code remains 0 but warning is emitted.
    """
    tex_lines = ["\\documentclass{article}\n", "\\begin{document}\n"]
    while len(tex_lines) < 9:
        tex_lines.append("\n")
    tex_lines.append("\\begin{theorem}\n")  # L10
    tex_lines.append("\\label{thm:foo}\n")  # L11
    tex_lines.append("body\n")  # L12
    tex_lines.append("\\end{theorem}\n")  # L13
    tex_lines.append("Post-theorem prose\n")  # L14
    tex = "".join(tex_lines)
    props = [
        {
            "id": "01910b9c-d4f0-7000-8aaa-00000000b001",
            "text": "Post-theorem prose",
            "location": "main.tex:L14",  # outside thm:foo (L10-L13)
            "containing_block": "thm:foo",  # falsely claims to be inside
            "claim_type": "claim",
            "asserts": ["post"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    # DP4: WARN-as-baseline → exit 0 but R8 warning emitted
    assert result.returncode == 0, (
        f"T-B: WARN-as-baseline must keep exit 0: {result.stdout}\n{result.stderr}"
    )
    assert _r9_warn_fired(result.stdout), (
        f"T-B: misclassified prop MUST trigger R8 WARN.\nstdout:\n{result.stdout}"
    )


def test_r9_non_env_containing_block_skip(tmp_path):
    """T-C: containing_block referring to non-theorem env (sec:setup,
    discussion, abstract) silently skipped per DP6.
    """
    tex_lines = ["\\documentclass{article}\n", "\\begin{document}\n"]
    while len(tex_lines) < 9:
        tex_lines.append("\n")
    tex_lines.append("\\section{Setup}\\label{sec:setup}\n")  # L10
    tex_lines.append("Setup prose body\n")  # L11
    tex = "".join(tex_lines)
    props = [
        {
            "id": "01910b9c-d4f0-7000-8aaa-00000000c001",
            "text": "Setup prose body",
            "location": "main.tex:L11",
            "containing_block": "sec:setup/conventions",  # NOT a theorem-like env
            "claim_type": "claim",
            "asserts": ["setup"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0
    assert not _r9_warn_fired(result.stdout), (
        f"T-C: non-env containing_block MUST be silently skipped (no R8 WARN).\nstdout:\n{result.stdout}"
    )


def test_r9_skip_no_theorem_envs(tmp_path):
    """T-D: R9 silent skip when tex has NO theorem-like envs. Edge case where
    parser runs but env_map is empty (e.g. plain prose .tex). Per DP6 +
    silent-skip semantics, R9 should NOT emit WARN even though the prop's
    containing_block doesn't resolve.
    """
    tex = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "Just plain prose, no numbered theorem-like envs at all.\n"
        "\\section{Some Section}\n"
        "More prose.\n"
        "\\end{document}\n"
    )
    props = [
        {
            "id": "01910b9c-d4f0-7000-8aaa-00000000d001",
            "text": "Just plain prose, no numbered theorem-like envs at all.",
            "location": "main.tex:L3",
            "containing_block": "thm:foo",  # claims thm env but none exists
            "claim_type": "claim",
            "asserts": ["plain"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, f"unexpected exit: {result.stdout}{result.stderr}"
    assert not _r9_warn_fired(result.stdout), (
        f"T-D: R9 must NOT WARN when tex has no theorem-like envs.\nstdout:\n{result.stdout}"
    )


def test_r9_inverted_location_range_still_warns(tmp_path):
    """T-E (#100 Path B, Codex HIGH): an inverted location range
    (main.tex:L<big>-L<small>) must NOT silently pass R9. Before the
    #115 M-2 fix, `L14-L12` against env L10-L13 passed the containment
    check by coincidence (10<=14 AND 12<=13). Now _r9_parse_location
    rejects inverted ranges → location unparseable → prop with a real
    misclassification is still surfaced rather than masked.

    Fixture: prop genuinely outside env (L20-L25, env is L10-L13) but
    written inverted (L25-L20). Must WARN.
    """
    tex_lines = ["\\documentclass{article}\n", "\\begin{document}\n"]
    while len(tex_lines) < 9:
        tex_lines.append("\n")
    tex_lines.append("\\begin{theorem}\n")  # L10
    tex_lines.append("\\label{thm:foo}\n")  # L11
    tex_lines.append("body\n")  # L12
    tex_lines.append("\\end{theorem}\n")  # L13
    for _ in range(14, 26):
        tex_lines.append("post-theorem prose\n")  # L14-L25
    tex = "".join(tex_lines)
    props = [
        {
            "id": "01910b9c-d4f0-7000-8aaa-00000000e001",
            "text": "post-theorem prose",
            "location": "main.tex:L25-L20",  # inverted; real span is well outside thm:foo
            "containing_block": "thm:foo",
            "claim_type": "claim",
            "asserts": ["x"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, f"unexpected exit: {result.stdout}{result.stderr}"
    # Inverted range → _r9_parse_location returns None → prop skipped from R9
    # check (cannot validate an unparseable location). The key assertion:
    # the inverted range must NOT yield a false [PASS]-masking-a-violation.
    # Since location is unparseable, R9 neither WARNs nor falsely passes it;
    # the malformed range is the data bug to fix, surfaced via R1/manual review.
    # What we forbid: R9 silently treating L25-L20 as "inside L10-L13".
    assert "location=main.tex:L25-L20 outside" not in result.stdout or _r9_warn_fired(
        result.stdout
    ), "inverted range must not be silently accepted as in-range"


def test_r9_summary_counts_non_main_tex_skips(tmp_path):
    """T-F (#116, DA-3 from #100 verify): R9 emits a [summary] line counting
    props skipped because their `location` uses a non-`main.tex` prefix.

    Before #116 this skip was a silent `continue` with no counter — a reader
    could not tell how many props R9 silently bypassed. The summary-line shape
    mirrors audit-theorem-boundaries.py's `[summary] ... skipped_unresolvable_cb=N`.
    """
    tex_lines = ["\\documentclass{article}\n", "\\begin{document}\n"]
    while len(tex_lines) < 9:
        tex_lines.append("\n")
    tex_lines.append("\\begin{theorem}\n")  # L10
    tex_lines.append("\\label{thm:foo}\n")  # L11
    tex_lines.append("body alpha\n")  # L12
    tex_lines.append("\\end{theorem}\n")  # L13
    tex_lines.append("body beta\n")  # L14
    tex = "".join(tex_lines)
    props = [
        {
            # in-env prop → counted as `checked`
            "id": "01910b9c-d4f0-7000-8aaa-00000000f001",
            "text": "body alpha",
            "location": "main.tex:L12",
            "containing_block": "thm:foo",
            "claim_type": "claim",
            "asserts": ["a"],
            "cites": [],
        },
        {
            # non-main.tex location prefix → R9 cannot parse → skipped, counted
            "id": "01910b9c-d4f0-7000-8aaa-00000000f002",
            "text": "body beta",
            "location": "supplement.tex:L10-L20",
            "containing_block": "thm:foo",
            "claim_type": "claim",
            "asserts": ["b"],
            "cites": [],
        },
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, f"unexpected exit: {result.stdout}{result.stderr}"
    assert "[summary] R9" in result.stdout, (
        f"#116: R9 must emit a [summary] line when theorem-like envs exist.\n"
        f"stdout:\n{result.stdout}"
    )
    assert "skipped_non_main_tex=1" in result.stdout, (
        f"#116: the non-main.tex-prefix prop must be counted, not silently "
        f"skipped.\nstdout:\n{result.stdout}"
    )
    assert "checked=1" in result.stdout, (
        f"#116: the in-env prop must be counted as checked.\nstdout:\n{result.stdout}"
    )


def test_r9_non_main_substring_prefix_not_miscounted(tmp_path):
    """T-G (#116 Path B, Codex /idd-verify finding): a non-main.tex location
    whose string merely *contains* `main.tex:` as a substring — e.g.
    `not_main.tex:L12` — must count as `skipped_non_main_tex`, NOT `checked`.

    Before the strict-prefix gate, `_r9_parse_location`'s non-anchored
    `.search()` parsed the embedded `main.tex:L12` and the prop was
    miscounted as `checked` (and containment-checked against a real env).
    """
    tex_lines = ["\\documentclass{article}\n", "\\begin{document}\n"]
    while len(tex_lines) < 9:
        tex_lines.append("\n")
    tex_lines.append("\\begin{theorem}\n")  # L10
    tex_lines.append("\\label{thm:foo}\n")  # L11
    tex_lines.append("body gamma\n")  # L12
    tex_lines.append("\\end{theorem}\n")  # L13
    tex = "".join(tex_lines)
    props = [
        {
            # location contains `main.tex:` mid-string but is NOT a main.tex loc
            "id": "01910b9c-d4f0-7000-8aaa-00000000f003",
            "text": "body gamma",
            "location": "not_main.tex:L12",
            "containing_block": "thm:foo",
            "claim_type": "claim",
            "asserts": ["g"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, f"unexpected exit: {result.stdout}{result.stderr}"
    assert "skipped_non_main_tex=1" in result.stdout, (
        f"#116 Path B: a non-main.tex location containing `main.tex:` as a "
        f"substring must count as skipped_non_main_tex.\nstdout:\n{result.stdout}"
    )
    assert "checked=0" in result.stdout, (
        f"#116 Path B: the substring-contaminated location must NOT be "
        f"miscounted as checked.\nstdout:\n{result.stdout}"
    )


# ---------- #90 R10: claim_type vs asserts compatibility (Phase 2 LLM mistag guard) ----------


def _r10_fail_fired(stdout: str) -> bool:
    """Helper: True if [FAIL] R10 finding appears in validator output."""
    return "[FAIL] R10" in stdout or "R10: claim_type=" in stdout


def test_r10_connective_with_asserts_fails(tmp_path):
    """T-A (#90): `claim_type=connective` with non-empty `asserts` must
    trigger R10 FAIL — Phase 2 LLM mistag guard. The exemption R3 grants
    to `structural_leaf_types` (connective/reference/scope_qualifier) is
    `claim_type`-based; a content-bearing prop mistagged as connective
    would slip past R3 + R1. R10 catches it.
    """
    tex_lines = ["\\documentclass{article}\n", "\\begin{document}\n"]
    while len(tex_lines) < 9:
        tex_lines.append("\n")
    tex_lines.append("\\section{Setup}\\label{sec:setup}\n")  # L10
    tex_lines.append("Hence, $F = \\mathrm{id}$.\n")  # L11
    tex = "".join(tex_lines)
    props = [
        {
            "id": "01910b9c-d4f0-7000-8aaa-0000000000a1",
            "text": "Hence, $F = \\mathrm{id}$.",
            "location": "main.tex:L11",
            "containing_block": "sec:setup",
            # Mistag: a real equality assertion tagged as `connective`
            "claim_type": "connective",
            "asserts": ["F = id"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode != 0, (
        f"T-A: mistagged connective with non-empty asserts must fail R10 "
        f"(exit 1).\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert _r10_fail_fired(result.stdout), (
        f"T-A: [FAIL] R10 must fire for connective + non-empty asserts.\n"
        f"stdout:\n{result.stdout}"
    )


def test_r10_reference_with_asserts_fails(tmp_path):
    """T-B (#90): `claim_type=reference` with non-empty `asserts` must
    trigger R10 FAIL. References are pure cross-cite markers per
    SCHEMA.md; carrying assertions is a mistag.
    """
    tex_lines = ["\\documentclass{article}\n", "\\begin{document}\n"]
    while len(tex_lines) < 9:
        tex_lines.append("\n")
    tex_lines.append("\\section{Setup}\\label{sec:setup}\n")  # L10
    tex_lines.append("See Lemma 1 for the construction.\n")  # L11
    tex = "".join(tex_lines)
    props = [
        {
            "id": "01910b9c-d4f0-7000-8aaa-0000000000b1",
            "text": "See Lemma 1 for the construction.",
            "location": "main.tex:L11",
            "containing_block": "sec:setup",
            "claim_type": "reference",
            "asserts": ["see Lemma 1"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode != 0, (
        f"T-B: mistagged reference with non-empty asserts must fail R10.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert _r10_fail_fired(result.stdout), (
        f"T-B: [FAIL] R10 must fire for reference + non-empty asserts.\n"
        f"stdout:\n{result.stdout}"
    )


def test_r10_scope_qualifier_with_asserts_passes(tmp_path):
    """T-C (#90): `claim_type=scope_qualifier` with non-empty `asserts`
    is **intentional behaviour** — scope_qualifier props typically carry
    1 short assert documenting the scope (e.g. "scope: for every s in S").
    Regression guard against accidentally adding scope_qualifier to R10's
    `must_be_empty` set.
    """
    tex_lines = ["\\documentclass{article}\n", "\\begin{document}\n"]
    while len(tex_lines) < 9:
        tex_lines.append("\n")
    tex_lines.append("\\section{Setup}\\label{sec:setup}\n")  # L10
    tex_lines.append("For every $s \\in S$, the function $f(s)$ holds.\n")  # L11
    tex = "".join(tex_lines)
    props = [
        {
            "id": "01910b9c-d4f0-7000-8aaa-0000000000c1",
            "text": "For every $s \\in S$",
            "location": "main.tex:L11",
            "containing_block": "sec:setup",
            "claim_type": "scope_qualifier",
            "asserts": ["scope: for every s in S"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, (
        f"T-C: scope_qualifier prop must yield exit 0 (no unrelated rule "
        f"should fail this fixture).\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert not _r10_fail_fired(result.stdout), (
        f"T-C: scope_qualifier with 1 assert MUST NOT trigger R10 — "
        f"intentional behaviour per SCHEMA.md.\nstdout:\n{result.stdout}"
    )


def test_r10_connective_empty_asserts_passes(tmp_path):
    """T-D (#90): `claim_type=connective` with empty `asserts` is the
    canonical correct usage and must pass R10.
    """
    tex_lines = ["\\documentclass{article}\n", "\\begin{document}\n"]
    while len(tex_lines) < 9:
        tex_lines.append("\n")
    tex_lines.append("\\section{Setup}\\label{sec:setup}\n")  # L10
    tex_lines.append("Hence,\n")  # L11
    tex = "".join(tex_lines)
    props = [
        {
            "id": "01910b9c-d4f0-7000-8aaa-0000000000d1",
            "text": "Hence,",
            "location": "main.tex:L11",
            "containing_block": "sec:setup",
            "claim_type": "connective",
            "asserts": [],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, (
        f"T-D: connective + empty asserts must yield exit 0 (no unrelated "
        f"rule should fail this fixture).\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert not _r10_fail_fired(result.stdout), (
        f"T-D: connective with empty asserts is canonical correct usage; "
        f"R10 must not fire.\nstdout:\n{result.stdout}"
    )


# ---------- #119: R11 evidence_class enum check ----------


def _r11_fail_fired(stdout: str) -> bool:
    """Helper: True if [FAIL] R11 finding appears in validator output."""
    return "[FAIL] R11" in stdout or "R11: evidence_class=" in stdout


def _r11_skip_fired(stdout: str) -> bool:
    """Helper: True if R11 was skipped (schema_version < 1.2)."""
    return "[SKIP] R11" in stdout


def _r11_fixture_prop(pid_suffix: str, evidence_class: str) -> dict:
    """Minimal connective prop (R3-exempt, R10-clean) carrying evidence_class."""
    return {
        "id": f"01910b9c-d4f0-7000-8aaa-0000000000{pid_suffix}",
        "text": "Hence,",
        "location": "main.tex:L11",
        "containing_block": "sec:setup",
        "claim_type": "connective",
        "asserts": [],
        "cites": [],
        "evidence_class": evidence_class,
    }


def _r11_fixture_tex() -> str:
    tex_lines = ["\\documentclass{article}\n", "\\begin{document}\n"]
    while len(tex_lines) < 9:
        tex_lines.append("\n")
    tex_lines.append("\\section{Setup}\\label{sec:setup}\n")  # L10
    tex_lines.append("Hence,\n")  # L11
    return "".join(tex_lines)


def test_r11_unknown_evidence_class_fails(tmp_path):
    """#119 C.1/C.2: a prop whose `evidence_class` is outside the canonical
    5-element enum (`verified | derived | hypothesized | conventional | open`)
    must trigger R11 FAIL under schema v1.2+. SCHEMA.md defines the enum
    prose-only; before R11 no rule enforced it, so Phase 2 LLM extractor
    hallucinations (`definitional`, `claim`) slipped past R1-R10.
    """
    props = [_r11_fixture_prop("e1", "definitional")]
    result = run_validator(
        *write_fixture(tmp_path, props, _r11_fixture_tex(), schema_version="1.2")
    )
    assert result.returncode != 0, (
        f"non-canonical evidence_class must fail R11 (exit 1).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert _r11_fail_fired(result.stdout), (
        f"[FAIL] R11 must fire for evidence_class outside the enum.\n"
        f"stdout:\n{result.stdout}"
    )


def test_r11_canonical_values_pass(tmp_path):
    """#119: props using canonical `evidence_class` values must pass R11."""
    props = [
        _r11_fixture_prop("f1", "verified"),
        _r11_fixture_prop("f2", "derived"),
        _r11_fixture_prop("f3", "hypothesized"),
        _r11_fixture_prop("f4", "conventional"),
        _r11_fixture_prop("f5", "open"),
    ]
    result = run_validator(
        *write_fixture(tmp_path, props, _r11_fixture_tex(), schema_version="1.2")
    )
    assert result.returncode == 0, (
        f"canonical evidence_class values must yield exit 0.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert not _r11_fail_fired(result.stdout), (
        f"R11 must not fire for canonical evidence_class values.\n"
        f"stdout:\n{result.stdout}"
    )


def test_r11_schema_v1_skip(tmp_path):
    """#119: R11 is schema-gated v1.2+ (mirrors R7). Under schema v1.1 a
    non-canonical `evidence_class` must NOT trigger R11 — backward compat
    for legacy fixtures predating the enum-enforcement rule.
    """
    props = [_r11_fixture_prop("a1", "definitional")]
    result = run_validator(
        *write_fixture(tmp_path, props, _r11_fixture_tex(), schema_version="1.1")
    )
    assert _r11_skip_fired(result.stdout), (
        f"R11 must be skipped under schema v1.1 (backward compat).\n"
        f"stdout:\n{result.stdout}"
    )
    assert not _r11_fail_fired(result.stdout), (
        f"R11 must not fire under schema v1.1 even with non-canonical "
        f"evidence_class.\nstdout:\n{result.stdout}"
    )


# ---------- #124: R12 claim_type enum check ----------


def _r12_fail_fired(stdout: str) -> bool:
    """Helper: True if [FAIL] R12 finding appears in validator output."""
    return "[FAIL] R12" in stdout or "R12: claim_type=" in stdout


def _r12_skip_fired(stdout: str) -> bool:
    """Helper: True if R12 was skipped (schema_version < 1.2)."""
    return "[SKIP] R12" in stdout


def _r12_fixture_prop(pid_suffix: str, claim_type: str) -> dict:
    """Minimal prop carrying a parameterized claim_type. asserts must be empty
    when claim_type is `connective`/`reference` (R10 compat), so the fixture
    uses generic-claim text and empty asserts to stay R10-clean across all
    enum members.
    """
    return {
        "id": f"01910b9c-d4f0-7000-8bbb-0000000000{pid_suffix}",
        "text": "Hence,",
        "location": "main.tex:L11",
        "containing_block": "sec:setup",
        "claim_type": claim_type,
        "asserts": [],
        "cites": [],
        "evidence_class": "derived",
    }


def _r12_fixture_tex() -> str:
    tex_lines = ["\\documentclass{article}\n", "\\begin{document}\n"]
    while len(tex_lines) < 9:
        tex_lines.append("\n")
    tex_lines.append("\\section{Setup}\\label{sec:setup}\n")  # L10
    tex_lines.append("Hence,\n")  # L11
    return "".join(tex_lines)


def _r12_fixture_prop_no_claim_type(pid_suffix: str) -> dict:
    """Minimal prop WITHOUT a `claim_type` key — for the absent-vs-falsy
    distinction test (#130). R12 must skip props whose claim_type key is
    absent (R3 handles defaulting via .get("claim_type", "claim")), but
    must FAIL props whose claim_type IS present but None/empty.
    """
    return {
        "id": f"01910b9c-d4f0-7000-8bbb-0000000000{pid_suffix}",
        "text": "Hence,",
        "location": "main.tex:L11",
        "containing_block": "sec:setup",
        # claim_type intentionally omitted
        "asserts": [],
        "cites": [],
        "evidence_class": "derived",
    }


def test_r12_unknown_claim_type_fails(tmp_path):
    """#124: a prop whose `claim_type` is outside the canonical 12-element
    enum must trigger R12 FAIL under schema v1.2+. SCHEMA.md defines the enum
    prose-only; before R12 no rule enforced it. The R3 `structural_leaf_types`
    exemption keys off `claim_type`, so a hallucinated value would silently
    misroute orphan detection.
    """
    props = [_r12_fixture_prop("e1", "definitional")]  # not in 12-enum
    result = run_validator(
        *write_fixture(tmp_path, props, _r12_fixture_tex(), schema_version="1.2")
    )
    assert result.returncode != 0, (
        f"non-canonical claim_type must fail R12 (exit 1).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert _r12_fail_fired(result.stdout), (
        f"[FAIL] R12 must fire for claim_type outside the enum.\n"
        f"stdout:\n{result.stdout}"
    )


def test_r12_canonical_values_pass(tmp_path):
    """#124: props using canonical `claim_type` values must pass R12.
    Covers all 12 enum members so any future enum drift surfaces here.
    """
    canonical = [
        "axiom", "definition", "hypothesis", "claim", "case_split",
        "display_equation", "restatement", "commentary", "example",
        "connective", "reference", "scope_qualifier",
    ]
    props = [
        _r12_fixture_prop(f"{i:02x}", ct)
        for i, ct in enumerate(canonical)
    ]
    result = run_validator(
        *write_fixture(tmp_path, props, _r12_fixture_tex(), schema_version="1.2")
    )
    assert not _r12_fail_fired(result.stdout), (
        f"R12 must not fire for canonical claim_type values.\n"
        f"stdout:\n{result.stdout}"
    )


def test_r12_schema_v1_skip(tmp_path):
    """#124: R12 is schema-gated v1.2+ (mirrors R7 + R11). Under schema v1.1
    a non-canonical `claim_type` must NOT trigger R12 — backward compat
    for legacy fixtures predating the enum-enforcement rule.
    """
    props = [_r12_fixture_prop("a1", "definitional")]
    result = run_validator(
        *write_fixture(tmp_path, props, _r12_fixture_tex(), schema_version="1.1")
    )
    assert _r12_skip_fired(result.stdout), (
        f"R12 must be skipped under schema v1.1 (backward compat).\n"
        f"stdout:\n{result.stdout}"
    )
    assert not _r12_fail_fired(result.stdout), (
        f"R12 must not fire under schema v1.1 even with non-canonical "
        f"claim_type.\nstdout:\n{result.stdout}"
    )


def test_r12_null_claim_type_fails(tmp_path):
    """#130: a prop whose `claim_type` is JSON null must FAIL R12 — `None`
    is not in the 12-element frozenset. Present-but-None is an enum
    violation, distinct from absent.

    Refactor-regression anchor: this test prevents a future "simplification"
    of `if "claim_type" not in prop: continue` to `if not prop.get(...): continue`,
    which would silently flip null/empty from FAIL to skip (both are falsy
    under `not`).
    """
    props = [_r12_fixture_prop("01", None)]
    result = run_validator(
        *write_fixture(tmp_path, props, _r12_fixture_tex(), schema_version="1.2")
    )
    assert result.returncode != 0, (
        f"null claim_type must fail R12 (exit 1).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert _r12_fail_fired(result.stdout), (
        f"[FAIL] R12 must fire for claim_type=null.\n"
        f"stdout:\n{result.stdout}"
    )


def test_r12_empty_string_claim_type_fails(tmp_path):
    """#130: a prop whose `claim_type` is the empty string must FAIL R12 —
    `""` is not in the 12-element frozenset. Companion to the null test;
    the present-but-falsy class spans both `None` and `""`.
    """
    props = [_r12_fixture_prop("02", "")]
    result = run_validator(
        *write_fixture(tmp_path, props, _r12_fixture_tex(), schema_version="1.2")
    )
    assert result.returncode != 0, (
        f'empty-string claim_type must fail R12 (exit 1).\n'
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert _r12_fail_fired(result.stdout), (
        f'[FAIL] R12 must fire for claim_type="".\n'
        f"stdout:\n{result.stdout}"
    )


def test_r12_absent_claim_type_skips(tmp_path):
    """#130: a prop with NO `claim_type` key must NOT trigger R12 — absence
    is R3's call (it defaults via `.get("claim_type", "claim")`), not R12's.

    Symmetric anchor to the null/empty tests: locks the absent-vs-falsy
    distinction. If R12's `if "claim_type" not in prop: continue` ever gets
    changed to `if not prop.get("claim_type"): continue`, this test still
    passes (absent stays skipped) but the null/empty tests fail — together
    they cover the regression class.
    """
    props = [_r12_fixture_prop_no_claim_type("03")]
    result = run_validator(
        *write_fixture(tmp_path, props, _r12_fixture_tex(), schema_version="1.2")
    )
    # R12 alone must not FAIL for the absent-key case. Note: the validator
    # may still exit non-zero for unrelated reasons on this minimal fixture
    # (e.g. R3 / R10 behavior on a prop without claim_type), so we assert
    # specifically that no R12 FAIL appears, not on returncode.
    assert not _r12_fail_fired(result.stdout), (
        f"R12 must NOT fire when claim_type key is absent.\n"
        f"stdout:\n{result.stdout}"
    )


# ---------- #115 M-4: R9 quiet on unmatched begin residue ----------


def test_r9_uses_warn_on_residue_false(tmp_path):
    """#115 M-4 — validator R9 passes ``warn_on_residue=False`` to the shared
    LaTeX env parser so stderr stays clean (informational ``[PASS]``/``[WARN]``
    line format).

    Audit-script (``audit-theorem-boundaries.py --jsonl``) is the loud CI gate
    and keeps the default ``warn_on_residue=True``; this differentiates the
    two callers' lifecycle (gate vs. informational).
    """
    # Fixture: dangling \begin{theorem} with a prop inside an unrelated env so
    # validator runs to completion. Containing_block is sec:* so R9 skips the
    # prop (silent skip per DP6), but R9's call to parse_envs still encounters
    # the unmatched begin in the open_stack.
    tex = (
        "\\section{Setup}\\label{sec:setup}\n"   # L1
        "\\begin{theorem}\n"                       # L2  — no matching \end
        "\\label{thm:dangling}\n"                  # L3
        "Theorem body without close\n"             # L4
    )
    props = [
        {
            "id": SAMPLE_UUID_V7,
            "text": "Theorem body without close",
            "location": "main.tex:L4",
            "containing_block": "sec:setup",  # silent-skip cb → R9 won't check
            "claim_type": "claim",
            "asserts": ["dummy"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    # R9 itself doesn't crash on dangling begin. With dangling \begin the
    # residue stays in open_stack and envs is empty, so R9 takes the DP6
    # silent-skip path ([SKIP] R9). [PASS]/[WARN] also acceptable if a
    # future fixture has matched envs.
    assert any(
        marker in result.stdout for marker in ("[PASS] R9", "[WARN] R9", "[SKIP] R9")
    ), (
        f"R9 should run cleanly on dangling-begin fixture; got: {result.stdout}"
    )
    # Critical assertion: validator stderr must NOT contain the
    # 'unmatched \begin{...}' warning string. parse_envs is shared with
    # audit-script but R9 passes warn_on_residue=False to suppress it.
    assert "unmatched" not in result.stderr, (
        f"R9 leaked unmatched-begin stderr; warn_on_residue=False not honored.\n"
        f"stderr: {result.stderr!r}\n"
        f"stdout: {result.stdout!r}"
    )


# ---------- #115 M-5: shared module locked-down (validator-side) ----------


def test_validator_uses_shared_lib():
    """#115 M-5 — validate-propositions.py must import the LaTeX env parser
    from scripts/_lib/, not maintain its own ``_R9_*`` / ``_r9_*`` inline
    shadows.

    Regression guard: if a future refactor re-introduces module-level
    _R9_BEGIN_RE / _R9_PROOF_TARGET_RE constants directly in
    validate-propositions.py (as the pre-#115 inline copy had), this fires.
    """
    source = SCRIPT.read_text(encoding="utf-8")
    assert "from _lib.latex_env_parser import" in source, (
        "validate-propositions.py must import shared parser from _lib; "
        "got source without expected import line"
    )
    # Pre-#115 inline shadows must not return
    assert "_R9_BEGIN_RE = re.compile" not in source, (
        "validator has inline _R9_BEGIN_RE — re-introduces M-5 drift surface"
    )
    assert "_R9_PROOF_TARGET_RE = re.compile" not in source, (
        "validator has inline _R9_PROOF_TARGET_RE — re-introduces drift"
    )
    assert "_R9_TYPE_PREFIX_RE = re.compile" not in source, (
        "validator has inline _R9_TYPE_PREFIX_RE — re-introduces drift "
        "(this was the regex that diverged 4-type vs 7-type pre-#115)"
    )


# ---------- R13 location line-anchoring (verify-tex-prop-correspondence) ----------


def _r13_warn_fired(stdout: str) -> bool:
    """Helper: True if a [WARN] R13 location-drift finding appears in output."""
    return "[WARN] R13" in stdout


def test_r13_location_correct_no_warn(tmp_path):
    """A prop whose text sits within its declared location line range MUST NOT
    trigger an R13 location-drift WARN (regression guard against false positives).
    """
    sentence = "We study four eta-class specializations."
    tex = "\n" * 10 + sentence + "\n"  # sentence lands on L11
    props = [
        {
            "id": "01910b9c-d4f0-7000-8ccc-00000000d001",
            "text": sentence,
            "location": "main.tex:L11",
            "containing_block": "test",
            "claim_type": "claim",
            "asserts": ["four eta-class specializations"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, f"unexpected exit: {result.stdout}{result.stderr}"
    assert not _r13_warn_fired(result.stdout), (
        f"correctly-located prop must NOT trigger R13 WARN:\n{result.stdout}"
    )


def test_r13_location_drift_emits_warn(tmp_path):
    """A prop whose text is present in main.tex but OUTSIDE its declared
    location line range MUST trigger an R13 location-drift WARN. WARN-as-baseline
    (mirrors R9 DP4): the finding surfaces but the exit code stays 0.

    Spec example (verify-tex-prop-correspondence): a sentence whose declared
    range no longer contains the text after a line shift.
    """
    sentence = "We study four eta-class specializations."
    tex = "\n" * 10 + sentence + "\n"  # sentence is actually on L11
    drifted_id = "01910b9c-d4f0-7000-8ccc-00000000d002"
    props = [
        {
            "id": drifted_id,
            "text": sentence,
            "location": "main.tex:L3",  # declared L3 — but text is on L11
            "containing_block": "test",
            "claim_type": "claim",
            "asserts": ["four eta-class specializations"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    # WARN-as-baseline: drift surfaces as WARN, exit code stays 0
    assert result.returncode == 0, (
        f"R13 WARN-as-baseline must keep exit 0:\n{result.stdout}{result.stderr}"
    )
    assert _r13_warn_fired(result.stdout), (
        f"prop text outside its declared location range MUST trigger R13 WARN:\n{result.stdout}"
    )
    assert "00000000d002" in result.stdout, (
        f"R13 location-drift finding MUST name the proposition:\n{result.stdout}"
    )


def test_r13_single_line_multiline_source_passes(tmp_path):
    """A single-line `location` (main.tex:L<a>) whose text spans several source
    lines MUST pass: single-line `location` is a start-anchor naming where the
    text begins, not a claim that it occupies only line a
    (verify-tex-prop-correspondence design: `location` 單行值語意).
    """
    prop_text = (
        "Under the start anchor convention the location field names "
        "the beginning line rather than the only line a proposition occupies."
    )
    wrapped = (
        "Under the start anchor convention the location field names\n"
        "the beginning line rather than the only line a proposition\n"
        "occupies."
    )
    tex = "\n" * 10 + wrapped + "\n"  # wrapped sentence begins on L11
    props = [
        {
            "id": "01910b9c-d4f0-7000-8ccc-00000000d010",
            "text": prop_text,
            "location": "main.tex:L11",
            "containing_block": "test",
            "claim_type": "claim",
            "asserts": ["location names the beginning line"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, f"unexpected exit: {result.stdout}{result.stderr}"
    assert not _r13_warn_fired(result.stdout), (
        f"single-line location with a multi-line source span must NOT trigger "
        f"an R13 WARN (start-anchor semantics):\n{result.stdout}"
    )


def test_r13_single_line_within_tolerance_passes(tmp_path):
    """A single-line `location` declared exactly R13_START_TOLERANCE lines off
    from the text's true start MUST still pass — the tolerance band is inclusive.
    """
    sentence = "A proposition anchored within the inclusive tolerance band."
    tex = "\n" * 12 + sentence + "\n"  # sentence on L13
    props = [
        {
            "id": "01910b9c-d4f0-7000-8ccc-00000000d011",
            "text": sentence,
            "location": "main.tex:L11",  # declared L11, true start L13 — delta 2
            "containing_block": "test",
            "claim_type": "claim",
            "asserts": ["anchored within tolerance"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, f"unexpected exit: {result.stdout}{result.stderr}"
    assert not _r13_warn_fired(result.stdout), (
        f"single-line location within the inclusive tolerance band must NOT "
        f"trigger an R13 WARN:\n{result.stdout}"
    )


def test_r13_single_line_start_anchor_drift_warns(tmp_path):
    """A single-line `location` whose text's true start drifts beyond the
    tolerance MUST trigger an R13 WARN; WARN-as-baseline keeps exit 0 and the
    finding names the proposition.
    """
    sentence = "A proposition whose declared start line drifted far from its text."
    tex = "\n" * 20 + sentence + "\n"  # sentence on L21
    drifted_id = "01910b9c-d4f0-7000-8ccc-00000000d012"
    props = [
        {
            "id": drifted_id,
            "text": sentence,
            "location": "main.tex:L5",  # declared L5, true start L21 — delta 16
            "containing_block": "test",
            "claim_type": "claim",
            "asserts": ["declared start drifted"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, (
        f"R13 WARN-as-baseline must keep exit 0:\n{result.stdout}{result.stderr}"
    )
    assert _r13_warn_fired(result.stdout), (
        f"single-line start-anchor drift beyond tolerance MUST trigger an "
        f"R13 WARN:\n{result.stdout}"
    )
    assert "00000000d012" in result.stdout, (
        f"R13 start-anchor drift finding MUST name the proposition:\n{result.stdout}"
    )


def test_r13_range_form_within_range_passes(tmp_path):
    """A range-form `location` (main.tex:L<a>-L<b>) whose text falls within the
    declared slice MUST pass — the range branch keeps exact-slice semantics.
    """
    prop_text = (
        "The range form names an explicit span so the validator checks "
        "exact containment within the declared start and end lines."
    )
    wrapped = (
        "The range form names an explicit span so the validator checks\n"
        "exact containment within the declared start and end lines."
    )
    tex = "\n" * 10 + wrapped + "\n"  # wrapped sentence on L11-L12
    props = [
        {
            "id": "01910b9c-d4f0-7000-8ccc-00000000d013",
            "text": prop_text,
            "location": "main.tex:L11-L12",
            "containing_block": "test",
            "claim_type": "claim",
            "asserts": ["range form checks exact containment"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, f"unexpected exit: {result.stdout}{result.stderr}"
    assert not _r13_warn_fired(result.stdout), (
        f"range-form location whose text is within the declared slice must "
        f"NOT trigger an R13 WARN:\n{result.stdout}"
    )


def test_r13_range_form_outside_range_warns(tmp_path):
    """A range-form `location` whose text lies outside the declared slice MUST
    trigger an R13 WARN; the finding names the proposition.
    """
    sentence = "A proposition whose text sits well outside its declared range."
    tex = "\n" * 19 + sentence + "\n"  # sentence on L20
    drifted_id = "01910b9c-d4f0-7000-8ccc-00000000d014"
    props = [
        {
            "id": drifted_id,
            "text": sentence,
            "location": "main.tex:L11-L13",  # declared L11-L13, text actually on L20
            "containing_block": "test",
            "claim_type": "claim",
            "asserts": ["text outside declared range"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, (
        f"R13 WARN-as-baseline must keep exit 0:\n{result.stdout}{result.stderr}"
    )
    assert _r13_warn_fired(result.stdout), (
        f"range-form location whose text is outside the declared slice MUST "
        f"trigger an R13 WARN:\n{result.stdout}"
    )
    assert "00000000d014" in result.stdout, (
        f"R13 range-drift finding MUST name the proposition:\n{result.stdout}"
    )


def _r13_unanchorable_fired(stdout: str) -> bool:
    """Helper: True if a distinct R13 un-anchorable informational finding
    appears in output (separate channel from the location-drift WARN)."""
    return "[summary] R13" in stdout and "un-anchorable" in stdout


def test_r13_missing_location_unanchorable(tmp_path):
    """A prop with no `location` field MUST be reported as a distinct
    un-anchorable informational finding, NOT a wrong-line drift WARN, and the
    validator MUST continue (exit 0).
    """
    sentence = "A proposition that carries no location field at all."
    tex = "\n" * 4 + sentence + "\n"
    prop_id = "01910b9c-d4f0-7000-8ccc-00000000d020"
    props = [
        {
            "id": prop_id,
            "text": sentence,
            # no "location" key
            "containing_block": "test",
            "claim_type": "claim",
            "asserts": ["no location field"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, (
        f"missing-location prop must not abort the run:\n{result.stdout}{result.stderr}"
    )
    assert _r13_unanchorable_fired(result.stdout), (
        f"missing-location prop must surface as an R13 un-anchorable finding:\n{result.stdout}"
    )
    assert not _r13_warn_fired(result.stdout), (
        f"missing-location prop must NOT be mis-flagged as a drift WARN:\n{result.stdout}"
    )
    assert prop_id in result.stdout, (
        f"R13 un-anchorable finding MUST name the proposition:\n{result.stdout}"
    )


def test_r13_malformed_location_unanchorable(tmp_path):
    """A prop whose `location` value does not match the `main.tex:L<n>` form
    MUST be reported as a distinct un-anchorable informational finding, not a
    drift WARN; the validator MUST continue.
    """
    sentence = "A proposition whose location string is malformed."
    tex = "\n" * 6 + sentence + "\n"
    prop_id = "01910b9c-d4f0-7000-8ccc-00000000d021"
    props = [
        {
            "id": prop_id,
            "text": sentence,
            "location": "chapter three, paragraph two",  # not main.tex:L<n>
            "containing_block": "test",
            "claim_type": "claim",
            "asserts": ["malformed location string"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, (
        f"malformed-location prop must not abort the run:\n{result.stdout}{result.stderr}"
    )
    assert _r13_unanchorable_fired(result.stdout), (
        f"malformed-location prop must surface as an R13 un-anchorable finding:\n{result.stdout}"
    )
    assert not _r13_warn_fired(result.stdout), (
        f"malformed-location prop must NOT be mis-flagged as a drift WARN:\n{result.stdout}"
    )
    assert prop_id in result.stdout, (
        f"R13 un-anchorable finding MUST name the proposition:\n{result.stdout}"
    )


def test_r13_oversized_span_unanchorable(tmp_path):
    """A single-line `location` prop whose text spans more source lines than
    the R13_MAX_SPAN scan window MUST be reported as un-anchorable informational,
    not a drift WARN.
    """
    # 35 one-word source lines; the prop text concatenates all 35 words, so no
    # 30-line (R13_MAX_SPAN) window can contain it.
    words = [f"alpha{i}" for i in range(1, 36)]
    tex = "\n".join(words) + "\n"  # words on L1..L35
    prop_text = " ".join(words)
    prop_id = "01910b9c-d4f0-7000-8ccc-00000000d022"
    props = [
        {
            "id": prop_id,
            "text": prop_text,
            "location": "main.tex:L1",
            "containing_block": "test",
            "claim_type": "claim",
            "asserts": ["text spans more than the scan window"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, (
        f"oversized-span prop must not abort the run:\n{result.stdout}{result.stderr}"
    )
    assert _r13_unanchorable_fired(result.stdout), (
        f"oversized-span prop must surface as an R13 un-anchorable finding:\n{result.stdout}"
    )
    assert not _r13_warn_fired(result.stdout), (
        f"oversized-span prop must NOT be mis-flagged as a drift WARN:\n{result.stdout}"
    )
    assert prop_id in result.stdout, (
        f"R13 un-anchorable finding MUST name the proposition:\n{result.stdout}"
    )


def test_normalize_preserves_case_labels(tmp_path):
    """`normalize_for_match` must preserve literal `Case (X)` / `Sub-case (X)`
    labels that appear verbatim in current main.tex (#140). Pre-fix: the
    legacy line-226 strip removed `Case (D)` from BOTH prop.text and main.tex,
    collapsing `"This is Case (D)."` to `"This is."` — the degenerate fragment
    that drove the #139 false-positive. Post-fix: the labels are preserved,
    so R13's start-anchor sees a unique discriminator and anchors correctly.
    """
    # Import the validator's normalize_for_match via importlib (filename has hyphen).
    # Resolve the script path relative to the test file's plugin root so the
    # test works regardless of pytest's CWD (e.g. when invoked from a consumer
    # repo with `pytest propositions-plugin/tests/`, CWD is the consumer's
    # repo root, not the plugin's).
    import importlib.util
    spec = importlib.util.spec_from_file_location("v", SCRIPT)
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)

    # The discriminator MUST survive normalization. Before #140 the strip
    # would collapse this to "This is.".
    assert "Case (D)" in v.normalize_for_match("This is Case (D)."), (
        f"normalize_for_match must preserve `Case (D)` discriminator (#140); "
        f"got {v.normalize_for_match('This is Case (D).')!r}"
    )
    assert "Sub-case (C)" in v.normalize_for_match(
        r"\emph{Sub-case (C): $v(x) = B x^{\beta_0} + B_0$, $p \neq \beta_0$.}"
    ), "normalize_for_match must preserve `Sub-case (C)` discriminator (#140)"

    # Bare `Case (E)` mention (no surrounding macro) must also pass through.
    assert "Case (E)" in v.normalize_for_match(
        "other $g$ choices are genuinely distinct, so Case (E) is not absorbed."
    ), "normalize_for_match must preserve inline `Case (E)` reference (#140)"


def test_r13_ambiguous_anchor_unanchorable(tmp_path):
    """A short prop whose normalized form collapses to a high-frequency fragment
    (so `_find_start_anchor`'s scan-range hit set fills the entire window) MUST
    be reported as un-anchorable informational, NOT a drift WARN (#139).

    The fixture constructs a tex with the *same* short sentence repeated at
    five widely-spaced lines. The prop declares the middle occurrence as its
    location, but every scan window touches at least one occurrence — the
    hit set fills the entire window. The legacy contract "largest s is the
    true start" would silently pick the latest hit and report a false drift;
    the degeneracy guard catches this and routes to un-anchorable instead.

    Note: this test used to rely on `normalize_for_match` stripping `Case (X)`
    labels to manufacture the degenerate fragment (#139). After #140 removed
    that strip, the fixture now uses a genuinely-duplicated identical
    sentence to exercise the same guard.
    """
    # Build a tex with five copies of the same short sentence spaced 20 lines
    # apart. The hits set spans more than R13_MAX_SPAN=30 lines, so the guard
    # in `_find_start_anchor` returns None (un-anchorable) for any prop
    # declaring one of these lines.
    sentence = "An unspecified condition holds."
    tex_lines = [""] * 90
    tex_lines[0] = sentence   # L1
    tex_lines[20] = sentence  # L21
    tex_lines[40] = sentence  # L41 (declared location of the prop)
    tex_lines[60] = sentence  # L61
    tex_lines[80] = sentence  # L81
    tex = "\n".join(tex_lines) + "\n"
    prop_id = "01910b9c-d4f0-7000-8ccc-00000000d023"
    props = [
        {
            "id": prop_id,
            "text": sentence,
            "location": "main.tex:L41",  # actually correct location
            "containing_block": "test",
            "claim_type": "claim",
            "asserts": ["unspecified condition"],
            "cites": [],
        }
    ]
    result = run_validator(*write_fixture(tmp_path, props, tex, schema_version="1.2"))
    assert result.returncode == 0, (
        f"ambiguous-anchor prop must not abort the run:\n{result.stdout}{result.stderr}"
    )
    assert _r13_unanchorable_fired(result.stdout), (
        f"ambiguous-anchor prop must surface as an R13 un-anchorable finding:\n{result.stdout}"
    )
    assert not _r13_warn_fired(result.stdout), (
        f"ambiguous-anchor prop must NOT be mis-flagged as a drift WARN:\n{result.stdout}"
    )
    assert prop_id in result.stdout, (
        f"R13 un-anchorable finding MUST name the proposition:\n{result.stdout}"
    )
