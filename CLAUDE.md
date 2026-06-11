# parabank-qa-ai — instructions for AI agents

QA automation for the ParaBank demo bank. Two stacks:

- **`python/`** — primary suite: Python, Playwright sync API, pytest, Allure,
  httpx, local Ollama for AI features. Most work happens here.
- **`dotnet/`** — C#/.NET vertical slice (NUnit + Playwright for .NET +
  Allure.NUnit) mirroring auth/accounts/transfer. See `dotnet/README.md`.

`docs/` (shared test plan + defect register) and `docker-compose.yml` (the
ParaBank app under test) live at the repo root.

## Commands

Python — run from `python/`:

```bash
cd python
uv run pytest -m smoke          # critical path
uv run pytest                   # full suite (ai_demo excluded via addopts)
uv run pytest -m ai_demo        # AI showcase; needs Ollama + AI_ANALYSIS/SELF_HEAL=true
uv run ruff check .
```

.NET — run from `dotnet/ParabankQa.Tests/`:

```bash
dotnet test --filter "Category!=ai_demo"
```

The app under test starts from the repo root: `docker compose up -d parabank`.

## Conventions (Python)

- Page Objects in `python/pages/`: selectors as class constants, behavior as
  methods returning plain values; assertions live in tests, never in page objects.
- All LLM calls go through `python/ai/llm.py` — do not instantiate OpenAI clients elsewhere.
- AI features are opt-in via `AI_ANALYSIS` / `SELF_HEAL` env flags and must
  degrade gracefully when Ollama is unreachable.
- Tests must not depend on pre-existing server state: the suite registers its
  own customer (`utils/parabank_api.register_customer`) and opens accounts it
  needs (`account_pair` fixture).
- Known ParaBank defects are `xfail(strict=True)` with the defect documented in
  `docs/test_plan.md`. Do not "fix" such tests by asserting the buggy behavior.
- Failure artifacts are retain-on-failure (`_managed_page` in `python/conftest.py`):
  trace and video record always, attach only on failure. Do not add per-step
  screenshots.

## Gotchas

- Run against a local app: `docker compose up -d parabank` and
  `BASE_URL=http://localhost:8080`. The public demo wipes its database every
  few minutes and will kill sessions mid-run. Never hardcode customer or
  account ids.
- A fresh ParaBank instance redirects the first request to `initializeDB.htm`;
  hit `index.htm` once (curl -L) before testing.
- Overview table, account balance, and the transfer form are populated by
  XHR after page load — page objects must wait, `count()`/`inner_text()`
  alone race the request.
- The transfer API returns 200 for zero/negative/same-account transfers
  (defects D-01..D-09 in `docs/test_plan.md`); the register form requires a
  JSESSIONID warm-up GET.
- `python/tests/ui/test_ai_showcase.py::test_failure_analysis_demo` fails by design.
- .NET only: NUnit `[SetUpFixture]` applies to its namespace and descendants,
  so the session fixture lives in the root namespace `ParabankQa.Tests`.
