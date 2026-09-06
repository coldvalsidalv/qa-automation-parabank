"""Guard: tool versions pinned in two places must move together.

* **ruff** — `python/uv.lock` (what CI runs) and the `ruff-pre-commit` hook rev
  in `.pre-commit-config.yaml` (what a developer's commit hook runs).
* **playwright** — `python/uv.lock` (the client library) and the base image tag
  in `python/Dockerfile` (the preinstalled browsers).

CI invokes neither pre-commit nor the image build, so drift on either pair is
invisible to it: a hook that passes locally and a CI job that fails, or a
`docker compose run tests` that breaks for whoever runs it. Dependabot updates
each side from a different ecosystem (`uv`, `pre-commit`, `docker`), i.e. in
separate PRs that can land apart — which is exactly how the copies drift.

Paths are resolved by walking up from this file rather than by a fixed number
of `.parents[...]` hops: the suite also runs inside its own image, where the
Dockerfile builds with `./python` as context and `COPY . .` into `/app`, so
`uv.lock` sits next to `tests/` instead of one level up.

`.pre-commit-config.yaml` lives at the repository root, outside that build
context, so it is absent from the image entirely. Its test skips when there is
no checkout to inspect, and only then — inside a checkout a missing file is a
failure, so the skip cannot quietly disable the guard where it should run.
"""

import re
import tomllib
from pathlib import Path

import pytest


def _ancestor_containing(*names: str) -> Path | None:
    """Nearest directory at or above this file holding all of `names`."""
    for candidate in Path(__file__).resolve().parents:
        if all((candidate / name).exists() for name in names):
            return candidate
    return None


# Holds uv.lock: `<repo>/python` in a checkout, `/app` inside the image.
PYTHON_DIR = _ancestor_containing("uv.lock", "Dockerfile")
# Only exists in a real checkout — the image never contains the repo root.
REPO_ROOT = _ancestor_containing("docker-compose.yml", ".pre-commit-config.yaml")

pytestmark = [pytest.mark.unit, pytest.mark.smoke]

# Tolerates comment lines between `- repo:` and `rev:` — there are some.
RUFF_HOOK_REV = re.compile(
    r"^\s*-\s*repo:\s*https://github\.com/astral-sh/ruff-pre-commit\s*$"
    r"(?:\n\s*#.*)*"
    r"\n\s*rev:\s*v(\d+\.\d+\.\d+)\s*$",
    re.MULTILINE,
)

PLAYWRIGHT_IMAGE_TAG = re.compile(
    r"^FROM\s+mcr\.microsoft\.com/playwright/python:v(\d+\.\d+\.\d+)-\S+\s*$",
    re.MULTILINE,
)


def _locked_version(package: str) -> str:
    """The version `uv.lock` pins for `package`."""
    assert PYTHON_DIR is not None, (
        "could not find the directory holding uv.lock and Dockerfile above "
        f"{Path(__file__).resolve()} — the project layout changed, fix this guard"
    )
    locked = tomllib.loads((PYTHON_DIR / "uv.lock").read_text(encoding="utf-8"))["package"]
    versions = [entry["version"] for entry in locked if entry["name"] == package]
    assert len(versions) == 1, (
        f"expected exactly one {package!r} entry in uv.lock, found {versions}"
    )
    return str(versions[0])


def _sole_match(pattern: re.Pattern[str], path: Path, what: str) -> str:
    """The single pinned version `pattern` finds in `path`.

    Fails loudly on zero or multiple matches instead of skipping the
    comparison: a guard that quietly finds nothing to compare is worse than no
    guard at all, because it keeps reporting green while the invariant it
    claims to protect goes unchecked.
    """
    matches = pattern.findall(path.read_text(encoding="utf-8"))
    assert len(matches) == 1, (
        f"expected exactly one {what} in {path.name}, found {matches}. "
        "The pin was moved, renamed or reformatted — fix this guard so it keeps "
        "checking, do not delete it."
    )
    return str(matches[0])


def test_ruff_pre_commit_hook_matches_the_lockfile() -> None:
    if REPO_ROOT is None:
        pytest.skip(
            ".pre-commit-config.yaml lives at the repository root, outside the "
            "image's ./python build context, so it cannot be checked from inside "
            "the container; CI runs this from a checkout"
        )
    locked = _locked_version("ruff")
    hook = _sole_match(RUFF_HOOK_REV, REPO_ROOT / ".pre-commit-config.yaml", "ruff-pre-commit rev")
    assert hook == locked, (
        f"ruff version drift: .pre-commit-config.yaml pins v{hook}, "
        f"uv.lock pins {locked}. CI lints with the lockfile's version while "
        "the commit hook uses its own, so the two disagree about what passes. "
        "Bump the hook rev to match the lock (they are updated by separate "
        "Dependabot ecosystems and arrive as separate PRs)."
    )


def test_playwright_docker_image_matches_the_lockfile() -> None:
    locked = _locked_version("playwright")
    assert PYTHON_DIR is not None  # already asserted in _locked_version
    image = _sole_match(PLAYWRIGHT_IMAGE_TAG, PYTHON_DIR / "Dockerfile", "playwright image tag")
    assert image == locked, (
        f"playwright version drift: Dockerfile uses the v{image} base image, "
        f"uv.lock pins the {locked} client. The image ships the browsers the "
        "client drives, so a mismatch breaks `docker compose run tests` while CI — "
        "which runs `playwright install` instead of building the image — stays green."
    )
