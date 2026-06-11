using Allure.NUnit;
using Allure.Net.Commons;
using Microsoft.Playwright;
using NUnit.Framework;
using NUnit.Framework.Interfaces;
using ParabankQa.Tests.Ai;

namespace ParabankQa.Tests.Support;

/// <summary>
/// Base for UI tests with retain-on-failure artifacts: every test records a
/// Playwright trace and a video; on failure they are attached to the Allure
/// report (with a screenshot and, when AI_ANALYSIS=true, an AI diagnosis),
/// and discarded on success. Mirrors _managed_page + the makereport hook.
/// </summary>
[AllureNUnit]
public abstract class UiTestBase
{
    protected IBrowserContext Context = null!;
    protected IPage Page = null!;
    protected string BaseUrl => Config.BaseUrl;

    private string _videoDir = null!;

    [SetUp]
    public async Task CreatePage()
    {
        _videoDir = Path.Combine(Path.GetTempPath(), $"pb-video-{Guid.NewGuid():N}");
        Context = await PlaywrightSession.Browser.NewContextAsync(new()
        {
            ViewportSize = new() { Width = 1440, Height = 900 },
            StorageStatePath = Authenticated ? PlaywrightSession.StorageStatePath : null,
            RecordVideoDir = _videoDir,
        });
        await Context.Tracing.StartAsync(new() { Screenshots = true, Snapshots = true, Sources = true });
        Page = await Context.NewPageAsync();
    }

    /// <summary>Override to false for login/registration tests.</summary>
    protected virtual bool Authenticated => true;

    [TearDown]
    public async Task TeardownPage()
    {
        var failed = TestContext.CurrentContext.Result.Outcome.Status == TestStatus.Failed;

        var tracePath = Path.Combine(_videoDir, "trace.zip");
        await Context.Tracing.StopAsync(new() { Path = failed ? tracePath : null });

        if (failed)
            await AttachFailureEvidenceAsync(tracePath);

        var video = Page.Video;
        await Context.CloseAsync(); // finalizes the video file

        if (failed && video is not null)
            AllureApi.AddAttachment("video", "video/webm", await video.PathAsync());

        TryDeleteDir(_videoDir, keepIfFailed: failed, tracePath);
    }

    private async Task AttachFailureEvidenceAsync(string tracePath)
    {
        try
        {
            AllureApi.AddAttachment("failure-screenshot", "image/png",
                await Page.ScreenshotAsync(new() { FullPage = true }));
        }
        catch { /* page/context already gone — screenshot is best-effort */ }

        if (File.Exists(tracePath))
            AllureApi.AddAttachment("playwright-trace", "application/zip", tracePath);

        if (!Config.AiAnalysis) return;
        try
        {
            var result = TestContext.CurrentContext.Result;
            var error = $"{result.Message}\n{result.StackTrace}";
            var diagnosis = await FailureAnalyzer.AnalyzeAsync(
                TestContext.CurrentContext.Test.FullName, error);
            AllureApi.AddAttachment("AI failure analysis", "text/plain",
                System.Text.Encoding.UTF8.GetBytes(diagnosis), ".txt");
        }
        catch (Exception ex)
        {
            AllureApi.AddAttachment("AI failure analysis", "text/plain",
                System.Text.Encoding.UTF8.GetBytes($"AI analysis unavailable: {ex.Message}"), ".txt");
        }
    }

    private static void TryDeleteDir(string dir, bool keepIfFailed, string keepFile)
    {
        try
        {
            if (!Directory.Exists(dir)) return;
            foreach (var f in Directory.GetFiles(dir))
                if (!(keepIfFailed && f == keepFile)) File.Delete(f);
            if (!keepIfFailed) Directory.Delete(dir, recursive: true);
        }
        catch { /* best-effort cleanup */ }
    }
}
