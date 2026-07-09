import allure
from playwright.sync_api import Page

from pages.base_page import BasePage


class OverviewPage(BasePage):
    """Accounts Overview — landing page after login."""

    URL = "/parabank/overview.htm"

    ACCOUNT_ROWS = "#accountTable tbody tr"
    ACCOUNT_LINKS = "#accountTable tbody tr td:first-child a"
    LOGOUT_LINK = 'a[href*="logout"]'
    TRANSFER_LINK = 'a[href*="transfer.htm"]'
    BILL_PAY_LINK = 'a[href*="billpay.htm"]'
    REQUEST_LOAN_LINK = 'a[href*="requestloan.htm"]'

    # Navigation links keyed by their user-facing label. The label is what a
    # test knows; the selector stays an implementation detail of the page.
    NAV_LINKS = {
        "Transfer Funds": TRANSFER_LINK,
        "Bill Pay": BILL_PAY_LINK,
        "Request Loan": REQUEST_LOAN_LINK,
    }

    def __init__(self, page: Page, base_url: str) -> None:
        super().__init__(page, base_url)

    @allure.step("Open Accounts Overview")
    def open(self) -> "OverviewPage":
        self.navigate(self.URL)
        # The account table is populated by an XHR after page load.
        self.page.locator(self.ACCOUNT_LINKS).first.wait_for(state="visible")
        return self

    def is_on_overview_page(self) -> bool:
        return "overview.htm" in self.page.url

    def is_logged_in(self) -> bool:
        return self.page.locator(self.LOGOUT_LINK).count() > 0

    def account_count(self) -> int:
        # Count links, not rows: the tbody also contains the "Total" row.
        return self.page.locator(self.ACCOUNT_LINKS).count()

    def has_nav_link(self, name: str) -> bool:
        return self.page.locator(self.NAV_LINKS[name]).count() > 0

    @allure.step("Open the first account from the overview table")
    def open_first_account(self) -> None:
        self.click(f"{self.ACCOUNT_LINKS} >> nth=0", "first account link")
        self.page.wait_for_url("**/activity.htm*")

    @allure.step("Go to Transfer Funds via the navigation menu")
    def go_to_transfer(self) -> None:
        self.click(self.TRANSFER_LINK, "Transfer Funds link")
        self.page.wait_for_url("**/transfer.htm*")
