using Allure.NUnit;
using Allure.NUnit.Attributes;
using ParabankQa.Tests.Support;

namespace ParabankQa.Tests.Tests;

/// <summary>
/// Guard for <see cref="KnownDefect"/> itself. It is the piece that makes the
/// defect register strict, and it would fail silently: get the verdict
/// backwards and every documented defect turns into a test that passes no
/// matter what the application does — green, meaningless, and impossible to
/// spot by reading a report.
///
/// The Python suite unit-tests its Allure category regex for the same reason.
/// No app, no browser, no network.
/// </summary>
[TestFixture]
[AllureNUnit]
[AllureSuite("Unit")]
[AllureFeature("Defect register")]
public class KnownDefectTests
{
    [Test]
    public async Task DefectStillPresent_Passes()
    {
        await KnownDefect.Expect("D-TEST", "the application should behave",
            behavesCorrectly: () => Task.FromResult(false));
    }

    [Test]
    public void DefectFixed_FailsAndSaysSo()
    {
        var ex = Assert.ThrowsAsync<AssertionException>(async () =>
            await KnownDefect.Expect("D-TEST", "the application should behave",
                behavesCorrectly: () => Task.FromResult(true)));

        Assert.Multiple(() =>
        {
            Assert.That(ex!.Message, Does.Contain("D-TEST"), "the report must name the defect");
            Assert.That(ex.Message, Does.Contain("FIXED"));
            Assert.That(ex.Message, Does.Contain("test_plan.md"),
                "the message must say where to remove the defect from");
        });
    }

    [Test]
    public void CheckThatThrows_IsReportedAsABrokenTest_NotAsAVerdict()
    {
        var ex = Assert.ThrowsAsync<AssertionException>(async () =>
            await KnownDefect.Expect("D-TEST", "the application should behave",
                behavesCorrectly: () => throw new HttpRequestException("connection refused")));

        Assert.Multiple(() =>
        {
            Assert.That(ex!.Message, Does.Contain("broken test"),
                "an unreachable app must not read as either verdict on the defect");
            Assert.That(ex.Message, Does.Contain("connection refused"));
            Assert.That(ex.Message, Does.Not.Contain("FIXED"));
        });
    }
}
