"""ParaBank REST API tests — deposit and withdrawal.

Defects discovered by probing the live API:
  D-05  Deposit accepts negative amounts (money vanishes from the account).
  D-06  Withdraw accepts amounts exceeding the account balance (no overdraft protection).
  D-07  Withdraw accepts negative amounts (effectively credits the account).
"""

import allure
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
def test_deposit_negative_amount_is_rejected(
    api: ParabankApi, account_pair: tuple[int, int]
) -> None:
    acc_id, _ = account_pair
    response = api.deposit(acc_id, "-50.00")
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
def test_withdraw_overdraft_is_rejected(
    api: ParabankApi, customer_id: int, account_pair: tuple[int, int]
) -> None:
    # Use a dedicated temporary account so account_pair[0] balance stays intact
    # for other tests (a successful overdraft would push it deep negative).
    from_id, _ = account_pair
    temp = api.create_account(customer_id, from_account_id=from_id).json()["id"]
    api.deposit(temp, "50.00")
    response = api.withdraw(temp, "9999999.00")
    with allure.step("Verify overdraft withdrawal is rejected"):
        assert response.status_code >= 400


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known defect D-07: API accepts negative withdrawal amounts with HTTP 200",
    strict=True,
)
def test_withdraw_negative_amount_is_rejected(
    api: ParabankApi, account_pair: tuple[int, int]
) -> None:
    acc_id, _ = account_pair
    response = api.withdraw(acc_id, "-50.00")
    with allure.step("Verify negative withdrawal is rejected"):
        assert response.status_code >= 400
