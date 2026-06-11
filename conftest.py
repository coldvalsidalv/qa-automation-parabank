"""Shared fixtures and the AI failure-analysis hook.

The suite is self-sufficient: if TEST_USERNAME/TEST_PASSWORD are not set,
it registers a fresh ParaBank customer for the session, so no secrets are
required either locally or in CI.
"""
import os
from collections.abc import Iterator
from pathlib import Path

import allure
import pytest
from dotenv import load_dotenv
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from utils.parabank_api import Credentials, ParabankApi, register_customer

load_dotenv()

VIEWPORT = {"width": 1440, "height": 900}

# Set by the makereport hook, read by page fixtures on teardown to decide
# whether to keep the trace/video (retain-on-failure policy).
_test_failed_key = pytest.StashKey[bool]()


# ---------------------------------------------------------------------------
# Environment and test data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("BASE_URL", "https://parabank.parasoft.com")


@pytest.fixture(scope="session")
def api(base_url: str) -> Iterator[ParabankApi]:
    client = ParabankApi(base_url)
    yield client
    client.close()


@pytest.fixture(scope="session")
def credentials(base_url: str) -> Credentials:
    """Credentials from the environment, or a freshly registered customer."""
    username = os.getenv("TEST_USERNAME")
    password = os.getenv("TEST_PASSWORD")
    if username and password:
        return Credentials(username, password)
    return register_customer(base_url)


@pytest.fixture(scope="session")
def customer_id(api: ParabankApi, credentials: Credentials) -> int:
    response = api.login(credentials)
    assert response.status_code == 200, (
        f"API login failed for {credentials.username}: "
        f"{response.status_code} {response.text}"
    )
    return response.json()["id"]


@pytest.fixture(scope="session")
def account_pair(api: ParabankApi, customer_id: int) -> tuple[int, int]:
    """IDs of two distinct accounts; opens a second one for fresh customers."""
    accounts = api.get_accounts(customer_id).json()
    if len(accounts) < 2:
        response = api.create_account(customer_id, from_account_id=accounts[0]["id"])
        assert response.status_code == 200, f"Could not open a second account: {response.text}"
        accounts = api.get_accounts(customer_id).json()
    return accounts[0]["id"], accounts[1]["id"]


# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def playwright() -> Iterator[Playwright]:
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Iterator[Browser]:
    browser = playwright.chromium.launch(
        headless=os.getenv("HEADLESS", "true").lower() == "true",
    )
    yield browser
    browser.close()


@pytest.fixture(scope="session")
def auth_state(browser: Browser, base_url: str, credentials: Credentials) -> dict:
    """Log in through the UI once per session; reuse the storage state everywhere."""
    context = browser.new_context(viewport=VIEWPORT)
    page = context.new_page()
    page.goto(f"{base_url}/parabank/index.htm", wait_until="domcontentloaded")
    page.locator('input[name="username"]').fill(credentials.username)
    page.locator('input[name="password"]').fill(credentials.password)
    page.locator('input[value="Log In"]').click()
    page.wait_for_url("**/overview.htm", timeout=10_000)
    state = context.storage_state()
    context.close()
    return state


@pytest.fixture
def page(
    browser: Browser, auth_state: dict, request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[Page]:
    """Authenticated page with a fresh context per test."""
    yield from _managed_page(browser, request, tmp_path, storage_state=auth_state)


@pytest.fixture
def unauth_page(
    browser: Browser, request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[Page]:
    """Unauthenticated page — for login and registration tests."""
    yield from _managed_page(browser, request, tmp_path)


def _managed_page(
    browser: Browser,
    request: pytest.FixtureRequest,
    tmp_path: Path,
    storage_state: dict | None = None,
) -> Iterator[Page]:
    """Page with retain-on-failure artifacts.

    A Playwright trace (per-step screenshots, DOM snapshots, network, console)
    and a video are always recorded, but attached to the Allure report only
    when the test fails; for passing tests they are discarded.
    """
    context = browser.new_context(
        viewport=VIEWPORT,
        storage_state=storage_state,
        record_video_dir=tmp_path,
    )
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    yield page

    failed = request.node.stash.get(_test_failed_key, False)
    trace_path = tmp_path / "trace.zip"
    context.tracing.stop(path=str(trace_path) if failed else None)
    context.close()  # finalizes the video file

    video_path = Path(page.video.path()) if page.video else None
    if failed:
        allure.attach.file(trace_path, name="playwright-trace", extension="zip")
        if video_path is not None:
            allure.attach.file(
                video_path, name="video", attachment_type=allure.attachment_type.WEBM
            )
    elif video_path is not None:
        video_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Failure evidence: screenshot + optional AI diagnosis in the Allure report
# ---------------------------------------------------------------------------

@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    report = yield
    if report.when == "call":
        item.stash[_test_failed_key] = report.failed
        if report.failed:
            _attach_failure_evidence(item, report)
    return report


def _attach_failure_evidence(item: pytest.Item, report: pytest.TestReport) -> None:
    page = next(
        (item.funcargs[name] for name in ("page", "unauth_page") if name in item.funcargs),
        None,
    )
    if page is not None:
        try:
            allure.attach(
                page.screenshot(full_page=True),
                name="failure-screenshot",
                attachment_type=allure.attachment_type.PNG,
            )
        except Exception:
            pass  # page/context already closed — screenshot is best-effort

    if os.getenv("AI_ANALYSIS", "false").lower() != "true":
        return
    from ai.failure_analyzer import analyze_failure

    try:
        analysis = analyze_failure(item.nodeid, report.longreprtext)
    except Exception as exc:
        analysis = f"AI analysis unavailable: {exc}"
    allure.attach(
        analysis,
        name="AI failure analysis",
        attachment_type=allure.attachment_type.TEXT,
    )
