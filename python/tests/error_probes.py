"""The requests that make ParaBank show a user an error.

Shared by the deterministic gate (`tests/api/test_error_messages.py`) and the
AI lane (`tests/ai/test_message_judge_lane.py`) so both sweep exactly the same
messages: a probe added here is judged in both places, with no second table to
keep in step.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from _pytest.mark.structures import ParameterSet

from utils.parabank_api import ParabankApi

# (customer_id, funded account id)
Customer = tuple[int, int]
Probe = Callable[[ParabankApi, Customer], str]


def _unknown_account_deposit(api: ParabankApi, _: Customer) -> str:
    return api.deposit(999999, "10.00").text


def _unknown_account_get(api: ParabankApi, _: Customer) -> str:
    return api.get_account(999999).text


def _unknown_customer_get(api: ParabankApi, _: Customer) -> str:
    return api.get_customer(999999).text


def _unknown_position_history(api: ParabankApi, _: Customer) -> str:
    return api.get_position_history(999999, "01-01-2020", "01-01-2026").text


def _transfer_to_unknown_account(api: ParabankApi, customer: Customer) -> str:
    return api.transfer(customer[1], 999999, "1.00").text


def _loan_zero_amount(api: ParabankApi, customer: Customer) -> str:
    return api.request_loan(customer[0], "0", "0", customer[1]).text


def _loan_empty_amount(api: ParabankApi, customer: Customer) -> str:
    return api.request_loan(customer[0], "", "", customer[1]).text


def _update_customer(api: ParabankApi, customer: Customer) -> str:
    return api.update_customer(customer[0], firstName="Renamed").text


@dataclass(frozen=True)
class ErrorProbe:
    """One request that makes ParaBank show the user an error."""

    id: str
    call: Probe
    known_leak: str | None = None
    """Defect id and summary when this message is a documented leak.
    None means the message must be clean."""


PROBES: tuple[ErrorProbe, ...] = (
    ErrorProbe("deposit-to-unknown-account", _unknown_account_deposit),
    ErrorProbe("get-unknown-account", _unknown_account_get),
    ErrorProbe("get-unknown-customer", _unknown_customer_get),
    ErrorProbe("history-of-unknown-position", _unknown_position_history),
    ErrorProbe("transfer-to-unknown-account", _transfer_to_unknown_account),
    ErrorProbe(
        "loan-zero-amount",
        _loan_zero_amount,
        "Known defect D-20: a zero loan amount answers with the raw Java message '/ by zero'",
    ),
    ErrorProbe(
        "loan-empty-amount",
        _loan_empty_amount,
        "Known defect D-23: an empty loan amount answers with a raw 'Cannot invoke ...' "
        "NullPointerException message",
    ),
    ErrorProbe(
        "update-customer",
        _update_customer,
        "Known defect D-10: updateCustomer always answers with the internal-error page",
    ),
)


def probe_params() -> list[ParameterSet]:
    """`PROBES` as pytest params, documented leaks carrying their strict xfail."""
    return [
        pytest.param(
            probe,
            id=probe.id,
            marks=[pytest.mark.xfail(strict=True, reason=probe.known_leak)]
            if probe.known_leak
            else [],
        )
        for probe in PROBES
    ]
