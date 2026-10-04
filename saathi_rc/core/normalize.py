"""Step 1: input normalisation (+ language/script detection, entity extraction, masking).

The text returned here is UNTRUSTED DATA. Nothing in it is ever interpreted as an instruction.
"""
import re
import unicodedata
from urllib.parse import urlsplit

ZERO_WIDTH = "\u200b\u200c\u200d\u200e\u200f\u2060\ufeff\u00ad"
# Cyrillic/Greek look-alikes -> Latin
HOMOGLYPHS = {
    "\u0406": "I", "\u0456": "i", "\u0410": "A", "\u0430": "a", "\u0415": "E", "\u0435": "e", "\u041e": "O", "\u043e": "o",
    "\u0420": "P", "\u0440": "p", "\u0421": "C", "\u0441": "c", "\u0425": "X", "\u0445": "x", "\u0423": "Y", "\u0443": "y",
    "\u0405": "S", "\u0455": "s", "\u0408": "J", "\u0458": "j", "\u041d": "H", "\u041c": "M", "\u0422": "T", "\u0412": "B", "\u041a": "K",
    "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0397": "H", "\u0399": "I", "\u039a": "K", "\u039c": "M", "\u039d": "N",
    "\u039f": "O", "\u03a1": "P", "\u03a4": "T", "\u03a7": "X", "\u03bf": "o",
}
SCRIPT_RANGES = {
    "latin": [(0x41, 0x24F)], "devanagari": [(0x900, 0x97F)], "tamil": [(0xB80, 0xBFF)], "bengali": [(0x980, 0x9FF)],
    "telugu": [(0xC00, 0xC7F)], "gujarati": [(0xA80, 0xAFF)], "gurmukhi": [(0xA00, 0xA7F)], "kannada": [(0xC80, 0xCFF)],
    "malayalam": [(0xD00, 0xD7F)], "odia": [(0xB00, 0xB7F)], "arabic": [(0x600, 0x6FF)], "cyrillic": [(0x400, 0x4FF)],
}
MARATHI_MARKERS = ["आहे", "करा", "तुमचे", "तुमच्या", "आजच", "नोंदणीकृत", "सांगा", "होईल", "हमखास", "परतावा", "उपलब्ध", "कृपया"]
HINGLISH_MARKERS = ["hai", "hain", "karo", "kijiye", "bhejo", "bhej", "aapka", "aap", "nahi", "warna", "jayega", "daalein", "paisa",
                    "har mahine", "aaj", "kar lena", "bhai", "ho gaya", "pe", "ki", "ka", "ko", "tips", "sir"]
SUPPORTED_LANGS = {"en": "supported", "hinglish": "supported", "hi": "supported", "mixed": "supported",
                   "mr": "limited", "ta": "limited"}

URL_RE = re.compile(r"(?i)\b((?:https?://|www\.)[^\s<>\"']+|(?:[a-z0-9\-]+\.)+(?:com|in|co|net|org|me|cc|app|io|xyz|info|biz|online|site|top|link|ly|gl|co\.in|gov\.in)(?:/[^\s<>\"']*)?|t\.me/[^\s<>\"']+|chat\.whatsapp\.com/[^\s<>\"']+|wa\.me/[^\s<>\"']+|bit\.ly/[^\s<>\"']+|tinyurl\.com/[^\s<>\"']+)")
VPA_RE = re.compile(r"(?i)\b([a-z0-9][a-z0-9._\-]{1,40})@([a-z][a-z0-9]{1,20})\b(?!\.[a-z])")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s\-]?)?([6-9]\d{4}[\s\-]?\d{5})(?!\d)")
REG_RE = re.compile(r"(?i)\bIN\s?([AHZ])\s?((?:\d\s?){1,12})(?!\d)")
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "rb.gy", "cutt.ly", "is.gd", "shorturl.at", "ow.ly"}
TWO_LABEL_SUFFIXES = {"co.in", "gov.in", "org.in", "ac.in", "net.in", "nic.in", "co.uk", "com.au", "res.in"}


def _script_of(ch):
    o = ord(ch)
    for name, rngs in SCRIPT_RANGES.items():
        for a, b in rngs:
            if a <= o <= b:
                return name
    return None


def nfkc_clean(text):
    """Return (clean_text, flags). flags: zero_width_inside_word, mixed_script_token."""
    flags = {"zero_width_inside_word": False, "mixed_script_token": False}
    t = unicodedata.normalize("NFKC", text)
    # zero-width characters inside ASCII words = obfuscation (ZWJ/ZWNJ are legitimate in Indic scripts: only flag between Latin letters)
    if re.search(r"[A-Za-z][%s]+[A-Za-z]" % re.escape(ZERO_WIDTH), t):
        flags["zero_width_inside_word"] = True
    t = t.translate({ord(c): None for c in ZERO_WIDTH})
    # mixed-script tokens: Latin + Cyrillic/Greek in one token
    for tok in re.findall(r"\S+", t):
        scripts = {_script_of(c) for c in tok if c.isalpha()}
        if "latin" in scripts and ({"cyrillic"} & scripts or any(0x370 <= ord(c) <= 0x3FF for c in tok)):
            flags["mixed_script_token"] = True
    t = "".join(HOMOGLYPHS.get(c, c) for c in t)
    # non-ASCII decimal digits -> ASCII
    t = "".join(str(unicodedata.digit(c)) if (not c.isascii() and unicodedata.category(c) == "Nd") else c for c in t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t, flags


LEET = {"4": "a", "3": "e", "0": "o", "1": "i", "5": "s", "7": "t"}
LEET_KEYWORDS = {"guaranteed", "returns", "return", "profit", "assured", "daily", "calls", "join", "today", "registered", "sebi", "trading", "invest", "account", "monthly"}
OCR_SPLIT_KEYWORDS = ["guaranteed", "returns", "monthly", "month", "today", "profit", "assured"]


def repair_noisy_text(t):
    """Targeted, deterministic repair of anticipated obfuscation/OCR noise. NOT a general solution: only the
    keyword list above is repaired. Returns (text, flags)."""
    flags = {"leet_folded": False, "ocr_repaired": False}
    import itertools

    def fold(tok):
        if not re.fullmatch(r"[A-Za-z0-9]+", tok) or not re.search(r"[A-Za-z]", tok) or not re.search(r"[0-9]", tok):
            return tok
        idx = [i for i, ch in enumerate(tok) if ch in LEET]
        if not idx or len(idx) > 6:
            return tok
        for combo in itertools.product([False, True], repeat=len(idx)):   # fold subset of digits
            chars = list(tok)
            for use, i in zip(combo, idx):
                if use:
                    chars[i] = LEET[tok[i]]
            cands = ["".join(chars)]
            if "1" in tok:
                cands.append("".join(chars).replace("1", "l")) if False else None
            for cand in cands:
                variants = [cand]
                # '1' may be i or l
                if any(tok[i] == "1" and chars[i] == "i" for i in idx):
                    variants.append("".join("l" if (j in idx and tok[j] == "1" and chars[j] == "i") else chars[j] for j in range(len(chars))))
                for v in variants:
                    if v.lower() in LEET_KEYWORDS:
                        return v
        return tok

    def tokfix(m):
        tok = m.group(0)
        new = fold(tok)
        if new != tok:
            flags["leet_folded"] = True
        return new
    t = re.sub(r"(?<![\w./@:-])[A-Za-z0-9]{4,14}(?![\w./@:-])", tokfix, t)
    # digits written with letter O: '4O%', '1OO%'
    def ofix(m):
        tok = m.group(0)
        if re.search(r"\d", tok) and re.search(r"[Oo]", tok):
            flags["ocr_repaired"] = True
            return tok.replace("O", "0").replace("o", "0")
        return tok
    t = re.sub(r"(?<![\w])[\dOo]{2,8}(?=%)", ofix, t)
    t = re.sub(r"(?i)\bSEB[1l]\b", lambda m: (flags.__setitem__("ocr_repaired", True) or "SEBI"), t)
    for kw in OCR_SPLIT_KEYWORDS:
        rx = re.compile(r"(?i)\b" + r" ?".join(kw) + r"\b")
        def j(m):
            if " " in m.group(0):
                flags["ocr_repaired"] = True
                return m.group(0).replace(" ", "")
            return m.group(0)
        t = rx.sub(j, t)
    return t, flags


def compact_registration_numbers(t):
    """'INH 0 0 0 1 2 3 4 5 6' -> 'INH000123456'."""
    def fix(m):
        digits = re.sub(r"\s", "", m.group(2))
        trail = " " if m.group(2).endswith(" ") else ""
        return "IN" + m.group(1).upper() + digits + trail
    return REG_RE.sub(fix, t)


def detect_script_mix(t):
    counts = {}
    for ch in t:
        if ch.isalpha():
            s = _script_of(ch) or "other"
            counts[s] = counts.get(s, 0) + 1
    return counts


def detect_language(t):
    counts = detect_script_mix(t)
    total = sum(counts.values())
    if total == 0:
        return "none", counts
    top = max(counts, key=counts.get)
    latin, deva = counts.get("latin", 0), counts.get("devanagari", 0)
    unsupported_scripts = {k: v for k, v in counts.items() if k not in ("latin", "devanagari", "tamil", "other")}
    if unsupported_scripts and sum(unsupported_scripts.values()) / total > 0.3:
        return "unsupported:" + max(unsupported_scripts, key=unsupported_scripts.get), counts
    if counts.get("tamil", 0) / total > 0.3:
        return "ta", counts
    if deva / total > 0.3:
        if latin / total > 0.2:
            return "mixed", counts
        if any(m in t for m in MARATHI_MARKERS):
            return "mr", counts
        return "hi", counts
    if latin / total > 0.5:
        words = re.findall(r"[a-z]+", t.lower())
        hits = sum(1 for w in words if w in {m for m in HINGLISH_MARKERS if " " not in m}) + sum(1 for m in HINGLISH_MARKERS if " " in m and m in t.lower())
        if words and hits >= 3 and hits / len(words) > 0.08:
            return "hinglish", counts
        return "en", counts
    return "en", counts


def registrable_domain(host):
    host = host.lower().strip(".")
    labels = host.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in TWO_LABEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def parse_url(raw):
    """Return dict(host, registrable, userinfo, shortener, raw). Handles userinfo and punycode."""
    r = raw.rstrip(".,;:!?)\"'")
    cand = r if re.match(r"(?i)^[a-z][a-z0-9+.\-]*://", r) else "http://" + r
    try:
        sp = urlsplit(cand)
        host = (sp.hostname or "").lower()
        userinfo = sp.username
    except ValueError:
        host, userinfo = "", None
    if host.startswith("xn--") or ".xn--" in host:
        try:
            decoded = host.encode("ascii").decode("idna")
        except Exception:
            decoded = host
    else:
        decoded = host
    reg = registrable_domain(host) if host else ""
    return {"raw": r, "host": host, "host_decoded": decoded, "registrable": reg, "userinfo": userinfo,
            "shortener": reg in SHORTENERS, "full_text": r.lower()}


def extract_entities(t):
    urls = []
    seen = set()
    vpa_spans = [m.span() for m in VPA_RE.finditer(t)]
    for m in URL_RE.finditer(t):
        raw = m.group(1)
        if any(a <= m.start() < b for a, b in vpa_spans):
            continue
        if raw.lower() in seen:
            continue
        seen.add(raw.lower())
        urls.append(parse_url(raw))
    vpas = []
    for m in VPA_RE.finditer(t):
        a = t.rfind(" ", 0, m.start()) + 1
        b = t.find(" ", m.end())
        tok = t[a:(b if b != -1 else len(t))]
        if "://" in tok or "/" in tok:
            continue   # userinfo inside a URL, not a payment address
        vpas.append(m.group(0))
    vpas = [v for v in vpas if not re.search(r"(?i)@(gmail|yahoo|outlook|hotmail|rediffmail)$", v)]
    vpa_spans = [m.span() for m in VPA_RE.finditer(t)]
    phones = []
    for m in PHONE_RE.finditer(t):
        if any(a <= m.start(1) < b for a, b in vpa_spans):
            continue    # digits that are part of a UPI address are not a phone number
        p = re.sub(r"[\s\-]", "", m.group(1))
        if p not in phones:
            phones.append(p)
    regs = []
    for m in re.finditer(r"(?i)\bIN([AHZ])(\d{1,12})(?!\d)", t):
        regs.append({"raw": m.group(0).upper(), "prefix": "IN" + m.group(1).upper(), "digits": m.group(2),
                     "well_formed": len(m.group(2)) == 9})
    return {"urls": urls, "vpas": vpas, "phones": phones, "reg_numbers": regs}


# ----- privacy masking -------------------------------------------------------
def mask_identifier(s):
    if "@" in s:
        a, b = s.split("@", 1)
        return (a[:2] + "***" + a[-1:] if len(a) > 3 else a[:1] + "***") + "@" + b
    if s.isdigit() and len(s) >= 8:
        return s[:2] + "*" * (len(s) - 4) + s[-2:]
    return s


SENSITIVE_PATTERNS = [
    re.compile(r"(?<!\d)(?:\d[ \-]?){12,19}(?!\d)"),                 # card / aadhaar-like (12-19 digits)
    re.compile(r"(?i)(?:otp|pin|cvv|code|passcode)\D{0,15}(\d{4,8})(?!\d)"),
    re.compile(r"(?i)(\d{4,8})(?!\d)\D{0,12}(?:is your|is the)\D{0,10}(?:otp|code)"),
]


def sensitive_digit_runs(text):
    """Digit strings (>=4) that must never be reproduced in output."""
    runs = set()
    for p in SENSITIVE_PATTERNS:
        for m in p.finditer(text):
            for g in (m.groups() or (m.group(0),)):
                if g:
                    d = re.sub(r"\D", "", g)
                    if len(d) >= 4:
                        runs.add(d)
            d = re.sub(r"\D", "", m.group(0))
            if len(d) >= 4:
                runs.add(d)
    return runs


def mask_sensitive(snippet, runs=None):
    out = snippet
    for p in SENSITIVE_PATTERNS:
        def rep(m):
            s = m.group(0)
            return re.sub(r"\d", "#", s)
        out = p.sub(rep, out)
    if runs:
        for r in sorted(runs, key=len, reverse=True):
            out = out.replace(r, "#" * len(r))
    # also mask 9-10 digit phone-like runs and VPAs
    out = VPA_RE.sub(lambda m: mask_identifier(m.group(0)), out)
    out = re.sub(r"(?<!\d)(?:\+?91[\s\-]?)?[6-9]\d{4}[\s\-]?\d{5}(?!\d)", lambda m: mask_identifier(re.sub(r"\D", "", m.group(0))[-10:]), out)
    return out


def sentences(t):
    parts = re.split(r"(?<=[.!?।\n])\s+|\n+", t)
    return [p.strip() for p in parts if p.strip()]


def normalize(text, input_type="text"):
    clean, flags = nfkc_clean(text)
    clean = compact_registration_numbers(clean)
    clean, rflags = repair_noisy_text(clean)
    flags.update(rflags)
    lang, script_counts = detect_language(clean)
    ents = extract_entities(clean)
    return {
        "original_length": len(text), "text": clean, "flags": flags, "language": lang, "script_counts": script_counts,
        "entities": ents, "sensitive_runs": sensitive_digit_runs(clean), "sentences": sentences(clean), "input_type": input_type,
    }
