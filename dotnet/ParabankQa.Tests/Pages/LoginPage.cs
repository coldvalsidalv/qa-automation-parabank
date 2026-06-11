using Allure.Net.Commons;
using Microsoft.Playwright;

namespace ParabankQa.Tests.Pages;

public sealed class LoginPage(IPage page, string baseUrl) : BasePage(page, baseUrl)
{
    public const string Url = "/parabank/index.htm";

    private const string UsernameInput = "input[name=\"username\"]";
    private const string PasswordInput = "input[name=\"password\"]";
    private const string LoginButton = "input[value=\"Log In\"]";
    private const string ErrorMessage = "p.error";
    public const string RegisterLink = "a[href*=\"register.htm\"]";

    public async Task<LoginPage> OpenAsync()
    {
        await NavigateAsync(Url);
        return this;
    }

    public Task LoginAsync(string username, string password) =>
        AllureApi.Step($"Log in as '{username}'", async () =>
        {
            await FillAsync(UsernameInput, username, "username");
            await FillAsync(PasswordInput, password, "password");
            await ClickAsync(LoginButton, "Log In button");
        });

    public bool IsOnLoginPage() =>
        Page.Url.Contains("index.htm") || Page.Url.TrimEnd('/').EndsWith("/parabank");

    public bool IsLoggedIn() => Page.Url.Contains("overview.htm");

    public Task<bool> HasErrorAsync() =>
        Page.Locator(ErrorMessage).CountAsync().ContinueWith(t => t.Result > 0);

    public Task<bool> IsUsernameFieldVisibleAsync() => Page.Locator(UsernameInput).IsVisibleAsync();
}
