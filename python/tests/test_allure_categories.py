"""Guard: every documented defect must land in its Allure report category.

`conftest._write_allure_categories` writes a "Known ParaBank defects (xfail)"
bucket whose `messageRegex` is matched against each xfail's status message. That
regex has no test of its own and fails *silently*: a reason worded slightly
differently just drops into the uncategorised pile, the report still renders,
and the run is still green. That is exactly what happened — matching on the word
"known" quietly excluded all four xfails in `test_security_api.py`, whose
reasons read "Defect D-09" rather than "Known defect D-09".

Matching mirrors allure2's `CategoriesPlugin`:

    Pattern.compile(pattern, Pattern.DOTALL).matcher(message).matches()

so `re.DOTALL` plus `fullmatch` — a *full* match (hence the wrapping `.*` in the
regexes) over a message where `.` already spans newlines (hence no `(?s)`).

Scope, honestly stated: this checks our regex against our reasons. It cannot
catch allure2 changing how it matches, or allure-pytest changing the message
format. It deliberately does not assume the `"XFAIL "` prefix beyond using a
representative message, so it keeps working if that prefix ever changes.
"""

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest

import conftest

TESTS_DIR = Path(__file__).resolve().parent
KNOWN_DEFECTS_CATEGORY = "Known ParaBank defects (xfail)"

pytestmark = [pytest.mark.unit, pytest.mark.smoke]


def _xfail_reasons() -> tuple[list[tuple[str, str, str]], list[str]]:
    """Every `xfail(reason=...)` in the suite as (file, test, reason).

    Also returns the markers whose reason is missing or not a literal. Those are
    reported rather than skipped: silently ignoring what it cannot parse is how
    a guard like this rots into always-green.
    """
    reasons: list[tuple[str, str, str]] = []
    unreadable: list[str] = []
    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            for decorator in getattr(node, "decorator_list", []):
                if not isinstance(decorator, ast.Call):
                    continue
                if "xfail" not in ast.unparse(decorator.func):
                    continue
                where = f"{path.name}::{getattr(node, 'name', '?')}"
                keywords = {kw.arg: kw.value for kw in decorator.keywords}
                if "reason" not in keywords:
                    unreadable.append(f"{where} (no reason= given)")
                    continue
                try:
                    reasons.append(
                        (
                            path.name,
                            str(getattr(node, "name", "?")),
                            str(ast.literal_eval(keywords["reason"])),
                        )
                    )
                except ValueError:
                    unreadable.append(f"{where} (reason is not a literal)")
    return reasons, unreadable


def _categories(tmp_path: Path) -> list[dict[str, Any]]:
    """The categories exactly as conftest writes them for a real run."""
    conftest._write_allure_categories(tmp_path)
    loaded = json.loads((tmp_path / "categories.json").read_text(encoding="utf-8"))
    assert isinstance(loaded, list) and loaded, "conftest wrote no categories"
    return [dict(entry) for entry in loaded]


def _allure_matches(pattern: str, message: str) -> bool:
    """Replicate allure2 CategoriesPlugin.matches (DOTALL + full match)."""
    return re.compile(pattern, re.DOTALL).fullmatch(message) is not None


def test_every_xfail_reason_lands_in_the_known_defects_category(tmp_path: Path) -> None:
    reasons, unreadable = _xfail_reasons()
    assert not unreadable, (
        "every xfail must carry a literal reason= so it can be categorised and "
        f"read in the report; offenders: {unreadable}"
    )
    # Non-vacuity: if the extractor stops finding markers (a refactor, a new way
    # of spelling xfail), the assertion below would pass over an empty list and
    # this guard would go quietly useless.
    assert len(reasons) > 20, (
        f"expected the suite's documented defects, found only {len(reasons)} xfail "
        "reasons — the extractor is probably no longer matching how they are written"
    )

    category = next(c for c in _categories(tmp_path) if c["name"] == KNOWN_DEFECTS_CATEGORY)
    uncategorised = [
        f"{file}::{test} — {reason!r}"
        for file, test, reason in reasons
        if not _allure_matches(category["messageRegex"], f"XFAIL {reason}\n\ntraceback")
    ]
    assert not uncategorised, (
        f"these xfails do not match {category['messageRegex']!r} and would land in the "
        "report's uncategorised pile instead of "
        f"{KNOWN_DEFECTS_CATEGORY!r}:\n  " + "\n  ".join(uncategorised)
    )


def test_every_category_regex_compiles(tmp_path: Path) -> None:
    """An invalid regex makes the Allure generator throw at report time, long
    after the test run has gone green."""
    broken = []
    for category in _categories(tmp_path):
        pattern = category.get("messageRegex")
        if pattern is None:
            continue
        try:
            re.compile(pattern)
        except re.error as exc:
            broken.append(f"{category['name']}: {pattern!r} ({exc})")
    assert not broken, "invalid messageRegex in categories.json:\n  " + "\n  ".join(broken)
