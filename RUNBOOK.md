# RRMS-v1 Session Runbook

Operational quick-start for the `rrms-v1` CXAS voice agent. Read this + `CLAUDE.md`
at the start of a session and you're up to speed. **Update this file at the end of
every session** (see "End-of-session ritual" at the bottom).

Last updated: 2026-06-11.

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
- **`cxas pull` nests** an app-named subfolder inside `--target-dir`. Never pull into
  `cxas_app/rrms-v1/`.
- **`cxas pull` masks** bucket/project/dataset as `$env_var`. Use `get_app` for real values (§5).
- **Stale platform golden?** `push-goldens --force-recreate` hard-resets; the diff-aware
  upsert can miss tool-arg changes.
- **Missed tool calls are an AUDIO artifact** (confirmed 2026-06-11: text run had 0
  `(None / Missed)`; audio drops `cancel_alarm`/`put_account_on_test` intermittently). Audio
  goldens sit in a **~85–96% stochastic band**; the same code scores ~100% in text. Read the
  transcript (`capture-golden-transcripts.py`) before changing code; don't chase 2/3 audio dips.
- **The live model parrots instruction phrasing** into caller speech — write guidelines so no
  sentence is speakable verbatim. (It also auto-switched language on the word "Hola" until the
  guideline got an explicit non-example.)
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
`set_language`) + system `end_session`. Two callbacks: `before_agent` (default CLID),
`after_model` (bilingual farewell). Mock data lives ONLY in `lookup_accounts_by_caller`.

**Features shipped & validated (committed `ee76756`, deployed to canonical + both variants):**
- Company-name greeting (lookup on first turn; `{company_name, branches}` mock structure).
- Passcode ASR robustness (verify_passcode Levenshtein ≤ 2).
- Language switching EN↔ES, explicit-request-only (`set_language` tool, `language_switching`
  guideline, bilingual farewell, `es-US` supported).
- `deploy-variants.sh` preserves variant logging/audio settings via `appConfigOverrides`.

**Eval inventory:** 11 goldens, 6 sims, 24 tool tests, 29 callback cases.
**Latest scores:** text 30–32/33 (~91–97%, paraphrase noise); audio 25–28/33 (stochastic band,
confirmed via text A/B that the gap is dropped tool calls in the audio path, not logic).

**Open items / candidate next steps:**
- Minor polish (not yet done): after switching to Spanish the agent sometimes prepends an
  English filler ("Got it,") — the persona acknowledgment guideline hardcodes English fillers
  and isn't language-aware. One-line instruction fix would tighten Spanish purity. (User aware.)
- `todo.md` item 8c: wire the two GTP phone numbers to the variant apps in the Console (user task).

---

## 9. End-of-session ritual

Before ending a session, refresh this file so the next session starts clean:
1. Update **§8 Current state** (features shipped, latest scores, open items).
2. Add any **new gotcha** discovered this session to §7.
3. Add/adjust any **new script or recipe** used to §4/§5.
4. Bump the "Last updated" date at the top.
5. Mirror durable, cross-session facts into `tdd.md` (design) and the auto-memory if warranted.
