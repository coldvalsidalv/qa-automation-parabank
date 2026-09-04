import allure
from playwright.sync_api import Page

from pages.base_page import BasePage


class LoginPage(BasePage):
    URL = "/parabank/index.htm"

    USERNAME_INPUT = 'input[name="username"]'
    PASSWORD_INPUT = 'input[name="password"]'
    LOGIN_BUTTON = 'input[value="Log In"]'
    ERROR_MESSAGE = "p.error"
    REGISTER_LINK = 'a[href*="register.htm"]'

    def __init__(self, page: Page, base_url: str) -> None:
        super().__init__(page, base_url)

    @allure.step("Open the login page")
    def open(self) -> "LoginPage":
        self.navigate(self.URL)
        return self

    @allure.step("Log in as '{username}'")
    def login(self, username: str, password: str) -> None:
        self.fill(self.USERNAME_INPUT, username, "username")
        self.fill(self.PASSWORD_INPUT, password, "password")
        self.click(self.LOGIN_BUTTON, "Log In button")
        # Submit is a full-page navigation; wait for it to settle so callers can
        # read the outcome — overview on success, index+error on failure.
        self.page.wait_for_load_state("domcontentloaded")

    def is_on_login_page(self) -> bool:
        return "index.htm" in self.page.url or self.page.url.endswith("/parabank/")

    def is_login_successful(self) -> bool:
        """Login succeeded when the app has navigated to Accounts Overview."""
        return "overview.htm" in self.page.url

    def has_error(self) -> bool:
        return self.page.locator(self.ERROR_MESSAGE).count() > 0

    def error_text(self) -> str:
        """The visible error text, or "" when none is shown.

        The login form is part of a shared template that ParaBank also renders
        on its internal-error page, so "the username field is visible" does not
        mean "this is the login page" — the error text is what tells them apart.
        """
        errors = self.page.locator(self.ERROR_MESSAGE)
        shown = [
            errors.nth(i).inner_text().strip()
            for i in range(errors.count())
            if errors.nth(i).is_visible()
        ]
        return " ".join(shown)

    def is_username_field_visible(self) -> bool:
        return self.page.locator(self.USERNAME_INPUT).is_visible()

    def has_register_link(self) -> bool:
        return self.has_element(self.REGISTER_LINK)
