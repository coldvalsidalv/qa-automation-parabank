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

Findings are triaged, not asserted. It is a hunting tool, run by hand:

    python -m ai.api_fuzzer > docs/fuzz_report.md

It provisions its own throwaway customer and accounts, the way the suite's
fixtures do. That is not just convenience: the cases it fires are deliberately
abusive — a proposed deposit of 1e9 really does land — so pointing it at an
account anyone else uses would wreck that account's balance. Ids belonging to a
real customer are also required for the cases to reach the logic under test at
all; against ids that do not exist every case only ever exercises the
not-found path.

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

from ai.llm import LLMUnavailable, complete_json, load_prompt, require_available
from ai.message_judge import signature_leaks
from utils.parabank_api import ParabankApi, open_account, register_customer


@dataclass(frozen=True)
class Endpoint:
    name: str
    path: str
    method: str
    parameters: str
    valid_params: dict[str, str]
    """A complete, known-good call, shown to the model as the example. Not used
    as the health check — every valid call on this API moves money."""
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

    Returns no cases when the model answers with something other than the
    agreed shape. A model that cannot be reached at all raises instead — the
    sweep has to tell "nothing worth trying here" from "nobody answered",
    because an empty report reads identically to a clean one.
    """
    description = (
        f"Endpoint: {endpoint.method} {endpoint.path}\n"
        f"Parameters: {endpoint.parameters}\n"
        f"Example of a valid call: {endpoint.valid_example}"
    )
    result = complete_json(load_prompt("fuzz_endpoint"), description, max_tokens=2048)
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
    """Run one case; a `Finding` only if `classify` says the answer was wrong.

    A transport error propagates rather than becoming a finding. The request
    never reached the application, so there is nothing to attribute to the
    input — reporting it beside real defects would put "the network dropped"
    under the same heading as "this parameter crashes the server".
    """
    params = {**endpoint.fixed_params, **(_case_params(case) or {})}
    response = client.request(endpoint.method, endpoint.path, params=params)
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


def is_healthy(client: httpx.Client, canary_path: str) -> bool:
    """Is the server still answering a read-only call cleanly?

    A canary, so that a finding means "this input did it" rather than "the
    server was already unwell". The first version of this tool had no check and
    reported 18 findings on three endpoints where a rerun found 5; a sweep that
    cannot tell a fresh failure from an inherited one is not evidence.

    Read-only on purpose. The obvious canary is the call the sweep already
    knows is valid, but on this API every one of those moves money — the check
    would run before each endpoint and after every finding, quietly
    depositing, withdrawing and transferring as it went. `GET /accounts/{id}`
    answers the same question and changes nothing.

    Honest limits: this catches a server that has stopped answering, not every
    way one can go wrong. ParaBank has a separate documented degradation in
    which its fault handling gives up and every *error* comes back sanitised
    while valid calls keep succeeding (see the D-20 note in
    tests/api/test_loans_api.py). No canary of this shape detects that, because
    nothing healthy changes.
    """
    try:
        response = client.get(canary_path)
    except httpx.HTTPError:
        return False
    return response.status_code < 400 and not signature_leaks(response.text)


@dataclass(frozen=True)
class SweepResult:
    findings: list[Finding]
    swept: tuple[str, ...] = ()
    """Endpoints actually reached. Reporting the endpoints *asked* for would
    name ones the sweep never called and imply they came back clean."""
    degraded_after: str | None = None
    """The case whose damage the server did not recover from, if the sweep
    stopped early. Everything after it would have been unattributable."""
    model_failed: str | None = None
    """Set when the model stopped answering part-way through. Without this a
    half-swept run and a clean one produce the same report."""
    transport_errors: tuple[str, ...] = ()
    """Cases whose request never reached the application. Not findings: there
    is no answer to classify, so there is nothing to blame the input for."""

    @property
    def is_partial(self) -> bool:
        """Did anything stop this sweep from covering what it set out to?

        The one question a caller needs, and the reason it is a property rather
        than three checks at each call site: a new way to end early would
        otherwise have to be remembered in every one of them.
        """
        return bool(self.degraded_after or self.model_failed or self.transport_errors)


def fuzz(base_url: str, endpoints: Sequence[Endpoint], canary_path: str) -> SweepResult:
    """Sweep `endpoints`, using a GET on `canary_path` to attribute findings."""
    findings: list[Finding] = []
    swept: list[str] = []
    transport_errors: list[str] = []
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
            if not is_healthy(client, canary_path):
                return SweepResult(
                    findings,
                    tuple(swept),
                    degraded_after=f"before sweeping {endpoint.name}",
                    transport_errors=tuple(transport_errors),
                )
            try:
                cases = propose_cases(endpoint)
            except Exception as exc:
                return SweepResult(
                    findings,
                    tuple(swept),
                    model_failed=f"{endpoint.name} ({exc})",
                    transport_errors=tuple(transport_errors),
                )

            swept.append(endpoint.name)
            for case in cases:
                try:
                    finding = run_case(client, endpoint, case)
                except httpx.HTTPError as exc:
                    # The request never reached the application, so this case
                    # was not tested — recorded, but never as a finding.
                    transport_errors.append(f"{endpoint.name} — {case.get('name', '?')} ({exc})")
                    continue
                if finding is not None:
                    findings.append(finding)
                    # A finding means the server just took a fault. Only keep it
                    # if the server can still answer a read-only call; otherwise
                    # every later case would inherit this one's damage.
                    if not is_healthy(client, canary_path):
                        return SweepResult(
                            findings,
                            tuple(swept),
                            degraded_after=f"{endpoint.name} — {finding.case}",
                            transport_errors=tuple(transport_errors),
                        )
    return SweepResult(findings, tuple(swept), transport_errors=tuple(transport_errors))


def as_markdown(result: SweepResult) -> str:
    """A triage list for a human, not a pass/fail verdict.

    Reports `result.swept` rather than the endpoints the caller asked for: on
    an early stop those are not the same list, and naming an endpoint nothing
    ever called reads as a clean result for it.
    """
    findings = result.findings
    lines = [
        "# API fuzz report",
        "",
        f"Endpoints swept: {', '.join(result.swept) or 'none'}.",
        "",
        "Cases proposed by a local LLM, executed and classified deterministically:",
        "a 5xx on client input, or implementation detail leaked to the caller.",
        "A 4xx is the correct answer to bad input and is not reported.",
        "",
        "**These are candidates.** Confirm each by hand, then promote it to a",
        "strict-xfail test with a defect id — that is what makes it stick.",
        "",
    ]
    if result.transport_errors:
        lines += [
            f"> **{len(result.transport_errors)} case(s) never reached the application.**",
            "> Their requests failed in transport, so they were not tested and are",
            "> not findings:",
            "",
        ]
        lines += [f"> - `{error}`" for error in result.transport_errors]
        lines.append("")
    if result.model_failed is not None:
        lines += [
            f"> **The model stopped answering at `{result.model_failed}`.** The",
            "> endpoints after it were never swept, so this report is partial —",
            "> it is not evidence that they are clean.",
            "",
        ]
    if result.degraded_after is not None:
        lines += [
            f"> **Sweep stopped early at `{result.degraded_after}`.** ParaBank stopped",
            "> answering a read-only call cleanly, so every later case would have",
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


@dataclass(frozen=True)
class Sandbox:
    """A throwaway customer's two accounts, for the sweep to abuse freely."""

    from_account: int
    to_account: int


def provision(base_url: str) -> Sandbox:
    """Register a customer and open two funded accounts of the fuzzer's own.

    Uses the suite's own client, so this inherits the D-25 and D-26 retries
    rather than reimplementing them.
    """
    credentials = register_customer(base_url)
    api = ParabankApi(base_url)
    try:
        login = api.login(credentials)
        if login.status_code != 200:
            raise RuntimeError(f"could not log in as {credentials.username}: {login.text}")
        customer_id = login.json()["id"]

        accounts = api.get_accounts(customer_id).json()
        if not accounts:
            raise RuntimeError(f"customer {customer_id} was created with no account")
        from_account = accounts[0]["id"]

        # Funded well past anything the cases withdraw, so a finding is the
        # endpoint failing rather than the account running dry.
        api.deposit(from_account, "100000.00")

        opened = open_account(api, customer_id, from_account)
        if opened.status_code != 200:
            raise RuntimeError(f"could not open a second account: {opened.text}")
        return Sandbox(from_account, opened.json()["id"])
    finally:
        api.close()


def main() -> int:
    # Preflight: a sweep with no model produces an empty report that looks
    # exactly like a clean one. Say so instead, before provisioning anything.
    try:
        require_available()
    except LLMUnavailable as exc:
        print(f"Cannot fuzz without a model.\n{exc}", file=sys.stderr)
        return 1

    base_url = os.getenv("BASE_URL", "http://localhost:8080")
    try:
        sandbox = provision(base_url)
    except Exception as exc:
        print(
            f"Could not provision a throwaway customer at {base_url}: {exc}\n"
            "Is ParaBank running? `docker compose up -d parabank`",
            file=sys.stderr,
        )
        return 1

    from_id, to_id = str(sandbox.from_account), str(sandbox.to_account)
    print(
        f"Sweeping accounts {from_id} and {to_id} of a throwaway customer.",
        file=sys.stderr,
    )
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

    # Read-only canary: the sweep's own endpoints all move money, and this runs
    # before every endpoint and after every finding.
    result = fuzz(base_url, account_endpoints, canary_path=f"/accounts/{from_id}")
    print(as_markdown(result))

    # Any early stop exits non-zero. A partial sweep whose report a human never
    # opens must not look, to a shell or a CI step, like a clean one.
    if not result.is_partial:
        return 0
    notes = [
        f"the model stopped answering at {result.model_failed}" if result.model_failed else "",
        f"the server stopped recovering at {result.degraded_after}"
        if result.degraded_after
        else "",
        f"{len(result.transport_errors)} case(s) never reached the application"
        if result.transport_errors
        else "",
    ]
    for note in notes:
        if note:
            print(f"Sweep incomplete: {note}.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
