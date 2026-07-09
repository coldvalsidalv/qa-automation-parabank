import allure
import pytest
from playwright.sync_api import Page

from pages.login_page import LoginPage
from utils.parabank_api import Credentials

pytestmark = [
    allure.feature("Authentication"),
    allure.story("UI login"),
    allure.severity(allure.severity_level.CRITICAL),
]


@pytest.mark.smoke
@pytest.mark.ui
def test_login_page_loads(unauth_page: Page, base_url: str) -> None:
    login = LoginPage(unauth_page, base_url).open()
    with allure.step("Verify the login form is displayed"):
        assert login.is_on_login_page(), f"Expected login page, got: {unauth_page.url}"
        assert login.is_username_field_visible(), "Username input not visible on login page"


@pytest.mark.smoke
@pytest.mark.ui
def test_login_with_valid_credentials(
    unauth_page: Page, base_url: str, credentials: Credentials
) -> None:
    login = LoginPage(unauth_page, base_url).open()
    login.login(credentials.username, credentials.password)
    with allure.step("Verify the user landed on Accounts Overview"):
        assert login.is_login_successful()


@pytest.mark.smoke
@pytest.mark.ui
def test_login_with_invalid_credentials_shows_error(unauth_page: Page, base_url: str) -> None:
    login = LoginPage(unauth_page, base_url).open()
    login.login("no_such_user_xyz", "wrong_password_123")
    with allure.step("Verify an error message is shown and the user is not logged in"):
        assert login.has_error(), "Expected an error message after invalid credentials"
        assert not login.is_login_successful()


@pytest.mark.ui
def test_login_with_empty_credentials_shows_error(unauth_page: Page, base_url: str) -> None:
    login = LoginPage(unauth_page, base_url).open()
    login.login("", "")
    with allure.step("Verify an error message is shown and the user is not logged in"):
        assert login.has_error(), "Expected an error message after empty credentials"
        assert not login.is_login_successful()


@pytest.mark.ui
def test_login_page_has_register_link(unauth_page: Page, base_url: str) -> None:
    login = LoginPage(unauth_page, base_url).open()
    with allure.step("Verify the Register link is present"):
        assert login.has_register_link(), "Register link not found"
