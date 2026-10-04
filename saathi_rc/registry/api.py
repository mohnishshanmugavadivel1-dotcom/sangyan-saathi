"""Single entry point for the OPTIONAL register step. Never raises; any failure becomes a SOURCE_ERROR card. Contains no message analysis."""
import datetime as dt
from .engine import analyze_v03
from .contract import LANGS

REMINDER = {
    "en": "Even a match only shows that an entry exists on SEBI's list. Scammers can quote a real registered name and number. A match does not show who contacted you, and it says nothing about the offer, the returns, a link, an app or a payment account. It does not lower the warnings above.",
    "hi": "मिलान का मतलब केवल इतना है कि सेबी की सूची में एक प्रविष्टि है। ठग असली पंजीकृत नाम और संख्या का उपयोग कर सकते हैं। मिलान से यह पता नहीं चलता कि आपसे किसने संपर्क किया, और ऑफ़र, रिटर्न, लिंक, ऐप या भुगतान खाते के बारे में कुछ नहीं पता चलता। इससे ऊपर की चेतावनियाँ कम नहीं होतीं।",
}


def check_registration(number, name, category, source, lang="en", now=None):
    lang = lang if lang in LANGS else "en"
    now = now or dt.datetime.now(dt.timezone.utc)
    req = {"situation": "UNSURE", "claimed_number": number or "", "claimed_name": name or "", "category": category or None, "language": lang, "claim_kind": "REG_NUMBER"}
    try:
        r = analyze_v03(req, source, now=now)
        card = r["source_verification"]
        failed = r.get("validation_failed", False)
    except Exception:
        card, failed = None, True
    if card is None:
        card = {"status": "NOT_CHECKABLE", "reason": "NO_REGISTRATION_NUMBER", "headline": "Nothing was checked", "means": "", "does_not_mean": "", "register_record": None, "candidates": [],
                "as_of": None, "provenance": [], "source": {}, "number_checked": None}
    return {"card": card, "reminder": REMINDER[lang], "effect_on_message_result": "none", "validation_failed": failed, "language": lang}
