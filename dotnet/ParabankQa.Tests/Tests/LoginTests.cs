using Allure.NUnit.Attributes;
using Allure.Net.Commons;
using NUnit.Framework;
using ParabankQa.Tests.Api;
using ParabankQa.Tests.Pages;
using ParabankQa.Tests.Support;

namespace ParabankQa.Tests.Tests;

[TestFixture]
[AllureSuite("UI")]
[AllureFeature("Authentication")]
[AllureStory("UI login")]
[AllureSeverity(SeverityLevel.critical)]
public class LoginTests : UiTestBase
{
    protected override bool Authenticated => false;

    [Test]
    [Category("smoke")]
    public async Task LoginPage_Loads()
    {
        var login = await new LoginPage(Page, BaseUrl).OpenAsync();
        await AllureApi.Step("Verify the login form is displayed", () =>
        {
            Assert.That(login.IsOnLoginPage(), Is.True);
            return login.IsUsernameFieldVisibleAsync()
                .ContinueWith(t => Assert.That(t.Result, Is.True));
        });
    }

    [Test]
    [Category("smoke")]
    public async Task Login_WithValidCredentials_LandsOnOverview()
    {
        using var api = new ParabankApi(BaseUrl);
        var creds = await TestData.CredentialsAsync(api);

        var login = await new LoginPage(Page, BaseUrl).OpenAsync();
        await login.LoginAsync(creds.Username, creds.Password);

        await Page.WaitForURLAsync("**/overview.htm");
        Assert.That(login.IsLoggedIn(), Is.True);
    }

    [Test]
    [Category("smoke")]
    public async Task Login_WithInvalidCredentials_ShowsError()
    {
        var login = await new LoginPage(Page, BaseUrl).OpenAsync();
        await login.LoginAsync("no_such_user_xyz", "wrong_password_123");

        await Page.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.DOMContentLoaded);
        Assert.That(await login.HasErrorAsync(), Is.True);
        Assert.That(login.IsLoggedIn(), Is.False);
    }

    [Test]
    public async Task LoginPage_HasRegisterLink()
    {
        var login = await new LoginPage(Page, BaseUrl).OpenAsync();
        Assert.That(await Page.Locator(LoginPage.RegisterLink).CountAsync(), Is.GreaterThan(0));
    }
}
