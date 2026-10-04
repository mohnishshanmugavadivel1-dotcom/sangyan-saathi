"""Safe next steps. Every action carries source IDs from the corpus. No action ever promises recovery."""
from .contracts import LOSS_SITUATIONS

ACTIONS = {
    "A_NO_PAY_NO_SHARE": dict(sources=["SEBI-PR14-2026-b", "RBI-BEAWARE-VISHING"],
        en="Do not pay money, and do not share OTPs, PINs, passwords or trading-account details, because of this message.",
        hi="इस संदेश के कारण पैसे न भेजें, और OTP, पिन, पासवर्ड या ट्रेडिंग-खाते की जानकारी किसी को न दें।"),
    "A_VERIFY_REG": dict(sources=["SEBI-PR14-2026-c"],
        en="Check the sender's name and registration number yourself on SEBI's official 'Intermediaries' page (sebi.gov.in) before dealing with them.",
        hi="उनसे लेन-देन करने से पहले सेबी की आधिकारिक वेबसाइट (sebi.gov.in) के 'Intermediaries' पेज पर भेजने वाले का नाम और पंजीकरण नंबर खुद जांचें।"),
    "A_OFFICIAL_CALLBACK": dict(sources=["RBI-BEAWARE-CONTACT", "SANCHAR-FAQ-EXAMPLES"],
        en="If you are unsure, contact your bank or broker through the number or app you already have, not through the link or number in the message.",
        hi="यदि संदेह हो तो अपने बैंक या ब्रोकर से उसी नंबर या ऐप के जरिए संपर्क करें जो आपके पास पहले से है, संदेश में दिए लिंक या नंबर से नहीं।"),
    "A_AVOID_GROUPS": dict(sources=["TEAMLEASE-PR27-a"],
        en="Do not join investment groups that reach you unasked; unsolicited Telegram/WhatsApp groups are a known channel for these schemes.",
        hi="बिना मांगे आए निवेश ग्रुप में शामिल न हों; अनचाहे टेलीग्राम/व्हाट्सएप ग्रुप ऐसी योजनाओं का जाना-पहचाना माध्यम हैं।"),
    "A_NO_REMOTE": dict(sources=["RBI-BEAWARE-REMOTE"],
        en="Do not install screen-sharing or remote-access apps (for example AnyDesk or TeamViewer) at a stranger's request.",
        hi="किसी अजनबी के कहने पर स्क्रीन-शेयरिंग या रिमोट-एक्सेस ऐप (जैसे AnyDesk, TeamViewer) इंस्टॉल न करें।"),
    "A_SEBI_CHECK_PAYEE": dict(sources=["REDIFF-SEBICHECK", "SEBICHECK-LIVE"],
        en="SEBI's 'SEBI Check' service is meant for checking whether a payment ID belongs to a registered intermediary. Use it before paying any UPI ID.",
        hi="सेबी की 'SEBI Check' सेवा यह जांचने के लिए है कि कोई भुगतान आईडी पंजीकृत मध्यस्थ की है या नहीं। किसी भी UPI आईडी में भुगतान से पहले इसका उपयोग करें।"),
    "A_CHAKSHU": dict(sources=["SANCHAR-SFC-30"],
        en="You can report the suspected fraudulent call, SMS or WhatsApp message on Sanchar Saathi's Chakshu within 30 days (sancharsaathi.gov.in). Chakshu is not for reporting money already lost.",
        hi="संदिग्ध कॉल, SMS या व्हाट्सएप संदेश की रिपोर्ट 30 दिन के भीतर संचार साथी के चक्षु (sancharsaathi.gov.in) पर कर सकते हैं। चक्षु खो चुके पैसों की रिपोर्ट के लिए नहीं है।"),
    "A_REPORT_SUSPECT": dict(sources=["NCRP-SUSPECT"],
        en="The national cybercrime portal (cybercrime.gov.in) has a 'Report Suspect' option for suspicious links, numbers and accounts.",
        hi="राष्ट्रीय साइबर अपराध पोर्टल (cybercrime.gov.in) पर संदिग्ध लिंक, नंबर और खातों के लिए 'Report Suspect' विकल्प है।"),
    "A_CALL_1930": dict(sources=["SANCHAR-SFC", "MHA-RS-1930", "NCRP-SUSPECT"],
        en="If money has already gone or you shared credentials: call 1930 (national cyber-fraud helpline) or report at cybercrime.gov.in as soon as possible.",
        hi="यदि पैसे जा चुके हैं या आपने जानकारी साझा की है: तुरंत 1930 (राष्ट्रीय साइबर-धोखाधड़ी हेल्पलाइन) पर कॉल करें या cybercrime.gov.in पर रिपोर्ट करें।"),
    "A_CALL_1930_COND": dict(sources=["SANCHAR-SFC", "MHA-RS-1930"],
        en="If you have already lost money, report to 1930 or cybercrime.gov.in; the Chakshu service is not for that.",
        hi="यदि आप पैसे खो चुके हैं, तो 1930 या cybercrime.gov.in पर रिपोर्ट करें; चक्षु सेवा इसके लिए नहीं है।"),
    "A_CONTACT_BANK": dict(sources=["RBI-LIMITED-LIABILITY"],
        en="Contact your bank right away through its official number or app to report the transaction and ask about blocking or disputing it.",
        hi="अपने बैंक के आधिकारिक नंबर या ऐप से तुरंत संपर्क करें, लेन-देन की सूचना दें और उसे रोकने या विवाद दर्ज करने के बारे में पूछें।"),
    "A_PRESERVE_EVIDENCE": dict(sources=["NCRP-FIN-MANUAL"],
        en="Keep screenshots, transaction IDs, phone numbers and chat history; do not delete them. You will need them for the complaint. (The official guide names the transaction ID, the date and a screenshot of the transaction; the other items are general good practice.)",
        hi="स्क्रीनशॉट, लेन-देन आईडी, फोन नंबर और चैट इतिहास सुरक्षित रखें, उन्हें डिलीट न करें। शिकायत के लिए इनकी जरूरत होगी। (आधिकारिक मार्गदर्शिका में लेन-देन आईडी, तारीख और लेन-देन का स्क्रीनशॉट बताया गया है; बाकी चीज़ें सामान्य अच्छी आदत हैं।)"),
}
LOSS_REQUIRED = ["A_CALL_1930", "A_CONTACT_BANK", "A_PRESERVE_EVIDENCE"]
ORDER = ["A_CALL_1930", "A_CONTACT_BANK", "A_PRESERVE_EVIDENCE", "A_NO_PAY_NO_SHARE", "A_NO_REMOTE", "A_VERIFY_REG", "A_SEBI_CHECK_PAYEE",
         "A_OFFICIAL_CALLBACK", "A_AVOID_GROUPS", "A_REPORT_SUSPECT", "A_CHAKSHU", "A_CALL_1930_COND"]


def action_id_for_output(a):
    return "A_CALL_1930" if a == "A_CALL_1930_COND" else a


def choose(posture, claims, indicators, norm, situation, abstained):
    """Return ordered list of action keys."""
    import re
    inds = {i["indicator"] for i in indicators}
    cts = {c["claim_type"] for c in claims}
    loss = situation in LOSS_SITUATIONS
    t = norm["text"]
    # RC change CH-03: the free-text 'already paid' regex that used to sit here fired on negated statements ('I have not paid').
    # Loss inference from free text now lives in saathi_rc.cues (negation-aware) and is decided BEFORE this function is called.
    acts = []
    if loss:
        acts += LOSS_REQUIRED
    if inds or cts - {"PERFORMANCE_CLAIM", "MARKET_PREDICTION"}:
        if posture in ("HIGH_CONCERN", "SOME_CONCERN") or abstained and inds:
            acts.append("A_NO_PAY_NO_SHARE")
    if "REMOTE_ACCESS_APP" in inds:
        acts.append("A_NO_REMOTE")
    if "SEBI_REG_CLAIM" in cts or norm["entities"]["reg_numbers"]:
        acts.append("A_VERIFY_REG")
    if "PERSONAL_PAYEE" in inds:
        acts.append("A_SEBI_CHECK_PAYEE")
    if inds & {"CREDENTIAL_REQUEST", "AUTHORITY_IMPERSONATION"} or {"UNSOLICITED_CONTACT", "PAYMENT_DEMAND"} <= inds or cts & {"ACCOUNT_BLOCK_KYC", "AUTHORITY_THREAT", "BANK_ASKS_OTP_CLAIM"}:
        acts.append("A_OFFICIAL_CALLBACK")
    if "GROUP_INVITE" in inds:
        acts.append("A_AVOID_GROUPS")
    if posture == "HIGH_CONCERN" and (norm["entities"]["urls"] or norm["entities"]["vpas"] or norm["entities"]["phones"]):
        acts.append("A_REPORT_SUSPECT")
        if not loss:
            acts.append("A_CHAKSHU")
    if cts & {"CHAKSHU_SCOPE_CLAIM", "SCORES_SCOPE_CLAIM"} and not loss:
        acts.append("A_CALL_1930_COND")
    if not acts and not abstained:
        acts.append("A_OFFICIAL_CALLBACK")
    seen, out = set(), []
    for a in sorted(set(acts), key=lambda x: ORDER.index(x) if x in ORDER else 99):
        out.append(a)
    return out, loss
