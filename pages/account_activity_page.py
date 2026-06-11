from playwright.sync_api import Page, expect

from pages.base_page import BasePage


class AccountActivityPage(BasePage):
    """Account Activity — opens from an account link on the Overview page."""

    BALANCE = "#balance"
    TRANSACTION_TABLE = "#transactionTable"
    TRANSACTION_ROWS = "#transactionTable tbody tr"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def is_on_account_page(self) -> bool:
        return "activity.htm" in self.page.url

    def get_balance(self) -> str:
        balance = self.page.locator(self.BALANCE)
        # The balance cell is filled by an XHR after page load.
        expect(balance).not_to_have_text("")
        return balance.inner_text().strip()

    def has_transaction_table(self) -> bool:
        return self.page.locator(self.TRANSACTION_TABLE).count() > 0

    def transaction_count(self) -> int:
        return self.page.locator(self.TRANSACTION_ROWS).count()
