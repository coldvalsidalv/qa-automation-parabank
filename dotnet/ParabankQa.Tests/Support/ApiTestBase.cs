using Allure.NUnit;
using NUnit.Framework;
using ParabankQa.Tests.Api;

namespace ParabankQa.Tests.Support;

/// <summary>Base for API tests: one shared <see cref="ParabankApi"/> client.</summary>
[AllureNUnit]
public abstract class ApiTestBase
{
    protected ParabankApi Api = null!;

    [SetUp]
    public void CreateApiClient() => Api = new ParabankApi(Config.BaseUrl);

    [TearDown]
    public void DisposeApiClient() => Api.Dispose();
}
