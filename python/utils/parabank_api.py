"""Thin HTTP client for the ParaBank demo application.

Used directly by API tests and by fixtures for test-data setup
(self-registration, opening extra accounts).
"""

import uuid
from dataclasses import dataclass

import allure
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

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    # Allure stringifies args before formatting titles, so no {credentials.username} here.
    @allure.step("API: log in")
    def login(self, credentials: Credentials) -> httpx.Response:
        return self._client.get(f"/login/{credentials.username}/{credentials.password}")

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    @allure.step("API: get customer {customer_id}")
    def get_customer(self, customer_id: int) -> httpx.Response:
        return self._client.get(f"/customers/{customer_id}")

    @allure.step("API: update customer {customer_id}")
    def update_customer(self, customer_id: int, **fields: str) -> httpx.Response:
        return self._client.post(f"/customers/update/{customer_id}", params=fields)

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    @allure.step("API: get accounts of customer {customer_id}")
    def get_accounts(self, customer_id: int) -> httpx.Response:
        return self._client.get(f"/customers/{customer_id}/accounts")

    @allure.step("API: get account {account_id}")
    def get_account(self, account_id: int) -> httpx.Response:
        return self._client.get(f"/accounts/{account_id}")

    @allure.step("API: open a new account for customer {customer_id}")
    def create_account(
        self, customer_id: int, from_account_id: int, account_type: int = 0
    ) -> httpx.Response:
        """0 = CHECKING, 1 = SAVINGS."""
        return self._client.post(
            "/createAccount",
            params={
                "customerId": customer_id,
                "newAccountType": account_type,
                "fromAccountId": from_account_id,
            },
        )

    # ------------------------------------------------------------------
    # Deposits / withdrawals
    # ------------------------------------------------------------------

    @allure.step("API: deposit {amount} to account {account_id}")
    def deposit(self, account_id: int, amount: str) -> httpx.Response:
        return self._client.post("/deposit", params={"accountId": account_id, "amount": amount})

    @allure.step("API: withdraw {amount} from account {account_id}")
    def withdraw(self, account_id: int, amount: str) -> httpx.Response:
        return self._client.post("/withdraw", params={"accountId": account_id, "amount": amount})

    # ------------------------------------------------------------------
    # Transfers
    # ------------------------------------------------------------------

    @allure.step("API: transfer {amount} from {from_account_id} to {to_account_id}")
    def transfer(self, from_account_id: int, to_account_id: int, amount: str) -> httpx.Response:
        return self._client.post(
            "/transfer",
            params={
                "fromAccountId": from_account_id,
                "toAccountId": to_account_id,
                "amount": amount,
            },
        )

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    @allure.step("API: list transactions for account {account_id}")
    def get_transactions(self, account_id: int) -> httpx.Response:
        return self._client.get(f"/accounts/{account_id}/transactions")

    @allure.step("API: get transaction {transaction_id}")
    def get_transaction(self, transaction_id: int) -> httpx.Response:
        return self._client.get(f"/transactions/{transaction_id}")

    @allure.step("API: transactions for account {account_id} with amount {amount}")
    def get_transactions_by_amount(self, account_id: int, amount: str) -> httpx.Response:
        return self._client.get(f"/accounts/{account_id}/transactions/amount/{amount}")

    @allure.step("API: transactions for account {account_id} from {from_date} to {to_date}")
    def get_transactions_by_date_range(
        self, account_id: int, from_date: str, to_date: str
    ) -> httpx.Response:
        return self._client.get(
            f"/accounts/{account_id}/transactions/fromDate/{from_date}/toDate/{to_date}"
        )

    @allure.step("API: transactions for account {account_id} on {date}")
    def get_transactions_on_date(self, account_id: int, date: str) -> httpx.Response:
        return self._client.get(f"/accounts/{account_id}/transactions/onDate/{date}")

    @allure.step("API: transactions for account {account_id} month={month} type={tx_type}")
    def get_transactions_by_month_type(
        self, account_id: int, month: str, tx_type: str
    ) -> httpx.Response:
        return self._client.get(f"/accounts/{account_id}/transactions/month/{month}/type/{tx_type}")

    # ------------------------------------------------------------------
    # Loans
    # ------------------------------------------------------------------

    @allure.step("API: request loan for customer {customer_id}")
    def request_loan(
        self,
        customer_id: int,
        amount: str,
        down_payment: str,
        from_account_id: int,
    ) -> httpx.Response:
        return self._client.post(
            "/requestLoan",
            params={
                "customerId": customer_id,
                "amount": amount,
                "downPayment": down_payment,
                "fromAccountId": from_account_id,
            },
        )

    # ------------------------------------------------------------------
    # Bill pay
    # ------------------------------------------------------------------

    @allure.step("API: bill pay from account {account_id} amount={amount}")
    def bill_pay(self, account_id: int, amount: str, payee: dict) -> httpx.Response:
        return self._client.post(
            "/billpay",
            params={"accountId": account_id, "amount": amount},
            json=payee,
        )

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    @allure.step("API: buy position for customer {customer_id}")
    def buy_position(
        self,
        customer_id: int,
        account_id: int,
        name: str,
        symbol: str,
        shares: int,
        price_per_share: str,
    ) -> httpx.Response:
        return self._client.post(
            f"/customers/{customer_id}/buyPosition",
            params={
                "accountId": account_id,
                "name": name,
                "symbol": symbol,
                "shares": shares,
                "pricePerShare": price_per_share,
            },
        )

    @allure.step("API: get positions for customer {customer_id}")
    def get_positions(self, customer_id: int) -> httpx.Response:
        return self._client.get(f"/customers/{customer_id}/positions")

    @allure.step("API: get position {position_id}")
    def get_position(self, position_id: int) -> httpx.Response:
        return self._client.get(f"/positions/{position_id}")

    @allure.step("API: get position history {position_id} from {start_date} to {end_date}")
    def get_position_history(
        self, position_id: int, start_date: str, end_date: str
    ) -> httpx.Response:
        return self._client.get(f"/positions/{position_id}/{start_date}/{end_date}")

    @allure.step("API: sell position {position_id} for customer {customer_id}")
    def sell_position(
        self,
        customer_id: int,
        account_id: int,
        position_id: int,
        shares: int,
        price_per_share: str,
    ) -> httpx.Response:
        return self._client.post(
            f"/customers/{customer_id}/sellPosition",
            params={
                "accountId": account_id,
                "positionId": position_id,
                "shares": shares,
                "pricePerShare": price_per_share,
            },
        )


@allure.step("Register a fresh ParaBank customer via the web form")
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
