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
    public const string RegistrationSuccessMarker = "Your account was created successfully";
    public const string DuplicateUsernameMarker = "This username already exists.";

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

    public Task<HttpResponseMessage> CreateAccountAsync(int customerId, long fromAccountId, int accountType) =>
        Step($"API: open a type-{accountType} account for customer {customerId}",
            () => _http.PostAsync(
                $"createAccount?customerId={customerId}&newAccountType={accountType}&fromAccountId={fromAccountId}",
                null));

    public Task<HttpResponseMessage> GetCustomerAsync(int customerId) =>
        Step($"API: get customer {customerId}", () => _http.GetAsync($"customers/{customerId}"));

    public Task<HttpResponseMessage> DepositAsync(long accountId, string amount) =>
        Step($"API: deposit {amount} to account {accountId}",
            () => _http.PostAsync($"deposit?accountId={accountId}&amount={amount}", null));

    public Task<HttpResponseMessage> WithdrawAsync(long accountId, string amount) =>
        Step($"API: withdraw {amount} from account {accountId}",
            () => _http.PostAsync($"withdraw?accountId={accountId}&amount={amount}", null));

    /// <summary>POST /transfer with the amount parameter absent entirely, not empty (defect D-14).</summary>
    public Task<HttpResponseMessage> TransferWithoutAmountAsync(long fromId, long toId) =>
        Step($"API: transfer from {fromId} to {toId} with no amount parameter",
            () => _http.PostAsync($"transfer?fromAccountId={fromId}&toAccountId={toId}", null));

    /// <summary>
    /// Open an account, retrying past defect D-26: concurrent createAccount calls
    /// fail with 400 while the same calls succeed serially. Tests that probe D-26
    /// itself must call <see cref="CreateAccountAsync(int, long)"/> directly.
    /// </summary>
    public async Task<HttpResponseMessage> OpenAccountAsync(int customerId, long fromAccountId)
    {
        HttpResponseMessage response = null!;
        for (var attempt = 0; attempt < OpenAccountAttempts; attempt++)
        {
            response = await CreateAccountAsync(customerId, fromAccountId);
            if (response.IsSuccessStatusCode) return response;
            await Task.Delay(150 * (attempt + 1));
        }
        return response;
    }

    private const int OpenAccountAttempts = 5;

    /// <summary>
    /// Submit the registration form once and return the credentials it used
    /// with the raw response. ParaBank's demo database is wiped periodically,
    /// so the suite provisions its own users; the form rejects cookieless
    /// POSTs, hence the warm-up GET for a JSESSIONID.
    /// </summary>
    public static async Task<(Credentials Credentials, HttpResponseMessage Response, string Body)>
        SubmitRegistrationAsync(string baseUrl, string? username = null)
    {
        var creds = new Credentials(
            Username: username ?? $"qa_{Guid.NewGuid():N}"[..13],
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
        return (creds, response, await response.Content.ReadAsStringAsync());
    }

    /// <summary>
    /// Register a fresh customer, retrying past defect D-25: under concurrency
    /// ParaBank rejects distinct, unused usernames as duplicates. The rejected
    /// name was never created, so a new one clears once the contending
    /// requests drain. A 5xx is retried too — general write contention rather
    /// than a registration-specific defect. Anything else throws immediately:
    /// that is the "form changed" case, which no retry fixes.
    /// </summary>
    public static async Task<Credentials> RegisterCustomerAsync(string baseUrl)
    {
        HttpResponseMessage response = null!;
        for (var attempt = 0; attempt < RegistrationAttempts; attempt++)
        {
            var (creds, resp, body) = await SubmitRegistrationAsync(baseUrl);
            if (body.Contains(RegistrationSuccessMarker)) return creds;
            response = resp;
            var transient = body.Contains(DuplicateUsernameMarker) || (int)resp.StatusCode >= 500;
            if (!transient) break;
            await Task.Delay(150 * (attempt + 1));
        }

        throw new InvalidOperationException(
            $"Self-registration failed (HTTP {(int)response.StatusCode}) after " +
            $"{RegistrationAttempts} attempt(s) — ParaBank may be down, the register form " +
            "changed, or the D-25 duplicate-username race did not clear");
    }

    private const int RegistrationAttempts = 5;

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
