"""Unit tests for ai/llm.py — the single entry point to the LLM.

No Ollama, no network: the OpenAI client is replaced by a stub that records the
arguments it was called with and returns a canned message.

This module had no tests, which mattered more than the line count suggests. Its
one piece of real logic — stripping the markdown fence a local model wraps JSON
in — sits directly under `ai/locator_healer.py`, which catches every exception
from `complete_json` and returns `None`. A bug in the stripping therefore does
not surface as a failure: SELF_HEAL silently stops healing while the suite stays
green. `test_malformed_json_raises_for_the_caller_to_handle` pins the contract
that makes that degradation deliberate rather than accidental.

Not covered on purpose: a response consisting of a bare "```" with no newline
raises IndexError rather than a JSON error. `complete_json` always calls the API
with `json_mode=True`, which constrains decoding to valid JSON, so the model
cannot produce it — and both callers treat any exception the same way.
"""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from ai import llm

pytestmark = [pytest.mark.unit, pytest.mark.smoke]


class _FakeClient:
    """Stands in for `OpenAI`, recording the create() kwargs."""

    def __init__(self, content: str | None) -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _stub(monkeypatch: pytest.MonkeyPatch, content: str | None) -> _FakeClient:
    client = _FakeClient(content)
    monkeypatch.setattr(llm, "_client", lambda: client)
    return client


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------


def test_complete_returns_the_message_content(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, "the diagnosis")

    assert llm.complete("system", "user") == "the diagnosis"


def test_complete_returns_empty_string_when_content_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refusal or a filtered response arrives as `content=None`."""
    _stub(monkeypatch, None)

    assert llm.complete("system", "user") == ""


def test_complete_sends_the_system_and_user_messages_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _stub(monkeypatch, "ok")

    llm.complete("SYS", "USR")

    assert client.calls[0]["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USR"},
    ]


def test_json_mode_constrains_decoding(monkeypatch: pytest.MonkeyPatch) -> None:
    """`format=json` is what actually guarantees JSON — the prompt alone does not."""
    client = _stub(monkeypatch, "{}")

    llm.complete("system", "user", json_mode=True)

    assert client.calls[0]["response_format"] == {"type": "json_object"}


def test_response_format_is_omitted_when_not_in_json_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omit, not None: passing None would be sent as an explicit null."""
    from openai import omit

    client = _stub(monkeypatch, "prose")

    llm.complete("system", "user")

    assert client.calls[0]["response_format"] is omit


def test_temperature_is_zero_for_reproducibility(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _stub(monkeypatch, "ok")

    llm.complete("system", "user")

    assert client.calls[0]["temperature"] == 0


def test_max_tokens_is_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _stub(monkeypatch, "ok")

    llm.complete("system", "user", max_tokens=77)

    assert client.calls[0]["max_tokens"] == 77


# ---------------------------------------------------------------------------
# complete_json() — the fence stripping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param('{"selectors": []}', id="plain"),
        pytest.param('```json\n{"selectors": []}\n```', id="json-fence"),
        pytest.param('```\n{"selectors": []}\n```', id="bare-fence"),
        pytest.param('  \n ```json\n{"selectors": []}\n```  \n', id="surrounded-by-whitespace"),
    ],
)
def test_complete_json_parses_fenced_and_unfenced_objects(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """Local models wrap JSON in a code fence despite being told not to."""
    _stub(monkeypatch, raw)

    assert llm.complete_json("system", "user") == {"selectors": []}


def test_complete_json_parses_a_top_level_array(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ai/test_generator.py` expects a list, so both shapes must survive."""
    _stub(monkeypatch, '```json\n[{"title": "a case"}]\n```')

    assert llm.complete_json("system", "user") == [{"title": "a case"}]


def test_complete_json_requests_json_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _stub(monkeypatch, "{}")

    llm.complete_json("system", "user")

    assert client.calls[0]["response_format"] == {"type": "json_object"}


def test_malformed_json_raises_for_the_caller_to_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The contract `ai/locator_healer.py` relies on.

    It catches this and returns None — healing is skipped, the run stays green.
    That degradation is only safe because the failure is an exception here and
    not a silently empty result.
    """
    _stub(monkeypatch, "not json at all")

    with pytest.raises(json.JSONDecodeError):
        llm.complete_json("system", "user")


# ---------------------------------------------------------------------------
# load_prompt()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["analyze_failure", "generate_tests", "heal_locator"])
def test_every_prompt_referenced_by_the_code_exists_and_is_non_empty(name: str) -> None:
    """A missing prompt file is a FileNotFoundError at the first AI call, which
    the callers' broad excepts would turn into a silent no-op."""
    assert llm.load_prompt(name).strip()


def test_load_prompt_raises_for_an_unknown_name() -> None:
    with pytest.raises(FileNotFoundError):
        llm.load_prompt("no_such_prompt")
