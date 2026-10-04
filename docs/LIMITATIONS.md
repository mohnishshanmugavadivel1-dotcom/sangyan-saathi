# Limitations and known failures (v0.4.0-rc2)

Labels: **Established** = reproduced in the development or release-preparation runs; **Unknown** = never measured; **Unverified** = could not be checked.
This file is a curated summary of the development-history limitation list and of the rc2 verification findings. Where an older statement was superseded by rc2, that is said explicitly. Result files cited in the older list (for example `results/s3/...`) are not part of this repository.

## 1. Open safety-relevant misses (do not demo as emergency coverage)
1. **R03 (Established, open):** `I paid the registration amount, then they added a GST charge, then a compliance charge.` returns `ASK_FOLLOWUP` / `USER_PAID` with questions only, no urgent block. A test documents it as an expected failure.
2. **Card details typed after a WhatsApp link (Established):** `I entered my debit card number, expiry and CVV on the link that came in a WhatsApp message.` returns follow-up questions only. (The rc2 credential-entry rule needs wording such as a page or site from an SMS or message; some other phrasings, for example `I entered my UPI PIN on the page the caller sent.`, now escalate. This supersedes an older note that said they did not.)
3. **Hinglish card-detail report (Established):** `maine apna card number aur CVV SMS ke link pe daal diya` is `HIGH_CONCERN` with no urgent block; rc2 has no Hinglish credential-entry rule.
4. **Repeated fees without "I paid" (Established):** `After paying the demat charge, they kept adding new fees every few days.` is not escalated.
5. **Bare code requests (Established):** `Read out the code we send you to confirm your KYC.` is `CANNOT_ASSESS`; a code request is recognised only with a term such as OTP or verification code.
6. **Subject-less, passive or telegraphic reports** create no incident state by design unless rc2's narrow subject-less route applies (a completed payment plus structural risk context).
7. **Selecting a harm situation always escalates**, so the situation choice is the strongest safety control; text-only detection depends on regex rules.

## 2. Over-escalation and friction (Established, mostly not tuned away)
* Ordinary extra-charge payments escalate (`Paid 2,000 advance to the plumber; he asked for 300 more for parts.`, trade-offs B07/B08).
* Past-tense hypotheticals escalate (`If I paid 15,000 would they ask for more?`).
* Any `I will pay ...` text gets a stop-payment step (including bills); P04.
* Ordinary payments get follow-up questions and a red conditional block (`I paid 1,200 to Zomato via UPI`).
* A genuine OTP message (`Enter OTP 482913 to verify your login`) is rated `HIGH_CONCERN`: text cannot tell it from a fake one. Education or warning text containing "guaranteed returns" is flagged.
* The tool never tells a user a message is fine, so genuine messages get no reassurance and users may stop using it.

## 3. Detection limits
* Rules are regexes and fixed word lists; paraphrases outside them are missed (the result then says it could not assess, or asks follow-up questions). Negation uses a short window. Clause splitting is on commas and conjunctions.
* Posture weights are author-chosen and uncalibrated.
* Image or OCR input is not implemented.
* Recovery-scam ("fund recovery agent") guidance is not provided because no corpus source supports it.

## 4. Languages
English is the tested language. Hindi and Hinglish patterns and **all Hindi interface text, labels and guidance were written by the engine's author and not reviewed by a fluent speaker** (including the rc2 label for subject-less payments). Marathi and Tamil have very small keyword lists. Bengali, Telugu, Gujarati and other languages are not read; links and similar signs are still seen and the result says so. The form offers English and Hindi output only. No language is claimed as fully supported.

## 5. Evidence and sources
* **Excerpts removed in this variant:** the result page shows each source's title and link, not what the source says. A user cannot see on the page why a source was matched to a claim, and the claim state (for example "Contradicted by trusted sources") rests on the author's hand-made claim-to-source table, which the user can only check by opening each link. Matching of sources to a message uses titles and topic tags only, so it may differ from the earlier package on messages outside the 392 shipped examples.
* The corpus is a fixed snapshot dated 2026-10-02: 42 sources (10 official, 4 reproductions of official statements, 28 news or other secondary). It does not update itself; a rule change after the snapshot date cannot be detected.
* Several cited next-step sources are commercial or secondary pages (their tier is displayed; their accuracy was not independently checked). The About page (corrected in this release) now says some sources are official and others are news or commercial pages. The English and Hindi About wording was edited in this release; the Hindi edit is, like all Hindi text, not reviewed by a fluent speaker.
* Of 12 external links on three rendered pages, one official page was loaded, one commercial page was loaded, one returned a 504 on a single attempt, and nine were not checked.
* No endorsement by SEBI, NSDL or the organisers of any text is claimed or verified.

## 6. Registry step
* Some message strings in `saathi_rc/registry/contract.py` (for example "SEBI's website did not answer in time") remain from the earlier package. They cannot be reached in this variant, because nothing contacts SEBI, but they are still covered by the unit tests.
* This variant has no live SEBI lookup at all; the register step is a synthetic demonstration. (The earlier package's live client depended on an undocumented SEBI form without permission, which is why it was removed.)
* A match shows that an entry exists, not who contacted the user. Name matching is conservative (`CONFIRMED` only on identical normalised names).
* The fixture register stops returning results (`SOURCE_STALE`) from the real date 2026-10-10; `SAATHI_TODAY` does not affect this.
* The JSON registry response in fixture mode has no DEMO flag; only the HTML banner marks it. The card text under the banner still reads like a live-register statement (the banner now also says nothing was checked against SEBI and that a real number shows "not found"); a person who ignores the banner could misread it.

## 7. Display and documentation defects found in rc2 (not fixed in this release)
* The label "(listed below)" can point to a list that is not rendered; one quote can appear twice.
* An oversized request returns an HTML error page even on the JSON route.
* Docstrings and comments refer to directories (`poc/`, `rc/`, `v0_3/`) and a changelog not included here. Some `eval/` scripts of the development history were left out because they need removed files.

## 8. Operations and process
* Local use only: no TLS, authentication, hosting, monitoring or load testing. Rate limiting keys on the socket address (users behind one proxy share a key). `HOST` defaults to `127.0.0.1`; setting `0.0.0.0` exposes an unauthenticated server.
* No user testing, pilot, independent evaluation or evidence of effect on losses.
* Read-aloud depends on the browser voice and was not tested on real devices; browser checks used headless Chromium on an earlier build (rc1), and were not run on rc2.
