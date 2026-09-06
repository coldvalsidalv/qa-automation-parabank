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

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ai import llm

AI_DIR = Path(llm.__file__).resolve().parent

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


def _prompt_names_used_in_the_code() -> list[str]:
    """Every literal name passed to `load_prompt(...)` anywhere in `ai/`.

    Derived from the source rather than listed by hand. A hardcoded list cannot
    detect the case this check is named for — a new feature calling
    `load_prompt("summarize")` without adding the file would leave the list, and
    the test, untouched. Same approach as `tests/test_allure_categories.py`,
    which extracts xfail markers by AST for the same reason.
    """
    names: list[str] = []
    for path in sorted(AI_DIR.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            if ast.unparse(node.func).rsplit(".", 1)[-1] != "load_prompt":
                continue
            if node.args and isinstance(node.args[0], ast.Constant):
                names.append(str(node.args[0].value))
    return sorted(set(names))


def test_every_prompt_referenced_by_the_code_exists_and_is_non_empty() -> None:
    """A missing prompt file is a FileNotFoundError at the first AI call, which
    the callers' broad excepts turn into a silent no-op."""
    names = _prompt_names_used_in_the_code()
    # Non-vacuity: with an empty list the loop below asserts nothing, so a
    # refactor that changes how prompts are loaded would leave this test green
    # while checking no files at all.
    assert names, (
        f"found no load_prompt(...) calls under {AI_DIR.name}/ — the extractor no "
        "longer matches how prompts are loaded, fix it rather than deleting it"
    )
    missing = []
    for name in names:
        # load_prompt *raises* on a missing file, so calling it inside a
        # comprehension would surface a bare FileNotFoundError and hide which
        # name and which caller are at fault.
        try:
            if not llm.load_prompt(name).strip():
                missing.append(f"{name} (file is empty)")
        except FileNotFoundError:
            missing.append(f"{name} (no such file in ai/prompts/)")
    assert not missing, (
        "the code loads prompts that are not on disk; add the file rather than "
        f"removing the call: {missing}"
    )


def test_load_prompt_raises_for_an_unknown_name() -> None:
    with pytest.raises(FileNotFoundError):
        llm.load_prompt("no_such_prompt")


# --- preflight ---------------------------------------------------------------
#
# `require_available` is what makes the explicitly requested AI entry points
# fail loudly instead of producing an empty report that reads like a clean one.
# Its messages have to name the fix, because being told "unavailable" without
# knowing which of the two causes it is leaves you guessing.


class _Model:
    def __init__(self, ident: str) -> None:
        self.id = ident


def _installed(
    monkeypatch: pytest.MonkeyPatch, *names: str, base_url: str = "http://stub/v1"
) -> None:
    class _Models:
        def list(self) -> Any:
            return SimpleNamespace(data=[_Model(n) for n in names])

    monkeypatch.setattr(
        llm, "_client", lambda: SimpleNamespace(models=_Models(), base_url=base_url)
    )


def test_require_available_passes_when_the_model_is_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    _installed(monkeypatch, "llama3.1:8b", "other:7b")
    llm.require_available()  # must not raise


def test_an_unreachable_server_says_how_to_start_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """The endpoint named is the client's own, not the environment's.

    `_client` is cached, so a process that changed OLLAMA_BASE_URL after first
    use would otherwise be told to start a server at an address nothing
    contacted — the one thing this message exists to get right.
    """
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://never-contacted:1/v1")

    class _Models:
        def list(self) -> Any:
            raise ConnectionError("connection refused")

    monkeypatch.setattr(
        llm,
        "_client",
        lambda: SimpleNamespace(models=_Models(), base_url="http://127.0.0.1:9/v1"),
    )

    with pytest.raises(llm.LLMUnavailable) as excinfo:
        llm.require_available()
    message = str(excinfo.value)
    assert "http://127.0.0.1:9/v1" in message, "the message must name the endpoint it tried"
    assert "never-contacted" not in message, "the stale environment value must not be reported"
    assert "ollama serve" in message


def test_a_missing_model_is_distinguished_from_a_missing_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A running Ollama without the model pulled is the other common cause, and
    telling the two apart is the difference between a one-command fix and a
    debugging session."""
    monkeypatch.setenv("OLLAMA_MODEL", "absent:1b")
    _installed(monkeypatch, "llama3.1:8b", base_url="http://stub/v1")

    with pytest.raises(llm.LLMUnavailable) as excinfo:
        llm.require_available()
    message = str(excinfo.value)
    assert "is up but" in message
    assert "llama3.1:8b" in message, "the message must list what is installed"
    assert "ollama pull absent:1b" in message
