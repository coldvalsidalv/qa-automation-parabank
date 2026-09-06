"""Self-healing locators: when a selector matches nothing, ask the LLM
for alternatives and return the first *unambiguous* one that exists on
the live page.

Wired into `BasePage._locator` behind the SELF_HEAL=true flag.
"""

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from ai.llm import complete_json, load_prompt

# Keeps the prompt inside the local model's context window. On a page larger
# than this the target element can fall outside the truncated markup and
# healing misses it — fine for ParaBank, not for a real app.
MAX_HTML_CHARS = 8000


def heal_locator(page: Page, element_description: str, html_context: str) -> str | None:
    """Return the first suggested selector that matches exactly one element, or None.

    Only a unique match is acted on. An ambiguous candidate gives no way to
    tell which element the model meant, and picking the first would drive the
    action at the wrong one while the report still reads as a clean heal.
    """
    user_message = (
        f"Element to find: {element_description}\n\n"
        f"HTML context:\n```html\n{html_context[:MAX_HTML_CHARS]}\n```"
    )
    try:
        result = complete_json(load_prompt("heal_locator"), user_message)
    except Exception:
        # Malformed JSON or the LLM call itself failed (e.g. Ollama unreachable) —
        # degrade gracefully, no healing this time.
        return None
    if not isinstance(result, dict):
        return None

    for candidate in result.get("selectors", []) or []:
        if not isinstance(candidate, dict):
            continue  # malformed candidate (not an object) — skip it
        selector = candidate.get("selector")
        if not isinstance(selector, str) or not selector:
            continue  # malformed candidate (missing/non-string "selector") — skip it
        try:
            if page.locator(selector).count() == 1:
                return selector
        except PlaywrightError:
            continue  # model suggested invalid selector syntax — try the next one
    return None
