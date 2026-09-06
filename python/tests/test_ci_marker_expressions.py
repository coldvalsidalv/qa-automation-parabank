"""Guard: CI must not repeat pyproject's marker deselection.

A `-m` on the command line *overrides* the one in `addopts` rather than
narrowing it, so any deselection CI spells out itself is a second copy of the
`addopts` expression — and the copies drift.

They did. `addopts` learned to exclude `ai_judge` when that lane was added;
`ci.yml` kept its hardcoded `-m "not ai_demo"`, so every push to main pulled
16 tests requiring a local Ollama onto a runner that has none. Pull requests
run `-m smoke` and stayed green, which is why it surfaced only after a merge.

The invariant is therefore narrow and mechanical: a workflow may *select* a
subset (`-m smoke`, or a dispatch input), but it may not spell out what to
exclude. Excluding is `addopts`' job, and there is only one of it.

Like the other repository invariants here, this runs with no app, no browser
and no network.
"""

import re
import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.smoke]


def _ancestor_containing(*names: str) -> Path | None:
    for candidate in Path(__file__).resolve().parents:
        if all((candidate / name).exists() for name in names):
            return candidate
    return None


PYTHON_DIR = _ancestor_containing("pyproject.toml", "conftest.py")
# Workflows live at the repository root, outside the image's ./python build
# context, so they are absent when the suite runs from inside its own image.
REPO_ROOT = _ancestor_containing(".github", "docker-compose.yml")

# `-m expr`, `-m "expr"` or `-m 'expr'` as passed to pytest on a command line.
MARKER_FLAG = re.compile(r"""-m\s+(?:"([^"]*)"|'([^']*)'|(\S+))""")


def _addopts_marker_expression() -> str:
    assert PYTHON_DIR is not None, "pyproject.toml not found by walking up from this file"
    config = tomllib.loads((PYTHON_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    addopts = config["tool"]["pytest"]["ini_options"]["addopts"]
    match = MARKER_FLAG.search(addopts)
    assert match is not None, f"addopts no longer carries a -m expression: {addopts!r}"
    return next(group for group in match.groups() if group is not None)


def test_addopts_still_deselects_the_opt_in_lanes() -> None:
    """The premise of the guard below: exclusion lives in one place."""
    expression = _addopts_marker_expression()
    for marker in ("ai_demo", "ai_judge"):
        assert f"not {marker}" in expression, (
            f"addopts must exclude {marker!r} by default; it reads {expression!r}"
        )


def test_no_workflow_spells_out_its_own_deselection() -> None:
    """A workflow may select a subset, never restate what to exclude."""
    if REPO_ROOT is None:
        pytest.skip("no repository checkout to inspect (running from inside the image)")

    # Both extensions: GitHub loads *.yml and *.yaml alike, and a guard that
    # only knows one of them passes on the workflow it should have caught.
    workflows = sorted(
        path
        for pattern in ("*.yml", "*.yaml")
        for path in (REPO_ROOT / ".github" / "workflows").glob(pattern)
    )
    assert workflows, "no workflows found to check"

    offenders: list[str] = []
    for workflow in workflows:
        for line_number, line in enumerate(
            workflow.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "pytest" not in line or line.lstrip().startswith("#"):
                continue
            for match in MARKER_FLAG.finditer(line):
                expression = next(g for g in match.groups() if g is not None)
                if "not " in expression:
                    offenders.append(f"{workflow.name}:{line_number} passes -m {expression!r}")

    assert not offenders, (
        "These workflows deselect markers themselves, which overrides addopts "
        "instead of narrowing it — the two then drift:\n  " + "\n  ".join(offenders)
    )
