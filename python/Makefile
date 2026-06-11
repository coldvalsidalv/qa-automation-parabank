.PHONY: help install app smoke test ai-demo lint format report clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies and the Chromium browser
	uv sync --extra dev
	uv run playwright install chromium

app:  ## Start the ParaBank app under test (http://localhost:8080)
	docker compose up -d --wait parabank

smoke:  ## Run the critical-path suite
	uv run pytest -m smoke

test:  ## Run the full suite (ai_demo excluded)
	uv run pytest

ai-demo:  ## Run the AI showcase (needs Ollama running)
	AI_ANALYSIS=true SELF_HEAL=true uv run pytest -m ai_demo

lint:  ## Lint and format-check
	uv run ruff check .
	uv run ruff format --check .

format:  ## Auto-format the codebase
	uv run ruff format .

report:  ## Open the Allure report from the latest run
	uv run allure serve allure-results

clean:  ## Remove generated artifacts
	rm -rf allure-results allure-report .pytest_cache
