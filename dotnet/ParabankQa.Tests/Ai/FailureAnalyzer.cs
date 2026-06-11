using System.Text;
using System.Text.Json;
using ParabankQa.Tests.Support;

namespace ParabankQa.Tests.Ai;

/// <summary>
/// Turns a failed test (name + error) into a human-readable diagnosis via a
/// local Ollama model (OpenAI-compatible API). Mirrors ai/failure_analyzer.py.
/// </summary>
public static class FailureAnalyzer
{
    private const int MaxLogChars = 4000;

    private const string SystemPrompt =
        "You are a senior QA engineer. Analyze a failed automated test and reply with:\n" +
        "## What failed\n## Root cause hypothesis (app bug / flaky / broken locator / test data)\n" +
        "## Evidence\n## Recommended fix\n## Priority (LOW/MEDIUM/HIGH)\nBe concise and technical.";

    public static async Task<string> AnalyzeAsync(string testName, string errorLog)
    {
        var trimmed = errorLog.Length > MaxLogChars ? errorLog[^MaxLogChars..] : errorLog;
        var userMessage = $"**Test:** {testName}\n\n**Error log:**\n```\n{trimmed}\n```";

        var payload = new
        {
            model = Config.OllamaModel,
            temperature = 0,
            max_tokens = 1024,
            messages = new[]
            {
                new { role = "system", content = SystemPrompt },
                new { role = "user", content = userMessage },
            },
        };

        using var http = new HttpClient { Timeout = TimeSpan.FromMinutes(5) };
        var body = new StringContent(
            JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");
        var response = await http.PostAsync(
            $"{Config.OllamaBaseUrl}/chat/completions", body);
        response.EnsureSuccessStatusCode();

        using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        return doc.RootElement
            .GetProperty("choices")[0]
            .GetProperty("message")
            .GetProperty("content")
            .GetString() ?? "";
    }
}
