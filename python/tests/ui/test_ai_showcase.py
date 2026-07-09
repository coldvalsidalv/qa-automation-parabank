"""Demo tests for the AI features. Excluded from regular runs (see addopts).

Run with a local Ollama:
    AI_ANALYSIS=true SELF_HEAL=true pytest -m ai_demo
"""

import os

import pytest
from playwright.sync_api import Page

from pages.login_page import LoginPage
from pages.overview_page import OverviewPage
from utils.parabank_api import Credentials


@pytest.mark.ai_demo
@pytest.mark.ui
def test_failure_analysis_demo(page: Page, base_url: str) -> None:
    """Fails on purpose so the Allure report shows the AI diagnosis attachment."""
    overview = OverviewPage(page, base_url).open()
    assert overview.account_count() >= 100, (
        "Intentional failure: a fresh customer cannot have 100 accounts"
    )


@pytest.mark.ai_demo
@pytest.mark.ui
def test_self_healing_demo(unauth_page: Page, base_url: str, credentials: Credentials) -> None:
    """Logs in through a deliberately outdated button selector.

    With SELF_HEAL=true the AI suggests a working alternative and the test
    passes; the healed selector is visible as an Allure step.
    """
    if os.getenv("SELF_HEAL", "false").lower() != "true":
        pytest.skip("Requires SELF_HEAL=true and a running Ollama")

    login = LoginPage(unauth_page, base_url).open()
    login.fill(login.USERNAME_INPUT, credentials.username, "username")
    login.fill(login.PASSWORD_INPUT, credentials.password, "password")
    login.click('input[value="Sign In"]', "login submit button")  # outdated on purpose
    unauth_page.wait_for_url("**/overview.htm")
    assert login.is_login_successful()
