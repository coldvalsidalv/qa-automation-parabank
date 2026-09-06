"""Judges the error messages ParaBank shows its users.

Two layers, deliberately separated.

`signature_leaks` is deterministic: a list of fragments, each seen in a real
ParaBank response, that no user-facing message may contain. It needs no model,
never flakes, and is what gates CI.

`judge` asks the LLM the question a signature list cannot answer — is this
message *actionable* for a non-technical customer, and does it leak something
the list has not seen before. It generalises where the list only recognises.
The AI lane runs it over the same messages the deterministic gate covers, and
a leak the LLM finds that the list missed is a finding: the fragment gets
promoted into SIGNATURES, and from then on it is caught deterministically,
by everyone, with no model running.

That is the division of labour throughout: the model proposes, the checked-in
code decides.
"""

from dataclasses import dataclass

from ai.llm import complete_json, load_prompt

# Every entry was observed in a live ParaBank response; see
# docs/test_plan.md and tests/api/test_error_messages.py for where.
SIGNATURES: tuple[str, ...] = (
    "/ by zero",
    "Cannot invoke",
    "Exception",
    "com.parasoft",
    "java.lang",
    "java.math",
    "org.springframework",
    "org.apache",
    "at com.",
    "at java.",
    "An internal error has occurred",
    "Stacktrace",
    "SQLException",
)


@dataclass(frozen=True)
class Verdict:
    leaks_internals: bool
    actionable: bool
    reason: str
    source: str
    """Where the verdict came from: "llm", or "signatures" when the model was
    unreachable and the deterministic layer answered instead."""


def signature_leaks(message: str) -> list[str]:
    """Fragments of `message` that no user-facing text may contain."""
    return [s for s in SIGNATURES if s.lower() in message.lower()]


def judge(message: str, context: str) -> Verdict:
    """Ask the LLM to judge one message; fall back to signatures if it is down.

    The fallback never reports a message as clean on the model's behalf: it
    reports exactly what the deterministic layer can prove, and labels the
    verdict `source="signatures"` so a caller can tell the difference.
    """
    user_message = f"Request: {context}\n\nMessage shown to the user:\n{message!r}"
    try:
        result = complete_json(load_prompt("judge_message"), user_message)
    except Exception as exc:
        return _from_signatures(message, f"LLM unavailable ({exc})")
    if not isinstance(result, dict):
        got = type(result).__name__
        return _from_signatures(message, f"LLM returned {got}, expected an object")

    leaks = result.get("leaks_internals")
    actionable = result.get("actionable")
    if not isinstance(leaks, bool) or not isinstance(actionable, bool):
        return _from_signatures(message, "LLM verdict was missing a boolean field")

    reason = result.get("reason")
    return Verdict(
        leaks_internals=leaks,
        actionable=actionable,
        reason=str(reason) if reason else "(model gave no reason)",
        source="llm",
    )


def _from_signatures(message: str, why: str) -> Verdict:
    matched = signature_leaks(message)
    return Verdict(
        leaks_internals=bool(matched),
        # Unknowable without the model. False would invent a finding, so the
        # deterministic layer abstains by calling it actionable.
        actionable=True,
        reason=f"{why}; signature check matched {matched or 'nothing'}",
        source="signatures",
    )
