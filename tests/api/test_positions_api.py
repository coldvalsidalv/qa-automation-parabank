"""ParaBank REST API tests — stock positions (buy / get / sell)."""
import allure
import pytest

from utils.parabank_api import ParabankApi

pytestmark = [
    allure.feature("Positions"),
    allure.story("Stock positions API"),
    allure.severity(allure.severity_level.MINOR),
]


@pytest.fixture(scope="module")
def position(api: ParabankApi, customer_id: int, account_pair: tuple[int, int]) -> tuple[int, int]:
    """Buy 10 shares of TST; return (position_id, share_count) from the buy response.

    We capture shares from the buy response — not from a subsequent GET — because
    ParaBank may reassign a new positionId after a partial sell, which makes the
    original ID stale.
    """
    from_id, _ = account_pair
    api.deposit(from_id, "200.00")
    response = api.buy_position(
        customer_id, from_id, name="TestCorp", symbol="TST", shares=10, price_per_share="10.00"
    )
    assert response.status_code == 200, f"Setup: buy_position failed: {response.text}"
    pos = response.json()[0]
    return pos["positionId"], pos["shares"]


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
        pos = response.json()[0]
        assert isinstance(pos["positionId"], int) and pos["positionId"] > 0
        assert pos["symbol"] == "ACM"
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
    api: ParabankApi, customer_id: int, account_pair: tuple[int, int], position: tuple[int, int]
) -> None:
    pos_id, total_shares = position
    from_id, _ = account_pair
    sell_qty = min(5, total_shares)
    expected_remaining = total_shares - sell_qty

    response = api.sell_position(
        customer_id, from_id, position_id=pos_id, shares=sell_qty, price_per_share="12.00"
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
