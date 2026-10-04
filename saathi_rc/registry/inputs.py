"""Input handling. No keyword/indicator detection: the only thing taken from pasted text is a string shaped like a SEBI registration number."""
import re, unicodedata

STRICT_RE = re.compile(r"^IN[AH][0-9]{9}$")
# candidate shapes in pasted text: IN + letter + 9 alphanumerics (optionally separated), or an IN/.../.. style number
_CAND = re.compile(r"(?i)(?<![A-Za-z0-9])(IN[A-Z][\s\-]?[0-9A-Z]{9}|IN/[A-Z0-9]+/[0-9]{2}-[0-9]{2}/[0-9]+)(?![A-Za-z0-9])")


def norm_number(s):
    """Trim, uppercase, remove inner spaces and hyphens. Never changes characters."""
    return re.sub(r"[\s\-]", "", (s or "").strip()).upper()


def classify_number(raw):
    """-> ('OK', norm) | ('MALFORMED_NUMBER', norm) | ('UNSUPPORTED_REGISTRATION_TYPE', norm) | ('NO_NUMBER', '')"""
    n = norm_number(raw)
    if not n:
        return "NO_NUMBER", ""
    if STRICT_RE.match(n):
        return "OK", n
    if n.startswith("IN/") or (n.startswith("IN") and len(n) >= 3 and n[2].isalpha() and n[2] not in "AH"):
        return "UNSUPPORTED_REGISTRATION_TYPE", n
    return "MALFORMED_NUMBER", n


def extract_numbers(text):
    """Distinct normalised candidate numbers in pasted text. A candidate needs >= 4 digits so that ordinary words are not picked up."""
    out, seen = [], set()
    for m in _CAND.finditer(text or ""):
        n = norm_number(m.group(1))
        if sum(c.isdigit() for c in n) < 4 or n in seen:
            continue
        seen.add(n); out.append(n)
    return out


_SUB = {"pvt": "private", "ltd": "limited", "co": "company", "&": "and"}


def norm_name(s):
    t = unicodedata.normalize("NFKC", s or "").casefold().replace("&", " and ")
    t = re.sub(r"[^\w\s]", " ", t)
    toks = [_SUB.get(w, w) for w in t.split()]
    return " ".join(toks)


_LEGAL = {"private", "limited", "llp", "company", "pvt", "ltd", "opc", "and"}


def core_tokens(norm):
    return [w for w in norm.split() if w not in _LEGAL]


def _stem(w):
    return w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w


_PROP = re.compile(r"\bproprietor of\b")


def compare_names(claimed, registered):
    """-> 'EXACT' | 'LEGAL_FORM_DIFFERS' | 'SIMILAR' | 'PROPRIETOR_RECORD' | 'DIFFERENT'. Conservative: only identical normalised strings are EXACT.
    RC changes: CH-R3a singular/plural of a word ('Investment' vs 'Investments') is SIMILAR, never EXACT (frozen v0.3 returned DIFFERENT for one-word plurals
    with low overlap); CH-R3b a name equal to ONE PART of a 'Person Proprietor of Trade Name' entry is PROPRIETOR_RECORD, never EXACT."""
    a, b = norm_name(claimed), norm_name(registered)
    if not a or not b:
        return "DIFFERENT"
    if a == b:
        return "EXACT"
    ca, cb = core_tokens(a), core_tokens(b)
    if ca and ca == cb:
        return "LEGAL_FORM_DIFFERS"
    if ca and cb and [_stem(w) for w in ca] == [_stem(w) for w in cb]:
        return "SIMILAR"
    parts = _PROP.split(b)
    if len(parts) == 2 and a in (parts[0].strip(), parts[1].strip()) and a:
        return "PROPRIETOR_RECORD"
    sa, sb = set(ca), set(cb)
    if sa and sb:
        j = len(sa & sb) / len(sa | sb)
        pref = ca[:len(cb)] == cb or cb[:len(ca)] == ca
        if j >= 0.6 or pref:
            return "SIMILAR"
    return "DIFFERENT"


def name_searchable(name):
    n = norm_name(name)
    return len(n.replace(" ", "")) >= 5 and len(n.split()) >= 2
