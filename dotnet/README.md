# ParaBank QA — C# / .NET slice

[Live Allure report](https://coldvalsidalv.github.io/qa-automation-parabank/dotnet/)

A vertical slice of the [Python suite](../README.md) reimplemented on the .NET
stack, to show the approach is not tied to one language: the same test plan,
the same patterns (page objects, self-provisioned data, business-level report
steps, retain-on-failure artifacts, AI failure triage) in C#.

**Stack:** NUnit · Playwright for .NET · Allure.NUnit · HttpClient

## Scope

A slice, not full parity with the Python suite — the point is portability, not
two copies of everything. What the slice covers is chosen accordingly: happy
paths alone would only prove that page objects port between languages, which
was never in doubt. The part worth carrying across is the **defect register**,
because NUnit has no `xfail` and the discipline has to be rebuilt rather than
translated.

| Area | File |
|------|------|
| Accounts / login API | [Tests/AccountsApiTests.cs](ParabankQa.Tests/Tests/AccountsApiTests.cs) |
| UI login | [Tests/LoginTests.cs](ParabankQa.Tests/Tests/LoginTests.cs) |
| Accounts overview | [Tests/OverviewTests.cs](ParabankQa.Tests/Tests/OverviewTests.cs) |
| Transfer funds | [Tests/TransferTests.cs](ParabankQa.Tests/Tests/TransferTests.cs) |
| **Defect register** (D-01..D-03, D-05..D-07, D-14) | [Tests/DefectRegisterApiTests.cs](ParabankQa.Tests/Tests/DefectRegisterApiTests.cs) |
| **Security — no API auth (D-09)** + live theft proof | [Tests/SecurityApiTests.cs](ParabankQa.Tests/Tests/SecurityApiTests.cs) |
| Guard for the defect-register helper | [Tests/KnownDefectTests.cs](ParabankQa.Tests/Tests/KnownDefectTests.cs) |
| AI failure-hook demo | [Tests/AiShowcaseTests.cs](ParabankQa.Tests/Tests/AiShowcaseTests.cs) |

## The defect register without `xfail`

NUnit has no `xfail`. `[Ignore]` would hide a defect, and rewriting an
assertion to expect the broken behavior would make the suite endorse the bug
and stay green forever — the two failure modes the Python suite's
`xfail(strict=True)` exists to avoid.

[`KnownDefect.Expect`](ParabankQa.Tests/Support/KnownDefect.cs) rebuilds it.
The check is a predicate answering "does the application behave correctly
now?": false means the defect is still there and the test passes; true means it
is gone and the test fails, naming the defect and saying to remove it from the
test plan. Strictness is the point — silence on a fixed defect is how a defect
register rots.

Two NUnit 4 details shape the implementation, both found by hitting them:

* The check may not use NUnit assertions. A failed `Assert.That` is recorded in
  the test result even when its exception is caught, so a swallowed assertion
  still fails the test.
* The verdict throws `AssertionException` rather than calling `Assert.Fail`,
  for the same reason in reverse: `Assert.Fail` records, which would make the
  helper untestable by `Assert.ThrowsAsync`.

Because a helper like this fails *silently* when it is wrong — get the verdict
backwards and every documented defect becomes a test that passes regardless of
what the application does — it has a guard of its own,
[`KnownDefectTests`](ParabankQa.Tests/Tests/KnownDefectTests.cs), covering all
three outcomes including an unreachable app. That mirrors the Python suite,
which unit-tests its Allure category regex for exactly the same reason.

## What carries over from the Python suite

- **Self-provisioned data** — [`ParabankApi.RegisterCustomerAsync`](ParabankQa.Tests/Api/ParabankApi.cs)
  registers a fresh customer; no secrets, no pre-existing state. It retries
  past defect D-25, as `ParabankApi.OpenAccountAsync` does past D-26.
- **Test isolation** — `TestData.IsolatedAccountAsync` opens an account for a
  single test, with the same compensating deposit as the Python fixture:
  ParaBank's `createAccount` moves $100 out of the funding account, and that
  debit would otherwise land on the shared account and defeat the isolation.
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
