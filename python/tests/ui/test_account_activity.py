import allure
import pytest
from playwright.sync_api import Page

from pages.account_activity_page import AccountActivityPage
from pages.overview_page import OverviewPage

pytestmark = [
    allure.feature("Accounts"),
    allure.story("Account activity"),
    allure.severity(allure.severity_level.NORMAL),
]


@pytest.fixture
def account_page(page: Page, base_url: str) -> AccountActivityPage:
    OverviewPage(page, base_url).open().open_first_account()
    return AccountActivityPage(page, base_url)


@pytest.mark.smoke
@pytest.mark.ui
def test_account_activity_page_loads(account_page: AccountActivityPage) -> None:
    with allure.step("Verify the Account Activity page is open"):
        assert account_page.is_on_account_page()


@pytest.mark.smoke
@pytest.mark.ui
def test_account_shows_numeric_balance(account_page: AccountActivityPage) -> None:
    balance = account_page.get_balance()
    with allure.step(f"Verify the balance '{balance}' is a non-empty numeric value"):
        assert balance, "Account balance is empty"
        assert any(char.isdigit() for char in balance), f"Balance '{balance}' contains no digits"


@pytest.mark.ui
def test_account_has_transaction_table(account_page: AccountActivityPage) -> None:
    with allure.step("Verify the transaction table is present"):
        assert account_page.has_transaction_table(), "Transaction table not found"
