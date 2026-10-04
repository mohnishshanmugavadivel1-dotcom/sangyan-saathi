"""Fail-closed output validator for the message check. Returns a list of violation strings (empty = valid). Any violation replaces the output with a
safe fallback that keeps urgent guidance (engine.safe_fallback)."""
import json, re
from .contract import (INCIDENT_STATES, POSTURES, SEVERITY, LANGS, SITUATIONS, HARM, CLAIM_STATES, URGENT_REQUIRED, ESCALATE_STEPS, APPROVED_NEGATIVE, REASSURE_RE, NO_SIGNAL_RE,
                       ACTIONS, HEADLINE)
from .core.validate import FORBIDDEN as CORE_FORBIDDEN

BLOCKS = ["urgent_steps", "assessment", "steps", "registry", "unavailable", "limitations"]
LEGACY_CLEAN = ("NOT_VERIFIED", "NO_INDICATORS_FOUND", "OK", "SAFE", "CLEAR", "NO_CONCERN")


def _strings(res):
    out = [res.get("headline", ""), res.get("summary", ""), res.get("pause_notice", "")]
    for k in ("urgent_steps", "steps"):
        out += [a.get("text", "") for a in res.get(k, [])]
    out += [i.get("note", "") for i in res.get("indicators", [])]
    out += [c.get("state_label", "") for c in res.get("claims", [])]
    out += [c.get("explanation", "") for c in res.get("claims", []) if not c.get("freshness", {}).get("downgraded")]
    out += [u.get("text", "") for u in res.get("unavailable", [])]
    out += list(res.get("limitations", [])) + list(res.get("questions", []))
    out += [o.get("text", "") for o in res.get("options", [])]
    return [s for s in out if s]


def _digits(s):
    return re.sub(r"\D", "", s)


def validate(res, corpus, ctx):
    v = []
    sit, p, lang = res.get("situation"), res.get("posture"), res.get("language")
    if lang not in LANGS: v.append("lang")
    if p not in POSTURES: v.append("posture outside closed set: %r" % (p,))
    if str(p).upper() in LEGACY_CLEAN: v.append("clean posture")
    if res.get("block_order") != BLOCKS: v.append("block order")
    if p in POSTURES and res.get("headline") != HEADLINE[p][lang if lang in LANGS else "en"]: v.append("headline differs from the fixed text for the posture")
    urgent_ids = [a["action_id"] for a in res.get("urgent_steps", [])]
    step_ids = [a["action_id"] for a in res.get("steps", [])]
    # ---- gate rules
    if sit not in SITUATIONS:
        if p != "NEEDS_SITUATION": v.append("analysis without a situation")
        if res.get("claims") or res.get("indicators"): v.append("findings without a situation")
        return v
    if sit in HARM:
        if p != "ESCALATE": v.append("harm situation not escalated")
        if not URGENT_REQUIRED <= set(urgent_ids): v.append("harm situation without bank + 1930 steps")
        if res.get("claims") or res.get("indicators"): v.append("harm situation analysed message instead of escalating")
    if sit == "UNSURE" and not (p == "ASK_FOLLOWUP" and res.get("questions")) and not (p == "ESCALATE" and (res.get("incident") or {}).get("applied") == "escalated_from_text"): v.append("UNSURE without follow-up questions")
    if p == "ESCALATE" and not URGENT_REQUIRED <= set(urgent_ids): v.append("ESCALATE without urgent steps")
    if sit == "PAYMENT_PENDING" or ctx.get("pending"):
        if p in ("ASK_FOLLOWUP",) and sit != "PAYMENT_PENDING":   # S3 FIX-1: a user-selected pending payment needs the stop-payment step even when follow-up questions are asked
            pass
        elif "A_STOP_PAYMENT" not in urgent_ids: v.append("pending payment without stop-payment step in urgent block")
        elif urgent_ids[0] != "A_STOP_PAYMENT": v.append("stop-payment step not first")
        if p == "ABSTAIN": v.append("pending payment abstained")
    if any(s.get("conditional") for s in res.get("urgent_steps", [])): v.append("conditional step in urgent block")
    # ---- S4 incident-state invariants
    inc = res.get("incident"); ist = (inc or {}).get("state"); applied = (inc or {}).get("applied")
    if inc is not None and ist not in INCIDENT_STATES: v.append("incident state outside closed set")
    if inc is not None and inc.get("source") == "text" and ist in ("USER_PAID", "USER_SHARED_CREDENTIAL", "UNAUTHORISED_DEBIT") and p not in ("ESCALATE", "ASK_FOLLOWUP"):
        v.append("reported payment or credential share ended in %s" % p)
    if p == "ESCALATE" and sit not in HARM and applied != "escalated_from_text": v.append("text escalation without incident record")
    if applied == "escalated_from_text":
        if p != "ESCALATE": v.append("escalated_from_text but posture is %s" % p)
        # Sprint Oct-4: PAYMENT_UNCLEAR may escalate ONLY through the explicit subject-less route and only with a non-empty risk context
        subjectless_ok = ist == "PAYMENT_UNCLEAR" and bool(inc.get("risk_context")) and (res.get("provenance") or {}).get("incident_route") == "escalated_subjectless_payment_with_context"
        if ist not in ("USER_PAID", "USER_SHARED_CREDENTIAL", "UNAUTHORISED_DEBIT") and not subjectless_ok: v.append("escalated_from_text with state %s" % ist)
        if not [e for e in inc.get("events", []) if e.get("snippet")] and not inc.get("risk_context"): v.append("escalated_from_text without the quoted text")
        if res.get("claims") or res.get("indicators"): v.append("text escalation analysed message instead of escalating")
    if ist in ("NO_INCIDENT", "USER_DENIES", "SENDER_CLAIMS_PAYMENT", "THIRD_PARTY_PAID") and p == "ESCALATE" and sit not in HARM: v.append("escalation on a state that is not the user's own report")
    # ---- consistency (CH-01 / CH-04)
    inds, claims = res.get("indicators", []), res.get("claims", [])
    if p == "ABSTAIN" and (inds or any(c["state"] in ("CONTRADICTED", "MIXED", "INSUFFICIENT", "NOT_ASSESSED") for c in claims)): v.append("ABSTAIN with findings")
    if p == "ABSTAIN" and ctx.get("surface") and [x for x in ctx["surface"] if x != "pressure_terms"]: v.append("ABSTAIN although the message contains a request surface")
    if p in ("HIGH_CONCERN", "SOME_CONCERN", "CANNOT_ASSESS") and not (step_ids or urgent_ids): v.append("assessment without steps")
    if p in ("HIGH_CONCERN", "SOME_CONCERN") and not ({"A_NO_PAY_NO_SHARE", "A_OFFICIAL_CALLBACK"} & set(step_ids + urgent_ids)): v.append("concern without a do-not-pay / official-callback step")
    if ctx.get("floor") and p in SEVERITY and p in ("ABSTAIN", "CANNOT_ASSESS", "SOME_CONCERN", "HIGH_CONCERN") and SEVERITY[p] < ctx["floor"] and ctx["floor"] > 1:
        v.append("posture below the detection floor")
    if p == "CANNOT_ASSESS" and not res.get("summary"): v.append("CANNOT_ASSESS without reasons")
    for c in claims:
        if c.get("state") not in CLAIM_STATES: v.append("claim state outside closed set")
        for e in c.get("evidence", []):
            if corpus.get(e["passage_id"]) is None: v.append("unknown passage " + e["passage_id"])
        if c.get("state") in ("SUPPORTED", "CONTRADICTED"):
            if c.get("freshness", {}).get("downgraded"): v.append("decisive state kept despite stale evidence")
            if not corpus.eligible([e["passage_id"] for e in c.get("evidence", []) if e.get("relation") in ("supports", "contradicts", "format_rule")]): v.append("ineligible evidence")
    for k in ("urgent_steps", "steps"):
        for a in res.get(k, []):
            if a["action_id"] not in ACTIONS or not a.get("sources"): v.append("action without sources: " + a.get("action_id", "?"))
            for s in a.get("sources", []):
                if corpus.get(s) is None: v.append("action cites unknown passage " + s)
    # ---- wording
    for s in _strings(res):
        rest = s
        for ok in APPROVED_NEGATIVE: rest = rest.replace(ok, " ")
        m = REASSURE_RE.search(rest)
        if m: v.append("reassurance wording: %s" % m.group(0))
        for rx, why in CORE_FORBIDDEN[1:]:
            if rx.search(s): v.append("forbidden phrase (%s)" % why)
        if NO_SIGNAL_RE.search(s) and (p != "ABSTAIN"): v.append("'nothing found' wording")
    if lang == "hi" and not any("मातृभाषी" in x for x in res.get("limitations", [])): v.append("Hindi review disclosure missing")
    # ---- sensitive digits never echoed
    norm = ctx.get("norm")
    if norm:
        blob = json.dumps(res, ensure_ascii=False)
        toks = [_digits(m.group(0)) for m in re.finditer(r"(?:\d[ \-]?){6,}", blob)]
        for r in norm.get("sensitive_runs", []):
            dr = _digits(r)
            if r in blob or (len(dr) >= 6 and any(dr in t for t in toks)): v.append("sensitive digit run echoed"); break
    return v
