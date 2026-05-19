#!/usr/bin/env python3
"""Migrate proposition storage from single JSON to _meta.json + JSONL.

Splits a Phase 1 propositions JSON file into:
- `<stem>_meta.json` (or fixed `_meta.json` for main): schema_version + source
  + coverage + axioms + any other root-level metadata field
- `<stem>.jsonl`: one proposition per line, in original order

Proposition ordering is the JSONL file line order itself — no ordinal
fields are stored.

Usage:
    python3 scripts/migrate-json-to-jsonl.py <input.json> [--meta-out PATH] [--jsonl-out PATH] [--delete-input]

If --meta-out / --jsonl-out omitted, defaults derived from input path:
- `foo.json` → `foo_meta.json` + `foo.jsonl`
- `main.json` (special) → `_meta.json` + `main.jsonl` in the same dir

Refs PsychQuantHsu/psychophysical_representations#77 (Phase 2 prep)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def resolve_output_paths(
    input_path: Path,
    meta_out: Path | None,
    jsonl_out: Path | None,
) -> tuple[Path, Path]:
    """Derive _meta.json + .jsonl paths from input path when not explicit."""
    parent = input_path.parent
    stem = input_path.stem  # filename without extension

    if jsonl_out is None:
        jsonl_out = parent / f"{stem}.jsonl"

    if meta_out is None:
        # Special case: main.json → _meta.json (matches schema convention)
        if stem == "main":
            meta_out = parent / "_meta.json"
        else:
            meta_out = parent / f"{stem}_meta.json"

    return meta_out, jsonl_out


def migrate(
    input_path: Path,
    meta_out: Path,
    jsonl_out: Path,
) -> tuple[int, int]:
    """Read input JSON, write _meta.json + .jsonl.

    Returns (prop_count, meta_keys_count).
    """
    with input_path.open() as fp:
        data = json.load(fp)

    if "propositions" not in data:
        raise ValueError(f"{input_path}: no 'propositions' key at root")

    props = data.pop("propositions")
    if not isinstance(props, list):
        raise ValueError(f"{input_path}: 'propositions' must be a list")

    # Write metadata sidecar (everything except propositions)
    with meta_out.open("w") as fp:
        json.dump(data, fp, indent=2, ensure_ascii=False)
        fp.write("\n")

    # Write JSONL (one prop per line, no pretty-printing — single line each)
    with jsonl_out.open("w") as fp:
        for p in props:
            fp.write(json.dumps(p, ensure_ascii=False) + "\n")

    return len(props), len(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="input JSON file")
    parser.add_argument("--meta-out", type=Path, help="output _meta.json path")
    parser.add_argument("--jsonl-out", type=Path, help="output .jsonl path")
    parser.add_argument(
        "--delete-input",
        action="store_true",
        help="delete the input JSON after successful migration",
    )
    args = parser.parse_args()

    # Defense-in-depth path validation (#86): the input is consumed by
    # migrate() AND optionally deleted via --delete-input. Without these
    # guards, an attacker (or careless caller) with shell access could pass
    # /etc/passwd.json or ../../etc/X.json and pivot to arbitrary-file delete
    # via --delete-input. Real-world exploitability is low (shell access
    # required), but cheap to gate up-front for CI safety.
    repo_root = Path(__file__).resolve().parent.parent
    input_abs = args.input.resolve()
    try:
        input_abs.relative_to(repo_root)
    except ValueError:
        print(
            f"error: input must be inside repo: {repo_root} (got {input_abs})",
            file=sys.stderr,
        )
        return 2
    if input_abs.suffix != ".json":
        print(
            f"error: input must have .json suffix (got {input_abs.suffix or '<no suffix>'})",
            file=sys.stderr,
        )
        return 2

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    meta_out, jsonl_out = resolve_output_paths(
        args.input, args.meta_out, args.jsonl_out
    )

    try:
        prop_count, meta_keys = migrate(args.input, meta_out, jsonl_out)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"error: migration failed: {e}", file=sys.stderr)
        return 1

    print(f"✓ {args.input} → {jsonl_out} ({prop_count} props)")
    print(f"✓ {args.input} → {meta_out} ({meta_keys} metadata keys)")

    if args.delete_input:
        args.input.unlink()
        print(f"✓ deleted {args.input}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
