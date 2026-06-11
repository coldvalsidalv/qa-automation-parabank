# Smoke Test Plan — ParaBank

Scope: critical user paths of the ParaBank demo bank (UI + REST API).
Each scenario maps to an implemented automated test.

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

| ID | Scenario | Test |
|----|----------|------|
| TC-20 | Login returns the customer object | `tests/api/test_accounts_api.py::test_login_returns_customer` |
| TC-21 | Login with bad credentials returns 400 | `tests/api/test_accounts_api.py::test_login_with_invalid_credentials_returns_400` |
| TC-22 | Accounts match the JSON schema | `tests/api/test_accounts_api.py::test_accounts_match_schema` |
| TC-23 | Valid transfer succeeds and moves money | `tests/api/test_transfer_api.py::test_transfer_moves_money_between_balances` |
| TC-24 | Zero-amount transfer is rejected | `tests/api/test_transfer_api.py::test_transfer_zero_amount_is_rejected` (**xfail — D-01**) |
| TC-25 | Negative-amount transfer is rejected | `tests/api/test_transfer_api.py::test_transfer_negative_amount_is_rejected` (**xfail — D-02**) |
| TC-26 | Same-account transfer is rejected | `tests/api/test_transfer_api.py::test_transfer_to_same_account_is_rejected` (**xfail — D-03**) |

## Defects found in the application under test

Discovered by probing the live API while writing assertions; kept as
`xfail(strict=True)` so the suite alerts when ParaBank fixes them.

| ID | Defect | Evidence |
|----|--------|----------|
| D-01 | API and UI accept zero-amount transfers | `POST /services/bank/transfer?amount=0` → 200, "Successfully transferred $0" |
| D-02 | API accepts negative-amount transfers (money pump: drains the target account) | `POST /services/bank/transfer?amount=-10` → 200 |
| D-03 | API accepts transfers from an account to itself | `POST /services/bank/transfer` with equal ids → 200 |
| D-04 | Empty transfer amount surfaces as "An internal error has occurred" instead of validation | The `p#amount.errors` messages ("The amount cannot be empty.") exist in the DOM but are never displayed; the form posts and the server returns 500 |
