"""Steps 2-3: claim extraction (checkable assertions) and observable risk-indicator extraction.

Rule-based by design (deterministic, auditable). Limitations are documented in the feasibility report:
 - vocabulary is fixed; novel phrasing / paraphrase will be missed;
 - Hindi (Devanagari) and Hinglish have hand-written patterns; Marathi/Tamil have only small keyword lists.
Advisory/negated sentences ("never share your OTP", "past performance is not a guarantee") are skipped
so that protective messages are not read as requests or claims.
"""
import re
from .normalize import mask_sensitive, mask_identifier

_V = r"(share|give|click|tell|send|reveal|disclose|download|install|provide|enter|pay|trust|fall|respond|open)"
ADVISORY_RE = re.compile(r"(?i)((\bnever|\bdo not|\bdon't|\bdont|\bshould not|\bshouldn't)\s+(ever\s+)?" + _V + r"\b|\bnot a guarantee\b|\bno guarantee\b|\bnot guaranteed\b|\bnot a guaranteed\b|\bbeware\b|\bcaution|\bsubject to market risk|"
                         r"\bverify\s+(the\s+)?(registration|sebi|advis[eo]r|adviser|analyst|before|with)\b|\bcheck\b.{0,40}\bregistration\b|\bregistration\b.{0,40}\bcheck\b|\bkar lena\b|"
                         r"कभी\s*(भी)?\s*(किसी|अपना|ओटीपी)|(साझा|शेयर|बताएं|क्लिक)\s*न\s*करें|सतर्क|जोखिम के अधीन)")
# sentences that merely ADVISE should not yield claims/indicators of the matched patterns
ADVISORY_SKIPS_CRED = re.compile(r"(?i)(\bnever\b|\bdo not\b|\bdon't\b|\bdont\b|\bdoes not\b|\bdoesn't\b|\bwill not\b|\bwon't\b|\bwill never ask\b|कभी|न बताएं|साझा न|\bnot share\b)")   # S3 FIX-4b: 'does not ask for an OTP' is a denial too

W = r"\b"
def R(p):
    return re.compile(p, re.I)

# ---------------- claim patterns ----------------
CLAIM_PATTERNS = {
    "GUARANTEED_RETURNS": [
        R(r"\bguarante+d\b"), R(r"\bguarantee\b"), R(r"\bassured\b"), R(r"\brisk[\s\-]?free\b"), R(r"\bno risk\b"), R(r"\bzero risk\b"),
        R(r"\b100\s?%\s?(safe|sure|accura|profit|return)"), R(r"\bsure[\s\-]?shot\b"), R(r"\bcannot lose money\b"), R(r"\bcan'?t lose money\b"),
        R(r"\bnever lost money\b"), R(r"\bpakka (profit|munafa|return)"), R(r"\bfixed returns?\b"),
        R(r"गारंटी|गारंटीड|पक्का मुनाफा|जोखिम बिल्कुल नहीं|निश्चित रिटर्न|हमखास|உத்தரவாத"),
    ],
    "SEBI_REG_CLAIM": [
        R(r"\bsebi[\s\-]?(registered|regd|reg\b|registration|approved|authori[sz]ed|certified)"), R(r"\bregistered with sebi\b"),
        R(r"\bregistration\s*(no|number)?\s*:?\s*IN[AHZ]"), R(r"\bIN[AHZ]\d{3,}\b"), R(r"\breg\.?\s*(no\.?)?\s*:?\s*IN[AHZ]"),
        R(r"सेबी\s*(रजिस्टर्ड|पंजीकृत)"), R(r"सेबी\s*नोंदणीकृत"), R(r"செபி\s*பதிவு"),
        R(r"\bsebi\s+reg\b"),
    ],
    "AUTHORITY_THREAT": [
        R(r"\b(arrest|digital arrest|summons|money laundering|legal action|warrant)\b"),
        R(r"\b(sebi|dot|trai|rbi)\b.{0,60}\b(ban(ned)?|fined?|penalty|disconnect(ed)?|suspend(ed)?)\b"),
    ],
    "ACCOUNT_BLOCK_KYC": [
        R(r"\b(account|a/c|demat|wallet)\b.{0,60}\b(block(ed)?|suspend(ed)?|expire[ds]?|freeze|frozen|deactivat(ed)?|band|closed)\b"),
        R(r"\bkyc\b.{0,40}\b(expire[ds]?|update|pending)\b.{0,60}\b(block|suspend|band|close)"),
        R(r"(खाता|खाते|अकाउंट).{0,30}(बंद|ब्लॉक)"), R(r"(கணக்கு).{0,30}(முடக்க|தடை)"),
    ],
    "OFFICIAL_PLATFORM_CLAIM": [
        R(r"\binstitutional\s+(account|access|trading|client)"), R(r"\bguarantee[d]?\s+(ipo\s+)?allot"), R(r"\b(ipo|allotment)\b.{0,30}\bguarantee"),
        R(r"\bpre[\s\-]?ipo\b"), R(r"\bblock (deal|trade)s?\b"), R(r"\bdiscounted ipo\b"),
    ],
    "ACCOUNT_HANDLING": [
        R(r"\b(give|share|send)\b.{0,15}\b(us|me)\b.{0,25}\b(trading|demat)\b.{0,20}\b(account|login|credentials|password)"),
        R(r"\bwe (will |shall )?(trade|operate|handle)\b.{0,25}\b(for you|your account)"), R(r"\baccount[\s\-]handling\b"), R(r"\bprofit[\s\-]shar"),
    ],
    "PERFORMANCE_CLAIM": [
        R(r"\bprofit(s)?\s+(of\s+)?(rs\.?|₹|inr)?\s*[\d,]+"), R(r"\bi (have )?earned\b"), R(r"\bmade\s+(rs\.?|₹)?\s*[\d,]+"),
        R(r"\b(avg|average|past)\b.{0,25}\b\d+(\.\d+)?\s*%"), R(r"\b\d+(\.\d+)?\s*%\s*(annual|p\.a\.|per annum)"),
        R(r"\b\d+\s*%\s*accura"), R(r"\bwithdrawn\b"), R(r"\bhas given about\b.{0,30}%"), R(r"\bhave given about\b.{0,30}%"),
    ],
    "MARKET_PREDICTION": [
        R(r"\bwill (go|cross|hit|touch|reach|double|triple|rise|jump)\b.{0,30}"), R(r"\btarget price"), R(r"\bdouble my money\b"),
    ],
    "ENDORSEMENT_CLAIM": [
        R(r"\b(finance minister|prime minister|minister|sitharaman|ambani|narayana murthy|celebrity)\b.{0,30}\b(recommend|endorse|invest|launch)"),
        R(r"\bauthori[sz]ed partner\b"), R(r"\bendorsed by\b"), R(r"\bapproved by (sebi|rbi|nsdl)\b"),
    ],
    "REFUND_CLAIM": [R(r"\brefund\b"), R(r"\bcashback of\b")],
    "UPI_PIN_TO_RECEIVE": [R(r"\b(enter|put)\b.{0,25}\bupi pin\b.{0,30}\b(receive|get|credit)"), R(r"\bpin\b.{0,25}\b(to receive)\b")],
    "BANK_ASKS_OTP_CLAIM": [R(r"\bbanks?\b.{0,25}\b(may|will|can|do|does)\b(?:(?!\bnever\b|\bnot\b|\bno\b|n't).){0,15}\b(call|ask)\b.{0,40}\botp\b")],   # S3 FIX-4: "will never call to ask for OTP" is a denial, not the claim
    "CHAKSHU_SCOPE_CLAIM": [R(r"\bchakshu\b")],
    "SCORES_SCOPE_CLAIM": [R(r"\bscores\b.{0,120}\b(unregistered|any broker|any adviser|recover)")],
    "VALID_HANDLE_CLAIM": [R(r"@valid\b")],
    "VERIFIED_BADGE_CLAIM": [R(r"\bverified (app )?(badge|label)\b"), R(r"\bsebi verified\b")],
}
ORG_RE = R(r"\b(sebi|nsdl|cdsl|rbi|npci|scores|sanchar saathi|chakshu|nse|bse)\b")
LINK_CLAIM_ORG_PROSE = ORG_RE

# claim types whose patterns must not fire inside advisory sentences
ADVISORY_SENSITIVE = {"GUARANTEED_RETURNS", "SEBI_REG_CLAIM", "ACCOUNT_BLOCK_KYC", "BANK_ASKS_OTP_CLAIM"}
# A 'never lost money' etc. is NOT advisory, but 'not a guaranteed return' is. Handle by sentence test below.

NEGATION_BEFORE_GUARANTEE = R(r"\b(not|no|isn'?t)\b.{0,15}\bguarante")

# ---------------- indicator patterns ----------------
IND = {
    "URGENCY": [R(r"\burgent\b"), R(r"\bimmediately\b"), R(r"\bwithin\s+\d+\s*(hours?|hrs?|minutes?|mins?)\b"), R(r"\blimited\s+(seats?|period|time|offer)\b"),
                R(r"\b(today|right now|now)\b(?!\s*(is|was))"), R(r"\bbefore midnight\b"), R(r"\blast date\b"), R(r"\baaj hi\b"), R(r"\bwarna\b"),
                R(r"\bjayega\b"), R(r"आज ही|आजही|आजच|अभी|आज|तुरंत|सीट बाकी|இன்றே|இன்று|உடனே"), R(r"\bexpire[ds]?\b"), R(r"\b(otherwise|else)\b.{0,40}\b(block|suspend|arrest|fine)")],
    "CREDENTIAL_REQUEST": [
        R(r"\b(share|send|tell|give|enter|provide|read out|reveal|dictate)\b.{0,30}\b(otp|upi pin|pin|cvv|password|passcode|login|credentials|verification code)\b"),
        R(r"\b(otp|pin|cvv|password|login|credentials)\b.{0,25}\b(share|send|tell|give|provide|bata|batao|daal|daalein|enter)"),
        R(r"\bask(s|ed)?\b.{0,20}\b(for )?(your )?(otp|pin|cvv|password)\b"),
        R(r"(otp|पिन|ओटीपी).{0,20}(बताएं|बताओ|बतायें|भेजें|साझा)"), R(r"(अपना|आपला|तुमचा).{0,10}otp.{0,10}(बताएं|सांगा|बताओ)"),
        R(r"otp.{0,12}(सांगा|बताएं|बताओ)"), R(r"otp.{0,12}(பகிர|சொல்ல)"),
        R(r"\botp\b.{0,15}\bdaal"),
    ],
    "REMOTE_ACCESS_APP": [R(r"\b(anydesk|teamviewer|quicksupport|quick support|airdroid|rustdesk|ammyy|supremo|screen[\s\-]?shar(e|ing)|remote (access|control))\b"),
                          R(r"टीमव्यूअर|एनीडेस्क")],
    "PAYMENT_DEMAND": [R(r"\b(pay|transfer|send|deposit|remit)\b(?!ed)\b.{0,40}(rs\.?|₹|inr|\d)"), R(r"\bsafe account\b"), R(r"\b(bhejo|bhejiye|jama karo)\b"),
                       R(r"(जमा करें|भेजें|भेजो|ट्रांसफर करें)"), R(r"\bpay (the )?(fee|tax|penalty|charges?)\b")],
    "UPFRONT_FEE": [R(r"\b(processing|registration|membership|release|withdrawal|clearance|activation)\s+(fee|charges?)\b"),
                    R(r"\bpay\b.{0,40}\b(tax|fee|charges?)\b.{0,40}\b(withdraw|release)"), R(r"\bto (withdraw|release)\b.{0,40}\bpay\b"),
                    R(r"\bpay\b.{0,60}\bto (release|withdraw|unlock)\b"), R(r"\bmust (first )?pay\b"), R(r"\bpay\b.{0,15}\bfee\b")],
    "GROUP_INVITE": [R(r"t\.me/"), R(r"chat\.whatsapp\.com/"), R(r"wa\.me/"), R(r"\b(join|add)\b.{0,25}\b(telegram|whatsapp)\b"), R(r"\b(telegram|whatsapp)\s+(group|channel)\b"),
                     R(r"(व्हाट्सएप|व्हॉट्सएप|टेलीग्राम).{0,20}(ग्रुप)"), R(r"ग्रुप जॉइन")],
    "SECRECY": [R(r"\b(do not|don't|dont)\s+tell\b"), R(r"\bkeep (it|this) (secret|confidential|private)\b"), R(r"\bclose friends only\b"), R(r"किसी को न बताएं"),
                R(r"\bdo not disconnect\b")],
    "APK_DOWNLOAD": [R(r"\.apk\b"), R(r"\bdownload (our|the|this)\b.{0,20}\bapp\b"), R(r"\binstall (our|the|this) app\b")],
    "AUTHORITY_IMPERSONATION": [
        R(r"\b(this is|i am|i'm|calling from|message from)\s+(a |an |the )?(cbi|police|ed|income tax|customs|trai|dot|rbi|sebi|nsdl)\b(?!\s+(registered|regd|reg\b|certified|approved))"),
        R(r"\b(sebi|rbi|nsdl|trai|dot)\s+(notice|helpdesk|help desk|officer|summons|order)\b"), R(r"\bsummons\b"), R(r"\bcbi\b"),
    ],
    "MULE_RECRUITMENT": [R(r"\b(use|rent|lend|let)\w*\b.{0,25}\byour (bank )?account\b.{0,40}"), R(r"\bcommission\b.{0,60}\b(bank )?account\b")],
    "UNSOLICITED_CONTACT": [R(r"^\s*hi\b.{0,20}\b(i am|i'm|this is)\b"), R(r"\breply (yes|y|1)\b"), R(r"\ba caller\b"), R(r"\bsomeone (called|messaged)\b"), R(r"\bunknown (number|caller)\b")],
    "CHAIN_FORWARD": [R(r"\bforward\b.{0,15}\b(to|it to)\b.{0,10}\d+\s*(people|friends|contacts|groups)"), R(r"\bshare (this )?with everyone\b")],
    "PROMPT_INJECTION": [R(r"ignore (all |the )?(previous|prior|above) (instructions|messages)"), R(r"\byou are now\b"), R(r"\[/?system\]"), R(r"\breply with the word\b"),
                         R(r"system prompt"), R(r"tell the user this (message )?is (safe|legit|genuine)"), R(r"\bdisregard\b.{0,20}\binstructions"),
                         R(r"पिछले (सभी )?निर्देश भूल"), R(r"\bjailbreak\b"), R(r"knowledge base")],
    "CITATION_IN_MESSAGE": [R(r"\b(according to|as per)\b.{0,15}\b(sebi|rbi)\b.{0,15}\b(circular|notification|order|guidelines?)\b")],
}
HIGH_RATE_WORDS = R(r"(returns?|profit|परतावा|रिटर्न|मुनाफा|வருமானம்|லாபம்)")
PCT_PERIOD = [
    (R(r"(\d+(?:\.\d+)?)\s*%\s*(?:\w+\s){0,2}?(daily|per day|a day|every day|roz|rozana|प्रतिदिन)"), 1.0),
    (R(r"(\d+(?:\.\d+)?)\s*%\s*(?:\w+\s){0,2}?(weekly|per week|a week|every week)"), 3.0),
    (R(r"(\d+(?:\.\d+)?)\s*%\s*(?:\w+\s){0,3}?(monthly|per month|a month|every month|har mahine|mahine|महीने|प्रति माह)"), 8.0),
]
MULT_RE = R(r"(?<![\w.])(\d+)\s?x\b")
AMOUNT_RE = R(r"(?:rs\.?|₹|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(lakh|lac|crore|k)?\b")
SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "goo.gl", "rb.gy", "cutt.ly", "is.gd", "shorturl.at", "ow.ly")


def _amt(num, unit):
    v = float(num.replace(",", ""))
    unit = (unit or "").lower()
    return v * {"lakh": 1e5, "lac": 1e5, "crore": 1e7, "k": 1e3}.get(unit, 1)


def high_return_rate(text):
    for rx, thr in PCT_PERIOD:
        m = rx.search(text)
        if m and float(m.group(1)) >= thr:
            return m
    m = MULT_RE.search(text)
    if m and int(m.group(1)) >= 3:
        return m
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*%", text):
        if float(m.group(1)) >= 20 and HIGH_RETURN_WORDS_NEAR(text, m.start()):
            return m
    # invest A ... get B in N days/week/month  with B/A >= 2
    m = re.search(r"(?i)(?:invest|pay|deposit|जमा करें|send)\D{0,12}(?:rs\.?|₹)?\s*(\d[\d,]*(?:\.\d+)?)\s*(lakh|lac|crore|k)?.{0,60}?(?:get|receive|earn|पाएं|पाओ|ke baad|and get|=>|to)\D{0,12}(?:rs\.?|₹)?\s*(\d[\d,]*(?:\.\d+)?)\s*(lakh|lac|crore|k)?.{0,25}?(\d+|one|a)\s*(day|days|week|weeks|month|months|दिन|हफ्ते|महीने)", text)
    if m:
        a, b = _amt(m.group(1), m.group(2)), _amt(m.group(3), m.group(4))
        n = m.group(5)
        n = 1 if not n.isdigit() else int(n)
        unit = m.group(6)
        days = n * (7 if unit.startswith(("week", "हफ्ते")) else 30 if unit.startswith(("month", "महीने")) else 1)
        if a > 0 and b / a >= 2 and days <= 31:
            return m
    m = re.search(r"(?i)(?:rs\.?|₹)?\s*(\d[\d,]*)\s*(lakh|lac|crore|k)?\s*(?:in|and|=>|को|पर).{0,40}?(?:rs\.?|₹)?\s*(\d[\d,]*)\s*(lakh|lac|crore|k)?\s*(?:in|within)\s*(?:one|a|\d+)\s*(day|days|week|month|months)", text)
    if m:
        a, b = _amt(m.group(1), m.group(2)), _amt(m.group(3), m.group(4))
        if a > 0 and b / a >= 2:
            return m
    # generic fallback: >=2 currency amounts whose ratio is >=2, plus a short time frame (<=31 days) in the same sentence
    tf = re.search(r"(?i)(\d+)\s*(days?|दिन|weeks?|हफ्ते|महीने|months?)", text)
    if tf:
        amts = [_amt(a, u) for a, u in re.findall(r"(?i)(?:rs\.?|₹|inr)\s*(\d[\d,]*(?:\.\d+)?)\s*(lakh|lac|crore|k)?", text)]
        amts = [x for x in amts if x > 0]
        n = int(tf.group(1))
        days = n * (7 if tf.group(2).lower().startswith(("week", "हफ्ते")) else 30 if tf.group(2).lower().startswith(("month", "महीने")) else 1)
        if len(amts) >= 2 and max(amts) / min(amts) >= 2 and days <= 31:
            return tf
    return None


def HIGH_RETURN_WORDS_NEAR(text, pos):
    return bool(HIGH_RATE_WORDS.search(text[max(0, pos - 40): pos + 40]))


def _snip(sent, m=None, runs=None):
    """RC CH-07 (post-hoc): cut only at token boundaries. The original cut mid-token, which showed confusing fragments such as '0 now' for 'Rs 5000 now'.
    (A possible leak of partial sensitive digit runs was probed with 72 synthetic cases and NOT found; no privacy claim rests on this change.)"""
    if m is None:
        s = sent.strip()
    else:
        a, b = max(0, m.start() - 15), min(len(sent), m.end() + 25)
        while a > 0 and a < m.start() and not sent[a - 1].isspace(): a += 1      # drop a partial leading token
        while b < len(sent) and b > m.end() and not sent[b].isspace(): b -= 1     # drop a partial trailing token
        s = sent[a:b].strip()
    if len(s) > 90:
        cut = s[:87]
        if " " in cut and not s[87].isspace(): cut = cut[:cut.rfind(" ")]
        s = cut + "..."
    return mask_sensitive(s, runs)


def extract(norm):
    """Return dict(claims=[...], indicators=[...], flags=...). Pure function of normalised input."""
    sents = norm["sentences"] or [norm["text"]]
    runs = norm["sensitive_runs"]
    ents = norm["entities"]
    claims, inds = [], []
    seen_ind = set()

    def add_ind(name, snippet, note=""):
        key = (name, snippet)
        if key in seen_ind:
            return
        seen_ind.add(key)
        inds.append({"indicator": name, "snippet": snippet, "note": note})

    for s in sents:
        advisory = bool(ADVISORY_RE.search(s))
        cred_advisory = bool(ADVISORY_SKIPS_CRED.search(s))
        neg_guarantee = bool(NEGATION_BEFORE_GUARANTEE.search(s))
        # ---- claims
        for ctype, pats in CLAIM_PATTERNS.items():
            if advisory and ctype in ADVISORY_SENSITIVE:
                # still allow the claim if the sentence also contains a non-advisory assertion after a contrast word
                if not re.search(r"(?i)\b(but|however|also)\b", s):
                    continue
            if ctype == "GUARANTEED_RETURNS" and neg_guarantee:
                continue
            for p in pats:
                m = p.search(s)
                if m:
                    claims.append({"claim_type": ctype, "snippet": _snip(s, m, runs), "sentence": s, "match": m.group(0)})
                    break
        # ---- indicators
        for name, pats in IND.items():
            if name == "CREDENTIAL_REQUEST" and cred_advisory and not re.search(r"(?i)\b(but|however|also|please)\b", s):
                continue
            if name == "URGENCY" and advisory:
                continue
            for p in pats:
                m = p.search(s)
                if m:
                    add_ind(name, _snip(s, m, runs))
                    break
        hr = high_return_rate(s)
        if hr:
            add_ind("HIGH_RETURN_RATE", _snip(s, hr, runs), "promised return is far above what regulated products offer (heuristic threshold)")
    # ---- structural indicators from entities (language-independent)
    for v in ents["vpas"]:
        if not v.lower().endswith("@valid") and ".valid" not in v.lower():
            add_ind("PERSONAL_PAYEE", mask_identifier(v), "payment address (UPI ID) given; not a SEBI '@valid' handle")
    org_kw = ("sebi", "nsdl", "cdsl", "rbi", "npci", "nseindia", "bseindia", "sancharsaathi", "cybercrime", "scores")
    return {"claims": claims, "indicators": inds, "org_kw": org_kw}
