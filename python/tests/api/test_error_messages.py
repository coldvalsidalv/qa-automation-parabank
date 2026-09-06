"""Every error ParaBank shows a user must stay free of implementation detail.

A sweep, not one test per defect. The suite already documents the individual
leaks (D-10, D-20, D-23); what this adds is the general property, so an
endpoint that *starts* leaking is caught without anyone having written a test
for it first.

The gate is deterministic: `ai.message_judge.SIGNATURES` is a list of
fragments, each observed in a real ParaBank response. No model runs here, so
the check never flakes and needs no Ollama.

The AI lane (`tests/ai/test_message_judge_lane.py`, marker `ai_judge`) asks the
LLM the question the list cannot answer — is the message actionable, and does
it leak something not yet in the list. A leak found there is promoted into
SIGNATURES, and from then on everyone catches it deterministically.
"""

import allure
import pytest

from ai.message_judge import signature_leaks
from tests.error_probes import Customer, ErrorProbe, probe_params
from utils.parabank_api import ParabankApi

pytestmark = [
    allure.feature("Error messages"),
    allure.story("User-facing errors leak no internals"),
    allure.severity(allure.severity_level.NORMAL),
    pytest.mark.api,
]


@pytest.mark.parametrize("probe", probe_params())
def test_error_message_leaks_no_internals(
    message_api: ParabankApi, error_customer: Customer, probe: ErrorProbe
) -> None:
    message = probe.call(message_api, error_customer)
    leaks = signature_leaks(message)
    with allure.step("Verify the message carries no implementation detail"):
        assert not leaks, f"The message shown to the user contains {leaks}: {message[:400]!r}"
