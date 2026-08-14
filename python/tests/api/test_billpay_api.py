"""ParaBank REST API tests — bill payment.

Defect D-08: POST /billpay returns HTTP 500 whenever the payee payload
includes a `routingNumber` key at all — regardless of its value, even an
empty string. Omitting the field entirely succeeds. Found by exploratory
testing: the original D-08 wording ("always 500 regardless of payload") was
imprecise — it happened to always test with routingNumber present. Corrected
here rather than left inaccurate, per the "don't fit the test to the bug"
rule: the wrong root cause is itself a defect in our own test plan.
"""

import allure
import pytest

from utils.parabank_api import ParabankApi

pytestmark = [
    allure.feature("Bill Pay"),
    allure.story("Bill payment API"),
    allure.severity(allure.severity_level.NORMAL),
]

VALID_PAYEE_WITHOUT_ROUTING_NUMBER = {
    "name": "Test Payee",
    "address": {
        "street": "1 Pay Street",
        "city": "Paytown",
        "state": "PA",
        "zipCode": "11111",
    },
    "phoneNumber": "5550000001",
    "accountNumber": "99999",
}

VALID_PAYEE_WITH_ROUTING_NUMBER = {
    **VALID_PAYEE_WITHOUT_ROUTING_NUMBER,
    "routingNumber": "111000025",
}


@pytest.mark.smoke
@pytest.mark.api
def test_bill_pay_without_routing_number_succeeds(
    api: ParabankApi, account_pair: tuple[int, int]
) -> None:
    from_id, _ = account_pair
    api.deposit(from_id, "100.00")
    response = api.bill_pay(from_id, amount="25.00", payee=VALID_PAYEE_WITHOUT_ROUTING_NUMBER)
    with allure.step("Verify 200 and payment confirmation"):
        assert response.status_code == 200
        assert response.json()["payeeName"] == "Test Payee"


@pytest.mark.api
@pytest.mark.xfail(
    reason="Known defect D-08: POST /billpay returns 500 whenever routingNumber is present",
    strict=True,
)
def test_bill_pay_with_routing_number_succeeds(
    api: ParabankApi, account_pair: tuple[int, int]
) -> None:
    from_id, _ = account_pair
    api.deposit(from_id, "100.00")
    response = api.bill_pay(from_id, amount="25.00", payee=VALID_PAYEE_WITH_ROUTING_NUMBER)
    with allure.step("Verify 200 and payment confirmation"):
        assert response.status_code == 200
