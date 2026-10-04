"""Output text. English by default; Hindi headline/actions/labels are AUTHOR-TRANSLATED and NOT reviewed by a native
speaker or domain expert. Claim explanations stay in English (disclosed in `limitations`)."""
from .actions import ACTIONS

HEAD = {
 "HIGH_CONCERN": dict(en="Several warning signs were found. Do not pay or share anything until you have verified this through official channels.",
                      hi="कई चेतावनी संकेत मिले हैं। आधिकारिक माध्यम से जांच किए बिना कुछ भी न भेजें और कोई जानकारी साझा न करें।"),
 "SOME_CONCERN": dict(en="Some warning signs were found. Verify through official channels before you act.",
                      hi="कुछ चेतावनी संकेत मिले हैं। कदम उठाने से पहले आधिकारिक माध्यम से जांच करें।"),
 "NO_INDICATORS_FOUND": dict(en="No warning signs matched this tool's rules. This is not a safety guarantee: it only means nothing known was detected.",
                      hi="इस टूल के नियमों में कोई चेतावनी संकेत नहीं मिला। यह सुरक्षा की गारंटी नहीं है: इसका मतलब केवल यह है कि कुछ ज्ञात नहीं मिला।"),
 "ABSTAIN": dict(en="This tool cannot assess this message reliably, so it gives no assessment.",
                 hi="यह टूल इस संदेश का भरोसेमंद आकलन नहीं कर सकता, इसलिए कोई आकलन नहीं दे रहा।"),
}
LOSS_HEAD = dict(en="You may have already been targeted. Act as quickly as you can: contact your bank through its official number and call 1930 or report at cybercrime.gov.in. Official channels cannot promise that money will be returned.",
                 hi="हो सकता है आप धोखाधड़ी का शिकार हो चुके हों। जितनी जल्दी हो सके कदम उठाएं: बैंक के आधिकारिक नंबर पर संपर्क करें और 1930 पर कॉल करें या cybercrime.gov.in पर रिपोर्ट करें। आधिकारिक माध्यम पैसे लौटने का वादा नहीं कर सकते।")
STATE_LABEL = {
 "SUPPORTED": dict(en="Supported by trusted sources", hi="विश्वसनीय स्रोतों से समर्थित"),
 "CONTRADICTED": dict(en="Contradicted by trusted sources", hi="विश्वसनीय स्रोतों से विरोधाभासी"),
 "MIXED": dict(en="Mixed / partly supported", hi="मिश्रित / आंशिक"),
 "INSUFFICIENT": dict(en="Insufficient evidence", hi="अपर्याप्त प्रमाण"),
 "NOT_ASSESSED": dict(en="Not assessed", hi="आकलन नहीं किया गया"),
}
ABSTAIN_REASONS = {
 "too_short": dict(en="The text is too short to contain anything checkable.", hi="पाठ इतना छोटा है कि उसमें जांचने लायक कुछ नहीं।"),
 "empty_or_non_text": dict(en="No readable text was provided.", hi="कोई पढ़ने योग्य पाठ नहीं मिला।"),
 "image_stub": dict(en="Image input is not implemented in this prototype (no OCR). Paste the text of the message instead.", hi="इस प्रोटोटाइप में इमेज इनपुट उपलब्ध नहीं है (OCR नहीं)। संदेश का पाठ चिपकाएं।"),
 "unsupported_language": dict(en="This language is not supported by this prototype's analysis.", hi="इस भाषा का विश्लेषण इस प्रोटोटाइप में समर्थित नहीं है।"),
 "limited_language_no_findings": dict(en="This language has only limited support and no clear findings were produced; absence of findings here is not reassurance.", hi="इस भाषा के लिए सीमित समर्थन है और कोई स्पष्ट निष्कर्ष नहीं मिला; निष्कर्ष न मिलना आश्वासन नहीं है।"),
 "non_financial": dict(en="The text does not appear to be about money, investing or accounts, so it is outside this tool's scope.", hi="पाठ पैसे, निवेश या खातों से संबंधित नहीं लगता, इसलिए यह इस टूल के दायरे से बाहर है।"),
 "injection_only": dict(en="The text contains instructions aimed at this tool and nothing else checkable. They were not followed.", hi="पाठ में इस टूल को दिए निर्देश हैं, और जांचने लायक कुछ और नहीं। उनका पालन नहीं किया गया।"),
 "too_long": dict(en="The text is longer than the 20,000-character limit.", hi="पाठ 20,000 अक्षरों की सीमा से लंबा है।"),
 "advice_request": dict(en="This is a request for investment picks or price targets. This tool does not give stock tips, price predictions or buy/sell/hold guidance.", hi="यह निवेश सुझाव या मूल्य-लक्ष्य का अनुरोध है। यह टूल स्टॉक टिप्स, मूल्य अनुमान या खरीद/बिक्री/होल्ड सलाह नहीं देता।"),
 "validation_failed": dict(en="Internal safety checks failed, so the output was withheld.", hi="आंतरिक सुरक्षा जांच विफल रही, इसलिए परिणाम रोक दिया गया।"),
}
GENERIC_LIMITS = {
 "en": ["Indicators are warning signs, not proof of fraud. Claims were checked only against a small fixed set of sources; unknown claims are not assessed.",
        "This tool does not give investment advice, stock tips or price predictions."],
 "hi": ["संकेत चेतावनी हैं, धोखाधड़ी का प्रमाण नहीं। दावों को केवल स्रोतों के एक छोटे निश्चित समूह से जांचा गया; अज्ञात दावों का आकलन नहीं होता।",
        "यह टूल निवेश सलाह, स्टॉक टिप्स या मूल्य अनुमान नहीं देता।"],
}
HI_EXPL_NOTE = "Claim explanations are in English; Hindi translation of explanations is not provided in this prototype."
LANG_LIMIT = {"mr": "Marathi support is limited (small keyword list only); results may miss warning signs.",
              "ta": "Tamil support is limited (small keyword list only); results may miss warning signs.",
              "hinglish": "Romanised Hindi (Hinglish) is handled with a small hand-written word list; results may miss warning signs."}


def t(d, lang):
    return d[lang] if lang in d else d["en"]


def action_item(key, lang):
    from .actions import action_id_for_output
    a = ACTIONS[key]
    return {"action_id": action_id_for_output(key), "text": t(a, lang), "sources": list(a["sources"])}
