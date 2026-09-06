using ParabankQa.Tests.Api;

namespace ParabankQa.Tests.Support;

/// <summary>
/// Session-wide test data, provisioned once and shared across all tests.
/// The suite registers its own customer and opens a second account, so it
/// depends on no pre-existing server state (mirrors the Python fixtures).
/// </summary>
public static class TestData
{
    private static readonly SemaphoreSlim Gate = new(1, 1);
    private static Credentials? _credentials;
    private static int _customerId;
    private static (long From, long To)? _accountPair;

    public static async Task<Credentials> CredentialsAsync(ParabankApi api)
    {
        await EnsureAsync(api);
        return _credentials!;
    }

    public static async Task<int> CustomerIdAsync(ParabankApi api)
    {
        await EnsureAsync(api);
        return _customerId;
    }

    public static async Task<(long From, long To)> AccountPairAsync(ParabankApi api)
    {
        await EnsureAsync(api);
        return _accountPair!.Value;
    }

    private static async Task EnsureAsync(ParabankApi api)
    {
        if (_accountPair is not null) return;
        await Gate.WaitAsync();
        try
        {
            if (_accountPair is not null) return;

            _credentials = await ParabankApi.RegisterCustomerAsync(Config.BaseUrl);

            var login = await api.LoginAsync(_credentials);
            var customer = await JsonResponse.RootAsync(login);
            _customerId = customer.GetProperty("id").GetInt32();

            var accounts = await ReadAccountsAsync(api);
            if (accounts.Count < 2)
            {
                await api.OpenAccountAsync(_customerId, accounts[0]);
                accounts = await ReadAccountsAsync(api);
            }
            _accountPair = (accounts[0], accounts[1]);
        }
        finally
        {
            Gate.Release();
        }
    }

    /// <summary>
    /// A fresh account opened just for the caller, isolated from the shared
    /// account pair and from other callers.
    ///
    /// The compensating deposit is not optional: ParaBank's createAccount
    /// moves $100 out of the funding account into the new one, and that debit
    /// would land on the shared account, defeating the isolation. Mirrors the
    /// Python suite's isolated_account_factory fixture.
    /// </summary>
    public static async Task<long> IsolatedAccountAsync(ParabankApi api)
    {
        var customerId = await CustomerIdAsync(api);
        var fundingAccount = (await ReadAccountsAsync(api))[0];

        var response = await api.OpenAccountAsync(customerId, fundingAccount);
        Assert.That(response.IsSuccessStatusCode, Is.True,
            $"Could not open an isolated account: {await response.Content.ReadAsStringAsync()} " +
            "(see defect D-26)");

        var account = await JsonResponse.RootAsync(response);
        await api.DepositAsync(fundingAccount, "100.00");
        return account.GetProperty("id").GetInt64();
    }

    /// <summary>
    /// A fresh customer registered just for the caller. What
    /// <see cref="IsolatedAccountAsync"/> does for account-level mutations,
    /// one level up.
    /// </summary>
    public static async Task<(int CustomerId, long AccountId)> IsolatedCustomerAsync(ParabankApi api)
    {
        var credentials = await ParabankApi.RegisterCustomerAsync(Config.BaseUrl);
        var login = await api.LoginAsync(credentials);
        Assert.That(login.IsSuccessStatusCode, Is.True,
            $"Could not log in isolated customer {credentials.Username}");

        var customerId = (await JsonResponse.RootAsync(login)).GetProperty("id").GetInt32();
        var accounts = await api.GetAccountsAsync(customerId);
        var accountId = (await JsonResponse.RootAsync(accounts))
            .EnumerateArray().First().GetProperty("id").GetInt64();
        return (customerId, accountId);
    }

    private static async Task<List<long>> ReadAccountsAsync(ParabankApi api)
    {
        var response = await api.GetAccountsAsync(_customerId);
        var root = await JsonResponse.RootAsync(response);
        return root.EnumerateArray().Select(a => a.GetProperty("id").GetInt64()).ToList();
    }
}
