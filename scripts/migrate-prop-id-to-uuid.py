#!/usr/bin/env python3
"""Migrate proposition JSONL identifiers from sequential P/C-prefix to deterministic UUID v7.

Part of Spectra change `migrate-prop-id-to-stable-uuid` (Task 1.1).

Inputs: one or more JSONL files whose props use legacy `P<NNN>` or `C<NNN>` ids.
Outputs:
- One migrated JSONL per input (written into --out-dir, basename preserved).
- One audit map JSON (--emit-map) keyed by input basename, mapping each old id
  to the assigned UUID v7 string.

Determinism: UUID v7 generation is seeded by `(basename, old_id)` through
SHA-256 with a fixed base timestamp. Running the script twice on the same input
produces byte-identical outputs and audit maps.

UUID v7 layout (RFC 9562 §5.7):
  48-bit big-endian unix_ts_ms | 4-bit ver=7 | 12-bit rand_a |
  2-bit var=0b10                | 62-bit rand_b
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ID_REGEX = re.compile(r"^[PC]\d{3,}$")
# Fixed base timestamp (ms since unix epoch): 2026-05-14T00:00:00Z, the change
# merge intent date. Documented in design.md Risks/Trade-offs.
BASE_TIMESTAMP_MS = 1778889600000


def deterministic_uuid_v7(basename: str, old_id: str) -> str:
    """Generate a UUID v7-formatted string deterministically from inputs.

    The returned string is canonically formatted (8-4-4-4-12 lowercased hex)
    with version field `7` and the IETF variant (top two bits `10`).
    """
    seed = f"{basename}::{old_id}".encode()
    digest = hashlib.sha256(seed).digest()

    ts = BASE_TIMESTAMP_MS & 0xFFFFFFFFFFFF  # 48 bits
    rand_a = int.from_bytes(digest[0:2], "big") & 0x0FFF  # 12 bits
    rand_b = int.from_bytes(digest[2:10], "big") & 0x3FFFFFFFFFFFFFFF  # 62 bits

    high = (ts << 16) | (0x7 << 12) | rand_a
    low = (0b10 << 62) | rand_b

    h = high.to_bytes(8, "big").hex()
    l = low.to_bytes(8, "big").hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{l[0:4]}-{l[4:16]}"


def read_jsonl(path: Path) -> list[dict]:
    out = []
    for ln in path.read_text().splitlines():
        if ln.strip():
            out.append(json.loads(ln))
    return out


def build_id_map(input_files: list[Path]) -> dict[str, dict[str, str]]:
    """Build {basename: {old_id: new_uuid}} for every input file.

    Validates that each old id matches the P/C-prefix regex. Raises ValueError on
    the first invalid id encountered.
    """
    id_map: dict[str, dict[str, str]] = {}
    for path in input_files:
        props = read_jsonl(path)
        per_file: dict[str, str] = {}
        for line_idx, prop in enumerate(props, start=1):
            old_id = prop.get("id")
            if not isinstance(old_id, str) or not ID_REGEX.match(old_id):
                raise ValueError(
                    f"{path}:{line_idx}: id field {old_id!r} does not match P/C-prefix regex"
                )
            if old_id in per_file:
                raise ValueError(
                    f"{path}:{line_idx}: duplicate id {old_id!r} within file"
                )
            per_file[old_id] = deterministic_uuid_v7(path.name, old_id)
        id_map[path.name] = per_file
    return id_map


def resolve_cite(old_cite: str, id_map: dict[str, dict[str, str]]) -> str | None:
    """Look up a cite reference across every file's mapping.

    Returns the migrated UUID for the first file whose mapping contains the old id,
    or None when no file resolves the cite.
    """
    for per_file in id_map.values():
        if old_cite in per_file:
            return per_file[old_cite]
    return None


def migrate_file(path: Path, id_map: dict[str, dict[str, str]], out_dir: Path) -> None:
    """Rewrite one JSONL file into out_dir, swapping ids and cites for UUIDs."""
    props = read_jsonl(path)
    per_file = id_map[path.name]
    out_lines: list[str] = []
    for line_idx, prop in enumerate(props, start=1):
        new = dict(prop)
        new["id"] = per_file[prop["id"]]
        if "cites" in prop and prop["cites"]:
            migrated_cites: list[str] = []
            for old_cite in prop["cites"]:
                resolved = resolve_cite(old_cite, id_map)
                if resolved is None:
                    raise ValueError(
                        f"{path}:{line_idx}: cite {old_cite!r} does not resolve to any prop id"
                    )
                migrated_cites.append(resolved)
            new["cites"] = migrated_cites
        out_lines.append(json.dumps(new, ensure_ascii=False, sort_keys=False))
    out_path = out_dir / path.name
    out_path.write_text("\n".join(out_lines) + "\n")


def emit_map(id_map: dict[str, dict[str, str]], map_path: Path) -> None:
    """Write the audit map JSON with deterministic key order."""
    serializable = {
        basename: dict(sorted(mapping.items())) for basename, mapping in sorted(id_map.items())
    }
    map_path.write_text(json.dumps(serializable, indent=2, ensure_ascii=False) + "\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="JSONL files to migrate")
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="directory to write migrated JSONL files (basenames preserved)",
    )
    parser.add_argument(
        "--emit-map",
        type=Path,
        required=True,
        help="path to write the audit map JSON",
    )
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.emit_map.parent.mkdir(parents=True, exist_ok=True)

    try:
        id_map = build_id_map(args.inputs)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for path in args.inputs:
        try:
            migrate_file(path, id_map, args.out_dir)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    emit_map(id_map, args.emit_map)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
