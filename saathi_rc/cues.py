"""Lexicons and negation-aware cue detection for the situation gate (replaces v0.2 contract.CUES/SURFACE and the v0.1 free-text loss regex).

Design rules
* The cues only decide whether the TEXT contradicts the situation the user chose ("you said nothing happened, but the text says you paid").
  A false positive costs one follow-up question; a false negative can leave a victim without urgent guidance, so cues are broad.
* Negation is applied per verb, only to the two words immediately before it ("have not yet paid", "never shared") plus coordinated
  verbs ("not paid or shared"). It is NOT applied to anything further away ("I did not hesitate and paid" stays a positive cue).
* Pending-payment cues are separate: being asked to pay is not the same as having paid.
* The request SURFACE only blocks an out-of-scope abstention; it never creates reassurance. Deliberately broad; English, Hinglish, Hindi,
  Marathi, Tamil request/credential/money words. Any other Indic script is flagged as 'other_script'.
"""
import re

# ---------------------------------------------------------------- past-action cues (negation aware)
SUBJ = re.compile(r"(?i)\b(i|i've|ive|we|we've|maine|mene|humne|hamne)\b|मैंने|हमने|मुझसे|मी|आम्ही|நான்|நாங்கள்")
PAST_VERB = re.compile(
    r"(?i)\b(paid|sent|transferred|transfered|gave|given|shared|installed|clicked|opened|entered|downloaded|deposited|invested|lost|followed|complied|agreed|did|done|"
    r"bhej\s?diya|bhej\s?diye|bheja|bheje|bhej\s?di|de\s?diya|de\s?diye|bata\s?diya|bata\s?di|kar\s?diya|kar\s?liya|kiya|dal\s?diya|install\s?kar\s?liya|click\s?kar\s?diya|jama\s?kiya|jama\s?kar\s?diya)\b"
    r"|भेज\s?(दिया|दिए|दी|ा|े)|भेजे|भेजा|दे दिया|दे दिए|दिए|बता दिया|बता दी|कर दिया|कर लिया|किया|डाल दिया|खोल दिया|इंस्टॉल|जमा कर|"
    r"पाठवले|पाठवला|भरले|दिले|सांगितले|செலுத்தினேன்|அனுப்பினேன்|கொடுத்தேன்|பகிர்ந்தேன்")
NEG = re.compile(r"(?i)^(not|never|no|none|nothing|haven't|havent|hasn't|didn't|didnt|don't|dont|wasn't|wouldn't|won't|can't|cannot|nahi|nahin|nhi|nai|kabhi|नहीं|नही|नहि|न|कभी|नाही|नाहि|இல்லை|இல்ல)$")
COORD = {"or", "nor", "and", "ya", "aur", "या", "और", "किंवा", "आणि"}
NOT_ONLY = re.compile(r"(?i)not (only|just)")
_TOK = re.compile(r"[^\s.,;:!?()\[\]\"“”‘’]+")
_CLAUSE_SPLIT = re.compile(r"[.!?\n;।]+|\b(?:but|however|though|lekin|magar|par|parantu)\b|(?:लेकिन|परंतु|किंतु|पर|मगर|पण|ஆனால்)")


def _toks(s):
    return _TOK.findall(s)


def _verb_negated(clause, vstart, vend, depth=0):
    """True if the verb at clause[vstart:vend] is negated by a nearby word (two words before, or after for 'did/done not')."""
    before = _toks(clause[:vstart])[-2:]
    after = _toks(clause[vend:])[:1]
    word = clause[vstart:vend].lower()
    if any(NEG.match(w) for w in before):
        return not NOT_ONLY.search(clause[max(0, vstart - 12):vstart + 1])
    if word in ("did", "done") and after and NEG.match(after[0]):
        return True
    if len(before) == 2 and before[1].lower() in COORD and PAST_VERB.fullmatch(before[0]) and depth < 3:
        # 'not paid OR shared': the second verb inherits the negation of the verb it is coordinated with (and only that case)
        prev = None
        for m in PAST_VERB.finditer(clause[:vstart]):
            prev = m
        if prev is not None:
            return _verb_negated(clause, prev.start(), prev.end(), depth + 1)
    return False


def past_action_cues(text):
    """-> list of cue names that indicate the USER HAS ALREADY done something (paid, shared, clicked, installed...) and that are not negated."""
    found, negated = [], []
    for clause in _CLAUSE_SPLIT.split(text or ""):
        if not clause or not clause.strip():
            continue
        for v in PAST_VERB.finditer(clause):
            window = clause[max(0, v.start() - 70):v.start()]
            if not SUBJ.search(window):
                continue
            (negated if _verb_negated(clause, v.start(), v.end()) else found).append(v.group(0).lower())
    return found, negated


# ---- other (non-negation-sensitive) signs that something has already happened
OTHER_CUES = [
    ("money_gone", re.compile(r"(?i)\b(my|our|mera|meri|mere)\b[^.?!\n]{0,40}\b(money|amount|funds|savings|account|paise|paisa)\b[^.?!\n]{0,40}\b(gone|deducted|debited|withdrawn|missing|stolen|taken|empty|kat|nikal|gayab)\b|(₹|\brs\.?|\binr\b)\s?[\d,]+[^.?!\n]{0,30}\b(gone|stolen|missing)\b")),
    ("account_compromised", re.compile(r"(?i)\bmy (bank |demat |trading )?(account|wallet|phone|login|password|card)\b(?![^.?!\n]{0,25}\b(will|would|shall|going to|gonna|unless|if|or else)\b)[^.?!\n]{0,40}\b(hacked|compromised|emptied|empty|changed|locked|accessed|not working|acting strange|blocked)\b")),
    ("scam_underway", re.compile(r"(?i)\b(not replying|stopped replying|not picking|not answering|blocked me|switched off|can'?t withdraw|cannot withdraw|unable to withdraw|won'?t (let|allow) me withdraw|money is locked|account (is )?locked|withdraw(al)?[^.?!\n]{0,20}(fail|block|pending|stuck))\b")),
    ("victim_words", re.compile(r"(?i)\b(victim|cheated|duped|defrauded|scammed|fell for|fraud (happened|has happened)|thagi|thag liya)\b")),
    ("hindi_money_gone", re.compile(r"(पैसे|रकम|राशि|रुपये)[^.?!\n]{0,40}(कट|निकल|गायब|चले गए|ट्रांसफर हो|गए)|ठगी|धोखा हुआ")),
    ("lost_amount", re.compile(r"(?i)\blost\b[^.?!\n]{0,20}(rs|₹|\d|lakh|crore|k\b)")),
]

# ---- pending-payment cues: the user is being asked to pay / is about to pay (nothing has happened yet, but time matters)
PENDING = [
    ("about_to_pay", re.compile(r"(?i)\b(about|going|planning|ready|want(ing)?|wish(ing)?|trying|need|have) to (pay|send|transfer|invest|deposit|top ?up|add|fund|buy)\b|\bshould i (pay|send|transfer|invest|deposit)\b|\b(is it|would it be) (ok|okay|fine|safe) to (pay|send|transfer|invest)")),
    ("asked_to_pay", re.compile(r"(?i)\b(asked|told|asking|telling|forcing|pressuring|making|instructed|want|wants|wanting)\s+(me|us)\b[^.?!\n]{0,40}\b(pay|send|transfer|deposit|invest|add|fund|top ?up)\b|\bpay(ment)? link\b|\bwaiting for (my |the )?(payment|money|transfer)\b|\bpayment (is )?(pending|processing|in progress|due)\b")),
    # CH-08 (post-hoc, after S2 run1 case P03): first-person intent to pay ("I plan to transfer it in a few minutes"). First person only, so a message that says
    # "we are going to transfer your salary" does not trigger a stop-payment warning; "I am not going to pay" does not match because 'not' breaks the pattern.
    ("intent_to_pay", re.compile(r"(?i)\bI(?:\s+am|'m)?\s+(?:plan(?:ning)?|going|intend(?:ing)?|ready|about|want(?:ing)?|decid(?:ed|ing)|preparing|set)\s+to\s+(?:pay|send|transfer|deposit|invest|wire)\b|\bI(?:'ll|\s+will|\s+shall)\s+(?:pay|send|transfer|deposit|invest)\b")),
    # Sprint Oct-4 (X24): first-person deliberation ("I am thinking of paying") and an explicit pay-by deadline ("until tonight to pay", "gave me 48 hours to deposit"). Same stop-payment consequence as the other pending cues.
    ("deliberating_to_pay", re.compile(r"(?i)\bI(?:\s+am|'m)?\s+(?:thinking|contemplating|tempted|inclined|leaning)\s+(?:of|about|towards)\s+(?:paying|sending|transferring|depositing|wiring)\b|\bI(?:\s+am|'m)?\s+considering\s+(?:(?:of|about)\s+)?(?:paying|sending|transferring|depositing|wiring|a\s+payment)\b")),
    ("deadline_to_pay", re.compile(r"(?i)\b(?:until|till|by)\s+(?:tonight|tomorrow|today|midnight|\d{1,2}\s?(?:am|pm)|evening|morning|noon)\b[^.?!\n]{0,20}\bto\s+(?:pay|send|transfer|deposit)\b|\b(?:gave|given|give)\s+(?:me|us)\s+(?:\d+|a few|two|three|one)\s+(?:hours?|days?|minutes?)\s+to\s+(?:pay|send|transfer|deposit)\b")),
    ("hinglish_pending", re.compile(r"(?i)\b(bhejna|bhejne|jama karna|jama karne|pay karna|pay karne|dena hai|bhej raha|bhej rahi|transfer karna|transfer karne)\b")),
    ("hindi_pending", re.compile(r"भेजना है|भेजने वाला|भेजने वाली|जमा करना|जमा करने|भुगतान करना|देना है|भेजने जा")),
    ("marathi_tamil_pending", re.compile(r"पाठवणार|भरणार|पाठवायचे|செலுத்தப் போகிறேன்|அனுப்ப போகிறேன்")),
]


def pending_cues(text):
    """CH-08b (post-hoc): a pending cue is ignored when one of the two words before it is a negation ("I am not going to pay")."""
    out = []
    for n, rx in PENDING:
        for m in rx.finditer(text or ""):
            before = _toks((text or "")[:m.start()].split("\n")[-1])[-2:]
            if not any(NEG.match(w) for w in before):
                out.append(n); break
    return out


def other_cues(text):
    return [n for n, rx in OTHER_CUES if rx.search(text or "")]


def situation_conflict_cues(text):
    """-> (cues, negated). `cues` non-empty means the text suggests something has ALREADY happened."""
    found, negated = past_action_cues(text)
    cues = (["past_action:" + w for w in found]) + other_cues(text)
    return cues, negated


# ---------------------------------------------------------------- request surface (blocks out-of-scope ABSTAIN; never creates reassurance)
SURFACE = [
    ("url", re.compile(r"(?i)https?://|www\.|\bbit\.ly|\bt\.me/|\bwa\.me/|\b[a-z0-9-]+\.(com|in|co|net|org|cc|xyz|me|ly|link|app|info|online|site|top|live|club|vip|shop|pro|cfd)\b")),
    ("phone_number", re.compile(r"(?<!\d)(\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)|\b1800[\s-]?\d{3,}")),
    ("upi_id_shape", re.compile(r"\b[\w.\-]{2,}@[a-z]{2,}\b")),
    ("credential_terms", re.compile(r"(?i)\b(otp|pin|cvv|password|passcode|passwd|login|log in|net ?banking|card (number|details)|aadhaar|aadhar|pan (card|number)|kyc|mpin|upi pin)\b|ओटीपी|पासवर्ड|पिन|केवाईसी|केवायसी|आधार|கடவுச்சொல்|ஓடிபி")),
    ("money_terms", re.compile(r"(?i)\b(pay(ment|out)?|money|amount|rs\.?|inr|rupees?|fund(s|ing)?|wallet|deposit|fee|fees|charges?|dues?|refund|withdraw(al)?|profit|capital|balance|transfer|margin|advance|subscription|premium|tax|penalty|bonus|commission|paisa|paise|rupaye|jama|kamai|munafa|nivesh)\b|₹|रुपये|रुपए|पैसे|पैसा|भुगतान|जमा|मुनाफा|मुनाफ़ा|निवेश|नफा|गुंतवणूक|रुपये|ரூபாய்|லாபம்|முதலீடு|பணம்")),
    ("request_verbs", re.compile(r"(?i)\b(pay|send|transfer|deposit|add (rs|₹|money|funds|amount|more|\d)|top ?up|fund|settle|clear (the )?(dues?|payment)|invest|share|give|enter|install|download|click|tap|call|contact|reply|respond|verify|update|confirm|submit|join|register|subscribe|scan|forward|activate|renew|recharge|reserve|secure|claim|withdraw|open the link|bhejo|bhej|bhejiye|jama|batao|bataiye|karo|kijiye|kijie|aao|karein|kare)\b|भेज|भुगतान|जमा|ट्रांसफर|बताएं|बताइए|शेयर|डाउनलोड|इंस्टॉल|क्लिक|कॉल|वेरिफाई|अपडेट|जुड़ें|जॉइन|रजिस्टर|भरा|पाठवा|सामील|करा\b|அனுப்பு|செலுத்து|கிளிக்|சேருங்கள்|புதுப்பி")),
    ("pressure_terms", re.compile(r"(?i)\b(urgent(ly)?|immediately|asap|right now|now|today|tonight|within \d+ ?(hours?|hrs?|minutes?|mins?|days?)|last chance|limited (seats|slots|time)|seats? left|nearly full|expires?|expiry|blocked|block|suspend(ed)?|deactivat\w*|freez\w*|arrest\w*|penalt\w*|legal action|fir|abhi|turant|jaldi|aaj|warna|band ho|squared off|cut tonight)\b|तुरंत|अभी|आज|बंद हो|गिरफ्तार|आत्ताच|आजच|உடனே|இன்றே|முடக்க")),
    ("return_figures", re.compile(r"(?i)\b\d{2,}\s?%|\b\d+\s?x\b|\b(double|triple|multiply)\b|\b\d+\s?times\b|guarantee[sd]?|assured|certain|sure[- ]?shot|risk[- ]?free|no (chance of )?loss|fixed profit|locked in|गुना|दोगुना|गारंटी|पक्का|हमखास|परतावा|உறுதி")),
]
SUPPORTED_SCRIPTS = ("latin", "devanagari", "tamil")   # scripts for which some lexicon exists; every other script is flagged 'other_script'


def surface_of(norm):
    t = norm["text"]
    found = [name for name, rx in SURFACE if rx.search(t)]
    for k, nm in (("urls", "url"), ("phones", "phone_number"), ("vpas", "upi_id_shape")):
        if norm["entities"].get(k) and nm not in found:
            found.append(nm)
    sc = norm.get("script_counts", {})
    if any(k not in ("latin", "devanagari", "tamil") and v > 0 for k, v in sc.items()):
        found.append("other_script")
    return found


# CH-09 (post-hoc, after S2 run1 cases D10/I10): a REQUEST to hand over a code, PIN, password or card picture. A prohibition ("do not share your OTP", "never ask for") is not a request.
_CRED_TERM = r"(?:otp|one[- ]time[- ](?:password|code|pin)|pin|mpin|upi pin|cvv|password|passcode|(?:\d|four|six|4|6)[- ]?digit\s+(?:code|number|pin|otp)|verification code|security code|ओटीपी|पासवर्ड)"
_CRED_REQ = re.compile(r"(?i)\b(?:share|send|tell|give|read(?: out)?|provide|forward|reply with|text|whatsapp|bata(?:o|na|iye)?|bhej(?:o|na|iye)?)\b[^.?!\n;]{0,45}?\b" + _CRED_TERM + r"\b|\b(?:photo|picture|image|snap(?:shot)?|scan|copy|screenshot)\b[^.?!\n;]{0,25}?\b(?:debit card|credit card|atm card|card|aadhaar|aadhar|pan card|passbook|cheque)\b|"
                       r"(?:ओटीपी|पासवर्ड|पिन|\botp\b|\bpin\b|\bmpin\b|\bcvv\b|\bpassword\b)[^.?!\n;।]{0,25}(?:बताएं|बताइए|बताओ|भेजें|भेजिए|साझा करें|दें|(?:बता|भेज|दे|साझा कर)\s*(?:दीजिए|दीजिये|दीजिएगा|दो|दें))")   # S3 FIX-3/3b (3b added after the challenge run, case S05: compound verbs such as "भेज दीजिए"): Hindi text usually writes OTP/PIN in Latin script
_PROHIBIT = re.compile(r"(?i)\b(?:do not|don'?t|dont|never|not|avoid|without|won'?t|nahi|nahin|kabhi)\b|नहीं|कभी|मत |(?:^|\s)न(?:\s|$)")


def credential_request(text):
    """-> matched clause (str) or None. Per clause; skipped when a prohibition word precedes the request verb in the same clause."""
    for clause in re.split(r"[.!?\n;।]+", text or ""):
        m = _CRED_REQ.search(clause)
        if m and not _PROHIBIT.search(clause[:m.end()]):
            return clause.strip()
    return None


STRUCT_CHANNEL = ("url", "phone_number", "upi_id_shape")


def structural_pattern(surf):
    """Language-light structural heuristic (CH-02): a message that (a) asks for money/credentials, (b) offers a contact/pay channel,
    (c) pressures or promises returns is the common SHAPE of a scam regardless of exact wording. Returns (level, parts).
    level: None | 'SOME_CONCERN' (never HIGH from structure alone)."""
    s = set(surf)
    ask = "credential_terms" in s or ("money_terms" in s and "request_verbs" in s)
    channel = bool(s & set(STRUCT_CHANNEL))
    push = ("pressure_terms" in s) or ("return_figures" in s)
    hits = [n for n, ok in (("asks for money or credentials", ask), ("gives a link, number or UPI ID to act on", channel), ("pressure or promised returns", push)) if ok]
    if ask and len(hits) >= 2 and (push or channel) and ("pressure_terms" in s or "return_figures" in s):
        return "SOME_CONCERN", hits
    return None, hits


# Safety sprint S-2 (2026-10-05): a link + a stated CONSEQUENCE (service cut, account blocked/expired...) + an action to take is the common shape of link phishing even when the text names no money or
# credential (S1 C13: "Your electricity will be cut tonight ... click http://..."). Consequence words are deliberately narrower than generic urgency ("today", "now"). ADV-1/ADV-2 (2026-10-05): plain expiry, lapse, cancellation and penalty wording was REMOVED because routine reminders (plan or policy expiry with a renewal link) matched it; an expiry-type scam ("your number will expire, click ...") is therefore no longer caught by this rule.
_CONSEQUENCE = re.compile(r"(?i)\b(?:will be|get|gets|being|be|is|are|has been|have been)\s+(?:\w+\s+){0,2}?(?:cut|disconnected|blocked|suspended|deactivated|terminated|closed|frozen|seized|forfeited)\b|\b(?:disconnection|suspension|deactivation|termination|blacklisted)\b|\bwill\s+(?:stop working)\b")
_LINK_ACTION = re.compile(r"(?i)\b(?:click|tap|open|visit|update|verify|confirm|log ?in|submit|complete|renew|recharge|pay|call|contact|reply)\b")


def link_threat_pattern(surf, text):
    """-> True when the text has a link, an action to take and a stated consequence. Used ONLY to move CANNOT_ASSESS to SOME_CONCERN (never HIGH); pattern match, not proof."""
    return "url" in set(surf) and bool(_CONSEQUENCE.search(text or "")) and bool(_LINK_ACTION.search(text or ""))
