"""Module M-INC: incident guidance from the user-selected situation only. Static, sourced texts; no dependence on any other module."""
from .contract import HARM, QUESTIONS, COND_PREFIX
from .guidance_data import ACTIONS, COND_TEXT, COND_FOLLOW

URGENT_IDS = ["A_CALL_1930", "A_CONTACT_BANK", "A_PRESERVE_EVIDENCE"]


def _act(i, lang, conditional=False, follow=False):
    a = ACTIONS[i]; t = a.get(lang) or a["en"]
    if conditional: t = (COND_TEXT.get(i) or {}).get(lang) or t
    return {"id": i, "text": ((COND_FOLLOW if follow else COND_PREFIX)[lang] + (t[0].lower() + t[1:] if lang == "en" else t)) if conditional else t, "conditional": conditional, "sources": a["sources"]}


def guidance_for(situation, lang="en"):
    if situation in HARM:
        return {"mode": "URGENT", "questions": [], "actions": [_act(i, lang) for i in URGENT_IDS] + [_act("A_NO_PAY_NO_SHARE", lang)]}
    if situation == "UNSURE":
        return {"mode": "FOLLOWUP", "questions": list(QUESTIONS[lang]), "actions": [_act(i, lang, True, follow=(n > 0)) for n, i in enumerate(URGENT_IDS)]}
    if situation == "NO_ACTION_YET":
        return {"mode": "PREVENTIVE", "questions": [], "actions": [_act(i, lang) for i in ("A_NO_PAY_NO_SHARE", "A_OFFICIAL_CALLBACK", "A_SEBI_CHECK_PAYEE")]}
    return {"mode": "NONE", "questions": [], "actions": []}
