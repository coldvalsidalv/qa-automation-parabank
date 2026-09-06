"""Bill Pay UI tests.

Bill Pay is the one ParaBank form whose client-side validation actually works:
unlike Transfer Funds (defect D-04, where the messages sit in the DOM but are
never revealed), it displays "The amount cannot be empty.", "Payee name is
required." and "The account numbers do not match." — all verified against the
live app. Those are asserted as *visible* text rather than as DOM presence,
because presence proves nothing here.

The one thing it does not validate is the sign of the amount: a negative
payment is accepted and confirmed, which is defect D-21 surfacing through the
UI as well as the API.
"""

from collections.abc import Callable

import allure
import pytest
from playwright.sync_api import Page

from pages.bill_pay_page import BillPayPage

pytestmark = [
    allure.feature("Bill Pay"),
    allure.story("Bill payment (UI)"),
    allure.severity(allure.severity_level.NORMAL),
]


@pytest.fixture
def bill_pay_page(page: Page, base_url: str, account_pair: tuple[int, int]) -> BillPayPage:
    """Bill Pay with at least one funded account guaranteed by `account_pair`."""
    return BillPayPage(page, base_url).open()


@pytest.mark.smoke
@pytest.mark.ui
def test_bill_payment_completes(bill_pay_page: BillPayPage) -> None:
    bill_pay_page.pay()
    with allure.step("Verify the confirmation names the payee and the amount"):
        assert bill_pay_page.is_payment_complete(), "Payment confirmation not shown"
        confirmation = bill_pay_page.confirmation_text()
        assert "UI Test Payee" in confirmation, confirmation
        # "$25.00", not "25": the sentence also carries the paying account
        # number, so a bare "25" is satisfied by an account id containing those
        # digits and would pass on a wrong amount.
        assert "$25.00" in confirmation, confirmation
        # Also pins the visibility filter in `visible_validation_errors`: the
        # page keeps every validation message in the DOM at all times, so a
        # filter that returned DOM presence instead of what is shown would
        # report errors here on a payment that plainly succeeded.
        assert bill_pay_page.visible_validation_errors() == [], (
            f"successful payment still showed {bill_pay_page.visible_validation_errors()}"
        )


# Every case is the same journey — fill the form with valid defaults, spoil one
# field, submit — differing only in which field is spoiled and which message the
# page must show. The expected message is part of the case, not a shared
# assertion: "rejected" alone would pass on the wrong error, and picking the
# right one is exactly what distinguishes Bill Pay from Transfer Funds (D-04).
#
# The case carries the call rather than a (field, value) pair so that each
# `pay(...)` keeps literal keywords: `pay` takes `from_account: int` alongside
# `**overrides: str`, and splatting a `dict[str, str]` into it is a type error.
SpoilTheForm = Callable[[BillPayPage], None]


@pytest.mark.ui
@pytest.mark.parametrize(
    ("spoil", "expected_message"),
    [
        pytest.param(
            lambda page: page.pay(verify_account="99999"),
            "The account numbers do not match.",
            id="mismatched-accounts",
        ),
        pytest.param(
            lambda page: page.pay(amount=""),
            "The amount cannot be empty.",
            id="empty-amount",
        ),
        pytest.param(
            lambda page: page.pay(amount="abc"),
            "Please enter a valid amount.",
            id="non-numeric-amount",
        ),
        pytest.param(
            lambda page: page.pay(name=""),
            "Payee name is required.",
            id="empty-payee-name",
        ),
    ],
)
def test_invalid_field_is_rejected_with_its_message(
    bill_pay_page: BillPayPage, spoil: SpoilTheForm, expected_message: str
) -> None:
    spoil(bill_pay_page)
    with allure.step(f"Verify the payment did not go through and {expected_message!r} is shown"):
        assert not bill_pay_page.is_payment_complete(), (
            f"The form paid out despite {expected_message!r} being the expected outcome"
        )
        errors = bill_pay_page.visible_validation_errors()
        assert expected_message in errors, f"expected {expected_message!r}, page showed {errors}"


@pytest.mark.ui
@pytest.mark.xfail(
    reason="Known defect D-21: the Bill Pay form accepts a negative amount and confirms it",
    strict=True,
)
def test_negative_amount_is_rejected(page: Page, base_url: str, isolated_account: int) -> None:
    # isolated_account: this defect actually goes through and credits the payer,
    # so it must not land on the shared account_pair.
    bill_pay = BillPayPage(page, base_url).open()
    bill_pay.pay(amount="-50", from_account=isolated_account)
    with allure.step("Verify a negative payment is rejected rather than confirmed"):
        assert not bill_pay.is_payment_complete(), (
            "A negative bill payment was confirmed: " + bill_pay.confirmation_text()
        )
