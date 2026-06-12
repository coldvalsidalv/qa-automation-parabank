"""Contract checks: validate live API responses against JSON Schema documents.

The schemas in ``contracts/`` are the agreed response shape. A contract test
feeds the real response to ``schema_violations`` and asserts the list is empty,
so a field that changes type, goes missing, or appears unannounced fails the
build — drift that value-by-value assertions don't catch. The helper *returns*
the violations instead of asserting, so the assertion stays in the test, like
everywhere else in the suite.
"""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"


def load_schema(name: str) -> dict[str, Any]:
    return json.loads((CONTRACTS_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def schema_violations(instance: Any, schema_name: str) -> list[str]:
    """Return one human-readable string per contract violation (empty list = valid)."""
    validator = Draft202012Validator(load_schema(schema_name))
    return [
        f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    ]
