"""ParaBank REST API — authentication / authorization tests.

Defect D-09 (critical): the REST API enforces no authentication or
authorization whatsoever. Every endpoint accepts an unauthenticated request
and operates on any account or customer id supplied in the URL — a textbook
IDOR (Insecure Direct Object Reference). An attacker who only knows (or
guesses — ids are sequential) a victim's account id can read their PII and
withdraw their money.

Defect D-18 (critical): the web admin page (`/parabank/admin.htm`) — including
a "Clean" control that wipes the database — is reachable with zero
authentication, found by exploratory testing. No "living proof" test exists
for this one, unlike D-09's `test_money_theft_is_currently_possible`: actually
submitting the Clean action would wipe the shared local ParaBank instance for
every concurrent test run and developer, not just a scratch account we
created ourselves. The xfail probe below checks both the page render and the
underlying `db.htm` action endpoint, but only ever submits a harmless,
unrecognized `action` value — never `CLEAN` or `INIT`.

These tests are written the way the API *should* behave (the request must be
rejected) and marked xfail(strict=True), so the suite turns green the moment
ParaBank adds access control. The accompanying *_is_currently_unprotected
tests document the live broken behavior without asserting it is correct.
"""

from collections.abc import Iterator

import allure
import httpx
import pytest

from utils.parabank_api import ParabankApi, register_customer


@pytest.fixture
def victim_account(base_url: str) -> tuple[int, int]:
    """Register an isolated 'victim' customer; return (customer_id, account_id).

    Separate from the main `customer_id`/`account_pair` fixtures so the attack
    crosses a real tenant boundary: the attacker never authenticated as this user.
    """
    creds = register_customer(base_url)
    api = ParabankApi(base_url)
    try:
        customer_id = api.login(creds).json()["id"]
        account_id = api.get_accounts(customer_id).json()[0]["id"]
    finally:
        api.close()
    return customer_id, account_id


@pytest.fixture
def anonymous_client(base_url: str) -> Iterator[httpx.Client]:
    """A raw client with no cookies, no session, no auth header — the attacker."""
    with httpx.Client(
        base_url=f"{base_url}/parabank/services/bank",
        headers={"Accept": "application/json"},
        timeout=30,
    ) as client:
        yield client


@allure.feature("Security")
@allure.story("Authentication & authorization")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.api
@pytest.mark.security
class TestApiRequiresAuthorization:
    @pytest.mark.xfail(
        reason="Known defect D-09: API returns another customer's account to an "
        "unauthenticated caller (IDOR)",
        strict=True,
    )
    def test_reading_foreign_account_is_rejected(
        self, anonymous_client: httpx.Client, victim_account: tuple[int, int]
    ) -> None:
        _, account_id = victim_account
        response = anonymous_client.get(f"/accounts/{account_id}")
        with allure.step("An unauthenticated request for another user's account must be denied"):
            assert response.status_code in (401, 403), (
                f"Expected 401/403, got {response.status_code}: leaked {response.text}"
            )

    @pytest.mark.xfail(
        reason="Known defect D-09: API returns another customer's PII to an "
        "unauthenticated caller (IDOR)",
        strict=True,
    )
    def test_reading_foreign_customer_pii_is_rejected(
        self, anonymous_client: httpx.Client, victim_account: tuple[int, int]
    ) -> None:
        customer_id, _ = victim_account
        response = anonymous_client.get(f"/customers/{customer_id}")
        with allure.step("An unauthenticated request for another user's profile must be denied"):
            assert response.status_code in (401, 403), (
                f"Expected 401/403, got {response.status_code}: leaked {response.text}"
            )

    @pytest.mark.xfail(
        reason="Known defect D-09: API lets an unauthenticated caller withdraw from "
        "another customer's account — money theft",
        strict=True,
    )
    def test_withdrawing_from_foreign_account_is_rejected(
        self, anonymous_client: httpx.Client, victim_account: tuple[int, int]
    ) -> None:
        _, account_id = victim_account
        response = anonymous_client.post(
            "/withdraw", params={"accountId": account_id, "amount": "100"}
        )
        with allure.step("An unauthenticated withdrawal from another account must be denied"):
            assert response.status_code in (401, 403), (
                f"Expected 401/403, got {response.status_code}: {response.text}"
            )


@allure.feature("Security")
@allure.story("Authentication & authorization")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.api
@pytest.mark.security
@pytest.mark.defect_proof
def test_money_theft_is_currently_possible(
    anonymous_client: httpx.Client, victim_account: tuple[int, int]
) -> None:
    """Living proof of D-09: documents the exploit end to end.

    Asserts the *currently broken* behavior so the report shows a passing,
    explicit demonstration of the vulnerability rather than only an xfail.
    Pairs with the strict-xfail tests above, which flip to failing once the
    hole is closed — at which point this test should be deleted.

    Marked `defect_proof` because that makes it a maintenance trap: when
    ParaBank adds access control this test goes RED while the product got
    *better*. The marker is the escape hatch — `-m "not ai_demo and not
    defect_proof"` deselects every such test at once (spelling out `not
    ai_demo` matters: a command-line `-m` replaces the one in `addopts`
    rather than combining with it) — and the assertion messages below say
    what to do instead of leaving the next reader to guess.
    """
    _, account_id = victim_account
    with allure.step("Attacker reads the victim's balance with no credentials"):
        before = anonymous_client.get(f"/accounts/{account_id}").json()["balance"]
    with allure.step("Attacker withdraws $100 from the victim's account"):
        stolen = anonymous_client.post(
            "/withdraw", params={"accountId": account_id, "amount": "100"}
        )
        assert stolen.status_code == 200, (
            "D-09 may be FIXED: an unauthenticated withdrawal was rejected "
            f"({stolen.status_code}). If so, delete this test and expect the "
            "strict xfails above to XPASS."
        )
    with allure.step("The victim's balance dropped — money left the account"):
        after = anonymous_client.get(f"/accounts/{account_id}").json()["balance"]
        assert after == pytest.approx(before - 100, abs=0.01), (
            f"D-09 may be FIXED: balance did not move ({before} -> {after}). "
            "If so, delete this test."
        )


@allure.feature("Security")
@allure.story("Authentication & authorization")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.api
@pytest.mark.security
@pytest.mark.xfail(
    reason="Known defect D-18: the admin page (incl. a destructive DB-wipe control) has no auth",
    strict=True,
)
def test_admin_page_requires_authentication(base_url: str) -> None:
    # Deliberately never sends action=CLEAN or action=INIT — those really
    # wipe/reseed the database for every concurrent user of this ParaBank
    # instance. action=PROBE reaches the same db.htm endpoint's request
    # handling (confirmed live: it neither cleans nor initializes anything)
    # without triggering the destructive behavior, so this is safe to run.
    with httpx.Client(base_url=base_url, timeout=30) as client:
        page_response = client.get("/parabank/admin.htm")
        action_response = client.post("/parabank/db.htm", data={"action": "PROBE"})
    with allure.step("An anonymous request for the admin page must be denied"):
        assert page_response.status_code in (401, 403), (
            f"Expected 401/403, got {page_response.status_code}: admin page is reachable "
            "with no authentication"
        )
    with allure.step("An anonymous POST to the db.htm action endpoint must be denied"):
        assert action_response.status_code in (401, 403), (
            f"Expected 401/403, got {action_response.status_code}: the underlying db.htm "
            "endpoint (which the Clean/Initialize controls submit to) accepts unauthenticated "
            "requests, not just the page that renders the buttons"
        )
