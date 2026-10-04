"""Step 6: deterministic safety / output validation. Fails CLOSED: any error -> ABSTAIN with validation_failed=true."""
import re
from .contracts import (validate_result_shape, SUPPORTED, CONTRADICTED, ABSTAIN, NO_INDICATORS_FOUND, LOSS_SITUATIONS, POSTURES)
from .posture import posture_for
from .actions import LOSS_REQUIRED

FORBIDDEN = [
    (re.compile(r"(?i)\b(safe|legit|legitimate|genuine|trustworthy|authentic|no risk)\b"), "reassurance word"),
    (re.compile(r"(?i)\byou should (buy|sell|hold|invest)\b|\b(buy|sell|hold) (this|these|the) (stock|share)s?\b|\btarget price of\b"), "investment advice"),
    (re.compile(r"(?i)\b(will|can|shall) (recover|get back|refund)\b|money back\b|\bguarantee[sd]? (a )?(refund|recovery)"), "recovery promise"),
    (re.compile(r"(?i)\bwait\b"), "tells user to wait"),
    (re.compile(r"(?i)\bpay (more|again|the fee)\b"), "tells user to pay"),
]
PROSE_KEYS = ("headline", "summary")


def prose_fields(res):
    """Our own prose (not echoed user text, not verbatim source quotes)."""
    out = [res.get("headline", ""), res.get("summary", "")]
    out += [c.get("explanation", "") for c in res.get("claims", [])]
    out += [i.get("note", "") for i in res.get("indicators", [])]
    out += [a.get("text", "") for a in res.get("next_steps", [])]
    out += list(res.get("limitations", []))
    out += [res.get("abstention", {}).get("reason", "")]
    return out


def digits(s):
    return re.sub(r"\D", "", s)


def validate(res, corpus, norm, situation, fixture_mode=False):
    errs = []
    errs += validate_result_shape(res)
    posture = res.get("posture")
    # evidence ids + tier rule
    for c in res.get("claims", []):
        pids = []
        for e in c.get("evidence", []):
            if e["passage_id"] == "FIXTURE-REGISTRY":
                if not fixture_mode:
                    errs.append("fixture evidence outside fixture mode")
                continue
            if corpus.get(e["passage_id"]) is None:
                errs.append("unknown passage id " + e["passage_id"])
            elif e["relation"] in ("contradicts", "supports", "format_rule"):
                pids.append(e["passage_id"])
        if c["state"] in (SUPPORTED, CONTRADICTED):
            fixture_ev = any(e["passage_id"] == "FIXTURE-REGISTRY" for e in c.get("evidence", []))
            if not fixture_ev and not corpus.eligible(pids):
                errs.append("ineligible evidence for %s on %s" % (c["state"], c["claim_type"]))
    for a in res.get("next_steps", []):
        for s in a.get("sources", []):
            if corpus.get(s) is None:
                errs.append("action cites unknown passage " + s)
    # forbidden phrases
    for txt in prose_fields(res):
        for rx, why in FORBIDDEN:
            if rx.search(txt or ""):
                errs.append("forbidden phrase (%s): %r" % (why, rx.search(txt).group(0)))
    # sensitive digits: nothing from the input's sensitive runs may appear in any output field
    blob = repr(res)
    toks = [digits(m.group(0)) for m in re.finditer(r"(?:\d[ \-]?){6,}", blob)]
    for r in norm.get("sensitive_runs", []):
        dr = digits(r)
        if r in blob or (len(dr) >= 6 and any(dr in t for t in toks)):
            errs.append("sensitive digit run echoed")
            break
    # posture consistency (only for assessed outputs)
    if posture in (NO_INDICATORS_FOUND,):
        p, s, _ = posture_for(res["claims"], res["indicators"])
        if p != NO_INDICATORS_FOUND:
            errs.append("posture NO_INDICATORS_FOUND inconsistent with findings")
        if not re.search(r"(?i)not a safety guarantee|गारंटी नहीं", res.get("headline", "")):
            errs.append("NO_INDICATORS_FOUND missing disclaimer")
    # loss actions
    ids = {a["action_id"] for a in res.get("next_steps", [])}
    if situation in LOSS_SITUATIONS:
        if posture == NO_INDICATORS_FOUND:
            errs.append("loss situation with NO_INDICATORS_FOUND posture")
        for need in LOSS_REQUIRED:
            if need not in ids:
                errs.append("missing loss action " + need)
    if posture not in POSTURES:
        errs.append("bad posture")
    return errs
