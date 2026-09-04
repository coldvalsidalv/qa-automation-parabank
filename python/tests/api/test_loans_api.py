"""ParaBank REST API tests — loan requests.

Defects found by exploratory testing:
  D-19  A negative down payment is accepted, the loan is approved, and the
        account is credited the |down payment| instead of debited.
  D-20  A zero loan amount leaks a raw Java exception message ("/ by zero")
        in the response body instead of a validation error.
"""

from collections.abc import Iterator

import allure
import pytest

from utils.contracts import schema_violations
from utils.parabank_api import ParabankApi, register_customer

pytestmark = [
    allure.feature("Loans"),
    allure.story("Loan request API"),
    allure.severity(allure.severity_level.NORMAL),
]


@pytest.fixture(scope="module")
def loan_api(base_url: str) -> Iterator[ParabankApi]:
    """Fresh ParabankApi client for loan tests — keeps its own httpx session."""
    client = ParabankApi(base_url)
    yield client
    client.close()


def _register_loan_customer(
    base_url: str, loan_api: ParabankApi, *, deposit: str | None = "5000.00"
) -> tuple[int, int]:
    """Register a fresh customer + account for a loan test, optionally funded.

    `deposit=None` skips the deposit call entirely — for tests where the
    defect being probed fires before any balance check, so funding the
    account would just be a wasted HTTP round trip.
    """
    creds = register_customer(base_url)
    cid = loan_api.login(creds).json()["id"]
    acc_id = loan_api.get_accounts(cid).json()[0]["id"]
    if deposit is not None:
        loan_api.deposit(acc_id, deposit)
    return cid, acc_id


@pytest.fixture(scope="module")
def loan_customer(base_url: str, loan_api: ParabankApi) -> tuple[int, int]:
    """Register a brand-new customer so loan scoring is not skewed by the
    main test customer's negative balances (D-06 overdraft defect leaves
    account_pair[0] deep in the red, which causes loan declines).

    Returns (customer_id, account_id).
    """
    return _register_loan_customer(base_url, loan_api)


@pytest.mark.smoke
@pytest.mark.api
def test_request_loan_approved(loan_api: ParabankApi, loan_customer: tuple[int, int]) -> None:
    cid, acc_id = loan_customer
    response = loan_api.request_loan(cid, amount="1000", down_payment="500", from_account_id=acc_id)
    with allure.step("Verify 200 and loan is approved"):
        assert response.status_code == 200
        data = response.json()
        assert data["approved"] is True, f"Loan declined: {data.get('message')}"
        assert isinstance(data["accountId"], int) and data["accountId"] > 0


@pytest.mark.api
def test_request_loan_response_fields(
    loan_api: ParabankApi, loan_customer: tuple[int, int]
) -> None:
    cid, acc_id = loan_customer
    data = loan_api.request_loan(
        cid, amount="500", down_payment="200", from_account_id=acc_id
    ).json()
    with allure.step("Verify all expected fields are present"):
        assert isinstance(data["responseDate"], int) and data["responseDate"] > 0
        assert isinstance(data["loanProviderName"], str) and data["loanProviderName"]
        assert isinstance(data["approved"], bool)


@pytest.mark.api
def test_request_loan_creates_new_loan_account(
    loan_api: ParabankApi, loan_customer: tuple[int, int]
) -> None:
    cid, acc_id = loan_customer
    response = loan_api.request_loan(cid, amount="500", down_payment="200", from_account_id=acc_id)
    data = response.json()
    with allure.step("Verify a new LOAN account was created and is retrievable"):
        assert data["approved"] is True, f"Loan declined: {data.get('message')}"
        new_account_id = data["accountId"]
        new_account = loan_api.get_account(new_account_id).json()
        assert new_account["type"] == "LOAN"
        assert new_account["id"] == new_account_id
    with allure.step("A LOAN account still matches the 'account' contract"):
        # The only place in the suite with a guaranteed-approved loan, so this is
        # the only place the contract's LOAN account type actually gets exercised;
        # every test in test_contracts_api.py reads a CHECKING account.
        violations = schema_violations(new_account, "account")
        assert not violations, "LOAN account breaks the 'account' contract:\n" + "\n".join(
            violations
        )


@pytest.mark.api
def test_request_loan_down_payment_exceeding_amount(
    loan_api: ParabankApi, loan_customer: tuple[int, int]
) -> None:
    cid, acc_id = loan_customer
    response = loan_api.request_loan(cid, amount="100", down_payment="200", from_account_id=acc_id)
    with allure.step("Verify the API handles down payment > loan amount gracefully"):
        assert response.status_code in (200, 400)
        if response.status_code == 200:
            assert isinstance(response.json().get("approved"), bool)


@pytest.fixture
def isolated_loan_customer(base_url: str, loan_api: ParabankApi) -> tuple[int, int]:
    """A customer+account dedicated to a single mutating test, separate from
    the module-scoped `loan_customer` shared by the read-oriented tests above.

    D-19 below credits money to the account even when the xfail assertion
    fails (the API call itself still executes) — sharing `loan_customer`
    would silently inflate its balance for every other test in this module.
    """
    return _register_loan_customer(base_url, loan_api)


@pytest.fixture
def isolated_loan_customer_unfunded(base_url: str, loan_api: ParabankApi) -> tuple[int, int]:
    """Like `isolated_loan_customer`, but skips the $5000 deposit.

    D-20 below is a division-by-the-requested-amount that fires before any
    balance check (verified live: reproduces identically on a freshly
    registered, undeposited account) — funding it would be dead setup.
    """
    return _register_loan_customer(base_url, loan_api, deposit=None)


@pytest.mark.api
@pytest.mark.xfail(
    strict=True,
    reason="Known defect D-19: negative down payment accepted instead of rejected",
)
def test_request_loan_negative_down_payment_is_rejected(
    loan_api: ParabankApi, isolated_loan_customer: tuple[int, int]
) -> None:
    cid, acc_id = isolated_loan_customer
    response = loan_api.request_loan(
        cid, amount="1000", down_payment="-500", from_account_id=acc_id
    )
    with allure.step("Verify a negative down payment is rejected"):
        assert response.status_code >= 400


@pytest.mark.api
@pytest.mark.security
@pytest.mark.defect_proof
def test_negative_down_payment_currently_creates_money(
    loan_api: ParabankApi, isolated_loan_customer: tuple[int, int]
) -> None:
    """Living proof of D-19: a negative down payment gets approved and credits money.

    `defect_proof`: goes RED when ParaBank fixes D-19. Delete it then — the
    strict xfail above is what should stay and turn green.
    """
    cid, acc_id = isolated_loan_customer
    balance_before = loan_api.get_account(acc_id).json()["balance"]
    with allure.step("Request a loan with down_payment=-500"):
        response = loan_api.request_loan(
            cid, amount="1000", down_payment="-500", from_account_id=acc_id
        )
        assert response.status_code == 200, (
            f"D-19 may be FIXED: negative down payment rejected ({response.status_code}). "
            "If so, delete this test."
        )
        assert response.json()["approved"] is True, "D-19 may be FIXED: loan declined."
    with allure.step("Verify the account was credited $500, not debited"):
        balance_after = loan_api.get_account(acc_id).json()["balance"]
        assert balance_after == pytest.approx(balance_before + 500.00, abs=0.01), (
            f"D-19 may be FIXED: balance moved {balance_before} -> {balance_after}, "
            "expected a +500.00 credit. If so, delete this test."
        )


@pytest.mark.api
@pytest.mark.xfail(
    strict=True,
    reason="Known defect D-20: a zero loan amount leaks a raw internal exception message",
)
def test_request_loan_zero_amount_does_not_leak_internal_error(
    loan_api: ParabankApi, isolated_loan_customer_unfunded: tuple[int, int]
) -> None:
    cid, acc_id = isolated_loan_customer_unfunded
    response = loan_api.request_loan(cid, amount="0", down_payment="0", from_account_id=acc_id)
    with allure.step("Verify no raw internal exception text leaks to the client"):
        assert "by zero" not in response.text
