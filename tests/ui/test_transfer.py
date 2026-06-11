import allure
import pytest
from playwright.sync_api import Page

from pages.overview_page import OverviewPage
from pages.transfer_page import TransferPage


@pytest.fixture
def transfer_page(page: Page, base_url: str, account_pair: tuple[int, int]) -> TransferPage:
    """Transfer page with at least two accounts guaranteed by `account_pair`."""
    return TransferPage(page, base_url).open()


@pytest.mark.smoke
@pytest.mark.ui
def test_transfer_page_lists_accounts(transfer_page: TransferPage) -> None:
    with allure.step("Verify at least two accounts are available in the From dropdown"):
        assert transfer_page.is_on_transfer_page()
        assert transfer_page.available_from_accounts() >= 2, "Expected at least two accounts"


@pytest.mark.smoke
@pytest.mark.ui
def test_transfer_valid_amount_completes(transfer_page: TransferPage) -> None:
    transfer_page.transfer(amount="10")
    with allure.step("Verify the 'Transfer Complete!' confirmation is shown"):
        assert transfer_page.is_transfer_complete(), "Transfer confirmation not shown"


@pytest.mark.ui
def test_transfer_empty_amount_does_not_complete(transfer_page: TransferPage) -> None:
    transfer_page.transfer(amount="")
    with allure.step("Verify the transfer did not complete and an error is surfaced"):
        assert not transfer_page.is_transfer_complete(), "Empty-amount transfer must not complete"
        assert transfer_page.has_error(), "Expected an error panel"


@pytest.mark.ui
@pytest.mark.xfail(
    reason=(
        "Known ParaBank defect: empty amount triggers an internal server error; "
        "the validation messages exist in the DOM but are never displayed"
    ),
    strict=True,
)
def test_transfer_empty_amount_shows_validation_message(transfer_page: TransferPage) -> None:
    transfer_page.transfer(amount="")
    with allure.step("Verify the 'amount cannot be empty' validation message is shown"):
        assert transfer_page.has_amount_validation_error(), (
            "Expected 'The amount cannot be empty' validation message"
        )


@pytest.mark.ui
@pytest.mark.xfail(
    reason="Known ParaBank defect: UI accepts a zero-amount transfer",
    strict=True,
)
def test_transfer_zero_amount_is_rejected(transfer_page: TransferPage) -> None:
    transfer_page.transfer(amount="0")
    with allure.step("Verify the zero-amount transfer is rejected"):
        assert not transfer_page.is_transfer_complete(), (
            "Zero-amount transfer should be rejected"
        )


@pytest.mark.ui
def test_transfer_reachable_from_overview(page: Page, base_url: str) -> None:
    OverviewPage(page, base_url).open().go_to_transfer()
    with allure.step("Verify the Transfer Funds page opened"):
        page.wait_for_url("**/transfer.htm*")
        assert "transfer.htm" in page.url
