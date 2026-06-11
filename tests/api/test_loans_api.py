"""ParaBank REST API tests — loan requests."""

import allure
import pytest

from utils.parabank_api import ParabankApi, register_customer

pytestmark = [
    allure.feature("Loans"),
    allure.story("Loan request API"),
    allure.severity(allure.severity_level.NORMAL),
]


@pytest.fixture(scope="module")
def loan_api(base_url: str):
    """Fresh ParabankApi client for loan tests — keeps its own httpx session."""
    client = ParabankApi(base_url)
    yield client
    client.close()


@pytest.fixture(scope="module")
def loan_customer(base_url: str, loan_api: ParabankApi) -> tuple[int, int]:
    """Register a brand-new customer so loan scoring is not skewed by the
    main test customer's negative balances (D-06 overdraft defect leaves
    account_pair[0] deep in the red, which causes loan declines).

    Returns (customer_id, account_id).
    """
    creds = register_customer(base_url)
    data = loan_api.login(creds).json()
    cid = data["id"]
    acc_id = loan_api.get_accounts(cid).json()[0]["id"]
    loan_api.deposit(acc_id, "5000.00")
    return cid, acc_id


@pytest.mark.smoke
@pytest.mark.api
def test_request_loan_approved(loan_api: ParabankApi, loan_customer: tuple[int, int]) -> None:
    cid, acc_id = loan_customer
    response = loan_api.request_loan(cid, amount="1000", down_payment="500", from_account_id=acc_id)
    with allure.step("Verify 200 and loan is approved"):
        assert response.status_code == 200
        data = response.json()
        assert data["approved"] is True, f"Loan declined: {data.get('message')}"
        assert isinstance(data["accountId"], int) and data["accountId"] > 0


@pytest.mark.api
def test_request_loan_response_fields(
    loan_api: ParabankApi, loan_customer: tuple[int, int]
) -> None:
    cid, acc_id = loan_customer
    data = loan_api.request_loan(
        cid, amount="500", down_payment="200", from_account_id=acc_id
    ).json()
    with allure.step("Verify all expected fields are present"):
        assert isinstance(data["responseDate"], int) and data["responseDate"] > 0
        assert isinstance(data["loanProviderName"], str) and data["loanProviderName"]
        assert isinstance(data["approved"], bool)


@pytest.mark.api
def test_request_loan_creates_new_loan_account(
    loan_api: ParabankApi, loan_customer: tuple[int, int]
) -> None:
    cid, acc_id = loan_customer
    response = loan_api.request_loan(cid, amount="500", down_payment="200", from_account_id=acc_id)
    data = response.json()
    with allure.step("Verify a new LOAN account was created and is retrievable"):
        assert data["approved"] is True, f"Loan declined: {data.get('message')}"
        new_account_id = data["accountId"]
        new_account = loan_api.get_account(new_account_id).json()
        assert new_account["type"] == "LOAN"
        assert new_account["id"] == new_account_id


@pytest.mark.api
def test_request_loan_down_payment_exceeding_amount(
    loan_api: ParabankApi, loan_customer: tuple[int, int]
) -> None:
    cid, acc_id = loan_customer
    response = loan_api.request_loan(cid, amount="100", down_payment="200", from_account_id=acc_id)
    with allure.step("Verify the API handles down payment > loan amount gracefully"):
        assert response.status_code in (200, 400)
        if response.status_code == 200:
            assert isinstance(response.json().get("approved"), bool)
