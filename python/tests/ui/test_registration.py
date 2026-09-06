"""Registration UI tests.

The API-level counterpart ([test_registration_api.py]) posts the form directly
and documents D-16 and D-17. These cover what only a browser shows: that a
successful registration logs the customer straight in, and that the field
validation messages are actually displayed rather than merely present in the
DOM — the trap behind D-04 on the Transfer page.

`unauth_page` throughout: registering while carrying the session customer's
cookie would test something else entirely.
"""

import allure
import pytest
from playwright.sync_api import Page

from pages.register_page import RegisterPage

pytestmark = [
    allure.feature("Registration"),
    allure.story("Customer registration (UI)"),
    allure.severity(allure.severity_level.CRITICAL),
]


@pytest.fixture
def register_page(unauth_page: Page, base_url: str) -> RegisterPage:
    return RegisterPage(unauth_page, base_url).open()


@pytest.mark.smoke
@pytest.mark.ui
def test_registration_succeeds_and_logs_the_customer_in(register_page: RegisterPage) -> None:
    username = register_page.register()
    with allure.step("Verify the welcome heading and an authenticated session"):
        assert register_page.is_registered(), (
            "No Log Out link after registering — ParaBank should log the new "
            f"customer in; errors shown: {register_page.visible_validation_errors()}"
        )
        assert username in register_page.heading_text(), register_page.heading_text()
        assert register_page.visible_validation_errors() == []


@pytest.mark.ui
def test_mismatched_passwords_are_rejected(register_page: RegisterPage) -> None:
    register_page.register(confirm_password="Different1!")
    with allure.step("Verify registration did not happen and the mismatch is shown"):
        assert not register_page.is_registered(), "Mismatched passwords must not register"
        assert register_page.visible_validation_errors() == ["Passwords did not match."]


@pytest.mark.ui
@pytest.mark.parametrize(
    ("field", "message"),
    [
        pytest.param("last_name", "Last name is required.", id="last-name"),
        pytest.param("city", "City is required.", id="city"),
        pytest.param("state", "State is required.", id="state"),
        pytest.param("zip_code", "Zip Code is required.", id="zip-code"),
    ],
)
def test_required_fields_are_enforced(
    register_page: RegisterPage, field: str, message: str
) -> None:
    register_page.register(**{field: ""})
    with allure.step(f"Verify {field} is required and the message is displayed"):
        assert not register_page.is_registered(), f"Empty {field} must not register"
        # Exact list, not membership: this page shows only the relevant message,
        # so anything extra appearing is a change worth failing on.
        assert register_page.visible_validation_errors() == [message]


@pytest.mark.ui
def test_duplicate_username_is_rejected(register_page: RegisterPage) -> None:
    """The second attempt reuses the first one's username deliberately.

    This is also the control that makes D-16 meaningful: that defect is
    "registration reports 'This username already exists' for a username that
    does not" — worth documenting only because the message is correct here.
    """
    taken = register_page.register()
    assert register_page.is_registered(), "Setup: the first registration must succeed"

    register_page.open()
    register_page.register(username=taken)

    with allure.step("Verify the duplicate is refused with the collision message"):
        assert register_page.visible_validation_errors() == ["This username already exists."]
