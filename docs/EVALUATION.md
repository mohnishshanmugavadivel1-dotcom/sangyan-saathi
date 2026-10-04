# Evaluation: method, results and what they do not show

**Nothing here is independent validation.** One author wrote the engine, the case sets, the expected outcomes and the fixes. No user testing, pilot or external review exists. None of the numbers is an accuracy, detection-rate or effect-on-losses estimate.

## Case sets included in this repository (`eval/`)
| File | Cases | Role |
|---|---|---|
| `cases_s1.jsonl` | 79 | development set (numbers include post-hoc fixes) |
| `cases_s2.jsonl` | 69 | second set (numbers after the first run include post-hoc fixes) |
| `cases_incident_state.jsonl` | 100 | challenge set for payment and credential incidents; its first run was frozen, later runs were development |
| `cases_incident_dev.jsonl` | 42 | development set used to tune |
| `cases_final_fresh.jsonl` | 45 | "fresh" set; run once on rc1 (frozen); **burned** once rc2 was fixed against it |
| `cases_sprint_adjacent.jsonl` | 57 (54 scored) | adjacent set written before the rc2 changes; two cases (A04, P01) failed on the first rc2 pass and the code was changed after seeing them, so it is a **development set**. sha256 `93c96e51e4acd538954fd201fa5590ebfd82c7ebc346939c53b2af18682d6cef` |

Not included (they name real firms or contain recorded third-party register data): the 150-case S3 set, the 34-case S3b set, the recorded SEBI register lookups, the issue-regression tests, and result files other than `results/incident_state/raw_results.jsonl` (which one test reads).

## Historical (rc1, frozen) versus current (rc2, post-hoc)
| Item | rc1 (frozen, fresh run) | rc2 |
|---|---|---|
| 45-case fresh set, acceptable route | 41/45 | 45/45 **post-hoc** |
| Should-escalate cases that escalated | 14/20; the six not escalated: X08, X11, X13, X14, X15, X40 | 20/20 **post-hoc** (the cases had been seen) |
| False escalations on the set | 0/24 | 0/24 |
| 57-case adjacent set (54 scored) | 35/54 | 53/54; the failure is **R03** |

Only the rc1 column is a fresh-run result, and even that is same-author. The rc2 column must not be quoted as accuracy or blended with rc1.

rc2 disclosed trade-offs: new over-escalations B07 and B08 (ordinary extra-charge payments), and P04 (an electricity bill intention now gets a stop-payment step). R03 stays open: "I paid the registration amount, then they added a GST charge, then a compliance charge" gets follow-up questions only.

The comparison of rc1 and rc2 over 474 earlier cases (no posture changes found) and the registry replay are **not reproducible from this repository** (they need the frozen rc1 tree and removed files).

## What was run for this release preparation (see the audit report for logs)
* Unit and web tests: 173 tests, OK, 1 expected failure (documents R03).
* Mutation checks: 15 deliberate breakages of the incident logic, "mutations NOT caught: 0".
* `eval/run_sprint.py`: 54 scored, 53 pass, `['R03']`.
* `eval/run_suite.py cases_s1.jsonl <outdir>`: runs and reports its failure buckets.
* All of the above ran with outbound network blocked and `requests` unimportable.
* **Variant note:** the case sets, expected outcomes and recorded scores in this document were produced with the earlier package that held source excerpts and a live-register client. In this variant the excerpts were replaced by titles and the live client was removed; the unit tests, mutation run, sprint set and smoke checks were re-run on this variant (see the release decision report in the owner's workspace, not in this repository), and on 392 shipped inputs the compared outputs matched the earlier package. That is a consistency check only, not new evidence of accuracy.
Passing these only shows that the code matches the author's own expectations.

## Reproduction commands
```bash
python3 -B -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py"
python3 -B tests/mutation_incident.py all
python3 -B eval/run_sprint.py "$PWD" /tmp/sprint.json
cd eval && python3 -B run_suite.py cases_s1.jsonl /tmp/suite_s1
```
**Do not run `eval/run_incident.py --baseline/--postfix/--final` or the `author_*.py` scripts inside a checkout you want to keep clean:** they are single-use freezers or case writers that write into `results/` or `eval/`. Use a throwaway copy.

## Optional real-browser checks
`tests/browser_check.py` and `tests/browser_final.py` need Playwright (`requirements-browser.txt`). They were **not run** for this release preparation; earlier runs were on rc1 (headless Chromium only), not rc2.
