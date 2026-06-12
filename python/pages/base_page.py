"""Base page object: navigation, Allure-logged actions, self-healing locators."""

import os

import allure
from playwright.sync_api import Locator, Page

from ai.locator_healer import heal_locator


def _self_healing_enabled() -> bool:
    return os.getenv("SELF_HEAL", "false").lower() == "true"


class BasePage:
    def __init__(self, page: Page, base_url: str = "") -> None:
        self.page = page
        self.base_url = base_url

    def navigate(self, path: str) -> None:
        with allure.step(f"Open {path}"):
            self.page.goto(self.base_url + path)

    def click(self, selector: str, description: str = "") -> None:
        with allure.step(f"Click {description or selector}"):
            self._locator(selector, description).click()

    def fill(self, selector: str, value: str, description: str = "") -> None:
        with allure.step(f"Fill {description or selector}"):
            self._locator(selector, description).fill(value)

    def select_option(
        self,
        selector: str,
        *,
        index: int | None = None,
        value: str | None = None,
        description: str = "",
    ) -> None:
        with allure.step(f"Select {description or selector}"):
            locator = self._locator(selector, description)
            if index is not None:
                locator.select_option(index=index)
            else:
                locator.select_option(value=value)

    def _locator(self, selector: str, description: str = "") -> Locator:
        """Resolve a selector for an *action*, healing it when SELF_HEAL=true.

        Healing wraps the action methods above (click/fill/select_option) only;
        state queries like ``wait_for``/``is_visible`` call ``page.locator``
        directly, since their job is to observe presence, not to drive a broken
        selector to a working one.

        XHR-populated content (overview table, transfer form) is waited for in
        each page's ``open`` before any action runs, so a zero-count match at
        action time means a broken selector rather than a not-yet-rendered one —
        the case healing is meant to repair. The SELF_HEAL check comes first so
        the extra ``count()`` round-trip is never paid when healing is off (the
        default).
        """
        if not _self_healing_enabled():
            return self.page.locator(selector)

        locator = self.page.locator(selector)
        if locator.count() > 0:
            return locator

        healed = heal_locator(self.page, description or selector, self.page.content())
        if healed is None:
            return locator
        with allure.step(f"Self-healed locator: {selector!r} -> {healed!r}"):
            return self.page.locator(healed)
