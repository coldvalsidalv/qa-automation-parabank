"""ParaBank REST API tests — stock positions (buy / get / sell)."""

import allure
import pytest

from utils.parabank_api import ParabankApi

pytestmark = [
    allure.feature("Positions"),
    allure.story("Stock positions API"),
    allure.severity(allure.severity_level.MINOR),
]


def _buy_position(
    api: ParabankApi, customer_id: int, from_id: int, *, name: str, symbol: str
) -> tuple[int, int]:
    """Deposit, buy 10 shares under `symbol`, and return (position_id, shares).

    Filters the buy response by symbol rather than indexing [0]: `account_pair`
    is session-scoped, so by the time this runs the account may already hold
    other positions (see test_buy_position_returns_200 below, which filters for
    the same reason) — index 0 is not reliably "the position just bought".
    """
    api.deposit(from_id, "200.00")
    response = api.buy_position(
        customer_id, from_id, name=name, symbol=symbol, shares=10, price_per_share="10.00"
    )
    assert response.status_code == 200, f"Setup: buy_position failed: {response.text}"
    pos = next((p for p in response.json() if p["symbol"] == symbol), None)
    assert pos is not None, f"{symbol} position not found in buy response"
    return pos["positionId"], pos["shares"]


@pytest.fixture(scope="module")
def position(api: ParabankApi, customer_id: int, account_pair: tuple[int, int]) -> tuple[int, int]:
    """Buy 10 shares of TST; return (position_id, share_count) from the buy response.

    Read-only for the rest of this module: only the two GET tests below consume
    it. Selling is deliberately kept off this fixture (see `sellable_position`)
    because ParaBank may reassign a new positionId after a partial sell, which
    would make this id stale for whichever GET test runs after the sell — a real
    test-order dependency, not a hypothetical one (caught by pytest-randomly).
    """
    from_id, _ = account_pair
    return _buy_position(api, customer_id, from_id, name="TestCorp", symbol="TST")


@pytest.fixture
def sellable_position(api: ParabankApi, customer_id: int, isolated_account: int) -> tuple[int, int]:
    """A position dedicated to the sell test, on its own account — never read
    or mutated by another test.

    Selling mutates (and can invalidate) the position id, so it must not be
    the same id the GET tests above assert against — buying it on
    `isolated_account` rather than the shared `account_pair` account is what
    guarantees that regardless of test order, not just the symbol filter.
    """
    return _buy_position(api, customer_id, isolated_account, name="SellCorp", symbol="SEL")


@pytest.mark.smoke
@pytest.mark.api
def test_buy_position_returns_200(
    api: ParabankApi, customer_id: int, account_pair: tuple[int, int]
) -> None:
    from_id, _ = account_pair
    api.deposit(from_id, "100.00")
    response = api.buy_position(
        customer_id, from_id, name="AcmeCorp", symbol="ACM", shares=5, price_per_share="15.00"
    )
    with allure.step("Verify 200 and position fields"):
        assert response.status_code == 200
        pos = next((p for p in response.json() if p["symbol"] == "ACM"), None)
        assert pos is not None, "ACM position not found in buy response"
        assert isinstance(pos["positionId"], int) and pos["positionId"] > 0
        assert pos["shares"] == 5
        assert pos["purchasePrice"] == pytest.approx(15.00, abs=0.01)


@pytest.mark.api
def test_get_positions_contains_bought_position(
    api: ParabankApi, customer_id: int, position: tuple[int, int]
) -> None:
    pos_id, _ = position
    response = api.get_positions(customer_id)
    with allure.step("Verify the position list contains the newly bought position"):
        assert response.status_code == 200
        ids = [p["positionId"] for p in response.json()]
        assert pos_id in ids


@pytest.mark.api
def test_get_position_by_id(api: ParabankApi, customer_id: int, position: tuple[int, int]) -> None:
    pos_id, _ = position
    response = api.get_position(pos_id)
    with allure.step("Verify 200 and position fields"):
        assert response.status_code == 200
        pos = response.json()
        assert pos["positionId"] == pos_id
        assert pos["customerId"] == customer_id
        assert isinstance(pos["name"], str) and pos["name"]
        assert isinstance(pos["symbol"], str) and pos["symbol"]
        assert isinstance(pos["shares"], int) and pos["shares"] > 0
        assert isinstance(pos["purchasePrice"], (int, float))


@pytest.mark.api
def test_sell_partial_position_reduces_shares(
    api: ParabankApi,
    customer_id: int,
    isolated_account: int,
    sellable_position: tuple[int, int],
) -> None:
    # isolated_account is the same instance sellable_position bought on
    # (pytest caches function-scoped fixtures per test), so this sells shares
    # off the account that actually holds the position.
    pos_id, total_shares = sellable_position
    sell_qty = min(5, total_shares)
    expected_remaining = total_shares - sell_qty

    response = api.sell_position(
        customer_id, isolated_account, position_id=pos_id, shares=sell_qty, price_per_share="12.00"
    )
    with allure.step(f"Verify sell response shows {expected_remaining} shares remaining"):
        assert response.status_code == 200
        updated = response.json()
        if expected_remaining == 0:
            matching = [p for p in updated if p.get("positionId") == pos_id]
            assert not matching, "Position should be gone after selling all shares"
        else:
            matching = [p for p in updated if p.get("positionId") == pos_id]
            assert len(matching) > 0, "Position missing from sell response"
            assert matching[0]["shares"] == expected_remaining


@pytest.mark.api
def test_get_nonexistent_position_returns_error(api: ParabankApi) -> None:
    response = api.get_position(9999999)
    with allure.step("Verify non-200 for unknown position id"):
        assert response.status_code != 200
