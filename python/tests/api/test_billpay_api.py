"""ParaBank REST API tests — bill payment.

Defect D-08: POST /billpay returns HTTP 500 whenever the payee payload
includes a `routingNumber` key at all — regardless of its value, even an
empty string. Omitting the field entirely succeeds. Found by exploratory
testing: the original D-08 wording ("always 500 regardless of payload") was
imprecise — it happened to always test with routingNumber present. Corrected
here rather than left inaccurate, per the "don't fit the test to the bug"
rule: the wrong root cause is itself a defect in our own test plan.

Defect D-21: bill pay accepts a negative amount and credits the account
instead of debiting it — the same unvalidated-sign pattern already found at
transfer (D-02), deposit/withdraw (D-05/D-07), positions (D-12/D-13), and
loans (D-19).
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


@pytest.mark.api
@pytest.mark.security
@pytest.mark.xfail(
    reason="Known defect D-21: negative bill pay amount accepted instead of rejected",
    strict=True,
)
def test_bill_pay_negative_amount_is_rejected(api: ParabankApi, isolated_account: int) -> None:
    response = api.bill_pay(
        isolated_account, amount="-50.00", payee=VALID_PAYEE_WITHOUT_ROUTING_NUMBER
    )
    with allure.step("Verify a negative bill pay amount is rejected"):
        assert response.status_code >= 400
