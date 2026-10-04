# Privacy and data

## What the application does with user input
* The message check runs in memory on the server process. The source contains no database, file write, cookie, analytics or access-log code (`log_message` is a no-op; the exception handler logs the exception type only).
* In release-preparation runs (fixture mode, no network), a probe request containing a unique marker, a test card number, OTP, PAN-shaped, account and phone-like strings left the marker and digits in no file under the user's directories and not in server stderr (from the earlier rc2 verification; **not re-run for this repository** except that the server's stderr held only the start-up line). This supports "not written to disk or logged **on the paths exercised**". It does **not** support "never stored or logged": OS, proxy, crash-dump and hosting-layer logging were not examined (this variant has no live mode).
* The follow-up page shows the user's own pasted text back in an editable box (HTML-escaped). Long digit runs are masked in quoted snippets; 3-digit CVV and 6-digit OTP values are not.
* The page asks users not to paste OTPs, PINs or card numbers.
* This variant has no live registry mode and no network client: the register step only reads invented fixture entries. No outbound requests were observed in a network-less test environment.
* Alignment with the hackathon's "no unauthorised harvesting" guardrail is a self-assessment, not an external review.

## What data is in this repository
| Data | Where | Nature |
|---|---|---|
| Register fixture (8 entries) | `eval/registry_fixture.json` | **Synthetic** invented names and numbers, not SEBI data. One trade name ("Kuber Alpha Research") may coincide with a real trade name; origin unverified. |
| Source list (42 sources) | `saathi_rc/sources/corpus.json` | **Real third-party references**: publisher names, page titles and URLs (snapshot 2026-10-02). Excerpt text was removed in this variant; titles and URLs are still third-party material and have not been cleared with their publishers. |
| Author-written case sets (392 cases) | `eval/cases_*.jsonl`, `results/incident_state/raw_results.jsonl` | Invented messages. A case-insensitive search of this release found **no real adviser registration numbers and none of the real SEBI-registered firm names that were found elsewhere in the development workspace**. Benign real consumer brands (for example Zomato, Netflix, Amazon, Reliance Retail) appear in some example messages. |
| Test values | `tests/`, `eval/` | Fake-looking UPI handles, 98765xxxxx phone numbers, the public test card pattern 4111 1111 1111 1111 and PAN-shaped strings. Appear synthetic; not verified against real people. |

**Left out of this release on purpose** (kept in the development workspace): recorded real SEBI register lookups (129 real entities, including individual proprietors), scam-style test messages that name real registered firms and their real registration numbers, saved result pages from a live-mode run, the live SEBI client itself, and the development-history reports.

Do not describe the whole repository as "entirely synthetic": the source list holds real third-party titles and URLs, and the owner's decision on the third-party items is documented in the release-preparation report.
