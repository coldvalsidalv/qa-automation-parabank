using System.Net;
using System.Text.Json;
using Allure.Net.Commons;

namespace ParabankQa.Tests.Api;

public record Credentials(string Username, string Password);

/// <summary>
/// HTTP client for the ParaBank REST API, plus self-registration through the
/// web form. Mirrors utils/parabank_api.py from the Python suite.
/// </summary>
public sealed class ParabankApi : IDisposable
{
    private const string RegistrationSuccessMarker = "Your account was created successfully";

    private readonly HttpClient _http;
    private readonly string _baseUrl;

    public ParabankApi(string baseUrl)
    {
        _baseUrl = baseUrl;
        _http = new HttpClient { BaseAddress = new Uri($"{baseUrl}/parabank/services/bank/") };
        _http.DefaultRequestHeaders.Add("Accept", "application/json");
    }

    public Task<HttpResponseMessage> LoginAsync(Credentials c) =>
        Step($"API: log in", () => _http.GetAsync($"login/{c.Username}/{c.Password}"));

    public Task<HttpResponseMessage> GetAccountsAsync(int customerId) =>
        Step($"API: get accounts of customer {customerId}",
            () => _http.GetAsync($"customers/{customerId}/accounts"));

    public Task<HttpResponseMessage> GetAccountAsync(long accountId) =>
        Step($"API: get account {accountId}", () => _http.GetAsync($"accounts/{accountId}"));

    public Task<HttpResponseMessage> CreateAccountAsync(int customerId, long fromAccountId) =>
        Step($"API: open a new account for customer {customerId}",
            () => _http.PostAsync(
                $"createAccount?customerId={customerId}&newAccountType=0&fromAccountId={fromAccountId}",
                null));

    public Task<HttpResponseMessage> TransferAsync(long fromId, long toId, string amount) =>
        Step($"API: transfer {amount} from {fromId} to {toId}",
            () => _http.PostAsync(
                $"transfer?fromAccountId={fromId}&toAccountId={toId}&amount={amount}", null));

    /// <summary>
    /// Register a fresh customer through the public web form. ParaBank's demo
    /// database is wiped periodically, so the suite provisions its own user;
    /// the form rejects cookieless POSTs, hence the warm-up GET for a JSESSIONID.
    /// </summary>
    public static async Task<Credentials> RegisterCustomerAsync(string baseUrl)
    {
        var creds = new Credentials(
            Username: $"qa_{Guid.NewGuid():N}"[..13],
            Password: Guid.NewGuid().ToString("N")[..12]);

        var cookies = new CookieContainer();
        using var handler = new HttpClientHandler { CookieContainer = cookies };
        using var client = new HttpClient(handler)
        {
            BaseAddress = new Uri($"{baseUrl}/parabank/")
        };

        await client.GetAsync("register.htm"); // warm-up for JSESSIONID

        var form = new FormUrlEncodedContent(new Dictionary<string, string>
        {
            ["customer.firstName"] = "QA",
            ["customer.lastName"] = "Automation",
            ["customer.address.street"] = "1 Test Street",
            ["customer.address.city"] = "Testville",
            ["customer.address.state"] = "TS",
            ["customer.address.zipCode"] = "00000",
            ["customer.phoneNumber"] = "5551234567",
            ["customer.ssn"] = "123-45-6789",
            ["customer.username"] = creds.Username,
            ["customer.password"] = creds.Password,
            ["repeatedPassword"] = creds.Password,
        });
        var response = await client.PostAsync("register.htm", form);
        var body = await response.Content.ReadAsStringAsync();
        if (!body.Contains(RegistrationSuccessMarker))
            throw new InvalidOperationException(
                $"Self-registration failed (HTTP {(int)response.StatusCode}) — " +
                "ParaBank demo may be down or the register form changed");

        return creds;
    }

    private static async Task<HttpResponseMessage> Step(
        string name, Func<Task<HttpResponseMessage>> action)
    {
        HttpResponseMessage? result = null;
        await AllureApi.Step(name, async () => { result = await action(); });
        return result!;
    }

    public void Dispose() => _http.Dispose();
}

/// <summary>Helpers to read JSON out of API responses without a model per shape.</summary>
public static class JsonResponse
{
    public static async Task<JsonElement> RootAsync(HttpResponseMessage response)
    {
        var stream = await response.Content.ReadAsStreamAsync();
        using var doc = await JsonDocument.ParseAsync(stream);
        return doc.RootElement.Clone();
    }
}
