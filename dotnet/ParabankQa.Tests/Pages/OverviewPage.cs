using Allure.Net.Commons;
using Microsoft.Playwright;

namespace ParabankQa.Tests.Pages;

public sealed class OverviewPage(IPage page, string baseUrl) : BasePage(page, baseUrl)
{
    public const string Url = "/parabank/overview.htm";

    private const string AccountLinks = "#accountTable tbody tr td:first-child a";
    private const string LogoutLink = "a[href*=\"logout\"]";
    public const string TransferLink = "a[href*=\"transfer.htm\"]";
    public const string BillPayLink = "a[href*=\"billpay.htm\"]";
    public const string RequestLoanLink = "a[href*=\"requestloan.htm\"]";

    public async Task<OverviewPage> OpenAsync()
    {
        await NavigateAsync(Url);
        // The account table is populated by an XHR after page load.
        await Page.Locator(AccountLinks).First.WaitForAsync(
            new() { State = WaitForSelectorState.Visible });
        return this;
    }

    public bool IsOnOverviewPage() => Page.Url.Contains("overview.htm");

    public Task<bool> IsLoggedInAsync() =>
        Page.Locator(LogoutLink).CountAsync().ContinueWith(t => t.Result > 0);

    // Count links, not rows: the tbody also contains the "Total" row.
    public Task<int> AccountCountAsync() => Page.Locator(AccountLinks).CountAsync();

    public Task GoToTransferAsync() =>
        AllureApi.Step("Go to Transfer Funds via the navigation menu",
            () => Page.Locator(TransferLink).ClickAsync());
}
