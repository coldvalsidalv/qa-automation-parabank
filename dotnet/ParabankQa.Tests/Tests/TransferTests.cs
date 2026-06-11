using Allure.NUnit.Attributes;
using Allure.Net.Commons;
using NUnit.Framework;
using ParabankQa.Tests.Api;
using ParabankQa.Tests.Pages;
using ParabankQa.Tests.Support;

namespace ParabankQa.Tests.Tests;

[TestFixture]
[AllureSuite("UI")]
[AllureFeature("Transfers")]
[AllureStory("Transfer funds (UI)")]
[AllureSeverity(SeverityLevel.critical)]
public class TransferTests : UiTestBase
{
    [SetUp]
    public async Task EnsureTwoAccounts()
    {
        // Guarantee the customer has the second account the transfer form needs.
        using var api = new ParabankApi(BaseUrl);
        await TestData.AccountPairAsync(api);
    }

    [Test]
    [Category("smoke")]
    public async Task TransferPage_ListsAccounts()
    {
        var transfer = await new TransferPage(Page, BaseUrl).OpenAsync();
        await AllureApi.Step("Verify at least two accounts are available", async () =>
        {
            Assert.That(transfer.IsOnTransferPage(), Is.True);
            Assert.That(await transfer.AvailableFromAccountsAsync(), Is.GreaterThanOrEqualTo(2));
        });
    }

    [Test]
    [Category("smoke")]
    public async Task Transfer_ValidAmount_Completes()
    {
        var transfer = await new TransferPage(Page, BaseUrl).OpenAsync();
        await transfer.TransferAsync("10");
        await AllureApi.Step("Verify the 'Transfer Complete!' confirmation is shown", async () =>
            Assert.That(await transfer.IsTransferCompleteAsync(), Is.True));
    }

    [Test]
    public async Task Transfer_ReachableFromOverview()
    {
        var overview = await new OverviewPage(Page, BaseUrl).OpenAsync();
        await overview.GoToTransferAsync();
        await Page.WaitForURLAsync("**/transfer.htm*");
        Assert.That(Page.Url, Does.Contain("transfer.htm"));
    }
}
