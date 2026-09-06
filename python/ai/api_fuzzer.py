"""Exploratory API testing, made repeatable.

Several defects in this suite (D-14, D-15, D-16, D-24) were found by hand,
poking endpoints with awkward values and noticing a 500 or a leaked Java
message. That is real work and it does not survive as an asset: nobody
remembers which combinations were tried, and the next endpoint gets whatever
attention is left over.

This tool keeps the judgement where it belongs and automates the tedium. The
LLM proposes parameter combinations — the part that benefits from knowing what
usually breaks a bank API. Everything after that is deterministic: a plain
runner executes each case, and fixed rules classify the response. The model
never decides whether something is a defect, so a finding is reproducible from
the report without re-running the model.

Findings are triaged, not asserted. It is a hunting tool, run by hand, and the
two account ids are required — fuzzing ids that do not exist only ever
exercises the not-found path:

    python -m ai.api_fuzzer <fromAccountId> <toAccountId> > docs/fuzz_report.md

A confirmed finding becomes a normal strict-xfail test in the suite, with its
own defect id. That promotion is the point: the model widens the search, the
checked-in tests hold the ground.
"""

import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field

import httpx

from ai.llm import complete_json, load_prompt
from ai.message_judge import signature_leaks


@dataclass(frozen=True)
class Endpoint:
    name: str
    path: str
    method: str
    parameters: str
    valid_params: dict[str, str]
    """A complete, known-good call. Doubles as the health check between cases."""
    fixed_params: dict[str, str] = field(default_factory=dict)
    """Values the caller must supply — ids that have to exist for the case to
    reach the logic under test rather than bouncing off a not-found check."""

    @property
    def valid_example(self) -> str:
        return "&".join(f"{k}={v}" for k, v in self.valid_params.items())


@dataclass(frozen=True)
class Finding:
    endpoint: str
    case: str
    why: str
    params: dict[str, str]
    status: int
    verdict: str
    body: str


def propose_cases(endpoint: Endpoint) -> list[dict]:
    """Ask the model for parameter combinations worth trying.

    Returns no cases rather than raising when the model is unreachable or
    answers with something other than the agreed shape: the sweep then reports
    nothing for this endpoint instead of dying halfway with a traceback and
    taking the findings from earlier endpoints with it.
    """
    description = (
        f"Endpoint: {endpoint.method} {endpoint.path}\n"
        f"Parameters: {endpoint.parameters}\n"
        f"Example of a valid call: {endpoint.valid_example}"
    )
    try:
        result = complete_json(load_prompt("fuzz_endpoint"), description, max_tokens=2048)
    except Exception as exc:
        print(f"No cases for {endpoint.name}: the model is unavailable ({exc})", file=sys.stderr)
        return []
    if not isinstance(result, dict):
        return []
    cases = result.get("cases")
    if not isinstance(cases, list):
        return []
    return [c for c in cases if isinstance(c, dict) and _case_params(c) is not None]


def _case_params(case: dict) -> dict[str, str] | None:
    """The case's parameters, or None if the model did not send a usable map.

    `params` is whatever the model put in the JSON. A string or a list there
    makes the `{**...}` merge in `run_case` raise TypeError — which is not an
    `httpx.HTTPError`, so it would escape the sweep entirely and discard every
    finding collected so far. Values are coerced to str for the same reason:
    httpx rejects a nested object as a query parameter.
    """
    params = case.get("params")
    if params is None:
        return {}
    if not isinstance(params, dict):
        return None
    return {
        str(name): str(value)
        for name, value in params.items()
        if isinstance(value, str | int | float | bool)
    }


def classify(response: httpx.Response) -> str | None:
    """Rules only — no model. Returns a verdict, or None when nothing is wrong.

    A 4xx is the correct answer to bad input and is not a finding; the suite
    exists to catch the two ways a service gets that wrong.
    """
    if response.status_code >= 500:
        return f"HTTP {response.status_code} — the server crashed on client input"
    leaks = signature_leaks(response.text)
    if leaks:
        return f"Leaks implementation detail {leaks} to the caller"
    return None


def run_case(client: httpx.Client, endpoint: Endpoint, case: dict) -> Finding | None:
    params = {**endpoint.fixed_params, **(_case_params(case) or {})}
    try:
        response = client.request(endpoint.method, endpoint.path, params=params)
    except httpx.HTTPError as exc:
        return Finding(
            endpoint.name,
            str(case.get("name", "?")),
            str(case.get("why", "")),
            params,
            0,
            f"Request failed: {exc}",
            "",
        )

    verdict = classify(response)
    if verdict is None:
        return None
    return Finding(
        endpoint.name,
        str(case.get("name", "?")),
        str(case.get("why", "")),
        params,
        response.status_code,
        verdict,
        response.text[:500],
    )


def is_healthy(client: httpx.Client, endpoint: Endpoint) -> bool:
    """Does a known-good call still get a clean answer?

    ParaBank degrades: once a few faults have gone through it, its error
    handling gives up and *every* response becomes the same HTML 500 page. The
    first version of this tool reported 18 findings on three endpoints, and all
    but the first two were that degradation echoing — cases blamed for a server
    that a previous case had already broken. Checking between cases is what
    makes a finding mean "this input did it".
    """
    try:
        response = client.request(endpoint.method, endpoint.path, params=endpoint.valid_params)
    except httpx.HTTPError:
        return False
    return response.status_code < 400 and not signature_leaks(response.text)


@dataclass(frozen=True)
class SweepResult:
    findings: list[Finding]
    degraded_after: str | None = None
    """The case whose damage the server did not recover from, if the sweep
    stopped early. Everything after it would have been unattributable."""


def fuzz(base_url: str, endpoints: Sequence[Endpoint]) -> SweepResult:
    findings: list[Finding] = []
    # The Accept header is not decoration: without it ParaBank answers the REST
    # endpoints with its HTML error page and a 500, and the sweep reports a wall
    # of findings that are entirely the client's fault. Same header as
    # ParabankApi, so the fuzzer hits the surface the suite actually tests.
    with httpx.Client(
        base_url=f"{base_url}/parabank/services/bank",
        headers={"Accept": "application/json"},
        timeout=30,
    ) as client:
        for endpoint in endpoints:
            if not is_healthy(client, endpoint):
                return SweepResult(findings, degraded_after=f"before sweeping {endpoint.name}")
            for case in propose_cases(endpoint):
                finding = run_case(client, endpoint, case)
                if finding is not None:
                    findings.append(finding)
                    # A finding means the server just took a fault. Only keep it
                    # if the server can still answer a good call; otherwise every
                    # later case would inherit this one's damage.
                    if not is_healthy(client, endpoint):
                        return SweepResult(
                            findings, degraded_after=f"{endpoint.name} — {finding.case}"
                        )
    return SweepResult(findings)


def as_markdown(result: SweepResult, endpoints: Sequence[Endpoint]) -> str:
    """A triage list for a human, not a pass/fail verdict."""
    findings = result.findings
    lines = [
        "# API fuzz report",
        "",
        f"Endpoints swept: {', '.join(e.name for e in endpoints)}.",
        "",
        "Cases proposed by a local LLM, executed and classified deterministically:",
        "a 5xx on client input, or implementation detail leaked to the caller.",
        "A 4xx is the correct answer to bad input and is not reported.",
        "",
        "**These are candidates.** Confirm each by hand, then promote it to a",
        "strict-xfail test with a defect id — that is what makes it stick.",
        "",
    ]
    if result.degraded_after is not None:
        lines += [
            f"> **Sweep stopped early at `{result.degraded_after}`.** ParaBank stopped",
            "> answering a known-good call cleanly, so every later case would have",
            "> inherited the damage rather than caused it. Restart the app and sweep",
            "> the remaining endpoints again.",
            "",
        ]
    if not findings:
        lines.append("No findings this run.")
        return "\n".join(lines)

    lines.append(f"## {len(findings)} finding(s)")
    for finding in findings:
        lines += [
            "",
            f"### {finding.endpoint} — {finding.case}",
            "",
            f"- **Verdict:** {finding.verdict}",
            f"- **Expected to break:** {finding.why}",
            f"- **Params:** `{json.dumps(finding.params, sort_keys=True)}`",
            "",
            "```",
            finding.body.strip()[:500] or "(empty body)",
            "```",
        ]
    return "\n".join(lines)


def main(argv: Sequence[str]) -> int:
    if len(argv) < 2:
        print(
            "usage: python -m ai.api_fuzzer <fromAccountId> <toAccountId>\n"
            "\n"
            "Ids must belong to a real customer — open them with the suite's own\n"
            "fixtures, or register a customer through the app first. Fuzzing with\n"
            "ids that do not exist only ever exercises the not-found path.",
            file=sys.stderr,
        )
        return 2

    from_id, to_id = argv[0], argv[1]
    account_endpoints = [
        Endpoint(
            name="transfer",
            path="/transfer",
            method="POST",
            parameters="fromAccountId (int), toAccountId (int), amount (decimal string)",
            valid_params={"fromAccountId": from_id, "toAccountId": to_id, "amount": "1.00"},
            fixed_params={"fromAccountId": from_id, "toAccountId": to_id},
        ),
        Endpoint(
            name="deposit",
            path="/deposit",
            method="POST",
            parameters="accountId (int), amount (decimal string)",
            valid_params={"accountId": from_id, "amount": "1.00"},
            fixed_params={"accountId": from_id},
        ),
        Endpoint(
            name="withdraw",
            path="/withdraw",
            method="POST",
            parameters="accountId (int), amount (decimal string)",
            valid_params={"accountId": from_id, "amount": "1.00"},
            fixed_params={"accountId": from_id},
        ),
    ]

    base_url = os.getenv("BASE_URL", "http://localhost:8080")
    result = fuzz(base_url, account_endpoints)
    print(as_markdown(result, account_endpoints))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
