# RRMS v1 — Build Checklist

Build Steps (from references/build.md → Full Build):

- [x] 1. Gather requirements (gate 1) — brief saved to sources/rrms-demo-brief.md; config confirmed (yves-normandin-project/us, app rrms-v1, audio, English-only)
- [x] 2. TDD + user approval (gate 2) — approved 2026-06-04; 8 open questions resolved with demo defaults
- [x] 3. Scaffold app (gate 3) — status: complete; 14 files (1 agent, 5 tools, 1 callback); manifest at scaffold-manifest.json
- [x] 4. Lint clean (gate 4) — status: clean after 2 iterations (T001, I014, T004 fixed); summary at lint-summary.json
- [x] 5. Generate evals (gate 5) — 8 goldens, 5 sims, 16 tool tests, 1 callback test (18 pytest cases, all passing); all Coverage Map CUJs covered; 4 eval-writer dispatches
- [x] 6. Push + verify (gate 6) — pushed (app ec021a75-b0a0-4d88-90d9-1d39556bee7a); gate-check ALL PASS (5 passed, multi-turn skipped); fixed app_dir in gecx-config.json
- [ ] 7. Run baseline (post-gate-6) — user directive: validate TEXT goldens before audio
  - [x] 7a. First audio attempt errored: goldens.yaml parse error (empty common_session_parameters → None) + sims skipped (default --priority P0, all sims are P1/P2). Tool tests 16/16, callback tests 18/18 passed.
  - [x] 7b. Fixed goldens.yaml; switched app+config to TEXT mode (gemini-3-flash trio, gcs_bucket removed); lint clean; pushed.
  - [x] 7c. Text validation run 1 — 78% (goldens 11/24, sims 12/15, tool 16/16, callback 18/18); 5 clusters triaged
  - [x] 7c-fix. Fix round 1 applied (zero-arg lookup, 3 instruction edits, eval/tool-test updates); lint clean; pushed
  - [x] 7c-rerun. Text validation run 2 — 88% (goldens 17/24, sims 13/15); uc1/sms_declined/dispatch_status/single_site fixed; 4 new clusters triaged
  - [x] 7c-fix2. Fix round 2: standalone branch-confirm turn (fort_worth regression), mandatory put_account_on_test + action_grounding constraint (uc2 + declines_sms hallucinated action), passcode_gate golden text aligned (user-approved); stale nested pull artifact cxas_app/rrms-v1/rrms-v1/ deleted; lint clean; pushed
  - [x] 7c-rerun2. Text validation run 3 — 92% (goldens 18/24, sims 15/15, tool 16/16, callback 18/18); 2 failures left, both confirmed by user in Console
  - [x] 7c-fix3. Fix round 3: inline-passcode carve-out + standalone-turn scoping (deterministic_spoken_closing regression), SMS-accept branch confirm+offer-help (uc2); lint clean; pushed
  - [x] 7c-rerun3. Text validation run 4 — 96% (goldens 21/24, sims 15/15); deterministic_spoken_closing + uc2 fixed
  - [x] 7c-user. User hand-edited a golden + instruction ("do NOT confirm the site"); goldens-only text run 5 → 22/24, uc1 1/3 (stale platform golden args + uc1/passcode_gate contradiction on store-name mention)
  - [x] 7c-fix4. Alignment package (user-approved): instruction = no store name on single-site passcode ask; passcode_gate golden → generic text; uc1 cancel turn += "Anything else I can help with?"; platform goldens force-recreated; lint+push done
  - [x] 7c-rerun4. Goldens-only text run 6 — **24/24 (100%)**, all 8 goldens 3/3. TEXT VALIDATION COMPLETE (sims 15/15, tools 16/16, callbacks 18/18 as of run 4)
  - [ ] 7d. Revert to AUDIO mode (gemini-3.1-flash-live trio + gcs_bucket gs://yves-normandin-cxas-evals), lint, push, run audio baseline
  - [ ] 7e. Update TDD Pass Rate History + Changelog
