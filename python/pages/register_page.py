import uuid

import allure
from playwright.sync_api import Page

from pages.base_page import BasePage


class RegisterPage(BasePage):
    """Register — creates a customer and logs them straight in.

    Unlike Transfer Funds or Bill Pay this is a plain server-rendered form: it
    posts, and ParaBank re-renders `register.htm` either with a "Welcome
    <username>" panel or with the form and its validation messages. There are no
    show/hide panels to wait for, so `is_registered()` reads the outcome
    directly.

    Fields are addressed by ``name`` — they carry the Spring command-object
    paths (`customer.address.street` and so on) rather than ids.
    """

    URL = "/parabank/register.htm"

    REGISTER_BUTTON = 'input[value="Register"]'
    LOGOUT_LINK = 'a[href*="logout"]'
    HEADING = "#rightPanel h1"
    VALIDATION_ERRORS = "#rightPanel .error"

    FIELDS = {
        "first_name": 'input[name="customer.firstName"]',
        "last_name": 'input[name="customer.lastName"]',
        "street": 'input[name="customer.address.street"]',
        "city": 'input[name="customer.address.city"]',
        "state": 'input[name="customer.address.state"]',
        "zip_code": 'input[name="customer.address.zipCode"]',
        "phone": 'input[name="customer.phoneNumber"]',
        "ssn": 'input[name="customer.ssn"]',
        "username": 'input[name="customer.username"]',
        "password": 'input[name="customer.password"]',
        "confirm_password": 'input[name="repeatedPassword"]',
    }

    DEFAULTS = {
        "first_name": "QA",
        "last_name": "Automation",
        "street": "1 Test Street",
        "city": "Testville",
        "state": "TS",
        "zip_code": "00000",
        "phone": "5551234567",
        "ssn": "123-45-6789",
        "password": "Passw0rd!",
        "confirm_password": "Passw0rd!",
    }

    def __init__(self, page: Page, base_url: str) -> None:
        super().__init__(page, base_url)

    @allure.step("Open the registration page")
    def open(self) -> "RegisterPage":
        self.navigate(self.URL)
        return self

    @allure.step("Submit the registration form")
    def register(self, **overrides: str) -> str:
        """Fill every field with a valid default, apply `overrides`, submit.

        Returns the username used, so a caller can re-submit it to probe the
        duplicate-username path. The default is random per call: a fixed one
        would pass once and then collide with itself on every later run.
        """
        values = {"username": f"qa_ui_{uuid.uuid4().hex[:8]}", **self.DEFAULTS, **overrides}
        for field, selector in self.FIELDS.items():
            self.fill(selector, values[field], field)
        self.click(self.REGISTER_BUTTON, "Register button")
        self.page.wait_for_load_state("domcontentloaded")
        return values["username"]

    def is_registered(self) -> bool:
        """ParaBank logs the new customer in, so the Log Out link is the proof."""
        return self.page.locator(self.LOGOUT_LINK).count() > 0

    def heading_text(self) -> str:
        return self.page.locator(self.HEADING).first.inner_text().strip()

    def visible_validation_errors(self) -> list[str]:
        """The messages actually shown.

        Measured: unlike Bill Pay and Transfer, this page renders *only* the
        relevant message — there are no hidden error spans for the filter to
        remove, so it is a no-op here rather than the D-04 safeguard it is on
        those pages. Kept because "what the user sees" is the right semantics
        and costs nothing, not because it is currently load-bearing. The tests
        assert the exact list, which is what would catch ParaBank starting to
        render the others.
        """
        errors = self.page.locator(self.VALIDATION_ERRORS)
        return [
            errors.nth(i).inner_text().strip()
            for i in range(errors.count())
            if errors.nth(i).is_visible()
        ]
