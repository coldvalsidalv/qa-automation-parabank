import allure
from playwright.sync_api import Page

from pages.base_page import BasePage


class RequestLoanPage(BasePage):
    """Request Loan — applies for a loan funded from one of the customer's accounts.

    Submitting reveals #requestLoanResult, which then contains either
    #loanRequestApproved or #loanRequestDenied; a server-side failure reveals
    #requestLoanError instead. Approved and denied are therefore *nested*
    outcomes, not siblings of the result panel — checking only #requestLoanResult
    would report a denial as a success.
    """

    URL = "/parabank/requestloan.htm"

    AMOUNT_INPUT = "#amount"
    DOWN_PAYMENT_INPUT = "#downPayment"
    FROM_ACCOUNT_SELECT = "#fromAccountId"
    APPLY_BUTTON = 'input[value="Apply Now"]'
    RESULT_PANEL = "#requestLoanResult"
    APPROVED_PANEL = "#loanRequestApproved"
    DENIED_PANEL = "#loanRequestDenied"
    ERROR_PANEL = "#requestLoanError"
    NEW_ACCOUNT_ID = "#newAccountId"

    def __init__(self, page: Page, base_url: str) -> None:
        super().__init__(page, base_url)

    @allure.step("Open the Request Loan page")
    def open(self) -> "RequestLoanPage":
        self.navigate(self.URL)
        # The account dropdown is populated by an XHR after page load.
        self.page.locator(f"{self.FROM_ACCOUNT_SELECT} option").first.wait_for(state="attached")
        return self

    def is_on_request_loan_page(self) -> bool:
        return "requestloan.htm" in self.page.url

    @allure.step("Apply for a loan of ${amount} with ${down_payment} down")
    def apply(self, amount: str, down_payment: str, from_account: int | None = None) -> None:
        """`from_account` picks the funding account by id; without it the first
        option wins. Option values are the account ids (verified live)."""
        self.fill(self.AMOUNT_INPUT, amount, "loan amount")
        self.fill(self.DOWN_PAYMENT_INPUT, down_payment, "down payment")
        if from_account is None:
            self.select_option(self.FROM_ACCOUNT_SELECT, index=0, description="From account")
        else:
            self.select_option(
                self.FROM_ACCOUNT_SELECT, value=str(from_account), description="From account"
            )
        self.click(self.APPLY_BUTTON, "Apply Now button")
        self.page.wait_for_load_state("networkidle")

    def is_approved(self) -> bool:
        return self.page.locator(self.APPROVED_PANEL).is_visible()

    def is_denied(self) -> bool:
        return self.page.locator(self.DENIED_PANEL).is_visible()

    def has_error_panel(self) -> bool:
        return self.page.locator(self.ERROR_PANEL).is_visible()

    def new_account_id(self) -> str:
        return self.page.locator(self.NEW_ACCOUNT_ID).inner_text().strip()

    def result_text(self) -> str:
        return self.page.locator(self.RESULT_PANEL).inner_text().strip()
