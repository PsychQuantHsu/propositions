"""Tests for scripts/migrate-prop-id-to-uuid.py.

Covers the deterministic UUID v7 generator + JSONL rewrite + audit map emission
required by Spectra change `migrate-prop-id-to-stable-uuid` (Task 1.1).

Verification targets per tasks.md task 1.1:
- Running the migration twice on the same input MUST produce byte-identical
  output JSONL and byte-identical audit map.
- The audit map MUST contain every input prop's old id mapped to a UUID v7
  string in canonical 8-4-4-4-12 hex form with version field `7`.

Additional coverage:
- Cite re-pointing within a single file and across cross-file references.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "migrate-prop-id-to-uuid.py"

UUID_V7_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def write_jsonl(path: Path, props: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(p) for p in props) + "\n")


def run_migrator(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )


def test_deterministic_round_trip_byte_identical(tmp_path: Path) -> None:
    """Running the migrator twice on identical inputs MUST produce byte-identical outputs."""
    src = tmp_path / "main.jsonl"
    write_jsonl(
        src,
        [
            {
                "id": "P001",
                "text": "Suppose F is identity.",
                "location": "main.tex:L1",
                "containing_block": "sec:setup",
                "claim_type": "hypothesis",
                "asserts": ["F is identity"],
                "mathematical_objects": ["F"],
                "cites": [],
                "evidence_class": "hypothesized",
            },
            {
                "id": "P002",
                "text": "Then G follows.",
                "location": "main.tex:L2",
                "containing_block": "sec:setup",
                "claim_type": "claim",
                "asserts": ["G follows"],
                "mathematical_objects": ["G"],
                "cites": ["P001"],
                "evidence_class": "derived",
            },
        ],
    )

    out_dir_a = tmp_path / "out_a"
    out_dir_b = tmp_path / "out_b"
    out_dir_a.mkdir()
    out_dir_b.mkdir()

    a = run_migrator(src, "--out-dir", out_dir_a, "--emit-map", out_dir_a / "map.json")
    b = run_migrator(src, "--out-dir", out_dir_b, "--emit-map", out_dir_b / "map.json")

    assert a.returncode == 0, f"first run failed: stderr={a.stderr}"
    assert b.returncode == 0, f"second run failed: stderr={b.stderr}"

    jsonl_a = (out_dir_a / "main.jsonl").read_bytes()
    jsonl_b = (out_dir_b / "main.jsonl").read_bytes()
    assert jsonl_a == jsonl_b, "JSONL output is not byte-identical across runs"

    map_a = (out_dir_a / "map.json").read_bytes()
    map_b = (out_dir_b / "map.json").read_bytes()
    assert map_a == map_b, "audit map output is not byte-identical across runs"


def test_audit_map_contains_uuid_v7_for_each_input_id(tmp_path: Path) -> None:
    """Audit map MUST map every old id to a canonical UUID v7 string."""
    main = tmp_path / "main.jsonl"
    write_jsonl(
        main,
        [
            {
                "id": f"P{i:03d}",
                "text": f"prop {i}",
                "location": f"main.tex:L{i}",
                "containing_block": "sec:setup",
                "claim_type": "claim",
                "asserts": [],
                "mathematical_objects": [],
                "cites": [],
                "evidence_class": "derived",
            }
            for i in range(1, 6)
        ],
    )

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = run_migrator(main, "--out-dir", out_dir, "--emit-map", out_dir / "map.json")
    assert result.returncode == 0, result.stderr

    audit_map = json.loads((out_dir / "map.json").read_text())
    # Audit map keyed by source-file basename → mapping
    assert "main.jsonl" in audit_map
    mapping = audit_map["main.jsonl"]
    assert len(mapping) == 5

    for old_id in (f"P{i:03d}" for i in range(1, 6)):
        assert old_id in mapping, f"audit map missing {old_id}"
        new_uuid = mapping[old_id]
        assert UUID_V7_REGEX.match(new_uuid), (
            f"value for {old_id} is not a canonical UUID v7: {new_uuid}"
        )

    # All UUIDs must be unique
    assert len(set(mapping.values())) == 5, "UUIDs are not unique"


def test_cites_re_pointed_within_file(tmp_path: Path) -> None:
    """Each cites entry MUST be re-pointed to the migrated UUID of its target."""
    src = tmp_path / "main.jsonl"
    write_jsonl(
        src,
        [
            {
                "id": "P001",
                "text": "axiom",
                "location": "main.tex:L1",
                "containing_block": "sec:setup",
                "claim_type": "axiom",
                "asserts": [],
                "mathematical_objects": [],
                "cites": [],
                "evidence_class": "conventional",
            },
            {
                "id": "P002",
                "text": "from axiom",
                "location": "main.tex:L2",
                "containing_block": "sec:setup",
                "claim_type": "claim",
                "asserts": [],
                "mathematical_objects": [],
                "cites": ["P001"],
                "evidence_class": "derived",
            },
        ],
    )

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = run_migrator(src, "--out-dir", out_dir, "--emit-map", out_dir / "map.json")
    assert result.returncode == 0, result.stderr

    migrated_lines = [
        json.loads(ln)
        for ln in (out_dir / "main.jsonl").read_text().splitlines()
        if ln.strip()
    ]
    audit_map = json.loads((out_dir / "map.json").read_text())["main.jsonl"]

    # P001's new UUID is what P002 must now cite
    assert migrated_lines[1]["cites"] == [audit_map["P001"]]
    # And the cite must round-trip through UUID v7 format
    assert UUID_V7_REGEX.match(migrated_lines[1]["cites"][0])


def test_cross_file_cites_re_pointed(tmp_path: Path) -> None:
    """Phase 2 pilot props citing Phase 1 baseline ids MUST resolve across files."""
    main = tmp_path / "main.jsonl"
    pilot = tmp_path / "theorem1.jsonl"
    write_jsonl(
        main,
        [
            {
                "id": "P037",
                "text": "main axiom",
                "location": "main.tex:L37",
                "containing_block": "sec:setup",
                "claim_type": "axiom",
                "asserts": [],
                "mathematical_objects": [],
                "cites": [],
                "evidence_class": "conventional",
            }
        ],
    )
    write_jsonl(
        pilot,
        [
            {
                "id": "C001",
                "text": "uses axiom",
                "location": "main.tex:L466",
                "containing_block": "theorem:thm:eta-s",
                "claim_type": "claim",
                "asserts": [],
                "mathematical_objects": [],
                "cites": ["P037"],
                "evidence_class": "derived",
            }
        ],
    )

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = run_migrator(
        main, pilot, "--out-dir", out_dir, "--emit-map", out_dir / "map.json"
    )
    assert result.returncode == 0, result.stderr

    audit_map = json.loads((out_dir / "map.json").read_text())
    main_map = audit_map["main.jsonl"]
    pilot_lines = [
        json.loads(ln)
        for ln in (out_dir / "theorem1.jsonl").read_text().splitlines()
        if ln.strip()
    ]

    # C001's cite to "P037" must now be the UUID for P037 (cross-file resolved)
    assert pilot_lines[0]["cites"] == [main_map["P037"]]


def test_unresolved_cite_aborts_with_non_zero(tmp_path: Path) -> None:
    """A cites entry referencing an id not present in any input MUST abort."""
    src = tmp_path / "main.jsonl"
    write_jsonl(
        src,
        [
            {
                "id": "P001",
                "text": "dangling cite",
                "location": "main.tex:L1",
                "containing_block": "sec:setup",
                "claim_type": "claim",
                "asserts": [],
                "mathematical_objects": [],
                "cites": ["P999"],
                "evidence_class": "derived",
            }
        ],
    )

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = run_migrator(src, "--out-dir", out_dir, "--emit-map", out_dir / "map.json")
    assert result.returncode != 0, "expected non-zero exit on dangling cite"
    assert "P999" in result.stderr


def test_invalid_old_id_format_aborts_with_non_zero(tmp_path: Path) -> None:
    """An id that does not match P<NNN> or C<NNN> MUST abort."""
    src = tmp_path / "main.jsonl"
    write_jsonl(
        src,
        [
            {
                "id": "not-a-prefix-id",
                "text": "bad",
                "location": "main.tex:L1",
                "containing_block": "sec:setup",
                "claim_type": "claim",
                "asserts": [],
                "mathematical_objects": [],
                "cites": [],
                "evidence_class": "derived",
            }
        ],
    )

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = run_migrator(src, "--out-dir", out_dir, "--emit-map", out_dir / "map.json")
    assert result.returncode != 0
