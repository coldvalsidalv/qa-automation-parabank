"""Request Loan UI tests.

Approval and denial are *nested* inside the result panel rather than being
siblings of it — a denied loan still reveals #requestLoanResult — so these
assert on #loanRequestApproved / #loanRequestDenied. Asserting only on the
result panel would report a denial as a success.

Every test runs as a **freshly registered customer**, not the session-wide one.
ParaBank decides a loan on the customer's overall holdings rather than on the
funding account alone, and the defect-proof tests for D-12/D-13 credit the
session customer billions out of thin air. Sharing that customer made
`test_loan_beyond_available_funds_is_denied` pass or fail depending on whether
the money-creation tests had run first — reproduced deliberately, then fixed
here rather than papered over by inflating the requested amount.

Two defects surface through this form:
  D-20  A zero amount produces the "internal error" panel instead of a
        validation message (the API leaks "/ by zero" for the same input).
  D-23  An empty amount does the same. Bill Pay, the sibling form, correctly
        answers "The amount cannot be empty." for exactly this input, so the
        expected behaviour is not in doubt.
"""

import allure
import pytest
from playwright.sync_api import Page

from pages.login_page import LoginPage
from pages.request_loan_page import RequestLoanPage
from utils.parabank_api import ParabankApi, register_customer

pytestmark = [
    allure.feature("Loans"),
    allure.story("Loan request (UI)"),
    allure.severity(allure.severity_level.NORMAL),
]

FUNDING = "5000.00"


@pytest.fixture
def loan_page(unauth_page: Page, base_url: str, api: ParabankApi) -> tuple[RequestLoanPage, int]:
    """Request Loan as a brand-new, funded customer; returns (page, account id).

    `unauth_page` rather than `page`: the shared `page` fixture authenticates as
    the session customer, which is exactly the customer whose balance other
    tests distort.
    """
    credentials = register_customer(base_url)
    customer_id = api.login(credentials).json()["id"]
    account_id = int(api.get_accounts(customer_id).json()[0]["id"])
    api.deposit(account_id, FUNDING)

    LoginPage(unauth_page, base_url).open().login(credentials.username, credentials.password)
    unauth_page.wait_for_url("**/overview.htm")
    return RequestLoanPage(unauth_page, base_url).open(), account_id


@pytest.mark.smoke
@pytest.mark.ui
def test_loan_request_is_approved(loan_page: tuple[RequestLoanPage, int]) -> None:
    loan, account_id = loan_page
    loan.apply(amount="1000", down_payment="100", from_account=account_id)
    with allure.step("Verify the loan is approved and a new account number is shown"):
        assert loan.is_approved(), f"Loan not approved: {loan.result_text()}"
        assert not loan.is_denied(), "Approved and denied panels are both visible"
        assert loan.new_account_id().isdigit(), (
            f"Expected a numeric new account id, got {loan.new_account_id()!r}"
        )


@pytest.mark.ui
def test_loan_beyond_available_funds_is_denied(loan_page: tuple[RequestLoanPage, int]) -> None:
    loan, account_id = loan_page
    loan.apply(amount="999999999", down_payment="0", from_account=account_id)
    with allure.step("Verify the loan is denied with an explanation"):
        assert loan.is_denied(), f"Expected a denial, got: {loan.result_text()}"
        assert not loan.is_approved(), "A loan beyond available funds was approved"
        assert "cannot grant" in loan.result_text().lower(), loan.result_text()


@pytest.mark.ui
@pytest.mark.xfail(
    reason="Known defect D-20: a zero loan amount shows the internal-error panel "
    "instead of a validation message",
    strict=True,
)
def test_zero_amount_shows_validation_not_internal_error(
    loan_page: tuple[RequestLoanPage, int],
) -> None:
    loan, account_id = loan_page
    loan.apply(amount="0", down_payment="0", from_account=account_id)
    with allure.step("Verify no internal-error panel is shown"):
        assert not loan.has_error_panel(), (
            "Zero amount surfaced ParaBank's internal error page instead of "
            "a field validation message"
        )


@pytest.mark.ui
@pytest.mark.xfail(
    reason="Known defect D-23: an empty loan amount shows the internal-error panel "
    "instead of a validation message, unlike the Bill Pay form",
    strict=True,
)
def test_empty_amount_shows_validation_not_internal_error(
    loan_page: tuple[RequestLoanPage, int],
) -> None:
    loan, account_id = loan_page
    loan.apply(amount="", down_payment="", from_account=account_id)
    with allure.step("Verify no internal-error panel is shown"):
        assert not loan.has_error_panel(), (
            "Empty amount surfaced ParaBank's internal error page; the Bill Pay "
            "form answers 'The amount cannot be empty.' for the same input"
        )
