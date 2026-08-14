"""Contract tests — live API responses must match the JSON Schema in contracts/.

Value-level assertions elsewhere check *what* a field holds; these check the
*shape* of the response, so a renamed or retyped field surfaces even when the
values look right. `account` and `customer` cover exactly the data D-09 leaks;
`transaction`, `position`, `loan_response`, and `billpay_response` extend the
same discipline to the other resources with a non-trivial response shape.
"""

import allure
import pytest

from utils.contracts import schema_violations
from utils.parabank_api import ParabankApi

pytestmark = [
    allure.feature("API contracts"),
    allure.story("Response schema validation"),
    pytest.mark.api,
]


@pytest.mark.smoke
def test_account_response_matches_contract(api: ParabankApi, account_pair: tuple[int, int]) -> None:
    response = api.get_account(account_pair[0])
    assert response.status_code == 200, response.text
    violations = schema_violations(response.json(), "account")
    with allure.step("Account response matches the 'account' contract"):
        assert not violations, "Account response breaks its contract:\n" + "\n".join(violations)


def test_customer_response_matches_contract(api: ParabankApi, customer_id: int) -> None:
    response = api.get_customer(customer_id)
    assert response.status_code == 200, response.text
    violations = schema_violations(response.json(), "customer")
    with allure.step("Customer response matches the 'customer' contract"):
        assert not violations, "Customer response breaks its contract:\n" + "\n".join(violations)


def test_transaction_response_matches_contract(
    api: ParabankApi, customer_id: int, account_pair: tuple[int, int]
) -> None:
    from_id, _ = account_pair
    api.deposit(from_id, "10.00")
    transactions = api.get_transactions(from_id).json()
    assert transactions, "Setup: expected at least one transaction"
    violations = schema_violations(transactions[0], "transaction")
    with allure.step("Transaction response matches the 'transaction' contract"):
        assert not violations, "Transaction response breaks its contract:\n" + "\n".join(violations)


def test_position_response_matches_contract(
    api: ParabankApi, customer_id: int, isolated_account: int
) -> None:
    api.deposit(isolated_account, "200.00")
    response = api.buy_position(
        customer_id,
        isolated_account,
        name="ContractCo",
        symbol="CTR",
        shares=5,
        price_per_share="10.00",
    )
    assert response.status_code == 200, response.text
    positions = response.json()
    assert positions, "Setup: expected at least one position in the buy response"
    violations = schema_violations(positions[0], "position")
    with allure.step("Position response matches the 'position' contract"):
        assert not violations, "Position response breaks its contract:\n" + "\n".join(violations)


def test_loan_response_matches_contract(
    api: ParabankApi, customer_id: int, isolated_account: int
) -> None:
    response = api.request_loan(
        customer_id, amount="500", down_payment="200", from_account_id=isolated_account
    )
    assert response.status_code == 200, response.text
    violations = schema_violations(response.json(), "loan_response")
    with allure.step("Loan response matches the 'loan_response' contract"):
        assert not violations, "Loan response breaks its contract:\n" + "\n".join(violations)


def test_billpay_response_matches_contract(api: ParabankApi, isolated_account: int) -> None:
    api.deposit(isolated_account, "50.00")
    payee = {
        "name": "Test Payee",
        "address": {"street": "1 Pay Street", "city": "Paytown", "state": "PA", "zipCode": "11111"},
        "phoneNumber": "5550000001",
        "accountNumber": "99999",
    }
    # No routingNumber key: including it, with any value, returns 500 (defect D-08).
    response = api.bill_pay(isolated_account, amount="10.00", payee=payee)
    assert response.status_code == 200, response.text
    violations = schema_violations(response.json(), "billpay_response")
    with allure.step("Bill pay response matches the 'billpay_response' contract"):
        assert not violations, "Bill pay response breaks its contract:\n" + "\n".join(violations)
