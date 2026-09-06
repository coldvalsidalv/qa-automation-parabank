"""ParaBank REST API tests — login and accounts.

Defect found by running the suite under pytest-xdist:
  D-26  Concurrent createAccount calls fail with 400 "Could not create new
        account". The same requests all succeed when serialised, and the
        failure happens whether or not the customers are distinct — so it is
        global write contention, not a per-customer lock.
"""

from collections.abc import Iterator
from typing import cast

import allure
import pytest

from utils.concurrency import burst_until_failure
from utils.parabank_api import Credentials, ParabankApi, open_account, register_customer

pytestmark = [
    allure.feature("Accounts"),
    allure.story("Accounts API"),
    allure.severity(allure.severity_level.CRITICAL),
]


@pytest.fixture(scope="module")
def accounts(api: ParabankApi, customer_id: int) -> list[dict]:
    response = api.get_accounts(customer_id)
    assert response.status_code == 200
    return cast(list[dict], response.json())


# ------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.api
def test_login_returns_customer(api: ParabankApi, credentials: Credentials) -> None:
    response = api.login(credentials)
    with allure.step("Verify 200 and customer object fields"):
        assert response.status_code == 200
        customer = response.json()
        assert isinstance(customer["id"], int) and customer["id"] > 0
        assert isinstance(customer["firstName"], str) and customer["firstName"]
        assert isinstance(customer["lastName"], str) and customer["lastName"]


@pytest.mark.api
def test_login_with_invalid_credentials_returns_400(api: ParabankApi) -> None:
    response = api.login(Credentials("no_such_user_xyz", "wrong_password"))
    with allure.step("Verify 400 and error message"):
        assert response.status_code == 400
        assert "Invalid username and/or password" in response.text


# ------------------------------------------------------------------
# Account list
# ------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.api
def test_customer_has_accounts(accounts: list[dict]) -> None:
    with allure.step("Verify the customer has at least one account"):
        assert len(accounts) > 0


@pytest.mark.api
def test_account_fields(accounts: list[dict]) -> None:
    acc = accounts[0]
    with allure.step("Verify required fields are present and correctly typed"):
        assert isinstance(acc["id"], int) and acc["id"] > 0
        assert isinstance(acc["customerId"], int) and acc["customerId"] > 0
        assert acc["type"] in ("CHECKING", "SAVINGS", "LOAN")
        assert isinstance(acc["balance"], (int, float))


# ------------------------------------------------------------------
# Get account by ID
# ------------------------------------------------------------------


@pytest.mark.api
def test_get_account_by_id_matches(api: ParabankApi, accounts: list[dict]) -> None:
    expected = accounts[0]
    response = api.get_account(expected["id"])
    with allure.step("Verify the returned account matches the requested one"):
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == expected["id"]
        assert data["customerId"] == expected["customerId"]
        assert data["type"] == expected["type"]


@pytest.mark.api
def test_get_nonexistent_account_returns_error(api: ParabankApi) -> None:
    response = api.get_account(9999999)
    with allure.step("Verify 400 and a not-found message for an unknown account id"):
        # 400 with a specific message, not merely "non-200": ParaBank returns
        # HTTP 500 for bad input in several places (D-14, D-20, D-22), so a
        # `!= 200` assertion would stay green if this endpoint regressed to a
        # crash — the very defect class this suite documents elsewhere.
        assert response.status_code == 400, response.text
        assert "Could not find account" in response.text
        assert "9999999" in response.text


# ------------------------------------------------------------------
# Create account
# ------------------------------------------------------------------


@pytest.mark.api
def test_create_checking_account(api: ParabankApi, customer_id: int, accounts: list[dict]) -> None:
    from_id = accounts[0]["id"]
    response = open_account(api, customer_id, from_account_id=from_id, account_type=0)
    with allure.step("Verify 200 and the new account is CHECKING"):
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["id"], int) and data["id"] > 0
        assert data["customerId"] == customer_id
        assert data["type"] == "CHECKING"


@pytest.mark.api
def test_create_savings_account(api: ParabankApi, customer_id: int, accounts: list[dict]) -> None:
    from_id = accounts[0]["id"]
    response = open_account(api, customer_id, from_account_id=from_id, account_type=1)
    with allure.step("Verify 200 and the new account is SAVINGS"):
        assert response.status_code == 200
        assert response.json()["type"] == "SAVINGS"


@pytest.mark.api
def test_new_account_appears_in_account_list(
    api: ParabankApi, customer_id: int, accounts: list[dict]
) -> None:
    from_id = accounts[0]["id"]
    new_id = open_account(api, customer_id, from_account_id=from_id).json()["id"]
    all_ids = {a["id"] for a in api.get_accounts(customer_id).json()}
    with allure.step("Verify newly created account appears in the customer's account list"):
        assert new_id in all_ids


# Six matches the probe that isolated D-26: 3 of 6 concurrent calls failed
# while 6 of 6 sequential calls succeeded. Below six the defect starts to slip
# through, which a strict xfail cannot tolerate.
CONCURRENT_ACCOUNT_CREATIONS = 6


@pytest.fixture(scope="module")
def contention_api(base_url: str) -> Iterator[ParabankApi]:
    """Client for the D-26 tests, with its own session."""
    client = ParabankApi(base_url)
    yield client
    client.close()


@pytest.fixture(scope="module")
def contention_customer(base_url: str, contention_api: ParabankApi) -> tuple[int, int]:
    """A customer of this module's own for the D-26 tests.

    These tests open up to `CONCURRENT_ACCOUNT_CREATIONS` accounts per burst and
    cannot compensate the funding account the way `isolated_account_factory`
    does — the whole point is to fire the openings concurrently, so waiting to
    deposit each $100 back would serialise them and the defect would not
    reproduce. Running them against the shared session customer would therefore
    drain `account_pair[0]` by hundreds of dollars and bury its overview table
    under dozens of throwaway accounts, which is exactly the shared-state
    coupling the isolation fixtures exist to prevent.

    Each provisioning step is checked: these tests exist to diagnose ParaBank's
    write-path contention, so a setup failure that surfaced as a raw
    JSONDecodeError would send a reader after the defect instead of the setup.

    Returns (customer_id, funding account id).
    """
    credentials = register_customer(base_url)
    login = contention_api.login(credentials)
    assert login.status_code == 200, (
        f"Setup: could not log in as {credentials.username}: {login.status_code} {login.text}"
    )
    customer_id = login.json()["id"]

    accounts = contention_api.get_accounts(customer_id).json()
    assert accounts, f"Setup: customer {customer_id} was registered with no account"
    account_id = accounts[0]["id"]
    contention_api.deposit(account_id, "5000.00")
    return customer_id, account_id


@pytest.mark.api
@pytest.mark.xfail(
    strict=True,
    reason="Known defect D-26: concurrent createAccount calls fail with 400",
)
def test_concurrent_account_creation_all_succeed(
    contention_api: ParabankApi, contention_customer: tuple[int, int]
) -> None:
    """Opening N accounts at once must open N accounts.

    Nothing in the request is contended by design: each call is an independent
    insert, and serialising the very same calls succeeds every time.
    """
    customer_id, from_id = contention_customer
    responses = burst_until_failure(
        lambda _: contention_api.create_account(customer_id, from_account_id=from_id),
        size=CONCURRENT_ACCOUNT_CREATIONS,
        is_failure=lambda r: r.status_code != 200,
    )

    with allure.step(f"Verify all {CONCURRENT_ACCOUNT_CREATIONS} concurrent openings succeeded"):
        failed = [r for r in responses if r.status_code != 200]
        assert not failed, (
            f"{len(failed)}/{CONCURRENT_ACCOUNT_CREATIONS} concurrent account openings failed; "
            f"first: HTTP {failed[0].status_code} {failed[0].text!r}"
        )


@pytest.mark.api
@pytest.mark.defect_proof
def test_account_creation_refused_under_concurrency_succeeds_when_serialised(
    contention_api: ParabankApi, contention_customer: tuple[int, int]
) -> None:
    """Proof that D-26 is contention, not a rejected request.

    Provokes a concurrent failure, then repeats the identical call on its own.
    It succeeds — so the request was always valid and only the concurrency made
    it fail. Asserts the current behavior, so it starts failing once D-26 is
    fixed and no failure can be provoked; that is the signal to delete it.
    """
    customer_id, from_id = contention_customer
    responses = burst_until_failure(
        lambda _: contention_api.create_account(customer_id, from_account_id=from_id),
        size=CONCURRENT_ACCOUNT_CREATIONS,
        is_failure=lambda r: r.status_code != 200,
    )

    assert any(r.status_code != 200 for r in responses), (
        "Expected at least one concurrent account opening to fail (D-26); "
        "if this stops happening the defect may be fixed — delete this test"
    )

    with allure.step("Repeat the identical request serially — it must succeed"):
        retry = contention_api.create_account(customer_id, from_account_id=from_id)
        assert retry.status_code == 200, (
            f"The same request failed serially too (HTTP {retry.status_code} {retry.text!r}) — "
            "that would be an invalid request, not D-26 contention"
        )
