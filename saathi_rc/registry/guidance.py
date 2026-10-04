"""Module M-INC: incident guidance from the user-selected situation only. Static, sourced texts; no dependence on any other module."""
from .contract import HARM, QUESTIONS, COND_PREFIX
from .guidance_data import ACTIONS

URGENT_IDS = ["A_CALL_1930", "A_CONTACT_BANK", "A_PRESERVE_EVIDENCE"]


def _act(i, lang, conditional=False):
    a = ACTIONS[i]; t = a.get(lang) or a["en"]
    return {"id": i, "text": (COND_PREFIX[lang] + t) if conditional else t, "conditional": conditional, "sources": a["sources"]}


def guidance_for(situation, lang="en"):
    if situation in HARM:
        return {"mode": "URGENT", "questions": [], "actions": [_act(i, lang) for i in URGENT_IDS] + [_act("A_NO_PAY_NO_SHARE", lang)]}
    if situation == "UNSURE":
        return {"mode": "FOLLOWUP", "questions": list(QUESTIONS[lang]), "actions": [_act(i, lang, True) for i in URGENT_IDS]}
    if situation == "NO_ACTION_YET":
        return {"mode": "PREVENTIVE", "questions": [], "actions": [_act(i, lang) for i in ("A_NO_PAY_NO_SHARE", "A_OFFICIAL_CALLBACK", "A_SEBI_CHECK_PAYEE")]}
    return {"mode": "NONE", "questions": [], "actions": []}
