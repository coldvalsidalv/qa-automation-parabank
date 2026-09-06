"""Fixtures shared by the error-message gate and the AI judging lane.

Here rather than in either test module: `tests/api/` and `tests/ai/` both need
them, and importing a fixture across test modules re-binds the name, which the
linter rightly flags.
"""

from collections.abc import Iterator

import pytest

from tests.error_probes import Customer
from utils.parabank_api import ParabankApi, register_customer


@pytest.fixture(scope="module")
def message_api(base_url: str) -> Iterator[ParabankApi]:
    client = ParabankApi(base_url)
    yield client
    client.close()


@pytest.fixture(scope="module")
def error_customer(base_url: str, message_api: ParabankApi) -> Customer:
    """A funded customer of this module's own, so probes that move money or
    trip a defect cannot disturb the shared session fixtures.

    Each step is checked. Chaining `.json()["id"]` onto an unverified response
    turns a failed login into a JSONDecodeError against ParaBank's HTML error
    page, which says nothing about which step failed or for which customer.
    """
    credentials = register_customer(base_url)
    login = message_api.login(credentials)
    assert login.status_code == 200, (
        f"Setup: could not log in as {credentials.username}: {login.status_code} {login.text}"
    )
    customer_id = login.json()["id"]

    accounts = message_api.get_accounts(customer_id).json()
    assert accounts, f"Setup: customer {customer_id} was registered with no account"
    account_id = accounts[0]["id"]
    message_api.deposit(account_id, "1000.00")
    return customer_id, account_id
