"""ParaBank REST API tests — position price history (GET /positions/{id}/{start}/{end}).

The happy-path test is xfail because of defect D-11: the endpoint returns HTTP 400
"Could not find position" even for positions that exist and are returned by
GET /positions/{id}. The error-path test passes because the endpoint does correctly
reject an unknown id with a non-200 response.
"""

import allure
import pytest

from utils.parabank_api import ParabankApi

pytestmark = [
    allure.feature("Positions"),
    allure.story("Position history API"),
    allure.severity(allure.severity_level.MINOR),
]

_DATE_FROM = "01-01-2020"
_DATE_TO = "12-31-2030"


@pytest.fixture(scope="module")
def bought_position_id(api: ParabankApi, customer_id: int, account_pair: tuple[int, int]) -> int:
    from_id, _ = account_pair
    api.deposit(from_id, "150.00")
    response = api.buy_position(
        customer_id, from_id, name="HistoryCorp", symbol="HIS", shares=5, price_per_share="10.00"
    )
    assert response.status_code == 200, f"Setup: buy_position failed: {response.text}"
    return response.json()[0]["positionId"]


@pytest.mark.api
@pytest.mark.xfail(
    strict=True,
    reason="Known defect D-11: getPositionHistory returns 400 for valid positions",
)
def test_position_history_returns_list_for_valid_position(
    api: ParabankApi, bought_position_id: int
) -> None:
    response = api.get_position_history(bought_position_id, _DATE_FROM, _DATE_TO)
    with allure.step("Verify 200 and a list of history records"):
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.api
def test_position_history_invalid_position_returns_error(api: ParabankApi) -> None:
    response = api.get_position_history(9999999, _DATE_FROM, _DATE_TO)
    with allure.step("Verify non-200 for unknown position id"):
        assert response.status_code != 200
