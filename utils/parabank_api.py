"""Thin HTTP client for the ParaBank demo application.

Used directly by API tests and by fixtures for test-data setup
(self-registration, opening extra accounts).
"""
import uuid
from dataclasses import dataclass

import httpx

REGISTRATION_SUCCESS_MARKER = "Your account was created successfully"


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str


class ParabankApi:
    """Client for the ParaBank REST API (/parabank/services/bank).

    Methods return raw ``httpx.Response`` so tests can assert on status codes
    and bodies explicitly instead of hiding them behind the client.
    """

    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(
            base_url=f"{base_url}/parabank/services/bank",
            headers={"Accept": "application/json"},
            timeout=30,
        )

    def close(self) -> None:
        self._client.close()

    def login(self, credentials: Credentials) -> httpx.Response:
        return self._client.get(f"/login/{credentials.username}/{credentials.password}")

    def get_accounts(self, customer_id: int) -> httpx.Response:
        return self._client.get(f"/customers/{customer_id}/accounts")

    def get_account(self, account_id: int) -> httpx.Response:
        return self._client.get(f"/accounts/{account_id}")

    def create_account(self, customer_id: int, from_account_id: int) -> httpx.Response:
        """Open a new CHECKING account funded from an existing one."""
        return self._client.post(
            "/createAccount",
            params={
                "customerId": customer_id,
                "newAccountType": 0,
                "fromAccountId": from_account_id,
            },
        )

    def transfer(self, from_account_id: int, to_account_id: int, amount: str) -> httpx.Response:
        return self._client.post(
            "/transfer",
            params={
                "fromAccountId": from_account_id,
                "toAccountId": to_account_id,
                "amount": amount,
            },
        )


def register_customer(base_url: str) -> Credentials:
    """Register a fresh customer through the public web form.

    ParaBank's demo database is wiped periodically, so the suite provisions
    its own user instead of relying on a pre-created one. The form endpoint
    rejects cookieless POSTs, hence the warm-up GET to obtain a JSESSIONID.
    """
    credentials = Credentials(
        username=f"qa_{uuid.uuid4().hex[:10]}",
        password=uuid.uuid4().hex[:12],
    )
    with httpx.Client(base_url=f"{base_url}/parabank", timeout=30) as client:
        client.get("/register.htm")
        response = client.post(
            "/register.htm",
            data={
                "customer.firstName": "QA",
                "customer.lastName": "Automation",
                "customer.address.street": "1 Test Street",
                "customer.address.city": "Testville",
                "customer.address.state": "TS",
                "customer.address.zipCode": "00000",
                "customer.phoneNumber": "5551234567",
                "customer.ssn": "123-45-6789",
                "customer.username": credentials.username,
                "customer.password": credentials.password,
                "repeatedPassword": credentials.password,
            },
        )
    if REGISTRATION_SUCCESS_MARKER not in response.text:
        raise RuntimeError(
            f"Self-registration failed (HTTP {response.status_code}) — "
            "ParaBank demo may be down or the register form changed"
        )
    return credentials
