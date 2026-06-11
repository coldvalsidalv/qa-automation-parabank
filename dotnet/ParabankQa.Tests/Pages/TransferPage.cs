using Allure.Net.Commons;
using Microsoft.Playwright;

namespace ParabankQa.Tests.Pages;

/// <summary>
/// Transfer Funds — a small JS app: the form posts via XHR and toggles one of
/// #showForm / #showResult ("Transfer Complete!") / #showError.
/// </summary>
public sealed class TransferPage(IPage page, string baseUrl) : BasePage(page, baseUrl)
{
    public const string Url = "/parabank/transfer.htm";

    private const string FromAccountSelect = "#fromAccountId";
    private const string ToAccountSelect = "#toAccountId";
    private const string AmountInput = "#amount";
    private const string TransferButton = "input[value=\"Transfer\"]";
    private const string FormPanel = "#showForm";
    private const string ResultPanel = "#showResult";
    private const string ErrorPanel = "#showError";

    public async Task<TransferPage> OpenAsync()
    {
        await NavigateAsync(Url);
        // Account dropdowns are populated by an XHR after page load.
        await Page.Locator($"{FromAccountSelect} option").First.WaitForAsync(
            new() { State = WaitForSelectorState.Attached });
        return this;
    }

    public bool IsOnTransferPage() => Page.Url.Contains("transfer.htm");

    public Task<int> AvailableFromAccountsAsync() =>
        Page.Locator($"{FromAccountSelect} option").CountAsync();

    public Task TransferAsync(string amount) =>
        AllureApi.Step($"Transfer ${amount} between own accounts", async () =>
        {
            await Page.Locator(FromAccountSelect).SelectOptionAsync(new SelectOptionValue { Index = 0 });
            await Page.Locator(ToAccountSelect).SelectOptionAsync(new SelectOptionValue { Index = 1 });
            await FillAsync(AmountInput, amount, "amount");
            await ClickAsync(TransferButton, "Transfer button");
            // Both outcomes (result or error panel) hide the form.
            await Page.Locator(FormPanel).WaitForAsync(new() { State = WaitForSelectorState.Hidden });
        });

    public Task<bool> IsTransferCompleteAsync() => Page.Locator(ResultPanel).IsVisibleAsync();

    public Task<bool> HasErrorAsync() => Page.Locator(ErrorPanel).IsVisibleAsync();
}
