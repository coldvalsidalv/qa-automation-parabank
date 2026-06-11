"""ParaBank REST API tests — login and accounts."""
import allure
import pytest

from utils.parabank_api import Credentials, ParabankApi

pytestmark = [
    allure.feature("Accounts"),
    allure.story("Accounts API"),
    allure.severity(allure.severity_level.CRITICAL),
]


@pytest.fixture(scope="module")
def accounts(api: ParabankApi, customer_id: int) -> list[dict]:
    response = api.get_accounts(customer_id)
    assert response.status_code == 200
    return response.json()


# ------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------

@pytest.mark.smoke
@pytest.mark.api
def test_login_returns_customer(api: ParabankApi, credentials: Credentials) -> None:
    response = api.login(credentials)
    with allure.step("Verify 200 and customer object fields"):
        assert response.status_code == 200
        customer = response.json()
        assert isinstance(customer["id"], int) and customer["id"] > 0
        assert isinstance(customer["firstName"], str) and customer["firstName"]
        assert isinstance(customer["lastName"], str) and customer["lastName"]


@pytest.mark.api
def test_login_with_invalid_credentials_returns_400(api: ParabankApi) -> None:
    response = api.login(Credentials("no_such_user_xyz", "wrong_password"))
    with allure.step("Verify 400 and error message"):
        assert response.status_code == 400
        assert "Invalid username and/or password" in response.text


# ------------------------------------------------------------------
# Account list
# ------------------------------------------------------------------

@pytest.mark.smoke
@pytest.mark.api
def test_customer_has_accounts(accounts: list[dict]) -> None:
    with allure.step("Verify the customer has at least one account"):
        assert len(accounts) > 0


@pytest.mark.api
def test_account_fields(accounts: list[dict]) -> None:
    acc = accounts[0]
    with allure.step("Verify required fields are present and correctly typed"):
        assert isinstance(acc["id"], int) and acc["id"] > 0
        assert isinstance(acc["customerId"], int) and acc["customerId"] > 0
        assert acc["type"] in ("CHECKING", "SAVINGS", "LOAN")
        assert isinstance(acc["balance"], (int, float))


# ------------------------------------------------------------------
# Get account by ID
# ------------------------------------------------------------------

@pytest.mark.api
def test_get_account_by_id_matches(api: ParabankApi, accounts: list[dict]) -> None:
    expected = accounts[0]
    response = api.get_account(expected["id"])
    with allure.step("Verify the returned account matches the requested one"):
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == expected["id"]
        assert data["customerId"] == expected["customerId"]
        assert data["type"] == expected["type"]


@pytest.mark.api
def test_get_nonexistent_account_returns_error(api: ParabankApi) -> None:
    response = api.get_account(9999999)
    with allure.step("Verify non-200 for an unknown account id"):
        assert response.status_code != 200
        assert "9999999" in response.text


# ------------------------------------------------------------------
# Create account
# ------------------------------------------------------------------

@pytest.mark.api
def test_create_checking_account(api: ParabankApi, customer_id: int, accounts: list[dict]) -> None:
    from_id = accounts[0]["id"]
    response = api.create_account(customer_id, from_account_id=from_id, account_type=0)
    with allure.step("Verify 200 and the new account is CHECKING"):
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["id"], int) and data["id"] > 0
        assert data["customerId"] == customer_id
        assert data["type"] == "CHECKING"


@pytest.mark.api
def test_create_savings_account(api: ParabankApi, customer_id: int, accounts: list[dict]) -> None:
    from_id = accounts[0]["id"]
    response = api.create_account(customer_id, from_account_id=from_id, account_type=1)
    with allure.step("Verify 200 and the new account is SAVINGS"):
        assert response.status_code == 200
        assert response.json()["type"] == "SAVINGS"


@pytest.mark.api
def test_new_account_appears_in_account_list(
    api: ParabankApi, customer_id: int, accounts: list[dict]
) -> None:
    from_id = accounts[0]["id"]
    new_id = api.create_account(customer_id, from_account_id=from_id).json()["id"]
    all_ids = {a["id"] for a in api.get_accounts(customer_id).json()}
    with allure.step("Verify newly created account appears in the customer's account list"):
        assert new_id in all_ids
