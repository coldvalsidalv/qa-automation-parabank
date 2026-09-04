"""Logout UI tests.

These deliberately log in through `unauth_page` instead of reusing the
session-wide `page` fixture. That fixture seeds every context with one
storage state captured by a single login, so all tests share one JSESSIONID —
and logging out invalidates it server-side. A logout test riding on that
fixture would quietly unauthenticate every test that ran after it.

Defect D-22: once logged out, a protected page does not redirect to the login
form. It answers with ParaBank's internal-error page (HTTP 500 at the wire
level, see test_security_api.py), which is both a poor experience and an
information leak.
"""

import allure
import pytest
from playwright.sync_api import Page

from pages.login_page import LoginPage
from pages.overview_page import OverviewPage
from utils.parabank_api import Credentials

pytestmark = [
    allure.feature("Authentication"),
    allure.story("UI logout"),
    allure.severity(allure.severity_level.CRITICAL),
]


@pytest.fixture
def logged_in_overview(unauth_page: Page, base_url: str, credentials: Credentials) -> OverviewPage:
    """A session of this test's own, so logging out cannot affect other tests."""
    LoginPage(unauth_page, base_url).open().login(credentials.username, credentials.password)
    unauth_page.wait_for_url("**/overview.htm")
    return OverviewPage(unauth_page, base_url)


@pytest.mark.smoke
@pytest.mark.ui
def test_logout_returns_to_the_login_page(
    logged_in_overview: OverviewPage, unauth_page: Page, base_url: str
) -> None:
    assert logged_in_overview.is_logged_in(), "Setup: expected an authenticated session"

    logged_in_overview.log_out()

    login = LoginPage(unauth_page, base_url)
    with allure.step("Verify the login form is back and the session is gone"):
        assert login.is_on_login_page(), f"Expected the login page, got: {unauth_page.url}"
        assert login.is_username_field_visible(), "Username input not visible after logout"
        assert not logged_in_overview.is_logged_in(), "Log Out link still present after logout"


@pytest.mark.ui
@pytest.mark.xfail(
    reason="Known defect D-22: after logout a protected page returns ParaBank's "
    "internal-error page instead of redirecting to the login form",
    strict=True,
)
def test_protected_page_after_logout_does_not_show_an_internal_error(
    logged_in_overview: OverviewPage, unauth_page: Page, base_url: str
) -> None:
    logged_in_overview.log_out()

    overview = OverviewPage(unauth_page, base_url)
    overview.navigate(overview.URL)

    login = LoginPage(unauth_page, base_url)
    with allure.step("Verify no internal-error message is displayed"):
        # Not "is the username field visible": ParaBank renders the login form
        # in a shared side panel that appears on the error page too, so that
        # check passes even while the page is an HTTP 500 error (verified live).
        assert "internal error" not in login.error_text().lower(), (
            "Opening a protected page while logged out showed "
            f"{login.error_text()!r} instead of redirecting to the login form"
        )
