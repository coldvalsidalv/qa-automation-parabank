# Test Plan — ParaBank

Scope: critical user paths of the ParaBank demo bank (UI) plus the full REST
API surface. Each scenario maps to an implemented automated test; known
defects of the application under test are `xfail(strict=True)`.

## UI

| ID | Scenario | Test |
|----|----------|------|
| TC-01 | Login page renders with the login form | `python/tests/ui/test_login.py::test_login_page_loads` |
| TC-02 | Login with valid credentials lands on Accounts Overview | `python/tests/ui/test_login.py::test_login_with_valid_credentials` |
| TC-03 | Login with invalid credentials shows an error | `python/tests/ui/test_login.py::test_login_with_invalid_credentials_shows_error` |
| TC-04 | Login with empty credentials shows an error | `python/tests/ui/test_login.py::test_login_with_empty_credentials_shows_error` |
| TC-05 | Overview lists the customer's accounts | `python/tests/ui/test_overview.py::test_overview_shows_at_least_one_account` |
| TC-06 | Account link opens Account Activity | `python/tests/ui/test_overview.py::test_overview_account_link_opens_account_activity` |
| TC-07 | Account Activity shows a numeric balance | `python/tests/ui/test_account_activity.py::test_account_shows_numeric_balance` |
| TC-08 | Transfer between own accounts completes | `python/tests/ui/test_transfer.py::test_transfer_valid_amount_completes` |
| TC-09 | Transfer with empty amount does not move money | `python/tests/ui/test_transfer.py::test_transfer_empty_amount_does_not_complete` |
| TC-10 | Transfer with empty amount shows a validation message | `python/tests/ui/test_transfer.py::test_transfer_empty_amount_shows_validation_message` (**xfail — D-04**) |
| TC-11 | Transfer with zero amount is rejected | `python/tests/ui/test_transfer.py::test_transfer_zero_amount_is_rejected` (**xfail — D-01**) |
| TC-12 | Bill payment completes and confirms payee and amount | `python/tests/ui/test_bill_pay.py::test_bill_payment_completes` |
| TC-13 | Mismatched payee account numbers are rejected | `python/tests/ui/test_bill_pay.py::test_invalid_field_is_rejected_with_its_message[mismatched-accounts]` |
| TC-14 | Bill pay with an empty amount is rejected | `python/tests/ui/test_bill_pay.py::test_invalid_field_is_rejected_with_its_message[empty-amount]` |
| TC-15 | Bill pay with a non-numeric amount is rejected | `python/tests/ui/test_bill_pay.py::test_invalid_field_is_rejected_with_its_message[non-numeric-amount]` |
| TC-16 | Bill pay with no payee name is rejected | `python/tests/ui/test_bill_pay.py::test_invalid_field_is_rejected_with_its_message[empty-payee-name]` |
| TC-17 | Bill pay with a negative amount is rejected | `python/tests/ui/test_bill_pay.py::test_negative_amount_is_rejected` (**xfail — D-21**) |
| TC-18 | Loan request is approved for a funded customer | `python/tests/ui/test_request_loan.py::test_loan_request_is_approved` |
| TC-19 | Loan beyond available funds is denied with a reason | `python/tests/ui/test_request_loan.py::test_loan_beyond_available_funds_is_denied` |
| TC-20 | Zero loan amount shows validation, not an internal error | `python/tests/ui/test_request_loan.py::test_zero_amount_shows_validation_not_internal_error` (**xfail — D-20**) |
| TC-21 | Empty loan amount shows validation, not an internal error | `python/tests/ui/test_request_loan.py::test_empty_amount_shows_validation_not_internal_error` (**xfail — D-23**) |
| TC-22 | Logout returns to the login page and ends the session | `python/tests/ui/test_logout.py::test_logout_returns_to_the_login_page` |
| TC-23 | A protected page after logout does not show an internal error | `python/tests/ui/test_logout.py::test_protected_page_after_logout_does_not_show_an_internal_error` (**xfail — D-22**) |
| TC-24 | Registration succeeds and logs the customer straight in | `python/tests/ui/test_registration.py::test_registration_succeeds_and_logs_the_customer_in` |
| TC-25 | Mismatched passwords are rejected with a displayed message | `python/tests/ui/test_registration.py::test_mismatched_passwords_are_rejected` |
| TC-26 | Required fields (last name, city, state, zip) are enforced | `python/tests/ui/test_registration.py::test_required_fields_are_enforced` |
| TC-27 | A duplicate username is refused with the collision message | `python/tests/ui/test_registration.py::test_duplicate_username_is_rejected` |

## API

One file per resource under `python/tests/api/`; scenario names map 1:1 to test
function names.

| Area | File | Coverage |
|------|------|----------|
| Auth | `test_accounts_api.py` | login returns the customer object; invalid credentials → 400 |
| Accounts | `test_accounts_api.py` | concurrent account opening (**xfail — D-26**, + live proof); account list non-empty; field types; get-by-id consistency; unknown id → error; open CHECKING/SAVINGS account; new account appears in the list |
| Customer profile | `test_customer_api.py` | profile fields; nested address; unknown id → error |
| Deposit / withdraw | `test_deposit_withdraw_api.py` | deposit/withdraw move the balance by the exact amount; success messages; unknown account → error; negative deposit (**xfail — D-05**); overdraft (**xfail — D-06**); negative withdrawal (**xfail — D-07**); missing *or empty* amount → 500 (**xfail — D-14**, one parametrized test over both endpoints × both ways of supplying no amount); scientific-notation amount accepted (**xfail — D-15**) |
| Transfers | `test_transfer_api.py` | transfer succeeds and moves money; empty amount → 500 rather than a validation error (**xfail — D-14**); one parametrized `test_invalid_transfer_is_rejected` covering zero amount (**xfail — D-01**), negative amount (**xfail — D-02**) and same account (**xfail — D-03**), each case keeping its own strict xfail reason; missing amount param → 500 (**xfail — D-14**) |
| Transactions | `test_transactions_api.py` | list; field types; get-by-id; unknown id → error; filters by amount, date range, single date, month+type — both matching and empty cases. The fixture seeds one Credit **and** one Debit so the `type` filters have a guaranteed match and cannot pass on an empty response |
| Loans | `test_loans_api.py` | loan approved for a solvent customer; response fields; LOAN account created and validated against the `account` contract (the only guaranteed-approved loan in the suite, so the only place the contract's `LOAN` type is exercised); negative down payment (**xfail — D-19**, + live proof); zero amount leaks internal error (**xfail — D-20**); down payment exceeding the amount is approved (**xfail — D-24**, + live proof) |
| Bill pay | `test_billpay_api.py` | valid payment without `routingNumber` succeeds; with `routingNumber` present (**xfail — D-08**); negative amount (**xfail — D-21**) |
| Positions | `test_positions_api.py` | buy; list contains bought position; get-by-id; partial sell reduces shares; unknown id → error; negative share count on buy (**xfail — D-12**, + live proof); overselling a position (**xfail — D-13**, + live proof) |
| Position history | `test_position_history_api.py` | history for a valid position (**xfail — D-11**); unknown id → error |
| Update customer | `test_customer_update_api.py` | update succeeds (**xfail — D-10**); updated values visible via GET (**xfail — D-10**) |
| Registration | `test_registration_api.py` | valid registration succeeds; concurrent registrations (**xfail — D-25**, + live proof); missing state/zip correctly rejected; missing phone (**xfail — D-17**); overlong street reports the wrong error (**xfail — D-16**) |
| Contracts | `test_contracts_api.py` | account, customer, transaction, position, loan response, and bill pay response each validated against their JSON Schema in `contracts/` |
| Security | `test_security_api.py` | unauthenticated read of a foreign account / customer PII / withdrawal must be rejected (**xfail — D-09**); live proof that money theft is currently possible; admin page reachable with no auth (**xfail — D-18**); protected web pages answer anonymous callers with HTTP 500 instead of redirecting to login (**xfail — D-22**, four pages) |

## AI module (unit)

No browser, no server, no Ollama — these mock `ai.llm.complete`/`complete_json`
directly and run in every default suite invocation.

| Area | File | Coverage |
|------|------|----------|
| Failure triage | `test_failure_analyzer.py` | returns the LLM diagnosis; degrades to `"AI analysis unavailable: ..."` instead of raising when the LLM call fails (the AI_ANALYSIS graceful-degradation contract) |
| Test-case generation | `test_test_generator.py` | returns the parsed list; rejects a non-list LLM response with `ValueError` |
| LLM entry point | `test_llm.py` | message order, `temperature=0`, `max_tokens` forwarding; `format=json` requested only in JSON mode; markdown-fence stripping for objects **and** arrays; `content=None` becomes `""`; malformed JSON raises rather than returning empty — the contract `locator_healer` depends on to degrade deliberately; every prompt file the code names exists |
| Locator self-healing | `test_locator_healer.py` | returns the first candidate matching **exactly one** element; skips zero-match, ambiguous (>1) and syntactically invalid candidates; skips malformed JSON entries *before* touching the page; returns `None` for a non-object response or an unreachable LLM; clips oversized markup to `MAX_HTML_CHARS` |

## C# / .NET slice

A deliberately narrow vertical slice whose purpose is to show the patterns port
across stacks, not to duplicate coverage. 30 tests in
`dotnet/ParabankQa.Tests/Tests/` (29 plus one `ai_demo`, excluded by default).

| Area | File | Coverage |
|------|------|----------|
| Auth (API) | `AccountsApiTests.cs` | login returns the customer; invalid credentials rejected |
| Accounts (API) | `AccountsApiTests.cs` | customer has accounts; field types; get-by-id matches the list entry |
| Login (UI) | `LoginTests.cs` | page loads; valid login reaches Overview; invalid shows an error; Register link present |
| Overview (UI) | `OverviewTests.cs` | loads for a logged-in user; lists at least one account; navigation links present |
| Transfers (UI) | `TransferTests.cs` | account dropdown populated; a valid transfer completes; reachable from Overview |
| Defect register (API) | `DefectRegisterApiTests.cs` | zero-amount transfer (**D-01**); negative-amount transfer (**D-02**); same-account transfer (**D-03**); negative deposit (**D-05**); overdraft withdrawal (**D-06**); negative withdrawal (**D-07**); missing amount parameter → 500 (**D-14**) |
| Security (API) | `SecurityApiTests.cs` | unauthenticated read of a foreign account / customer PII / withdrawal must be rejected (**D-09**); live proof that money theft is currently possible |
| Defect-register guard (unit) | `KnownDefectTests.cs` | `KnownDefect.Expect` passes on a live defect, fails naming the id when it is fixed, and reports an unreachable app as a broken test rather than as either verdict |
| AI showcase | `AiShowcaseTests.cs` | one intentional failure carrying an AI diagnosis (`Category=ai_demo`, excluded by default) |

**Strict xfail, rebuilt.** NUnit has no `xfail`, so the register could not be
translated — it had to be re-implemented.
`Support/KnownDefect.cs` takes the check as a predicate answering "does the
application behave correctly now?": false means the defect is present and the
test passes, true means it is fixed and the test fails naming the defect id.
Same strictness as `xfail(strict=True)`, same alert when ParaBank is repaired.

Two NUnit 4 constraints shape it, both found by hitting them: the check may not
use NUnit assertions (a failed `Assert.That` is recorded in the test result even
when its exception is caught), and the verdict throws `AssertionException`
rather than calling `Assert.Fail` (which records, and would make the helper
untestable). Because a helper of this shape fails silently when it is wrong, it
carries its own guard — the same reasoning as the Allure-category test on the
Python side.

**Still out of scope for the slice:** D-04, D-08, D-10..D-13, D-15..D-26, the
JSON-Schema contract checks, and the UI defect probes. The slice documents the
defects reachable through the endpoints it already covers; the Python suite
remains the complete register.

## Repository invariants (unit)

Assertions about the repo itself, not the application. Same rationale as the
rest of the suite: an invariant that is only written in a comment is not
enforced.

| Area | File | Coverage |
|------|------|----------|
| Allure categorisation | `test_allure_categories.py` | every `xfail` reason in the suite matches the "Known ParaBank defects" `messageRegex`, replaying allure2's own matching (`Pattern.DOTALL` + `matches()`, i.e. `re.DOTALL` + `fullmatch`). This rule fails *silently* — a reason worded differently drops into the uncategorised pile while the run stays green, which is how all four `test_security_api.py` xfails were excluded. Reasons are collected from every call, not just decorators, so an xfail attached via `pytest.param(marks=...)` is covered too; a marker with a missing or non-literal `reason=` is reported rather than skipped. No test asserts the regexes *compile*: Allure is a JVM tool, so validating its patterns with Python's `re` would give false assurance in both directions |
| Tool pin lockstep | `test_tooling_pins.py` | the `ruff-pre-commit` hook rev matches the `ruff` version in `uv.lock`; the `Dockerfile` playwright base-image tag matches the `playwright` version in `uv.lock`. Both pins are updated by *different* Dependabot ecosystems (`pre-commit`/`docker` vs `uv`), so they arrive as separate PRs that can merge apart. Neither drift is visible to CI otherwise — CI never invokes pre-commit and never builds the image. Fails loudly if a pin cannot be located at all, so the guard cannot pass vacuously. Paths are found by walking up from the test file, because the suite also runs from inside the project image, where `uv.lock` sits beside `tests/`; the ruff check skips there and only there, since `.pre-commit-config.yaml` is outside that build context |

## Defects found in the application under test

Discovered by probing the live API while writing assertions; kept as
`xfail(strict=True)` so the suite alerts when ParaBank fixes them.

Six defects (D-09, D-12, D-13, D-19, D-25, D-26) additionally carry a **`defect_proof`**
test that asserts the exploit as it behaves *today*, so the report shows a
passing, explicit demonstration rather than only an xfail. These are the one
place in the suite where a test asserts broken behavior, and they are a
deliberate maintenance trap: when ParaBank fixes the defect they go red while
the product got better. Their assertion messages say so ("D-NN may be FIXED …
delete this test"), and `-m "not ai_demo and not defect_proof"` deselects all of
them at once (the `not ai_demo` half must be repeated: a command-line `-m`
replaces the one in `addopts` instead of combining with it).
The application image is pinned by digest for the same reason — see
`docker-compose.yml`.

| ID | Defect | Evidence |
|----|--------|----------|
| D-01 | API and UI accept zero-amount transfers | `POST /services/bank/transfer?amount=0` → 200, "Successfully transferred $0" |
| D-02 | API accepts negative-amount transfers (money pump: drains the target account) | `POST /services/bank/transfer?amount=-10` → 200 |
| D-03 | API accepts transfers from an account to itself | `POST /services/bank/transfer` with equal ids → 200 |
| D-04 | Empty transfer amount surfaces as "An internal error has occurred" instead of validation | The `p#amount.errors` messages ("The amount cannot be empty.") exist in the DOM but are never displayed; the form posts and the server returns 500 |
| D-05 | API accepts negative deposit amounts — money vanishes from the account | `POST /services/bank/deposit?amount=-50` → 200 |
| D-06 | Withdrawal exceeding the balance is accepted — no overdraft protection | `POST /services/bank/withdraw` with amount ≫ balance → 200, balance goes deep negative |
| D-07 | API accepts negative withdrawal amounts — effectively credits the account | `POST /services/bank/withdraw?amount=-50` → 200 |
| D-08 | Bill pay returns HTTP 500 whenever the payee payload includes a `routingNumber` key at all, regardless of its value (even `""`); omitting the field entirely succeeds. Corrected from an earlier, imprecise "always 500" description (found by exploratory testing — the original probe always happened to include `routingNumber`) | `POST /services/bank/billpay` with a payee payload containing `routingNumber` (any value) → 500; the identical payload with the key omitted → 200 |
| **D-09** | **Critical — the REST API has no authentication or authorization (IDOR).** An unauthenticated caller can read any customer's account and PII and withdraw their money by supplying the id in the URL; ids are sequential, so they are trivially guessable | A raw client with no cookies/token: `GET /accounts/{victim_id}` → 200 (full balance); `GET /customers/{victim_id}` → 200 (name, address, SSN, phone); `POST /withdraw?accountId={victim_id}&amount=100` → 200, "Successfully withdrew" |
| D-10 | `updateCustomer` always returns HTTP 500 and never persists changes | `POST /services/bank/customers/update/{id}` with valid fields → 500; a subsequent `GET /customers/{id}` shows the old values |
| D-11 | `getPositionHistory` returns HTTP 400 "Could not find position" even for a position that exists and is returned by `GET /positions/{id}` | `GET /positions/{id}/{start}/{end}` for a just-bought position → 400 |
| **D-12** | **Critical — money creation. `buyPosition` accepts a negative share count and credits the account instead of debiting it**, with no floor on the quantity | `POST /services/bank/customers/{id}/buyPosition?shares=-100&pricePerShare=10.00` → 200, account balance **+$1000.00** (reproduced again at -1,000,000 shares × $50 → **+$50,000,000.00**) |
| **D-13** | **Critical — money creation, repeatable without limit. `sellPosition` accepts selling more shares than a position holds**, with no ownership/quantity check at all; the position's share count goes negative with no floor. `shares` is bound to a 32-bit Java `int`, so a single call caps out at `Integer.MAX_VALUE` — not infinite per call, but nothing stops calling it again | Bought 10 shares, sold 999,999,999 → 200, balance **+$9,999,999,990.00**; sold `2,147,483,647` (`Integer.MAX_VALUE`) → 200, balance **+$21,474,836,470.00**; `2,147,483,648` → 404 (fails to bind as `int`, the actual ceiling per call) |
| D-14 | `deposit`, `withdraw` and `transfer` answer HTTP 500 on an `amount` that is **missing entirely or empty**, instead of a validation error. The empty case was found by `ai/api_fuzzer.py`: this plan previously claimed it was handled correctly, and the test that supposedly proved it asserted only `status >= 400`, which a 500 satisfies | `POST /services/bank/deposit?accountId=<id>` with no `amount`, and with `amount=`, both → 500 + ParaBank's HTML error page; same on `withdraw` and `transfer`, 2/2 runs against a freshly restarted container |
| D-15 | `deposit` accepts scientific-notation amounts with no validation and echoes them back unformatted | `POST /services/bank/deposit?amount=1e5` → 200, `"Successfully deposited $1E+5 to account #..."` |
| D-16 | Registration silently fails when `street`/`state` exceeds ~40 characters (a DB column-length violation), but reports the misleading error "This username already exists" instead of a field-length message — even for a guaranteed-fresh username | `POST /register.htm` with a 60-char `street` and a UUID-fresh username → registration fails, error text is "This username already exists."; the username was never actually taken (confirmed via login attempt) |
| D-17 | Registration does not enforce `phoneNumber` as a required field, unlike `state`/`zipCode`/`ssn` | `POST /register.htm` with `phoneNumber=""` and all other fields valid → registration succeeds |
| **D-18** | **Critical — the web admin page has no authentication**, including a "Clean" control that wipes the entire database (`POST /db.htm?action=CLEAN`). Not exploited (would destroy the shared local instance for every concurrent user); only the anonymous page-read was verified | `GET /parabank/admin.htm` with a client sending zero cookies → 200, page HTML includes the Database section with `INIT`/`CLEAN` buttons posting to `db.htm` |
| D-19 | `requestLoan` accepts a negative down payment, approves the loan, and credits `\|downPayment\|` to the account instead of debiting it | `POST /services/bank/requestLoan?amount=1000&downPayment=-500` → 200, `approved: true`, account balance **+$500.00** |
| D-20 | `requestLoan` with `amount=0` leaks a raw Java exception message instead of a validation error | `POST /services/bank/requestLoan?amount=0&downPayment=0` → 400, body is literally `"/ by zero"` (reproduced 3/3 times). **Reproduces on a freshly started container.** Once ParaBank's CXF fault chain degrades (it logs "An unexpected error occurred during error handling"), every fault is sanitised to "Fault occurred while processing." and the leak stops — the strict xfail then XPASSes, which is the defect not occurring rather than a broken test. CI starts a fresh container per run; restart the app if you hit it locally |
| D-21 | `billpay` accepts a negative amount and credits the account instead of debiting it — same unvalidated-sign pattern as D-02/D-05/D-07/D-12/D-13/D-19 | `POST /services/bank/billpay?amount=-50.00` with a valid payee (no `routingNumber`) → 200, account balance **+$50.00** instead of -$50.00 |
| **D-22** | **A protected page answers an unauthenticated request with HTTP 500 and ParaBank's internal-error page** instead of redirecting to the login form. Affects `overview.htm`, `billpay.htm`, `requestloan.htm` and `transfer.htm`; `activity.htm` answers 400. Reached by logging out and reopening the page, or by any cookieless client | `GET /parabank/overview.htm` with no session → 500, body contains "An internal error has occurred and has been logged." The shared template still renders the login form in a side panel, so "the username field is visible" does **not** distinguish this from the login page — the error text does |
| D-23 | The Request Loan form answers an **empty** amount with the internal-error panel instead of a field validation message. Bill Pay, the sibling form, answers "The amount cannot be empty." for exactly this input, so the expected behaviour is not in doubt | Apply Now with `amount=""` → `#requestLoanError` is revealed; the API equivalent returns 400 `Cannot invoke "java.math.BigDecimal.compareTo(java..."` |
| D-24 | A down payment larger than the loan amount is **approved**: ParaBank debits the full down payment and opens a loan for the smaller amount, so the customer is worse off for borrowing. Found by replacing an assertion that accepted any non-5xx answer | `POST /services/bank/requestLoan?amount=100&downPayment=200` → 200, `approved: true`, 3/3. Source account -$200.00, new LOAN account $100.00 — net **-$100.00** to the customer |
| **D-25** | **Concurrent registrations of distinct, unused usernames are rejected as duplicates.** Found by running the suite under `pytest-xdist` | 4 concurrent `POST /parabank/register.htm`, every username freshly generated: 1–2 succeed, the rest return HTTP 200 with "This username already exists." Reproduced 32/32 probe runs at concurrency ≥ 3; 6/6 sequentially. Proof the collision is false: re-submitting a rejected username on its own succeeds, so it was never created |
| **D-26** | **Concurrent `createAccount` calls fail with HTTP 400 "Could not create new account".** Global write contention, not a per-customer lock: it happens equally when the six callers are six different customers | 6 concurrent `POST /services/bank/createAccount` → 3 succeed, 3 return 400; the same six run sequentially succeed 6/6. Repeating the identical request on its own immediately afterwards succeeds |


## AI in the suite, and where it is not allowed

One rule decides the whole design: **the model proposes, the checked-in code
decides.** An LLM answers differently on two runs, so nothing that gates CI may
depend on one. Every AI feature is therefore either opt-in, or paired with a
deterministic layer that holds the ground on its own.

| Feature | What the model does | What decides |
|---------|---------------------|--------------|
| Failure triage (`ai/failure_analyzer.py`) | Diagnoses a failed test into the report | Nothing — it annotates, never votes |
| Self-healing locators (`ai/locator_healer.py`) | Suggests replacement selectors | Playwright: only a selector matching exactly one element is used |
| Error-message judge (`ai/message_judge.py`) | Judges whether a message leaks internals or is actionable | `SIGNATURES`, a list of fragments observed in real responses |
| API fuzzer (`ai/api_fuzzer.py`) | Proposes parameter combinations | Fixed rules: a 5xx on client input, or a leak — never the model |

### Error-message judge

`tests/api/test_error_messages.py` sweeps the endpoints that produce a
user-facing error and asserts none of them leaks implementation detail. It is a
general property, so an endpoint that *starts* leaking is caught without anyone
writing a test for it first; the three documented leaks (D-10, D-20, D-23) are
strict xfails. The gate runs everywhere and needs no model.

`tests/ai/test_message_judge_lane.py` (marker `ai_judge`, needs Ollama, never in
CI) asks the two questions a substring list cannot answer: is there a leak the
list has not seen, and could a customer actually act on this message. A leak
found there is promoted into `SIGNATURES`, after which everyone catches it
deterministically with no model running. Verified falsifiable: removing
`"/ by zero"` from the list makes the lane fail on the loan endpoint with
"add the fragment".

### API fuzzer

Several defects here (D-14..D-16, D-24) were found by hand, poking endpoints
with awkward values. That work does not survive as an asset — nobody remembers
what was tried. `ai/api_fuzzer.py` keeps the judgement and automates the
tedium: the model proposes combinations, a plain runner executes them, and
fixed rules classify the answers. Findings are candidates for a human to
confirm and promote to a strict-xfail test with a defect id.

Its first version reported 18 findings across three endpoints, and all but two
were its own fault: ParaBank's error handling degrades once a few faults pass
through it, after which *every* response is the same HTML 500, and cases were
being blamed for damage earlier ones had done. The tool now re-checks a
known-good call between cases and stops the sweep when the server no longer
recovers. On the corrected version it rediscovered D-14 independently — and
widened it, by reporting the empty-`amount` case that this plan had recorded as
working.

## Parallelism, and why the suite runs sequentially

The suite is built to run in parallel: every `pytest-xdist` worker registers its
own customer and opens its own accounts, so workers share no state by
construction. The application under test is the constraint, not the harness.

Running `-m "not ai_demo"` under `-n 4` surfaced two previously unknown defects
— **D-25** (registration) and **D-26** (account opening) — and then kept
producing scattered, non-repeating failures across unrelated modules: strict
xfails flipping to XPASS, malformed JSON bodies, 400s on requests that succeed
when repeated. Every one of them traces to ParaBank's write paths failing under
concurrent load. Six runs at `-n 2` were green 4 times; `-n 4`, 3 of 6.

So parallelism is kept as a **defect-hunting mode, not a speed mode**, and CI
runs sequentially:

* Sequential is already fast — the full suite is ~9s, against ~6s at `-n 2`.
  Three seconds do not buy a flaky gate.
* Test-data setup retries past D-25 and D-26 regardless
  (`parabank_api.register_customer` and `parabank_api.open_account`), because
  robust provisioning is worth having in either mode.
* The two defects are asserted by strict xfails plus `defect_proof` tests, so
  they are documented findings rather than a footnote about flakiness.

Concurrency probes repeat the burst up to three times
(`utils/concurrency.burst_until_failure`): a single burst reproduces D-25/D-26
with high probability but not certainty, and under a saturated server the
probability *falls*, because queuing serialises the requests. Requiring three
consecutive clean bursts before a strict xfail reports "fixed" is what keeps
those tests from flapping.

Against an application that tolerated concurrent writes, the same suite would
scale on workers with no change beyond dropping the two retries.
