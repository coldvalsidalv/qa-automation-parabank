"""Contract tests — live API responses must match the JSON Schema in contracts/.

Value-level assertions elsewhere check *what* a field holds; these check the
*shape* of the response, so a renamed or retyped field surfaces even when the
values look right. The two contracts cover exactly the data D-09 leaks: an
account and a customer's PII.
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
