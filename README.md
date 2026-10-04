# Sangyan Saathi (v0.4.0-rc2): research prototype

A situation-first, rule-based check for suspicious investment messages, with an optional and separate demonstration of a registration-number lookup (synthetic demo data only).

> **Reduced-third-party variant.** Compared with the earlier staging package, this variant (a) contains **no client for SEBI's website** (no code in it queries sebi.gov.in), and (b) contains **no source excerpts**: the 45 cited source entries (29 distinct pages) are kept as publisher, title, URL, tier and date only (the titles are themselves third-party text), and the result page shows the title and a link instead of an excerpt. This is a technical precaution. It does **not** by itself resolve any copyright, licence, permission or regulatory question (titles and URLs are also third-party material), and it does not replace the owner's own decisions on those questions.

> **Research prototype.** It is not a fraud detector, not an official SEBI or NSDL service, gives no investment advice, and has **not been validated by independent evaluators or tested with users**. It is **not endorsed** by SEBI, NSDL, IIT (BHU) or any regulator, and it is not a substitute for official financial or cybersecurity assistance. It never says a message is genuine or safe and it never promises recovery of money. **If money may already be lost or a code or password shared, contact your bank and call 1930 (National Cyber Crime Helpline) straight away.**

> **Status (v0.4.0-rc2, 2026-10-05):** this repository is public and this is a **research prototype**. The tree is the earlier public baseline plus the demo fixes described here and in `docs/LIMITATIONS.md`: official RBI/NCRP/SEBI sources in the next-steps panel where an official page directly supports the step (unresolved items are listed in `docs/LIMITATIONS.md`), de-duplicated conditional steps, a priority-ordered urgent block (bank, then 1930 / cybercrime.gov.in, then evidence), an uncertain-incident ("one question first") page with the same order, a text-box placeholder that tells users not to include OTPs, passwords, PINs or account details, **demo-only wording** for the registration checker in English and Hindi (it uses invented sample data, does not contact SEBI and cannot verify any real registration), registration-checker wording that states, in English, that the data is made-up (synthetic), nothing is queried at SEBI or NSDL and no real registration can be verified, the English "risk (listed below)" label now followed by the risk it names, and, in English only, a plain-language lead on the "not enough information" (`CANNOT_ASSESS`) result page (the backend state and text are unchanged; no new Hindi text was added). Detection rules and incident logic are unchanged. It is not validated, not endorsed by any regulator and not production-ready. Verdict of the validation sprint: **INCONCLUSIVE**. Exact demo launch command: `cd <this directory> && HOST=0.0.0.0 PORT=8000 python3 -B -m saathi_rc.web.app` (localhost-only default: `bash run_web.sh`).


> **Licence: none chosen yet.** This repository has no LICENSE file because the project owner has not made a licensing decision (the hackathon's intellectual-property terms have not been resolved). Do not assume any reuse rights until a licence is added.

## Problem and user journey
People receive investment "tips", "SEBI-registered adviser" claims and payment demands over WhatsApp, Telegram, SMS and calls. The first question that matters is not "is this message a scam?" but "what has already happened to me?".

1. The user chooses a situation (nothing done yet / payment pending / paid / shared a code or password / granted access / unsure) and pastes the text.
2. The tool reads who did what in the text and shows the words it relied on. It lists warning signs (pattern matches, **not proof**) and compares claims with a fixed, hand-made list of 45 cited source entries on 29 distinct web pages (19 entries from official sources, 26 from news or other secondary pages; see `docs/LIMITATIONS.md` section 5) (publisher, title, link and evidence tier are shown; the sources' own text is not included in this variant, so a user must open the link to read what the source says).
3. It gives generic next steps. If money or credentials may be at risk, bank and 1930 come first; for a pending payment, "stop the payment" comes first.
4. Separately and only on request, the user can look up a registration number (see "Registry step").

## What a registry match does NOT mean
A match shows only that an entry with that number and name exists in the list consulted. It does **not** show who contacted you, does not authenticate the sender, does not validate any investment offer or return, and does not show that a transaction is safe. Scammers can quote real registration numbers. The UI says this, but **whether users understand it was never tested.**

## Architecture
Pure Python standard library at run time (Python 3.10+; **3.13.14 is the only version tested**). A threaded stdlib HTTP server renders pages server-side. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```
saathi_rc/engine.py, journey.py, incident.py, cues.py, validate.py   situation gate, incident reader, fail-closed validator
saathi_rc/core/        claim/indicator pipeline over the fixed source corpus (no network, no model calls)
saathi_rc/registry/    register step demonstration (fixture | off); no live SEBI client
saathi_rc/sources/     corpus.json (45 source entries on 29 distinct pages: publisher, title, URL, tier, dates; no excerpt text), official_domains.json
saathi_rc/web/         app.py (server) and views.py (HTML)
eval/                  author-written case sets, runners, scorer, synthetic register fixture
tests/                 unit, web, mutation tests
```

## Setup and run (fixture mode is the default; no network needed)
```bash
python3 --version        # 3.10+; 3.13.14 tested
# no packages are needed in fixture or off mode
bash run_web.sh          # http://127.0.0.1:8000  (fixture mode, localhost only)
curl http://127.0.0.1:8000/healthz
# expected: {"status": "ok", "version": "0.4.0-rc2", "registry_mode": "fixture"}
```
**Environment variables** (all optional):

| Variable | Default | Meaning |
|---|---|---|
| `SAATHI_REGISTRY` | `fixture` | `fixture` = built-in synthetic register, labelled DEMO; `off` = register step disabled. Any other value, including `live`, is treated as `off` (this variant has no live SEBI client) |
| `HOST` | `127.0.0.1` | Bind address. Setting `0.0.0.0` exposes the server to your network |
| `PORT` | `8000` | Port |
| `SAATHI_TODAY` | real date | Pins the date used by the message check only |

The server has no TLS, no authentication and no monitoring: **do not deploy it as-is.**

### Synthetic demonstration
In the form, choose "unsure" and paste: `Paid 15,000 to an unknown account and now he is asking for 15,000 more.` The result is an escalation with bank and 1930 steps first (state `PAYMENT_UNCLEAR`, the text does not say who paid). Then open the register step and enter the **synthetic** number `INA000000201`: the fixture returns an entry for an invented firm, shown under a red "DEMO DATA" banner. Any real registration number will show "not found" in fixture mode, because only invented entries exist there; that result says nothing about the real number. All numbers and names in `eval/registry_fixture.json` are invented for tests. One trade name in it ("Kuber Alpha Research") may coincide with a real trade name; its origin is unverified.

API equivalents: `POST /api/check` with `{"situation","text","output_language"}`, `POST /api/registry` with `{"situation","number","name","output_language"}`. Note that the JSON registry response does not carry the DEMO flag (the HTML page does).

### Registry step (demonstration only)
This variant contains **no code that contacts SEBI** and no recorded SEBI data. The register step runs only against the invented entries in `eval/registry_fixture.json`, under a red "DEMO DATA" banner. Setting `SAATHI_REGISTRY=live` does not enable anything: the server prints a note on stderr and the register step stays off. In fixture mode the form, button, card headline, card text and source line all say "demo" / "sample data, not SEBI" (English and Hindi; display-level wording only, the backend result is unchanged), so a result cannot be read as a live SEBI lookup. A registration number should be checked by the user on sebi.gov.in, as the result pages say. Not having a live client is a limit of this variant, not evidence that a live lookup would work or be permitted.

Fixture date limit: the fixture register returns `SOURCE_STALE` ("no result given") from **2026-10-10** on the real date. `SAATHI_TODAY` does not change this (verified in this release preparation).

## Tests and evaluation
```bash
python3 -B -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py"   # 173 tests, OK, 1 expected failure (R03)
python3 -B tests/mutation_incident.py all                                           # last line: "mutations NOT caught: 0"
python3 -B eval/run_sprint.py "$PWD" /tmp/sprint.json                               # scored 54, pass 53, fail ['R03']
```
No network is needed for any of these. They were run in a clean copy of this tree with outbound network blocked and `requests` made unimportable (this variant does not use it at all). The logs belong to the release-preparation notes, not to this repository. **This proves the code behaves as its own tests expect; it is not an accuracy measure.**

Evaluation method and limits: [docs/EVALUATION.md](docs/EVALUATION.md). In short, **every case set was written by the same author as the engine**; the 45-case "fresh" set was used once on the earlier build (rc1) and was **burned** when rc2 was fixed against it, so rc2's score on it is post-hoc. The two must not be blended:

| Set | rc1 (frozen, fresh run) | rc2 (this code) |
|---|---|---|
| 45-case fresh set, acceptable route | 41/45; 14 of 20 should-escalate cases escalated (misses X08, X11, X13, X14, X15, X40) | 45/45; 20/20 **(post-hoc, cases seen)** |
| 57-case adjacent set (54 scored), development set | 35/54 | 53/54 (R03 fails) |

Not included in this repository, so not reproducible from it: the rc1-vs-rc2 comparison, the 474-case regression comparison, the S3/S3b sets, the issue-regression tests and recorded registry lookups (these contain real firm names or third-party register data and were deliberately left out), and the real-browser checks (need Playwright; `requirements-browser.txt`).

## Known failures and limits (full list: [docs/LIMITATIONS.md](docs/LIMITATIONS.md))
* **R03 (open):** "I paid the registration amount, then they added a GST charge, then a compliance charge" gets follow-up questions only, **not** an urgent escalation.
* **Credential-exposure gaps (re-run on this tree):** `I entered my debit card number, expiry and CVV on the link that came in a WhatsApp message.` gets follow-up questions only; the Hinglish `maine apna card number aur CVV SMS ke link pe daal diya` is rated `HIGH_CONCERN` with **no urgent block**; a bare request such as `Read out the code we send you to confirm your KYC.` is `CANNOT_ASSESS`. Related gap: `After paying the demat charge, they kept adding new fees every few days.` (no "I paid") gets no escalation. Some other phrasings of card or PIN entry do escalate; coverage is a list of regex rules, not general.
* **Over-escalation:** ordinary payments with an extra charge ("Paid 2,000 advance to the plumber; he asked for 300 more") and past-tense hypotheticals ("If I paid 15,000 would they ask for more?") escalate; ordinary "I will pay ..." texts get a stop-payment step; legitimate OTP messages look identical to fake ones.
* **Recall:** rules are regexes and word lists; unlisted paraphrases are missed (the result then says it could not assess).
* **Languages:** English is the tested language. Hindi/Hinglish rules and all Hindi text were written by the engine's author and **not reviewed by a fluent speaker**; Marathi and Tamil have tiny word lists; Bengali, Telugu, Gujarati and others are not read (the result says so). No language is claimed as fully supported.
* **Fixture mode is a demonstration, not a compliance or approval status:** its entries are invented, it contains no SEBI data, and a result in fixture mode says nothing about any real firm or number.
* **Privacy:** pasted text is processed in memory; the app has no database, cookies, analytics or access log, and bodies are not logged. This rests on source inspection and runtime probes on the paths exercised, **not** on a general guarantee (OS/proxy/crash logs and any hosting layer were not examined). Pasting OTPs, PINs, or card numbers is discouraged by the page; long digit runs are masked when quoted, short ones (3-digit CVV, 6-digit OTP) are not.
* The bank, 1930, evidence and detail steps now cite official pages only (RBI circular, MHA/I4C portal guide, Sanchar Saathi); the other next-step steps and the claim evidence still cite news or secondary pages (their tier is displayed; accuracy not independently checked). The portal guide cited for the evidence and detail steps is headed "For Delhi Only", so its nationwide scope is unverified. Display defects: in the Hindi page the label "(listed below)" can still point to nothing (the English page now lists the risk, 2026-10-05), and one quote can appear twice.
* **Demo examples (checked 2026-10-04 on this tree):** `Your bank account will be suspended today. Complete KYC immediately using the link below to avoid account closure.` is `SOME_CONCERN`; only an URGENCY phrase is flagged, **not** the link or the KYC request, and the KYC claim stays "not enough evidence". `Join our exclusive investment group. Earn guaranteed 20% weekly returns with no risk. Limited seats available. Send your payment today.` is `HIGH_CONCERN`; the high-return and urgency phrases are flagged, **not** a group invite or the payment demand (`WhatsApp group` wording and a UPI id are recognised in a variant). `Your account details need to be reviewed.` is `CANNOT_ASSESS`.
* **Browser checks (run 2026-10-04, headless Chromium, on a copy of this tree):** `tests/browser_final.py` 138 checks, 3 failed (the same 3 fail on the baseline: the ordinary `I paid 1,200 to Zomato via UPI` payment is not escalated: it gets the "One question first" page, which still contains a red conditional "if the answer is yes, start here" block that the check counts as an urgent block; left unchanged because removing it would need an incident-logic or vendor-specific rule); `tests/browser_check.py` no failures. Read-aloud (device voice) was not tested.
* Never tested with real users, never deployed, no effect-on-losses evidence.

## Third-party material and disclosure
* `saathi_rc/sources/corpus.json`: 45 source entries on 29 distinct public web pages (snapshot dated 2026-10-02; the SEBI PR 14/2026 entries and three RBI BE(A)WARE entries were re-pointed to official pages on 2026-10-04), each with publisher, title, URL and tier. The earlier staging package also held a short verbatim excerpt of each page; **this variant removed all excerpts**, and the `text` field of each entry just repeats the title. Titles, publisher names and URLs are still third-party material, and the sources' rights holders have not been asked about them. Removing excerpts is a precaution, not a clearance. One engine-written explanation still quotes seven words from a news page about `@valid` handles. (The "keep these ready when you call 1930" step was reworded on 2026-10-04 to follow the official portal guide instead of a commercial page.) Evaluation numbers recorded earlier were produced with the excerpts present; on the 392 shipped example inputs this variant gave identical postures, incident states, urgent-step counts, claim states, evidence counts and step counts (a consistency check against the staging package, not an accuracy measure).
* Runtime dependencies: Python standard library only. Optional: `playwright` and `axe-playwright-python` (browser checks).
* **AI assistance:** the code, tests, evaluation cases, expected outcomes and documentation in this repository were produced in AI-assisted sessions (Arena.ai Agent Mode, which uses several large language models) under the project owner's direction. The same AI-assisted process wrote the engine and its evaluation cases, so the evaluation is not independent of the code. The extent of human line-by-line review of each file has not been recorded.
* Source docstrings and a few comments refer to earlier development directories (`poc/`, `rc/`, `v0_3/`) and to `docs/CHANGELOG_RC.md`, which are not part of this repository.

## Registry data and real organisations
The register fixture is synthetic. This tree contains **no** recorded SEBI register data and, by a case-insensitive search of the release preparation, no real adviser registration numbers. Benign real consumer brands (for example Zomato, Netflix, Amazon) appear in a few example messages. Scam-style example messages in `eval/` are author-written inventions; see [docs/PRIVACY_AND_DATA.md](docs/PRIVACY_AND_DATA.md) for what is and is not synthetic.
