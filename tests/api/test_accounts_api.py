"""ParaBank REST API tests — login and accounts.

Docs: https://parabank.parasoft.com/parabank/api-docs/index.html
"""
import allure
import jsonschema
import pytest

from utils.parabank_api import Credentials, ParabankApi

ACCOUNT_SCHEMA = {
    "type": "object",
    "required": ["id", "customerId", "type", "balance"],
    "properties": {
        "id": {"type": "integer"},
        "customerId": {"type": "integer"},
        "type": {"type": "string", "enum": ["CHECKING", "SAVINGS", "LOAN"]},
        "balance": {"type": "number"},
    },
}


@pytest.fixture(scope="module")
def accounts(api: ParabankApi, customer_id: int) -> list[dict]:
    response = api.get_accounts(customer_id)
    assert response.status_code == 200
    return response.json()


@pytest.mark.smoke
@pytest.mark.api
def test_login_returns_customer(api: ParabankApi, credentials: Credentials) -> None:
    response = api.login(credentials)
    with allure.step("Verify the response is 200 and contains the customer object"):
        assert response.status_code == 200
        customer = response.json()
        assert customer["id"] > 0
        assert customer["firstName"]
        assert customer["lastName"]


@pytest.mark.api
def test_login_with_invalid_credentials_returns_400(api: ParabankApi) -> None:
    response = api.login(Credentials("no_such_user_xyz", "wrong_password"))
    with allure.step("Verify the API rejects the credentials with 400"):
        assert response.status_code == 400
        assert "Invalid username and/or password" in response.text


@pytest.mark.smoke
@pytest.mark.api
def test_customer_has_accounts(accounts: list[dict]) -> None:
    with allure.step("Verify the customer has at least one account"):
        assert len(accounts) > 0, "Customer has no accounts"


@pytest.mark.api
def test_accounts_match_schema(accounts: list[dict]) -> None:
    with allure.step(f"Verify all {len(accounts)} accounts match the JSON schema"):
        for account in accounts:
            jsonschema.validate(account, ACCOUNT_SCHEMA)


@pytest.mark.api
def test_get_account_by_id_returns_same_account(
    api: ParabankApi, accounts: list[dict]
) -> None:
    expected = accounts[0]
    response = api.get_account(expected["id"])
    with allure.step("Verify the returned account matches the requested one"):
        assert response.status_code == 200
        assert response.json()["id"] == expected["id"]
        assert response.json()["customerId"] == expected["customerId"]
