"""ParaBank REST API tests — transfers.

The validation tests are xfail(strict=True): probing the live API showed it
happily accepts zero, negative, and same-account transfers with HTTP 200.
These are real defects in the application under test; strict xfail makes the
suite flag the moment ParaBank fixes them.
"""
import allure
import pytest

from utils.parabank_api import ParabankApi


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
    api: ParabankApi, account_pair: tuple[int, int]
) -> None:
    from_id, to_id = account_pair
    with allure.step("Read the source balance before the transfer"):
        balance_before = api.get_account(from_id).json()["balance"]

    api.transfer(from_id, to_id, amount="5.00")

    with allure.step("Verify the source balance dropped by exactly 5.00"):
        balance_after = api.get_account(from_id).json()["balance"]
        assert balance_after == pytest.approx(balance_before - 5.00, abs=0.01), (
            f"Source balance should drop by 5.00: "
            f"before={balance_before}, after={balance_after}"
        )


@pytest.mark.api
def test_transfer_without_amount_returns_error(
    api: ParabankApi, account_pair: tuple[int, int]
) -> None:
    from_id, to_id = account_pair
    response = api.transfer(from_id, to_id, amount="")
    with allure.step("Verify the API responds with an error status"):
        assert response.status_code >= 400, f"Expected an error, got {response.status_code}"


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known ParaBank defect: API accepts zero-amount transfers with HTTP 200",
    strict=True,
)
def test_transfer_zero_amount_is_rejected(
    api: ParabankApi, account_pair: tuple[int, int]
) -> None:
    from_id, to_id = account_pair
    response = api.transfer(from_id, to_id, amount="0")
    with allure.step("Verify the API rejects a zero-amount transfer"):
        assert response.status_code >= 400


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known ParaBank defect: API accepts negative-amount transfers with HTTP 200",
    strict=True,
)
def test_transfer_negative_amount_is_rejected(
    api: ParabankApi, account_pair: tuple[int, int]
) -> None:
    from_id, to_id = account_pair
    response = api.transfer(from_id, to_id, amount="-10")
    with allure.step("Verify the API rejects a negative-amount transfer"):
        assert response.status_code >= 400


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known ParaBank defect: API accepts transfers to the same account with HTTP 200",
    strict=True,
)
def test_transfer_to_same_account_is_rejected(
    api: ParabankApi, account_pair: tuple[int, int]
) -> None:
    from_id, _ = account_pair
    response = api.transfer(from_id, from_id, amount="10")
    with allure.step("Verify the API rejects a same-account transfer"):
        assert response.status_code >= 400
