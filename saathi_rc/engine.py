"""analyze(request) -> result.  Situation gate -> (cues) -> v0.1 claim/indicator pipeline (copied in core/) -> freshness -> composition -> fail-closed validation.

Request: {"situation": one of SITUATIONS, "text": str, "input_type": "text"|"ocr_text"|"image_stub", "output_language": "en"|"hi", "request_id": str}
Deterministic, offline (no network, no model calls), does not store or log the input."""
import re
from . import VERSION, CONTRACT_VERSION, clock
from .contract import *
from .cues import situation_conflict_cues, pending_cues, surface_of, structural_pattern, link_threat_pattern, credential_request, other_cues, PAST_VERB, SUBJ, _CLAUSE_SPLIT as _LEGACY_SPLIT, _verb_negated
from . import incident as inc_mod
from .core.pipeline import analyze as analyze_core, get_corpus
from .core.normalize import normalize, mask_sensitive
from .core.posture import posture_for
from .core import render as core_render
from . import freshness
from .validate import validate
from .registry.inputs import extract_numbers, classify_number

BAD = ("CONTRADICTED", "MIXED", "INSUFFICIENT", "NOT_ASSESSED")
CRITICAL_INDICATORS = {"CREDENTIAL_REQUEST", "REMOTE_ACCESS_APP", "APK_DOWNLOAD", "LOOKALIKE_DOMAIN", "MULE_RECRUITMENT"}


def _lang(req):
    l = req.get("output_language") if isinstance(req, dict) else None
    return l if l in LANGS else "en"


def step(aid, lang, conditional=False, urgent=False, follow=False):
    a = ACTIONS[aid]
    txt = a.get(lang) or a["en"]
    if conditional:
        txt = (COND_TEXT.get(aid) or {}).get(lang) or txt
        txt = (COND_FOLLOW if follow else COND_PREFIX)[lang] + (txt[0].lower() + txt[1:] if lang == "en" else txt)
    return {"action_id": aid, "text": txt, "sources": list(a["sources"]), "conditional": conditional, "urgent": urgent}


def cond_block(lang):
    return [step(a, lang, True, follow=(i > 0)) for i, a in enumerate(ESCALATION_SET)]


def _base(req, lang, situation, posture, urgent=(), steps=(), **kw):
    r = {"contract_version": CONTRACT_VERSION, "version": VERSION, "request_id": str(req.get("request_id", ""))[:64] if isinstance(req, dict) else "", "language": lang,
         "situation": situation, "posture": posture, "headline": HEADLINE[posture][lang], "summary": kw.pop("summary", ""),
         "urgent_steps": list(urgent), "steps": list(steps), "questions": kw.pop("questions", []), "options": kw.pop("options", []),
         "claims": kw.pop("claims", []), "indicators": kw.pop("indicators", []), "unavailable": kw.pop("unavailable", []),
         "registry_offer": kw.pop("registry_offer", {"available": False, "numbers": []}),
         "limitations": list(LIMITS[lang]) + (list(HI_NOTES) if lang == "hi" else []) + list(kw.pop("extra_limits", [])),
         "block_order": ["urgent_steps", "assessment", "steps", "registry", "unavailable", "limitations"],
         "incident": kw.pop("incident", None), "freshness": kw.pop("freshness", None), "provenance": {"engine": "saathi_rc", "validation_failed": False, "validation_errors": []}}
    r["provenance"].update(kw.pop("prov", {}))
    return r


def _options(lang):
    return [{"code": k, "text": v[lang]} for k, v in SITUATION_OPTIONS.items()]


def _mask_simple(s):
    return re.sub(r"\d[\d\s-]{4,}\d", "[number hidden]", s or "")


def _incident_obj(inc, lang, source, applied, reasons=(), conflict=False):
    """The object shown to the user (and rendered by the web view without changes): state, the quoted clause(s), how it was applied."""
    evs = [{"actor": e["actor"], "action": e["action"], "status": e["status"], "timing": e.get("timing", ""), "confidence": e["confidence"], "snippet": e.get("snippet", "")}
           for e in inc.get("events", []) if e["status"] != "DENIED" or inc["state"] in ("USER_DENIES",)][:4]
    return {"state": inc["state"], "active": list(inc["active"]), "source": source, "applied": applied, "label": INCIDENT_LABEL[inc["state"]][lang],
            "also": [INCIDENT_LABEL[s][lang] for s in inc["active"] if s != inc["state"] and s != "NO_INCIDENT"], "events": evs, "risk_context": list(reasons),
            "note": INCIDENT_NOTE[applied][lang] if applied in INCIDENT_NOTE else "", "conflict_note": INCIDENT_CONFLICT[lang] if conflict else "", "confidence": inc.get("confidence")}


def _form_incident(situation, lang):
    st = {"PAID_MONEY": "USER_PAID", "SHARED_CREDENTIALS": "USER_SHARED_CREDENTIAL", "PAYMENT_PENDING": "USER_PAYMENT_PENDING"}.get(situation)
    if not st: return None
    return _incident_obj({"state": st, "active": [st], "events": [], "confidence": "HIGH"}, lang, "form", "form")


def _unexplained_legacy(legacy, text, inc):
    """Keep the older first-person cues only for verbs the incident reader did NOT classify (its own events carry actor and status), and never for a verb whose nearest subject is someone else."""
    from collections import Counter
    explained = Counter(e["verb"] for e in inc["events"] if e["action"] in ("PAYMENT", "CREDENTIAL"))
    out = [c for c in legacy if not c.startswith("past_action:")]
    for clause in _LEGACY_SPLIT.split(text or ""):
        if not clause or not clause.strip(): continue
        for v in PAST_VERB.finditer(clause):
            if not SUBJ.search(clause[max(0, v.start() - 70):v.start()]) or _verb_negated(clause, v.start(), v.end()): continue
            verb = v.group(0).lower()
            if explained[verb] > 0: explained[verb] -= 1; continue
            if inc_mod.actor_before(clause, v.start()) == inc_mod.THIRD: continue
            out.append("past_action:" + verb)
    return out


def _risk_reasons(norm, inc, situation, corpus, itype, legacy=()):
    """Why an unconfirmed report of a completed payment is treated as urgent (heuristic, closed list, see STATE_MODEL.md section 3)."""
    text = norm["text"]; out = list(inc_mod.risk_context(text))
    if situation == "PAYMENT_PENDING": out.append("you chose that you are being asked to pay")
    oc = other_cues(text)
    if oc: out.append("the text describes a bad outcome (%s)" % oc[0].replace("_", " "))
    r1 = analyze_core({"text": text, "user_situation": "NO_ACTION_YET", "input_type": itype if itype in ("text", "ocr_text", "image_stub") else "text", "output_language": "en"}, corpus)
    if r1.get("posture") == "HIGH_CONCERN" or (r1.get("posture") == "SOME_CONCERN" and len(r1.get("indicators", [])) >= 2): out.append("the text itself shows warning signs")   # a single weak indicator (e.g. the word 'pay') is not enough on a user's own narrative
    if structural_pattern(surface_of(norm))[0]: out.append("the text asks for money or codes with pressure or promises")
    if credential_request(text): out.append("the text asks for a code, PIN or password")
    if re.search(r"(?i)\b(?:click|open|install|download|scann?|approv|grant|enter)\w*\b[^.;]{0,25}\b(?:link|attachment|file|apk|anydesk|teamviewer|remote|qr|(?:they|he|she) sent|sent me|website)\b", text): out.append("the text also describes clicking, opening or installing something sent by the other side")
    return out


def _harm_incident(req, lang, situation):
    o = _form_incident(situation, lang)
    if o is None: return None
    try:
        txt = req.get("text") if isinstance(req.get("text"), str) else ""
        inc = inc_mod.read(txt, mask=_mask_simple) if txt.strip() else None
        if inc and inc["state"] == "USER_DENIES" and situation in ("PAID_MONEY", "SHARED_CREDENTIALS"):
            o["conflict_note"] = INCIDENT_CONFLICT[lang]
            o["events"] = [{"actor": e["actor"], "action": e["action"], "status": e["status"], "timing": e.get("timing", ""), "confidence": e["confidence"], "snippet": e.get("snippet", "")} for e in inc["events"] if e["status"] == "DENIED"][:2]
    except Exception:
        pass
    return o


def _escalation_urgent(lang, pending):
    return ([step("A_STOP_PAYMENT", lang, urgent=True)] if pending else []) + [step(a, lang, urgent=True) for a in ESCALATE_STEPS]


def _escalate_from_text(req, lang, situation, inc, reasons, pending):
    r = _base(req, lang, situation, "ESCALATE", urgent=_escalation_urgent(lang, pending), options=_options(lang), incident=_incident_obj(inc, lang, "text", "escalated_from_text", reasons),
              extra_limits=["This tool did not assess the message: when money or access may already be lost, speed matters more.", "No route guarantees that lost money can be returned; act quickly and use official channels only."] if lang == "en" else [],
              prov={"incident_route": "escalated_from_text"})
    r["provenance"]["pending"] = bool(pending)
    return r


def safe_fallback(req, lang, situation, errors):
    if situation in ("NO_ACTION_YET", "PAYMENT_PENDING", "UNSURE") and isinstance(req, dict):
        # S4: a validator or internal failure must never turn a reported payment or credential share into 'cannot assess'
        try:
            txt = req.get("text") if isinstance(req.get("text"), str) else ""
            inc = inc_mod.read(txt, mask=_mask_simple)
            if inc["state"] in inc_mod.USER_REPORT_STATES:
                r = _escalate_from_text(req, lang, situation, inc, ["(fallback: the normal route failed, so the cautious route was used)"], situation == "PAYMENT_PENDING")
                r["provenance"].update({"validation_failed": True, "validation_errors": list(errors)[:8]}); return r
        except Exception:
            pass
    if situation in HARM:
        r = _base(req, lang, situation, "ESCALATE", urgent=[step(a, lang, urgent=True) for a in ESCALATE_STEPS])
    elif situation not in SITUATIONS:
        r = _base(req, lang, situation, "NEEDS_SITUATION", steps=cond_block(lang), options=_options(lang), summary=SITUATION_QUESTION[lang])
    else:
        urgent = [step("A_STOP_PAYMENT", lang, urgent=True)] if situation == "PAYMENT_PENDING" else []
        r = _base(req, lang, situation, "CANNOT_ASSESS", urgent=urgent, steps=[step("A_OFFICIAL_CALLBACK", lang)] + cond_block(lang))
    r["provenance"]["validation_failed"] = True
    r["provenance"]["validation_errors"] = list(errors)[:8]
    return r


def _fallback_notice(req, res):
    """S3 FIX-2: if the caller asked for an output language that is not offered, say that the result is in English (never silently)."""
    raw = req.get("output_language") if isinstance(req, dict) else None
    if isinstance(raw, str) and raw and raw not in LANGS and isinstance(res, dict) and res.get("unavailable") is not None:
        res["unavailable"].append({"code": "OUTPUT_LANGUAGE_FALLBACK", "text": UNAVAILABLE_TEXT[res.get("language", "en")]["OUTPUT_LANGUAGE_FALLBACK"]})
    return res


def analyze(req, corpus=None):
    lang = _lang(req)
    situation = req.get("situation") if isinstance(req, dict) else None
    try:
        corpus = corpus or get_corpus_rc()
        res, ctx = _analyze(req, lang, situation, corpus)
        errs = validate(res, corpus, ctx)
        return _fallback_notice(req, safe_fallback(req, lang, situation, errs) if errs else res)
    except Exception as ex:  # fail closed
        return _fallback_notice(req, safe_fallback(req if isinstance(req, dict) else {}, lang, situation, ["exception: %s" % type(ex).__name__]))


_CORPUS = None


def get_corpus_rc():
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = get_corpus()
    return _CORPUS


def _analyze(req, lang, situation, corpus):
    ctx = {"situation": situation, "norm": None, "surface": [], "langsup": True, "floor": 0, "pending": False, "unresolved": False}
    if situation not in SITUATIONS:
        return _base(req, lang, situation, "NEEDS_SITUATION", steps=cond_block(lang), options=_options(lang), summary=SITUATION_QUESTION[lang]), ctx
    if situation in HARM:
        urgent = [step(a, lang, urgent=True) for a in ESCALATE_STEPS] + ([step("A_NO_REMOTE", lang, urgent=True)] if situation == "ACCESS_GRANTED" else [])
        return _base(req, lang, situation, "ESCALATE", urgent=urgent, incident=_harm_incident(req, lang, situation), extra_limits=["This tool did not assess the message: when money or access may already be lost, speed matters more.", "No route guarantees that lost money can be returned; act quickly and use official channels only."] if lang == "en" else []), ctx
    # ---- NO_ACTION_YET / PAYMENT_PENDING (and UNSURE: the text is read too, so a stated payment or code share is never silently ignored)
    text = req.get("text") if isinstance(req.get("text"), str) else ""
    itype = req.get("input_type", "text")
    ctx["today"] = clock.today()
    norm = normalize(text, itype if itype in ("text", "ocr_text", "image_stub") else "text")
    ctx["norm"] = norm
    msk = lambda t: mask_sensitive(t, norm.get("sensitive_runs"))
    inc = inc_mod.read(norm["text"], mask=msk)                      # S4: who did what, with what status
    legacy, negated = situation_conflict_cues(norm["text"])
    legacy = _unexplained_legacy(legacy, norm["text"], inc)         # verbs the reader attributed to someone else / denied / hedged are not the user's report
    cues = legacy
    pend_early = pending_cues(norm["text"])
    if situation != "PAYMENT_PENDING" and inc.get("pending_aborted"): pend_early = []   # "I was about to pay but stopped"
    pending_now = situation == "PAYMENT_PENDING" or bool(pend_early)
    if pending_now and "USER_PAYMENT_PENDING" not in inc["active"]:
        inc["active"] = [s for s in inc_mod.PRECEDENCE if s in set(inc["active"]) | {"USER_PAYMENT_PENDING"} and s != "NO_INCIDENT"]; inc["state"] = inc["active"][0]
    ctx["incident"] = inc
    if inc["state"] == "NO_INCIDENT":
        # Sprint Oct-4 (X13/X14/X15): a subject-less completed payment WITH explicit structural risk context is not treated as "no incident"
        sl = inc_mod.subjectless_payment_context(inc, norm["text"])
        if sl:
            inc["state"] = "PAYMENT_UNCLEAR"; inc["active"] = ["PAYMENT_UNCLEAR"]; inc["confidence"] = inc_mod.LOW; inc["subjectless_context"] = sl
    st = inc["state"]
    if st == "PAYMENT_UNCLEAR" and inc.get("subjectless_context"):
        ctx["pending"] = pending_now
        r = _escalate_from_text(req, lang, situation, inc, inc["subjectless_context"], pending_now)
        r["incident"]["label"] = SUBJECTLESS_LABEL[lang]
        r["provenance"]["incident_route"] = "escalated_subjectless_payment_with_context"
        return r, ctx
    if st in ("USER_SHARED_CREDENTIAL", "UNAUTHORISED_DEBIT", "USER_PAID", "THIRD_PARTY_PAID") or (st == "PAYMENT_UNCLEAR"):
        reasons = None
        if st in ("USER_PAID", "THIRD_PARTY_PAID"):
            reasons = _risk_reasons(norm, inc, situation, corpus, itype, legacy)
        if st in ("USER_SHARED_CREDENTIAL", "UNAUTHORISED_DEBIT") or (st == "USER_PAID" and reasons):
            ctx["pending"] = pending_now
            return _escalate_from_text(req, lang, situation, inc, reasons or (["money left your account without your action or knowledge"] if st == "UNAUTHORISED_DEBIT" else ["a code, PIN or password was shared"]), pending_now), ctx
        qk = {"USER_PAID": "paid_unconfirmed", "PAYMENT_UNCLEAR": "unclear", "THIRD_PARTY_PAID": "third_party"}[st]
        if st != "THIRD_PARTY_PAID" or reasons:
            stop = [step("A_STOP_PAYMENT", lang, urgent=True)] if pending_now else []
            ctx["pending"] = pending_now
            return _base(req, lang, situation, "ASK_FOLLOWUP", urgent=stop, steps=[step("A_NO_PAY_NO_SHARE", lang)] + cond_block(lang), questions=[INCIDENT_QUESTIONS[qk][lang]] + list(FOLLOWUP_QUESTIONS[lang]), options=_options(lang),
                         incident=_incident_obj(inc, lang, "text", "follow_up", reasons or []), prov={"followup_reason": "incident_" + qk, "cues": [], "negated_statements_ignored": len(negated)}), ctx
    if situation == "UNSURE":
        # Phase 5: choosing "I'm not sure" must not drop the stop-payment step when the text itself says a payment is about to be made
        stop = [step("A_STOP_PAYMENT", lang, urgent=True)] if pending_now else []
        ctx["pending"] = pending_now
        return _base(req, lang, situation, "ASK_FOLLOWUP", urgent=stop, steps=[step("A_NO_PAY_NO_SHARE", lang)] + cond_block(lang), questions=list(FOLLOWUP_QUESTIONS[lang]), options=_options(lang),
                     incident=_incident_obj(inc, lang, "text", "follow_up", []) if inc["state"] != "NO_INCIDENT" else None, prov={"followup_reason": "unsure"}), ctx
    if cues:
        # S3 FIX-1 (D09/D18): the user's own choice "payment pending" must never lose the stop-payment step because the text also contains a past-tense cue
        stop = [step("A_STOP_PAYMENT", lang, urgent=True)] if situation == "PAYMENT_PENDING" else []
        return _base(req, lang, situation, "ASK_FOLLOWUP", urgent=stop, steps=[step("A_NO_PAY_NO_SHARE", lang)] + cond_block(lang), questions=list(FOLLOWUP_QUESTIONS[lang]), options=_options(lang),
                     incident=_incident_obj(inc, lang, "text", "follow_up", []) if inc["state"] != "NO_INCIDENT" else None,
                     prov={"followup_reason": "situation_conflict", "cues": cues[:6], "negated_statements_ignored": len(negated)}), ctx
    pend = pend_early
    pending = situation == "PAYMENT_PENDING" or bool(pend)
    ctx["pending"] = pending
    r1 = analyze_core({"text": text, "user_situation": "NO_ACTION_YET", "input_type": itype if itype in ("text", "ocr_text", "image_stub") else "text", "output_language": "en"}, corpus)
    surf = surface_of(norm)
    ctx["surface"] = surf
    if "error" in r1:
        raise ValueError("core rejected request")
    p1 = r1["posture"]
    langsup = r1.get("language_support") == "supported"
    ctx["langsup"] = langsup
    reason = r1["abstention"].get("reason_code") if r1["abstention"]["abstained"] else None
    claims_raw = [dict(c) for c in r1["claims"]]
    for c in claims_raw:
        c.pop("limitations", None)
    inds = [dict(i) for i in r1["indicators"]]
    today = clock.today()
    # posture floor from detection only (claims BEFORE freshness downgrade: staleness must never lower concern)
    p_pre, score, _ = posture_for(claims_raw, inds)
    claims, snap = freshness.apply(claims_raw, corpus, today)
    strong = [x for x in surf if x != "pressure_terms"]
    fin_in_text = bool(core_render and re.search(r"(?i)money|rs\.?|₹|pay|account|invest|bank|upi|loan|return|profit|stock|share|fund|wallet", norm["text"]))
    if p1 in ("HIGH_CONCERN", "SOME_CONCERN"):
        posture = p1
    elif p1 == "ABSTAIN":
        if reason in ("unsupported_language", "limited_language_no_findings"):
            posture = "CANNOT_ASSESS"
        elif reason in ("non_financial", "advice_request", "injection_only", "too_short", "empty_or_non_text", "too_long", "image_stub") and not strong:
            posture = "ABSTAIN"
        else:
            posture = "CANNOT_ASSESS"
        if reason == "validation_failed":
            raise ValueError("core validation failed")
    else:   # core NO_INDICATORS_FOUND: this tool never turns it into a clean result
        posture = "CANNOT_ASSESS"
    # CH-01b: detection findings always count, even when the core abstained for another reason (found by the validator fallback on S1 case H15)
    if p_pre in ("HIGH_CONCERN", "SOME_CONCERN") and SEVERITY[posture] < SEVERITY[p_pre]:
        posture = p_pre
    # CH-02b: severity escalation rules owned by the rc layer (not by the copied core weights)
    names = {i["indicator"] for i in inds}
    ctypes = {c["claim_type"] for c in claims_raw}
    if posture in ("SOME_CONCERN", "CANNOT_ASSESS", "ABSTAIN") and (names & CRITICAL_INDICATORS or ("AUTHORITY_THREAT" in ctypes and "PAYMENT_DEMAND" in names)):
        posture = "HIGH_CONCERN"
    cr = credential_request(norm["text"])
    if cr and "CREDENTIAL_REQUEST" not in names:   # CH-09: rc-level cue for requests the core did not recognise
        sn = cr if len(cr) <= 90 else cr[:cr.rfind(" ", 0, 88)] + "..."
        inds.append({"indicator": "CREDENTIAL_REQUEST", "snippet": mask_sensitive(sn, norm.get("sensitive_runs")), "note": "asks you to share or send a code, PIN, password or card detail; real banks and brokers do not ask for these (pattern match, not proof)"})
        names.add("CREDENTIAL_REQUEST")
        if SEVERITY[posture] < SEVERITY["HIGH_CONCERN"]: posture = "HIGH_CONCERN"
    sp, parts = structural_pattern(surf)
    if sp and posture in ("CANNOT_ASSESS", "ABSTAIN"):
        posture = sp
        inds.append({"indicator": "REQUEST_PATTERN", "snippet": "(overall shape of the message)", "note": "asks for money or codes, gives a link/number/payment ID to act on, and uses pressure or big promises; this combination is common in scams (pattern match, not proof)"})
    if not sp and posture == "CANNOT_ASSESS" and link_threat_pattern(surf, norm["text"]):   # safety sprint S-2: SOME_CONCERN at most, never HIGH
        posture = "SOME_CONCERN"
        inds.append({"indicator": "REQUEST_PATTERN", "snippet": "(overall shape of the message)", "note": "gives a link to act on and warns of a consequence (a block, cut or expiry) if you do not; this combination is common in scams (pattern match, not proof)"})
    if posture == "ABSTAIN" and (inds or any(c["state"] in BAD for c in claims)):
        posture = "CANNOT_ASSESS"
    if pending and posture == "ABSTAIN":
        posture = "CANNOT_ASSESS"
    ctx["unresolved"] = any(c["state"] in BAD for c in claims) or bool(inds)
    ctx["floor"] = {"HIGH_CONCERN": 3, "SOME_CONCERN": 2, "NO_INDICATORS_FOUND": 1}.get(p_pre, 1) if (inds or claims_raw) else 0
    # ---- steps
    ids1 = [a["action_id"] for a in r1["next_steps"] if a["action_id"] not in ("A_CALL_1930",)]
    urgent = [step("A_STOP_PAYMENT", lang, urgent=True)] if pending else []
    steps = []
    if posture in ("HIGH_CONCERN", "SOME_CONCERN"):
        keep = list(ids1)
        if not ({"A_NO_PAY_NO_SHARE", "A_OFFICIAL_CALLBACK"} & set(keep)):
            keep.append("A_OFFICIAL_CALLBACK")
        steps = [step(a, lang) for a in keep if a not in ESCALATION_SET and a in ACTIONS]
    elif posture == "CANNOT_ASSESS":
        steps = [step("A_OFFICIAL_CALLBACK", lang)] + ([step("A_NO_PAY_NO_SHARE", lang)] if (surf or pending) else [])
        steps += [step(a, lang) for a in ids1 if a in ("A_NO_REMOTE", "A_VERIFY_REG", "A_SEBI_CHECK_PAYEE", "A_AVOID_GROUPS")]
    elif posture == "ABSTAIN":
        steps = [step("A_OFFICIAL_CALLBACK", lang)] if surf else []
    if pending and "A_OFFICIAL_CALLBACK" not in {s["action_id"] for s in steps}:
        steps.insert(0, step("A_OFFICIAL_CALLBACK", lang))
    seen, uniq = set(), []
    for s in steps:
        if s["action_id"] not in seen and s["action_id"] not in {u["action_id"] for u in urgent}:
            seen.add(s["action_id"]); uniq.append(s)
    uniq += cond_block(lang)
    # ---- summary
    W = WHY[lang]
    if posture == "CANNOT_ASSESS":
        why = []
        named = [SURFACE_PHRASE[lang][x] for x in surf if x in SURFACE_PHRASE[lang] and x != "other_script"]
        if "other_script" in surf:
            named.append(SURFACE_PHRASE[lang]["other_script"])
        if named:
            why.append(W["surface"] % ", ".join(named[:5]))
        if any(c["state"] in BAD for c in claims):
            why.append(W["unresolved"])
        if not langsup:
            why.append(W["lang"])
        if not why:
            why.append(W["none"])
        summary = W["prefix"] + "; ".join(why) + "."
    elif posture == "ABSTAIN":
        summary = core_render.t(core_render.ABSTAIN_REASONS[reason], lang) if reason in core_render.ABSTAIN_REASONS else ""
    else:
        summary = ("%d warning sign(s) recognised; %d claim(s) found in the message." if lang == "en" else "%d चेतावनी संकेत पहचाने गए; संदेश में %d दावे मिले।") % (len(inds), len(claims))
    # ---- unavailable / not checked (shown to the user as such)
    U = UNAVAILABLE_TEXT[lang]
    unavail = []
    nums = [n for n in extract_numbers(norm["text"]) if classify_number(n)[0] == "OK"]
    if nums or norm["entities"]["reg_numbers"]:
        unavail.append({"code": "REGISTRY_NOT_CHECKED", "text": U["REGISTRY_NOT_CHECKED"]})
    if norm["entities"]["urls"] or "url" in surf:
        unavail.append({"code": "LINK_NOT_OPENED", "text": U["LINK_NOT_OPENED"]})
    if norm["entities"]["phones"] or norm["entities"]["vpas"] or "phone_number" in surf or "upi_id_shape" in surf:
        unavail.append({"code": "PAYEE_NOT_CHECKED", "text": U["PAYEE_NOT_CHECKED"]})
    if snap["status"] in ("STALE", "UNKNOWN"):
        unavail.append({"code": "SOURCES_STALE", "text": U["SOURCES_STALE"]})
    elif snap["status"] == "AGING":
        unavail.append({"code": "SOURCES_AGING", "text": U["SOURCES_AGING"]})
    if r1["language_support"] == "limited" or r1["language"] == "mixed":   # S3 FIX-2b: mixed-script text (e.g. Marathi with Latin words) cannot be told apart from Hindi; say so
        unavail.append({"code": "LANGUAGE_LIMITED", "text": U["LANGUAGE_LIMITED"]})
    elif r1["language_support"] == "unsupported":
        unavail.append({"code": "LANGUAGE_UNSUPPORTED", "text": U["LANGUAGE_UNSUPPORTED"]})
    if itype == "image_stub":
        unavail.append({"code": "IMAGE_NOT_READ", "text": U["IMAGE_NOT_READ"]})
    extra = [LANG_LIMIT_TEXT[r1["language"]]] if r1["language"] in LANG_LIMIT_TEXT else []
    if snap["status"] in ("STALE", "UNKNOWN"):
        extra.append("Source snapshot is older than a year or undated: claim results were downgraded; contact numbers and portals should be confirmed on official sites.")
    shown_claims = [{k: v for k, v in c.items() if k not in ("snippet",)} | {"state_label": STATE_LABEL[c["state"]][lang], "snippet": c.get("snippet", "")} for c in claims]
    inc_shown = None
    if inc["state"] != "NO_INCIDENT":
        inc_shown = _incident_obj(inc, lang, "form" if (situation == "PAYMENT_PENDING" and not pend_early and not inc["events"]) else "text", "form" if (situation == "PAYMENT_PENDING" and not pend_early and not inc["events"]) else "analysis")
    r = _base(req, lang, situation, posture, urgent=urgent, steps=uniq, summary=summary, claims=shown_claims, incident=inc_shown, indicators=inds, unavailable=unavail,
              registry_offer={"available": bool(nums), "numbers": nums[:3]}, extra_limits=extra, freshness=snap,
              prov={"core_posture": p1, "core_language": r1["language"], "core_abstain_reason": reason, "request_surface": surf, "pending": pending, "pending_cues": pend,
                    "negated_statements_ignored": len(negated), "corpus_version": corpus.version, "core_version": r1["pipeline_version"]})
    r["headline"] = HEADLINE[posture][lang]
    if pending:
        r["pause_notice"] = PAUSE_HEAD[lang]
    return r, ctx
