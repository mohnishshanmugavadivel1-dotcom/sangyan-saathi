# -*- coding: utf-8 -*-
"""Runner + scorer for the incident-state challenge set (eval/cases_incident_state.jsonl).
  python3 -B eval/run_incident.py --baseline        untouched pre-fix engine, ONCE (results/incident_state/baseline_*)
  python3 -B eval/run_incident.py --postfix         first run after the fix, ONCE (results/incident_state/raw_results.jsonl, metrics.json)
  python3 -B eval/run_incident.py --posthoc <tag>   further runs after the challenge set has been used to change the engine (results/incident_state/posthoc_<tag>/): DEVELOPMENT evidence only
  python3 -B eval/run_incident.py --dev             the separate development set (eval/cases_incident_dev.jsonl); used to tune; writes results/incident_state/dev_run/
  python3 -B eval/run_incident.py --final          Phase 5: the fresh regression set eval/cases_final_fresh.jsonl, frozen before the Phase 5 fixes; SINGLE-USE; writes results/final_verification/fresh_raw_results.jsonl and fresh_metrics.json
S3_ENGINE_RC=<dir> runs against another copy of rc/ (e.g. the extracted pre-incident snapshot). Nothing is excluded: every case appears in raw_results."""
import hashlib, json, os, re, sys, platform, datetime, time
HERE = os.path.dirname(os.path.abspath(__file__)); RC = os.path.abspath(os.path.join(HERE, ".."))
ENGINE_RC = os.environ.get("S3_ENGINE_RC") or RC
sys.path.insert(0, ENGINE_RC); sys.dont_write_bytecode = True
from saathi_rc import clock
from saathi_rc.web import app as webapp, views
OUT = os.path.join(RC, "results", "incident_state")
PROMISE = re.compile(r"(?i)\b(will|can|shall)\s+(be\s+)?(recover|get\s+(your\s+)?money\s+back|reverse)|money\s+(will|can)\s+be\s+(recovered|returned|refunded|reversed)|guarantee[sd]?\s+(recovery|refund)")
NEGATED = re.compile(r"(?i)\b(cannot|can't|can not|not|no|never|nothing|without|unable)\b")   # scorer v2: a sentence that DENIES a promise ("cannot promise that money will be returned") is not a promise


def promise_wording(res):
    for s in re.split(r"(?<=[.!?;])\s+", json.dumps(res, ensure_ascii=False).replace("\\n", " ")):
        if PROMISE.search(s) and not NEGATED.search(s): return True
    return False
USER_STATES = ("USER_PAID", "USER_SHARED_CREDENTIAL", "UNAUTHORISED_DEBIT")   # scorer v4 (Phase 5): the new explicit state; no effect on any earlier run


def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()


def route_of(res):
    p = res["posture"]; u = [s["action_id"] for s in res["urgent_steps"]]
    if p == "ESCALATE": return "ESCALATE"
    if p == "ASK_FOLLOWUP": return "ASK"
    if u and u[0] == "A_STOP_PAYMENT": return "PENDING"
    return "NORMAL"


def run_case(c):
    t0 = time.time(); row = {"id": c["id"], "cat": c["cat"], "situation": c["sit"], "lang": c["lang"], "text": c["text"], "exception": None}
    try:
        res = webapp.run_check({"situation": c["sit"], "text": c["text"], "output_language": "en"})
        page = views.render_result(res, text=c["text"]).decode("utf-8")
    except Exception as ex:
        row.update(exception="%s: %s" % (type(ex).__name__, ex), route=None, posture=None); return row
    inc = res.get("incident")
    row.update(posture=res["posture"], route=route_of(res), urgent=[s["action_id"] for s in res["urgent_steps"]], steps=[(s["action_id"], bool(s["conditional"])) for s in res["steps"]],
               questions=len(res.get("questions", [])), indicators=[i["indicator"] for i in res["indicators"]], validation_failed=bool(res["provenance"].get("validation_failed")),
               validation_errors=res["provenance"].get("validation_errors", []), incident=inc, incident_state=(inc or {}).get("state"), incident_active=(inc or {}).get("active"),
               incident_actor=sorted({e["actor"] for e in (inc or {}).get("events", [])}), ms=round((time.time() - t0) * 1000, 1), headline=res["headline"], output=res)
    import html as _h                                       # scorer v3 (after the post-fix run): the page escapes with html.escape, so the check must too
    esc = lambda x: _h.escape(x)
    ui = {"posture_label": esc(views.UI["en"]["posture"].get(res["posture"], res["posture"])) in page, "headline": esc(res["headline"]) in page}
    ui["urgent_texts_present"] = all(esc(s["text"]) in page for s in res["urgent_steps"])
    if inc: ui["incident_label_present"] = esc(inc["label"]) in page
    if inc and inc.get("events"): ui["incident_quote_present"] = all(esc(ev["snippet"]) in page for ev in inc["events"] if ev.get("snippet"))
    row["ui"] = ui
    row["recovery_promise_wording"] = promise_wording(res)
    return row


def state_matches(r, c):
    """Phase 5 addition (additive; earlier runs were not re-scored): does the engine's incident state equal the expected state (or one of its allowed alternatives)? Expected PAYMENT_UNCLEAR with ideal ESCALATE also accepts UNAUTHORISED_DEBIT, which did not exist when the cases were frozen (declared before any run)."""
    got = r.get("incident_state") or "NO_INCIDENT"; allowed = {c["state"]} | set(c.get("also") or []) | set(r.get("incident_active") or []) & ({c["state"]} | set(c.get("also") or []))
    if c["state"] == "PAYMENT_UNCLEAR" and c["ideal"] == "ESCALATE": allowed.add("UNAUTHORISED_DEBIT")
    return got in allowed


def score(rows, cases):
    cm = {c["id"]: c for c in cases}; M = {}
    def frac(num_ids, den_ids, **kw): return dict(numerator=len(num_ids), denominator=len(den_ids), case_ids=sorted(num_ids), **kw)
    ok_rows = [r for r in rows if not r["exception"]]
    # 1 completed-payment/credential recognition
    A = [r["id"] for r in ok_rows if cm[r["id"]]["ideal"] in ("ESCALATE", "ASK") and cm[r["id"]]["state"] in ("USER_PAID", "USER_SHARED_CREDENTIAL")]
    R = {r["id"]: r for r in ok_rows}
    M["1_completed_report_recognition"] = {
        "definition": "cases whose ideal route is ESCALATE or ASK and whose expected state is USER_PAID or USER_SHARED_CREDENTIAL",
        "route_level_not_normal": frac([i for i in A if R[i]["route"] in ("ESCALATE", "ASK")], A),
        "route_in_acceptable_set": frac([i for i in A if R[i]["route"] in cm[i]["ok"]], A),
        "route_equals_ideal": frac([i for i in A if R[i]["route"] == cm[i]["ideal"]], A),
        "state_level_correct": frac([i for i in A if R[i]["incident_state"] == cm[i]["state"] or (R[i]["incident_active"] and cm[i]["state"] in R[i]["incident_active"])], A) if any(R[i]["incident_state"] for i in A) else "N/A (the engine had no explicit state)",
        "missed_as_normal_ids": sorted(i for i in A if R[i]["route"] in ("NORMAL", "PENDING"))}
    E = [r["id"] for r in ok_rows if cm[r["id"]]["ideal"] == "ESCALATE"]
    M["1b_critical_misses_ideal_escalate_got_normal"] = frac([i for i in E if R[i]["route"] in ("NORMAL", "PENDING")], E, note="ideal ESCALATE and the engine produced neither escalation nor follow-up")
    # 2 pending
    PEN = [r["id"] for r in ok_rows if cm[r["id"]]["ideal"] == "PENDING" or cm[r["id"]]["urgent_first"] == "A_STOP_PAYMENT"]
    M["2_pending_recognition"] = frac([i for i in PEN if R[i]["urgent"][:1] == ["A_STOP_PAYMENT"] or (R[i]["urgent"][:1] == [] and False)], PEN, note="stop-payment step first in the urgent block", missing=sorted(i for i in PEN if R[i]["urgent"][:1] != ["A_STOP_PAYMENT"]))
    # 3 false escalations / false follow-ups
    NE = [r["id"] for r in ok_rows if "ESCALATE" not in cm[r["id"]]["ok"]]
    M["3_false_completed_payment_escalations"] = frac([i for i in NE if R[i]["route"] == "ESCALATE"], NE, note="route ESCALATE where ESCALATE is not an acceptable route")
    NA = [r["id"] for r in ok_rows if "ASK" not in cm[r["id"]]["ok"]]
    M["3b_unwanted_follow_ups"] = frac([i for i in NA if R[i]["route"] == "ASK"], NA, note="ASK_FOLLOWUP where ASK is not an acceptable route (not urgent, but unwanted friction)")
    LG = [r["id"] for r in ok_rows if cm[r["id"]]["cat"] == "legit_everyday"]
    M["3c_legit_everyday"] = {"n": len(LG), "escalated": sorted(i for i in LG if R[i]["route"] == "ESCALATE"), "follow_up": sorted(i for i in LG if R[i]["route"] == "ASK"), "pending_block": sorted(i for i in LG if R[i]["route"] == "PENDING"), "normal": sorted(i for i in LG if R[i]["route"] == "NORMAL")}
    # 4 actor attribution
    TH = [r["id"] for r in ok_rows if cm[r["id"]]["actor"] in ("THIRD", "CLAIM")]
    wrong = [i for i in TH if (R[i]["incident_state"] in USER_STATES) or (R[i]["incident_state"] is None and R[i]["route"] in ("ESCALATE", "ASK") and R[i]["route"] not in cm[i]["ok"])]
    US = [r["id"] for r in ok_rows if cm[r["id"]]["actor"] == "USER" and cm[r["id"]]["state"] in USER_STATES]
    wrong2 = [i for i in US if R[i]["incident_state"] in ("THIRD_PARTY_PAID", "SENDER_CLAIMS_PAYMENT")]
    M["4_incorrect_actor_attribution"] = {"third_or_claim_attributed_to_user": frac(wrong, TH), "user_action_attributed_to_other": frac(wrong2, US),
                                          "note": "for the pre-fix engine (no explicit state) the first number is a route-level proxy"}
    # 5 negation
    NG = [r["id"] for r in ok_rows if cm[r["id"]]["state"] == "USER_DENIES" or "USER_DENIES" in cm[r["id"]]["also"] or r["id"] == "I48"]
    M["5_negation_errors"] = frac([i for i in NG if R[i]["route"] not in cm[i]["ok"]], NG, note="denied/aborted/refused cases that were treated as incidents, and negation traps where the real payment/credential share was lost")
    # 6 missing urgent guidance
    need_u = [i for i in E] + [r["id"] for r in ok_rows if cm[r["id"]]["urgent_first"] and cm[r["id"]]["ideal"] != "PENDING" and r["id"] not in E]
    def has_u(i):
        u = R[i]["urgent"]
        if cm[i]["ideal"] == "ESCALATE": return {"A_CONTACT_BANK", "A_CALL_1930"} <= set(u)
        return u[:1] == [cm[i]["urgent_first"]]
    M["6_missing_urgent_guidance"] = frac([i for i in need_u if not has_u(i)], need_u, note="ideal ESCALATE needs bank + 1930 in the urgent block; urgent_first cases need that step first",
                                         with_conditional_steps_only=sorted(i for i in need_u if not has_u(i) and any(a in ("A_CONTACT_BANK", "A_CALL_1930") for a, cnd in R[i]["steps"])))
    # 7 contradictory outputs (automatic invariants)
    contra = {}
    for r in ok_rows:
        v = []; st = r["incident_state"]
        if st in USER_STATES and r["route"] not in ("ESCALATE", "ASK"): v.append("user-reported incident but no escalation/follow-up")
        if r["route"] == "ESCALATE" and r["situation"] not in ("PAID_MONEY", "SHARED_CREDENTIALS", "ACCESS_GRANTED") and st in ("NO_INCIDENT", "USER_DENIES", "SENDER_CLAIMS_PAYMENT", "THIRD_PARTY_PAID"): v.append("text-derived escalation with a non-incident state")
        if r["urgent"] and "A_STOP_PAYMENT" in r["urgent"] and r["urgent"][0] != "A_STOP_PAYMENT": v.append("stop-payment not first")
        if r["posture"] == "ESCALATE" and not {"A_CONTACT_BANK", "A_CALL_1930"} <= set(r["urgent"]): v.append("escalation without bank+1930")
        if r["incident"] and r["incident"].get("state") not in ("USER_PAID", "USER_SHARED_CREDENTIAL", "UNAUTHORISED_DEBIT", "USER_PAYMENT_PENDING", "PAYMENT_UNCLEAR", "THIRD_PARTY_PAID", "SENDER_CLAIMS_PAYMENT", "USER_DENIES", "NO_INCIDENT"): v.append("state outside closed set")
        if r["incident"] and r["incident"].get("state") in USER_STATES and r["incident"].get("state") not in ([r["incident"]["state"]] + r["incident"].get("active", [])): v.append("state not in active list")
        if not all(r["ui"].values()): v.append("UI differs from backend: %s" % [k for k, ok in r["ui"].items() if not ok])
        if r["recovery_promise_wording"]: v.append("recovery promise wording")
        if v: contra[r["id"]] = v
    M["7_contradictory_outputs"] = frac(list(contra), [r["id"] for r in ok_rows], details=contra)
    # 8 appropriate uncertainty
    UNC = [r["id"] for r in ok_rows if cm[r["id"]]["unc"]]
    M["8_appropriate_uncertainty"] = frac([i for i in UNC if R[i]["route"] == "ASK" and R[i]["questions"] > 0 and R[i]["incident_state"] in (None, "PAYMENT_UNCLEAR", "USER_PAID", "USER_SHARED_CREDENTIAL")], UNC,
                                         state_is_unclear=frac([i for i in UNC if R[i]["incident_state"] == "PAYMENT_UNCLEAR"], UNC) if any(R[i]["incident_state"] for i in UNC) else "N/A",
                                         note="ASK_FOLLOWUP with at least one question where uncertainty was the right answer")
    # 9 technical failures
    M["9_technical_failures"] = frac([r["id"] for r in rows if r["exception"]], [r["id"] for r in rows], validator_fallback_used=sorted(r["id"] for r in ok_rows if r["validation_failed"]),
                                    max_ms=max([r.get("ms", 0) for r in ok_rows] or [0]))
    # route confusion by ideal route
    conf = {}
    for r in ok_rows: conf.setdefault(cm[r["id"]]["ideal"], {}).setdefault(r["route"], []).append(r["id"])
    M["route_confusion_by_ideal"] = {k: {kk: len(vv) for kk, vv in v.items()} for k, v in conf.items()}
    M["ambiguous_cases_not_counted_as_failures"] = sorted(c["id"] for c in cases if c["ambiguous"])
    M["by_language"] = {l: {"n": sum(1 for c in cases if c["lang"] == l), "route_in_acceptable_set": sum(1 for r in ok_rows if cm[r["id"]]["lang"] == l and r["route"] in cm[r["id"]]["ok"])} for l in ("en", "hinglish", "hi")}
    allok = [r["id"] for r in ok_rows if r["route"] in cm[r["id"]]["ok"]]
    M["overall_route_in_acceptable_set"] = frac(allok, [r["id"] for r in ok_rows], note="not an accuracy estimate: 100 author-written cases")
    sm = [r["id"] for r in ok_rows if state_matches(r, cm[r["id"]]) and not cm[r["id"]]["ambiguous"]]; sd = [r["id"] for r in ok_rows if not cm[r["id"]]["ambiguous"]]
    M["10_state_level_match"] = frac(sm, sd, mismatches=sorted(set(sd) - set(sm)), note="Phase 5 addition: incident_state equals the expected state (ambiguous cases excluded; UNAUTHORISED_DEBIT accepted for expected PAYMENT_UNCLEAR + ESCALATE). Reported separately from route correctness.")
    return M


def main(a):
    os.makedirs(OUT, exist_ok=True)
    if "--final" in a:
        FV = os.path.join(RC, "results", "final_verification"); cf = os.path.join(HERE, "cases_final_fresh.jsonl"); d = FV; tag = "final-fresh"
        rawp, metp = os.path.join(FV, "fresh_raw_results.jsonl"), os.path.join(FV, "fresh_metrics.json")
        if os.path.exists(rawp) or os.path.exists(metp): sys.exit("the fresh final run already exists (%s); it is single-use and must not be repeated or overwritten" % rawp)
        fz = json.load(open(os.path.join(FV, "FRESH_FREEZE.json")))
        if sha(cf) != fz.get("cases_sha256") and sha(cf) != fz.get("sha256"): sys.exit("fresh case file differs from the frozen hash; refusing to run")
    elif "--dev" in a:
        cf = os.path.join(HERE, "cases_incident_dev.jsonl"); d = os.path.join(OUT, "dev_run"); tag = "dev"
    else:
        cf = os.path.join(HERE, "cases_incident_state.jsonl")
        if "--baseline" in a: d = OUT; tag = "baseline"
        elif "--postfix" in a: d = OUT; tag = "postfix-run1"
        elif "--posthoc" in a: tag = a[a.index("--posthoc") + 1]; d = os.path.join(OUT, "posthoc_" + tag)
        else: sys.exit(__doc__)
    pre = "baseline_" if tag == "baseline" else ""
    if tag != "final-fresh": rawp, metp = os.path.join(d, pre + "raw_results.jsonl"), os.path.join(d, pre + "metrics.json")
    if tag not in ("final-fresh",) and "--out" in a: d = a[a.index("--out") + 1]; rawp, metp = os.path.join(d, pre + "raw_results.jsonl"), os.path.join(d, pre + "metrics.json")   # Phase 5: write elsewhere
    if tag not in ("baseline", "postfix-run1", "final-fresh") and os.path.exists(rawp) and "--force" not in a: sys.exit("%s already exists; pass --out <new dir> (or --force to overwrite): historical results must not be overwritten" % rawp)
    if tag in ("baseline", "postfix-run1") and os.path.exists(rawp): sys.exit("this run already exists (%s); it is single-use" % rawp)
    if tag == "baseline" and os.path.exists(os.path.join(OUT, "raw_results.jsonl")): sys.exit("baseline must precede the post-fix run")
    os.makedirs(d, exist_ok=True)
    cases = [json.loads(l) for l in open(cf, encoding="utf-8")]
    with clock.frozen("2026-10-03"):
        rows = [run_case(c) for c in cases]
    with open(rawp, "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    eng = hashlib.sha256("".join(sha(os.path.join(dp, fn)) for dp, dn, fns in sorted(os.walk(os.path.join(ENGINE_RC, "saathi_rc"))) for fn in sorted(fns) if fn.endswith(".py")).encode()).hexdigest()
    meta = {"run_tag": tag, "run_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "python": sys.version.split()[0], "platform": platform.platform(), "engine_dir": ENGINE_RC, "engine_py_bundle_sha256": eng,
            "cases_file": os.path.basename(cf), "cases_sha256": sha(cf), "n_cases": len(cases), "command": "python3 -B eval/run_incident.py " + " ".join(a),
            "status": {"baseline": "untouched pre-fix engine, single run", "postfix-run1": "first run after the fix; the engine was developed on a SEPARATE dev set and the spec, not on per-case outputs of this set; still author-written, NOT independent",
                       "dev": "development set used for tuning; not evidence", "final-fresh": "fresh regression set authored and frozen BEFORE the Phase 5 fixes (same author as the engine, NOT independent; Hindi/Hinglish unreviewed); single run; the engine was not designed from its outputs"}.get(tag, "POST-HOC development result: the frozen challenge set was used to change the engine before this run; not validation")}
    json.dump({"meta": meta, "metrics": score(rows, cases)}, open(metp, "w"), indent=1, ensure_ascii=False)
    m = json.load(open(metp))["metrics"]
    for k, v in m.items():
        print(k, json.dumps(v, ensure_ascii=False)[:420])


if __name__ == "__main__":
    main(sys.argv[1:])
