"""Generates test-case drafts from a page description.

Offline helper, not part of the pytest run: the engineer reviews the
generated cases and implements the ones worth keeping.

Usage:
    python -m ai.test_generator > docs/generated_test_cases.json
"""
import json
import sys

from ai.llm import complete_json, load_prompt

TRANSFER_PAGE_DESCRIPTION = """
ParaBank Transfer Funds page (/parabank/transfer.htm).
A logged-in user transfers money between their own accounts.
Elements: From Account dropdown, To Account dropdown, Amount input, Transfer button.
On success shows "Transfer Complete!" with amount and account ids.
Known quirks: the backend accepts zero and negative amounts (defect).
"""


def generate_test_cases(page_description: str) -> list[dict]:
    result = complete_json(
        load_prompt("generate_tests"),
        f"Generate test cases for this page:\n\n{page_description}",
        max_tokens=4096,
    )
    if not isinstance(result, list):
        raise ValueError(f"Expected a JSON array of test cases, got: {type(result).__name__}")
    return result


if __name__ == "__main__":
    cases = generate_test_cases(TRANSFER_PAGE_DESCRIPTION)
    json.dump(cases, sys.stdout, ensure_ascii=False, indent=2)
