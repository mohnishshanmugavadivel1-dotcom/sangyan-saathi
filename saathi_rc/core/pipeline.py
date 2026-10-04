"""Entry point: analyze(request) -> result. Deterministic, offline, no network, no model calls.

normalize -> (abstain gates) -> extract -> derive -> retrieve+assess -> posture -> actions -> render -> validate (fail closed)
"""
import hashlib
import re

from . import PIPELINE_VERSION
from .contracts import (validate_request, ContractError, HIGH_CONCERN, SOME_CONCERN, NO_INDICATORS_FOUND, ABSTAIN,
                        CONTRADICTED, MIXED, INSUFFICIENT, NOT_ASSESSED)
from .normalize import normalize, mask_sensitive
from .extract import extract
from .assess import assess_claim, derive
from .posture import posture_for
from .actions import choose
from .render import LOSS_HEAD, HEAD, STATE_LABEL, ABSTAIN_REASONS, GENERIC_LIMITS, HI_EXPL_NOTE, LANG_LIMIT, t, action_item
from .validate import validate
from .corpus import Corpus

LANG_STATUS = {"en": "supported", "hi": "supported", "hinglish": "supported", "mixed": "supported", "mr": "limited", "ta": "limited"}
FIN_RE = re.compile(r"(?i)(invest|stock|share|sebi|nse\b|bse\b|demat|mutual|sip\b|bank|account|a/c|upi|otp|kyc|trading|trade|returns?|profit|loan|ipo\b|₹|\brs\.?\b|\binr\b|lakh|crore|paisa|rupee|bond|pension|gold|scheme|fund|"
                    r"निवेश|शेयर|सेबी|खाता|खाते|बैंक|म्यूचुअल|म्युच्युअल|रिटर्न|मुनाफा|रुपये|पैसे|पैसा|ट्रेडिंग|डीमैट|परतावा|खाते|பங்கு|கணக்கு|வங்கி|முதலீடு|வருமானம்|செபி)")
ADVICE_RE = re.compile(r"(?i)\b(which|what)\b.{0,15}\b(stock|share|fund)s?\b.{0,25}\b(buy|invest)\b|\b(buy|sell|hold)\b.{0,30}\b(target|price)s?\b|target prices?|\bdouble my money\b")

_CORPUS = None


class FixtureRegistry:
    """PRIVILEGED TEST FIXTURE. Fictional registry used only when a request carries registry_fixture."""
    def __init__(self, d):
        self.d = {k.upper(): v for k, v in d.items()}

    def lookup(self, reg):
        return self.d.get(reg.upper())


def get_corpus():
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = Corpus()
    return _CORPUS


def _abstain_result(req, reason_key, lang_out, norm=None, claims=None, indicators=None, language="unknown", language_support="unknown",
                    validation_errors=None, corpus=None, extra_actions=None, situation="UNKNOWN"):
    claims = claims or []
    indicators = indicators or []
    acts = []
    if norm is not None and corpus is not None:
        acts, loss = choose(ABSTAIN, claims, indicators, norm, situation, True)
    acts = extra_actions or acts
    reason = t(ABSTAIN_REASONS[reason_key], lang_out)
    limits = list(GENERIC_LIMITS[lang_out if lang_out in GENERIC_LIMITS else "en"])
    return {
        "schema_version": "1.0", "pipeline_version": PIPELINE_VERSION, "request_id": req.get("request_id", ""),
        "posture": ABSTAIN, "headline": t(HEAD[ABSTAIN], lang_out), "summary": reason, "language": language, "language_support": language_support,
        "claims": claims, "indicators": indicators,
        "next_steps": [action_item(a, lang_out) for a in acts], "limitations": limits,
        "abstention": {"abstained": True, "reason_code": reason_key, "reason": reason, "validation_failed": reason_key == "validation_failed",
                       "validation_errors": validation_errors or []},
        "provenance": {"corpus_version": corpus.version if corpus else None, "input_sha256": hashlib.sha256(req["text"].encode("utf-8")).hexdigest()},
    }


def analyze(req, corpus=None):
    corpus = corpus or get_corpus()
    try:
        validate_request(req)
    except ContractError as e:
        return {"error": "invalid_request", "detail": str(e), "pipeline_version": PIPELINE_VERSION}
    lang_out = req.get("output_language", "en")
    situation = req.get("user_situation", "UNKNOWN")
    itype = req.get("input_type", "text")
    text_in = req["text"]
    fixture = req.get("registry_fixture")
    registry = FixtureRegistry(fixture) if fixture else None

    # ---- gates that do not need analysis
    if len(text_in) > 20000:
        return _abstain_result(req, "too_long", lang_out, corpus=corpus)
    if itype == "image_stub":
        return _abstain_result(req, "image_stub", lang_out, corpus=corpus)
    norm = normalize(text_in, itype)
    alnum = sum(ch.isalnum() for ch in norm["text"])
    if alnum == 0:
        return _abstain_result(req, "empty_or_non_text", lang_out, norm=norm, corpus=corpus, situation=situation)
    if alnum < 5:
        return _abstain_result(req, "too_short", lang_out, norm=norm, corpus=corpus, situation=situation)
    lang = norm["language"]
    lang_code = lang.split(":")[0] if lang.startswith("unsupported") else lang
    support = LANG_STATUS.get(lang, "unsupported")
    if lang_out == "en" and lang == "hi":
        lang_out = "hi"          # answer in the user's language when it is Hindi

    # ---- extraction (structural indicators are language independent, so they run even for unsupported languages)
    ext = extract(norm)
    d_claims, d_inds = derive(corpus, norm, ext)
    claims_raw = ext["claims"] + d_claims
    inds = ext["indicators"] + d_inds
    if support == "unsupported":
        # only structural (language-independent) indicators are trustworthy here
        struct = {"PERSONAL_PAYEE", "SHORTENED_LINK", "LOOKALIKE_DOMAIN", "OBFUSCATION", "GROUP_INVITE"}
        inds = [i for i in inds if i["indicator"] in struct]
        return _abstain_result(req, "unsupported_language", lang_out, norm=norm, indicators=_clean_inds(inds), language=lang, language_support=support, corpus=corpus, situation=situation)

    # ---- assessment
    claims, seen = [], set()
    for c in claims_raw:
        key = (c["claim_type"], c.get("match"))
        if key in seen:
            continue
        seen.add(key)
        a = assess_claim(corpus, c, norm, registry)
        claims.append({"claim_id": "C%d" % (len(claims) + 1), "claim_type": c["claim_type"], "snippet": c["snippet"], "state": a["state"],
                       "state_label": t(STATE_LABEL[a["state"]], lang_out), "evidence": a["evidence"], "explanation": a["explanation"], "limitations": a["limitations"]})
    # one SEBI_REG / GUARANTEED claim per type is enough for the user: collapse duplicates of the same type+state
    claims = _collapse(claims)
    indicators = _clean_inds(inds)

    # ---- abstain on out-of-scope content
    only_inj = indicators and all(i["indicator"] == "PROMPT_INJECTION" for i in indicators) and not claims
    if only_inj:
        return _abstain_result(req, "injection_only", lang_out, norm=norm, indicators=indicators, language=lang, language_support=support, corpus=corpus, situation=situation)
    if ADVICE_RE.search(norm["text"]) and not any(c["state"] == CONTRADICTED for c in claims):
        return _abstain_result(req, "advice_request", lang_out, norm=norm, claims=claims, indicators=indicators, language=lang, language_support=support, corpus=corpus, situation=situation)
    if not claims and not indicators:
        if not FIN_RE.search(norm["text"]) and not norm["entities"]["urls"]:
            return _abstain_result(req, "non_financial", lang_out, norm=norm, language=lang, language_support=support, corpus=corpus, situation=situation)
        if support == "limited":
            return _abstain_result(req, "limited_language_no_findings", lang_out, norm=norm, language=lang, language_support=support, corpus=corpus, situation=situation)

    posture, score, parts = posture_for(claims, indicators)
    acts, loss = choose(posture, claims, indicators, norm, situation, False)
    headline = t(HEAD[posture], lang_out)
    if loss:
        # the user reports a loss/exposure: never return a 'nothing found' posture; lead with urgent official steps
        posture = HIGH_CONCERN
        headline = t(LOSS_HEAD, lang_out)
    limits = list(GENERIC_LIMITS[lang_out if lang_out in GENERIC_LIMITS else "en"])
    if lang in LANG_LIMIT:
        limits.append(LANG_LIMIT[lang])
    if lang_out == "hi":
        limits.append(HI_EXPL_NOTE)
    if loss:
        limits.append("No route guarantees that lost money can be returned; act quickly and use official channels only.")
    if any(c["claim_type"] == "SEBI_REG_CLAIM" and any(e["passage_id"] == "FIXTURE-REGISTRY" for e in c["evidence"]) for c in claims):
        limits.append("A fictional test registry was used for SEBI registration status; this is not a real SEBI lookup.")
    summary = "%d claim(s) and %d warning sign(s) found." % (len(claims), len(indicators))
    result = {
        "schema_version": "1.0", "pipeline_version": PIPELINE_VERSION, "request_id": req.get("request_id", ""),
        "posture": posture, "headline": headline, "summary": summary, "language": lang, "language_support": support,
        "claims": claims, "indicators": indicators,
        "next_steps": [action_item(a, lang_out) for a in acts], "limitations": limits,
        "abstention": {"abstained": False, "reason_code": None, "reason": "", "validation_failed": False, "validation_errors": []},
        "posture_score_parts": parts, "posture_score": score,
        "provenance": {"corpus_version": corpus.version, "input_sha256": hashlib.sha256(text_in.encode("utf-8")).hexdigest(),
                       "normalisation_flags": norm["flags"], "active_loss_mode": loss},
    }
    errs = validate(result, corpus, norm, situation if not loss else "PAID_MONEY" if situation not in ("PAID_MONEY", "SHARED_CREDENTIALS", "INSTALLED_REMOTE_APP") else situation, fixture_mode=registry is not None)
    if errs:
        return _abstain_result(req, "validation_failed", lang_out, validation_errors=errs, corpus=corpus, language=lang, language_support=support,
                               extra_actions=["A_NO_PAY_NO_SHARE"] + (["A_CALL_1930", "A_CONTACT_BANK", "A_PRESERVE_EVIDENCE"] if loss else []))
    return result


def _clean_inds(inds):
    seen, out = set(), []
    for i in inds:
        if i["indicator"] in seen:
            continue
        seen.add(i["indicator"])
        out.append(i)
    return out


def _collapse(claims):
    seen, out = set(), []
    for c in claims:
        k = (c["claim_type"], c["state"])
        if k in seen:
            continue
        seen.add(k)
        c = dict(c)
        c["claim_id"] = "C%d" % (len(out) + 1)
        out.append(c)
    return out
