import pytest
from playwright.sync_api import Page

from pages.overview_page import OverviewPage


@pytest.mark.smoke
@pytest.mark.ui
def test_overview_page_loads_for_logged_in_user(page: Page, base_url: str) -> None:
    overview = OverviewPage(page, base_url).open()
    assert overview.is_on_overview_page(), f"Expected overview.htm, got: {page.url}"
    assert overview.is_logged_in(), "Logout link not found — user is not authenticated"


@pytest.mark.smoke
@pytest.mark.ui
def test_overview_shows_at_least_one_account(page: Page, base_url: str) -> None:
    overview = OverviewPage(page, base_url).open()
    assert overview.account_count() > 0, "No accounts in the overview table"


@pytest.mark.ui
def test_overview_has_navigation_links(page: Page, base_url: str) -> None:
    overview = OverviewPage(page, base_url).open()
    for selector, name in [
        (overview.TRANSFER_LINK, "Transfer Funds"),
        (overview.BILL_PAY_LINK, "Bill Pay"),
        (overview.REQUEST_LOAN_LINK, "Request Loan"),
    ]:
        assert page.locator(selector).count() > 0, f"{name} link not found"


@pytest.mark.ui
def test_overview_account_link_opens_account_activity(page: Page, base_url: str) -> None:
    overview = OverviewPage(page, base_url).open()
    overview.open_first_account()
    page.wait_for_url("**/activity.htm*")
    assert "activity.htm" in page.url
