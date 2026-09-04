"""Guard: tool versions pinned in two places must move together.

Two versions in this repo are written down twice, and nothing else notices when
the copies disagree:

* **ruff** — `python/uv.lock` (what CI runs via `uv run ruff`) and the
  `ruff-pre-commit` hook rev in `.pre-commit-config.yaml` (what a developer's
  commit hook runs). CI never invokes pre-commit, so a drift here is invisible
  to it: you get a hook that passes locally and a CI job that fails, or the
  reverse.
* **playwright** — `python/uv.lock` (the client library) and the base image tag
  in `python/Dockerfile` (the preinstalled browsers). The Dockerfile already
  says "Image version must match the playwright version pinned in uv.lock" —
  this turns that comment into something enforced. CI installs browsers with
  `playwright install` and never builds the image, so a drift here is likewise
  invisible to it and only bites whoever runs `docker compose run tests`.

Dependabot updates each side from a *different* ecosystem (`uv`, `pre-commit`,
`docker`), which means separate pull requests that can be merged apart or land
out of order. That is exactly how the copies drift, so these assertions are the
backstop rather than the primary mechanism.

These are plain unit tests: no app, no network, no browser, so they run in every
invocation of the suite including the PR smoke gate.
"""

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
UV_LOCK = REPO_ROOT / "python" / "uv.lock"
PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
DOCKERFILE = REPO_ROOT / "python" / "Dockerfile"

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
    locked = tomllib.loads(UV_LOCK.read_text(encoding="utf-8"))["package"]
    versions = [entry["version"] for entry in locked if entry["name"] == package]
    assert len(versions) == 1, (
        f"expected exactly one {package!r} entry in python/uv.lock, found {versions}"
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
        f"expected exactly one {what} in {path.relative_to(REPO_ROOT)}, found {matches}. "
        "The pin was moved, renamed or reformatted — fix this guard so it keeps "
        "checking, do not delete it."
    )
    return str(matches[0])


def test_ruff_pre_commit_hook_matches_the_lockfile() -> None:
    locked = _locked_version("ruff")
    hook = _sole_match(RUFF_HOOK_REV, PRE_COMMIT_CONFIG, "ruff-pre-commit rev")
    assert hook == locked, (
        f"ruff version drift: .pre-commit-config.yaml pins v{hook}, "
        f"python/uv.lock pins {locked}. CI lints with the lockfile's version while "
        "the commit hook uses its own, so the two disagree about what passes. "
        "Bump the hook rev to match the lock (they are updated by separate "
        "Dependabot ecosystems and arrive as separate PRs)."
    )


def test_playwright_docker_image_matches_the_lockfile() -> None:
    locked = _locked_version("playwright")
    image = _sole_match(PLAYWRIGHT_IMAGE_TAG, DOCKERFILE, "playwright base image tag")
    assert image == locked, (
        f"playwright version drift: python/Dockerfile uses the v{image} base image, "
        f"python/uv.lock pins the {locked} client. The image ships the browsers the "
        "client drives, so a mismatch breaks `docker compose run tests` while CI — "
        "which runs `playwright install` instead of building the image — stays green."
    )
