import allure
from playwright.sync_api import Page

from pages.base_page import BasePage


class BillPayPage(BasePage):
    """Bill Pay — sends a payment from one of the customer's accounts to a payee.

    Like Transfer Funds, the page is a small JS app: submitting toggles one of
    three panels — #billpayForm, #billpayResult, #billpayError. Unlike Transfer
    Funds (see defect D-04), its field validation messages are actually
    *displayed*, so tests can assert on them.

    Fields are addressed by ``name``: the phone input's ``id`` is a fresh UUID
    on every render, so an id-based selector would work once and then break.
    """

    URL = "/parabank/billpay.htm"

    FROM_ACCOUNT_SELECT = 'select[name="fromAccountId"]'
    SEND_BUTTON = 'input[value="Send Payment"]'
    FORM_PANEL = "#billpayForm"
    RESULT_PANEL = "#billpayResult"
    ERROR_PANEL = "#billpayError"
    VALIDATION_ERRORS = "#rightPanel .error"

    # Payee fields, keyed by the caller-facing name used in `pay()`.
    FIELDS = {
        "name": 'input[name="payee.name"]',
        "street": 'input[name="payee.address.street"]',
        "city": 'input[name="payee.address.city"]',
        "state": 'input[name="payee.address.state"]',
        "zip_code": 'input[name="payee.address.zipCode"]',
        "phone": 'input[name="payee.phoneNumber"]',
        "account_number": 'input[name="payee.accountNumber"]',
        "verify_account": 'input[name="verifyAccount"]',
        "amount": 'input[name="amount"]',
    }

    DEFAULTS = {
        "name": "UI Test Payee",
        "street": "1 Payee Street",
        "city": "Paytown",
        "state": "PA",
        "zip_code": "11111",
        "phone": "5550001111",
        "account_number": "12345",
        "verify_account": "12345",
        "amount": "25",
    }

    def __init__(self, page: Page, base_url: str) -> None:
        super().__init__(page, base_url)

    @allure.step("Open the Bill Pay page")
    def open(self) -> "BillPayPage":
        self.navigate(self.URL)
        # The account dropdown is populated by an XHR after page load.
        self.page.locator(f"{self.FROM_ACCOUNT_SELECT} option").first.wait_for(state="attached")
        return self

    def is_on_bill_pay_page(self) -> bool:
        return "billpay.htm" in self.page.url

    @allure.step("Send a bill payment")
    def pay(self, *, from_account: int | None = None, **overrides: str) -> None:
        """Fill every field with a valid default, apply `overrides`, submit.

        Callers override only what they are probing, e.g.
        ``pay(amount="-50")`` or ``pay(verify_account="99999")``.

        `from_account` picks the paying account by id. Without it the first
        option wins, which is the customer's shared first account — fine for
        read-only checks, wrong for any test that needs isolation, since
        passing an isolated account id to the *fixture* does nothing unless the
        dropdown actually selects it. The option values are the account ids
        (verified against the live page).
        """
        values = {**self.DEFAULTS, **overrides}
        for field, selector in self.FIELDS.items():
            self.fill(selector, values[field], field)
        if from_account is None:
            self.select_option(self.FROM_ACCOUNT_SELECT, index=0, description="From account")
        else:
            self.select_option(
                self.FROM_ACCOUNT_SELECT, value=str(from_account), description="From account"
            )
        self.click(self.SEND_BUTTON, "Send Payment button")
        # Every outcome (result, error, or re-rendered form with messages)
        # settles the XHR; the form panel stays put when validation rejects.
        self.page.wait_for_load_state("networkidle")

    def is_payment_complete(self) -> bool:
        return self.page.locator(self.RESULT_PANEL).is_visible()

    def has_error_panel(self) -> bool:
        return self.page.locator(self.ERROR_PANEL).is_visible()

    def confirmation_text(self) -> str:
        return self.page.locator(self.RESULT_PANEL).inner_text().strip()

    def visible_validation_errors(self) -> list[str]:
        """Only the messages actually shown.

        The page ships every validation message in the DOM and reveals the
        relevant ones, so presence proves nothing — this is the same trap that
        makes defect D-04 easy to miss on the Transfer page.
        """
        errors = self.page.locator(self.VALIDATION_ERRORS)
        return [
            errors.nth(i).inner_text().strip()
            for i in range(errors.count())
            if errors.nth(i).is_visible()
        ]
