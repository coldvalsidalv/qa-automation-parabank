"""Unit tests for ai/api_fuzzer.py. No Ollama, no app.

The model's proposals are mocked; what is tested is everything that decides
whether a response counts as a finding — the part that must be right for a
report to mean anything.

`is_healthy` gets the most attention because the first version of the fuzzer
did not have it: ParaBank degrades once a few faults pass through it, after
which every response is the same HTML 500, and a sweep without a health check
blamed sixteen innocent cases for damage the first two had done.
"""

from typing import Any

import httpx
import pytest

from ai import api_fuzzer
from ai.api_fuzzer import Endpoint, SweepResult, as_markdown, classify, fuzz, propose_cases

pytestmark = [pytest.mark.unit, pytest.mark.smoke]

ENDPOINT = Endpoint(
    name="deposit",
    path="/deposit",
    method="POST",
    parameters="accountId (int), amount (decimal string)",
    valid_params={"accountId": "1", "amount": "1.00"},
    fixed_params={"accountId": "1"},
)

LEAKING_BODY = '"/ by zero"'


def _response(status: int, body: str = "") -> httpx.Response:
    return httpx.Response(status, text=body, request=httpx.Request("POST", "http://x/deposit"))


@pytest.mark.parametrize(
    ("status", "body", "is_finding"),
    [
        pytest.param(500, "boom", True, id="server-crash"),
        pytest.param(503, "", True, id="any-5xx"),
        pytest.param(400, LEAKING_BODY, True, id="4xx-that-leaks-internals"),
        pytest.param(400, "Could not find account number 999999", False, id="clean-rejection"),
        pytest.param(200, "Successfully deposited $1.00", False, id="accepted"),
    ],
)
def test_classify_reports_crashes_and_leaks_but_not_plain_rejections(
    status: int, body: str, is_finding: bool
) -> None:
    """A 4xx is the correct answer to bad input, so it is not a finding on its
    own — but a 4xx whose body leaks implementation detail still is."""
    assert (classify(_response(status, body)) is not None) is is_finding


@pytest.mark.parametrize(
    "junk",
    [
        pytest.param([], id="array-instead-of-object"),
        pytest.param({"cases": "not a list"}, id="cases-not-a-list"),
        pytest.param({"nope": []}, id="no-cases-key"),
        pytest.param({"cases": ["not an object", 3]}, id="cases-are-not-objects"),
        pytest.param({"cases": [{"name": "x", "params": "amount=-1"}]}, id="params-is-a-string"),
        pytest.param({"cases": [{"name": "x", "params": [1, 2]}]}, id="params-is-a-list"),
    ],
)
def test_propose_cases_survives_malformed_model_output(
    monkeypatch: pytest.MonkeyPatch, junk: Any
) -> None:
    """A case whose `params` is not a map is dropped, not carried into the sweep.

    Merging a string or a list into the fixed params raises TypeError, which is
    not an `httpx.HTTPError` — it would escape `run_case` and abort the whole
    sweep, discarding every finding collected before it.
    """
    monkeypatch.setattr(api_fuzzer, "load_prompt", lambda _: "prompt")
    monkeypatch.setattr(api_fuzzer, "complete_json", lambda *a, **k: junk)
    assert propose_cases(ENDPOINT) == []


def test_an_unreachable_model_yields_no_cases_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ollama being down must not take the sweep's earlier findings with it."""

    def boom(*_: Any, **__: Any) -> dict:
        raise ConnectionError("connection refused")

    monkeypatch.setattr(api_fuzzer, "load_prompt", lambda _: "prompt")
    monkeypatch.setattr(api_fuzzer, "complete_json", boom)
    assert propose_cases(ENDPOINT) == []


def test_non_scalar_parameter_values_are_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """httpx cannot encode a nested object as a query parameter."""
    monkeypatch.setattr(api_fuzzer, "load_prompt", lambda _: "prompt")
    monkeypatch.setattr(
        api_fuzzer,
        "complete_json",
        lambda *a, **k: {
            "cases": [{"name": "x", "params": {"amount": {"nested": 1}, "accountId": 7}}]
        },
    )
    assert propose_cases(ENDPOINT) == [
        {"name": "x", "params": {"amount": {"nested": 1}, "accountId": 7}}
    ]
    assert api_fuzzer._case_params(propose_cases(ENDPOINT)[0]) == {"accountId": "7"}


def _fuzz_against(monkeypatch: pytest.MonkeyPatch, cases: list[dict], handler: Any) -> SweepResult:
    monkeypatch.setattr(api_fuzzer, "load_prompt", lambda _: "prompt")
    monkeypatch.setattr(api_fuzzer, "complete_json", lambda *a, **k: {"cases": cases})
    real_client = httpx.Client

    def fake_client(**kwargs: Any) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(**kwargs)

    monkeypatch.setattr(api_fuzzer.httpx, "Client", fake_client)
    return fuzz("http://app", [ENDPOINT])


def test_sweep_stops_when_the_server_stops_recovering(monkeypatch: pytest.MonkeyPatch) -> None:
    """One bad case, then a server that answers everything with a 500.

    Only the case that actually broke it may be reported; the rest would be
    inheriting its damage.
    """
    broken = {"healthy": True}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("amount") == "1.00" and broken["healthy"]:
            return httpx.Response(200, text="Successfully deposited")
        broken["healthy"] = False
        return httpx.Response(500, text="internal")

    result = _fuzz_against(
        monkeypatch,
        [
            {"name": "first", "params": {"amount": "-1"}, "why": "sign"},
            {"name": "second", "params": {"amount": "abc"}, "why": "type"},
            {"name": "third", "params": {"amount": "1e5"}, "why": "format"},
        ],
        handler,
    )

    assert [f.case for f in result.findings] == ["first"], (
        "cases after the server stopped recovering must not be reported"
    )
    assert result.degraded_after == "deposit — first"


def test_a_healthy_server_lets_the_whole_sweep_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("amount") == "1.00":
            return httpx.Response(200, text="Successfully deposited")
        return httpx.Response(500, text="internal")

    result = _fuzz_against(
        monkeypatch,
        [
            {"name": "first", "params": {"amount": "-1"}, "why": "sign"},
            {"name": "second", "params": {"amount": "abc"}, "why": "type"},
        ],
        handler,
    )

    assert [f.case for f in result.findings] == ["first", "second"]
    assert result.degraded_after is None


def test_fixed_params_are_supplied_and_a_case_may_drop_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitting a parameter is a distinct case from sending it empty — D-14
    crashes on both, and the sweep has to be able to express each."""
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(200, text="Successfully deposited")

    _fuzz_against(monkeypatch, [{"name": "absent amount", "params": {}, "why": "x"}], handler)

    assert seen[-1] == {"accountId": "1"}, "the case sent no amount, and none was invented"


def test_report_says_when_it_stopped_early() -> None:
    report = as_markdown(SweepResult([], degraded_after="deposit — first"), [ENDPOINT])
    assert "stopped early" in report
    assert "deposit — first" in report


def test_report_of_a_clean_sweep_says_so() -> None:
    report = as_markdown(SweepResult([]), [ENDPOINT])
    assert "No findings this run." in report
    assert "stopped early" not in report
