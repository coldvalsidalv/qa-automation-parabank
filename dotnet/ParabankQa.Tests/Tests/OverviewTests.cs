using Allure.NUnit.Attributes;
using Allure.Net.Commons;
using NUnit.Framework;
using ParabankQa.Tests.Pages;
using ParabankQa.Tests.Support;

namespace ParabankQa.Tests.Tests;

[TestFixture]
[AllureSuite("UI")]
[AllureFeature("Accounts")]
[AllureStory("Accounts overview")]
[AllureSeverity(SeverityLevel.critical)]
public class OverviewTests : UiTestBase
{
    [Test]
    [Category("smoke")]
    public async Task Overview_LoadsForLoggedInUser()
    {
        var overview = await new OverviewPage(Page, BaseUrl).OpenAsync();
        await AllureApi.Step("Verify the user is on Accounts Overview and authenticated", async () =>
        {
            Assert.That(overview.IsOnOverviewPage(), Is.True);
            Assert.That(await overview.IsLoggedInAsync(), Is.True);
        });
    }

    [Test]
    [Category("smoke")]
    public async Task Overview_ShowsAtLeastOneAccount()
    {
        var overview = await new OverviewPage(Page, BaseUrl).OpenAsync();
        await AllureApi.Step("Verify at least one account is listed", async () =>
            Assert.That(await overview.AccountCountAsync(), Is.GreaterThan(0)));
    }

    [Test]
    public async Task Overview_HasNavigationLinks()
    {
        var overview = await new OverviewPage(Page, BaseUrl).OpenAsync();
        foreach (var (selector, name) in new[]
        {
            (OverviewPage.TransferLink, "Transfer Funds"),
            (OverviewPage.BillPayLink, "Bill Pay"),
            (OverviewPage.RequestLoanLink, "Request Loan"),
        })
        {
            await AllureApi.Step($"Verify the '{name}' link is present", async () =>
                Assert.That(await Page.Locator(selector).CountAsync(), Is.GreaterThan(0),
                    $"{name} link not found"));
        }
    }
}
