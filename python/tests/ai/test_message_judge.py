"""Unit tests for ai/message_judge.py. No Ollama, no app, no browser.

The signature cases are the real messages captured from a live ParaBank —
`/ by zero` and the `Cannot invoke ...` NullPointerException on one side,
`Could not find account number 999999` on the other. That distinction is the
whole point of the gate: a message may name a business entity the user typed
and still be clean.

`judge`'s fallback matters as much as its happy path. When Ollama is down the
gate must not silently become a coin flip, so the fallback answers with what
the deterministic layer can prove and labels the verdict `source="signatures"`
for callers to see.
"""

from typing import Any

import pytest

from ai import message_judge
from ai.message_judge import Verdict, judge, signature_leaks

pytestmark = [pytest.mark.unit, pytest.mark.smoke]

LEAKING = """Cannot invoke "java.math.BigDecimal.compareTo(java.math.BigDecimal)" because \
the return value of "com.parasoft.parabank.domain.LoanRequest.getDownPayment()" is null"""


@pytest.mark.parametrize(
    ("message", "expected_leak"),
    [
        pytest.param("/ by zero", True, id="raw-arithmetic-exception"),
        pytest.param(LEAKING, True, id="npe-with-package-paths"),
        pytest.param(
            "An internal error has occurred and has been logged.", True, id="internal-error-page"
        ),
        pytest.param("Could not find account number 999999", False, id="names-a-business-entity"),
        pytest.param("Could not find customer #999999", False, id="names-a-customer-id"),
        pytest.param("The amount cannot be empty.", False, id="plain-validation-message"),
        pytest.param("", False, id="empty-body"),
    ],
)
def test_signature_leaks_separates_internals_from_business_detail(
    message: str, expected_leak: bool
) -> None:
    assert bool(signature_leaks(message)) is expected_leak


def test_signature_matching_is_case_insensitive() -> None:
    assert signature_leaks("caused by a nullpointerEXCEPTION here")


def test_judge_returns_the_models_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(*_: Any, **__: Any) -> dict:
        return {"leaks_internals": True, "actionable": False, "reason": "raw exception text"}

    monkeypatch.setattr(message_judge, "complete_json", fake)
    monkeypatch.setattr(message_judge, "load_prompt", lambda _: "prompt")

    assert judge("/ by zero", "ctx") == Verdict(
        leaks_internals=True, actionable=False, reason="raw exception text", source="llm"
    )


@pytest.mark.parametrize(
    ("response", "why"),
    [
        pytest.param(["not", "an", "object"], "a list is not a verdict", id="list"),
        pytest.param({"actionable": True}, "leaks_internals missing", id="missing-field"),
        pytest.param(
            {"leaks_internals": "yes", "actionable": True},
            "a string is not a boolean verdict",
            id="non-boolean-field",
        ),
    ],
)
def test_malformed_model_output_falls_back_to_signatures(
    monkeypatch: pytest.MonkeyPatch, response: Any, why: str
) -> None:
    monkeypatch.setattr(message_judge, "complete_json", lambda *a, **k: response)
    monkeypatch.setattr(message_judge, "load_prompt", lambda _: "prompt")

    verdict = judge("/ by zero", "ctx")
    assert verdict.source == "signatures", why
    assert verdict.leaks_internals, "the signature layer still catches this one"


def test_unreachable_model_falls_back_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: Any, **__: Any) -> dict:
        raise ConnectionError("connection refused")

    monkeypatch.setattr(message_judge, "complete_json", boom)
    monkeypatch.setattr(message_judge, "load_prompt", lambda _: "prompt")

    verdict = judge(LEAKING, "ctx")
    assert verdict.source == "signatures"
    assert verdict.leaks_internals
    assert "connection refused" in verdict.reason


def test_fallback_does_not_invent_an_unactionable_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actionability is unknowable without the model, so the fallback abstains.

    Reporting `actionable=False` here would manufacture a usability finding out
    of the LLM merely being down — a failure mode worse than the missing check.
    """
    monkeypatch.setattr(
        message_judge, "complete_json", lambda *a, **k: (_ for _ in ()).throw(OSError("down"))
    )
    monkeypatch.setattr(message_judge, "load_prompt", lambda _: "prompt")

    assert judge("Could not find account number 999999", "ctx").actionable is True
