# Experiment Log

Tracking what was tried, results across all eval types, and failure details.

## Iteration 1 — 2026-06-04
**Change:** Initial baseline

| Eval Type | Pass Rate |
|-----------|-----------|
| Goldens | 0/0 (0%) |
| Tool Tests | 16/16 (100%) |
| Callback Tests | 18/18 (100%) |

## Iteration 2 — 2026-06-04
**Change:** Text-mode golden validation (pre-audio)

| Eval Type | Pass Rate |
|-----------|-----------|
| Goldens | 11/24 (46%) |
| Simulations | 12/15 (80%) |
| Tool Tests | 16/16 (100%) |
| Callback Tests | 18/18 (100%) |

**Golden failures:**
- `EXPECTATION_FAIL` uc2_on_test_disambiguation_sms_happy_path x3: "The agent must confirm the on-test result referencing the ac" — The custom expectation states that 
- `EXPECTATION_FAIL` sms_offered_after_validation_then_declined x3: "The agent must confirm verbally that no text will be sent, t" — The agent verbally confirmed that n
- `TEXT_MISMATCH` passcode_gate_enforced_before_action x2: sem_score=2
- `TEXT_MISMATCH` dispatch_status_reassurance x2: sem_score=2
- `TOOL_MISSING` uc1_cancel_false_alarm_happy_path x3: expected lookup_accounts_by_caller, got lookup_accounts_by_caller. Called: [lookup_accounts_by_calle

**Sim failures:**

**Triage (iteration 2, 5 clusters dispatched):**
- `uc1` 0/3 TOOL_MISSING → platform result: observed `lookup_accounts_by_caller` called with `args {}` vs golden's EXACT_MATCH `caller_phone` arg ("Type mismatch: str != NoneType"). Tool has state fallback; LLM arg-passing is nondeterministic. USER-APPROVED fix: make the tool zero-arg (state-only).
- `uc2` 0/3 EXPECTATION_FAIL → agent listed all 3 branches + open "which one?" despite caller saying "Dallas"; cascade: "Bluebird" read as branch name → operator transfer. Fix: instruction (confirm caller-named branch).
- `sms_offered_after_validation_then_declined` 0/3 EXPECTATION_FAIL → agent confirms decline but skips "anything else today?" before closing. Fix: instruction (one message: confirm + offer help).
- `passcode_gate` 1/3 TEXT_MISMATCH → USER ruled: not paraphrase variance — agent must re-ask for the passcode on pushback. Fix: instruction (refuse + renew passcode request in same response).
- `dispatch_status_reassurance` 1/3 TEXT_MISMATCH → paraphrase variance (sem_score=2, behavior correct); user declined similarity-threshold change. LEFT AS-IS — watch next run.

**Fix round 1 applied before iteration 3:**
1. `lookup_accounts_by_caller` → zero-arg (reads `caller_phone` from session state only). Tool JSON updated; 3 lookup tool tests moved phone `args:`→`variables:`; all 8 golden lookup expectations → `args: {}`.
2. Instruction `Resolve_Account`: caller-named branch ⇒ confirm that one branch (name + address); never open-enumerate.
3. Instruction `Put_On_Test` step 5: decline ⇒ ONE message confirming no-text AND offering further help.
4. Instruction `Verify_Passcode` step 5 (new): pushback ⇒ refuse + re-ask passcode in same response.

Expected: uc1/uc2/sms_declined 0/3→3/3, passcode_gate 1/3→3/3, sim declines_sms pass. Watch for regressions: `disambiguation_accuracy_fort_worth`, `single_site_no_disambiguation`.
## Iteration 3 — 2026-06-04
**Change:** Fix round 1 (text mode): lookup_accounts_by_caller now zero-arg (reads caller_phone from state) — fixes uc1 TOOL_MISSING arg mismatch; instruction edits: confirm caller-named branch in multi-branch disambiguation (uc2), SMS-decline must confirm + offer further help in one turn (sms_declined golden + sim), passcode pushback must re-ask for passcode (passcode_gate). Tool tests switched lookup args to variables. Goldens expect argless lookup.

| Eval Type | Pass Rate |
|-----------|-----------|
| Goldens | 17/24 (71%) |
| Simulations | 13/15 (87%) |
| Tool Tests | 16/16 (100%) |
| Callback Tests | 18/18 (100%) |

**Status:** improved from 11/24 (45.8%)

**Golden failures:**
- `TOOL_MISSING` uc2_on_test_disambiguation_sms_happy_path x3: expected put_account_on_test, not found. Called: [lookup_accounts_by_caller, verify_passcode, send_c
- `TEXT_MISMATCH` disambiguation_accuracy_fort_worth x3: sem_score=2
- `TEXT_MISMATCH` passcode_gate_enforced_before_action: sem_score=2

**Sim failures:**
- `declines_sms_after_on_test`: The agent must call a tool to put the Dallas branch on test for one hour. — The trace does not show a tool call to perform the 'put on test' action. The age
- `declines_sms_after_on_test`: The agent must call a tool to put the Dallas branch on test for one hour. — While the agent verbally confirmed the branch was on test, there is no tool call

## Iteration 4 — 2026-06-04
**Change:** Fix round 2 (text mode): standalone branch-confirmation turn (fixes fort_worth regression from round 1 — agent was chaining passcode request into the confirm turn); put_account_on_test now MANDATORY before any on-test confirmation + new action_grounding constraint (fixes uc2 golden 0/3 + declines_sms sim hallucinated-action bug — model narrated success without calling the tool); passcode_gate golden turn-2 text aligned with verified-correct agent phrasing (judge variance on store-name mention, user-approved eval edit).

| Eval Type | Pass Rate |
|-----------|-----------|
| Goldens | 18/24 (75%) |
| Simulations | 15/15 (100%) |
| Tool Tests | 16/16 (100%) |
| Callback Tests | 18/18 (100%) |

**Status:** improved from 17/24 (70.8%)

**Golden failures:**
- `TOOL_MISSING` uc2_on_test_disambiguation_sms_happy_path x3: expected , not found. Called: [lookup_accounts_by_caller, verify_passcode, put_account_on_test, send
- `TOOL_MISSING` deterministic_spoken_closing x3: expected cancel_alarm, not found. Called: [lookup_accounts_by_caller, end_session]


**Triage (iteration 4, 2 clusters — both confirmed by user in Console):**
- `deterministic_spoken_closing` 0/3 TOOL_MISSING cancel_alarm — REGRESSION from fix round 2: the standalone-turn rule + unconditional "ask for the passcode" made the agent discard the caller's INLINE passcode ("...cancel it? Passcode is Sunset.") and re-ask; the scripted "No, that's everything" then read as a decline → [lookup, end_session] only.
- `uc2` 0/3 TOOL_MISSING end_session — branch asymmetry: SMS-ACCEPT path (step 4) lacked the confirm+offer-help rule added to the DECLINE path in round 1; agent collapsed confirmation+sign-off into turn 5, the scripted "Nope." hit unintelligible-handling, end_session never fired on the expected turn.

**Fix round 3 applied before iteration 5:**
1. `Verify_Passcode` step 1: inline-passcode carve-out — never re-ask if the caller already stated it.
2. `Resolve_Account`: standalone-turn rule explicitly scoped to multi-branch confirmation only; single-account callers chain verify+action in the same turn.
3. `Put_On_Test` step 4 (SMS-ACCEPT): ONE message = confirm sent + "Anything else today?" (mirrors decline branch).
## Iteration 5 — 2026-06-04
**Change:** Fix round 3 (text mode): inline-passcode carve-out in Verify_Passcode (agent was discarding a passcode supplied in the caller's first utterance and re-asking — broke deterministic_spoken_closing chain lookup->verify->cancel); standalone-turn rule scoped to multi-branch confirmation only; single-account callers chain verification+action in same turn; SMS-ACCEPT branch now mirrors decline branch (confirm sent + offer further help in ONE message) so uc2 turn alignment holds and end_session fires.

| Eval Type | Pass Rate |
|-----------|-----------|
| Goldens | 21/24 (88%) |
| Simulations | 15/15 (100%) |
| Tool Tests | 16/16 (100%) |
| Callback Tests | 18/18 (100%) |

**Status:** improved from 18/24 (75.0%)

**Golden failures:**
- `TEXT_MISMATCH` dispatch_status_reassurance x2: sem_score=2
- `TEXT_MISMATCH` uc1_cancel_false_alarm_happy_path: sem_score=2


## Iteration 5–6 — 2026-06-04 (goldens-only text runs after user edits)
**Run 5** (after USER hand-edits to a golden + instruction "do NOT confirm the site"): 22/24; uc1 1/3 — two causes: (a) STALE PLATFORM GOLDEN (uc1 lookup still expected caller_phone arg platform-side despite local args:{}; diff-aware upsert missed it), (b) uc1 vs passcode_gate goldens demanded contradictory store-name behavior on the single-site passcode ask.
**Fix (user-approved alignment package):** instruction = never name the store on the single-site passcode ask (site name OK in action confirmations); passcode_gate golden reverted to generic text; uc1 cancel turn += "Anything else I can help with?"; `push-goldens --force-recreate` to hard-reset platform copies.
**Run 6: 24/24 (100%) — all 8 goldens 3/3. Text validation complete.**

LESSON: when a previously-fixed arg-mismatch failure reappears, suspect the platform copy (use --force-recreate), and check for golden-vs-golden contradictions before blaming the agent.
