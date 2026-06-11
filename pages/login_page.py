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

    def open(self) -> "LoginPage":
        self.navigate(self.URL)
        return self

    def login(self, username: str, password: str) -> None:
        self.fill(self.USERNAME_INPUT, username, "username")
        self.fill(self.PASSWORD_INPUT, password, "password")
        self.click(self.LOGIN_BUTTON, "Log In button")

    def is_on_login_page(self) -> bool:
        return "index.htm" in self.page.url or self.page.url.endswith("/parabank/")

    def is_logged_in(self) -> bool:
        return "overview.htm" in self.page.url

    def has_error(self) -> bool:
        return self.page.locator(self.ERROR_MESSAGE).count() > 0

    def is_username_field_visible(self) -> bool:
        return self.page.locator(self.USERNAME_INPUT).is_visible()
