# Architecture (v0.4.0-rc2)

Everything below was read from the source in this repository. Statements about behaviour that were run are marked in `README.md` and the release audit report; this file describes structure only.

## Flow of one message check
1. **Web layer** (`saathi_rc/web/app.py`, `views.py`): a stdlib `ThreadingHTTPServer`. Routes: `GET /`, `/about`, `/healthz`; `POST /check`, `/registry`, `/registry-fragment` (HTML forms); `POST /api/check`, `/api/registry` (JSON). Request bodies over about 90 KB and texts over 20,000 characters are refused. No debug or admin route exists in the source (checked by reading the route table). Pages are rendered server-side with a Content-Security-Policy using hashes, `no-store` caching, `nosniff` and `no-referrer`.
2. **Journey** (`journey.py`): runs the message check first (offline, never waits on the network); the register step is a separate, user-requested action and cannot change the message result.
3. **Engine** (`engine.py`): the user-chosen *situation* gate comes first. Harm situations (paid money, shared credentials, granted access) escalate with bank and 1930 steps first.
4. **Incident reader** (`incident.py`, `cues.py`): reads actor, action, status and negation per clause from the text with regexes and word lists (English, Hindi, some Hinglish). A subject-less payment is never labelled "user paid"; it becomes `PAYMENT_UNCLEAR` and escalates only with structural risk context.
5. **Claim/indicator pipeline** (`core/`): extracts checkable claims and warning signs, retrieves from the fixed corpus of 45 source entries on 29 distinct pages (`sources/corpus.json`; in this variant each entry's text is just its title, with no third-party excerpt) with lexical scoring, assigns a posture with author-chosen, uncalibrated weights. No network access and no model calls in this path.
6. **Freshness** (`freshness.py`): the corpus is a fixed snapshot dated 2026-10-02; after 90 days a notice is shown and after 365 days decisive claims become `INSUFFICIENT`.
7. **Validator** (`validate.py`, `core/validate.py`): fail-closed. A rule violation (clean/reassuring posture on a risky case, wrong block order, missing urgent steps) replaces the output with a safe fallback.
8. **Registry step** (`registry/`): `FixtureSource` (synthetic, `eval/registry_fixture.json`) or off. This variant has no live SEBI client (the development build's `LiveSebiSource` was removed). Statuses form a closed vocabulary; a failure is shown as an error or unavailable status, never a guess. A per-IP and global rate limit and a one-lookup-at-a-time lock apply to the register step.

## Configuration (environment variables)
| Variable | Default | Meaning |
|---|---|---|
| `SAATHI_REGISTRY` | `fixture` | `fixture` (synthetic, DEMO banner) or `off`. Any other value, including `live`, is treated as `off` with a stderr note. |
| `HOST` | `127.0.0.1` | Bind address; `0.0.0.0` exposes the server to the network. |
| `PORT` | `8000` | Port. |
| `SAATHI_TODAY` | real date | Pins the date used by the message check (corpus age and freshness); it does not affect the fixture register's staleness. |

## Layout notes
* `saathi_rc/core/` and `saathi_rc/registry/` are copies of earlier prototype code (v0.1 and v0.3 of the development history); their docstrings refer to directories not included here.
* Version strings: `VERSION = "0.4.0-rc2"`; internal `contract_version`, pipeline and registry version strings carry older labels (`rc-1`, `0.1.0-poc+rc`, `0.3+rc`) and were not changed.
