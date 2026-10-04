# Adversarial validation of the 2026-10-05 safety rules — summary of the two changes in this copy

Full report: the `adversarial_validation/` folder beside this candidate (dataset, labelling rationale, results). The datasets are author-written (ADV-1: 142 diagnostic cases; ADV-2: 46 held-out cases written after the root-cause analysis and before any ADV-2 run) and are not independent validation.

* **P1 (`saathi_rc/cues.py`)**: the link-plus-consequence rule (S-2) no longer treats plain expiry, lapse, cancellation or penalty wording as a consequence. On ADV-1 it had flagged 5 of 19 routine link-plus-deadline reminders and caught no scam that was not already flagged; on ADV-2 it flagged 4 of 10. Cost, measured on ADV-2: a scam worded "your number will expire ... click" is no longer caught by this rule (1 of 5 ADV-2 threat cases).
* **P3 (`saathi_rc/incident.py`)**: "unhe" (to them) was listed as a third-party subject, so "maine unhe apna OTP bata diya" was not read as the user's own share. It is now treated as a recipient.

Not changed (evidence in the report): see `docs/LIMITATIONS.md` section 10.
