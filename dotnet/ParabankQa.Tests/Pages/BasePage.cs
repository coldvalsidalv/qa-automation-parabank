using Allure.Net.Commons;
using Microsoft.Playwright;

namespace ParabankQa.Tests.Pages;

public abstract class BasePage(IPage page, string baseUrl)
{
    protected readonly IPage Page = page;
    protected readonly string BaseUrl = baseUrl;

    protected Task NavigateAsync(string path) =>
        AllureApi.Step($"Open {path}", () => Page.GotoAsync(BaseUrl + path));

    protected Task FillAsync(string selector, string value, string description) =>
        AllureApi.Step($"Fill {description}", () => Page.Locator(selector).FillAsync(value));

    protected Task ClickAsync(string selector, string description) =>
        AllureApi.Step($"Click {description}", () => Page.Locator(selector).ClickAsync());
}
