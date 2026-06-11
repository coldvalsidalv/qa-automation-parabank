# AI Discovery — exploring the app before writing tests

Before any test code was written, the application was explored with an LLM
driving a real browser through [Playwright MCP](https://github.com/microsoft/playwright-mcp).
The output of that session became the basis for [test_plan.md](test_plan.md).

## Setup

```bash
npm install -g @playwright/mcp
```

Claude Desktop / Claude Code MCP config:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

## Discovery prompt

```
Explore https://parabank.parasoft.com as a QA engineer.

Navigate through: registration, login, accounts overview,
transfer funds, bill pay, request loan, find transactions.

For each page produce:
## [Page Name]
### Critical UI elements (with likely selectors)
### Key user flows
### Test scenarios (positive + negative + boundary)
### Risks / observations
```

## What came out of it

- The page inventory and selector candidates for the page objects in `pages/`
- The scenario list that was reviewed, pruned, and formalized in `docs/test_plan.md`
- Early observations that led to probing the transfer API and finding defects D-01..D-03
