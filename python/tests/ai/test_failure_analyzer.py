"""Unit tests for the AI_ANALYSIS degrade-gracefully contract.

No Ollama, no network, no browser: these exercise ai/failure_analyzer.py
directly by mocking ai.llm.complete, so the fallback behavior documented in
CLAUDE.md ("must degrade gracefully when Ollama unreachable") is actually
verified instead of only exercised incidentally through ai_demo runs.
"""

import pytest

from ai import failure_analyzer

pytestmark = [pytest.mark.unit, pytest.mark.smoke]


def test_analyze_failure_returns_the_llm_diagnosis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        failure_analyzer, "complete", lambda *_a, **_kw: "root cause: stale locator"
    )

    result = failure_analyzer.analyze_failure("tests/ui/test_login.py::test_x", "Timeout 30000ms")

    assert result == "root cause: stale locator"


def test_analyze_failure_degrades_gracefully_when_llm_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(*_args: object, **_kwargs: object) -> str:
        raise ConnectionError("Ollama unreachable")

    monkeypatch.setattr(failure_analyzer, "complete", _raise)

    result = failure_analyzer.analyze_failure("tests/ui/test_login.py::test_x", "Timeout 30000ms")

    assert result == "AI analysis unavailable: Ollama unreachable"
