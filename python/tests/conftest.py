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
    trip a defect cannot disturb the shared session fixtures."""
    credentials = register_customer(base_url)
    customer_id = message_api.login(credentials).json()["id"]
    account_id = message_api.get_accounts(customer_id).json()[0]["id"]
    message_api.deposit(account_id, "1000.00")
    return customer_id, account_id
