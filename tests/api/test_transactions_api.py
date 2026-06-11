"""ParaBank REST API tests — transaction queries.

Covers all five transaction-retrieval endpoints:
  GET /accounts/{id}/transactions
  GET /accounts/{id}/transactions/amount/{amount}
  GET /accounts/{id}/transactions/fromDate/{from}/toDate/{to}
  GET /accounts/{id}/transactions/onDate/{date}
  GET /accounts/{id}/transactions/month/{month}/type/{type}
  GET /transactions/{id}

Date format accepted by the API: MM-DD-YYYY.
Month names accepted by /month/{month}: January, February … December.
"""
from datetime import UTC, datetime

import allure
import pytest

from utils.parabank_api import ParabankApi

TODAY = datetime.now(UTC)
TODAY_STR = TODAY.strftime("%m-%d-%Y")           # e.g. "06-11-2026"
MONTH_STR = TODAY.strftime("%B")                 # e.g. "June"
MONTH_RANGE_FROM = TODAY.strftime("%m-01-%Y")
MONTH_RANGE_TO = TODAY.strftime("%m-%d-%Y")


@pytest.fixture(scope="module")
def seeded_account(api: ParabankApi, account_pair: tuple[int, int]) -> tuple[int, float]:
    """Deposit a known amount so transaction-filter tests have data to work with.

    Returns (account_id, deposited_amount).
    """
    acc_id, _ = account_pair
    amount = 77.00
    api.deposit(acc_id, str(amount))
    return acc_id, amount


@pytest.fixture(scope="module")
def transactions(api: ParabankApi, seeded_account: tuple[int, float]) -> list[dict]:
    acc_id, _ = seeded_account
    response = api.get_transactions(acc_id)
    assert response.status_code == 200
    return response.json()


# ------------------------------------------------------------------
# Full transaction list
# ------------------------------------------------------------------

@pytest.mark.smoke
@pytest.mark.api
def test_get_transactions_returns_200(api: ParabankApi, seeded_account: tuple[int, float]) -> None:
    acc_id, _ = seeded_account
    response = api.get_transactions(acc_id)
    with allure.step("Verify 200 OK"):
        assert response.status_code == 200


@pytest.mark.api
def test_transactions_list_is_non_empty(transactions: list[dict]) -> None:
    with allure.step("Verify the account has at least one transaction"):
        assert len(transactions) > 0


@pytest.mark.api
def test_transaction_fields(transactions: list[dict]) -> None:
    tx = transactions[0]
    with allure.step("Verify required fields are present and typed correctly"):
        assert isinstance(tx["id"], int) and tx["id"] > 0
        assert isinstance(tx["accountId"], int)
        assert tx["type"] in ("Credit", "Debit")
        assert isinstance(tx["date"], int)          # epoch milliseconds
        assert isinstance(tx["amount"], (int, float)) and tx["amount"] > 0
        assert isinstance(tx["description"], str) and tx["description"]


# ------------------------------------------------------------------
# Get transaction by ID
# ------------------------------------------------------------------

@pytest.mark.api
def test_get_transaction_by_id(api: ParabankApi, transactions: list[dict]) -> None:
    tx_id = transactions[0]["id"]
    response = api.get_transaction(tx_id)
    with allure.step("Verify 200 and the returned id matches"):
        assert response.status_code == 200
        assert response.json()["id"] == tx_id


@pytest.mark.api
def test_get_nonexistent_transaction_returns_error(api: ParabankApi) -> None:
    response = api.get_transaction(9999999)
    with allure.step("Verify non-200 for an unknown transaction id"):
        assert response.status_code != 200


# ------------------------------------------------------------------
# Filter by amount
# ------------------------------------------------------------------

@pytest.mark.api
def test_transactions_by_amount_returns_matching_records(
    api: ParabankApi, seeded_account: tuple[int, float]
) -> None:
    acc_id, amount = seeded_account
    response = api.get_transactions_by_amount(acc_id, str(amount))
    with allure.step(f"Verify all returned transactions have amount={amount}"):
        assert response.status_code == 200
        results = response.json()
        assert len(results) > 0
        assert all(tx["amount"] == amount for tx in results)


@pytest.mark.api
def test_transactions_by_amount_no_match_returns_empty_or_error(
    api: ParabankApi, seeded_account: tuple[int, float]
) -> None:
    acc_id, _ = seeded_account
    response = api.get_transactions_by_amount(acc_id, "0.01")
    with allure.step("Verify empty list or 404 for amount with no transactions"):
        if response.status_code == 200:
            assert response.json() == []
        else:
            assert response.status_code == 404


# ------------------------------------------------------------------
# Filter by date range
# ------------------------------------------------------------------

@pytest.mark.api
def test_transactions_by_date_range_returns_200(
    api: ParabankApi, seeded_account: tuple[int, float]
) -> None:
    acc_id, _ = seeded_account
    response = api.get_transactions_by_date_range(acc_id, MONTH_RANGE_FROM, MONTH_RANGE_TO)
    with allure.step("Verify 200 and non-empty list for current-month range"):
        assert response.status_code == 200
        assert len(response.json()) > 0


@pytest.mark.api
def test_transactions_by_date_range_future_returns_empty_or_error(
    api: ParabankApi, seeded_account: tuple[int, float]
) -> None:
    acc_id, _ = seeded_account
    response = api.get_transactions_by_date_range(acc_id, "01-01-2099", "12-31-2099")
    with allure.step("Verify empty list or 404 for a future date range"):
        if response.status_code == 200:
            assert response.json() == []
        else:
            assert response.status_code == 404


# ------------------------------------------------------------------
# Filter by specific date
# ------------------------------------------------------------------

@pytest.mark.api
def test_transactions_on_date_returns_todays_transactions(
    api: ParabankApi, seeded_account: tuple[int, float]
) -> None:
    acc_id, _ = seeded_account
    response = api.get_transactions_on_date(acc_id, TODAY_STR)
    with allure.step("Verify 200 and at least one transaction recorded today"):
        assert response.status_code == 200
        assert len(response.json()) > 0


# ------------------------------------------------------------------
# Filter by month + type
# ------------------------------------------------------------------

@pytest.mark.api
def test_transactions_by_month_and_type_returns_correct_type(
    api: ParabankApi, seeded_account: tuple[int, float]
) -> None:
    acc_id, _ = seeded_account
    response = api.get_transactions_by_month_type(acc_id, MONTH_STR, "Credit")
    with allure.step("Verify all returned transactions are Credits in the current month"):
        assert response.status_code == 200
        results = response.json()
        assert len(results) > 0
        assert all(tx["type"] == "Credit" for tx in results)


@pytest.mark.api
def test_transactions_by_month_and_type_debit(
    api: ParabankApi, seeded_account: tuple[int, float]
) -> None:
    acc_id, _ = seeded_account
    response = api.get_transactions_by_month_type(acc_id, MONTH_STR, "Debit")
    with allure.step("Verify all returned transactions are Debits"):
        assert response.status_code == 200
        results = response.json()
        assert all(tx["type"] == "Debit" for tx in results)
