"""Generates test-case drafts from a page description.

Offline helper, not part of the pytest run: the engineer reviews the
generated cases and implements the ones worth keeping.

Usage:
    python -m ai.test_generator [page_description.txt] > docs/generated_test_cases.json

With no argument it uses the built-in Transfer-page description as an example.
"""

import json
import sys
from pathlib import Path

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
    description = (
        Path(sys.argv[1]).read_text(encoding="utf-8")
        if len(sys.argv) > 1
        else TRANSFER_PAGE_DESCRIPTION
    )
    cases = generate_test_cases(description)
    json.dump(cases, sys.stdout, ensure_ascii=False, indent=2)
