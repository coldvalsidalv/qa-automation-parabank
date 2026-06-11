namespace ParabankQa.Tests.Support;

/// <summary>Environment-driven configuration, mirroring the Python suite's conftest.</summary>
public static class Config
{
    public static string BaseUrl =>
        Environment.GetEnvironmentVariable("BASE_URL") ?? "http://localhost:8080";

    public static bool Headless =>
        (Environment.GetEnvironmentVariable("HEADLESS") ?? "true").ToLower() != "false";

    public static bool AiAnalysis =>
        (Environment.GetEnvironmentVariable("AI_ANALYSIS") ?? "false").ToLower() == "true";

    public static string OllamaBaseUrl =>
        Environment.GetEnvironmentVariable("OLLAMA_BASE_URL") ?? "http://localhost:11434/v1";

    public static string OllamaModel =>
        Environment.GetEnvironmentVariable("OLLAMA_MODEL") ?? "llama3.1:8b";
}
