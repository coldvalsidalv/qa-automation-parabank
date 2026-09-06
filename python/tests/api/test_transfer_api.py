"""ParaBank REST API tests — transfers.

The validation tests are xfail(strict=True): probing the live API showed it
happily accepts zero, negative, and same-account transfers with HTTP 200.
These are real defects in the application under test; strict xfail makes the
suite flag the moment ParaBank fixes them.

D-14 (found by exploratory testing, widened by the AI fuzzer): a transfer with
the `amount` parameter missing returns HTTP 500 instead of a validation error.
An *empty* amount does the same — this file used to claim otherwise, and the
test below passed only because `>= 400` accepts a 500. `ai/api_fuzzer.py`
reported the empty case on deposit and withdraw, and rechecking transfer showed
it there too.
"""

from collections.abc import Callable

import allure
import httpx
import pytest

from utils.parabank_api import ParabankApi

pytestmark = [
    allure.feature("Transfers"),
    allure.story("Transfer funds (API)"),
    allure.severity(allure.severity_level.CRITICAL),
]


@pytest.mark.smoke
@pytest.mark.api
def test_transfer_valid_amount(api: ParabankApi, account_pair: tuple[int, int]) -> None:
    from_id, to_id = account_pair
    response = api.transfer(from_id, to_id, amount="1.00")
    with allure.step("Verify HTTP 200 and the success message"):
        assert response.status_code == 200, f"Transfer failed: {response.text}"
        assert "Successfully transferred" in response.text


@pytest.mark.api
def test_transfer_moves_money_between_balances(
    api: ParabankApi, isolated_account_factory: Callable[[], int]
) -> None:
    # isolated_account_factory, not account_pair: this asserts an *exact* balance
    # delta on both legs, which only holds if nothing else touches either account
    # between the before/after reads. On the shared, session-scoped account_pair
    # that is true by accident (single process, sequential run) and would break
    # silently under pytest-xdist.
    from_id, to_id = isolated_account_factory(), isolated_account_factory()
    with allure.step("Read both balances before the transfer"):
        source_before = api.get_account(from_id).json()["balance"]
        target_before = api.get_account(to_id).json()["balance"]

    response = api.transfer(from_id, to_id, amount="5.00")

    with allure.step("Verify the transfer was accepted"):
        assert response.status_code == 200, f"Transfer failed: {response.text}"
        assert "Successfully transferred" in response.text

    with allure.step("Verify 5.00 left the source and arrived at the target"):
        source_after = api.get_account(from_id).json()["balance"]
        target_after = api.get_account(to_id).json()["balance"]
        assert source_after == pytest.approx(source_before - 5.00, abs=0.01), (
            f"Source balance should drop by 5.00: before={source_before}, after={source_after}"
        )
        assert target_after == pytest.approx(target_before + 5.00, abs=0.01), (
            f"Target balance should rise by 5.00: before={target_before}, after={target_after}"
        )


@pytest.mark.api
@pytest.mark.xfail(
    strict=True,
    reason="Known defect D-14: an empty amount crashes with 500 instead of a validation error",
)
def test_transfer_with_empty_amount_is_rejected_without_crashing(
    api: ParabankApi, account_pair: tuple[int, int]
) -> None:
    """Asserts a validation error, not merely "not 200".

    The previous `>= 400` was satisfied by the 500 ParaBank actually returns,
    so it reported this endpoint as correct for as long as it existed.
    """
    from_id, to_id = account_pair
    response = api.transfer(from_id, to_id, amount="")
    with allure.step("Verify a validation error, not a server crash"):
        assert 400 <= response.status_code < 500, (
            f"Expected a validation error, got {response.status_code}"
        )


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known defect D-14: missing amount param returns 500, not a validation error",
    strict=True,
)
def test_transfer_missing_amount_param_is_rejected(
    base_url: str, account_pair: tuple[int, int]
) -> None:
    from_id, to_id = account_pair
    with httpx.Client(base_url=f"{base_url}/parabank/services/bank", timeout=30) as client:
        response = client.post("/transfer", params={"fromAccountId": from_id, "toAccountId": to_id})
    with allure.step("Verify a validation error, not a server crash"):
        assert response.status_code < 500


# Three separate defects, one shape: a transfer the API should refuse and
# answers with HTTP 200. Each case keeps its own strict xfail reason, so the
# report still names the individual defect and still alerts if only one of the
# three is fixed.
#
# All three run on `isolated_account_factory` rather than the shared
# `account_pair`. D-02 in particular really does move money, and uniform
# isolation is simpler to reason about than picking a fixture per case — the
# same-account case just uses one of the two accounts twice.
@pytest.mark.api
@pytest.mark.parametrize(
    ("amount", "to_same_account"),
    [
        pytest.param(
            "0",
            False,
            marks=pytest.mark.xfail(
                reason="Known defect D-01: API accepts zero-amount transfers with HTTP 200",
                strict=True,
            ),
            id="zero-amount",
        ),
        pytest.param(
            "-10",
            False,
            marks=pytest.mark.xfail(
                reason="Known defect D-02: API accepts negative-amount transfers with HTTP 200",
                strict=True,
            ),
            id="negative-amount",
        ),
        pytest.param(
            "10",
            True,
            marks=pytest.mark.xfail(
                reason="Known defect D-03: API accepts transfers to the same account with HTTP 200",
                strict=True,
            ),
            id="same-account",
        ),
    ],
)
def test_invalid_transfer_is_rejected(
    api: ParabankApi,
    isolated_account_factory: Callable[[], int],
    amount: str,
    to_same_account: bool,
) -> None:
    from_id = isolated_account_factory()
    to_id = from_id if to_same_account else isolated_account_factory()
    response = api.transfer(from_id, to_id, amount=amount)
    with allure.step(
        f"Verify the API rejects a transfer of {amount} "
        f"{'to the same account' if to_same_account else 'between two accounts'}"
    ):
        assert response.status_code >= 400
