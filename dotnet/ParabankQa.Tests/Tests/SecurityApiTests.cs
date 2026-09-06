using Allure.NUnit.Attributes;
using Allure.Net.Commons;
using ParabankQa.Tests.Api;
using ParabankQa.Tests.Support;

namespace ParabankQa.Tests.Tests;

/// <summary>
/// D-09, the register's most severe entry: the REST API enforces no
/// authentication or authorization at all. Every endpoint accepts an
/// unauthenticated request and acts on whatever customer or account id the URL
/// carries — a textbook IDOR. Account ids are sequential, so knowing or
/// guessing one is enough to read a stranger's PII and take their money.
///
/// The victim is a separately registered customer the "attacker" never
/// authenticates as, so the requests really do cross a tenant boundary.
/// </summary>
[TestFixture]
[AllureSuite("API")]
[AllureFeature("Security")]
[AllureStory("API authentication and authorization")]
[AllureSeverity(SeverityLevel.blocker)]
public class SecurityApiTests : ApiTestBase
{
    private int _victimCustomerId;
    private long _victimAccountId;

    /// <summary>
    /// An anonymous client: no login call, no cookies carried over from one.
    /// Reusing <see cref="ApiTestBase.Api"/> would prove less, since a reader
    /// could reasonably wonder whether a session was riding along.
    /// </summary>
    private ParabankApi Anonymous => new(Config.BaseUrl);

    [SetUp]
    public async Task RegisterVictim()
    {
        (_victimCustomerId, _victimAccountId) = await TestData.IsolatedCustomerAsync(Api);
        await Api.DepositAsync(_victimAccountId, "500.00");
    }

    [Test]
    public async Task ReadingForeignAccount_IsRejected()
    {
        using var anonymous = Anonymous;
        await KnownDefect.Expect("D-09",
            "an unauthenticated read of someone else's account must be refused",
            async () => !(await anonymous.GetAccountAsync(_victimAccountId)).IsSuccessStatusCode);
    }

    [Test]
    public async Task ReadingForeignCustomerPii_IsRejected()
    {
        using var anonymous = Anonymous;
        await KnownDefect.Expect("D-09",
            "an unauthenticated read of someone else's personal data must be refused",
            async () => !(await anonymous.GetCustomerAsync(_victimCustomerId)).IsSuccessStatusCode);
    }

    [Test]
    public async Task WithdrawingFromForeignAccount_IsRejected()
    {
        using var anonymous = Anonymous;
        await KnownDefect.Expect("D-09",
            "an unauthenticated withdrawal from someone else's account must be refused",
            async () => !(await anonymous.WithdrawAsync(_victimAccountId, "1.00")).IsSuccessStatusCode);
    }

    /// <summary>
    /// Live proof rather than a KnownDefect probe: asserts the theft as it
    /// behaves today, end to end, so the report carries an explicit
    /// demonstration instead of only "a defect exists". Mirrors the Python
    /// suite's defect_proof tests. It fails the day D-09 is fixed, which is
    /// the signal to delete it.
    /// </summary>
    [Test]
    [Category("defect_proof")]
    public async Task MoneyTheft_IsCurrentlyPossible()
    {
        using var attacker = Anonymous;
        var before = await BalanceAsync(attacker, _victimAccountId);

        var withdrawal = await attacker.WithdrawAsync(_victimAccountId, "100.00");
        Assert.That(withdrawal.IsSuccessStatusCode, Is.True,
            "D-09 may be FIXED: an anonymous withdrawal was refused. If so, delete this test.");

        var after = await BalanceAsync(attacker, _victimAccountId);
        Assert.That(after, Is.EqualTo(before - 100.00m).Within(0.01m),
            $"An unauthenticated caller moved money out of account {_victimAccountId}: " +
            $"{before} -> {after}");
    }

    private static async Task<decimal> BalanceAsync(ParabankApi api, long accountId)
    {
        var response = await api.GetAccountAsync(accountId);
        Assert.That(response.IsSuccessStatusCode, Is.True,
            "Setup: could not read the victim's balance anonymously");
        return (await JsonResponse.RootAsync(response)).GetProperty("balance").GetDecimal();
    }
}
