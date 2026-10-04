"""HTML rendering. Pure functions of the backend result dict: nothing is decided here. Every safety-relevant string comes from the backend result; the only
strings defined here are interface labels (English + Hindi, Hindi unreviewed). No external assets (works offline / low bandwidth). No green anywhere (green reads as 'safe')."""
import hashlib, html, json, re
from .. import VERSION
from ..contract import SITUATION_OPTIONS, SITUATION_QUESTION, ACTIONS, LANGS, INCIDENT_UI_HEAD

e = html.escape
# (text, background, border) -- contrast ratios of text on background are asserted in tests (>= 7:1 for body text, >= 4.5:1 elsewhere)
PALETTE = {
    "page": ("#1a1a1a", "#ffffff", "#767676"),
    "urgent": ("#5f1410", "#fdecea", "#b3261e"),
    "concern": ("#3d2300", "#fff4e0", "#a35200"),
    "info": ("#1b2a41", "#eaf0f7", "#3d5a80"),
    "unavail": ("#2b2b2b", "#f1f1f1", "#6b6b6b"),
    "banner": ("#3b3000", "#fff8d6", "#8a6d00"),
    "button": ("#ffffff", "#1d3f72", "#1d3f72"),
}
CSS = """
*{box-sizing:border-box}html{font-size:112.5%}body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans","Noto Sans Devanagari",sans-serif;line-height:1.55;margin:0;color:@page_t@;background:@page_b@}
.wrap{max-width:46rem;margin:0 auto;padding:1rem}h1{font-size:1.5rem;margin:.4rem 0}h2{font-size:1.2rem;margin:.2rem 0 .5rem}h3{font-size:1.05rem;margin:.8rem 0 .3rem}
.skip{position:absolute;left:-999px}.skip:focus{left:.5rem;top:.5rem;background:#fff;padding:.5rem;z-index:9}
.box{border:2px solid;border-left-width:10px;border-radius:.5rem;padding:.8rem 1rem;margin:1rem 0}
.urgent{color:@urgent_t@;background:@urgent_b@;border-color:@urgent_c@}.concern{color:@concern_t@;background:@concern_b@;border-color:@concern_c@}
.info{color:@info_t@;background:@info_b@;border-color:@info_c@}.unavail{color:@unavail_t@;background:@unavail_b@;border-color:@unavail_c@;border-style:dashed}
.banner{color:@banner_t@;background:@banner_b@;border:1px solid @banner_c@;border-radius:.4rem;padding:.5rem .8rem;font-size:.9rem}
.tag{display:inline-block;font-weight:700;font-size:.8rem;letter-spacing:.03em;text-transform:uppercase;border:2px solid currentColor;border-radius:.3rem;padding:0 .4rem;margin-right:.4rem}
label{display:block}.opt{display:flex;gap:.6rem;align-items:flex-start;padding:.6rem .5rem;margin:.3rem 0;border:1px solid @page_c@;border-radius:.4rem;min-height:2.75rem;cursor:pointer}
.opt input{width:1.4rem;height:1.4rem;margin-top:.2rem;flex:none}textarea,input[type=text],select{width:100%;font:inherit;padding:.6rem;border:2px solid @page_c@;border-radius:.4rem}
button,.btn{font:inherit;font-weight:700;color:@button_t@;background:@button_b@;border:2px solid @button_c@;border-radius:.4rem;padding:.7rem 1.2rem;min-height:2.75rem;cursor:pointer;text-decoration:none;display:inline-block}
button.secondary,.btn.secondary{color:@button_b@;background:#fff}
a{color:#0b3d91}:focus-visible{outline:4px solid #000;outline-offset:2px}.muted{font-size:.9rem}ul,ol{padding-left:1.3rem}li{margin:.35rem 0}
details{margin:.5rem 0}summary{cursor:pointer;font-weight:600;min-height:2.75rem;padding:.4rem 0}.src{font-size:.88rem;margin:.2rem 0 .6rem}.q{font-family:ui-monospace,monospace;font-size:.9rem}
fieldset.plain{border:0;padding:0;margin:1rem 0}label.gap{margin-top:.5rem}
@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}@media print{.nop{display:none}}
"""
for _k, _v in PALETTE.items():
    for _i, _s in enumerate("tbc"):
        CSS = CSS.replace("@%s_%s@" % (_k, _s), _v[_i])
JS = """(function(){var f=document.getElementById('regform');if(f&&window.fetch){f.addEventListener('submit',function(ev){ev.preventDefault();var o=document.getElementById('regout');o.textContent=f.getAttribute('data-wait');
fetch('/registry-fragment',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(f)).toString()}).then(function(r){return r.text()}).then(function(t){o.innerHTML=t;}).catch(function(){o.textContent=f.getAttribute('data-fail')})})}
var s=document.getElementById('speak');if(s&&window.speechSynthesis){s.hidden=false;s.addEventListener('click',function(){var t=document.getElementById('main').innerText;var u=new SpeechSynthesisUtterance(t);u.lang=document.documentElement.lang==='hi'?'hi-IN':'en-IN';window.speechSynthesis.cancel();window.speechSynthesis.speak(u)})}})();"""
CSP = "default-src 'none'; style-src 'sha256-%s'; script-src 'sha256-%s'; connect-src 'self'; form-action 'self'; base-uri 'none'" % (
    __import__("base64").b64encode(hashlib.sha256(CSS.encode()).digest()).decode(), __import__("base64").b64encode(hashlib.sha256(JS.encode()).digest()).decode())

UI = {
    "en": {"title": "Sangyan Saathi - check a suspicious message", "h1": "Suspicious message? Check it before you act", "skip": "Skip to main content",
           "banner": "Research prototype. It is not a fraud check. It cannot tell you that a message is genuine or safe, and it never gives a clean result.",
           "step1": "1. What has already happened?", "step2": "2. Paste the message (optional if you chose an option saying you already paid, shared details or gave access)",
           "privacy": "Do not paste OTPs, PINs, passwords, card or Aadhaar numbers. If you do, they are masked and nothing is stored or logged by this tool.",
           "ph": "Type or paste the suspicious message here. Do not include OTPs, passwords, PINs or account details.", "go": "Check the message", "lang": "हिन्दी", "langcode": "hi", "urgent_h": "Do this first", "found_h": "What this tool found in the message",
           "facts_h": "Checked against sources", "facts_sub": "What the collected sources say about claims in the message. This does not verify the message itself.",
           "ind_h": "Warning signs detected", "ind_sub": "Pattern matches in the text. They are warning signs, not proof of fraud.", "unc_h": "Could not be confirmed",
           "unc_sub": "Claims where the sources are not enough to say anything.", "steps_h": "What you can do next", "unav_h": "Not checked or not available", "lim_h": "Limits of this tool",
           "reg_h": "Optional demo: registration-number checker (sample data, not SEBI)", "reg_p": "DEMO ONLY: this compares the number with a small built-in list of made-up (synthetic) sample entries, not a real register. It does not contact SEBI, and it queries no SEBI or NSDL register. It cannot verify any real registration: a real registration number will show \"not found\" here, which says nothing about that number. To check a real number yourself, use the Intermediaries page on sebi.gov.in. A match here says nothing about any real message or offer.", "reg_num": "Registration number (INA or INH + 9 digits)",
           "reg_name": "Name the sender used (optional)", "reg_go": "Run demo check on sample data (not SEBI)", "reg_wait": "Checking the built-in sample list (SEBI is not contacted)...", "reg_fail": "Could not reach this tool's server. Nothing was checked.",
           "back": "Start again", "ifyes": "If the answer to any question is yes, start here", "sources": "Sources", "snap": "Source snapshot collected on %s (%s days ago)", "unknown": "unknown", "emerg": "Money already lost? Call 1930 and your bank now.",
           "speak": "Read this page aloud (uses your device's voice; availability varies)", "none_found": "Nothing in this group.","tier": {"T1": "official source", "T2": "reproduction of an official statement", "T3": "news or secondary report"},
           "label": {"urgent": "Urgent", "concern": "Warning", "info": "Info", "unavail": "Not checked"}, "posture": {"HIGH_CONCERN": "High concern", "SOME_CONCERN": "Some concern", "CANNOT_ASSESS": "Not enough information", "ABSTAIN": "No assessment", "ESCALATE": "Act now", "ASK_FOLLOWUP": "One question first", "NEEDS_SITUATION": "Choose first"},
           "pause": "Pause", "again_h": "Choose what applies, then check again", "err_h": "Something went wrong. Nothing was checked.", "toolong": "The text is too long.", "regsrc": "Source", "regdate": "Register date", "retrieved": "Retrieved", "record": "Register record"},
    "hi": {"title": "संज्ञान साथी - संदिग्ध संदेश जाँचें", "h1": "संदिग्ध संदेश? कुछ करने से पहले जाँचें", "skip": "मुख्य सामग्री पर जाएँ",
           "banner": "शोध प्रोटोटाइप। यह धोखाधड़ी की जाँच नहीं है। यह नहीं बता सकता कि कोई संदेश असली या सुरक्षित है, और कभी 'सब ठीक' नतीजा नहीं देता।",
           "step1": "1. अब तक क्या हुआ है?", "step2": "2. संदेश चिपकाएँ (वैकल्पिक, यदि आपने पैसे भेजने, जानकारी साझा करने या एक्सेस देने वाला विकल्प चुना है)", "privacy": "OTP, पिन, पासवर्ड, कार्ड या आधार संख्या न चिपकाएँ। चिपकाने पर वे छिपा दी जाती हैं और यह टूल कुछ भी सहेजता या लॉग नहीं करता।",
           "ph": "संदिग्ध संदेश यहाँ टाइप या चिपकाएँ। OTP, पासवर्ड, पिन या खाते का विवरण शामिल न करें।", "go": "संदेश जाँचें", "lang": "English", "langcode": "en", "urgent_h": "पहले यह करें", "found_h": "इस टूल को संदेश में क्या मिला",
           "facts_h": "स्रोतों से मिलान", "facts_sub": "संदेश के दावों के बारे में जुटाए गए स्रोत क्या कहते हैं। इससे संदेश की पुष्टि नहीं होती।", "ind_h": "पहचाने गए चेतावनी संकेत", "ind_sub": "पाठ में पैटर्न-मिलान। ये चेतावनी हैं, धोखाधड़ी का प्रमाण नहीं।",
           "unc_h": "पुष्टि नहीं हो सकी", "unc_sub": "ऐसे दावे जिनके बारे में स्रोत कुछ कहने के लिए काफ़ी नहीं हैं।", "steps_h": "आगे आप क्या कर सकते हैं", "unav_h": "जाँचा नहीं गया या उपलब्ध नहीं", "lim_h": "इस टूल की सीमाएँ",
           "reg_h": "वैकल्पिक डेमो: पंजीकरण-संख्या जाँच (नमूना डेटा, सेबी नहीं)", "reg_p": "केवल डेमो: यह संख्या को काल्पनिक नमूना प्रविष्टियों की एक छोटी अंतर्निहित सूची से मिलाता है। यह सेबी से संपर्क नहीं करता, और यह नहीं बता सकता कि कोई असली पंजीकरण संख्या सेबी की सूची में है या नहीं। असली संख्या खुद जाँचने के लिए sebi.gov.in का Intermediaries पेज देखें। यहाँ मिलान का किसी असली संदेश या ऑफ़र के बारे में कोई मतलब नहीं है।", "reg_num": "पंजीकरण संख्या (INA या INH + 9 अंक)",
           "reg_name": "भेजने वाले का बताया नाम (वैकल्पिक)", "reg_go": "नमूना डेटा पर डेमो जाँच चलाएँ (सेबी नहीं)", "reg_wait": "अंतर्निहित नमूना सूची में जाँच हो रही है (सेबी से संपर्क नहीं हो रहा)...", "reg_fail": "इस टूल के सर्वर तक नहीं पहुँचा जा सका। कुछ भी नहीं जाँचा गया।",
           "back": "फिर शुरू करें", "ifyes": "अगर किसी भी सवाल का जवाब हाँ है, तो यहाँ से शुरू करें", "sources": "स्रोत", "snap": "स्रोत %s को जुटाए गए (%s दिन पहले)", "unknown": "अज्ञात", "emerg": "पैसे जा चुके हैं? अभी 1930 और अपने बैंक को कॉल करें।",
           "speak": "यह पृष्ठ पढ़कर सुनाएँ (आपके डिवाइस की आवाज़; उपलब्धता अलग-अलग)", "none_found": "इस समूह में कुछ नहीं।", "tier": {"T1": "आधिकारिक स्रोत", "T2": "आधिकारिक बयान की प्रति", "T3": "समाचार या द्वितीयक रिपोर्ट"},
           "label": {"urgent": "ज़रूरी", "concern": "चेतावनी", "info": "जानकारी", "unavail": "जाँचा नहीं"}, "posture": {"HIGH_CONCERN": "अधिक चिंता", "SOME_CONCERN": "कुछ चिंता", "CANNOT_ASSESS": "आकलन नहीं हो सकता", "ABSTAIN": "कोई आकलन नहीं", "ESCALATE": "अभी कदम उठाएँ", "ASK_FOLLOWUP": "पहले एक सवाल", "NEEDS_SITUATION": "पहले चुनें"},
           "pause": "रुकिए", "again_h": "जो लागू हो चुनें, फिर दोबारा जाँचें", "err_h": "कुछ गलत हुआ। कुछ भी नहीं जाँचा गया।", "toolong": "पाठ बहुत लंबा है।", "regsrc": "स्रोत", "regdate": "रजिस्टर की तारीख", "retrieved": "प्राप्त", "record": "रजिस्टर रिकॉर्ड"},
}
# English-only plain-language lead for the CANNOT_ASSESS page. Kept out of UI[] on purpose: UI must have identical keys in en and hi, and no Hindi text was written or added here.
CANNOT_ASSESS_EN = {"lead": "There is not enough information to assess this message reliably.",
                    "note": "Please verify it through trusted channels: contact your bank, broker or the sender using a phone number or app you already have, not the link or number in the message. An inconclusive result does not mean the message is safe."}

SUBJECTLESS_RISK_EN = "The risk found in your text (a pattern match, not certain):"

POSTURE_BOX = {"ESCALATE": "urgent", "ASK_FOLLOWUP": "concern", "HIGH_CONCERN": "concern", "SOME_CONCERN": "concern", "CANNOT_ASSESS": "info", "ABSTAIN": "unavail", "NEEDS_SITUATION": "info"}


def L(lang):
    return lang if lang in LANGS else "en"


def page(body, lang, title=None):
    u = UI[L(lang)]
    return ("<!doctype html><html lang='%s'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='color-scheme' content='light'>"
            "<title>%s</title><style>%s</style></head><body><a class='skip' href='#main'>%s</a><div class='wrap'><header><div class='banner' role='note'>%s</div></header>"
            "<main id='main' tabindex='-1'>%s</main><footer class='muted'><p>Sangyan Saathi %s &middot; <a href='/about?lang=%s'>%s</a></p></footer></div><script>%s</script></body></html>"
            % (L(lang), e(title or u["title"]), CSS, e(u["skip"]), e(u["banner"]), body, e(VERSION), L(lang), "About, limits and data" if L(lang) == "en" else "जानकारी, सीमाएँ और डेटा", JS)).encode("utf-8")


SOURCE_INDEX = {}   # passage_id -> {publisher,url}; filled by the app from the corpus. Display only.


def _src_link(pid):
    x = SOURCE_INDEX.get(pid)
    if not x: return e(pid)
    return "<a href='%s' rel='noopener noreferrer'>%s</a>" % (e(x["url"]), e(x["publisher"]))


# Priority labels for the urgent block (display only; step texts, sources and order come from the backend unchanged).
PRIO = {"A_CONTACT_BANK": {"en": "Step 1: Your bank", "hi": "चरण 1: आपका बैंक"}, "A_CALL_1930": {"en": "Step 2: 1930 or cybercrime.gov.in", "hi": "चरण 2: 1930 या cybercrime.gov.in"},
        "A_HAVE_DETAILS": {"en": "Step 3: Evidence", "hi": "चरण 3: सबूत"}, "A_PRESERVE_EVIDENCE": {"en": "Step 3: Evidence", "hi": "चरण 3: सबूत"},
        "A_NO_PAY_NO_SHARE": {"en": "Also", "hi": "साथ ही"}, "A_NO_REMOTE": {"en": "Also", "hi": "साथ ही"}}


def _ifyes_order(steps):
    """Display only: in the "if the answer is yes" block, show the conditional bank -> 1930 -> evidence steps first (same order as the urgent block), then the general do-not-pay step. Texts, sources and the backend order are unchanged."""
    return [s for s in steps if s.get("conditional")] + [s for s in steps if not s.get("conditional")]


def _steps_html(steps, lang, cls=None):
    prio = cls == "urgent"   # urgent block only: add priority labels
    out = "<ul>"; last = None
    for s in steps:
        lab = PRIO.get(s.get("action_id"), {}).get(L(lang)) if prio else None
        tag = "<strong>%s</strong> &mdash; " % e(lab) if lab and lab != last else ""
        if lab: last = lab
        out += "<li>%s%s <span class='muted'>(%s: %s)</span></li>" % (tag, e(s["text"]), e(UI[L(lang)]["sources"]), "; ".join(_src_link(i) for i in s["sources"]))
    return out + "</ul>"


def emergency_strip(lang):
    s = ACTIONS["A_CALL_1930"]
    u = UI[L(lang)]
    return "<div class='box urgent' role='note'><span class='tag'>%s</span> <strong>%s</strong> %s</div>" % (e(u["label"]["urgent"]), e(u["emerg"]), e(s.get(L(lang)) or s["en"]))


def form(lang="en", text="", chosen=None):
    u, hi = UI[L(lang)], L(lang) == "hi"
    opts = "".join("<label class='opt'><input type='radio' name='situation' value='%s' required%s> <span>%s</span></label>" % (k, " checked" if chosen == k else "", e(v[L(lang)])) for k, v in SITUATION_OPTIONS.items())
    body = ("<p><a class='btn secondary nop' href='/?lang=%s' lang='%s'>%s</a></p><h1>%s</h1>%s<form method='post' action='/check'><input type='hidden' name='output_language' value='%s'>"
            "<fieldset class='plain'><legend><h2>%s</h2></legend>%s</fieldset><h2><label for='text'>%s</label></h2><p class='muted' id='priv'>%s</p>"
            "<textarea id='text' name='text' rows='7' maxlength='20000' aria-describedby='priv' placeholder='%s'>%s</textarea><p><button type='submit'>%s</button></p></form>"
            % (u["langcode"], u["langcode"], e(u["lang"]), e(u["h1"]), emergency_strip(lang), L(lang), e(u["step1"]), opts, e(u["step2"]), e(u["privacy"]), e(u["ph"]), e(text), e(u["go"])))
    return page(body, lang)


def _src_html(ev, lang):
    u = UI[L(lang)]
    if not ev: return ""
    items = "".join("<li class='src'>%s &middot; %s &middot; %s &middot; <a href='%s' rel='noopener noreferrer'>%s</a><br><span class='muted'>&ldquo;%s&rdquo; (the source's title only: its own text is not included in this release &mdash; open the link to read it)</span></li>" % (
        e(x["publisher"]), e(u["tier"].get(x["tier"], x["tier"])), e(x["date_of_source"]), e(x["url"]), e(x["passage_id"]), e(x["title"][:240])) for x in ev)
    return "<details><summary>%s (%d)</summary><ul>%s</ul></details>" % (e(u["sources"]), len(ev), items)


def _claim_html(c, lang):
    return "<li><strong>%s</strong> <span class='muted'>(%s)</span><br>%s%s</li>" % (e(c["state_label"]), e(c["claim_type"].replace("_", " ").lower()), e(c["explanation"]), _src_html(c.get("evidence", []), lang))


_DEMO_EN = [(r"(?:the )?SEBI lists searched", "the demo sample list"), (r"SEBI's list of (?=cancelled|ended)", "the demo sample list of "),
            (r"SEBI's (?:current )?(?:(?:Investment Advisers?|Research Analysts?|Investment Adviser and Research Analyst) )?(?:register|lists?)\b", "the demo sample list"),
            (r"\bthe SEBI lists?\b", "the demo sample list"), (r"\bSEBI lists?\b", "the demo sample list")]
_DEMO_HI = [(r"सेबी की (?=रद्द|समाप्त)", "डेमो नमूना-सूची की "), (r"सेबी (?:के|का) रजिस्टर(?: में)?", "डेमो नमूना-सूची में"),
            (r"सेबी (?:की|के|का) [^।]*?सूच(?:ी|ियों)", "डेमो नमूना-सूची"), (r"सेबी सूचि", "डेमो नमूना-सूचि")]


DEMO_SOURCE = {"en": "built-in demo fixture of invented sample entries (not SEBI)", "hi": "अंतर्निहित डेमो फ़िक्स्चर, काल्पनिक नमूना प्रविष्टियाँ (सेबी नहीं)"}


def _demo_wording(s, lang):
    """Fixture mode only: the backend's register wording says 'SEBI's list'. In demo mode the page must say 'demo sample list' instead, so a card can never be read as a live SEBI result. Display-level only; the backend result is unchanged."""
    for pat, to in (_DEMO_HI if L(lang) == "hi" else _DEMO_EN):
        s = re.sub(pat, to, s or "")
    return s


def registry_card_html(reg, lang, demo=False):
    """Card + reminder. The reminder is NOT muted: same size and weight as the result, directly under the headline."""
    u = UI[L(lang)]; c = reg["card"]
    rr = c.get("register_record")
    rec = "<p><strong>%s:</strong> <span class='q'>%s &middot; %s</span> %s %s</p>" % (e(u["record"]), e(rr["reg_no"]), e(rr["name"]), e(rr.get("validity") or ""), e(rr.get("register_status") or "")) if rr else ""
    cands = "<ul>" + "".join("<li><span class='q'>%s</span> %s</li>" % (e(x["reg_no"]), e(x["name"])) for x in c.get("candidates", [])) + "</ul>" if c.get("candidates") else ""
    prov = ", ".join(sorted({p.get("retrieved_at_utc") or "" for p in c.get("provenance", [])}))
    cls = "info" if c["status"] in ("CONFIRMED_IN_REGISTER", "LISTED_NAME_NOT_COMPARED") else "concern" if c["status"] in ("NAME_DIFFERS", "INACTIVE_IN_REGISTER", "NOT_FOUND", "AMBIGUOUS") else "unavail"
    demo_box = ("<div class='box urgent' role='note'><strong>DEMO DATA: made-up sample entries, not a real register. This card comes from a built-in fixture, not from SEBI's list.</strong> Nothing below was checked against SEBI. No live SEBI or NSDL register was queried, and nothing below verifies a real registration. Only invented entries can match here; a real registration number will show \"not found\", which says nothing about that number.</div>" if L(lang) == "en" else
                "<div class='box urgent' role='note'><strong>DEMO DATA (डेमो डेटा): यह कार्ड अंतर्निहित नमूना फ़िक्स्चर से आया है, सेबी की सूची से नहीं।</strong> नीचे कुछ भी सेबी से नहीं जाँचा गया। यहाँ केवल काल्पनिक प्रविष्टियाँ ही मिल सकती हैं; कोई असली पंजीकरण संख्या \"नहीं मिली\" दिखाएगी, जिसका उस संख्या के बारे में कोई मतलब नहीं है।</div>") if demo else ""
    if demo:
        c = dict(c, headline=("DEMO RESULT (sample data, not SEBI): " if L(lang) == "en" else "डेमो परिणाम (नमूना डेटा, सेबी नहीं): ") + _demo_wording(c["headline"], lang),
                 means=_demo_wording(c["means"], lang), does_not_mean=_demo_wording(c["does_not_mean"], lang))
        reg = dict(reg, reminder=_demo_wording(reg["reminder"], lang))
    return (demo_box + "<div class='box %s' id='registry-card'><h3>%s</h3><p><strong>%s</strong></p><p>%s</p>%s%s<div class='box concern' role='note'><p><strong>%s</strong></p><p>%s</p></div>"
            "<p class='muted'>%s: %s &middot; %s: %s &middot; %s: %s</p></div>" % (
                cls, e(u["reg_h"]), e(c["headline"]), e(c["means"]), rec, cands, e(c["does_not_mean"]), e(reg["reminder"]),
                e(u["regsrc"]), e((DEMO_SOURCE[L(lang)] if demo else (c.get("source") or {}).get("name", ""))), e(u["regdate"]), e(str(c.get("as_of"))), e(u["retrieved"]), e(prov)))


def registry_form_html(res, lang):
    u = UI[L(lang)]
    nums = res.get("registry_offer", {}).get("numbers", [])
    pre = nums[0] if nums else ""
    return ("<section class='box info' aria-labelledby='regh'><details%s><summary id='regh'>%s</summary><p>%s</p><form id='regform' method='post' action='/registry' data-wait='%s' data-fail='%s'>"
            "<input type='hidden' name='output_language' value='%s'><input type='hidden' name='situation' value='%s'><label for='rn'>%s</label><input id='rn' type='text' name='number' value='%s' autocomplete='off' inputmode='text'>"
            "<label for='rm' class='gap'>%s</label><input id='rm' type='text' name='name' autocomplete='off'><p><button type='submit'>%s</button></p></form><div id='regout' aria-live='polite'></div></details></section>"
            % (" open" if pre else "", e(u["reg_h"]), e(u["reg_p"]), e(u["reg_wait"]), e(u["reg_fail"]), L(lang), e(res.get("situation") or ""), e(u["reg_num"]), e(pre), e(u["reg_name"]), e(u["reg_go"])))


def incident_html(res, lang):
    """S4: shows the backend's incident object as is (state label, quoted clause, heuristic note); nothing is recomputed here. Not shown for NO_INCIDENT, so it can never read as reassurance."""
    inc = res.get("incident")
    if not inc or inc.get("state") == "NO_INCIDENT": return ""
    quotes = "".join("<li><span class='muted q'>&ldquo;%s&rdquo;</span></li>" % e(x["snippet"]) for x in inc.get("events", []) if x.get("snippet"))
    also = "".join("<li>%s</li>" % e(x) for x in inc.get("also", []))
    risk_html = ""
    # P3 (demo sprint 3): the subject-less-payment label says "a risk (listed below)" but the view never listed the backend's risk_context. Shown for that route only, in English
    # only (the backend reason strings are English; no Hindi text was written, so the Hindi page is unchanged).
    if (res.get("provenance") or {}).get("incident_route") == "escalated_subjectless_payment_with_context" and inc.get("risk_context") and lang == "en":
        risk_html = "<p><strong>%s</strong></p><ul>%s</ul>" % (e(SUBJECTLESS_RISK_EN), "".join("<li>%s</li>" % e(x) for x in inc["risk_context"]))
    return ("<section class='box concern' id='incident' data-state='%s' aria-labelledby='inch'><h2 id='inch'>%s</h2><p><strong>%s</strong></p>%s%s<p class='muted'>%s</p>%s</section>" % (
        e(inc["state"]), e(INCIDENT_UI_HEAD[lang]), e(inc["label"]), ("<ul>%s</ul>" % quotes) if quotes else "", (("<ul>%s</ul>" % also) if also else "") + risk_html, e(inc.get("note", "")),
        ("<p><strong>%s</strong></p>" % e(inc["conflict_note"])) if inc.get("conflict_note") else ""))


def correction_form(res, lang, text, u):
    opts = "".join("<label class='opt'><input type='radio' name='situation' value='%s' required> <span>%s</span></label>" % (o["code"], e(o["text"])) for o in res.get("options", []))
    return ("<form method='post' action='/check'><input type='hidden' name='output_language' value='%s'><fieldset class='plain'><legend><h2>%s</h2></legend>%s</fieldset>"
            "<h2><label for='t3'>%s</label></h2><textarea id='t3' name='text' rows='5' maxlength='20000' placeholder='%s'>%s</textarea><p><button type='submit'>%s</button></p></form>" % (lang, e(u["again_h"]), opts, e(u["step2"]), e(u["ph"]), e(text), e(u["go"])))


def render_result(res, extra_registry=None, text=""):
    lang = L(res.get("language")); u = UI[lang]; p = res["posture"]
    box = POSTURE_BOX.get(p, "info")
    out = ["<p><a class='btn secondary nop' href='/?lang=%s'>&larr; %s</a> <button type='button' id='speak' class='secondary nop' hidden>%s</button></p>" % (lang, e(u["back"]), e(u["speak"]))]
    if p == "CANNOT_ASSESS" and lang == "en":   # English only: plain-language lead (CANNOT_ASSESS_EN); the backend headline and summary stay on the page unchanged. No Hindi text was added.
        out.append("<section class='box %s' aria-labelledby='hd'><h1 id='hd'><span class='tag'>%s</span></h1><p><strong>%s</strong></p><p>%s</p><p>%s</p>%s</section>" % (
            box, e(u["posture"].get(p, p)), e(CANNOT_ASSESS_EN["lead"]), e(CANNOT_ASSESS_EN["note"]), e(res["headline"]), ("<p>%s</p>" % e(res["summary"])) if res.get("summary") else ""))
    else:
        out.append("<section class='box %s' aria-labelledby='hd'><h1 id='hd'><span class='tag'>%s</span></h1><p><strong>%s</strong></p>%s</section>" % (
            box, e(u["posture"].get(p, p)), e(res["headline"]), ("<p>%s</p>" % e(res["summary"])) if res.get("summary") and p not in ("NEEDS_SITUATION",) else ""))
    if res.get("pause_notice"):
        out.append("<p><strong>%s</strong></p>" % e(res["pause_notice"]))
    if res.get("urgent_steps"):
        out.append("<section class='box urgent' role='alert' aria-labelledby='ug'><h2 id='ug'><span class='tag'>%s</span> %s</h2>%s</section>" % (e(u["label"]["urgent"]), e(u["urgent_h"]), _steps_html(res["urgent_steps"], lang, "urgent")))
    out.append(incident_html(res, lang))
    if (res.get("incident") or {}).get("applied") == "escalated_from_text":
        out.append(correction_form(res, lang, text, u))
    if p in ("ASK_FOLLOWUP", "NEEDS_SITUATION"):
        if res.get("questions"):
            out.append("<section class='box concern'><ol>%s</ol></section>" % "".join("<li>%s</li>" % e(q) for q in res["questions"]))
        if res.get("steps"):
            out.append("<section class='box urgent' role='alert' aria-labelledby='ifyes'><h2 id='ifyes'><span class='tag'>%s</span> %s</h2>%s</section>" % (e(u["label"]["urgent"]), e(u["ifyes"]), _steps_html(_ifyes_order(res["steps"]), lang, "urgent")))
        opts = "".join("<label class='opt'><input type='radio' name='situation' value='%s' required> <span>%s</span></label>" % (o["code"], e(o["text"])) for o in res.get("options", []))
        out.append("<form method='post' action='/check'><input type='hidden' name='output_language' value='%s'><fieldset class='plain'><legend><h2>%s</h2></legend>%s</fieldset>"
                   "<h2><label for='t2'>%s</label></h2><p class='muted'>%s</p><textarea id='t2' name='text' rows='5' maxlength='20000' placeholder='%s'>%s</textarea><p><button type='submit'>%s</button></p></form>" % (
                       lang, e(u["again_h"]), opts, e(u["step2"]), e(u["privacy"]), e(u["ph"]), e(text), e(u["go"])))
    else:
        facts = [c for c in res["claims"] if c["state"] in ("SUPPORTED", "CONTRADICTED")]
        unc = [c for c in res["claims"] if c["state"] not in ("SUPPORTED", "CONTRADICTED")]
        if p not in ("ESCALATE",):
            out.append("<h2>%s</h2>" % e(u["found_h"]))
            out.append("<section class='box info' aria-labelledby='fh'><h3 id='fh'><span class='tag'>%s</span> %s</h3><p class='muted'>%s</p>%s</section>" % (
                e(u["label"]["info"]), e(u["facts_h"]), e(u["facts_sub"]), ("<ul>%s</ul>" % "".join(_claim_html(c, lang) for c in facts)) if facts else "<p>%s</p>" % e(u["none_found"])))
            out.append("<section class='box concern' aria-labelledby='ih'><h3 id='ih'><span class='tag'>%s</span> %s</h3><p class='muted'>%s</p>%s</section>" % (
                e(u["label"]["concern"]), e(u["ind_h"]), e(u["ind_sub"]), ("<ul>%s</ul>" % "".join("<li><strong>%s</strong>: %s <span class='muted q'>&ldquo;%s&rdquo;</span></li>" % (e(i["indicator"].replace("_", " ").lower()), e(i["note"]), e(i["snippet"])) for i in res["indicators"])) if res["indicators"] else "<p>%s</p>" % e(u["none_found"])))
            if unc:
                out.append("<section class='box unavail' aria-labelledby='uh'><h3 id='uh'><span class='tag'>%s</span> %s</h3><p class='muted'>%s</p><ul>%s</ul></section>" % (e(u["label"]["unavail"]), e(u["unc_h"]), e(u["unc_sub"]), "".join(_claim_html(c, lang) for c in unc)))
        if res.get("steps"):
            out.append("<section class='box info' aria-labelledby='sh'><h2 id='sh'>%s</h2>%s</section>" % (e(u["steps_h"]), _steps_html(res["steps"], lang)))
        if p in ("HIGH_CONCERN", "SOME_CONCERN", "CANNOT_ASSESS", "ABSTAIN"):
            out.append(registry_form_html(res, lang))
        if extra_registry:
            out.append(extra_registry)
    if res.get("unavailable"):
        out.append("<section class='box unavail' aria-labelledby='nh'><h2 id='nh'><span class='tag'>%s</span> %s</h2><ul>%s</ul></section>" % (e(u["label"]["unavail"]), e(u["unav_h"]), "".join("<li>%s</li>" % e(x["text"]) for x in res["unavailable"])))
    fr = res.get("freshness") or {}
    snap = (u["snap"] % (fr.get("snapshot_date") or u["unknown"], fr.get("age_days") if fr.get("age_days") is not None else u["unknown"])) if fr else ""
    out.append("<section class='box info' aria-labelledby='lh'><h2 id='lh'>%s</h2><ul>%s</ul><p class='muted'>%s</p></section>" % (e(u["lim_h"]), "".join("<li>%s</li>" % e(x) for x in res["limitations"]), e(snap)))
    return page("".join(out), lang)


def render_registry_page(res, reg, lang, demo=False):
    """Standalone page for the no-JavaScript path: urgent block for the chosen situation first, then the card."""
    lang = L(lang); u = UI[lang]
    body = ["<p><a class='btn secondary nop' href='/?lang=%s'>&larr; %s</a></p><h1>%s</h1>" % (lang, e(u["back"]), e(u["reg_h"]))]
    if res.get("urgent_steps"):
        body.append("<section class='box urgent' role='alert'><h2><span class='tag'>%s</span> %s</h2>%s</section>" % (e(u["label"]["urgent"]), e(u["urgent_h"]), _steps_html(res["urgent_steps"], lang, "urgent")))
    else:
        body.append(emergency_strip(lang))
    body.append(registry_card_html(reg, lang, demo))
    return page("".join(body), lang)


def render_error(lang="en"):
    u = UI[L(lang)]
    return page("<h1>%s</h1>%s" % (e(u["err_h"]), emergency_strip(lang)), lang)


def render_about(lang="en"):
    from ..contract import LIMITS
    lang = L(lang)
    items = {"en": ["What it does: you say what has already happened; the tool then compares the pasted message with a small fixed set of warning patterns and a fixed, hand-made list of cited sources, and gives steps taken from those sources. This release shows only each source's title and link, not its text. Some sources are official; others are news or commercial pages. The tier of each source is shown.",
                    "What it never does: say a message is genuine or safe; give stock tips, predictions or recommendations; open links; contact the sender. It does not store or log your text in its own code (no database, no access log), but servers and networks you use may still log traffic.",
                    "Languages: English and Hindi are the core languages. Marathi and Tamil are limited. Other languages are not read: only links and similar signs are seen, and the tool says so.",
                    "Hindi text has not been reviewed by a native speaker or domain expert. Source explanations are in English.",
                    "Sources: a fixed list of official and news pages, shown by title and link (see each result); the pages' own text is not included in this release. Their age is shown on every result; old snapshots weaken what claims can show.",
                    "Register check: in this release it works only on made-up demo records and never contacts SEBI. It is not an official SEBI service and SEBI has not endorsed this tool. A match does not show who contacted you or that an offer is trustworthy."],
             "hi": ["यह क्या करता है: आप बताते हैं कि अब तक क्या हुआ है; फिर टूल चिपकाए संदेश को चेतावनी-पैटर्न के छोटे निश्चित समूह और उद्धृत स्रोतों की निश्चित, हाथ से बनी सूची से मिलाता है और उन्हीं स्रोतों से लिए गए कदम बताता है। इस संस्करण में हर स्रोत का केवल शीर्षक और लिंक दिखता है, उसका अपना पाठ शामिल नहीं है। कुछ स्रोत आधिकारिक हैं; अन्य समाचार या व्यावसायिक पेज हैं। हर स्रोत का स्तर दिखाया जाता है।",
                    "यह क्या कभी नहीं करता: संदेश को असली या सुरक्षित नहीं कहता; स्टॉक टिप्स, अनुमान या सिफ़ारिश नहीं देता; लिंक नहीं खोलता; भेजने वाले से संपर्क नहीं करता। यह अपने कोड में आपका पाठ सहेजता या लॉग नहीं करता (कोई डेटाबेस या एक्सेस लॉग नहीं), लेकिन आपके द्वारा उपयोग किए जा रहे सर्वर और नेटवर्क फिर भी ट्रैफ़िक लॉग कर सकते हैं।",
                    "भाषाएँ: अंग्रेज़ी और हिंदी मुख्य हैं। मराठी और तमिल सीमित हैं। अन्य भाषाएँ पढ़ी नहीं जातीं: केवल लिंक जैसे संकेत दिखते हैं, और टूल यह बताता है।",
                    "हिंदी पाठ किसी मातृभाषी या विशेषज्ञ द्वारा जाँचा नहीं गया है। स्रोतों के स्पष्टीकरण अंग्रेज़ी में हैं।", "स्रोत: आधिकारिक और समाचार पेजों की निश्चित सूची, जो शीर्षक और लिंक के रूप में दिखती है (पेजों का अपना पाठ इस संस्करण में शामिल नहीं है)। हर नतीजे पर उसकी उम्र दिखती है; पुराना संग्रह दावों से निकलने वाले निष्कर्ष कमज़ोर करता है।",
                    "रजिस्टर जाँच: इस संस्करण में यह केवल बनावटी डेमो रिकॉर्ड पर चलती है और सेबी से कभी संपर्क नहीं करती। यह सेबी की आधिकारिक सेवा नहीं है और सेबी ने इस टूल का समर्थन नहीं किया है। मिलान से यह पता नहीं चलता कि आपसे किसने संपर्क किया या ऑफ़र भरोसेमंद है।"]}
    body = "<p><a class='btn secondary' href='/?lang=%s'>&larr; %s</a></p><h1>%s</h1><ul>%s</ul>" % (lang, e(UI[lang]["back"]), "About, limits and data" if lang == "en" else "जानकारी, सीमाएँ और डेटा", "".join("<li>%s</li>" % e(x) for x in items[lang]))
    return page(body, lang)
