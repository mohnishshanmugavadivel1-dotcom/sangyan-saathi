"""Orchestrator. Assembles three independent blocks; never lets one block change another."""
import datetime as dt
from . import VERSION
from .contract import *
from .contract import T, CATEGORY
from .inputs import extract_numbers, classify_number
from .guidance import guidance_for
from .verify import verify_claim
from .invariants import validate

BLOCK_ORDER = ["incident_guidance", "source_verification", "not_checked"]


def _lang(x):
    return x if x in LANGS else "en"


def _card(ver, lang, origin):
    key = ver["status"] + (":" + ver["reason"] if ver.get("reason") else "")
    t = T[lang].get(key) or T[lang][ver["status"]]
    pre = (ver["claim"].get("reg_no") or "")[:3]
    cat = CATEGORY[pre][lang] if pre in CATEGORY else ("Investment Advisers and Research Analysts" if lang == "en" else "निवेश सलाहकारों और रिसर्च एनालिस्ट")
    fmt = dict(as_of=ver.get("as_of") or "an unknown date", category=cat, n=ver.get("match_count"))
    rr = ver.get("register_record")
    return {"status": ver["status"], "reason": ver.get("reason"), "headline": t["h"], "means": t["m"].format(**fmt), "does_not_mean": t["n"], "register_record": rr,
            "candidates": ver.get("candidates", []), "match_count": ver.get("match_count"), "as_of": ver.get("as_of"), "provenance": ver.get("provenance", []),
            "source": dict(SOURCE_INFO), "source_note": ver.get("note"), "input_origin": origin, "number_checked": ver["claim"].get("reg_no")}


def _base(lang, situation, flow):
    return {"version": VERSION, "language": lang, "situation": situation, "flow_status": flow, "block_order": list(BLOCK_ORDER),
            "incident_guidance": {"mode": "NONE", "questions": [], "actions": []}, "source_verification": None,
            "message_assessment": {"status": "NOT_PROVIDED", "text": MESSAGE_ASSESSMENT[lang]},
            "not_checked": list(NOT_CHECKED[lang]), "official_check": OFFICIAL_CHECK[lang], "limits": list(LIMITS[lang]), "validation_failed": False}


def analyze_v03(req, source, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    lang = _lang(req.get("language"))
    sit = req.get("situation")
    ctx = {"situation": sit, "name": req.get("claimed_name"), "pasted_text": req.get("pasted_text"), "claim_kind": req.get("claim_kind") or "REG_NUMBER", "too_many": False}
    if sit not in SITUATIONS:
        r = _base(lang, None, "NEEDS_SITUATION")
        r["prompt"] = {"en": "Please choose what has happened so far. Nothing has been checked yet.", "hi": "कृपया चुनें कि अब तक क्या हुआ है। अभी कुछ भी नहीं जाँचा गया है।"}[lang]
        return r
    resp = _base(lang, sit, "OK")
    resp["incident_guidance"] = guidance_for(sit, lang)
    number, origin = (req.get("claimed_number") or ""), "typed"
    text = req.get("pasted_text") or ""
    if not number.strip() and text.strip():
        ex = extract_numbers(text)
        if len(ex) > 1:
            ctx["too_many"] = True
        elif ex:
            number, origin = ex[0], "extracted_from_pasted_text"
    ctx["number"] = number
    has_claim = bool(number.strip() or (req.get("claimed_name") or "").strip() or text.strip() or ctx["too_many"] or ctx["claim_kind"] == "OTHER")
    if has_claim:
        try:
            ver = verify_claim(number, req.get("claimed_name"), req.get("category"), ctx["claim_kind"], source, now, too_many=ctx["too_many"])
        except Exception:
            ver = {"status": "SOURCE_ERROR", "reason": None, "claim": {}, "register_record": None, "candidates": [], "match_count": None, "provenance": [], "as_of": None}
        resp["source_verification"] = _card(ver, lang, origin)
    viol = validate(resp, ctx, now)
    if viol:  # safe fallback: guidance stays, source result withdrawn
        resp["validation_failed"] = True; resp["violations"] = viol
        if has_claim:
            resp["source_verification"] = _card({"status": "SOURCE_ERROR", "reason": None, "claim": {}, "register_record": None, "candidates": [], "match_count": None, "provenance": [], "as_of": None}, lang, origin)
    return resp
