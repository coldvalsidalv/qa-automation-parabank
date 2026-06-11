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

    def _locator(self, selector: str, description: str = "") -> Locator:
        """Resolve a selector, falling back to AI healing when SELF_HEAL=true.

        Healing triggers only when the selector matches nothing. ParaBank pages
        are server-rendered, so an absent element right after load means a
        broken selector rather than a not-yet-rendered one.
        """
        locator = self.page.locator(selector)
        if locator.count() > 0 or not _self_healing_enabled():
            return locator

        healed = heal_locator(self.page, description or selector, self.page.content())
        if healed is None:
            return locator
        with allure.step(f"Self-healed locator: {selector!r} -> {healed!r}"):
            return self.page.locator(healed)
