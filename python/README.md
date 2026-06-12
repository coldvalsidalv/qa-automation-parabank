# ParaBank QA — Python suite

The primary suite: Python + Playwright + pytest + Allure, with the AI features.
For the project overview, the two-stack comparison, and report screenshots, see
the [root README](../README.md).

Thesis: **AI is a force multiplier for a QA engineer, not a replacement.** Every
stage of the testing process has an AI integration point, and every AI output
passes through engineering review before it ships.

## Where AI is wired in

| Stage | What the AI does | Where | Human's role |
|-------|------------------|-------|--------------|
| Discovery | Explores the app via Playwright MCP, proposes a test plan | [../docs/discovery.md](../docs/discovery.md) → [../docs/test_plan.md](../docs/test_plan.md) | Reviews, prunes, formalizes |
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

## Quick start

Run everything from this `python/` directory. No credentials or secrets needed —
the suite registers a fresh ParaBank customer per session. The app under test
runs locally (the public parabank.parasoft.com works too, but wipes its database
every few minutes, which makes runs flaky — see `BASE_URL` in
[.env.example](.env.example)).

```bash
git clone https://github.com/coldvalsidalv/qa-automation-parabank.git
cd qa-automation-parabank

docker compose up -d parabank             # app under test on :8080 (from repo root)

cd python
cp .env.example .env
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

From the repository root (`docker-compose.yml` lives there):

```bash
docker compose run --rm tests                          # parabank + smoke suite
docker compose --profile ai up -d ollama               # + local LLM
docker compose exec ollama ollama pull llama3.1:8b
docker compose run --rm -e AI_ANALYSIS=true -e SELF_HEAL=true tests pytest -m ai_demo
```

## Project structure

```
python/
├── ai/                  # LLM integrations (single entry point: ai/llm.py)
│   └── prompts/         # versioned prompt templates
├── pages/               # Page Objects (self-healing via BasePage)
├── tests/
│   ├── ui/              # Playwright UI tests
│   └── api/             # httpx REST API tests
├── utils/parabank_api.py# API client + self-registration
├── conftest.py          # fixtures + AI failure-analysis hook
└── Dockerfile           # Playwright-python image for the test runner
```

## Design decisions

- **Dedicated app under test.** The public ParaBank demo wipes its database
  every few minutes — a full run against it died mid-session during
  development. Locally and in CI the app runs from the official
  `parasoft/parabank` image: hermetic, fast (full suite in ~5 s), reproducible.
- **Self-provisioned test data.** The suite registers its own customer and
  opens a second account when needed. No flaky shared users, no secrets in CI.
- **Runs single-process by design — an app constraint, not a framework one.**
  The test data is isolated per session (each customer touches only its own two
  accounts), so the design itself is parallel-friendly. The limit is the app
  under test: the `parasoft/parabank` demo is a single H2-backed container that
  starts dropping account-creation and registration requests under concurrent
  load (verified — `pytest -n 2` already produces provisioning errors). The
  suite is fast enough sequentially (~5 s) that this costs nothing; the same
  reason perf numbers are out of scope (a single container can't produce valid
  ones).
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
