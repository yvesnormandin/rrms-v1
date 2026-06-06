# RRMS Demo Agent (`rrms-v1`)

A telephone customer-service demo agent for **Rapid Response Monitoring Services** (alarm monitoring), built on **Google CX Agent Studio** (Customer Engagement Suite) with [cxas-scrapi](https://github.com/GoogleCloudPlatform/cxas-scrapi). Voice-first (`gemini-3.1-flash-live`), publicly callable, fully mocked customer data.

## Demo scenarios

**1. False alarm cancellation (8 AM rush hour)** — a store manager accidentally trips the alarm while opening:

> **Agent:** Rapid Response Monitoring. How can I help you today?
> **Caller:** Hi, I just opened my store and accidentally set off the alarm. Can you cancel it?
> **Agent:** Of course. Could you please provide the passcode for verification?
> **Caller:** Sunset.
> **Agent:** Thanks, verified. The alarm at Johnson Verizon Store has been canceled. Police were not dispatched.

**2. Multi-location "on test / no action"** — a manager of several branches puts one on test:

> **Caller:** I need to put the Dallas branch on testing for one hour.
> **Agent:** I see you manage multiple branches. Did you mean the Dallas branch at 123 Main Street?
> **Caller:** Yes. … Bluebird.
> **Agent:** Thanks, verified. The Dallas branch account ending in 345 is now on test for one hour. Would you like me to send a confirmation text as well?

Edge cases covered: wrong passcode (2 retries → operator transfer), unknown caller, no active alarm, missing/out-of-range test duration, SMS declined, and a site where police **were** dispatched.

## How it works

- **Single `root_agent`** with a taskflow instruction: resolve account → spoken-passcode gate → action → grounded confirmation → spoken closing + `end_session`.
- **Five Python tools over in-code mock data.** `_MOCK_ACCOUNTS` lives only in `lookup_accounts_by_caller`, which distributes the caller's records to the other tools via session state (`_caller_accounts` / `_resolved_account`). Passcodes never appear in tool returns, so the model never sees them.
- **Voice-hardened**: passcode matching is fuzzy (Levenshtein ≤ 1 after lowercase/accent/whitespace/punctuation normalization) because ASR lowercases and word-splits spoken words ("Bluebird" → "Blue Bird"); dispatch status is data-driven; a callback guarantees a spoken farewell before hangup.
- **Publicly callable via two GTP phone numbers.** Real callers' CLIDs can't key the mock data, so each Google Telephony Platform number is wired to a *variant app* whose `before_agent` callback hard-codes one demo CLID — callers to one number become the single-site store, callers to the other become the multi-branch manager. Eval-supplied `caller_phone` always wins, so one eval suite covers canonical and both variants.

```
cxas_app/rrms-v1/  ──lint──► push to canonical app ──► evals
        │
        └── ./deploy-variants.sh  (substitutes one constant per variant)
                ├── rrms-demo-store      ◄── GTP number 1 (CLID +1 512 555 0142)
                └── rrms-demo-multisite  ◄── GTP number 2 (CLID +1 214 555 0199)
```

## Evaluation

Built test-first with four suites (run on the platform against the deployed app):

| Suite | Count | Status (latest) |
|---|---|---|
| Goldens (turn-by-turn scripted) | 9 conversations | 27/27 (100%, text channel) |
| Simulations (LLM-driven caller) | 5 scenarios | 15/15 |
| Tool tests | 19 | 19/19 |
| Callback tests (pytest) | 25 | 25/25 |

Audio-channel goldens settle at ~90–96% run-to-run (ASR/judge noise); the same code scores 100% on the text channel. The full build/eval/fix history — including the live-model and ASR bugs the eval suite caught — is in [`experiment_log.md`](experiment_log.md), and the living design doc with pass-rate history is [`tdd.md`](tdd.md).

## Repository layout

```
cxas_app/rrms-v1/        Agent source (instruction, tools, callbacks, app.json)
evals/                   Goldens, simulations, tool tests, callback tests
deploy-variants.sh/.json GTP variant deployment (regenerates variants from canonical)
tdd.md                   Living technical design doc (architecture, coverage map, pass rates)
experiment_log.md        Every eval iteration: results, triage, fixes
sources/                 Original requirements brief + sample calls
eval-reports/            Run artifacts (reports, snapshots, triage JSONs)
CLAUDE.md                Working notes for AI-assisted development
```

## Working on it

Requires the cxas-scrapi workspace (venv + `cxas` CLI) one directory up — see [`CLAUDE.md`](CLAUDE.md) for the full command reference, the eval workflow, and the platform gotchas. The short version:

```bash
cxas lint --app-dir cxas_app/rrms-v1                    # zero warnings policy
cxas push --app-dir cxas_app/rrms-v1 --to <canonical>   # evals run against the platform
# run goldens/sims/tool/callback tests (see CLAUDE.md)
./deploy-variants.sh                                     # release to the phone numbers
```

Mock customers (passcodes are demo fixtures, intentionally public):

| Caller phone | Customer | Passcode | Notes |
|---|---|---|---|
| +1 512 555 0142 | Johnson Verizon Store (single site) | Sunset | active alarm, not dispatched |
| +1 214 555 0199 | Dallas / Fort Worth / Plano (multi-branch) | Bluebird / Maple / Harbor | Plano: alarm with police **dispatched** |
