from playwright.sync_api import Page

from pages.base_page import BasePage


class TransferPage(BasePage):
    """Transfer Funds — moves money between the customer's own accounts.

    The page is a small JS app: the form posts via XHR and toggles one of
    three panels — #showForm, #showResult ("Transfer Complete!"), #showError.
    """

    URL = "/parabank/transfer.htm"

    FROM_ACCOUNT_SELECT = "#fromAccountId"
    TO_ACCOUNT_SELECT = "#toAccountId"
    AMOUNT_INPUT = "#amount"
    TRANSFER_BUTTON = 'input[value="Transfer"]'
    FORM_PANEL = "#showForm"
    RESULT_PANEL = "#showResult"
    ERROR_PANEL = "#showError"
    AMOUNT_VALIDATION_ERROR = "p[id='amount.errors']"

    def __init__(self, page: Page, base_url: str) -> None:
        super().__init__(page, base_url)

    def open(self) -> "TransferPage":
        self.navigate(self.URL)
        # Account dropdowns are populated by an XHR after page load.
        self.page.locator(f"{self.FROM_ACCOUNT_SELECT} option").first.wait_for(state="attached")
        return self

    def is_on_transfer_page(self) -> bool:
        return "transfer.htm" in self.page.url

    def transfer(self, amount: str, from_index: int = 0, to_index: int = 1) -> None:
        self.page.locator(self.FROM_ACCOUNT_SELECT).select_option(index=from_index)
        self.page.locator(self.TO_ACCOUNT_SELECT).select_option(index=to_index)
        self.fill(self.AMOUNT_INPUT, amount, "amount")
        self.click(self.TRANSFER_BUTTON, "Transfer button")
        # Both outcomes (result or error panel) hide the form.
        self.page.locator(self.FORM_PANEL).wait_for(state="hidden")

    def is_transfer_complete(self) -> bool:
        return self.page.locator(self.RESULT_PANEL).is_visible()

    def has_error(self) -> bool:
        return self.page.locator(self.ERROR_PANEL).is_visible()

    def has_amount_validation_error(self) -> bool:
        errors = self.page.locator(self.AMOUNT_VALIDATION_ERROR)
        return any(errors.nth(i).is_visible() for i in range(errors.count()))

    def available_from_accounts(self) -> int:
        return self.page.locator(f"{self.FROM_ACCOUNT_SELECT} option").count()
