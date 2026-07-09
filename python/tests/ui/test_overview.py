import allure
import pytest
from playwright.sync_api import Page

from pages.overview_page import OverviewPage

pytestmark = [
    allure.feature("Accounts"),
    allure.story("Accounts overview"),
    allure.severity(allure.severity_level.CRITICAL),
]


@pytest.mark.smoke
@pytest.mark.ui
def test_overview_page_loads_for_logged_in_user(page: Page, base_url: str) -> None:
    overview = OverviewPage(page, base_url).open()
    with allure.step("Verify the user is on Accounts Overview and authenticated"):
        assert overview.is_on_overview_page(), f"Expected overview.htm, got: {page.url}"
        assert overview.is_logged_in(), "Logout link not found — user is not authenticated"


@pytest.mark.smoke
@pytest.mark.ui
def test_overview_shows_at_least_one_account(page: Page, base_url: str) -> None:
    overview = OverviewPage(page, base_url).open()
    with allure.step("Verify at least one account is listed"):
        assert overview.account_count() > 0, "No accounts in the overview table"


@pytest.mark.ui
def test_overview_has_navigation_links(page: Page, base_url: str) -> None:
    overview = OverviewPage(page, base_url).open()
    for name in ["Transfer Funds", "Bill Pay", "Request Loan"]:
        with allure.step(f"Verify the '{name}' link is present"):
            assert overview.has_nav_link(name), f"{name} link not found"


@pytest.mark.ui
def test_overview_account_link_opens_account_activity(page: Page, base_url: str) -> None:
    overview = OverviewPage(page, base_url).open()
    overview.open_first_account()
    with allure.step("Verify the Account Activity page opened"):
        assert "activity.htm" in page.url
