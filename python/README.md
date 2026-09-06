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
| Error-message judging | Judges whether an error shown to a user leaks internals or is unactionable | [ai/message_judge.py](ai/message_judge.py) → [tests/ai/test_message_judge_lane.py](tests/ai/test_message_judge_lane.py) | Promotes what it finds into the deterministic signature list |
| Defect hunting | Proposes parameter combinations likely to break an endpoint | [ai/api_fuzzer.py](ai/api_fuzzer.py) | Confirms a candidate, then writes it up as a strict-xfail test |
| Failure triage | Failed test → diagnosis (root cause, evidence, fix) attached to the Allure report | hook in [conftest.py](conftest.py) → [ai/failure_analyzer.py](ai/failure_analyzer.py) | Reads the triage instead of raw tracebacks |
| Self-healing | Broken locator → suggested alternatives → first working one used, logged as an Allure step | [pages/base_page.py](pages/base_page.py) → [ai/locator_healer.py](ai/locator_healer.py) | Sees the healed selector in the report, fixes the page object properly |

All AI features run on a **local Ollama** (`llama3.1:8b`) — free, offline, no
API keys — and are off by default (`AI_ANALYSIS`, `SELF_HEAL` env flags, the
`ai_judge` marker), so the suite is fully deterministic unless you opt in.

**One rule governs all of it: the model proposes, the checked-in code decides.**
Nothing that gates CI depends on a model answering the same way twice. The judge
has a signature list that gates on its own; the fuzzer classifies with fixed
rules; healing only accepts a selector Playwright says matches exactly one
element; triage annotates and never votes.

```bash
make ai-judge   # LLM judges the app's real error messages
make fuzz       # hunt for new API defects
```

The fuzzer registers a throwaway customer and opens its own funded accounts, the
way the suite's fixtures do. That is not just convenience: the cases it fires are
deliberately abusive — a proposed deposit of `1e9` really does land — so pointing
it at an account anything else uses would wreck that account's balance. Real ids
are needed regardless, since against ids that do not exist every case only
exercises the not-found path.

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
- **The judge and the fuzzer are where it paid off.** Both found something a
  careful engineer had missed. The fuzzer widened D-14: `amount=""` crashes
  `deposit`/`withdraw`/`transfer` with a 500, which this project had recorded as
  working because the test asserting it only checked `status >= 400` — and a 500
  satisfies that. The judge generalises "no error leaks internals" to endpoints
  nobody wrote a test for.
- **The fuzzer's first version was wrong, and how it was wrong is the lesson.**
  It reported 18 findings across three endpoints; a rerun on a freshly
  restarted app found 5, and the bodies of the extra ones were ParaBank's
  generic HTML error page rather than anything specific to the input. A tool
  that proposes candidates has to be able to say "the server was already
  unwell when I asked", so it now runs a read-only canary
  (`GET /accounts/{id}`) before each endpoint and after each finding, and
  stops the sweep when the server stops answering it cleanly.

  Two honest caveats. I could not reproduce the bad state on demand
  afterwards — firing D-14, bad-account-id, zero-loan, updateCustomer and
  billpay faults at a fresh container left both GETs and valid POSTs clean —
  so "the server was already unwell" is the best-supported reading of that
  run, not a demonstrated mechanism. And this canary shape cannot detect
  ParaBank's *other* documented degradation, where fault handling gives up and
  errors come back sanitised while valid calls keep succeeding (the D-20 note
  in `tests/api/test_loans_api.py`): nothing healthy changes, so no canary
  sees it.
- **The canary is read-only on purpose.** Every valid call on these endpoints
  is a deposit, a withdrawal or a transfer, so checking with one would move
  money on every check — several times per sweep. `tests/ai/test_api_fuzzer.py`
  asserts the canary is a GET.
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
uv run pytest -m unit                     # no app needed (AI module, offline)
uv run pytest -m "not ai_demo and not defect_proof"   # skip the current-defect proofs
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
├── contracts/           # JSON-Schema response contracts (account, customer,
│                        #   transaction, position, loan_response, billpay_response)
├── pages/               # Page Objects (self-healing via BasePage)
├── tests/
│   ├── ui/              # Playwright UI tests
│   ├── api/             # httpx REST API tests (incl. test_contracts_api.py)
│   ├── ai/              # unit tests for the AI module — mocked LLM, no Ollama
│   ├── test_tooling_pins.py      # guard: versions pinned twice must agree
│   └── test_allure_categories.py # guard: every xfail lands in its report bucket
├── utils/parabank_api.py# API client + self-registration
├── utils/contracts.py   # validate a response against a JSON-Schema contract
├── conftest.py          # fixtures + AI failure-analysis hook
└── Dockerfile           # Playwright-python image for the test runner
```

## Design decisions

- **Dedicated app under test.** The public ParaBank demo wipes its database
  every few minutes — a full run against it died mid-session during
  development. Locally and in CI the app runs from the official
  `parasoft/parabank` image, **pinned by digest** rather than `:latest`:
  hermetic, fast (full suite in ~7 s), reproducible. The pin is not incidental —
  the `defect_proof` tests below assert ParaBank's current broken behavior down
  to the cent, so a silently republished tag would turn CI red with no change on
  our side. To move to a newer build, update the digest in `docker-compose.yml`
  and the three workflows together and re-run the full suite.
- **Self-provisioned test data.** The suite registers its own customer and
  opens a second account when needed. No flaky shared users, no secrets in CI.
- **Randomized test order (pytest-randomly).** Heavy fixture sharing (see the
  trade-off below) means order-independence isn't free — it has to be
  verified, not assumed. It already earned its keep: randomizing order caught
  `test_get_position_by_id` intermittently failing whenever
  `test_sell_partial_position_reduces_shares` happened to run first and
  invalidated the shared position id. Fixed by giving the sell test its own
  dedicated position instead of sharing one with the read-only tests
  ([tests/api/test_positions_api.py](tests/api/test_positions_api.py)).
- **Mutating tests get an isolated resource, not a shared one.** `account_pair`
  is session-scoped, so a test that overdrafts, credits via a negative-amount
  defect probe, or buys/sells a throwaway position can corrupt state every
  other test reads. Two files independently hand-rolled a fix for this before
  it was generalized: `test_positions_api.py` forked a second buy fixture, and
  `test_deposit_withdraw_api.py` inlined its own `create_account(...)` call for
  the overdraft test. Both now use the shared `isolated_account` fixture
  ([conftest.py](conftest.py)) — one fresh account per test that needs
  isolation, instead of each file reinventing the same workaround.
- **Known trade-off: session-scoped identity, wide blast radius.**
  `credentials` → `customer_id` → `account_pair` → `auth_state` in
  [conftest.py](conftest.py) are all `scope="session"` — one customer and one
  pair of accounts serve the entire run. That is what makes self-provisioning
  cheap (one registration and one UI login instead of 79). The cost: if
  registration or the first login fails, every dependent test errors out as a
  fixture failure instead of a contained, diagnosable red — the whole run goes
  down together rather than degrading. Accepted deliberately because the
  failure surface is small and network-shaped (one HTTP round trip against a
  container on the same host), not because the risk doesn't exist. A suite
  provisioning real money movements or hitting a flakier upstream would need
  function- or module-scoped identity instead, trading setup cost for
  isolation.
- **Runs single-process by design — an app constraint, not a framework one.**
  The test data is isolated per session (each customer touches only its own two
  accounts), so the design itself is parallel-friendly. The limit is the app
  under test: the `parasoft/parabank` demo is a single H2-backed container that
  starts dropping account-creation and registration requests under concurrent
  load (verified — `pytest -n 2` already produces provisioning errors). The
  suite is fast enough sequentially (~7 s) that this costs nothing; the same
  reason perf numbers are out of scope (a single container can't produce valid
  ones).
- **Defects as strict xfail, not skipped or "fixed" assertions.** Tests assert
  the *correct* behavior and are marked with the defect; if the app gets
  fixed, the run flags it.
- **Contract checks alongside value assertions.** Value-level assertions check
  *what* a field holds; the contract tests
  ([test_contracts_api.py](tests/api/test_contracts_api.py)) validate the
  *shape* of the response against a JSON Schema in [contracts/](contracts/), so
  a renamed, retyped, missing, or unannounced field fails the build even when
  the values look right — drift that field-by-field checks miss. The helper
  returns the violations; the test owns the assertion, like everywhere else.
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
