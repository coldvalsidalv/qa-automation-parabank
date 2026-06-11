"""ParaBank REST API tests — bill payment.

Defect D-08: POST /billpay always returns HTTP 500 Internal Server Error
regardless of the request payload. Tested as xfail(strict=True).
"""

import allure
import pytest

from utils.parabank_api import ParabankApi

pytestmark = [
    allure.feature("Bill Pay"),
    allure.story("Bill payment API"),
    allure.severity(allure.severity_level.NORMAL),
]

VALID_PAYEE = {
    "name": "Test Payee",
    "address": {
        "street": "1 Pay Street",
        "city": "Paytown",
        "state": "PA",
        "zipCode": "11111",
    },
    "phoneNumber": "5550000001",
    "accountNumber": "99999",
    "routingNumber": "111000025",
}


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known defect D-08: POST /billpay always returns HTTP 500",
    strict=True,
)
def test_bill_pay_valid_request_succeeds(api: ParabankApi, account_pair: tuple[int, int]) -> None:
    from_id, _ = account_pair
    api.deposit(from_id, "100.00")
    response = api.bill_pay(from_id, amount="25.00", payee=VALID_PAYEE)
    with allure.step("Verify 200 and payment confirmation"):
        assert response.status_code == 200
