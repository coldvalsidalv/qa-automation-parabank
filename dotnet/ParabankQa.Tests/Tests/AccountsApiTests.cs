using System.Net;
using System.Text.Json;
using Allure.NUnit.Attributes;
using NUnit.Framework;
using ParabankQa.Tests.Api;
using ParabankQa.Tests.Support;

namespace ParabankQa.Tests.Tests;

[TestFixture]
[AllureSuite("API")]
[AllureFeature("Accounts")]
public class AccountsApiTests : ApiTestBase
{
    [Test]
    [Category("smoke")]
    [AllureStory("Login API")]
    [AllureSeverity(Allure.Net.Commons.SeverityLevel.critical)]
    public async Task Login_ReturnsCustomer()
    {
        var creds = await TestData.CredentialsAsync(Api);
        var response = await Api.LoginAsync(creds);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.OK));
        var customer = await JsonResponse.RootAsync(response);
        Assert.That(customer.GetProperty("id").GetInt32(), Is.GreaterThan(0));
        Assert.That(customer.GetProperty("firstName").GetString(), Is.Not.Empty);
        Assert.That(customer.GetProperty("lastName").GetString(), Is.Not.Empty);
    }

    [Test]
    [AllureStory("Login API")]
    public async Task Login_WithInvalidCredentials_Returns400()
    {
        var response = await Api.LoginAsync(new Credentials("no_such_user_xyz", "wrong_password"));

        Assert.That((int)response.StatusCode, Is.EqualTo(400));
        var body = await response.Content.ReadAsStringAsync();
        Assert.That(body, Does.Contain("Invalid username and/or password"));
    }

    [Test]
    [Category("smoke")]
    [AllureStory("Accounts API")]
    [AllureSeverity(Allure.Net.Commons.SeverityLevel.critical)]
    public async Task Customer_HasAccounts()
    {
        var customerId = await TestData.CustomerIdAsync(Api);
        var response = await Api.GetAccountsAsync(customerId);

        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.OK));
        var accounts = await JsonResponse.RootAsync(response);
        Assert.That(accounts.GetArrayLength(), Is.GreaterThan(0));
    }

    [Test]
    [AllureStory("Accounts API")]
    public async Task Account_HasRequiredFields()
    {
        var customerId = await TestData.CustomerIdAsync(Api);
        var accounts = await JsonResponse.RootAsync(await Api.GetAccountsAsync(customerId));
        var account = accounts[0];

        Assert.That(account.GetProperty("id").GetInt64(), Is.GreaterThan(0));
        Assert.That(account.GetProperty("customerId").GetInt32(), Is.EqualTo(customerId));
        Assert.That(account.GetProperty("type").GetString(),
            Is.AnyOf("CHECKING", "SAVINGS", "LOAN"));
        Assert.That(account.GetProperty("balance").ValueKind, Is.EqualTo(JsonValueKind.Number));
    }

    [Test]
    [AllureStory("Accounts API")]
    public async Task GetAccountById_MatchesAccountFromList()
    {
        var customerId = await TestData.CustomerIdAsync(Api);
        var accounts = await JsonResponse.RootAsync(await Api.GetAccountsAsync(customerId));
        var expectedId = accounts[0].GetProperty("id").GetInt64();

        var single = await JsonResponse.RootAsync(await Api.GetAccountAsync(expectedId));
        Assert.That(single.GetProperty("id").GetInt64(), Is.EqualTo(expectedId));
        Assert.That(single.GetProperty("customerId").GetInt32(), Is.EqualTo(customerId));
    }
}
