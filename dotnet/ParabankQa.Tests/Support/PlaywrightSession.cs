using Microsoft.Playwright;
using NUnit.Framework;
using ParabankQa.Tests.Api;
using ParabankQa.Tests.Support;

// Root namespace on purpose: a [SetUpFixture] applies to its namespace and all
// descendants, so this must be an ancestor of ParabankQa.Tests.Tests.
namespace ParabankQa.Tests;

/// <summary>
/// Assembly-level fixture: starts Playwright, launches one browser, and logs in
/// once through the UI to produce a storage-state file reused by every UI test
/// (mirrors the session-scoped browser/auth_state fixtures in conftest.py).
/// </summary>
[SetUpFixture]
public class PlaywrightSession
{
    public static IPlaywright Playwright { get; private set; } = null!;
    public static IBrowser Browser { get; private set; } = null!;
    public static string StorageStatePath { get; private set; } = null!;

    [OneTimeSetUp]
    public async Task GlobalSetUp()
    {
        Playwright = await Microsoft.Playwright.Playwright.CreateAsync();
        Browser = await Playwright.Chromium.LaunchAsync(new() { Headless = Config.Headless });

        using var api = new ParabankApi(Config.BaseUrl);
        var creds = await TestData.CredentialsAsync(api);

        var context = await Browser.NewContextAsync(
            new() { ViewportSize = new() { Width = 1440, Height = 900 } });
        var page = await context.NewPageAsync();
        await page.GotoAsync($"{Config.BaseUrl}/parabank/index.htm",
            new() { WaitUntil = WaitUntilState.DOMContentLoaded });
        await page.Locator("input[name=\"username\"]").FillAsync(creds.Username);
        await page.Locator("input[name=\"password\"]").FillAsync(creds.Password);
        await page.Locator("input[value=\"Log In\"]").ClickAsync();
        await page.WaitForURLAsync("**/overview.htm", new() { Timeout = 10_000 });

        StorageStatePath = Path.Combine(Path.GetTempPath(), $"pb-state-{Guid.NewGuid():N}.json");
        await context.StorageStateAsync(new() { Path = StorageStatePath });
        await context.CloseAsync();
    }

    [OneTimeTearDown]
    public async Task GlobalTearDown()
    {
        await Browser.CloseAsync();
        Playwright.Dispose();
        if (File.Exists(StorageStatePath)) File.Delete(StorageStatePath);
    }
}
