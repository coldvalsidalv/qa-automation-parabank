"""Unit tests for ai/test_generator.py — the offline test-case-draft helper.

Not part of the pytest run in any AI demo (it is a standalone CLI, not wired
into conftest.py or any page object), so without this it had zero coverage.
Mocks complete_json — no Ollama needed.
"""

import pytest

from ai import test_generator

pytestmark = [pytest.mark.unit, pytest.mark.smoke]


def test_generate_test_cases_returns_the_parsed_list(monkeypatch: pytest.MonkeyPatch) -> None:
    cases = [{"title": "Transfer with empty amount", "steps": ["..."]}]
    monkeypatch.setattr(test_generator, "complete_json", lambda *_a, **_kw: cases)

    result = test_generator.generate_test_cases("Transfer page description")

    assert result == cases


def test_generate_test_cases_rejects_a_non_list_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(test_generator, "complete_json", lambda *_a, **_kw: {"not": "a list"})

    with pytest.raises(ValueError, match="Expected a JSON array"):
        test_generator.generate_test_cases("Transfer page description")
