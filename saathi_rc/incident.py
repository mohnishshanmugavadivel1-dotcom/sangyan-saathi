# -*- coding: utf-8 -*-
"""Incident-state reader (S4). Reads WHO did WHAT (payment / credential share), with what STATUS, from free text, clause by clause.
It is a transparent set of heuristics, not language understanding (see results/incident_state/STATE_MODEL.md). When actor, action or negation is unclear it says so
(LOW confidence / PAYMENT_UNCLEAR) instead of producing a definitive state. Passive or subject-less reports ("Rs 500 was sent", "Paid Rs 500 to X") create no user state on purpose,
because ordinary bank and merchant notices are written that way; the older first-person loss cues in cues.py still apply to them.
Pure functions, no I/O, deterministic."""
import re
from .cues import _verb_negated, NEG

USER, THIRD, UNKNOWN = "USER", "THIRD", "UNKNOWN"
PAYMENT, CREDENTIAL = "PAYMENT", "CREDENTIAL"
COMPLETED, UNCERTAIN, DENIED, ATTEMPTED = "COMPLETED", "UNCERTAIN", "DENIED", "ATTEMPTED"
HIGH, LOW = "HIGH", "LOW"
STATES = ("USER_PAID", "USER_SHARED_CREDENTIAL", "UNAUTHORISED_DEBIT", "USER_PAYMENT_PENDING", "PAYMENT_UNCLEAR", "THIRD_PARTY_PAID", "SENDER_CLAIMS_PAYMENT", "USER_DENIES", "NO_INCIDENT")
PRECEDENCE = ("USER_SHARED_CREDENTIAL", "UNAUTHORISED_DEBIT", "USER_PAID", "PAYMENT_UNCLEAR", "USER_PAYMENT_PENDING", "THIRD_PARTY_PAID", "SENDER_CLAIMS_PAYMENT", "USER_DENIES", "NO_INCIDENT")
USER_REPORT_STATES = ("USER_PAID", "USER_SHARED_CREDENTIAL", "UNAUTHORISED_DEBIT")

# ------------------------------------------------------------------ subjects
_U = r"i|i've|ive|i'd|we|we've|maine|mene|humne|hamne|main\s?ne|mai\s?ne|hum\s?ne|main|mai|hum|मैंने|मैं|हमने|हम|मुझसे|मी|आम्ही|நான்|நாங்கள்"
USER_SUBJ = re.compile(r"(?i)^(?:" + _U + r")$")
_KIN = ("father mother dad mom mum papa mummy brother sister wife husband son daughter uncle aunt cousin friend colleague neighbour neighbor boss grandfather grandmother in-laws "
        "broker advisor adviser agent manager company firm sender caller bank scammer fraudster dealer merchant shop person man woman someone somebody he she they it "
        "screenshot message email receipt document statement sms letter website app page group team executive officer mentor trader operator representative platform").split()
THIRD_WORDS = set(_KIN) | set("unhone usne unho woh wo vo ve unka unki uska uski kisi unhe उन्होंने उन्होने उसने वह वे वो किसी पापा भाई बहन माँ पिताजी पत्नी पति".split())
INANIMATE = set("screenshot message email receipt document statement sms letter website app page group platform bank shop link file apk attachment pdf photo video qr form".split())
THIRD_POSS = re.compile(r"(?i)^(?:his|her|their|its|the|a|an)$")
YOU = {"you", "your", "you've", "youve", "aapne", "आपने", "tumne", "तुमने", "आप"}
NOT_SUBJ_NOUNS = set("money amount funds payment sum rs inr rupees cash fee fees charge charges deposit transaction transfer proceeds dividend salary refund bill bills".split())
_TOK = re.compile(r"[^\s.,;:!?()\[\]\"“”‘’।]+")


_NON_SUBJECT_POSTPOSITIONS = frozenset("ko ka ki ke se को का की के से".split())


def _toks(s): return [(m.group(0), m.start(), m.end()) for m in _TOK.finditer(s)]


def _marker(tok, prev):
    """-> USER / THIRD / None for one token (prev = previous token, for 'X ne' / possessive + kin)."""
    t = tok.lower()
    if USER_SUBJ.match(tok): return USER
    if t in YOU: return THIRD
    if t in THIRD_WORDS: return THIRD
    return None


def actor_before(clause, pos, floor=0):
    """Nearest subject marker in clause[floor:pos]; 'X ne'/'X ने' (ergative) with X not first person counts as THIRD."""
    toks = [x for x in _toks(clause[floor:pos])]
    last = None; last_i = -1
    for i, (w, a, b) in enumerate(toks):
        m = _marker(w, None)
        if m is not None and i + 1 < len(toks) and toks[i + 1][0].lower() in _NON_SUBJECT_POSTPOSITIONS: m = None   # Sprint Oct-4 (X11): "trader ko ... transfer kar diya": "ko/ka/ki/ke/se" mark a recipient, possessor or source, not the subject
        if m is None and i + 1 < len(toks) and toks[i + 1][0].lower() in ("ne", "ने") and not USER_SUBJ.match(w):
            m = THIRD
        if m is None and w.lower() in ("ne", "ने") and i > 0 and not USER_SUBJ.match(toks[i - 1][0]):
            m = THIRD
        if m is None and w.lower() in ("ne", "ने") and i > 0 and USER_SUBJ.match(toks[i - 1][0]): m = USER
        if m: last = m; last_i = i
    # coordinated predicate: "I opened the app and paid ...": an inanimate noun that is the object of the user's own verb is not the subject of "paid"
    if last == THIRD and last_i < len(toks) and toks[last_i][0].lower() in INANIMATE and any(_marker(w, None) == USER for w, _, _ in toks[:last_i]):
        tail = [w.lower() for w, _, _ in toks[last_i + 1:]]
        if tail and len(tail) <= 3 and tail[0] in ("and", "then", "&") and all(w in ("and", "then", "also", "just", "already", "immediately", "quickly", "&") for w in tail):
            return USER
    # relative clause: "I opened the file they sent and paid ...": [inanimate] [they/he/she] [verb] and <verb>
    if last == THIRD and last_i >= 1 and toks[last_i - 1][0].lower() in INANIMATE and any(_marker(w, None) == USER for w, _, _ in toks[:last_i - 1]):
        tail = [w.lower() for w, _, _ in toks[last_i + 1:]]
        ks = [k for k, w in enumerate(tail) if w in ("and", "then", "&")]
        if ks and ks[0] in (1, 2) and (ks[0] == 1 or tail[1] in ("me", "us")) and all(w in ("and", "then", "also", "just", "already", "immediately", "quickly", "&") for w in tail[ks[0]:]):
            return USER
    return last


# ------------------------------------------------------------------ payment lexicon (grouped by what they mean; extended by structure below, not by case)
_MONEY_OBJ = (r"(?:(?:₹|rs\.?|inr|rupees?)\s?[\d,.]+|\b\d{1,3}(?:,\d{2,3})+\b|\b\d{4,}\b|\b\d+(?:\.\d+)?\s?(?:k|lakh|lakhs|crore|crores|cr)\b|\b(?:the |my |that |this |our |their |some |any |all |more )?"
              r"(?:money|amount|sum|funds?|fees?|payments?|deposit|dues|charges?|tax(?:es)?|cash|rupees?|paise|paisa|rupaye|installments?|instalments?|premium|commission|bill|balance)\b|पैसे|पैसा|रुपये|रकम|राशि|शुल्क|फीस)")
PAY_CLEAR = (r"paid|transferred|transfered|wired|remitted|deposited|invested|settled|paid out|topped up|funded|"
             r"pay kar diya|pay kar diye|payment kar diya|payment kiya|transfer kar diya|transfer kar diye|transfer kiya|transfer kar di|jama kar diya|jama kar diye|jama kar di|jama kiya|jama karwa diya|bhar diya|bhar di|bhar diye|"
             r"भुगतान कर दिया|भुगतान किया|ट्रांसफर कर दिया|ट्रांसफर कर दिए|ट्रांसफर किया|ट्रांसफर किए|जमा कर दिया|जमा कर दिए|जमा कर दी|जमा किया|जमा कराया|भर दिया|भर दी|भर दिए|चुका दिया")
PAY_NEEDS_OBJECT = (r"sent|gave|given|put in|handed over|handed|forwarded|credited|cleared|paid in|"
                    r"bhej diya|bhej diye|bhej di|bheja|bheje|de diya|de diye|de di|diya|diye|bhej chuka|bhej chuki|bhej chuke|"
                    r"भेज दिया|भेज दिए|भेज दी|भेजा|भेजे|दे दिया|दे दिए|दे दी|दिया|दिए|भेज चुका|भेज चुकी|भेज चुके")
_PAY_CLEAR = re.compile(r"(?i)(?<![\w\u0900-\u097F])(?:" + PAY_CLEAR + r")(?![\w\u0900-\u097F])")
_PAY_OBJ = re.compile(r"(?i)(?<![\w\u0900-\u097F])(?:" + PAY_NEEDS_OBJECT + r")(?![\w\u0900-\u097F])")
_PAY_LIGHT = re.compile(r"(?i)\b(?:made|did|done|completed|processed|initiated|authori[sz]ed|approved|finished)\b\s+(?:(?:the|a|an|my|that|this|our|one|another|first|second)\s+){0,2}(?:\w+\s+){0,1}(?:payment|transfer|transaction|deposit|remittance|investment)s?\b")
_DID_BASE = re.compile(r"(?i)\bdid\s+(?:also\s+|actually\s+|just\s+)?(pay|transfer|deposit|send|share|tell|give|provide|read out|make)\b")
_GAVE_ME_NON_PAYMENT = re.compile(r"(?i)(?:gave|given|give)\s+(?:me|us)\s+(?:until|till|time|a\s+deadline|\d+\s+(?:hours?|days?|minutes?)|(?:a|the|my)\s+(?:\w+\s+)?(?:receipt|slip|invoice|number|id|link|code)\b)")
_MODAL_PASSIVE = re.compile(r"(?i)\b(?:must|should|shall|will|would|can|could|may|might|has to|have to|needs? to|need to|ought to|to|got to|gotta)\s+(?:also\s+|first\s+|immediately\s+)?be\s*$")
_PAY_CHUKA = re.compile(r"(?i)(?:bhej|transfer kar|jama kar|pay kar|bhar)\s+(?:chuka|chuki|chuke)|(?:भेज|जमा कर|ट्रांसफर कर|भर)\s+(?:चुका|चुकी|चुके)")
# ------------------------------------------------------------------ credential lexicon
_CRED_STRONG = r"(?:otp|one[- ]time[- ](?:password|code|pin)|upi pin|mpin|pin|cvv|cvc|password|passcode|passwd|login details?|login|credentials|card number|card details?|card no|verification code|security code|(?:\d|four|six|4|6)[- ]?digit\s+(?:code|number|pin|otp)|ओटीपी|पासवर्ड|पिन|कार्ड नंबर)"
_CRED_STRONG_RX = re.compile(r"(?i)(?<![\w\u0900-\u097F])" + _CRED_STRONG + r"(?![\w\u0900-\u097F])")
_POSTAL_PIN = re.compile(r"(?i)\bpin\s?code\b")
_CODE_WEAK = re.compile(r"(?i)(?<!referral )(?<!promo )(?<!coupon )(?<!discount )(?<!invite )(?<!gift )(?<!voucher )(?<!zip )(?<!area )(?<!source )(?<!postal )(?<!country )(?<!offer )\bcode\b(?!\s*(?:of conduct|word))")
_SHARE_EN = re.compile(r"(?i)\b(?:shared|told|gave|given|sent|read out|forwarded|dictated|provided|revealed|disclosed|typed|texted|whatsapped|messaged|spoke|said)\b")
_SHARE_HI = re.compile(r"(?i)(?<![\w\u0900-\u097F])(?:bata diya|bata di|bataya|bata chuka|bata chuki|bhej diya|bheja|de diya|de di|share kar diya|share kiya|share kar di|बता दिया|बता दी|बताया|बता चुका|बता चुकी|भेज दिया|भेजा|दे दिया|दे दी|साझा कर दिया|साझा किया|शेयर कर दिया|शेयर किया)(?![\w\u0900-\u097F])")
_ENTRY = re.compile(r"(?i)\b(?:entered|filled(?:\s+in|\s+out)?|submitted|keyed\s+in|punched\s+in|typed\s+in|put\s+in|inputted|input)\b")
_ENTRY_BLOCK = re.compile(r"(?i)\b(?:if|whether|should|would|could|suppose|supposing|what if|in case|never|almost|nearly|about to|going to|will|want to|wanted to|plan(?:ning)? to|asked me to|told me to|before)\b")
_EXT_PAGE = re.compile(r"(?i)\b(?:page|link|site|website|form|portal|screen|app|url)\b[^.;!?]{0,60}?\b(?:opened from|came from|from (?:the |an? |that |their |his |her )?(?:sms|text|message|email|e-mail|whatsapp|telegram|caller|call|stranger|agent|link)|(?:the |that )?(?:sms|message|caller|agent|stranger|they|he|she|someone)\s+(?:sent|gave|shared|forwarded|texted)|sent\s+(?:by|me|to me))|\b(?:link|page|website)\s+(?:in|from)\s+(?:the |an? )?(?:sms|message|text|email|whatsapp)\b")
_PROHIBIT = re.compile(r"(?i)\b(?:never|not|no|don'?t|do not|dont|avoid|without|nahi|nahin|kabhi)\b|नहीं|कभी|मत\b|\bto (?:share|tell|give|send|read|provide)\b")
# ------------------------------------------------------------------ status markers
_DENY_BASE = re.compile(r"(?i)\b(?:did\s*not|didn'?t|didnt|have\s*not|haven'?t|havent|has\s*not|hasn'?t|had\s*not|hadn'?t|never|would\s*never|will\s*not|won'?t|do\s*not|don'?t|dont|could\s*not|couldn'?t|cannot|can'?t|refuse[ds]?\s+to|decided\s+against|not\s+going\s+to)\s+(?:\w+\s+){0,2}?(pay|paying|paid|send|sending|sent|transfer|transferring|transferred|deposit|depositing|deposited|wire|wired|give|giving|gave|share|sharing|shared|tell|telling|told|reveal|revealed|read out|complete[d]?|make (?:the |a |any )?(?:payment|transfer|transaction|deposit|investment)s?|made (?:the |a |any )?(?:payment|transfer|transaction|deposit|investment)s?)\b")
_DENY_PHRASE = re.compile(r"(?i)\b(?:i|we)\s+(?:said no|refused|declined|hung up|walked away|did nothing|paid nothing|sent nothing|shared nothing|gave nothing)\b|\b(?:nothing|no money|not a (?:rupee|paisa|penny))\b[^.?!;\n]{0,25}\b(?:left|gone|deducted|debited|went|sent|paid)\b|\bmoney\b[^.?!;\n]{0,12}\bnever (?:left|went)\b|\b(?:paid|sent|shared|gave|transferred)\s+(?:nothing|nobody|no one|none)\b|\brefused\b")
_DENY_HI = re.compile(r"(?:नहीं|नही|nahi|nahin|nhi)\s+(?:\S+\s+){0,2}(?:भेजा|भेजे|दिया|दिए|बताया|किया|भरा|जमा किया|bheja|bheje|diya|diye|bataya|kiya)|(?:पैसा|पैसे|paisa|paise|otp|ओटीपी)\s+(?:\S+\s+){0,2}(?:नहीं|nahi)\s+(?:\S+\s+){0,1}(?:दिया|दिए|बताया|भेजा|भेजे|diya|bataya|bheja|bheje)")
_ABORT = re.compile(r"(?i)\b(?:but|and|then|so|though)\s+(?:i\s+|we\s+)?(?:then\s+)?(?:stopped|decided against|changed my mind|cancelled|canceled|backed out|held back|refused|declined|hung up|walked away|closed the app|did not go ahead|didn'?t go ahead)\b|\b(?:bank|app)\s+blocked\b|\bblocked the (?:transaction|payment)\b|\bchanged my mind\b|\bdecided against\b")
_ATTEMPT = re.compile(r"(?i)\b(?:tried|trying|attempted|attempting)\s+to\s+(?:pay|send|transfer|deposit|wire)\b|\bclicked\s+(?:on\s+)?pay\b|\bpressed\s+pay\b")
_FAILED = re.compile(r"(?i)\b(?:failed|declined|error|did not go through|didn'?t go through|not go through|not completed|not complete|was cancelled|got cancelled|timed out|unsuccessful)\b")
_HEDGE = re.compile(r"(?i)\b(?:not sure|unsure|not certain|do not remember|don'?t remember|cannot remember|can'?t remember|cannot recall|can'?t recall|do not recall|don'?t recall|do not know (?:if|whether)|don'?t know (?:if|whether)|maybe|perhaps|might have|may have|i think|i guess|i believe|not clear whether|no idea whether)\b|याद नहीं|पता नहीं|पक्का नहीं|शायद|pata nahi|pata nhi|yaad nahi|yaad nhi|shayad|pakka nahi")
_FUTURE = re.compile(r"(?i)\b(?:will|shall|should|would|going to|plan(?:ning)?|about to|tomorrow|tonight|next|intend|want to|wish to|ready to)\b|आज रात|वाला हूँ|वाली हूँ|भेजूँगा|भेजूंगा|भेजूँगी|भेजूंगी|करूँगा|करूंगा|दूँगा|दूंगा|aaj raat|(?:wala|wali) ho+n|(?:wala|wali) hu+n|karunga|karungi|karna hai|bhejunga|bhejungi")   # "कल" / "kal" mean both yesterday and tomorrow, so they are not a future marker on their own
_PAY_CONTEXT = re.compile(r"(?i)\b(?:payment|transaction|transfer|paid|pay|sent|send|money|amount|went through|go through|gone through|got through|code|otp|pin|clicked pay|deposit|wired)\b|पैसे|पैसा|लेन-देन|भेजा|भेजे|रकम|paise|paisa|bheja|bheje|gaya|gaye|गए|गया|ओटीपी")
_REVERSAL = re.compile(r"(?i)\b(?:returned|refunded|reversed|bounced|rolled back|credited back|sent (?:it|the money|the amount) back|gave (?:it|the money|the amount) back)\b|\b(?:wapas|vapas) (?:kar|aa|aaya|mil)|वापस (?:कर|आ|मिल|लौट)|लौटा")
_REPORT = re.compile(r"(?i)\b(?:said|says|saying|claim(?:s|ed|ing)?|told|tells|mention(?:s|ed)|stated?|states|wrote|writes|messaged|insist(?:s|ed)?|alleg(?:es|ed)|assur(?:es|ed)|confirm(?:s|ed)|shows?|showed)\b|(?<![\w\u0900-\u097F])(?:kaha|kehta|kehte|keh rahe|keh rahi|bola|bol rahe|bol rahi|bolte|bataya|bata rahe|कहा|कहते|कहता|कह रहे|कह रही|बोला|बोल रहे|बताया|बता रहे)(?![\w\u0900-\u097F])")
_TIMING = [("recent", re.compile(r"(?i)\b(?:yesterday|last (?:night|week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|ago|this (?:morning|afternoon|evening)|earlier|today|just now|already|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|कल|आज|पिछले|kal|aaj|pichle")),
           ("future", re.compile(r"(?i)\b(?:tomorrow|tonight|will|going to|about to)\b")), ]
_PARTIAL = re.compile(r"(?i)\b(?:part of|partly|partial(?:ly)?|half|some of|first (?:instal+ment|payment|part)|a portion)\b|आंशिक|आधा|कुछ हिस्सा")
_FROM_USER_ACCOUNT = re.compile(r"(?i)\bfrom my\b[^.;]{0,15}\b(?:account|card|wallet|upi|savings|bank)\b|\bmere (?:account|card|khate)\b[^.;]{0,12}\bse\b|मेरे (?:खाते|अकाउंट|कार्ड) से")
# Phase 5: money left the user's own account AND the text says the user did not do / authorise / recognise it. Two explicit conditions, both required.
_MONEY_OUT = re.compile(r"(?i)\b(?:debit(?:ed)?|deduct(?:ed|ion)?|withdr(?:ew|awn|awal)|charged?|charge|transfer(?:red)?|paid|sent|payment|money|amount|funds?|cash|collect request|took|taken|take|stole|stolen|drained|siphoned|\\d[\\d,.]*)\b[^.;!?\n]{0,60}\b(?:from|out of|in|on|of|using|via|through)\s+my\s+(?:\w+\s+){0,2}(?:account|card|wallet|savings|upi|bank|demat)\b|\b(?:money|amount|funds?|cash)\s+(?:has\s+|have\s+|had\s+|just\s+)?(?:left|gone from|vanished from|disappeared from)\s+my\s+(?:\w+\s+)?(?:account|card|wallet|savings)\b|\bmy\s+(?:\w+\s+){0,2}(?:account|card|wallet)\s+(?:was|got|has been|is|shows?|showed|had)\b[^.;!?\n]{0,40}\b(?:debit(?:ed)?|charged|deduct(?:ed)?|transfer|withdraw\w*|payment)\b|\b(?:debit|charge|withdrawal|transfer|transaction|payment|deduction)s?\b[^.;!?\n]{0,30}\b(?:on|in|from|to)\s+my\s+(?:\w+\s+){0,2}(?:account|card|statement|passbook)\b|मेरे\s+(?:खाते|अकाउंट|कार्ड)\s+से|mere\s+(?:account|khate|card)\s+se")
_NOT_ME = re.compile(r"(?i)\b(?:never made|never did|never approved|never authori[sz]ed|(?:did not|didn'?t|do not|don'?t|have not|haven'?t|had not|hadn'?t)\s+(?:\w+\s+){0,2}?(?:make|made|do|did|authori[sz]e[d]?|approve[d]?|initiate[d]?|send|sent|pay|paid|recogni[sz]e|know|give|permit|allow|share)|(?:cannot|can'?t|could not|couldn'?t)\s+(?:recogni[sz]e|identify)|not recogni[sz]ed|unrecogni[sz]ed|unknown|unfamiliar|unauthori[sz]ed|without (?:my|any) (?:knowledge|permission|consent|approval|authori[sz]ation)|not (?:me|mine|done by me)|no idea (?:who|what|why|where)|who did|visited|wrong (?:account|number)|someone|somebody|a stranger|strangers|unknown (?:person|people)|scammers?|fraudsters?|hackers?)\b|नहीं\s+(?:किया|की|भेजा|भेजे|पहचान)|अनजान|बिना\s+(?:मेरी\s+)?(?:जानकारी|अनुमति)|maine\s+(?:nahi|nahin|nhi)|nahi\s+(?:kiya|bheja)|bina\s+(?:meri\s+)?(?:jaankari|permission)")
_SENT_SPLIT = re.compile(r"[.!?\n;।]+")
_CLAUSE_SPLIT = re.compile(r"(?<!\d),\s+|(?<=\d),\s+|\b(?:but|however|though|lekin|magar|parantu|while|because|although)\b|(?:लेकिन|परंतु|किंतु|मगर|पण|ஆனால்)")


def _clip(s, n=110):
    s = re.sub(r"\s+", " ", s).strip(" ,;:-")
    return s if len(s) <= n else s[:s.rfind(" ", 0, n - 3)] + "..."


def _timing(s):
    if _FUTURE.search(s) and not re.search(r"(?i)\bhad\b|\balready\b", s): return "future"
    for name, rx in _TIMING:
        if rx.search(s): return name
    return "unspecified"


def _object_ok(clause, end, extra=45):
    return bool(re.search(_MONEY_OBJ, clause[end:end + extra], re.I)) or bool(re.search(_MONEY_OBJ, clause[max(0, end - 25):end], re.I))


def _events_in_clause(clause, sent, in_hedged_sentence, claimed_ctx):
    """-> list of event dicts for one clause."""
    ev = []
    # reporting verbs split who is speaking; the nearest reporting verb before an action decides CLAIMED
    reports = []
    for m in _REPORT.finditer(clause):
        a = actor_before(clause, m.start())
        reports.append((m.start(), m.end(), a))
    def claimed_at(pos):
        prior = [r for r in reports if r[1] <= pos]
        if not prior: return False, 0
        r = prior[-1]
        return (r[2] != USER), r[1]          # a reporting verb whose subject is not the user ⇒ the embedded statement is a claim
    spans = []
    def add(kind, m, action, status, conf=HIGH, extra=None):
        floor = 0
        prior = [r[1] for r in reports if r[1] <= m.start()]
        if prior: floor = max(prior)
        for s in spans:
            if s[0] < m.end() and m.start() < s[1] and s[2] == action: return
        a = actor_before(clause, m.start(), floor)
        cl, _ = claimed_at(m.start())
        d = {"actor": a or UNKNOWN, "action": action, "status": status, "confidence": conf, "verb": m.group(0).lower(), "claimed": cl, "start": m.start(), "end": m.end()}
        if extra: d.update(extra)
        ev.append(d); spans.append((m.start(), m.end(), action))
    # --- payment, completed forms
    for rx, need_obj in ((_PAY_CLEAR, False), (_PAY_OBJ, True), (_PAY_LIGHT, False), (_PAY_CHUKA, False), (_DID_BASE, False)):
        for m in rx.finditer(clause):
            word = m.group(0).lower()
            if rx is _DID_BASE:
                verb = m.group(1).lower()
                if verb in ("share", "tell", "give", "read out", "provide", "send") and _CRED_STRONG_RX.search(clause[m.end():m.end() + 45]):
                    continue    # handled as a credential event below
                if verb in ("share", "tell", "give", "provide", "read out", "make") and not _object_ok(clause, m.end()):
                    continue
                if verb == "send" and not _object_ok(clause, m.end()): continue
            if need_obj and not _object_ok(clause, m.end()):
                continue
            if _MODAL_PASSIVE.search(clause[max(0, m.start() - 22):m.start()]): continue          # Sprint Oct-4 (A04): "tax of 15,000 must be paid" is an obligation, not a completed payment
            if need_obj and _GAVE_ME_NON_PAYMENT.match(clause[m.start():m.end() + 40]): continue   # Sprint Oct-4 (X24): "They gave me until tonight to pay ..." is a deadline, not a payment
            if need_obj and _CRED_STRONG_RX.search(clause[m.end():m.end() + 45]) and not _object_ok(clause, m.end(), 20) is True:
                continue
            if need_obj and re.search(r"(?i)\bto\s*$", clause[:m.start()][-4:]): continue   # infinitive: "asked me to send the money"
            neg = bool(re.search(r"(?i)\b(?:not|never|nahi|nahin|nhi)\b|n't", word)) or _verb_negated(clause, m.start(), m.end()) or bool(re.match(r"\s*(?:nothing|nobody|no one|none|zero)\b", clause[m.end():m.end() + 14], re.I)) or bool(re.search(r"(?i)\b(?:never|not|no|nahi|nahin|नहीं)\s*$", clause[max(0, m.start() - 12):m.start()]))
            add("pay", m, PAYMENT, DENIED if neg else COMPLETED, HIGH, {"partial": bool(_PARTIAL.search(sent))})
    # --- credential shares
    for term in _CRED_STRONG_RX.finditer(clause):
        if _POSTAL_PIN.search(clause[max(0, term.start() - 1):term.end() + 6]): continue
        t_start, t_end = term.start(), term.end()
        best = None
        for vm in list(_SHARE_EN.finditer(clause)) + list(_SHARE_HI.finditer(clause)):
            before = vm.end() <= t_start and t_start - vm.end() <= 40
            after = t_end <= vm.start() and vm.start() - t_end <= 25 and _SHARE_HI.fullmatch(vm.group(0)) is not None
            if not (before or after): continue
            between = clause[vm.end():t_start] if before else clause[t_end:vm.start()]
            if _PROHIBIT.search(between) and not _DENY_BASE.search(clause[max(0, vm.start() - 25):vm.end()]): continue
            if re.search(r"(?i)\bto\s*$", clause[:vm.start()][-4:]): continue          # infinitive: "asked me to read out ..."
            best = vm if best is None or abs(vm.start() - t_start) < abs(best.start() - t_start) else best
        if best is not None:
            neg = _verb_negated(clause, best.start(), best.end()) or bool(re.match(r"\s*(?:nothing|nobody)\b", clause[best.end():best.end() + 12], re.I))
            if not neg and best.start() > t_end:   # Hindi order: OTP ... बताया ; negation sits between
                neg = bool(NEG.match((_toks(clause[t_end:best.start()]) or [("",)])[-1][0]) or any(NEG.match(w[0]) for w in _toks(clause[t_end:best.start()])))
            m2 = best
            floor = max([r[1] for r in reports if r[1] <= m2.start()] or [0])
            a = actor_before(clause, min(m2.start(), t_start), floor)
            cl, _ = claimed_at(m2.start())
            ev.append({"actor": a or UNKNOWN, "action": CREDENTIAL, "status": DENIED if neg else COMPLETED, "confidence": HIGH, "verb": m2.group(0).lower(), "claimed": cl, "start": min(m2.start(), t_start), "end": max(m2.end(), t_end)})
    # Sprint Oct-4 (X40): credential ENTERED on a page/link/site of external origin ("I entered my card number and CVV on a page that opened from the SMS").
    # Three explicit conditions: first-person subject, a credential term, and an external-origin marker (SMS/message/caller/"they sent"). Entering a PIN at an ATM or a card number
    # on an ordinary checkout page has no such marker and is not read as a share. Negation, hypotheticals, advice, quotes, infinitives and "almost" are excluded.
    for term in _CRED_STRONG_RX.finditer(clause):
        if _POSTAL_PIN.search(clause[max(0, term.start() - 1):term.end() + 6]): continue
        if any(e["action"] == CREDENTIAL and e["start"] <= term.start() <= e["end"] for e in ev): continue
        em = None
        for m in _ENTRY.finditer(clause[:term.start()]):
            if term.start() - m.end() <= 40: em = m
        if em is None: continue
        if _verb_negated(clause, em.start(), em.end()) or _ENTRY_BLOCK.search(clause[max(0, em.start() - 30):em.start()]) or re.search(r"(?i)\bto\s*$", clause[:em.start()][-4:]): continue
        if _PROHIBIT.search(clause[em.end():term.start()]): continue
        if not _EXT_PAGE.search(clause[term.start():]): continue
        floor = max([r[1] for r in reports if r[1] <= em.start()] or [0])
        a = actor_before(clause, em.start(), floor)
        cl, _ = claimed_at(em.start())
        if a != USER or cl: continue
        ev.append({"actor": USER, "action": CREDENTIAL, "status": COMPLETED, "confidence": HIGH, "verb": em.group(0).lower(), "claimed": False, "start": em.start(), "end": term.end()})
    for m in _DID_BASE.finditer(clause):
        if m.group(1).lower() in ("share", "tell", "give", "read out", "provide", "send") and any(e["action"] == CREDENTIAL and abs(e["start"] - m.start()) < 3 for e in ev): continue
        tail = clause[m.end():m.end() + 45]
        if m.group(1).lower() in ("share", "tell", "give", "read out", "provide", "send") and _CRED_STRONG_RX.search(tail):
            floor = max([r[1] for r in reports if r[1] <= m.start()] or [0]); a = actor_before(clause, m.start(), floor); cl, _ = claimed_at(m.start())
            ev.append({"actor": a or UNKNOWN, "action": CREDENTIAL, "status": COMPLETED, "confidence": HIGH, "verb": m.group(0).lower(), "claimed": cl, "start": m.start(), "end": m.end()})
    # --- weak credential object: a bare "code" (could be a referral code): LOW confidence only
    if not any(e["action"] == CREDENTIAL for e in ev):
        for vm in _SHARE_EN.finditer(clause):
            tail = clause[vm.end():vm.end() + 30]
            wm = _CODE_WEAK.search(tail)
            if wm and not _PROHIBIT.search(tail[:wm.start()]) and not re.search(r"(?i)\bto\s*$", clause[:vm.start()][-4:]):
                floor = max([r[1] for r in reports if r[1] <= vm.start()] or [0]); a = actor_before(clause, vm.start(), floor); cl, _ = claimed_at(vm.start())
                neg = _verb_negated(clause, vm.start(), vm.end())
                ev.append({"actor": a or UNKNOWN, "action": CREDENTIAL, "status": DENIED if neg else COMPLETED, "confidence": LOW, "verb": vm.group(0).lower(), "claimed": cl, "start": vm.start(), "end": vm.end() + wm.end()})
                break
    # --- denial phrases and negated base verbs ("did not pay", "refused", "paid nothing")
    for m in _DENY_BASE.finditer(clause):
        verb = m.group(1).lower()
        action = CREDENTIAL if re.match(r"(?i)(share|sharing|shared|tell|telling|told|reveal|revealed|read out)", verb) or _CRED_STRONG_RX.search(clause[m.end():m.end() + 40]) else PAYMENT
        a = actor_before(clause, m.start(), 0) or USER
        if not any(e["status"] == DENIED and e["action"] == action and abs(e["start"] - m.start()) < 30 for e in ev):
            cl, _ = claimed_at(m.start())
            ev.append({"actor": a, "action": action, "status": DENIED, "confidence": HIGH, "verb": m.group(0).lower(), "claimed": cl, "start": m.start(), "end": m.end()})
    for rx in (_DENY_PHRASE, _DENY_HI):
        for m in rx.finditer(clause):
            action = CREDENTIAL if _CRED_STRONG_RX.search(clause) and not re.search(r"(?i)money|paid|pay|transfer|पैसे|paise|paisa", clause) else PAYMENT
            if any(e["status"] == DENIED and abs(e["start"] - m.start()) < 30 for e in ev): continue
            a = actor_before(clause, m.start(), 0) or USER
            ev.append({"actor": a, "action": action, "status": DENIED, "confidence": HIGH, "verb": m.group(0).lower(), "claimed": False, "start": m.start(), "end": m.end()})
    for m in _ATTEMPT.finditer(clause):
        a = actor_before(clause, m.start(), 0)
        if a in (USER, None):
            ev.append({"actor": USER, "action": PAYMENT, "status": ATTEMPTED, "confidence": LOW, "verb": m.group(0).lower(), "claimed": False, "start": m.start(), "end": m.end()})
    return ev


def _unmarked_money_events(clause):
    """Verb-independent net: first-person clause, past tense, an AMOUNT or 'the money'-type object, and no receiving verb. LOW confidence only."""
    out = []
    m_user = None
    for w, a, b in _toks(clause):
        if USER_SUBJ.match(w): m_user = (w, a, b); break
    if not m_user: return out
    after = clause[m_user[2]:]
    pm = re.match(r"\s*(?:have |had |just |already |then |also |really )*((?:\w+ ){0,1}\w+(?:ed|t|en|ew|ut))\b(.{0,60})", after, re.I)
    if not pm: return out
    verb, rest = pm.group(1).lower(), pm.group(2)
    if re.search(r"(?i)\b(?:received|got|earned|won|collected|claimed|borrowed|withdrew|withdrawn|saved|checked|counted|asked|requested|wanted|needed|noticed|saw|read|thought|felt|wondered|decided|realised|realized|learned|learnt|found|lost|spent|bought|ordered|booked|used|tried|did not|didn't|not)\b", verb): return out
    if re.search(r"(?i)\b(?:lost|stolen)\b", verb): return out
    if re.search(r"(?i)\b(?:must|might|cannot|not|never|dont|don't|doesn't|didn't|wont|won't|haven't|hasn't|hadn't|isn't|aren't|wasn't|weren't|couldn't|wouldn't|shouldn't)\b", verb): return out    # modal or negated: an obligation or a denial, never a completed payment
    if not re.search(_MONEY_OBJ, rest, re.I): return out
    if re.search(r"(?i)\bto\s*$", clause[:m_user[1]][-4:]): return out
    out.append({"actor": USER, "action": PAYMENT, "status": COMPLETED, "confidence": LOW, "verb": verb, "claimed": False, "start": m_user[1], "end": m_user[2] + pm.end(), "net": True})
    return out


def read(text, mask=None):
    """-> {"events": [...], "state": primary, "active": [...], "confidence": HIGH|LOW|None, "timing": str, "pending_aborted": bool}. `mask` hides sensitive digit runs in snippets."""
    text = text or ""
    mask = mask or (lambda s: s)
    events, aborted_pending = [], False
    pos = 0
    sents = []
    for sm in re.finditer(r"[^.!?\n;।]+", text):
        sent = sm.group(0)
        if not sent.strip(): continue
        hedged = bool(_HEDGE.search(sent)) and not _FUTURE.search(sent)
        sent_events = []
        for clause in _CLAUSE_SPLIT.split(sent):
            if not clause or not clause.strip(): continue
            evs = _events_in_clause(clause, sent, hedged, False)
            if not evs:
                evs = _unmarked_money_events(clause)
                evs = [e for e in evs if not any(x["action"] == PAYMENT for x in sent_events)]
            ct = _timing(clause)
            def _intent(e):   # a future marker just before the verb: "I am about to transfer": intent, handled by the pending cues, never a completed report
                lead = clause[max(0, e.get("start", 0) - 40):e.get("end", 0)]
                trail = clause[e.get("end", 0):e.get("end", 0) + 16]          # Hindi order: "... bhejne wala hoon"
                return (bool(_FUTURE.search(lead)) and not re.search(r"(?i)\bhad\b|\balready\b", lead)) or bool(re.match(r"\s*\w{0,6}\s*(?:wala|wali|वाला|वाली)\b", trail, re.I))
            evs = [e for e in evs if not (e["status"] == COMPLETED and _intent(e))]
            for e in evs:
                if e["actor"] in (THIRD, UNKNOWN) and e["action"] == PAYMENT and e["status"] == COMPLETED and not e["claimed"] and _FROM_USER_ACCOUNT.search(clause[e.get("end", 0):e.get("end", 0) + 60]):
                    e["from_account"] = True        # "Someone paid from my account": money left the user's account, whoever did it
                e["snippet"] = _clip(mask(clause)); e["timing"] = ct if ct not in ("unspecified", "future") else (_timing(sent) if _timing(sent) != "future" else "unspecified")
                e.setdefault("partial", bool(_PARTIAL.search(sent)))
            sent_events += evs
        # sentence-level markers
        if _ABORT.search(sent) or re.search(r"(?i)\bblocked\b", sent) and re.search(r"(?i)\btransaction\b", sent):
            aborted_pending = True      # an abort marker ("but stopped", "bank blocked it") in the same sentence cancels any pending cue from that sentence
            if not any(e["status"] == DENIED for e in sent_events):
                sent_events.append({"actor": USER, "action": PAYMENT, "status": DENIED, "confidence": HIGH, "verb": "stopped", "claimed": False, "snippet": _clip(mask(sent)), "timing": _timing(sent), "partial": False, "start": 0, "end": len(sent)})
        if re.search(r"(?i)\balmost\s+(?:paid|sent|transferred)\b|\bnearly\s+(?:paid|sent|transferred)\b", sent):
            for e in sent_events:
                if e["status"] == COMPLETED: e["status"] = DENIED
        if hedged:
            if sent_events:
                for e in sent_events:
                    if e["status"] in (COMPLETED, ATTEMPTED) and e["actor"] in (USER, UNKNOWN): e["status"] = UNCERTAIN
            elif _PAY_CONTEXT.search(sent) and (any(USER_SUBJ.match(w) for w, _, _ in _toks(sent)) or re.match(r"\s*(?:not sure|unsure|(?:do not|don'?t|cannot|can'?t) (?:remember|recall)|no idea)\b", sent, re.I) or re.search(r"याद नहीं|पता नहीं|पक्का नहीं|शायद|pata nahi|pata nhi|yaad nahi|yaad nhi|shayad", sent)) and not _REPORT.search(sent):
                action = CREDENTIAL if re.search(r"(?i)\b(?:code|otp|pin|password)\b|ओटीपी", sent) and not re.search(r"(?i)\b(?:money|paid|payment|transfer|amount)\b|पैसे|paise|paisa", sent) else PAYMENT
                sent_events.append({"actor": USER, "action": action, "status": UNCERTAIN, "confidence": LOW, "verb": "(hedge)", "claimed": False, "snippet": _clip(mask(sent)), "timing": _timing(sent), "partial": False, "start": 0, "end": len(sent)})
        events += sent_events
        sents.append((sent, sent_events))
    # Phase 5: unexplained / unauthorised debit from the user's own account (explicit two-part state; denials of paying alone never reach here because the first part is required)
    for k, (sent, sevs) in enumerate(sents):
        if not _MONEY_OUT.search(sent): continue
        near = sent + " " + (sents[k - 1][0] if k else "") + " " + (sents[k + 1][0] if k + 1 < len(sents) else "")
        if not _NOT_ME.search(near): continue
        for e in sevs:
            if e["actor"] in (THIRD, UNKNOWN) and e["action"] == PAYMENT: e["from_account"] = True
        events.append({"actor": UNKNOWN, "action": PAYMENT, "status": COMPLETED, "confidence": HIGH, "verb": "(debit not made by the user)", "claimed": False, "unauthorised": True, "snippet": _clip(mask(sent)), "timing": _timing(sent), "partial": False, "start": 0, "end": len(sent)})
        break
    # reversal after a completed payment (the recipient sent it back): the status of the payment is contradictory
    reversal = bool(_REVERSAL.search(text))
    return _summarise(events, reversal, aborted_pending)


def _summarise(events, reversal, aborted_pending):
    states = set()
    user_comp = {PAYMENT: [], CREDENTIAL: []}
    for cls in (PAYMENT, CREDENTIAL):
        comp = [e for e in events if e["action"] == cls and e["actor"] == USER and e["status"] == COMPLETED and not e["claimed"] and e["confidence"] == HIGH]
        low = [e for e in events if e["action"] == cls and e["actor"] == USER and not e["claimed"] and (e["status"] in (UNCERTAIN, ATTEMPTED) or (e["status"] == COMPLETED and e["confidence"] == LOW))]
        den = [e for e in events if e["action"] == cls and e["actor"] == USER and e["status"] == DENIED and not e["claimed"]]
        user_comp[cls] = comp
        if den and not comp: low = [e for e in low if e["status"] != ATTEMPTED]     # "I tried to pay but I have not completed the payment": the attempt did not complete
        if comp and (den or (reversal and cls == PAYMENT)): states.add("PAYMENT_UNCLEAR")
        elif comp: states.add("USER_PAID" if cls == PAYMENT else "USER_SHARED_CREDENTIAL")
        elif low: states.add("PAYMENT_UNCLEAR")
        if den and not comp: states.add("USER_DENIES")
    if any(e["actor"] == THIRD and e["action"] == PAYMENT and e["status"] == COMPLETED and not e["claimed"] and not e.get("from_account") for e in events): states.add("THIRD_PARTY_PAID")
    if any(e.get("unauthorised") for e in events): states.add("UNAUTHORISED_DEBIT")
    if any(e.get("from_account") for e in events): states.add("PAYMENT_UNCLEAR")        # the user did not necessarily pay, but money may have left their account
    if any(e["claimed"] and e["status"] in (COMPLETED, UNCERTAIN) for e in events): states.add("SENDER_CLAIMS_PAYMENT")
    if not states: states.add("NO_INCIDENT")
    active = [s for s in PRECEDENCE if s in states]
    conf = None
    if active and active[0] in USER_REPORT_STATES: conf = HIGH
    elif active and active[0] == "PAYMENT_UNCLEAR": conf = LOW
    kinds = {e["timing"] for e in events if e["actor"] == USER and e["status"] == COMPLETED}
    return {"events": events, "state": active[0], "active": active, "confidence": conf, "timing": ("recent" if "recent" in kinds else ("unspecified" if kinds else "")), "pending_aborted": aborted_pending,
            "reversal": reversal}


# ------------------------------------------------------------------ risk context (why an unconfirmed report becomes urgent)
_DEMAND_SUBJ = re.compile(r"(?i)\b(?:they|he|she|the \w+|his|her|their|agent|manager|company|broker|advis[eo]r|caller|sender|firm|mentor|person|man|woman|team|executive|officer|operator|woh|wo|vo|unhone|usne|वे|वह|वो|उन्होंने)\b|(?<![\w])(?:वे|वह|वो)(?![\w])")
_DEMAND_VERB = re.compile(r"(?i)\b(?:ask(?:s|ed|ing)?|want(?:s|ed|ing)?|demand(?:s|ed|ing)?|say(?:s)?|said|insist(?:s|ed)?|require[sd]?|need(?:s|ed)?|keeps? asking|keep asking|maang|mang|bol|chahiye|chahte|keh)\b|मांग|माँग|कह रहे|चाहिए|बोल रहे")
_DEMAND_OBJ = re.compile(r"(?i)\b(?:rest|balance|remaining|fees?|charges?|tax(?:es)?|gst|deposit|amount|payments?|money|paisa|paise|more|rupees?|commission|penalty|duty|advance|margin|processing|release|clearance|pay|send|transfer|deposit|jama|bhej|dena)\b|पैसे|रकम|शुल्क|टैक्स|जमा|भेज")
# Sprint Oct-4 (X14): a money AMOUNT or "another" after a clear demand verb (asking for / wants / demands). Weak verbs (say, need, bol, keh) are excluded: "the agent sent me a screenshot that says I paid 50,000" is not a demand (found by the cross-set comparison, case I30).
_DEMAND_AMT = re.compile(r"(?i)(?:₹|\brs\.?|\binr)\s?\d|\b\d{1,3}(?:,\d{2,3})+\b|\b\d{4,6}\b(?!\s?(?:digit|digits))|\b\d+\s?(?:k|lakh|lakhs)\b|\banother\b")
_WEAK_DEMAND_VERBS = frozenset("say says said need needs needed bol keh".split())
_UNFAMILIAR = re.compile(r"(?i)\b(?:strangers?|unknown (?:person|number|man|woman|caller|contact|account|people)|someone i (?:met|do not know|don'?t know)|telegram|online friend|anonymous|random (?:person|man|number|people)|(?:a|the) (?:man|woman|person|guy|caller) who (?:called|messaged|contacted|texted|emailed|approached|rang|wrote)|caller who|a man who|a woman who|a person who|ajnabi|anjaan|anjan)\b|अनजान|अज्ञात|अजनबी")


_UNKNOWN_RECIPIENT = re.compile(r"(?i)\b(?:to|into)\s+(?:an?\s+|the\s+)?(?:unknown|unfamiliar|unrecogni[sz]ed|wrong)\s+(?:\w+\s+){0,2}(?:account|number|upi|id|person|recipient|receiver|beneficiary)\b|\b(?:account|number|upi id|id|person|recipient|receiver|beneficiary)\s+(?:that\s+)?i\s+(?:do not|don'?t|did not|didn'?t)\s+(?:know|recogni[sz]e)\b")
# advance-fee purposes: paying "for" something that real services do not charge for (KYC update, unlocking, releasing profit, clearance, lottery/prize); ordinary fees (exam, loan processing, courier, customs, premiums) are deliberately not listed
_SCAM_PURPOSE = re.compile(r"(?i)\b(?:for|as|towards|to)\s+(?:the\s+|my\s+|a\s+|an\s+)?(?:\w+\s+){0,1}(?:kyc|unlock(?:ing)?|release|releasing|clearance|lottery|prize|reward|activation|account (?:update|verification|reactivation)|withdrawal (?:fee|tax|charge)|verification (?:fee|charge|amount))\b")
_RETURNS_WITHHELD = re.compile(r"(?i)\b(?:profits?|returns?|payouts?|withdrawals?|earnings?|gains?)\b\W+(?:\w+\W+){0,4}?(?:not|never|yet to)\s+(?:\w+\s+){0,2}(?:released|credited|paid out|processed|transferred|available)\b|\b(?:not|never)\s+(?:yet\s+)?(?:released|credited|paid out|processed|transferred)\s+(?:\w+\s+){0,2}(?:profits?|returns?|payouts?|withdrawals?|earnings?|gains?)\b")
_TROUBLE = re.compile(r"(?i)\b(?:still|yet)\s+(?:has|have|had)?\s*not\s+(?:released|returned|refunded|credited|paid out)\b|\b(?:nobody|no one)\s+(?:answers|replies|responds|picks)\b|\bunreachable\b|\bphone\s+(?:is\s+)?(?:switched )?off\b|\bnot\s+(?:released|returned|refunded)\s+my\b")

# Sprint Oct-4 (X08): an iterative marker (kept / keeps / continues to) + a charging verb + a charge word, with a non-user subject earlier in the clause. A single added tax on an invoice has no iterative marker.
_REPEAT_CHARGE = re.compile(r"(?i)\b(?:kept|keeps|keep|continues?|continued|continuing|started|keeps\s+on|kept\s+on)\s+(?:on\s+)?(?:finding|adding|inventing|imposing|levying|raising|charging|demanding|asking\s+for|creating|piling|coming\s+up\s+with)\b[^.;!?]{0,40}\b(?:charges?|fees?|taxes|tax|penalt\w+|amounts?|dues|payments?|deposits?|costs?)\b")


def risk_context(text):
    """-> list of short reasons (empty = none). Heuristic, closed, documented in STATE_MODEL.md. Detection-layer reasons (concern posture etc.) are added by the engine."""
    out = []
    for sent in re.split(r"[.!?\n;।]+", text or ""):
        for clause in re.split(r"(?<!\d),\s+|(?<=\d),\s+", sent):
            dm, vm = _DEMAND_SUBJ.search(clause), _DEMAND_VERB.search(clause)
            if dm and vm and dm.start() < vm.end() and (_DEMAND_OBJ.search(clause[vm.end():vm.end() + 70]) or _DEMAND_OBJ.search(clause[dm.end():vm.start()]) or (vm.group(0).lower() not in _WEAK_DEMAND_VERBS and _DEMAND_AMT.search(clause[vm.end():vm.end() + 70]))) and not USER_SUBJ.match((_toks(clause[:vm.start()]) or [("", 0, 0)])[-1][0]):
                out.append("a further payment is demanded"); break
        if "a further payment is demanded" in out: break
    for sent in re.split(r"[.!?\n;।]+", text or ""):
        for clause in re.split(r"(?<!\d),\s+|(?<=\d),\s+", sent):
            rm = _REPEAT_CHARGE.search(clause)
            if rm and _DEMAND_SUBJ.search(clause[:rm.start() + 1]) and not USER_SUBJ.match((_toks(clause[:rm.start()]) or [("", 0, 0)])[-1][0]):
                out.append("further or repeated charges are being added after the payment"); break
        if "further or repeated charges are being added after the payment" in out: break
    if _UNFAMILIAR.search(text or ""): out.append("an unfamiliar contact is involved")
    if _TROUBLE.search(text or "") or _RETURNS_WITHHELD.search(text or ""): out.append("the money or profit is withheld, or the other side stopped answering")
    if _SCAM_PURPOSE.search(text or ""): out.append("the payment was for something real services do not charge for (KYC update, unlocking, releasing profit, clearance, prize)")
    if _UNKNOWN_RECIPIENT.search(text or ""): out.append("the money went to an unknown or wrong recipient")
    return out


# ------------------------------------------------------------------ Sprint Oct-4 (X13, X14, X15): subject-less completed payment + explicit risk context
def subjectless_payment_context(inc, text):
    """-> list of reasons when the text describes a completed payment WITHOUT saying who made it ("Paid 15,000 to the account he gave me; now he wants more.") AND the same text
    contains structural risk context (a further payment demanded, an unknown recipient, an advance-fee purpose, withheld money, repeated charges). It never says the user paid: the caller
    labels the state PAYMENT_UNCLEAR and shows the urgent steps, because they cost little if the reading is wrong. "An unfamiliar contact" alone is not enough (a Telegram Premium receipt names Telegram).
    Ordinary receipts and bank notices have no such context and stay NO_INCIDENT. Denials and hedged payments never reach this because their events are not COMPLETED."""
    evs = [e for e in inc.get("events", []) if e["action"] == PAYMENT and e["actor"] == UNKNOWN and e["status"] == COMPLETED and e["confidence"] == HIGH and not e.get("claimed") and not e.get("from_account") and not e.get("unauthorised")]
    if not evs or any(e["status"] == DENIED and e["action"] == PAYMENT for e in inc.get("events", [])): return []
    return [r for r in risk_context(text) if r != "an unfamiliar contact is involved"]
