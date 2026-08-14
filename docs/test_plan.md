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

## API

One file per resource under `python/tests/api/`; scenario names map 1:1 to test
function names.

| Area | File | Coverage |
|------|------|----------|
| Auth | `test_accounts_api.py` | login returns the customer object; invalid credentials → 400 |
| Accounts | `test_accounts_api.py` | account list non-empty; field types; get-by-id consistency; unknown id → error; open CHECKING/SAVINGS account; new account appears in the list |
| Customer profile | `test_customer_api.py` | profile fields; nested address; unknown id → error |
| Deposit / withdraw | `test_deposit_withdraw_api.py` | deposit/withdraw move the balance by the exact amount; success messages; unknown account → error; negative deposit (**xfail — D-05**); overdraft (**xfail — D-06**); negative withdrawal (**xfail — D-07**); missing amount param → 500 (**xfail — D-14**, both endpoints); scientific-notation amount accepted (**xfail — D-15**) |
| Transfers | `test_transfer_api.py` | transfer succeeds and moves money; empty amount → error; zero amount (**xfail — D-01**); negative amount (**xfail — D-02**); same account (**xfail — D-03**); missing amount param → 500 (**xfail — D-14**) |
| Transactions | `test_transactions_api.py` | list; field types; get-by-id; unknown id → error; filters by amount, date range, single date, month+type — both matching and empty cases |
| Loans | `test_loans_api.py` | loan approved for a solvent customer; response fields; LOAN account created; down payment > amount handled; negative down payment (**xfail — D-19**, + live proof); zero amount leaks internal error (**xfail — D-20**) |
| Bill pay | `test_billpay_api.py` | valid payment without `routingNumber` succeeds; with `routingNumber` present (**xfail — D-08**) |
| Positions | `test_positions_api.py` | buy; list contains bought position; get-by-id; partial sell reduces shares; unknown id → error; negative share count on buy (**xfail — D-12**, + live proof); overselling a position (**xfail — D-13**, + live proof) |
| Position history | `test_position_history_api.py` | history for a valid position (**xfail — D-11**); unknown id → error |
| Update customer | `test_customer_update_api.py` | update succeeds (**xfail — D-10**); updated values visible via GET (**xfail — D-10**) |
| Registration | `test_registration_api.py` | valid registration succeeds; missing state/zip correctly rejected; missing phone (**xfail — D-17**); overlong street reports the wrong error (**xfail — D-16**) |
| Contracts | `test_contracts_api.py` | account, customer, transaction, position, loan response, and bill pay response each validated against their JSON Schema in `contracts/` |
| Security | `test_security_api.py` | unauthenticated read of a foreign account / customer PII / withdrawal must be rejected (**xfail — D-09**); live proof that money theft is currently possible; admin page reachable with no auth (**xfail — D-18**) |

## AI module (unit)

No browser, no server, no Ollama — these mock `ai.llm.complete`/`complete_json`
directly and run in every default suite invocation.

| Area | File | Coverage |
|------|------|----------|
| Failure triage | `test_failure_analyzer.py` | returns the LLM diagnosis; degrades to `"AI analysis unavailable: ..."` instead of raising when the LLM call fails (the AI_ANALYSIS graceful-degradation contract) |
| Test-case generation | `test_test_generator.py` | returns the parsed list; rejects a non-list LLM response with `ValueError` |

## Defects found in the application under test

Discovered by probing the live API while writing assertions; kept as
`xfail(strict=True)` so the suite alerts when ParaBank fixes them.

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
| D-14 | `deposit`/`withdraw`/`transfer` return HTTP 500 when the `amount` parameter is missing entirely (distinct from `amount=""`, which is already handled correctly) | `POST /services/bank/deposit?accountId={id}` with no `amount` key at all → 500; same for `/withdraw` and `/transfer` |
| D-15 | `deposit` accepts scientific-notation amounts with no validation and echoes them back unformatted | `POST /services/bank/deposit?amount=1e5` → 200, `"Successfully deposited $1E+5 to account #..."` |
| D-16 | Registration silently fails when `street`/`state` exceeds ~40 characters (a DB column-length violation), but reports the misleading error "This username already exists" instead of a field-length message — even for a guaranteed-fresh username | `POST /register.htm` with a 60-char `street` and a UUID-fresh username → registration fails, error text is "This username already exists."; the username was never actually taken (confirmed via login attempt) |
| D-17 | Registration does not enforce `phoneNumber` as a required field, unlike `state`/`zipCode`/`ssn` | `POST /register.htm` with `phoneNumber=""` and all other fields valid → registration succeeds |
| **D-18** | **Critical — the web admin page has no authentication**, including a "Clean" control that wipes the entire database (`POST /db.htm?action=CLEAN`). Not exploited (would destroy the shared local instance for every concurrent user); only the anonymous page-read was verified | `GET /parabank/admin.htm` with a client sending zero cookies → 200, page HTML includes the Database section with `INIT`/`CLEAN` buttons posting to `db.htm` |
| D-19 | `requestLoan` accepts a negative down payment, approves the loan, and credits `\|downPayment\|` to the account instead of debiting it | `POST /services/bank/requestLoan?amount=1000&downPayment=-500` → 200, `approved: true`, account balance **+$500.00** |
| D-20 | `requestLoan` with `amount=0` leaks a raw Java exception message instead of a validation error | `POST /services/bank/requestLoan?amount=0&downPayment=0` → 400, body is literally `"/ by zero"` (reproduced 3/3 times) |
