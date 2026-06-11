# Test Plan — ParaBank

Scope: critical user paths of the ParaBank demo bank (UI) plus the full REST
API surface. Each scenario maps to an implemented automated test; known
defects of the application under test are `xfail(strict=True)`.

## UI

| ID | Scenario | Test |
|----|----------|------|
| TC-01 | Login page renders with the login form | `tests/ui/test_login.py::test_login_page_loads` |
| TC-02 | Login with valid credentials lands on Accounts Overview | `tests/ui/test_login.py::test_login_with_valid_credentials` |
| TC-03 | Login with invalid credentials shows an error | `tests/ui/test_login.py::test_login_with_invalid_credentials_shows_error` |
| TC-04 | Login with empty credentials shows an error | `tests/ui/test_login.py::test_login_with_empty_credentials_shows_error` |
| TC-05 | Overview lists the customer's accounts | `tests/ui/test_overview.py::test_overview_shows_at_least_one_account` |
| TC-06 | Account link opens Account Activity | `tests/ui/test_overview.py::test_overview_account_link_opens_account_activity` |
| TC-07 | Account Activity shows a numeric balance | `tests/ui/test_account_activity.py::test_account_shows_numeric_balance` |
| TC-08 | Transfer between own accounts completes | `tests/ui/test_transfer.py::test_transfer_valid_amount_completes` |
| TC-09 | Transfer with empty amount does not move money | `tests/ui/test_transfer.py::test_transfer_empty_amount_does_not_complete` |
| TC-10 | Transfer with empty amount shows a validation message | `tests/ui/test_transfer.py::test_transfer_empty_amount_shows_validation_message` (**xfail — D-04**) |
| TC-11 | Transfer with zero amount is rejected | `tests/ui/test_transfer.py::test_transfer_zero_amount_is_rejected` (**xfail — D-01**) |

## API

One file per resource under `tests/api/`; scenario names map 1:1 to test
function names.

| Area | File | Coverage |
|------|------|----------|
| Auth | `test_accounts_api.py` | login returns the customer object; invalid credentials → 400 |
| Accounts | `test_accounts_api.py` | account list non-empty; field types; get-by-id consistency; unknown id → error; open CHECKING/SAVINGS account; new account appears in the list |
| Customer profile | `test_customer_api.py` | profile fields; nested address; unknown id → error |
| Deposit / withdraw | `test_deposit_withdraw_api.py` | deposit/withdraw move the balance by the exact amount; success messages; unknown account → error; negative deposit (**xfail — D-05**); overdraft (**xfail — D-06**); negative withdrawal (**xfail — D-07**) |
| Transfers | `test_transfer_api.py` | transfer succeeds and moves money; missing amount → error; zero amount (**xfail — D-01**); negative amount (**xfail — D-02**); same account (**xfail — D-03**) |
| Transactions | `test_transactions_api.py` | list; field types; get-by-id; unknown id → error; filters by amount, date range, single date, month+type — both matching and empty cases |
| Loans | `test_loans_api.py` | loan approved for a solvent customer; response fields; LOAN account created; down payment > amount handled |
| Bill pay | `test_billpay_api.py` | valid payment succeeds (**xfail — D-08**) |
| Positions | `test_positions_api.py` | buy; list contains bought position; get-by-id; partial sell reduces shares; unknown id → error |

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
| D-08 | Bill pay is broken: the endpoint always returns HTTP 500 | `POST /services/bank/billpay` with a valid payee payload → 500 |
