using NUnit.Framework;

namespace ParabankQa.Tests.Support;

/// <summary>
/// NUnit equivalent of the Python suite's <c>xfail(strict=True)</c>.
///
/// NUnit has no xfail. <c>[Ignore]</c> would hide the defect, and rewriting the
/// assertion to expect the broken behavior would make the suite endorse the bug
/// and stay green forever — the two failure modes strict xfail exists to avoid.
///
/// So <see cref="Expect"/> takes the check as a predicate that answers "does
/// the application behave correctly now?". False means the defect is still
/// there and the test passes, recording the observation. True means it is gone
/// and the test fails, telling whoever fixed it to delete the case. Strictness
/// is the point: silence on a fixed defect is how a defect register rots.
///
/// Two NUnit 4 details shape this. The check must not use NUnit assertions: a
/// failed <c>Assert.That</c> is recorded in the test result even when its
/// exception is caught, so a swallowed assertion would still fail the test.
/// And the verdict here throws <see cref="AssertionException"/> rather than
/// calling <c>Assert.Fail</c>, for the same reason in reverse — <c>Assert.Fail</c>
/// records, which would make this helper untestable by
/// <c>Assert.ThrowsAsync</c>. Throwing fails the test just the same.
/// </summary>
public static class KnownDefect
{
    /// <param name="id">Defect id from docs/test_plan.md, e.g. "D-01".</param>
    /// <param name="whenFixed">What the application should do instead.</param>
    /// <param name="behavesCorrectly">
    /// True once the application does the right thing — i.e. the defect is fixed.
    /// </param>
    public static async Task Expect(string id, string whenFixed, Func<Task<bool>> behavesCorrectly)
    {
        bool fixedNow;
        try
        {
            fixedNow = await behavesCorrectly();
        }
        catch (Exception ex)
        {
            throw new AssertionException(
                $"Known defect {id}: the check itself failed to run ({ex.GetType().Name}: " +
                $"{ex.Message}). That is a broken test, not a verdict on the defect.", ex);
        }

        if (fixedNow)
            throw new AssertionException(
                $"Known defect {id} appears to be FIXED — {whenFixed}. The application now " +
                "behaves correctly, so this case no longer documents a defect: turn it into a " +
                "normal test and remove it from docs/test_plan.md.");

        TestContext.Out.WriteLine($"Known defect {id} still present — expected that {whenFixed}.");
    }
}
