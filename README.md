# ParaBank QA — AI-Assisted Test Automation

[![QA Automation CI (Python)](https://github.com/coldvalsidalv/qa-automation-parabank/actions/workflows/ci.yml/badge.svg)](https://github.com/coldvalsidalv/qa-automation-parabank/actions/workflows/ci.yml)
[![QA Automation CI (.NET)](https://github.com/coldvalsidalv/qa-automation-parabank/actions/workflows/ci-dotnet.yml/badge.svg)](https://github.com/coldvalsidalv/qa-automation-parabank/actions/workflows/ci-dotnet.yml)
[![CodeQL](https://github.com/coldvalsidalv/qa-automation-parabank/actions/workflows/codeql.yml/badge.svg)](https://github.com/coldvalsidalv/qa-automation-parabank/actions/workflows/codeql.yml)

[Live Allure report](https://coldvalsidalv.github.io/qa-automation-parabank/) · [AI demo report](https://coldvalsidalv.github.io/qa-automation-parabank/ai-demo/) · [.NET report](https://coldvalsidalv.github.io/qa-automation-parabank/dotnet/)

Test automation for [ParaBank](https://parabank.parasoft.com) — a demo banking
application with a full UI and REST API.

**Probing it while writing assertions surfaced 26 real defects.** The REST API
enforces no authentication at all: an unauthenticated caller reads any
customer's personal data and withdraws their money by putting a sequential,
guessable account id in a URL —
[demonstrated end to end](python/tests/api/test_security_api.py). `buyPosition`
credits an account for a negative share count, so money can be created. Two more
defects were found by trying to run the suite in parallel, and the AI fuzzer
widened a third by catching a crash that a weak assertion had been hiding. Each
is `xfail(strict=True)`, so the suite goes red the day ParaBank fixes one
— [full register](docs/test_plan.md#defects-found-in-the-application-under-test).

Built to show two things: **AI is a force multiplier for a QA engineer, not a
replacement**, and the approach is not tied to one language. The first claim is
only worth making if the AI earns its place, so it is held to one rule: **the
model proposes, the checked-in code decides.** An LLM answers differently on two
runs, so nothing that gates CI may depend on one.

## Run it yourself

Everything runs in Docker — no Python, no .NET, no browser install. One command
brings up the application under test and runs the suite against it:

```bash
git clone https://github.com/coldvalsidalv/qa-automation-parabank.git
cd qa-automation-parabank

# critical path (110 tests)
docker compose run --rm --build --user "$(id -u):$(id -g)" tests

# everything (225 tests)
docker compose run --rm --build --user "$(id -u):$(id -g)" tests pytest
```

The first run builds the test image and pulls ParaBank, which takes a few
minutes; after that a full run is about ten seconds.

Two details in that command are not decoration. `--build` matters on a repeat
run: Compose reuses a cached image otherwise, and you would be testing
yesterday's code. `--user` matters on Linux: the container writes the Allure
results into your clone through a bind mount, and as root it would leave files
there that need `sudo` to delete and that break a later local `pytest` run.

Expect one skip: the test that compares the `ruff` pin in `.pre-commit-config.yaml`
against `uv.lock` cannot run inside the image, because that file lives at the
repository root, outside the image's `./python` build context. It says so when it
skips.

To work on the suite rather than just run it, see the
[Python quick start](python/README.md#quick-start) — `uv sync`, `playwright
install chromium`, `pytest`.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/coldvalsidalv/qa-automation-parabank?quickstart=1)

The Codespaces button gives you a cloud machine with Docker ready; run the same
commands there.

## Two stacks, one test plan

The same patterns — page objects, self-provisioned test data, business-level
Allure steps, retain-on-failure artifacts, AI failure triage — implemented on
two stacks. The [test plan](docs/test_plan.md) covers both, with a section per
stack.

The interesting half of the port is the defect register. NUnit has no `xfail`,
so `KnownDefect.Expect` rebuilds strict-xfail semantics from a predicate, and
carries eight defects — including D-09 with its live theft proof — into C#.
Porting more happy paths would only have shown that page objects translate
between languages, which was never in doubt.

| | Stack | Scope | Where |
|---|-------|-------|-------|
| **Python** (primary) | pytest · Playwright · httpx · Allure | 225 tests — **139 against ParaBank** (102 API across 14 resource areas incl. JSON-Schema contracts and error-message sweeps + 37 UI) and **86 harness guards** (AI modules, repository invariants; no app required). 26 defects as 44 strict-xfail plus 7 live proofs; +16 opt-in `ai_judge`, +2 AI-showcase | [python/](python/README.md) |
| **C# / .NET** (slice) | NUnit · Playwright for .NET · Allure.NUnit | Vertical slice — auth + accounts + transfer, UI + API, 29 tests (+1 AI-showcase): 8 defects as strict `KnownDefect` checks including D-09 with a live theft proof, AI failure hook | [dotnet/](dotnet/README.md) |

The C# slice exists to prove portability, not to maintain two copies of
everything — hence a focused slice rather than full parity. The full register
(26 defects) stays on the Python side.

## What the report looks like

The [live Allure report](https://coldvalsidalv.github.io/qa-automation-parabank/)
(Python suite) is published from CI on every run.

Overview — pass rate, trend, the Environment widget, and features-by-story:

![Allure overview](docs/images/allure-overview.png)

Each test reads like a classic test case: business-level steps with the
underlying actions nested, including the fixtures that register a customer and
open accounts via the API:

![Allure test steps](docs/images/allure-steps.png)

A failed test carries its evidence — screenshot, Playwright trace, video, and
the AI diagnosis (root cause, evidence, recommended fix) generated by a local
model:

![AI failure analysis](docs/images/allure-ai-analysis.png)

## Where the AI actually does work

Four features, each paired with the deterministic layer that makes it safe to
rely on. The full design is in the [test plan](docs/test_plan.md#ai-in-the-suite-and-where-it-is-not-allowed).

| Feature | The model | What decides |
|---------|-----------|--------------|
| **Error-message judge** | Judges whether a message leaks internals or is actionable | A list of fragments seen in real responses — the gate needs no model |
| **API fuzzer** | Proposes parameter combinations worth trying | Fixed rules: a 5xx on client input, or a leak |
| **Failure triage** | Diagnoses a failed test into the Allure report | Nothing — it annotates, never votes |
| **Self-healing locators** | Suggests replacement selectors | Playwright: only a selector matching exactly one element is used |

**The judge** turns "no user-facing error leaks implementation detail" into a
general property. `pytest` runs it against a fixed signature list — deterministic,
no Ollama, always on. The `ai_judge` lane then asks the LLM the questions a
substring list cannot answer: is there a leak the list has not seen, and could a
customer act on this message at all. What the model finds is promoted into the
list, after which everyone catches it with no model running.

**The fuzzer** is exploratory testing made repeatable. Its own history is the
argument for the design: the first version reported 18 findings on three
endpoints where a rerun on a freshly restarted app found 5. A sweep that cannot
tell a case which broke the server from one that inherited an earlier case's
damage is not evidence, so it now runs a read-only canary — `GET /accounts/{id}`
— before each endpoint and after each finding, and stops when the server stops
answering it cleanly. Corrected, it rediscovered D-14 on its own and **widened
it**: the empty-`amount` crash that the test plan had recorded as working,
because the test asserting it only checked `status >= 400` — which a 500
satisfies.

That is the shape of the claim. The AI did not write the suite; it found two
things a careful engineer had missed, and every verdict it influenced is
reproducible without it.

**A missing model fails loudly where it was asked for, quietly where it was
not.** The two entry points you invoke on purpose — `make ai-judge` and
`make fuzz` — check first and stop with the command that fixes it, telling a
stopped Ollama apart from a model that was never pulled. A lane that reports
success having judged nothing is worse than an error. The ambient features are
the opposite case: `AI_ANALYSIS` and `SELF_HEAL` run inside suites that gate
merges, so they degrade silently and never fail a build because a side feature
is offline.

## Defects found in the application under test

The 26 from the top of this page, with the reproduction for each in the
[test plan](docs/test_plan.md#defects-found-in-the-application-under-test).
The ones worth naming:

- **Critical: the REST API has no authentication (D-09).** An unauthenticated
  caller can read any customer's PII and withdraw their money just by putting a
  (sequential, guessable) account id in the URL —
  [`test_security_api.py`](python/tests/api/test_security_api.py) demonstrates
  the theft end to end.
- **Critical: money creation (D-12, D-13).** `buyPosition` accepts a negative
  share count and credits the account instead of debiting it; `sellPosition`
  sells shares the customer does not own, with no ownership check at all. A
  single call is bounded only by `Integer.MAX_VALUE`, and nothing stops
  repeating it.
- **Critical: the admin page has no authentication (D-18)** — including the
  control that wipes the entire database.
- Negative-amount transfers and withdrawals are accepted — a money pump that
  drains accounts (zero-amount and same-account transfers pass too).
- No overdraft protection: withdrawals exceeding the balance succeed.
- Bill pay returns HTTP 500 whenever the payee payload carries a
  `routingNumber` key at all — any value, even `""` — while omitting the field
  succeeds (D-08); it also accepts a negative amount and credits the payer (D-21).
- A protected page answers an unauthenticated request with HTTP 500 and an
  internal-error page instead of redirecting to the login form (D-22).
- `updateCustomer` always returns HTTP 500 — the profile cannot be changed via API (D-10).
- `getPositionHistory` returns 400 for every valid position — the history endpoint is inaccessible (D-11).
- **Not concurrency-safe (D-25, D-26).** Registering distinct, unused usernames
  concurrently gets them rejected as duplicates, and concurrent `createAccount`
  calls fail outright — while the identical requests all succeed when
  serialised. Both were found by running the suite under `pytest-xdist`, and
  both are why it [runs sequentially by choice](docs/test_plan.md#parallelism-and-why-the-suite-runs-sequentially).

## CI/CD

All workflows run ParaBank as a service container — no dependency on the public
demo, no secrets:

- **[ci.yml](.github/workflows/ci.yml)** — Python lint + type-check (mypy) +
  smoke on PRs; the full suite on push to `main` and a weekly schedule; any
  marker on demand (`workflow_dispatch`); Allure report with history published
  to GitHub Pages.
- **[ci-dotnet.yml](.github/workflows/ci-dotnet.yml)** — the .NET slice on push/PR
  touching `dotnet/`, and on demand.
- **[ai-demo.yml](.github/workflows/ai-demo.yml)** — manual AI showcase: installs
  Ollama on the runner and publishes a report with real AI attachments to `/ai-demo`.
- **[codeql.yml](.github/workflows/codeql.yml)** — static analysis of Python and C#.

`main` is protected (required checks, up-to-date branches, no force-push).
Dependabot keeps dependencies and Actions current; `ruff` and `mypy` run as
pre-commit hooks and CI gates.

Coverage is measured on the full run and gated at 85% (currently 89%), with the
HTML report published as a CI artifact. It covers the **test harness** — page
objects, the API client, the AI modules, the fixtures — and answers "how much of
our own code does the suite exercise". It is not a measure of how much of
ParaBank is tested; that question is answered by the [test plan](docs/test_plan.md),
not by a percentage.

## License

[MIT](LICENSE) © 2026 Uladzislau. Free to read, fork, and learn from — keep the
copyright notice. Built as a portfolio piece; the ParaBank application under
test is a separate product of Parasoft.

## Repository layout

```
├── python/        # Python suite (pytest + Playwright) — see python/README.md
├── dotnet/        # C#/.NET vertical slice (NUnit) — see dotnet/README.md
├── docs/          # shared test plan, defect register, discovery notes, report images
├── docker-compose.yml  # ParaBank app under test (+ optional Ollama)
└── .github/workflows/  # CI, AI demo, CodeQL
```
