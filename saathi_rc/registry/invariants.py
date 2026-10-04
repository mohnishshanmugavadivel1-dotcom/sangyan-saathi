"""Deterministic output validator (SPEC section 5). Returns a list of violation strings; empty list = valid."""
import datetime as dt, json, re
from .contract import (SV_STATUSES, POSITIVE, SOURCE_PROBLEM, HARM, NOT_CHECKABLE_REASONS, AMBIGUOUS_REASONS, NOT_FOUND_REASONS, FORBIDDEN_RE, MAX_CANDIDATES, STALE_DAYS, LANGS)
from .inputs import compare_names, classify_number
from .guidance import URGENT_IDS

ALLOWED_REC_KEYS = {"name", "reg_no", "list", "validity", "register_status"}
BAD_KEYS = re.compile(r"(?i)^(e-?mail|telephone|phone|fax|address|contact|contact_person)")
REASONS = {"NOT_CHECKABLE": NOT_CHECKABLE_REASONS, "AMBIGUOUS": AMBIGUOUS_REASONS + ("LEGAL_FORM_DIFFERS",), "NOT_FOUND": NOT_FOUND_REASONS}


def _strings(resp):
    out = [resp["message_assessment"]["text"], resp.get("official_check", "")] + list(resp.get("not_checked", [])) + list(resp.get("limits", []))
    g = resp.get("incident_guidance") or {}
    out += list(g.get("questions", [])) + [a["text"] for a in g.get("actions", [])]
    sv = resp.get("source_verification")
    if sv:
        out += [sv["headline"], sv["means"], sv["does_not_mean"]]
    return out


def validate(resp, ctx, now):
    v = []
    lang = resp.get("language")
    if lang not in LANGS:
        v.append("I-lang")
    if resp.get("flow_status") not in ("OK", "NEEDS_SITUATION"):
        v.append("I-flow")
    ma = resp.get("message_assessment") or {}
    if ma.get("status") != "NOT_PROVIDED":
        v.append("I4 message_assessment not NOT_PROVIDED")
    if not resp.get("not_checked"):
        v.append("I4 not_checked block missing")
    if resp.get("block_order") != ["incident_guidance", "source_verification", "not_checked"]:
        v.append("I5 block order")
    sit = ctx.get("situation")
    if resp.get("flow_status") == "NEEDS_SITUATION":
        if resp.get("source_verification") or (resp.get("incident_guidance") or {}).get("actions"):
            v.append("CF3 processing without situation")
        return v
    g = resp.get("incident_guidance") or {}
    if sit in HARM:
        ids = [a["id"] for a in g.get("actions", []) if not a["conditional"]]
        if not all(i in ids for i in URGENT_IDS) or g.get("mode") != "URGENT":
            v.append("I5 harm situation without unconditional urgent actions")
    if sit == "UNSURE":
        ids = [a["id"] for a in g.get("actions", []) if a["conditional"]]
        if not g.get("questions") or not all(i in ids for i in URGENT_IDS):
            v.append("I5 UNSURE without questions + conditional actions")
    sv = resp.get("source_verification")
    if sv:
        st, rs = sv.get("status"), sv.get("reason")
        if st not in SV_STATUSES:
            v.append("I11 status outside closed set")
        if st in REASONS and rs not in REASONS[st]:
            v.append("I11 reason outside closed set")
        if st not in REASONS and rs is not None:
            v.append("I11 unexpected reason")
        prov = sv.get("provenance") or []
        for p in prov:
            if not p.get("retrieved_at_utc"):
                v.append("I7 provenance without retrieval time")
        if st in POSITIVE or st in ("NAME_DIFFERS", "INACTIVE_IN_REGISTER", "NOT_FOUND") or (st == "AMBIGUOUS"):
            if not prov:
                v.append("I7 definitive status without provenance")
            if any(p.get("result") != "OK" for p in prov[:2]):
                v.append("I3 definitive status although a source lookup did not succeed")
            asof = sv.get("as_of")
            if not asof:
                v.append("I3 definitive status without as-of date")
            else:
                try:
                    if (now.date() - dt.date.fromisoformat(asof)).days > STALE_DAYS:
                        v.append("I3 definitive status on stale data")
                except ValueError:
                    v.append("I3 bad as-of")
        if st in SOURCE_PROBLEM and (sv.get("register_record") or sv.get("candidates")):
            v.append("I3 register content shown with source problem")
        if st in POSITIVE:
            rec = sv.get("register_record") or {}
            n = classify_number(ctx.get("number") or "")
            if n[0] != "OK" or rec.get("reg_no") != n[1] or sv.get("match_count") != 1:
                v.append("I2 positive status without exact single number match")
            if st == "CONFIRMED_IN_REGISTER" and compare_names(ctx.get("name") or "", rec.get("name") or "") != "EXACT":
                v.append("I2 CONFIRMED without exact name")
            if st == "LISTED_NAME_NOT_COMPARED" and (ctx.get("name") or "").strip():
                v.append("I2 LISTED_NAME_NOT_COMPARED although a name was given")
            if ctx.get("claim_kind") == "OTHER" or ctx.get("too_many"):
                v.append("CF7 positive status for ineligible claim")
        if sv.get("candidates"):
            if len(sv["candidates"]) > MAX_CANDIDATES:
                v.append("I9 too many candidates")
            if [c["reg_no"] for c in sv["candidates"]] != sorted(c["reg_no"] for c in sv["candidates"]):
                v.append("I9 candidates not ordered by number")
            if any(set(c) - {"name", "reg_no", "list"} for c in sv["candidates"]):
                v.append("I10 candidate fields")
        if sv.get("register_record") and set(sv["register_record"]) - ALLOWED_REC_KEYS:
            v.append("I10 register record fields")
    # I6 forbidden wording in generated strings
    for s in _strings(resp):
        if lang == "en" and FORBIDDEN_RE.search(s):
            v.append("I6 forbidden wording: " + FORBIDDEN_RE.search(s).group(0))
        if lang == "hi" and FORBIDDEN_RE.search(s):
            v.append("I6 forbidden wording (Latin text in hi)")
    # I8 no echo of pasted text; I10 no contact keys anywhere
    # CH-R5 (fixes F-V3-002): the echo check looks only at DYNAMIC fields. Fixed template sentences and register-sourced names/records are excluded; the
    # frozen v0.3 check compared against the whole response and rejected correct results when pasted text shared ordinary words with templates.
    dyn = {k: v for k, v in resp.items() if k not in ("incident_guidance", "not_checked", "limits", "official_check", "message_assessment", "prompt", "block_order")}
    sv_ = dict(dyn.get("source_verification") or {})
    for k in ("headline", "means", "does_not_mean", "register_record", "candidates", "source"):
        sv_.pop(k, None)
    dyn["source_verification"] = sv_
    dump = json.dumps(dyn, ensure_ascii=False)
    typed = " ".join([ctx.get("name") or ""]).strip()
    pt = ctx.get("pasted_text") or ""
    if pt:
        rest = re.sub(r"\s+", " ", re.sub(r"(?i)IN[A-Z][\s\-]?[0-9A-Z]{9}", " ", pt)).strip()
        for i in range(0, max(0, len(rest) - 11), 3):
            w = rest[i:i + 12]
            if w in dump and w not in typed:
                v.append("I8 pasted text echoed"); break
    def walk(o):
        if isinstance(o, dict):
            for k, x in o.items():
                if BAD_KEYS.match(str(k)):
                    v.append("I10 contact key " + k)
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(resp)
    return v
