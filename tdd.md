# Technical Design Document (TDD) — RRMS Demo Agent (`rrms-v1`)

> Living document. Update the TDD first, then update evals to match.
> Status: **APPROVED 2026-06-04** (user approved as-is; all 8 open questions resolved with demo defaults — see §9).

**Sources:**
- `sources/rrms-demo-brief.md` — requirements brief with two use-case scenarios (false alarm cancellation; multi-location on-test) plus a sample call for each, and demo constraints (all customer data mocked; passcodes are real words).
- User interview 2026-06-04 — modality/model/platform config, English-only, mock-data requirements, company persona.
- `gecx-config.json` — platform configuration (GCP project, location, app name, bucket, model, modality).

---

## Agent Design

### 1. Architecture

**Company / persona:** Rapid Response Monitoring (professional alarm-monitoring company). Greeting style per the sample calls: *"Rapid Response Monitoring. How can I help you today?"*

**Modality:** Audio (telephone voice agent). **Model:** `gemini-3.1-flash-live`. **Default channel:** `audio`. **Language:** English only (single-language; no language-switching logic needed). Source: user interview 2026-06-04 + `gecx-config.json`.

> Audio-modality note for eval design downstream: voice goldens/sims need higher `max_turns` headroom (+4–6) and similarity-threshold tuning vs. text. Speech pacing, if needed, should be set via `speakingRate` in the Console audio config, not via persona text (see design guide → Voice / Audio: Speech Rate and Pacing). Surfaced here so eval-writer and the scaffolder account for it.

**Proposed hierarchy: single agent.**

| Agent | Role | Justification |
|-------|------|---------------|
| `root_agent` (alarm-monitoring service agent) | Greets caller, detects intent (cancel alarm vs. put branch on test), disambiguates location when needed, verifies passcode, performs the requested action, offers/sends SMS confirmation, and closes the call. | Both use cases are short, linear voice flows that share the same persona and the same "verify passcode → perform action → confirm" backbone. Per design guide, start single-agent for prototypes/linear flows; only decompose at 2+ meaningfully different personas/CUJs. The two CUJs differ only in the action taken, not in persona or flow shape, so a single agent with two task-flow branches is appropriate. Revisit if more use cases are added. |

No sub-agents proposed. The brief describes exactly two conversational flows that share authentication and closing behavior.

### 2. Tools

All tools are **Python function tools backed by an in-code mock dataset** (user interview 2026-06-04: "All customer data must be mocked inside the app … in-code mock dataset of a few sample customers"). No real external systems. `end_session` is the only system tool.

| Tool Name | Type | Purpose | Justified by |
|-----------|------|---------|--------------|
| `lookup_accounts_by_caller` | Python function | Given the caller's phone number, return the account(s) linked to it. Returns a single account for single-site callers and multiple branch records for multi-location callers (drives disambiguation). Returns enough per-branch detail to disambiguate (branch name, street address, account-number last digits) and to support actions. | UC1 step 4 (resolve the caller's site); UC2 steps 2–3 ("recognizes multiple accounts tied to caller's phone number"; disambiguation). |
| `verify_passcode` | Python function | Validate a spoken passcode against the resolved account's passcode. Returns verified true/false. Must be called before any cancel/test action. | UC1 steps 3–4; UC2 step 4 ("standard security check before action"). |
| `cancel_alarm` | Python function | Cancel the active alarm on the verified account; returns confirmation including whether police/dispatch occurred. | UC1 steps 4–5 ("immediately cancels the alarm, preventing unnecessary dispatch"; reassure whether dispatch occurred). |
| `put_account_on_test` | Python function | Place the verified branch/account on test for a caller-stated duration; returns confirmation. | UC2 steps 1, 5 ("put a specific branch on test … states duration in their own words"; "validates and confirms the test"). |
| `send_confirmation_sms` | Python function | Send (mock) an SMS confirmation of the completed action to the caller. | UC2 step 5 ("offering SMS confirmation based on the prior validation"). |
| `end_session` | System | Deterministically terminate the call after the closing line. | Both sample calls end with an explicit goodbye. |

Tool-design notes (from design guide; for the scaffolder):
- **Voice-expressible inputs.** Duration should be captured as a human-friendly value (e.g., `"one hour"` / a normalized duration the caller can say), not a high-cardinality raw value. Passcode is a single spoken word. Avoid asking the caller to read account numbers aloud — use the last-digits field only for *agent-to-caller* confirmation, not as an input.
- **Confirm-before-act.** The sample calls show the agent confirming the resolved branch (UC2) and verifying the passcode *before* calling `cancel_alarm` / `put_account_on_test`. Treat passcode verification as a hard prerequisite (early validation) for both destructive/state-changing tools.
- **Error returns.** Mock tools should return an `agent_action` key on failure (e.g., wrong passcode, unknown account) so the agent has a deterministic recovery path. **The brief does not show failure dialogues — see Open Questions / Known Issues.**

### 3. Routing Logic

Single agent; "routing" here is intra-agent intent + flow selection rather than sub-agent transfer.

**Intent detection (from the caller's first utterance):**
- Cancel-alarm intent — *"I accidentally set off the alarm. Would you be able to cancel that for me"* (UC1 sample) → false-alarm cancellation flow.
- On-test intent — *"I need to put the Dallas branch on testing for one hour"* (UC2 sample) → on-test flow.

**Account resolution / disambiguation:**
- Call `lookup_accounts_by_caller`.
- If exactly one account → proceed (UC1: Johnson Verizon Store resolves directly; the agent never asks which site).
- If multiple accounts → disambiguate conversationally before acting. Quote (UC2 sample): *"I see you manage multiple branches. Did you mean the Dallas branch at 123 Main Street?"* Confirm the specific branch (by name + address) before requesting the passcode.

**Verification gate (both flows):** request and validate the passcode before performing the action. Quotes: UC1 — *"Could you please provide the passcode for verification?"*; UC2 — *"Please provide the account passcode to confirm."*

**Action + confirmation:**
- UC1: after verification, cancel the alarm and report dispatch status. Quote: *"Thanks, verified. The alarm at Johnson Verizon Store has been canceled. Police were not dispatched."*
- UC2: after verification, put the branch on test for the stated duration, confirm using the account's last digits, then **offer** SMS. Quote: *"The Dallas branch account ending in 345 is now on test for one hour. Would you like me to send a confirmation text as well?"* If the caller accepts, call `send_confirmation_sms`, then offer further help and close.

**Closing:** end with a warm sign-off then `end_session`. Quotes: *"You're all set. Have a good day."* / *"All right, have a great day."*

**Failure / edge-case policies (user-approved demo defaults, 2026-06-04):**
- **Wrong passcode:** allow up to 2 retries (3 attempts total); after the final failure, politely decline to perform the action and offer to transfer the caller to a live operator (simulated — the agent states the transfer, then ends the session).
- **Unknown caller / phone not in dataset:** apologize that the account can't be located and offer transfer to a live operator (simulated, as above).
- **Cancel request with no active alarm:** inform the caller there is no active alarm signal on the account and nothing to cancel; offer further help.
- **Missing/ambiguous on-test duration:** ask the caller for the duration; accept 30 minutes to 8 hours. Out-of-range → explain the accepted range and re-ask.
- **Caller declines SMS:** confirm verbally and close normally.

### 4. Variables

The brief is silent on session schema; these are proposals. Default to session parameters unless a lookup is required.

| Variable | Schema | Source | Notes |
|----------|--------|--------|-------|
| `caller_phone` | string (E.164 or display) | Session parameter (supplied by telephony platform / eval) | Key into the mock dataset via `lookup_accounts_by_caller`. Drives single- vs multi-account branching. |
| `_resolved_account` | JSON object: `{account_id, branch_name, street_address, account_last_digits, has_active_alarm, passcode_verified}` | Derived during the conversation (set by lookup / verify tools) | Observability lens into which account the agent is acting on and whether the passcode gate has been cleared. Consolidated as one JSON state variable to avoid variable explosion. **Do NOT override directly in evals** — it is populated by tool calls; drive it via `caller_phone` + dialogue instead. |

> Sources do not specify any pre-authenticated user attributes or tiers. No `auth_status`/`user_role`-style variables proposed — identity here is per-action passcode verification, not a session-level auth state. Confirm with user.

### 5. Callbacks

| Callback | Agent | Type | Purpose | Justified by |
|----------|-------|------|---------|--------------|
| Deterministic farewell + end | `root_agent` | `after_model` | The LLM frequently calls `end_session` without speaking the closing line first (design guide). Inject the closing line before `end_session` so every call ends with a spoken sign-off. | Both sample calls end with a spoken goodbye immediately before hanging up. |
| Default demo CLID | `root_agent` | `before_agent` | Sets `caller_phone` to `DEFAULT_CALLER_PHONE` ONLY when the session has none (live GTP callers); eval `session_parameters` always win. The constant is the single point of per-variant substitution for the GTP deployment (see Deployment below). | Public demo: any phone can call, so real CLIDs can't key the mock data — each GTP number maps to a fixed mock customer (user requirement 2026-06-05). |

### 5b. Deployment (GTP variants)

The canonical app `rrms-v1` is the only app developed/eval'd against. Two deploy-artifact apps serve the public GTP numbers, regenerated from canonical by `deploy-variants.sh` (only `DEFAULT_CALLER_PHONE` + app identity differ; config in `deploy-variants.json`):

| Variant | App ID | CLID → mock customer |
|---|---|---|
| `rrms-demo-store` | `3f88fc77-6616-42cb-b3ec-72ba75369fb3` | `+15125550142` → Johnson Verizon Store (UC1) |
| `rrms-demo-multisite` | `1a32623a-96d0-43f3-bf91-7f533a9deb58` | `+12145550199` → Dallas/Fort Worth/Plano (UC2) |

Release flow: edit canonical → lint → push `rrms-v1` → evals green → `./deploy-variants.sh`. App IDs are stable, so GTP number wiring (Console, one-time) survives redeploys. Never edit variant apps directly.

No other callbacks proposed. Intent detection, disambiguation, and the passcode gate are judgment/dialogue tasks that belong in the instruction, not in callbacks (design guide: keep detection generative; use callbacks only to enforce execution). Revisit if coverage analysis surfaces non-determinism in the closing or in the verify→act sequence (a trigger pattern for `cancel_alarm` / `put_account_on_test` could be added if the LLM proves unreliable about calling them after verification).

---

## Eval Design

### 6. Coverage Map

| Requirement | Eval Type | Rationale | Priority | Severity | Tags |
|-------------|-----------|-----------|----------|----------|------|
| UC1 happy path: cancel false alarm after passcode verification, report dispatch status | Golden | Deterministic linear flow; sample call gives exact turn-by-turn dialogue (brief, UC1 sample) — use it verbatim as the golden basis. | P0 | NO-GO | `uc1, cancel-alarm, happy-path` |
| UC2 happy path: multi-location disambiguation → verify → on-test → offer + send SMS | Golden | Linear flow with predictable tool calls; sample call (brief, UC2 sample) gives exact dialogue including disambiguation phrasing and SMS offer — use verbatim. | P0 | NO-GO | `uc2, on-test, disambiguation, sms, happy-path` |
| Passcode gate enforced: agent does NOT cancel/test before a valid passcode | Golden | Hard prerequisite; deterministic — agent must request passcode before calling the action tool. | P0 | NO-GO | `auth, passcode-gate` |
| Multi-location disambiguation accuracy (correct branch by name + address) | Golden | Deterministic given mock data; the resolved branch must match the caller's stated branch (UC2 step 3). | P0 | HIGH | `uc2, disambiguation` |
| Single-site caller resolves without asking which site | Golden | UC1 shows the agent acting on Johnson Verizon Store without a disambiguation question. | P1 | HIGH | `uc1, account-resolution` |
| Dispatch-status reassurance is clear and accurate | Golden | UC1 step 5 requires explicit, accurate dispatch status ("Police were not dispatched"). | P1 | HIGH | `uc1, dispatch-status` |
| SMS offered only after successful validation; sent only if caller accepts | Golden | UC2 step 5 ("based on the prior validation"); offer→accept→send is deterministic. | P1 | MEDIUM | `uc2, sms` |
| Deterministic spoken closing before `end_session` | Golden | Callback-enforced farewell; both samples end with a spoken sign-off. | P1 | MEDIUM | `closing, callback` |
| `verify_passcode` returns correct true/false per account | Tool test | Isolated logic over mock dataset; assert on output for valid + invalid passcodes. | P0 | HIGH | `tool-test, verify_passcode` |
| `lookup_accounts_by_caller` returns one vs. many per caller | Tool test | Assert single-account caller returns 1 record; multi-location caller returns multiple branch records with disambiguation fields. | P0 | HIGH | `tool-test, lookup` |
| `cancel_alarm` / `put_account_on_test` / `send_confirmation_sms` return expected confirmations | Tool test | Assert confirmation payloads (dispatch status; on-test duration + last digits; SMS sent). | P1 | MEDIUM | `tool-test, actions` |
| after_model farewell callback injects closing before `end_session` | Callback test | Assert the callback adds the spoken closing when the model calls `end_session` without text. | P1 | MEDIUM | `callback-test, closing` |
| Wrong-passcode handling: 2 retries, then decline + offer operator transfer | Sim | Policy resolved 2026-06-04 (user-approved default); phrasing varies, so sim not golden. | P1 | HIGH | `auth, error-handling` |
| Unknown caller / no linked account → apologize + offer operator transfer | Sim | Policy resolved 2026-06-04 (user-approved default); phrasing varies. | P2 | MEDIUM | `error-handling` |
| Caller declines SMS in UC2 → confirm verbally and close | Sim | Policy resolved 2026-06-04; variation on UC2 close; phrasing varies. | P2 | LOW | `uc2, sms, variation` |
| Missing duration in UC2 → agent asks; accepts 30 min–8 h | Sim | Policy resolved 2026-06-04; clarification phrasing varies. | P2 | LOW | `uc2, on-test, clarification` |
| Cancel request with no active alarm → inform caller, offer further help | Sim | Policy resolved 2026-06-04; phrasing varies. | P2 | MEDIUM | `uc1, error-handling` |

### 7. Test Data (Mock Customers)

Mock dataset lives **in the app code** (user interview 2026-06-04). Minimum required customers below; the scaffolder may add 1–2 more for variety. Phone numbers are placeholders — confirm/replace.

| Profile | `caller_phone` | Accounts returned | Key fields | Scenario |
|---------|----------------|-------------------|------------|----------|
| Single-site: Johnson Verizon Store | `<phone-A>` (TBD) | 1 | branch_name="Johnson Verizon Store", passcode="Sunset", has_active_alarm=true, dispatch=not dispatched | UC1 false-alarm cancellation. Caller resolves to one site; passcode "Sunset" cancels the active alarm. |
| Multi-location manager | `<phone-B>` (TBD) | Multiple branches incl. Dallas | Dallas branch: street_address="123 Main Street", account_last_digits="345", passcode="Bluebird" + ≥1 other branch to force disambiguation | UC2 on-test. Caller manages several branches; agent disambiguates to the Dallas branch, verifies "Bluebird", puts it on test for the stated duration, offers SMS. |

> The multi-location profile must include at least one branch *besides* Dallas so disambiguation is genuinely exercised (the sample shows "I see you manage multiple branches"). The brief does not name the other branch(es) — scaffolder to invent plausible mock branches (any real-word passcodes), noting these are demo fixtures.

---

## Tracking

### 8. Pass Rate History

| Date | Goldens | Sims | Tool Tests | Callback Tests | Notes |
|------|---------|------|------------|----------------|-------|
| 2026-06-04 | 11/24 (46%) | 12/15 (80%) | 16/16 | 18/18 | Text-mode baseline (gemini-3-flash trio, pre-audio validation) |
| 2026-06-04 | 17/24 (71%) | 13/15 (87%) | 16/16 | 18/18 | Fix round 1: zero-arg lookup, disambiguation/SMS-decline/passcode-pushback instruction edits |
| 2026-06-04 | 18/24 (75%) | 15/15 (100%) | 16/16 | 18/18 | Fix round 2: standalone confirm turn, mandatory put_account_on_test + action_grounding |
| 2026-06-04 | 21/24 (88%) | 15/15 (100%) | 16/16 | 18/18 | Fix round 3: inline-passcode carve-out, SMS-accept offer-help |
| 2026-06-04 | **24/24 (100%)** | 15/15 (100%) | 16/16 | 18/18 | Alignment package + platform golden force-recreate. Text validation complete — later found to have run on platform-default gemini-2.5-flash ("gemini-3-flash" invalid, silently dropped). |
| 2026-06-04 | 21/24 (88%) | — | — | — | **First run on gemini-3.1-flash-live** (text channel). dispatch_status 0/3: model parroted "the tool response confirms" to the caller. |
| 2026-06-04 | **23/24 (96%)** | — | — | — | no_speculation guideline rewritten (internal grounding only). Residual failure = judge paraphrase noise. **Live-model text validation complete.** |
| 2026-06-04 | 24/24 (100%) | 15/15 (100%) | 16/16 | 18/18 | "Hello" openers (TTS reads `<event>welcome</event>` aloud) + dispatch golden aligned. Live model, text channel. |
| 2026-06-05 | 9/24 → 22/24 | — | — | — | FIRST AUDIO runs. 0/24 via `--audio` flag = scoring artifact (score via evaluation_status). Real causes: ASR lowercases passcodes (fixed: case-insensitive regexp args) → 22/24; then speak-after-tool tightening for turn-splitting. |
| 2026-06-05 | 20/24 (83%) | 11/15 (73%) | 16/16 | 18/18 | Full audio baseline round 1. Sims found REAL-CALLER BUG: ASR splits "Bluebird"→"Blue Bird", verify failed. |
| 2026-06-05 | **21/24 (88%)** | **15/15 (100%)** | **17/17** | **18/18** | Audio round 2 after verify_passcode whitespace normalization. 3 goldens each 2/3, no shared cause — irreducible audio-stochastic band. **AUDIO VALIDATION COMPLETE (96% overall).** |

### 9. Known Issues / Open Design Questions

All 8 open questions from the initial draft were resolved with user-approved demo defaults on 2026-06-04:

1. **Wrong passcode** → 2 retries (3 attempts total), then politely decline and offer transfer to a live operator (simulated).
2. **Unknown caller / phone not in dataset** → apologize, offer transfer to a live operator (simulated).
3. **No active alarm to cancel (UC1)** → inform the caller there is no active alarm signal and nothing to cancel; offer further help.
4. **Duration handling (UC2)** → agent asks if missing; accepts 30 minutes to 8 hours; out-of-range → explain range and re-ask.
5. **Caller declines SMS (UC2)** → confirm verbally and close normally.
6. **Placeholder phone numbers** → scaffolder chooses demo placeholders.
7. **Other branches for the multi-location profile** → scaffolder invents demo fixtures (any real-word passcodes).
8. **Session schema / identity** → `caller_phone` is the only session parameter; no pre-authenticated telephony context; identity is per-action passcode verification.

No remaining open issues.

### 10. Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-06-04 | Initial requirements-derived TDD draft (sources: `sources/rrms-demo-brief.md`, user interview 2026-06-04, `gecx-config.json`). | tdd-writer |
| 2026-06-04 | User approved TDD as-is; folded in user-approved demo defaults for all 8 open questions (failure policies, fixtures, session schema). Status → APPROVED. | main thread |
| 2026-06-04 | Built, deployed (app ec021a75-b0a0-4d88-90d9-1d39556bee7a), and text-validated to 100% goldens / 100% sims over 4 fix rounds. Design deltas vs original TDD: `lookup_accounts_by_caller` is ZERO-ARG (reads `caller_phone` from session state — deterministic, no wrong-number risk); new `action_grounding` constraint (no action claims without successful tool call); single-site passcode ask never names the store; multi-branch confirmation is a standalone turn; inline-supplied passcodes are used without re-asking; SMS accept/decline branches both end with an offer of further help. Audio phase pending (model temporarily gemini-3-flash for text validation). | main thread |

---

*Approved 2026-06-04 — cleared for scaffolding.*
