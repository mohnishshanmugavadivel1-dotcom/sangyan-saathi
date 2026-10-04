# Safety-reliability sprint (2026-10-05) — what changed and what did not

Scope: three small, reversible changes to classification and incident reading, each with regression tests and counterexamples. No new features, no vendor or brand rules, no fixture, benchmark-result or existing-test changes. These are the author's own checks, not independent validation; the validation verdict remains INCONCLUSIVE.

## Changes
| ID | File | Change | Why |
|---|---|---|---|
| S-1a | `saathi_rc/incident.py` | New Hindi/Hinglish rule: first-person subject + credential term + entry verb ("daal diya", "bhar diya", "डाल दिया"...) + a link or "SMS/WhatsApp/message ke/se..." marker reads as `USER_SHARED_CREDENTIAL`. Negation, advice, hypothetical, future and reported-speech words block it. | "maine apna card number aur CVV SMS ke link pe daal diya" was HIGH_CONCERN with no incident and no urgent steps. The English rule (entry on an externally sourced page) had no Hinglish equivalent. |
| S-1b | `saathi_rc/incident.py` | A possessive ("mera/apna/मेरा") directly before a credential term, with a share verb and no third-party subject ("ne", "unhone", "bank"), counts as the user's own share. | "mera OTP unhe share kar diya" had no readable subject, so no incident was created. |
| S-1c | `saathi_rc/incident.py` | Hinglish/Hindi "from my account ... nikal/kat" and "bina mere bataye / मुझे बताए बिना" are read as an unauthorised debit. A bare "paise kat gaye" is deliberately NOT escalated. | Unauthorised-debit reports in Hinglish got only a follow-up question. |
| S-2 | `saathi_rc/cues.py`, `saathi_rc/engine.py` | `link_threat_pattern`: link + an action word + a stated consequence ("will be cut/blocked/expired...") moves CANNOT_ASSESS to SOME_CONCERN, never to HIGH, and never from ABSTAIN. | S1 case C13 (utility-cut threat with a link) got no concern signal although the safe steps apply. |

## Not changed (documented)
* A04 (genuine "I transferred the school fee" gets a follow-up) and the Zomato browser failures: all share one incident route (`USER_PAID` / `incident_paid_unconfirmed`); the engine state is identical for benign, genuine and look-alike inputs, so no fix without a brand whitelist or weaker incident logic.
* B07: SOME_CONCERN instead of the expected HIGH_CONCERN. By design (CH-02: never HIGH from structure alone); steps are still shown.
* C05 (advance-fee, ASK_FOLLOWUP, safe direction), C06 (romance/crypto "deposit a little": CANNOT_ASSESS, no safe pattern found), H07 (Bengali: honest abstention, unsupported script).

## New or confirmed gaps
* "maine SMS se aaye page pe OTP daal diya" (page, not link) is still not read as an incident (HIGH_CONCERN, no urgent steps).
* "maine payment link pe OTP daal diya" for one's own purchase is escalated (the link marker cannot tell a genuine payment link from a phishing link); the steps are contact-your-bank and 1930.
* The S-2 consequence wording is English only; "बिजली आज रात कट जाएगी, लिंक पर क्लिक करें" still gets CANNOT_ASSESS.
* Pre-existing: "Your subscription expires on 30 Oct. Renew in the app." gets SOME_CONCERN because "30" is read as a number to act on.
* Devanagari "सीवीवी" is not in the credential lexicon (card number alone triggers); "मैंने कार्ड नंबर और सीवीवी डाल दिया" (no link) stays a follow-up question.

## Results (before → after)
Unit 173 OK + 1 expected failure → 183 OK + 1 expected failure (10 new). S1 (n=79): critical_unsafe 0 → 0, incorrect_classification 6 → 5 (C13 fixed), missing_guidance 0, technical_failure 0. Differential over 389 cases in six eval sets: 1 changed (C13). Sprint 53/54, fail R03 (unchanged). Mutation 0 missed (unchanged). Live 27/27, smoke 26/26, browser_final 138 checks with the same 3 Zomato failures, browser_check no failures.
