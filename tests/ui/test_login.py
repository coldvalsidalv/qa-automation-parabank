import pytest
from playwright.sync_api import Page

from pages.login_page import LoginPage
from utils.parabank_api import Credentials


@pytest.mark.smoke
@pytest.mark.ui
def test_login_page_loads(unauth_page: Page, base_url: str) -> None:
    login = LoginPage(unauth_page, base_url).open()
    assert login.is_on_login_page(), f"Expected login page, got: {unauth_page.url}"
    assert login.is_username_field_visible(), "Username input not visible on login page"


@pytest.mark.smoke
@pytest.mark.ui
def test_login_with_valid_credentials(
    unauth_page: Page, base_url: str, credentials: Credentials
) -> None:
    login = LoginPage(unauth_page, base_url).open()
    login.login(credentials.username, credentials.password)
    unauth_page.wait_for_url("**/overview.htm")
    assert login.is_logged_in()


@pytest.mark.smoke
@pytest.mark.ui
def test_login_with_invalid_credentials_shows_error(unauth_page: Page, base_url: str) -> None:
    login = LoginPage(unauth_page, base_url).open()
    login.login("no_such_user_xyz", "wrong_password_123")
    unauth_page.wait_for_load_state("domcontentloaded")
    assert login.has_error(), "Expected an error message after invalid credentials"
    assert not login.is_logged_in()


@pytest.mark.ui
def test_login_with_empty_credentials_shows_error(unauth_page: Page, base_url: str) -> None:
    login = LoginPage(unauth_page, base_url).open()
    login.login("", "")
    unauth_page.wait_for_load_state("domcontentloaded")
    assert login.has_error(), "Expected an error message after empty credentials"
    assert not login.is_logged_in()


@pytest.mark.ui
def test_login_page_has_register_link(unauth_page: Page, base_url: str) -> None:
    login = LoginPage(unauth_page, base_url).open()
    assert unauth_page.locator(login.REGISTER_LINK).count() > 0, "Register link not found"
