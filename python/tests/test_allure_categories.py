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

There is deliberately **no test that the category regexes compile**. Allure is a
JVM tool — `npx allure-commandline` only installs it — so the patterns are
compiled by `java.util.regex.Pattern`, and validating them with Python's `re`
gives false assurance in both directions: `(?P<code>500).*` compiles here but is
invalid in Java (which spells it `(?<code>...)`), while `\\p{Alpha}+` is valid
Java and raises `re.error` here. A pattern Python cannot compile still fails the
run, via `_allure_matches` below.
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


def _is_xfail(node: ast.expr) -> bool:
    """True for `xfail`, `pytest.mark.xfail`, and anything ending in `.xfail`."""
    return ast.unparse(node).rsplit(".", 1)[-1] == "xfail"


def _xfail_reasons() -> tuple[list[tuple[str, str]], list[str]]:
    """Every xfail marker in the suite as (location, reason).

    Walks *every* call, not only decorators, because an xfail is just as often
    attached to a single parametrised case via
    ``pytest.param(..., marks=pytest.mark.xfail(reason=...))``, where the marker
    is a keyword-argument value rather than an entry in any ``decorator_list``.
    A decorator-only walk silently skipped those, which is precisely the kind of
    blind spot this module exists to prevent.

    Also returns markers whose reason is missing or not a literal, including a
    bare ``@pytest.mark.xfail`` with no call at all. Those are reported rather
    than skipped: silently ignoring what it cannot parse is how a guard like
    this rots into always-green.
    """
    reasons: list[tuple[str, str]] = []
    unreadable: list[str] = []
    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_xfail(node.func):
                continue
            called.add(id(node.func))
            where = f"{path.name}:{node.lineno}"
            keyword = next((kw for kw in node.keywords if kw.arg == "reason"), None)
            if keyword is None:
                unreadable.append(f"{where} (no reason= given)")
                continue
            try:
                reasons.append((where, str(ast.literal_eval(keyword.value))))
            except ValueError:
                unreadable.append(f"{where} (reason is not a literal)")
        # A bare `@pytest.mark.xfail` / `marks=pytest.mark.xfail` is a reference
        # that is never called, so the loop above cannot see it.
        unreadable += [
            f"{path.name}:{node.lineno} (bare xfail marker, no reason= given)"
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute | ast.Name)
            and _is_xfail(node)
            and id(node) not in called
        ]
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
    # Non-vacuity: `not uncategorised` below is vacuously true on an empty list,
    # so an extractor that stops finding markers would leave this guard quietly
    # useless. Deliberately not a count threshold: xfails are *meant* to be
    # deleted as ParaBank fixes defects, so any floor tied to today's number
    # would eventually fail and blame the extractor for the intended cleanup.
    assert reasons, (
        "found no xfail markers at all — the suite documents its defects with "
        "them, so the extractor is no longer matching how they are written"
    )

    categories = _categories(tmp_path)
    category = next((c for c in categories if c["name"] == KNOWN_DEFECTS_CATEGORY), None)
    assert category is not None, (
        f"conftest no longer writes a {KNOWN_DEFECTS_CATEGORY!r} category; it "
        f"writes {[c['name'] for c in categories]}. If it was renamed, update "
        "KNOWN_DEFECTS_CATEGORY here rather than dropping the check."
    )

    uncategorised = [
        f"{where} — {reason!r}"
        for where, reason in reasons
        if not _allure_matches(category["messageRegex"], f"XFAIL {reason}\n\ntraceback")
    ]
    assert not uncategorised, (
        f"these xfails do not match {category['messageRegex']!r} and would land in the "
        "report's uncategorised pile instead of "
        f"{KNOWN_DEFECTS_CATEGORY!r}:\n  " + "\n  ".join(uncategorised)
    )
