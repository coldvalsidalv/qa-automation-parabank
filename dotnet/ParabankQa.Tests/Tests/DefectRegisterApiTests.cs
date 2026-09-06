using Allure.NUnit.Attributes;
using Allure.Net.Commons;
using ParabankQa.Tests.Api;
using ParabankQa.Tests.Support;

namespace ParabankQa.Tests.Tests;

/// <summary>
/// The Python suite's defect register, ported to the slice: the assertions are
/// written the way ParaBank *should* behave and wrapped in
/// <see cref="KnownDefect.Expect"/>, so each one alerts the moment the defect
/// is fixed. Defect ids match docs/test_plan.md.
///
/// This is the part of the Python suite worth porting. Copying more happy
/// paths would prove nothing that the existing slice does not already prove;
/// carrying the register across proves the *discipline* survives a stack that
/// has no xfail of its own.
/// </summary>
[TestFixture]
[AllureSuite("API")]
[AllureFeature("Defect register")]
[AllureSeverity(SeverityLevel.critical)]
public class DefectRegisterApiTests : ApiTestBase
{
    // The defect id is an argument, not something derived from the amount. It
    // used to be `amount == "0" ? "D-01" : "D-02"`, which meant a third case
    // would silently be reported as D-02 — and in a defect register the id is
    // the payload: get it wrong and the report tells whoever fixes the bug to
    // delete the wrong entry from the test plan.
    [TestCase("D-01", "0", TestName = "Transfer_ZeroAmount_IsRejected")]
    [TestCase("D-02", "-10", TestName = "Transfer_NegativeAmount_IsRejected")]
    public async Task Transfer_InvalidAmount_IsRejected(string defect, string amount)
    {
        var from = await TestData.IsolatedAccountAsync(Api);
        var to = await TestData.IsolatedAccountAsync(Api);

        await KnownDefect.Expect(defect, $"a transfer of {amount} must be refused",
            async () => (int)(await Api.TransferAsync(from, to, amount)).StatusCode >= 400);
    }

    [Test]
    public async Task Transfer_ToSameAccount_IsRejected()
    {
        var account = await TestData.IsolatedAccountAsync(Api);

        await KnownDefect.Expect("D-03", "a transfer to the same account must be refused",
            async () => (int)(await Api.TransferAsync(account, account, "10")).StatusCode >= 400);
    }

    [Test]
    public async Task Transfer_WithoutAmountParameter_IsRejected()
    {
        var (from, to) = await TestData.AccountPairAsync(Api);

        await KnownDefect.Expect("D-14",
            "a missing amount parameter must be a validation error, not a server crash",
            async () => (int)(await Api.TransferWithoutAmountAsync(from, to)).StatusCode < 500);
    }

    [Test]
    public async Task Deposit_NegativeAmount_IsRejected()
    {
        var account = await TestData.IsolatedAccountAsync(Api);

        await KnownDefect.Expect("D-05", "a negative deposit must be refused",
            async () => (int)(await Api.DepositAsync(account, "-50.00")).StatusCode >= 400);
    }

    [Test]
    public async Task Withdraw_ExceedingBalance_IsRejected()
    {
        var account = await TestData.IsolatedAccountAsync(Api);
        await Api.DepositAsync(account, "50.00");

        await KnownDefect.Expect("D-06", "a withdrawal beyond the balance must be refused",
            async () => (int)(await Api.WithdrawAsync(account, "9999999.00")).StatusCode >= 400);
    }

    [Test]
    public async Task Withdraw_NegativeAmount_IsRejected()
    {
        var account = await TestData.IsolatedAccountAsync(Api);

        await KnownDefect.Expect("D-07", "a negative withdrawal must be refused",
            async () => (int)(await Api.WithdrawAsync(account, "-50.00")).StatusCode >= 400);
    }
}
