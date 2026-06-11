"""Self-healing locators: when a selector matches nothing, ask the LLM
for alternatives and return the first one that exists on the page.

Wired into `BasePage._locator` behind the SELF_HEAL=true flag.
"""

import json

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from ai.llm import complete_json, load_prompt

# Keep the prompt within the local model's context window.
MAX_HTML_CHARS = 8000


def heal_locator(page: Page, element_description: str, html_context: str) -> str | None:
    """Return the first suggested selector that matches the live page, or None."""
    user_message = (
        f"Element to find: {element_description}\n\n"
        f"HTML context:\n```html\n{html_context[:MAX_HTML_CHARS]}\n```"
    )
    try:
        result = complete_json(load_prompt("heal_locator"), user_message)
    except json.JSONDecodeError:
        return None  # model produced malformed JSON — no healing this time
    if not isinstance(result, dict):
        return None

    for candidate in result.get("selectors", []):
        selector = candidate.get("selector")
        if not selector:
            continue
        try:
            if page.locator(selector).count() > 0:
                return selector
        except PlaywrightError:
            continue  # model suggested invalid selector syntax — try the next one
    return None
