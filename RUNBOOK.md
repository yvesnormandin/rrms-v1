# RRMS-v1 Session Runbook

Operational quick-start for the `rrms-v1` CXAS voice agent. Read this + `CLAUDE.md`
at the start of a session and you're up to speed. **Update this file at the end of
every session** (see "End-of-session ritual" at the bottom).

Last updated: 2026-06-12 (audio tool-drop fixed via deterministic emission — §7 FIX gotcha, §8).

---

## 1. Session startup (paste this first)

```bash
cd /home/norman/dev/cxas-scrapi          # WORKSPACE ROOT (not the project dir)
source .venv/bin/activate                # venv lives at the workspace root
export GECX_PROJECT=rrms-v1              # every .agents script resolves the project from this
SCRIPTS=.agents/skills/cxas-agent-foundry/scripts
APP=projects/yves-normandin-project/locations/us/apps/ec021a75-b0a0-4d88-90d9-1d39556bee7a
```

- The **workspace root** is `/home/norman/dev/cxas-scrapi` — it holds `.venv/`,
  `.agents/skills/cxas-agent-foundry/`, and `.active-project`.
- The **project** is `rrms-v1/` (the git repo, `CLAUDE.md`, `cxas_app/`, `evals/`).
  All script paths below are relative to the workspace root; app/eval paths start `rrms-v1/`.
- Most scripts need `GECX_PROJECT=rrms-v1` in the env (or inline: `GECX_PROJECT=rrms-v1 python …`).

---

## 2. Apps, project, infra

| Thing | Value |
|---|---|
| GCP project / location | `yves-normandin-project` / `us` |
| **Canonical app** (develop + eval here) | `ec021a75-b0a0-4d88-90d9-1d39556bee7a` |
| Variant `rrms-demo-store` (CLID +15125550142, UC1) | `3f88fc77-6616-42cb-b3ec-72ba75369fb3` |
| Variant `rrms-demo-multisite` (CLID +12145550199, UC2) | `1a32623a-96d0-43f3-bf91-7f533a9deb58` |
| Model | `gemini-3.1-flash-live` |
| Eval audio bucket | `gs://yves-normandin-cxas-evals` (in `environment.json`) |
| Live audio-recording bucket (variants) | `gs://rrms-demo-audio-recordings-2026-06-08` |
| BigQuery export (variants) | `yves-normandin-project` / dataset `conversational_insights` |
| Git remote | `git@github.com:yvesnormandin/rrms-v1.git` (branch `main`) |

**Never edit/push the variant apps directly** — they are regenerated from canonical by
`./deploy-variants.sh`. Develop only against canonical.

---

## 3. `cxas` CLI

```bash
# Lint — but prefer the lint-fixer sub-agent (keeps verbose output off the main thread)
cxas lint --app-dir rrms-v1/cxas_app/rrms-v1

# Push canonical (evals run against the PLATFORM, not local files)
cxas push --app-dir rrms-v1/cxas_app/rrms-v1 --to $APP \
  --project-id yves-normandin-project --location us

# Pull platform -> local. NEVER pull into cxas_app/rrms-v1 (it nests a stale
# cxas_app/rrms-v1/rrms-v1/). Pull into a temp dir, or cxas_app/ for a fresh copy.
cxas pull $APP --project-id yves-normandin-project --location us --target-dir /tmp/pull-check
```

---

## 4. The `.agents` Python scripts (what we actually use)

Run from the workspace root with `GECX_PROJECT=rrms-v1`. `S=.agents/skills/cxas-agent-foundry/scripts`.

| Script | Use it for | Example |
|---|---|---|
| `run-and-report.py` | **Full iteration**: snapshot → push goldens → run all 4 eval types → triage → iteration report. The everyday driver. | `python $S/run-and-report.py --message "what changed" --channel text --runs 3 --priority P0,P1,P2 --no-push-goldens --json-summary /tmp/sum.json` |
| `run-evals.py` | In-process run of goldens+tools+callbacks (+sims unless `--skip-sims`). Resolves the run name and waits; prints the `evaluationRuns/<id>`. | `python $S/run-evals.py --channel audio --runs 3 --priority P0,P1,P2 --skip-sims` |
| `scrapi-eval-runner.py` | Golden ops by subcommand: `status`, `push-goldens [--force-recreate]`, `run-goldens --channel --runs` (async — only triggers), `results <run_id>` (score; **NO `--audio` ever**), `report <run_id>` (writes a markdown report). | `python $S/scrapi-eval-runner.py results <run_id>` |
| `scrapi-sim-runner.py` | Simulations: `run --priority P1,P2 --channel text --runs 3 --parallel 1`. (All sims here are P1/P2 — pass the priorities or none run.) | `python $S/scrapi-sim-runner.py run --priority P1,P2 --channel text --runs 3` |
| `generate-iteration-report.py` | `snapshot` (before a change) and `report --message … [--json-summary …] [--auto-revert]` (after a run; appends to `experiment_log.md`, writes `eval-reports/iterations/iteration_N/`). | `python $S/generate-iteration-report.py snapshot` |
| `triage-results.py` | Diagnose failures. `--last N` aggregates across recent runs; `--eval NAME` or `--run-id ID` for one. | `python $S/triage-results.py --last 3` |
| `gate-check.py` | 6 build-verification gates against the deployed app. Run after structural changes (new tool/agent/callback) and before release. | `python $S/gate-check.py` |
| `capture-golden-transcripts.py` | Replay a golden against the live app to SEE the transcript (best triage tool). `--eval NAME` or `--all`, `--channel text|audio`. | `python $S/capture-golden-transcripts.py --eval plano_alarm_canceled_police_dispatched --channel text` |
| `sync-callbacks.py` | Sync callback code into `evals/callback_tests/agents/` + test.py symlinks. `--from-local <app_dir>` before push; bare (pull from platform) after. **Run after editing any callback.** | `python $S/sync-callbacks.py --from-local rrms-v1/cxas_app/rrms-v1/` |
| `inspect-app.py` | Quick "what's in here" architecture view (no verification). | `python $S/inspect-app.py` |
| `app-thresholds.py` | Show/tune scoring thresholds (similarity, hallucination, extra-tools). | `python $S/app-thresholds.py show` |
| `setup.sh`, `setup-project.py` | Cold-start only (venv + project bootstrap). Not needed in an existing session. |

**Lint is a sub-agent, not a script call.** Dispatch the `lint-fixer` agent
(`.agents/skills/cxas-agent-foundry/agents/lint-fixer.md`) with the app dir +
`lint-summary.json` output path; wait for `status: clean`. Never run `cxas lint` on the main thread.

---

## 5. Eval recipes

**Strategy:** validate on the **text** channel first (fast/cheap, same model), then **audio**
before a release.

### Channel flip (required for text runs)
The runners refuse `--channel text` unless `gecx-config.json` says so. Flip both fields,
run, flip back:
```bash
python3 -c "import json;c=json.load(open('rrms-v1/gecx-config.json'));c['modality']='text';c['default_channel']='text';json.dump(c,open('rrms-v1/gecx-config.json','w'),indent=2)"
# … run text evals …
python3 -c "import json;c=json.load(open('rrms-v1/gecx-config.json'));c['modality']='audio';c['default_channel']='audio';json.dump(c,open('rrms-v1/gecx-config.json','w'),indent=2)"
```
Keep `model` as `gemini-3.1-flash-live` throughout.

### Goldens (full pipeline, recommended)
```bash
python $S/run-and-report.py --message "…" --channel text --runs 3 --priority P0,P1,P2 \
  --no-push-goldens --json-summary /tmp/sum.json    # read /tmp/sum.json for the summary
# Edited golden YAMLs? Drop --no-push-goldens, or first: scrapi-eval-runner.py push-goldens --force-recreate
```

### Long runs in the background
Eval runs take minutes. Launch detached and poll:
```bash
nohup env GECX_PROJECT=rrms-v1 python $S/run-evals.py --channel audio --runs 3 \
  --priority P0,P1,P2 --skip-sims > /tmp/run.log 2>&1 &      # stdout is BUFFERED — empty while alive is normal
grep -o "evaluationRuns/[a-f0-9-]*" /tmp/run.log              # the run id, once it appears
python $S/scrapi-eval-runner.py results <run_id>             # score (NO --audio)
```

### `run-goldens` is async — resolving the run id
`scrapi-eval-runner.py run-goldens` only triggers and prints an `operations/…` name, not a
run id. Resolve the run id from the operation metadata:
```python
from google.cloud.ces_v1beta.services.agent_service import AgentServiceClient  # (for get_app, below)
from google.cloud.ces_v1beta.types import RunEvaluationOperationMetadata
# poll: ops = ev.client.transport.operations_client; op = ops.get_operation(name="projects/…/operations/…")
# meta = RunEvaluationOperationMetadata(); meta._pb.ParseFromString(op.metadata.value); meta.evaluation_run
```
Easier: use `run-evals.py` (in-process; it resolves + prints the run name in the log).

### Tool tests — run directly (the pipeline under-counts them)
```bash
GECX_PROJECT=rrms-v1 python -c "
from cxas_scrapi.evals.tool_evals import ToolEvals
te = ToolEvals(app_name='$APP')
te.run_tool_tests(te.load_tool_tests_from_dir('rrms-v1/evals/tool_tests'))"
```

### Callback tests — pytest, one file per invocation (module-name collision)
```bash
python -m pytest rrms-v1/evals/callback_tests/tests/root_agent/after_model_callbacks/after_model/test.py -q
python -m pytest rrms-v1/evals/callback_tests/tests/root_agent/before_agent_callbacks/before_agent/test.py -q
# After editing callback code: sync-callbacks.py --from-local first.
```

### Reading UNMASKED app config (pull masks bucket/project/dataset as `$env_var`)
`cxas pull` redacts sensitive values to `$env_var`. To see the real values (e.g. to verify
variant logging settings), read them from the API:
```python
from google.cloud.ces_v1beta.services.agent_service import AgentServiceClient
ls = AgentServiceClient().get_app(name="projects/yves-normandin-project/locations/us/apps/<id>").logging_settings
print(ls.audio_recording_config.gcs_bucket, ls.cloud_logging_settings.enable_cloud_logging,
      ls.bigquery_export_settings.project, ls.bigquery_export_settings.dataset)
```

---

## 6. The change cycle

1. **Pull** before editing (skip only if you know local == platform). Pull to a temp dir.
2. **Edit** `rrms-v1/cxas_app/rrms-v1/`. After callback edits: `sync-callbacks.py --from-local`.
3. **Lint** via the `lint-fixer` sub-agent → `status: clean`.
4. **Push** to canonical (`cxas push … --to $APP`).
5. Structural change (new tool/agent/callback)? **`gate-check.py`** (expect ALL PASS).
6. **Run evals** (text first). Triage failures by reading transcripts before changing code.
7. Update `tdd.md` (pass-rate history + changelog), `experiment_log.md` (auto), `todo.md`.
8. Commit + push git only when the user asks. **`git add` the actual files** — verify with
   `git status` that feature code is staged, not just incidental files.

### Releasing to the demo phone numbers
```bash
./deploy-variants.sh --dry-run     # preview merged config per variant
./deploy-variants.sh               # regenerate both variants from canonical + push
```
`deploy-variants.json` holds per-variant config (CLID, app_id) **and** `appConfigOverrides`
(deep-merged into each variant's `app.json` before push) — this is what preserves the
Console-only advanced settings (Cloud Logging, BigQuery export, live audio bucket) that a
plain push would otherwise reset. Edit those values in `deploy-variants.json`, never in the Console.

---

## 7. Gotchas (each cost real debugging time)

- **`--priority` filters GOLDENS too**, not just sims (the `--help` is wrong). Passing
  `P1,P2` silently skips P0 goldens. **Always pass `P0,P1,P2`** and sanity-check per-type totals.
- **Invalid model names are silently dropped on push** → app falls back to platform default.
  After changing `modelSettings.model`, pull and verify. Valid: `gemini-3.1-flash-live`.
- **Never score audio with `results --audio`** — that flag returns a bogus 0%. Plain
  `results <run_id>` (platform `evaluation_status`) is the truth.
- **`run-evals.py` proto-enum crash at the scoring step — PATCHED 2026-06-12 (re-apply after any
  `pip install`/upgrade of `cxas_scrapi`).** Symptom: run triggers fine, then `Unrecognized
  EvaluationRunState enum value: 5` → `ERROR: Evaluation run failed: 'int' object has no
  attribute 'name'`. Cause: the server returns `EvaluationRunState=5` but the installed
  `google-cloud-ces` (0.6.0) stubs only define 0–3, so proto-plus returns the raw int and
  `run_status.state.name` blows up. Fix is in
  `.venv/lib/python3.14/site-packages/cxas_scrapi/utils/eval_utils.py`, method
  `wait_for_run_and_get_results` (~line 1305): compare by **integer** and treat anything not
  pending as terminal —
  `if int(run_status.state) not in {0, 1}: break` (0=UNSPECIFIED, 1=RUNNING). Forward-compatible
  (won't recrash when the server adds state 6). **Not an upgrade problem** — verified 2026-06-12
  that `cxas_scrapi` (1.4.1) and `google-cloud-ces` (0.6.0) are BOTH already the latest published
  versions; the CES *server* is ahead of its own published stubs (newest ces still defines only
  states 0–3), so there's nothing to upgrade to and the bug is unfixed upstream. The value-tolerant
  compare is the only robust fix. Workaround if the patch is gone: the run still completes on the
  platform — score it separately with `scrapi-eval-runner.py results <run_id>`.
- **`cxas pull` nests** an app-named subfolder inside `--target-dir`. Never pull into
  `cxas_app/rrms-v1/`.
- **`cxas pull` masks** bucket/project/dataset as `$env_var`. Use `get_app` for real values (§5).
- **Stale platform golden?** `push-goldens --force-recreate` hard-resets; the diff-aware
  upsert can miss tool-arg changes.
- **Audio tool-drop — SOLVED 2026-06-12 via deterministic emission (see the FIX gotcha below).**
  Historically `gemini-3.1-flash-live` dropped `cancel_alarm`/`put_account_on_test`/`end_session`
  intermittently in audio (text scored ~100%; audio sat in a ~85–96% band). That gap is now
  closed — audio goldens 45/55 → **54/55 (98.2%)** with ZERO tool drops across runs. The residual
  is now language-purity / judge noise, not dropped tools. (Still: read the transcript with
  `capture-golden-transcripts.py` before chasing a dip; the script saves user/agent TEXT only —
  for the tool trajectory use `triage-results.py --run-id` and read the `Called: [...]` list.)
- **★ FIX for the audio tool-drop — deterministic emission from callbacks (2026-06-12).** The
  model can't drop a call it never had to make: have a **callback emit the function_call** instead
  of relying on the model.
    - **State-changing action tools (`cancel_alarm`, `put_account_on_test`) → `before_model`
      callback that RETURNS the call**, short-circuiting that model turn. The runtime executes it
      and re-invokes the model with the result, which then speaks a grounded confirmation. This
      also guarantees tool-before-confirmation ordering. Trigger must be a SAFE state signal, not a
      data coincidence: we added an `intent` arg (+ `duration_minutes`/`duration_label` for test)
      to the reliably-called `verify_passcode`, which writes `_pending_action` / `_test_duration_*`
      on a SUCCESSFUL verify; the callback fires only when `_pending_action` is set AND
      `passcode_verified` (gate never bypassed — confirmed by `passcode_gate_enforced_before_action`
      staying 5/5). `has_active_alarm` alone is NOT a safe cancel-vs-test signal (Fort Worth/Plano
      on-test branches also have active alarms). Args-carrying tools work only if the args are in
      state (duration stashed via verify_passcode). Missing signal → callback no-ops → safe fallback.
    - **`end_session` → `after_model` callback that APPENDS the call** (the close happens in one
      invocation, so `before_model` has nothing to intercept). "Case B" in the after_model callback:
      when the model SPEAKS a terminal sign-off but drops `end_session`, append
      `Part.from_function_call("end_session", {})`. Trigger = the model's own farewell text (closing
      markers, with a negative guard for "anything else?"/"algo más") → zero premature-hangup risk.
    - **CONFIRMED: both a `before_model`-RETURNED and an `after_model`-APPENDED function_call execute
      in Live/audio.** This resolves the old "untested whether appended function_calls execute"
      question and overturns the prior "audio tool-drop has no callback fix" conclusion.
- **Do NOT add a pre-call "bridge" utterance to fix the audio tool-drop — it makes it WORSE**
  (FALSIFIED 2026-06-11, Iteration 25; A/B: bridge 17/55 = 30.9% vs baseline 45/55 = 81.8%,
  runs=5). Hypothesis was that the strict "call the tool FIRST, never speak in-progress phrasing
  before the call, speak once after the fact" rule *caused* the drops by removing the model's
  speech slot. Reality is the **opposite**: with `gemini-3.1-flash-live`, any permitted pre-call
  speech becomes a **runway** — the live transcript showed the agent say "Thanks, let me take
  care of that for you…" and glide STRAIGHT into "The alarm at the Plano branch has been
  canceled…" in one breath, **never calling cancel_alarm** (bridge-then-hallucinate). That strict
  prohibition is **load-bearing — it suppresses the hallucination glide. Keep it; never relax it.**
  (The drop itself is now fixed STRUCTURALLY via deterministic emission — see the FIX gotcha
  above — not by relaxing this prompt rule. The prohibition still stands as a backstop.)
- **The live model parrots instruction phrasing** into caller speech — write guidelines so no
  sentence is speakable verbatim. (It also auto-switched language on the word "Hola" until the
  guideline got an explicit non-example.)
- **`after_model` callback can only ADD parts in audio/Live, never replace** — returning
  `LlmResponse.from_parts(...)` in Live mode does NOT replace the model's output; it **appends**
  the returned parts to what the model already produced (which is already committed/streaming).
  So a callback can prepend/append text or append a function_call, but it **cannot suppress or
  rewrite** an utterance the model already emitted. This is why the farewell callback works (it
  only adds text when the turn had none) and why a "suppress the false confirmation" guard for
  the dropped-tool-call bug is **not viable in audio** — the hallucinated confirmation is already
  out. **RESOLVED 2026-06-12: an appended `function_call` IS executed by the Live runtime** — the
  after_model "Case B" appends a dropped `end_session` and it fires (audio end_session drops → 0).
  So the append-a-function_call rescue is real. (And `put_account_on_test` IS forceable after all —
  stash its `duration` in state via verify_passcode; see the FIX gotcha above.) The "can't
  suppress/rewrite an already-emitted utterance" limit still holds — these callbacks only ADD.
- **ASR realities** (audio): spoken words lowercase + compound words split ("Bluebird"→"Blue
  Bird"). Absorb in *tools* (verify_passcode normalizes + fuzzy-matches, Levenshtein ≤ 2). In
  golden tool-args use `$matchType: ignore` for spoken values (passcodes) — regexes can't cover
  all variants.
- **Goldens' first user turn is `"Hello"`**, not `<event>welcome</event>` (TTS reads the tag aloud).
- **Spanish audio** needs `es-US` in `app.json` `languageSettings.supportedLanguageCodes`
  BEFORE it can appear in `synthesizeSpeechConfigs` (push 400s otherwise). Keep
  `enable_multilingual_support` OFF — it triggers platform auto-handling (we want explicit-only switching).
- **Background runs**: stdout is buffered; an empty log while the PID is alive is normal.

---

## 8. Current state (update me each session)

**Architecture:** single `root_agent`, 6 Python tools (`lookup_accounts_by_caller`,
`verify_passcode`, `cancel_alarm`, `put_account_on_test`, `send_confirmation_sms`,
`set_language`) + system `end_session`. THREE callbacks: `before_agent` (default CLID),
`before_model` (deterministic action-tool emission — forces `cancel_alarm`/`put_account_on_test`),
`after_model` (Case A bilingual farewell + Case B `end_session` rescue). `verify_passcode` takes
`intent` (+ `duration_minutes`/`duration_label` for test) and writes `_pending_action` /
`_test_duration_*` to drive the before_model callback. Mock data lives ONLY in
`lookup_accounts_by_caller`.

**Features shipped & validated:**
- (committed `ee76756`, on canonical + both variants) Company-name greeting; passcode ASR
  robustness (Levenshtein ≤ 2); EN↔ES explicit-only language switching; `deploy-variants.sh`
  preserving variant logging/audio via `appConfigOverrides`.
- **(2026-06-12, on canonical + BOTH variants @ commit `e9d0ffe`) Audio tool-drop fix via
  deterministic emission** (before_model RETURNS cancel/test; after_model APPENDS end_session).
  See §7 FIX gotcha for the full mechanism + safety gate.

**Eval inventory:** 11 goldens, 6 sims, 24 tool tests, 29 callback cases.
**Latest scores (2026-06-12, after the tool-drop fix):**
- **audio 54/55 = 98.2% (runs=5 ×2), ZERO tool drops** — up from the 45/55 (81.8%) baseline. The
  only residual is language-purity / judge noise (`no_language_autoswitch` / `language_switch`),
  a different golden each run; not a tool drop.
- **text 29/33 (runs=3): all action + closing goldens 3/3** (cancel, on-test, plano, dispatch,
  closing, passcode-gate). The 4 misses = `no_language_autoswitch` 0/3 (language autoswitch, see
  open items) + 1 `sms_offered` TEXT_MISMATCH (judge noise). No tool-drop regression in text.

**2026-06-11 — FALSIFIED the "pre-call bridge" prompt fix** (Iteration 25): relaxing the strict
"speak only after the tool returns" rule made the drop WORSE (30.9% vs 81.8%). The prohibition is
load-bearing; keep it. **2026-06-12 — SOLVED the drop structurally** via deterministic emission
(above), without touching that rule.

**Open items / candidate next steps:**
- **`no_language_autoswitch_without_request` fails in TEXT (0/3)** — the agent calls `set_language`
  / replies in Spanish when the caller merely USES a Spanish greeting. Pre-existing & orthogonal to
  the tool-drop fix (passes 4–5/5 in audio; was failing in text before the end_session work).
  **To investigate next session** (the existing language-autoswitch issue, more pronounced in text).
- **Callback tests not yet written** for the new `before_model` callback and the after_model
  "Case B" (sync-callbacks flags the before_model test missing). Add under
  `evals/callback_tests/tests/root_agent/{before_model_callbacks/before_model,after_model_callbacks/after_model}/test.py`.
- ~~Variants NOT redeployed~~ — DONE 2026-06-12: both variants deployed @ `e9d0ffe` via
  `./deploy-variants.sh`.
- `experiment_log.md` / `tdd.md` not yet updated with the 2026-06-12 iteration (auto-memory IS
  updated — see `cxas-before-model-emit-fixes-audio-tool-drop`).
- Minor polish: English filler ("Got it,") sometimes prepended after switching to Spanish
  (persona acknowledgment guideline hardcodes English fillers). (User aware.)
- `todo.md` item 8c: wire the two GTP phone numbers to the variant apps in the Console (user task).

---

## 9. End-of-session ritual

Before ending a session, refresh this file so the next session starts clean:
1. Update **§8 Current state** (features shipped, latest scores, open items).
2. Add any **new gotcha** discovered this session to §7.
3. Add/adjust any **new script or recipe** used to §4/§5.
4. Bump the "Last updated" date at the top.
5. Mirror durable, cross-session facts into `tdd.md` (design) and the auto-memory if warranted.
