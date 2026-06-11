# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚀 Start here: `RUNBOOK.md`

**At the start of every session, read [`RUNBOOK.md`](RUNBOOK.md)** — the operational
quick-start: session setup, app/infra IDs, the `cxas` CLI, every `.agents` Python script
with examples, eval recipes, gotchas, and current project state. It's the fastest way to be
up and running.

**At the END of every session, update `RUNBOOK.md`** (see its §9 "End-of-session ritual"):
refresh current state + latest scores, add any new gotcha/recipe, bump the date. Keeping it
current is what lets the next session start clean.

## What this is

A CX Agent Studio (GECX/CES) voice demo agent for Rapid Response Monitoring Services: telephone callers cancel false alarms or place branches "on test", gated by a spoken passcode. All customer data is mocked in-code. Built and evaluated with [cxas-scrapi](https://github.com/GoogleCloudPlatform/cxas-scrapi) via the `cxas-agent-foundry` skill, whose workflow (lint → push → eval → triage → iterate) governs all changes here.

**The workspace root is the PARENT directory** (`../`, e.g. `~/dev/cxas-scrapi/`): the Python venv (`../.venv/`), the foundry skill (`../.agents/skills/cxas-agent-foundry/`), and the `.active-project` pointer live there, not in this repo. Scripts resolve this project via `GECX_PROJECT=rrms-v1`.

## Deployed apps (yves-normandin-project / us)

| App | ID | Role |
|---|---|---|
| `rrms-v1` | `ec021a75-b0a0-4d88-90d9-1d39556bee7a` | **Canonical** — the only app you develop and eval against |
| `rrms-demo-store` | `3f88fc77-6616-42cb-b3ec-72ba75369fb3` | GTP variant, hard-coded CLID `+15125550142` (UC1 store) |
| `rrms-demo-multisite` | `1a32623a-96d0-43f3-bf91-7f533a9deb58` | GTP variant, hard-coded CLID `+12145550199` (UC2 multi-branch) |

**Never edit or push the variant apps directly.** They are build artifacts regenerated from canonical by `./deploy-variants.sh` (only `DEFAULT_CALLER_PHONE` in the before_agent callback + app identity differ; config in `deploy-variants.json`, app IDs auto-recorded).

## The change cycle

```bash
VENV=../.venv/bin            # activate: source ../.venv/bin/activate
APP=projects/yves-normandin-project/locations/us/apps/ec021a75-b0a0-4d88-90d9-1d39556bee7a

# 1. Edit cxas_app/rrms-v1/ ; then lint (zero errors AND warnings expected)
cxas lint --app-dir cxas_app/rrms-v1

# 2. Push to canonical (evals run against the PLATFORM, not local files)
cxas push --app-dir cxas_app/rrms-v1 --to $APP \
  --project-id yves-normandin-project --location us

# 3. Evals (see below), then release to the phone numbers:
./deploy-variants.sh          # --dry-run to preview
```

## Running evals

Validation strategy: **text channel first** (fast/cheap, same `gemini-3.1-flash-live` model), audio channel before releases. The runner refuses `--channel text` unless `gecx-config.json` has `modality`/`default_channel` = `text` — flip both temporarily, run, flip back to `audio` (keep `model` as-is; the trio lives in `gecx-config.json`).

```bash
cd .. && source .venv/bin/activate
SCRIPTS=.agents/skills/cxas-agent-foundry/scripts

# Goldens: sync local YAML to platform, trigger, then score
GECX_PROJECT=rrms-v1 python $SCRIPTS/scrapi-eval-runner.py push-goldens --force-recreate
GECX_PROJECT=rrms-v1 python $SCRIPTS/scrapi-eval-runner.py run-goldens --channel text --runs 3
GECX_PROJECT=rrms-v1 python $SCRIPTS/scrapi-eval-runner.py results <run_id>   # NO --audio flag, ever

# Sims (LLM-driven caller; the only file the runner reads is evals/simulations/simulations.yaml)
GECX_PROJECT=rrms-v1 python $SCRIPTS/scrapi-sim-runner.py run --priority P1,P2 --parallel 1 --channel text --runs 3

# Tool tests — run via ToolEvals directly (the runner script's tool phase reports nothing)
GECX_PROJECT=rrms-v1 python -c "
from cxas_scrapi.evals.tool_evals import ToolEvals
te = ToolEvals(app_name='$APP')
te.run_tool_tests(te.load_tool_tests_from_dir('rrms-v1/evals/tool_tests'))"

# Callback tests — pytest does NOT auto-discover files named test.py; pass paths explicitly
python -m pytest rrms-v1/evals/callback_tests/tests/root_agent/*/*/test.py   # one invocation per file (module-name collision)
# After changing callback code: re-sync copies/symlinks
GECX_PROJECT=rrms-v1 python $SCRIPTS/sync-callbacks.py --from-local rrms-v1/cxas_app/rrms-v1/
```

The full pipeline (`run-and-report.py --message "..." --channel ... --runs 3 --priority P1,P2 --json-summary <path>`) snapshots, runs everything, triages, and appends to `experiment_log.md`. Sims default to `--priority P0` — all sims here are P1/P2, so always pass `--priority P1,P2` or none run.

## Platform gotchas (each cost real debugging time)

- **Invalid model names are silently dropped on push** and the app falls back to the platform default. After changing `modelSettings.model`, pull to a temp dir and verify the field landed. Valid here: `gemini-3.1-flash-live`.
- **Never score audio runs with `results --audio`** — that flag uses goal+expectations scoring and returns a bogus 0%. Plain `results <run_id>` (platform `evaluation_status`) is the truth.
- **`cxas pull` creates an app-named subfolder INSIDE `--target-dir`.** Never pull into `cxas_app/rrms-v1/` — it nests a stale copy at `cxas_app/rrms-v1/rrms-v1/`. (The workspace copy of the foundry's `gate-check.py` was patched for this; `deploy-variants.sh` strips such artifacts defensively.)
- **When a previously-fixed golden failure reappears, suspect a stale platform copy** — `push-goldens --force-recreate` hard-resets; the diff-aware upsert can miss tool-arg changes.
- **ASR realities** (audio channel): spoken words arrive lowercased and compound words split ("Bluebird" → "Blue Bird"). Absorb in *tools* (verify_passcode normalizes + fuzzy-matches, Levenshtein ≤ 2), and in golden tool-args use `$matchType: ignore` for spoken values (passcodes) — regexes can't cover all ASR variants.
- **The live model parrots instruction phrasing into caller speech** — write guidelines so no sentence is speakable verbatim (a literal "Only state what the tool responses confirm" produced "the tool response confirms…" to a caller).
- **Goldens' first user turn is `"Hello"`, not `<event>welcome</event>`** — TTS reads the event tag aloud in audio mode.
- Expect **~90–96% on audio goldens run-to-run** (judge/ASR noise); text runs on the same code score 100%. Don't chase 2/3 audio failures with code changes — read the transcript first.

## Architecture

Single `root_agent` (`cxas_app/rrms-v1/agents/root_agent/`), six Python tools + system `end_session`. The flow backbone — greet (lookup at first turn; company-name greeting) → resolve request → passcode gate → action → confirm → offer further help → spoken closing + `end_session` — lives in `instruction.txt`'s taskflow; constraints there (passcode_gate, action_grounding, confirm_branch_before_action) are deliberately load-bearing for the evals.

**Language switching (EN ↔ ES):** `set_language` records the active language in `_language` state, but ONLY on an explicit caller request (the `language_switching` guideline is the load-bearing rule — a foreign greeting/word/passcode is NOT a switch request; the live model needed the explicit "Hola! Can you cancel my alarm?" non-example to stop auto-switching). The conversation always starts in English. `enable_multilingual_support` is intentionally OFF in `languageSettings` — it triggers the platform's pre-built multilingual auto-handling, the opposite of the explicit-only requirement. Spanish audio needs `es-US` in `languageSettings.supportedLanguageCodes` BEFORE it can appear in `audioProcessingConfig.synthesizeSpeechConfigs` (push 400s otherwise).

**Session-state data flow (single source of truth):**

```
caller_phone  ← eval session_parameters  OR  before_agent callback default (GTP)
   │
lookup_accounts_by_caller       ← _MOCK_ACCOUNTS lives ONLY here; edit mock data only here
   ├─ writes _caller_accounts   (full records incl. passcode/dispatch_status; never in tool returns)
   └─ writes _resolved_account  (single-account callers)
   │
verify_passcode                 ← reads _caller_accounts; fuzzy match (Levenshtein ≤ 2 after
   │                              lowercase/NFKD-accent/whitespace/punctuation normalization);
   └─ writes _resolved_account with passcode_verified=true + dispatch_status
   │
cancel_alarm / put_account_on_test / send_confirmation_sms
                                ← read _resolved_account only; enforce the passcode gate
                                  defensively; dispatch_status is data-driven (Plano fixture
                                  is "dispatched" to exercise that branch)
```

**Callbacks** (`agents/root_agent/*/python_code.py`): `before_agent` defaults `caller_phone` only when the session has none (live GTP callers; eval session params always win — this is what makes one eval suite valid for canonical and both variants); `after_model` guarantees a spoken farewell before `end_session`, choosing the farewell language from `_language` (English/Spanish, default English).

**Evals** (`evals/`): 11 goldens (bundled `goldens/goldens.yaml`; incl. `language_switch_to_spanish_on_request` and the negative `no_language_autoswitch_without_request`), 6 sims (`simulations/simulations.yaml`), 24 tool tests (`tool_tests/tool_tests.yaml`, state injected via `variables:` as JSON strings; run via ToolEvals directly — the in-process pipeline under-counts these), 29 callback test cases (`callback_tests/tests/<agent>/<type>/<base>/test.py` + synced copies/symlinks under `callback_tests/agents/`). `caller_phone` is the only session parameter evals may set; `_caller_accounts`/`_resolved_account`/`_language` are tool-derived (tool tests excepted).

## Project documents

- `tdd.md` — living design doc: architecture, coverage map, **pass-rate history**, changelog. Update it when design changes; update evals to match.
- `experiment_log.md` — per-iteration record of every eval run, triage diagnosis, and fix. **Check it before proposing a fix** — repeated-approach regressions are logged here.
- `deploy-variants.json` — variant registry (names, CLIDs, app IDs).
- `sources/rrms-demo-brief.md` — the original requirements brief and verbatim sample calls (the UC1/UC2 goldens mirror them).
