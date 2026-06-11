# parabank-qa-ai — instructions for AI agents

QA automation for the ParaBank demo bank (Python, Playwright sync API, pytest,
Allure, httpx, local Ollama for AI features).

## Commands

```bash
uv run pytest -m smoke          # critical path (~1 min, hits the live demo)
uv run pytest                   # full suite (ai_demo excluded via addopts)
uv run pytest -m ai_demo        # AI showcase; needs Ollama + AI_ANALYSIS/SELF_HEAL=true
uv run ruff check .
```

## Conventions

- Page Objects in `pages/`: selectors as class constants, behavior as methods
  returning plain values; assertions live in tests, never in page objects.
- All LLM calls go through `ai/llm.py` — do not instantiate OpenAI clients elsewhere.
- AI features are opt-in via `AI_ANALYSIS` / `SELF_HEAL` env flags and must
  degrade gracefully when Ollama is unreachable.
- Tests must not depend on pre-existing server state: the suite registers its
  own customer (`utils/parabank_api.register_customer`) and opens accounts it
  needs (`account_pair` fixture).
- Known ParaBank defects are `xfail(strict=True)` with the defect documented in
  `docs/test_plan.md`. Do not "fix" such tests by asserting the buggy behavior.

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
  (defects D-01..D-04 in docs/test_plan.md); the register form requires a
  JSESSIONID warm-up GET.
- `tests/ui/test_ai_showcase.py::test_failure_analysis_demo` fails by design.
