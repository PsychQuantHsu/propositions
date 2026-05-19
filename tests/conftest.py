"""pytest configuration for the propositions plugin standalone test suite.

The original test file expected to run from inside a manuscript repo with
`manuscript/main.tex` + `propositions/_smoke_tests/*` available. In the
plugin standalone context, those paths don't exist. Two strategies:

1. Tests referencing `propositions/_smoke_tests/*`: fixture symlink
   (we copy the smoke_tests directory into the plugin and expose it at
   `tests/fixtures/_smoke_tests/`; the conftest creates a session-scoped
   symlink to match the legacy `propositions/_smoke_tests/` path).
2. Tests referencing `manuscript/main.tex`: skip — these are integration
   tests against a real paper; they pass when the plugin is run from
   inside a manuscript repo.

Run only the standalone-passing tests via:

    pytest tests/ -m "not integration"
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def _ensure_legacy_smoke_test_path() -> None:
    """Symlink `manuscript/propositions/_smoke_tests/` -> `tests/fixtures/_smoke_tests/`.

    Tests use the path `REPO_ROOT / "manuscript" / "propositions" / "_smoke_tests"`
    which assumes a manuscript-repo layout. In standalone plugin context we
    expose the fixtures at that path via symlink so tests don't need patching.
    """
    src = PLUGIN_ROOT / "tests" / "fixtures" / "_smoke_tests"
    if not src.exists():
        return  # fixtures not copied in; tests that need them will fail/skip naturally
    legacy_dir = PLUGIN_ROOT / "manuscript" / "propositions"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_link = legacy_dir / "_smoke_tests"
    if legacy_link.exists() or legacy_link.is_symlink():
        return  # already wired
    try:
        legacy_link.symlink_to(src, target_is_directory=True)
    except OSError:
        # filesystem doesn't support symlinks — caller will see the test fail
        # with a clearer downstream error
        pass


_ensure_legacy_smoke_test_path()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests that need a real manuscript checkout.

    These tests are kept in the suite so they pass when the plugin is invoked
    from inside a manuscript repo (the original development context), but they
    require `manuscript/main.tex` which doesn't exist in the standalone plugin.
    """
    manuscript_tex = PLUGIN_ROOT / "manuscript" / "main.tex"
    if manuscript_tex.exists():
        return  # caller IS in manuscript context; let tests run

    needs_manuscript = pytest.mark.skip(
        reason="needs manuscript/main.tex — integration test, run from a manuscript repo"
    )
    integration_test_names = {
        "test_inventory_main_tex",
        "test_format_md_emits_table",
    }
    for item in items:
        if item.name in integration_test_names:
            item.add_marker(needs_manuscript)
