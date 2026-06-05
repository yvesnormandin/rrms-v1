# RRMS Demo Agent — Requirements Brief (provided by user, 2026-06-04)

## Overview

Telephone (voice) customer service demo agent for **Rapid Response Monitoring Services Inc.** (https://www.rrms.com/), a professional alarm-monitoring company. Built on CX Agent Studio via cxas-scrapi.

Two use cases:
1. **False Alarm Cancellation (8 AM Rush Hour)**
2. **Multi-Location "On Test / No Action"**

## Demo constraints

- All customer data must be **mocked** — create mock data for a few sample customers when building the application.
- Passcodes can be any real word.

## Use Case 1 — False Alarm Cancellation

Scenario steps:
1. Caller explains they accidentally set off the alarm when opening the premises this morning.
2. System detects intent to cancel the alarm and begins the cancellation process.
3. Caller provides passcode for verification (identity + authority to cancel).
4. System validates passcode and immediately cancels the alarm, preventing unnecessary dispatch.
5. Caller is reassured whether dispatch occurred or not — clear status, positive experience.

### Sample call

- Monitoring Service: Rapid Response Monitoring. How can I help you today?
- Caller: Hi, so I just opened my store and I accidentally set off the alarm. Would you be able to cancel that for me please?
- Monitoring Service: Of course. Could you please provide the passcode for verification?
- Caller: Yes, that passcode is Sunset.
- Monitoring Service: Thanks, verified. The alarm at Johnson Verizon Store has been canceled. Police were not dispatched.
- Caller: Great, that's perfect. Thank you.
- Monitoring Service: You're all set. Have a good day.
- Caller: Bye.

## Use Case 2 — Multi-Location "On Test / No Action"

Scenario steps:
1. Caller requests to put a specific branch/location on test — states branch name and duration in their own words.
2. System recognizes multiple accounts tied to caller's phone number (one number linked to many sites).
3. System disambiguates by confirming the correct branch/location conversationally.
4. Caller provides passcode for verification (standard security check before action).
5. System validates and confirms the test, offering SMS confirmation based on the prior validation.

### Sample call

- Monitoring Service: Rapid Response Monitoring, how can I help you today?
- Caller: Hey, so I need to put the Dallas branch on testing for one hour.
- Monitoring Service: I see you manage multiple branches. Did you mean the Dallas branch at 123 Main Street?
- Caller: Yes.
- Monitoring Service: Great. Please provide the account passcode to confirm.
- Caller: Bluebird.
- Monitoring Service: Thanks, verified. The Dallas branch account ending in 345 is now on test for one hour. Would you like me to send a confirmation text as well?
- Caller: Please.
- Monitoring Service: Done. A confirmation has been sent. Anything else today?
- Caller: Nope.
- Monitoring Service: All right, have a great day.
