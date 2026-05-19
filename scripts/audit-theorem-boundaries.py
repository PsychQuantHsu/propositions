#!/usr/bin/env python3
"""LaTeX theorem-env boundary audit (#98 prevention layer).

Mechanically lists every numbered theorem-like environment in main.tex with its
real begin/end line range and nearest preceding \\label, so that proposition
extractors stop guessing "intuitive statement end" and use the physical
`\\end{theorem}` boundary (root cause of #97 pilot misjudgment).

Modes
-----
- ``--format text`` (default): human-readable table
- ``--format md``:              markdown table for ``_stage3_baseline.md``
- ``--format json``:            machine-readable env inventory
- ``--jsonl <path>``:           cross-check mode. For every prop in the JSONL,
                                resolve its ``containing_block`` prefix to an env
                                and assert ``prop.location`` falls within the
                                real env line range. Exit 1 on any mismatch.

LaTeX env parsing is shared with ``scripts/validate-propositions.py`` R9 via
``scripts/_lib/latex_env_parser.py`` (#115 M-5 dedup). Edge case semantics
documented there.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# #115 R-1 mitigation: insert script dir on sys.path BEFORE importing from
# _lib, so cross-cwd invocation (`python /path/to/scripts/audit-...py …` from
# anywhere) resolves `_lib` relative to the script, not the caller's cwd.
sys.path.insert(0, str(Path(__file__).parent))

from _lib.latex_env_parser import (  # noqa: E402  (sys.path setup must precede)
    build_associated,
    normalize_containing_block,
    parse_envs,
    parse_location,
)


def emit_text(envs: list[dict]) -> str:
    out: list[str] = []
    out.append(f"{'type':<12} {'begin':>6} {'end':>6}  label")
    out.append("-" * 60)
    for e in envs:
        label = e.get("label") or "(no-label)"
        out.append(f"{e['type']:<12} {e['begin_line']:>6} {e['end_line']:>6}  {label}")
    return "\n".join(out)


def emit_md(envs: list[dict]) -> str:
    out: list[str] = []
    out.append("| label | type | begin | end | line count |")
    out.append("|-------|------|-------|-----|------------|")
    for e in envs:
        label = e.get("label") or "(no-label)"
        count = e["end_line"] - e["begin_line"] + 1
        out.append(
            f"| `{label}` | {e['type']} | L{e['begin_line']} | L{e['end_line']} | {count} |"
        )
    return "\n".join(out)


def emit_json(envs: list[dict]) -> str:
    return json.dumps(envs, indent=2)


def crosscheck(envs: list[dict], jsonl_path: Path) -> tuple[int, list[str]]:
    """Return (mismatch_count, mismatch_descriptions).

    For each prop with a resolvable ``containing_block`` and ``location``:
    - Find the env whose ``label`` equals the normalized cb.
    - Map env's covered range to (statement env range) ∪ (its proof env range,
      if any with label ``"Proof of <label>"`` or sibling-proof following).
    - Assert location range ⊆ allowed range.
    """
    # #115 M-5: reuse shared `build_associated` instead of inline loop.
    associated = build_associated(envs)

    mismatches: list[str] = []
    seen = 0
    skipped_no_cb_or_loc = 0
    skipped_unresolvable_cb = 0
    total = 0
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                prop = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            cb_raw = prop.get("containing_block", "")
            loc_raw = prop.get("location", "")
            if not cb_raw or not loc_raw:
                skipped_no_cb_or_loc += 1
                continue
            label = normalize_containing_block(cb_raw)
            if label not in associated:
                # cb doesn't resolve to a known env (e.g. discussion/*, sec:*).
                # Track count for visibility (per /idd-verify #98 Codex finding:
                # 103/321 main.jsonl props silently skipped was invisible
                # without this summary line).
                skipped_unresolvable_cb += 1
                continue
            seen += 1
            loc_range = parse_location(loc_raw)
            if loc_range is None:
                continue
            l_start, l_end = loc_range
            # Check location falls within any of the associated env ranges
            allowed = associated[label]
            ok = any(
                env["begin_line"] <= l_start and l_end <= env["end_line"]
                for env in allowed
            )
            if not ok:
                allowed_str = ", ".join(
                    f"{env['type']}:L{env['begin_line']}-L{env['end_line']}"
                    for env in allowed
                )
                mismatches.append(
                    f"prop {prop.get('id','?')} containing_block={cb_raw!r} "
                    f"location={loc_raw} not in [{allowed_str}]"
                )
    # Stash summary in a sentinel-shaped first element of mismatches so main()
    # can render it without changing the return signature. Use a leading
    # "[summary]" prefix; main() pulls and prints separately.
    summary = (
        f"[summary] total={total} checked={seen} "
        f"skipped_no_cb_or_loc={skipped_no_cb_or_loc} "
        f"skipped_unresolvable_cb={skipped_unresolvable_cb} "
        f"mismatches={len(mismatches)}"
    )
    return len(mismatches), [summary] + mismatches


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("tex_path", type=Path, help="manuscript/main.tex")
    p.add_argument(
        "--format",
        choices=("text", "md", "json"),
        default="text",
        help="Inventory output format (ignored when --jsonl is set)",
    )
    p.add_argument(
        "--jsonl",
        type=Path,
        default=None,
        help="Cross-check this JSONL's props against envs (exits 1 on mismatch)",
    )
    args = p.parse_args(argv)

    if not args.tex_path.exists():
        print(f"error: {args.tex_path} not found", file=sys.stderr)
        return 2
    tex_text = args.tex_path.read_text(encoding="utf-8")
    # Audit script is the CI-gate caller: keep `warn_on_residue=True` (default)
    # so unmatched \begin surfaces in stderr.
    envs = parse_envs(tex_text)

    if args.jsonl is not None:
        if not args.jsonl.exists():
            print(f"error: {args.jsonl} not found", file=sys.stderr)
            return 2
        n_mismatch, descriptions = crosscheck(envs, args.jsonl)
        # First entry is the [summary] sentinel
        summary, real_descriptions = descriptions[0], descriptions[1:]
        if n_mismatch == 0:
            print(f"OK: 0 mismatches in {args.jsonl}")
            print(f"  {summary}")
            return 0
        print(f"FAIL: {n_mismatch} mismatch(es) in {args.jsonl}")
        print(f"  {summary}")
        for desc in real_descriptions:
            print(f"  - {desc}")
        return 1

    if args.format == "text":
        print(emit_text(envs))
    elif args.format == "md":
        print(emit_md(envs))
    elif args.format == "json":
        print(emit_json(envs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
