# ParaBank QA — AI-Assisted Test Automation

[![QA Automation CI](https://github.com/coldvalsidalv/qa-automation-parabank/actions/workflows/ci.yml/badge.svg)](https://github.com/coldvalsidalv/qa-automation-parabank/actions/workflows/ci.yml)
[![CodeQL](https://github.com/coldvalsidalv/qa-automation-parabank/actions/workflows/codeql.yml/badge.svg)](https://github.com/coldvalsidalv/qa-automation-parabank/actions/workflows/codeql.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Playwright](https://img.shields.io/badge/playwright-1.60-green)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)

[Live Allure report](https://coldvalsidalv.github.io/qa-automation-parabank/) · [AI demo report](https://coldvalsidalv.github.io/qa-automation-parabank/ai-demo/)

Test automation for [ParaBank](https://parabank.parasoft.com) — a demo banking
application with a full UI and REST API — built to show one thing: **AI is a
force multiplier for a QA engineer, not a replacement.** Every stage of the
testing process has an AI integration point, and every AI output passes through
engineering review before it ships.

The stack here is Python + Playwright + pytest, but nothing in the approach is
stack-specific: the same workflow (AI discovery → reviewed generation → AI
failure triage → self-healing) ports to TypeScript, Java, or anything else.

## Where AI is wired in

| Stage | What the AI does | Where | Human's role |
|-------|------------------|-------|--------------|
| Discovery | Explores the app via Playwright MCP, proposes a test plan | [docs/discovery.md](docs/discovery.md) → [docs/test_plan.md](docs/test_plan.md) | Reviews, prunes, formalizes |
| Test generation | Drafts test cases from a page description | [ai/test_generator.py](ai/test_generator.py) | Implements only the cases worth keeping |
| Failure triage | Failed test → diagnosis (root cause, evidence, fix) attached to the Allure report | hook in [conftest.py](conftest.py) → [ai/failure_analyzer.py](ai/failure_analyzer.py) | Reads the triage instead of raw tracebacks |
| Self-healing | Broken locator → suggested alternatives → first working one used, logged as an Allure step | [pages/base_page.py](pages/base_page.py) → [ai/locator_healer.py](ai/locator_healer.py) | Sees the healed selector in the report, fixes the page object properly |

All AI features run on a **local Ollama** (`llama3.1:8b`) — free, offline, no
API keys — and are off by default (`AI_ANALYSIS`, `SELF_HEAL` env flags), so
the suite is fully deterministic unless you opt in.

### What worked, what didn't — an honest retrospective

The point of this project is to be specific about where AI helps and where it
doesn't, rather than to claim it does everything.

- **Why a local 8B model, not GPT-4 over an API.** Three reasons, in order:
  (1) a banking app is exactly the context where you cannot ship test data to a
  third-party LLM — running locally keeps it on the machine; (2) zero cost, so
  the failure-triage hook can run on every red test in CI without a bill;
  (3) determinism — with `temperature=0` and Ollama's `format=json` the model's
  output is reproducible, which a test suite needs.
- **Failure triage — genuinely useful.** Reading a one-paragraph "what failed /
  likely cause / where to look" beats scrolling a Playwright traceback. It is an
  assistant: it points, the engineer decides.
- **Self-healing — useful as a signal, dangerous as a fix.** It belongs in the
  report as "the old selector broke, here's one that works," *not* as a silent
  runtime substitution that hides a real UI change. That is why the healed
  selector shows up as a visible Allure step and the engineer still fixes the
  page object properly. An auto-heal that quietly keeps the test green would be
  worse than the failure.
- **Where the 8B model is weak.** It occasionally returned malformed JSON despite
  the instruction (fixed by constraining decoding, not by trusting the prompt),
  and its locator suggestions are only as good as the HTML context it is given.
  Test-case *generation* produces drafts, never final tests — every generated
  case is reviewed and most are rewritten or dropped.
- **What I deliberately did not build.** No AI that writes and commits tests on
  its own, no auto-fix that edits the repo. Trusting a non-deterministic system
  in a place that gates merges is the opposite of what testing is for.

## Defects found in the application under test

Probing the app while writing assertions surfaced nine real ParaBank defects,
documented as `xfail(strict=True)` so the suite alerts if they ever get fixed
([full list](docs/test_plan.md#defects-found-in-the-application-under-test)).
Highlights:

- **Critical: the REST API has no authentication (D-09).** An unauthenticated
  caller can read any customer's PII and withdraw their money just by putting a
  (sequential, guessable) account id in the URL — `test_security_api.py`
  demonstrates the theft end to end.
- Negative-amount transfers and withdrawals are accepted — a money pump that
  drains accounts (zero-amount and same-account transfers pass too)
- No overdraft protection: withdrawals exceeding the balance succeed
- Bill pay is entirely broken — the endpoint always returns HTTP 500
- Empty transfer amount surfaces as "internal error" instead of the validation
  message that exists in the DOM but is never shown

## Quick start

No credentials or secrets needed — the suite registers a fresh ParaBank
customer per session. The app under test runs locally (the public
parabank.parasoft.com works too, but wipes its database every few minutes,
which makes runs flaky — see `BASE_URL` in [.env.example](.env.example)).

```bash
git clone https://github.com/coldvalsidalv/qa-automation-parabank.git
cd qa-automation-parabank
cp .env.example .env

docker compose up -d parabank             # app under test on :8080
uv sync                                   # or: pip install -e ".[dev]"
uv run playwright install chromium

uv run pytest -m smoke                    # critical path
uv run pytest                             # full suite
allure serve allure-results               # local report
```

`make help` lists shortcuts for all of the above (`make app`, `make smoke`,
`make test`, `make ai-demo`, `make lint`, `make report`).

### With AI features

```bash
brew install ollama
ollama pull llama3.1:8b

AI_ANALYSIS=true SELF_HEAL=true uv run pytest -m ai_demo
allure serve allure-results
```

`pytest -m ai_demo` runs two showcase tests: one fails on purpose (producing an
AI diagnosis attachment), one logs in through a deliberately outdated selector
(healed at runtime, visible as an Allure step).

### Fully in Docker

```bash
docker compose run --rm tests                          # parabank + smoke suite
docker compose --profile ai up -d ollama               # + local LLM
docker compose exec ollama ollama pull llama3.1:8b
docker compose run --rm -e AI_ANALYSIS=true -e SELF_HEAL=true tests pytest -m ai_demo
```

## CI/CD

Both workflows run ParaBank as a service container — no dependency on the
public demo, no secrets:

- **[ci.yml](.github/workflows/ci.yml)** — lint + smoke on every push/PR,
  manual runs with any marker expression (`workflow_dispatch`), weekly
  scheduled run; Allure report with history published to GitHub Pages.
- **[ai-demo.yml](.github/workflows/ai-demo.yml)** — manual showcase: installs
  Ollama on the runner, executes the `ai_demo` tests, publishes the report with
  real AI attachments to `/ai-demo`.
- **[codeql.yml](.github/workflows/codeql.yml)** — CodeQL static analysis on
  push/PR and weekly.

`main` is protected: the `test` and CodeQL checks are required to merge,
branches must be up to date, and force-pushes are disabled. Dependencies and
GitHub Actions versions are kept current by Dependabot; `ruff` lint+format runs
both as a pre-commit hook and as a CI gate.

## Project structure

```
├── ai/                  # LLM integrations (single entry point: ai/llm.py)
│   └── prompts/         # versioned prompt templates
├── pages/               # Page Objects (self-healing via BasePage)
├── tests/
│   ├── ui/              # Playwright UI tests
│   └── api/             # httpx REST API tests
├── utils/parabank_api.py# API client + self-registration
├── conftest.py          # fixtures + AI failure-analysis hook
├── docs/                # test plan, discovery notes
└── .github/workflows/   # CI + AI demo
```

## Design decisions

- **Dedicated app under test.** The public ParaBank demo wipes its database
  every few minutes — a full run against it died mid-session during
  development. Locally and in CI the app runs from the official
  `parasoft/parabank` image: hermetic, fast (full suite in ~5 s), reproducible.
- **Self-provisioned test data.** The suite registers its own customer and
  opens a second account when needed. No flaky shared users, no secrets in CI.
- **Defects as strict xfail, not skipped or "fixed" assertions.** Tests assert
  the *correct* behavior and are marked with the defect; if the app gets
  fixed, the run flags it.
- **Retain-on-failure artifacts.** Every UI test records a Playwright trace
  (per-step screenshots, DOM snapshots, network, console) and a video; both
  are attached to the Allure report only when the test fails and discarded
  otherwise. Green runs stay lightweight, red ones come with full evidence —
  per-step screenshots of passing tests are cost without value.
- **AI is opt-in and observable.** Flags off → plain deterministic suite.
  Flags on → every AI intervention is visible in the report (diagnosis
  attachment, "Self-healed locator" step), never silent.
- **One LLM entry point** ([ai/llm.py](ai/llm.py)) — swapping the model or
  provider is a one-file change.
