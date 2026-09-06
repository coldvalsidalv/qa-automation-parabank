"""ParaBank REST API tests — customer profile."""

import allure
import pytest

from utils.parabank_api import ParabankApi

pytestmark = [
    allure.feature("Customer"),
    allure.story("Customer profile API"),
    allure.severity(allure.severity_level.NORMAL),
]


@pytest.mark.api
def test_get_customer_returns_200(api: ParabankApi, customer_id: int) -> None:
    response = api.get_customer(customer_id)
    with allure.step("Verify 200 OK"):
        assert response.status_code == 200


@pytest.mark.api
def test_get_customer_fields(api: ParabankApi, customer_id: int) -> None:
    data = api.get_customer(customer_id).json()
    with allure.step("Verify all required customer fields are present and non-empty"):
        assert data["id"] == customer_id
        assert isinstance(data["id"], int) and data["id"] > 0
        assert isinstance(data["firstName"], str) and data["firstName"]
        assert isinstance(data["lastName"], str) and data["lastName"]
        assert isinstance(data["phoneNumber"], str) and data["phoneNumber"]
        assert isinstance(data["ssn"], str) and data["ssn"]


@pytest.mark.api
def test_get_customer_address_fields(api: ParabankApi, customer_id: int) -> None:
    addr = api.get_customer(customer_id).json()["address"]
    with allure.step("Verify nested address object is complete"):
        assert isinstance(addr["street"], str) and addr["street"]
        assert isinstance(addr["city"], str) and addr["city"]
        assert isinstance(addr["state"], str) and addr["state"]
        assert isinstance(addr["zipCode"], str) and addr["zipCode"]


@pytest.mark.api
def test_get_nonexistent_customer_returns_error(api: ParabankApi) -> None:
    response = api.get_customer(9999999)
    with allure.step("Verify 400 and a not-found message for an unknown customer id"):
        # 400 with a specific message, not merely "non-200": ParaBank returns
        # HTTP 500 for bad input in several places (D-14, D-20, D-22), so a
        # `!= 200` assertion would stay green if this endpoint regressed to a
        # crash — the very defect class this suite documents elsewhere.
        assert response.status_code == 400, response.text
        assert "Could not find customer" in response.text
        assert "9999999" in response.text
