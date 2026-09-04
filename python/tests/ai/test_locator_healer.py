"""Unit tests for ai/locator_healer.py — the SELF_HEAL candidate-selection logic.

No Ollama, no browser: `complete_json` is monkeypatched and the page is a stub
whose `locator(sel).count()` is driven by a dict.

This module previously had zero coverage. Its only exercise was
`tests/ui/test_ai_showcase.py::test_self_healing_demo`, which skips unless
SELF_HEAL=true *and* a live Ollama is reachable, and which the default run
excludes via the `ai_demo` marker — so every branch below (the uniqueness gate,
malformed-candidate handling, invalid-selector recovery, graceful degradation)
ran in CI exactly never.
"""

from typing import Any, cast

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from ai import locator_healer

pytestmark = [pytest.mark.unit, pytest.mark.smoke]


class _FakeLocator:
    """Defers every failure to `count()`, like the real Locator.

    Verified against Playwright 1.60 with a live Chromium page: `locator()`
    itself never raises — `locator(None)`, `locator(42)` and `locator("")` all
    construct fine and then fail inside `count()` with `Error` ("expected
    string, got undefined" / "got number" / "Unexpected token"). Modelling that
    faithfully matters: it is what makes the `except PlaywrightError` branch in
    `heal_locator` the thing that actually absorbs a malformed suggestion.
    """

    def __init__(self, selector: Any, counts: dict[str, Any]) -> None:
        self._selector = selector
        self._counts = counts

    def count(self) -> int:
        if not isinstance(self._selector, str):
            raise PlaywrightError(
                f"Locator.count: selector: expected string, got {type(self._selector).__name__}"
            )
        if not self._selector:
            raise PlaywrightError('Locator.count: Unexpected token "" while parsing css selector')
        configured = self._counts.get(self._selector, 0)
        if configured is PlaywrightError:
            raise PlaywrightError("Locator.count: Unexpected token while parsing css selector")
        assert isinstance(configured, int)
        return configured


class _FakePage:
    """Stub page: `counts` maps a selector to the number of elements it matches.

    A selector mapped to the `PlaywrightError` class raises on `count()`, which
    is how Playwright reports syntactically invalid selector strings.
    """

    def __init__(self, counts: dict[str, Any]) -> None:
        self.counts = counts
        self.queried: list[Any] = []

    def locator(self, selector: Any) -> _FakeLocator:
        self.queried.append(selector)
        return _FakeLocator(selector, self.counts)


def _respond_with(monkeypatch: pytest.MonkeyPatch, payload: Any) -> None:
    monkeypatch.setattr(locator_healer, "complete_json", lambda *_a, **_kw: payload)


def _selectors(*names: Any) -> dict[str, Any]:
    return {"selectors": [{"selector": name} for name in names]}


def _heal(page: _FakePage, html: str = "<html/>") -> str | None:
    """Run `heal_locator` against the stub page.

    `heal_locator` is typed against Playwright's `Page`; the stub implements
    only the single method it actually calls, so the cast is confined here
    instead of being repeated at every call site.
    """
    return locator_healer.heal_locator(cast(Page, page), "Log In button", html)


def test_returns_the_first_selector_matching_exactly_one_element(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _respond_with(monkeypatch, _selectors("#nope", "#found", "#also-found"))
    page = _FakePage({"#found": 1, "#also-found": 1})

    assert _heal(page) == "#found"


def test_skips_a_candidate_that_matches_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _respond_with(monkeypatch, _selectors("#missing", "#present"))
    page = _FakePage({"#present": 1})

    assert _heal(page) == "#present"
    assert page.queried == ["#missing", "#present"]


def test_rejects_an_ambiguous_candidate_and_moves_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 2-match selector must never be returned.

    This is the whole point of the `count() == 1` gate: binding to "whichever
    element matched first" would drive the action at an arbitrary element while
    the Allure report still reads as a clean heal.
    """
    _respond_with(monkeypatch, _selectors("input", "#unique"))
    page = _FakePage({"input": 2, "#unique": 1})

    assert _heal(page) == "#unique"


def test_returns_none_when_every_candidate_is_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    _respond_with(monkeypatch, _selectors("input", "a"))
    page = _FakePage({"input": 2, "a": 7})

    assert _heal(page) is None


def test_skips_a_syntactically_invalid_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    _respond_with(monkeypatch, _selectors("<<<garbage", "#good"))
    page = _FakePage({"<<<garbage": PlaywrightError, "#good": 1})

    assert _heal(page) == "#good"


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {"selectors": ["#bare-string", {"selector": "#good"}]}, id="candidate-not-object"
        ),
        pytest.param(
            {"selectors": [{"css": "#wrong-key"}, {"selector": "#good"}]}, id="missing-key"
        ),
        pytest.param(
            {"selectors": [{"selector": None}, {"selector": "#good"}]}, id="selector-null"
        ),
        pytest.param({"selectors": [{"selector": ""}, {"selector": "#good"}]}, id="selector-empty"),
        pytest.param(
            {"selectors": [{"selector": 42}, {"selector": "#good"}]}, id="selector-not-string"
        ),
    ],
)
def test_skips_malformed_candidates(monkeypatch: pytest.MonkeyPatch, payload: Any) -> None:
    """A local model returns loosely-shaped JSON; a bad entry must not abort healing."""
    _respond_with(monkeypatch, payload)
    page = _FakePage({"#good": 1})

    assert _heal(page) == "#good"
    # The shape guards must reject the bad entry *before* it reaches the page.
    # Without this the test still passes with those guards deleted, because the
    # `except PlaywrightError` fallback quietly absorbs the resulting failure —
    # a wasted round trip per candidate, and the guards' intent unverified.
    assert page.queried == ["#good"], f"malformed candidate reached the page: {page.queried}"


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({}, id="no-selectors-key"),
        pytest.param({"selectors": None}, id="selectors-null"),
        pytest.param({"selectors": []}, id="selectors-empty"),
    ],
)
def test_returns_none_when_the_model_suggests_nothing(
    monkeypatch: pytest.MonkeyPatch, payload: Any
) -> None:
    _respond_with(monkeypatch, payload)

    assert _heal(_FakePage({})) is None


def test_returns_none_when_the_response_is_not_an_object(monkeypatch: pytest.MonkeyPatch) -> None:
    """`complete_json` is typed `dict | list`; a list has no "selectors"."""
    _respond_with(monkeypatch, [{"selector": "#good"}])
    page = _FakePage({"#good": 1})

    assert _heal(page) is None
    assert page.queried == [], "must not probe the page for a malformed response"


def test_degrades_gracefully_when_the_llm_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """SELF_HEAL must never turn an unreachable Ollama into a test error."""

    def _raise(*_args: object, **_kwargs: object) -> dict:
        raise ConnectionError("Ollama unreachable")

    monkeypatch.setattr(locator_healer, "complete_json", _raise)

    assert _heal(_FakePage({})) is None


def test_html_context_is_truncated_before_reaching_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Oversized markup must be clipped to MAX_HTML_CHARS, not sent whole."""
    seen: dict[str, str] = {}

    def _capture(_system: str, user_message: str, *_a: object, **_kw: object) -> dict:
        seen["user"] = user_message
        return {"selectors": []}

    monkeypatch.setattr(locator_healer, "complete_json", _capture)
    marker = "<div id='needle'></div>"
    oversized = "y" * locator_healer.MAX_HTML_CHARS + marker

    _heal(_FakePage({}), oversized)

    assert oversized not in seen["user"], "full oversized markup reached the model"
    assert marker not in seen["user"], "content past MAX_HTML_CHARS was not clipped"
    assert "y" * locator_healer.MAX_HTML_CHARS in seen["user"]
