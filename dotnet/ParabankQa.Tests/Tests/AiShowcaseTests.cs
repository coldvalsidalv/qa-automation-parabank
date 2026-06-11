using Allure.NUnit.Attributes;
using Allure.Net.Commons;
using NUnit.Framework;
using ParabankQa.Tests.Pages;
using ParabankQa.Tests.Support;

namespace ParabankQa.Tests.Tests;

/// <summary>
/// Demo test for the AI failure hook. Excluded from regular runs by the
/// "ai_demo" category; run with AI_ANALYSIS=true and a local Ollama:
///   dotnet test --filter Category=ai_demo
/// </summary>
[TestFixture]
[AllureSuite("UI")]
[AllureFeature("AI showcase")]
[Category("ai_demo")]
public class AiShowcaseTests : UiTestBase
{
    [Test]
    public async Task FailureAnalysisDemo()
    {
        // Fails on purpose so the Allure report shows the AI diagnosis attachment.
        var overview = await new OverviewPage(Page, BaseUrl).OpenAsync();
        Assert.That(await overview.AccountCountAsync(), Is.GreaterThanOrEqualTo(100),
            "Intentional failure: a fresh customer cannot have 100 accounts");
    }
}
