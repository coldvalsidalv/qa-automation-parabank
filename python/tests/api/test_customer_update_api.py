"""ParaBank REST API tests — update customer profile (POST /customers/update/{id}).

Both tests are xfail because of defect D-10: the endpoint always returns HTTP 500
and never persists changes. They will turn green once the defect is fixed.
"""

import allure
import pytest

from utils.parabank_api import ParabankApi

pytestmark = [
    allure.feature("Customer"),
    allure.story("Update customer profile API"),
    allure.severity(allure.severity_level.NORMAL),
]

_UPDATED_FIELDS = dict(
    firstName="Updated",
    lastName="User",
    street="42 New Street",
    city="Newcity",
    state="NC",
    zipCode="12345",
    phoneNumber="5559990000",
    ssn="111-22-3333",
)


@pytest.mark.api
@pytest.mark.xfail(strict=True, reason="Known defect D-10: updateCustomer always returns 500")
def test_update_customer_returns_success(api: ParabankApi, customer_id: int) -> None:
    response = api.update_customer(customer_id, **_UPDATED_FIELDS)
    with allure.step("Verify 200 OK"):
        assert response.status_code == 200


@pytest.mark.api
@pytest.mark.xfail(strict=True, reason="Known defect D-10: updateCustomer always returns 500")
def test_update_customer_reflects_new_values(api: ParabankApi, customer_id: int) -> None:
    api.update_customer(customer_id, **_UPDATED_FIELDS)
    data = api.get_customer(customer_id).json()
    with allure.step("Verify updated values are returned by GET /customers/{id}"):
        assert data["firstName"] == _UPDATED_FIELDS["firstName"]
        assert data["address"]["city"] == _UPDATED_FIELDS["city"]
