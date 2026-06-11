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
                await api.CreateAccountAsync(_customerId, accounts[0]);
                accounts = await ReadAccountsAsync(api);
            }
            _accountPair = (accounts[0], accounts[1]);
        }
        finally
        {
            Gate.Release();
        }
    }

    private static async Task<List<long>> ReadAccountsAsync(ParabankApi api)
    {
        var response = await api.GetAccountsAsync(_customerId);
        var root = await JsonResponse.RootAsync(response);
        return root.EnumerateArray().Select(a => a.GetProperty("id").GetInt64()).ToList();
    }
}
