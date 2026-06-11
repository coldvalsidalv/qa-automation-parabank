# ParaBank QA — C# / .NET slice

A vertical slice of the [Python suite](../README.md) reimplemented on the .NET
stack, to show the approach is not tied to one language: the same test plan,
the same patterns (page objects, self-provisioned data, business-level report
steps, retain-on-failure artifacts, AI failure triage) in C#.

**Stack:** NUnit · Playwright for .NET · Allure.NUnit · HttpClient

## Scope

Auth + accounts + transfer, UI and API — the critical paths, not full parity
with the Python suite (which covers nine resource areas and documents nine
defects). The point is to demonstrate portability, not to maintain two copies
of everything.

| Area | File |
|------|------|
| Accounts / login API | [Tests/AccountsApiTests.cs](ParabankQa.Tests/Tests/AccountsApiTests.cs) |
| UI login | [Tests/LoginTests.cs](ParabankQa.Tests/Tests/LoginTests.cs) |
| Accounts overview | [Tests/OverviewTests.cs](ParabankQa.Tests/Tests/OverviewTests.cs) |
| Transfer funds | [Tests/TransferTests.cs](ParabankQa.Tests/Tests/TransferTests.cs) |
| AI failure-hook demo | [Tests/AiShowcaseTests.cs](ParabankQa.Tests/Tests/AiShowcaseTests.cs) |

## What carries over from the Python suite

- **Self-provisioned data** — [`ParabankApi.RegisterCustomerAsync`](ParabankQa.Tests/Api/ParabankApi.cs)
  registers a fresh customer; no secrets, no pre-existing state.
- **Business-level report steps** — `AllureApi.Step` on page-object and API
  methods, the same step titles as the Python report.
- **Retain-on-failure** — every UI test records a Playwright trace and video,
  attached only on failure ([`UiTestBase`](ParabankQa.Tests/Support/UiTestBase.cs)).
- **AI failure triage** — on failure with `AI_ANALYSIS=true`, the same local
  Ollama model diagnoses the failure into the Allure report
  ([`FailureAnalyzer`](ParabankQa.Tests/Ai/FailureAnalyzer.cs)).

## Run

```bash
cd dotnet/ParabankQa.Tests
dotnet build
pwsh bin/Debug/net10.0/playwright.ps1 install chromium   # once

# app under test (from the repo root): docker compose up -d parabank
dotnet test --filter "Category!=ai_demo"                 # full slice
dotnet test --filter "Category=smoke"                    # smoke only

# AI showcase (needs a local Ollama):
AI_ANALYSIS=true dotnet test --filter "Category=ai_demo"
```

`Category=ai_demo` contains the intentional-failure demo and is excluded from
normal runs.
