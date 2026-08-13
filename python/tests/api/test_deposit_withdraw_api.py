"""ParaBank REST API tests — deposit and withdrawal.

Defects discovered by probing the live API:
  D-05  Deposit accepts negative amounts (money vanishes from the account).
  D-06  Withdraw accepts amounts exceeding the account balance (no overdraft protection).
  D-07  Withdraw accepts negative amounts (effectively credits the account).
  D-14  Deposit/withdraw crash with HTTP 500 when the amount parameter is missing
        entirely (not just empty), instead of returning a validation error.
  D-15  Deposit accepts non-decimal amount formats (e.g. scientific notation) with
        no validation, silently echoing them back unformatted.
"""

import allure
import httpx
import pytest

from utils.parabank_api import ParabankApi

pytestmark = [
    allure.feature("Transfers"),
    allure.story("Deposit & withdraw API"),
    allure.severity(allure.severity_level.CRITICAL),
]


@pytest.mark.smoke
@pytest.mark.api
def test_deposit_increases_balance(api: ParabankApi, account_pair: tuple[int, int]) -> None:
    acc_id, _ = account_pair
    balance_before = api.get_account(acc_id).json()["balance"]
    api.deposit(acc_id, "100.00")
    balance_after = api.get_account(acc_id).json()["balance"]
    with allure.step("Verify balance increased by exactly 100.00"):
        assert balance_after == pytest.approx(balance_before + 100.00, abs=0.01)


@pytest.mark.api
def test_deposit_returns_success_message(api: ParabankApi, account_pair: tuple[int, int]) -> None:
    acc_id, _ = account_pair
    response = api.deposit(acc_id, "10.00")
    with allure.step("Verify 200 and success text"):
        assert response.status_code == 200
        assert "Successfully deposited" in response.text


@pytest.mark.api
def test_deposit_to_nonexistent_account_returns_error(api: ParabankApi) -> None:
    response = api.deposit(9999999, "10.00")
    with allure.step("Verify non-200 for unknown account"):
        assert response.status_code != 200


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known defect D-05: API accepts negative deposit amounts with HTTP 200",
    strict=True,
)
def test_deposit_negative_amount_is_rejected(api: ParabankApi, isolated_account: int) -> None:
    # isolated_account: D-05 actually goes through, so a shared account would
    # silently lose money on every run.
    response = api.deposit(isolated_account, "-50.00")
    with allure.step("Verify negative deposit is rejected"):
        assert response.status_code >= 400


@pytest.mark.smoke
@pytest.mark.api
def test_withdraw_decreases_balance(api: ParabankApi, account_pair: tuple[int, int]) -> None:
    acc_id, _ = account_pair
    api.deposit(acc_id, "50.00")
    balance_before = api.get_account(acc_id).json()["balance"]
    api.withdraw(acc_id, "10.00")
    balance_after = api.get_account(acc_id).json()["balance"]
    with allure.step("Verify balance decreased by exactly 10.00"):
        assert balance_after == pytest.approx(balance_before - 10.00, abs=0.01)


@pytest.mark.api
def test_withdraw_returns_success_message(api: ParabankApi, account_pair: tuple[int, int]) -> None:
    acc_id, _ = account_pair
    api.deposit(acc_id, "20.00")
    response = api.withdraw(acc_id, "5.00")
    with allure.step("Verify 200 and success text"):
        assert response.status_code == 200
        assert "Successfully withdrew" in response.text


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known defect D-06: API accepts withdrawal exceeding balance (no overdraft protection)",
    strict=True,
)
def test_withdraw_overdraft_is_rejected(api: ParabankApi, isolated_account: int) -> None:
    # isolated_account: a successful overdraft would push a shared account's
    # balance deep negative for every other test that reads it.
    api.deposit(isolated_account, "50.00")
    response = api.withdraw(isolated_account, "9999999.00")
    with allure.step("Verify overdraft withdrawal is rejected"):
        assert response.status_code >= 400


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known defect D-07: API accepts negative withdrawal amounts with HTTP 200",
    strict=True,
)
def test_withdraw_negative_amount_is_rejected(api: ParabankApi, isolated_account: int) -> None:
    # isolated_account: D-07 actually goes through, so a shared account would
    # silently gain money on every run.
    response = api.withdraw(isolated_account, "-50.00")
    with allure.step("Verify negative withdrawal is rejected"):
        assert response.status_code >= 400


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known defect D-14: missing amount param returns 500, not a validation error",
    strict=True,
)
def test_deposit_without_amount_param_is_rejected(base_url: str, isolated_account: int) -> None:
    # ParabankApi.deposit() always sends `amount`; this probes the parameter
    # being absent entirely (not just an empty string), so it goes straight
    # to the raw endpoint.
    with httpx.Client(base_url=f"{base_url}/parabank/services/bank", timeout=30) as client:
        response = client.post("/deposit", params={"accountId": isolated_account})
    with allure.step("Verify a validation error, not a server crash"):
        assert response.status_code < 500


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known defect D-14: missing amount param returns 500, not a validation error",
    strict=True,
)
def test_withdraw_without_amount_param_is_rejected(base_url: str, isolated_account: int) -> None:
    with httpx.Client(base_url=f"{base_url}/parabank/services/bank", timeout=30) as client:
        response = client.post("/withdraw", params={"accountId": isolated_account})
    with allure.step("Verify a validation error, not a server crash"):
        assert response.status_code < 500


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known defect D-15: scientific-notation amount accepted instead of rejected",
    strict=True,
)
def test_deposit_scientific_notation_amount_is_rejected(
    api: ParabankApi, isolated_account: int
) -> None:
    response = api.deposit(isolated_account, "1e5")
    with allure.step("Verify a scientific-notation amount is rejected"):
        assert response.status_code >= 400
