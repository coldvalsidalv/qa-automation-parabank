"""AI lane: the LLM judges the same messages the deterministic gate sweeps.

Opt-in (`pytest -m ai_judge`, needs a running Ollama) because an LLM is not a
CI oracle — a model that answers differently on two runs would make the gate
flap. The gate in `tests/api/test_error_messages.py` stays deterministic and
keeps running everywhere.

Opt-in, but not optional once opted in: asking for this lane and getting a
green run that judged nothing is worse than an error. A missing model fails
here rather than skipping. The ambient AI features are the opposite case and
still degrade quietly — AI_ANALYSIS and SELF_HEAL run inside gating suites and
must not fail a build because a side feature is offline.

What this lane adds is the two questions `SIGNATURES` cannot answer:

* **A leak the list has not seen.** The list recognises fragments; the model
  generalises. A leak it finds that the list misses is a real finding, and the
  fix is to promote the fragment into `SIGNATURES` — after which everyone
  catches it deterministically, with no model running.
* **Is the message actionable?** Nothing in a substring list can tell whether a
  customer could act on the text. A message that leaks nothing and still leaves
  the user stuck is a usability defect the gate is blind to by construction.

So the model proposes and the checked-in code decides — the lane's output is
work for the engineer, not a verdict shipped straight to CI.
"""

import allure
import pytest

from ai.llm import LLMUnavailable, require_available
from ai.message_judge import judge, signature_leaks
from tests.error_probes import PROBES, Customer, ErrorProbe
from utils.parabank_api import ParabankApi

pytestmark = [
    allure.feature("Error messages"),
    allure.story("LLM judge of user-facing errors"),
    pytest.mark.ai_judge,
]


@pytest.fixture(scope="module", autouse=True)
def require_llm() -> None:
    """Fail the whole lane once, with a fixable message, if no model answers.

    Module-scoped so the check costs one call rather than one per case, and
    autouse so a case cannot quietly bypass it.
    """
    try:
        require_available()
        return
    except LLMUnavailable as exc:
        # Held and re-raised outside the handler: calling pytest.fail in here
        # chains the original exception, and pytest then shows its bare message
        # ("Connection refused") in place of the one that says what to do.
        reason = str(exc)
    pytest.fail(f"The ai_judge lane needs a model and found none.\n{reason}", pytrace=False)


@pytest.mark.parametrize("probe", PROBES, ids=[p.id for p in PROBES])
def test_llm_finds_no_leak_the_signature_list_misses(
    message_api: ParabankApi, error_customer: Customer, probe: ErrorProbe
) -> None:
    """A leak the model sees and the list does not is a signature to add."""
    message = probe.call(message_api, error_customer)
    verdict = judge(message, context=probe.id)
    # The model answered the preflight, so falling back here means it failed or
    # answered malformed JSON mid-run — a judgement that did not happen, not a
    # reason to report the case as inapplicable.
    assert verdict.source == "llm", f"The model did not produce a verdict: {verdict.reason}"

    allure.attach(f"{verdict.reason}\n\nsource={verdict.source}", name=f"LLM verdict: {probe.id}")

    already_known = bool(signature_leaks(message))
    with allure.step("Verify the LLM found nothing the signature list missed"):
        assert not (verdict.leaks_internals and not already_known), (
            f"The LLM judged this message as leaking internals, and "
            f"ai.message_judge.SIGNATURES does not catch it — add the fragment.\n"
            f"  message: {message[:400]!r}\n"
            f"  reason:  {verdict.reason}"
        )


@pytest.mark.parametrize("probe", PROBES, ids=[p.id for p in PROBES])
def test_error_message_is_actionable_for_a_customer(
    message_api: ParabankApi, error_customer: Customer, probe: ErrorProbe
) -> None:
    """The question no substring list can answer.

    Documented leaks are expected to read as unactionable — that is what the
    defect *is* — so they are excluded rather than reported again here.
    """
    if probe.known_leak:
        pytest.skip(f"Documented leak, unactionable by definition: {probe.known_leak}")

    message = probe.call(message_api, error_customer)
    verdict = judge(message, context=probe.id)
    assert verdict.source == "llm", f"The model did not produce a verdict: {verdict.reason}"

    with allure.step("Verify a non-technical customer could act on the message"):
        assert verdict.actionable, (
            f"The message tells the customer nothing they can act on.\n"
            f"  message: {message[:400]!r}\n"
            f"  reason:  {verdict.reason}"
        )
