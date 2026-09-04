"""Shared fixtures and the AI failure-analysis hook.

The suite is self-sufficient: if TEST_USERNAME/TEST_PASSWORD are not set,
it registers a fresh ParaBank customer for the session, so no secrets are
required either locally or in CI.
"""

import json
import os
import platform
from collections.abc import Callable, Generator, Iterator
from importlib.metadata import version
from pathlib import Path
from typing import cast

import allure
import pytest
from dotenv import load_dotenv
from playwright.sync_api import (
    Browser,
    Page,
    Playwright,
    StorageState,
    ViewportSize,
    sync_playwright,
)

from pages.login_page import LoginPage
from utils.parabank_api import Credentials, ParabankApi, register_customer

load_dotenv()

# Default to the local app: the public demo wipes its database every few
# minutes, so a clone-and-run without a .env should still hit a stable target.
DEFAULT_BASE_URL = "http://localhost:8080"
VIEWPORT: ViewportSize = {"width": 1440, "height": 900}

# Set by the makereport hook, read by page fixtures on teardown to decide
# whether to keep the trace/video (retain-on-failure policy).
_test_failed_key = pytest.StashKey[bool]()


# ---------------------------------------------------------------------------
# Allure report metadata: environment widget + failure categories
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    results_dir = _allure_results_dir(config)
    if results_dir is None:
        return
    results_dir.mkdir(parents=True, exist_ok=True)
    _write_allure_environment(results_dir)
    _write_allure_categories(results_dir)


def _allure_results_dir(config: pytest.Config) -> Path | None:
    raw = config.getoption("--alluredir", default=None)
    return Path(raw) if raw else None


def _write_allure_environment(results_dir: Path) -> None:
    env = {
        "Base.URL": os.getenv("BASE_URL", DEFAULT_BASE_URL),
        "App.Under.Test": "ParaBank (parasoft/parabank)",
        "Python": platform.python_version(),
        "Playwright": version("playwright"),
        "OS": f"{platform.system()} {platform.release()}",
        "AI.Analysis": os.getenv("AI_ANALYSIS", "false"),
        "Self.Heal": os.getenv("SELF_HEAL", "false"),
        "LLM.Model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
    }
    (results_dir / "environment.properties").write_text(
        "\n".join(f"{key}={value}" for key, value in env.items()), encoding="utf-8"
    )


def _write_allure_categories(results_dir: Path) -> None:
    # Classifies results on the report's Categories tab. Known ParaBank defects
    # land in their own bucket so a green xfail run reads as "documented defects",
    # not noise; genuine product/test breakages stay separate.
    categories = [
        {
            "name": "Known ParaBank defects (xfail)",
            "matchedStatuses": ["skipped"],
            # Allure compiles this with Pattern.DOTALL and applies it with
            # matches(), i.e. a *full* match against the whole status message
            # (allure2 CategoriesPlugin.matches). Two consequences: the wrapping
            # `.*` are required, and no `(?s)` is needed — `.` already spans the
            # newlines between an xfail's reason and its traceback. The body is
            # deliberately just "defect": reasons are worded both "Known defect
            # D-14" and "Known ParaBank defect", and matching on "known" alone
            # silently dropped every xfail in test_security_api.py.
            "messageRegex": ".*[Dd]efect.*",
        },
        {
            "name": "Application defect (server error)",
            "matchedStatuses": ["failed", "broken"],
            "messageRegex": ".*(500|Internal [Ss]erver [Ee]rror).*",
        },
        {
            "name": "Test infrastructure problem",
            "matchedStatuses": ["broken"],
            "messageRegex": ".*(ConnectError|Timeout|Connection refused).*",
        },
        {
            "name": "Product bug",
            "matchedStatuses": ["failed"],
        },
    ]
    (results_dir / "categories.json").write_text(json.dumps(categories, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Environment and test data
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("BASE_URL", DEFAULT_BASE_URL)


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
        f"API login failed for {credentials.username}: {response.status_code} {response.text}"
    )
    return cast(int, response.json()["id"])


def _open_account(api: ParabankApi, customer_id: int, from_id: int) -> int:
    """Open a new account funded from `from_id`; return the new account's id."""
    response = api.create_account(customer_id, from_account_id=from_id)
    assert response.status_code == 200, f"Could not open an account: {response.text}"
    return cast(int, response.json()["id"])


@pytest.fixture(scope="session")
def account_pair(api: ParabankApi, customer_id: int) -> tuple[int, int]:
    """IDs of two distinct accounts; opens a second one for fresh customers."""
    accounts = api.get_accounts(customer_id).json()
    if len(accounts) < 2:
        _open_account(api, customer_id, accounts[0]["id"])
        accounts = api.get_accounts(customer_id).json()
    return accounts[0]["id"], accounts[1]["id"]


@pytest.fixture
def isolated_account_factory(api: ParabankApi, customer_id: int) -> Callable[[], int]:
    """Factory for fresh accounts isolated from `account_pair` and from each other.

    Use this directly when a test needs more than one isolated account (e.g.
    both legs of a transfer); use `isolated_account` for the common
    single-account case. Each call opens a new account funded from the
    customer's first account and immediately deposits the funding amount
    back — ParaBank's createAccount transfers $100 out of the funding
    account into the new one, and without the compensating deposit that
    debit would land on a shared account, defeating the whole point of
    isolation.
    """
    from_id = api.get_accounts(customer_id).json()[0]["id"]

    def _open() -> int:
        new_id = _open_account(api, customer_id, from_id)
        api.deposit(from_id, "100.00")
        return new_id

    return _open


@pytest.fixture
def isolated_account(isolated_account_factory: Callable[[], int]) -> int:
    """A fresh account opened just for the requesting test.

    Use this instead of acting directly on the shared, session-scoped
    `account_pair` whenever a test's action could leave state other tests
    read or rely on (an overdraft, a negative-amount defect probe that
    actually goes through, a throwaway position) — each caller gets its own
    account, so nothing else is affected no matter what order tests run in.
    """
    return isolated_account_factory()


@pytest.fixture
def isolated_customer_id(base_url: str, api: ParabankApi) -> int:
    """A fresh customer, registered just for the requesting test.

    Use this instead of the shared, session-scoped `customer_id` whenever a
    test mutates customer-level fields (name, address, SSN, ...) — the same
    isolation `isolated_account` gives account-level mutations, one level up.
    """
    credentials = register_customer(base_url)
    response = api.login(credentials)
    assert response.status_code == 200, (
        f"Could not log in isolated customer {credentials.username}: {response.text}"
    )
    return cast(int, response.json()["id"])


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
def auth_state(browser: Browser, base_url: str, credentials: Credentials) -> StorageState:
    """Log in through the UI once per session; reuse the storage state everywhere."""
    context = browser.new_context(viewport=VIEWPORT)
    page = context.new_page()
    LoginPage(page, base_url).open().login(credentials.username, credentials.password)
    page.wait_for_url("**/overview.htm", timeout=10_000)
    state = context.storage_state()
    context.close()
    return state


@pytest.fixture
def page(
    browser: Browser, auth_state: StorageState, request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[Page]:
    """Authenticated page with a fresh context per test."""
    yield from _managed_page(browser, request, tmp_path, storage_state=auth_state)


@pytest.fixture
def unauth_page(browser: Browser, request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Page]:
    """Unauthenticated page — for login and registration tests."""
    yield from _managed_page(browser, request, tmp_path)


def _managed_page(
    browser: Browser,
    request: pytest.FixtureRequest,
    tmp_path: Path,
    storage_state: StorageState | None = None,
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
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    if report.when == "call":
        item.stash[_test_failed_key] = report.failed
        if report.failed:
            _attach_failure_evidence(item, report)
    return report


def _attach_failure_evidence(item: pytest.Item, report: pytest.TestReport) -> None:
    funcargs = getattr(item, "funcargs", {})
    page = next(
        (funcargs[name] for name in ("page", "unauth_page") if name in funcargs),
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
        error_log = report.longreprtext
    except Exception as exc:
        error_log = f"<failed to format traceback: {exc}>"
    analysis = analyze_failure(item.nodeid, error_log)
    allure.attach(
        analysis,
        name="AI failure analysis",
        attachment_type=allure.attachment_type.TEXT,
    )
