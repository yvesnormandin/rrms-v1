# Upstream issue draft — cxas-scrapi

> Draft GitHub issue for **GoogleCloudPlatform/cxas-scrapi** (repo per project links;
> package metadata lists author Patrick Marlow <pmarlow@google.com>).
> Discovered while running rrms-v1 audio goldens, 2026-06-12. See RUNBOOK §7
> ("run-evals.py proto-enum crash") for the local patch we're carrying until this lands.

---

**Title:** `wait_for_run_and_get_results` crashes with `'int' object has no attribute 'name'` when the server returns an `EvaluationRunState` the installed `ces` stubs don't define

**Labels:** bug

## Summary

`EvalUtils.wait_for_run_and_get_results` (in `cxas_scrapi/utils/eval_utils.py`) polls an evaluation run and checks `run_status.state.name`. When the CES backend returns an `EvaluationRunState` enum value that the installed `google-cloud-ces` stubs don't define, proto-plus returns the **raw int** instead of an enum member and emits a warning; the subsequent `.name` access then raises `AttributeError`, aborting the entire run at the scoring step — even though the evaluation itself completed successfully on the platform.

This is currently reproducible with the **latest published versions of both packages** (`cxas-scrapi==1.4.1`, `google-cloud-ces==0.6.0`): the server returns state `5`, but the newest published `ces` enum only defines `0–3`. So the server is ahead of its own published client stubs, and there is no version combination that avoids the crash.

## Environment

| Package | Version |
|---|---|
| cxas-scrapi | 1.4.1 (latest on index) |
| google-cloud-ces | 0.6.0 (latest on index) |
| proto-plus | 1.28.0 |
| protobuf | 7.35.0 |
| Python | 3.14.2 |

## Error

```
UserWarning: Unrecognized EvaluationRunState enum value: 5
  (proto/marshal/rules/enums.py:37)
ERROR: Evaluation run failed: 'int' object has no attribute 'name'
```

## Root cause

`cxas_scrapi/utils/eval_utils.py`, in `wait_for_run_and_get_results` (~line 1305):

```python
while True:
    run_status = self.eval_client.get_evaluation_run(run_name)
    if run_status.state.name in ["COMPLETED", "ERROR"]:   # <-- AttributeError when state is a raw int
        break
    ...
```

`google.cloud.ces_v1beta` defines `EvaluationRun.EvaluationRunState` as only:

```
EVALUATION_RUN_STATE_UNSPECIFIED = 0
RUNNING = 1
COMPLETED = 2
ERROR = 3
```

When the backend returns `5`, proto-plus can't map it to a member, warns, and yields the int `5`. `(5).name` → `AttributeError`. Because the call sites (`generate_combined_report_from_dir` → `run_all_evals` → `wait_for_run_and_get_results`) run goldens **before** writing the combined HTML report, the crash also means no report is produced.

The bug is a forward-compatibility hazard in general: any time the server adds a new `EvaluationRunState`, every client on an older `ces` stub crashes here.

## Impact

- `run-evals` / `generate_combined_report_from_dir(run=True)` aborts at the goldens scoring step; no combined report is written.
- Affects all current users, since the failing state is returned by the live backend with the latest published `ces`.
- Workaround: the run does complete on the platform, so results can still be fetched out-of-band via a separate `get`/`list_evaluation_results_by_run` call — but the in-process flow is broken.

## Proposed fix

Compare by integer value and treat anything that isn't a *pending* state (`UNSPECIFIED=0`, `RUNNING=1`) as terminal. `int()` works on both real enum members and the raw-int fallback, so known states behave identically and unknown future states stop the loop instead of crashing:

```python
# State may be a value the installed ces stubs don't define yet; proto-plus
# then returns the raw int and `.state.name` raises AttributeError. Compare by
# integer and treat anything not pending (0=UNSPECIFIED, 1=RUNNING) as terminal.
_PENDING_RUN_STATES = {0, 1}
while True:
    run_status = self.eval_client.get_evaluation_run(run_name)
    if int(run_status.state) not in _PENDING_RUN_STATES:
        break
    if time.time() - start_time > timeout_seconds:
        raise TimeoutError(f"Evaluation run {run_name} timed out.")
    time.sleep(10)
```

This is forward-compatible (won't recrash when the backend adds state 6) and doesn't depend on shipping a matching `ces` stub bump.

## Alternatives considered

- **Bumping `google-cloud-ces`** so the enum knows state 5 — not currently possible (0.6.0 is the latest published and still only defines 0–3), and it would only postpone the crash to the next new state.
- **`getattr(run_status.state, "name", str(run_status.state))`** with a string-compare — works, but the int comparison is cleaner and avoids string-name coupling.

## Note

It would also be worth auditing other `.state.name` / enum-`.name` usages for the same raw-int fallback hazard; `wait_for_run_and_get_results` is the one we hit, but the pattern is generic.
