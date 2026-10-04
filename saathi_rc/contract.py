"""Closed vocabularies and fixed texts (English + Hindi). Hindi is author-translated and has NOT been reviewed by a native speaker or domain expert
(disclosed in every Hindi response). Claim explanations from the evidence layer remain English (disclosed)."""
import re
from .core.actions import ACTIONS as CORE_ACTIONS

SITUATIONS = ("NO_ACTION_YET", "PAYMENT_PENDING", "PAID_MONEY", "SHARED_CREDENTIALS", "ACCESS_GRANTED", "UNSURE")
HARM = ("PAID_MONEY", "SHARED_CREDENTIALS", "ACCESS_GRANTED")
LANGS = ("en", "hi")
POSTURES = ("NEEDS_SITUATION", "ESCALATE", "ASK_FOLLOWUP", "HIGH_CONCERN", "SOME_CONCERN", "CANNOT_ASSESS", "ABSTAIN")
# There is deliberately NO posture that means "no problem found". See docs/01 section 6.
SEVERITY = {"ABSTAIN": 0, "CANNOT_ASSESS": 1, "SOME_CONCERN": 2, "HIGH_CONCERN": 3, "ASK_FOLLOWUP": 4, "ESCALATE": 5, "NEEDS_SITUATION": 0}
ASSESS_POSTURES = ("HIGH_CONCERN", "SOME_CONCERN", "CANNOT_ASSESS", "ABSTAIN")
CLAIM_STATES = ("SUPPORTED", "CONTRADICTED", "MIXED", "INSUFFICIENT", "NOT_ASSESSED")

SITUATION_QUESTION = {"en": "What has already happened?", "hi": "अब तक क्या हुआ है?"}
SITUATION_OPTIONS = {
    "NO_ACTION_YET": {"en": "I only received it. I have not paid, shared a code or password, clicked, or installed anything.",
                      "hi": "मुझे बस यह मिला है। मैंने कुछ भेजा, कोई कोड या पासवर्ड साझा, क्लिक या इंस्टॉल नहीं किया है।"},
    "PAYMENT_PENDING": {"en": "I am about to pay, or I have been asked to pay right now.", "hi": "मैं अभी भुगतान करने वाला/वाली हूँ, या मुझसे अभी भुगतान करने को कहा गया है।"},
    "PAID_MONEY": {"en": "I already sent money, or money has left my account.", "hi": "मैंने पैसे भेज दिए हैं, या मेरे खाते से पैसे निकल गए हैं।"},
    "SHARED_CREDENTIALS": {"en": "I shared an OTP, PIN, password, card or login details.", "hi": "मैंने OTP, पिन, पासवर्ड, कार्ड या लॉगिन जानकारी साझा की है।"},
    "ACCESS_GRANTED": {"en": "I clicked a link, opened a file, installed an app, or let someone control my phone or computer.",
                       "hi": "मैंने लिंक पर क्लिक किया, फ़ाइल खोली, ऐप इंस्टॉल किया, या किसी को अपना फ़ोन या कंप्यूटर चलाने दिया।"},
    "UNSURE": {"en": "I am not sure, I do not remember, or this is about someone else.", "hi": "मुझे पक्का पता नहीं, याद नहीं, या यह किसी और के बारे में है।"},
}
# S4 incident-state texts (Hindi is author-translated and NOT reviewed by a fluent speaker; disclosed in every Hindi response)
INCIDENT_STATES = ("USER_PAID", "USER_SHARED_CREDENTIAL", "UNAUTHORISED_DEBIT", "USER_PAYMENT_PENDING", "PAYMENT_UNCLEAR", "THIRD_PARTY_PAID", "SENDER_CLAIMS_PAYMENT", "USER_DENIES", "NO_INCIDENT")
INCIDENT_LABEL = {
    "USER_PAID": {"en": "Your text says you made a payment.", "hi": "आपके पाठ के अनुसार आपने भुगतान किया है।"},
    "USER_SHARED_CREDENTIAL": {"en": "Your text says you shared a code, PIN, password, or card or login detail.", "hi": "आपके पाठ के अनुसार आपने कोई कोड, पिन, पासवर्ड, या कार्ड या लॉगिन जानकारी साझा की है।"},
    "UNAUTHORISED_DEBIT": {"en": "Your text says money left your account and you did not make or recognise it.", "hi": "आपके पाठ के अनुसार आपके खाते से पैसे गए हैं और यह आपने नहीं किया या आप इसे पहचानते नहीं।"},
    "USER_PAYMENT_PENDING": {"en": "Your text says you are about to pay, or are being asked to pay.", "hi": "आपके पाठ के अनुसार आप भुगतान करने वाले हैं, या आपसे भुगतान करने को कहा जा रहा है।"},
    "PAYMENT_UNCLEAR": {"en": "Your text does not make clear whether money or a code has already been sent.", "hi": "आपके पाठ से साफ़ नहीं है कि पैसे या कोड पहले ही भेजे जा चुके हैं या नहीं।"},
    "THIRD_PARTY_PAID": {"en": "Your text says someone else made a payment. It is not treated as your payment.", "hi": "आपके पाठ के अनुसार किसी और ने भुगतान किया है। इसे आपका भुगतान नहीं माना गया है।"},
    "SENDER_CLAIMS_PAYMENT": {"en": "Your text says someone claims a payment was made. This is a claim, not treated as something you did.", "hi": "आपके पाठ के अनुसार कोई कह रहा है कि भुगतान हुआ है। यह सिर्फ़ एक दावा है, इसे आपका किया हुआ नहीं माना गया है।"},
    "USER_DENIES": {"en": "Your text says you did not pay or share anything. This is taken as you wrote it.", "hi": "आपके पाठ के अनुसार आपने कुछ नहीं भेजा या साझा नहीं किया। इसे वैसे ही माना गया है जैसा आपने लिखा।"},
    "NO_INCIDENT": {"en": "Your text does not say that you paid or shared anything.", "hi": "आपके पाठ में यह नहीं लिखा कि आपने कुछ भेजा या साझा किया।"},
}
# Sprint Oct-4: shown instead of the PAYMENT_UNCLEAR label when a subject-less completed payment appears together with explicit risk context. The Hindi string is machine-authored and NOT reviewed by a fluent speaker.
SUBJECTLESS_LABEL = {"en": "Your text describes a payment but does not say who made it. Because it also describes a risk (listed below), the urgent steps are shown first.",
                     "hi": "आपके पाठ में एक भुगतान का ज़िक्र है पर यह नहीं लिखा कि किसने किया। साथ ही इसमें नीचे बताया गया जोखिम भी है, इसलिए ज़रूरी कदम पहले दिखाए गए हैं।"}
INCIDENT_NOTE = {
    "escalated_from_text": {"en": "You did not choose an option for this, but your text says it, so the steps for money or access that may already be lost are shown first. This reading is a pattern match on your wording, not certain. If it is wrong, change the text or the choice below and check again.",
                            "hi": "आपने इसके लिए कोई विकल्प नहीं चुना, पर आपके पाठ में यह लिखा है, इसलिए पैसे या खाते की पहुँच खो जाने की स्थिति के कदम सबसे पहले दिखाए गए हैं। यह आपके शब्दों का पैटर्न-मिलान है, पक्का नहीं। गलत हो तो पाठ या नीचे का विकल्प बदलकर फिर जाँचें।"},
    "follow_up": {"en": "This reading is a pattern match on your wording, not certain. The question below decides what to do next; the steps shown as conditional apply only if the answer is yes.",
                  "hi": "यह आपके शब्दों का पैटर्न-मिलान है, पक्का नहीं। नीचे का सवाल तय करेगा कि आगे क्या करना है; शर्त वाले कदम तभी लागू होते हैं जब जवाब हाँ हो।"},
    "analysis": {"en": "This reading is a pattern match on your wording, not certain. If it is wrong, change the text or the choice and check again.", "hi": "यह आपके शब्दों का पैटर्न-मिलान है, पक्का नहीं। गलत हो तो पाठ या विकल्प बदलकर फिर जाँचें।"},
    "form": {"en": "This comes from the option you chose, not from reading your text.", "hi": "यह आपके चुने विकल्प से आया है, पाठ पढ़कर नहीं।"},
}
INCIDENT_CONFLICT = {"en": "You chose an option that says money, a code or access may already be lost, but your text says you did not. The option you chose was followed, because acting early costs little.",
                     "hi": "आपने ऐसा विकल्प चुना जिसमें पैसे, कोड या पहुँच पहले ही जा चुकी हो सकती है, पर आपके पाठ में लिखा है कि आपने ऐसा नहीं किया। आपके चुने विकल्प को माना गया है, क्योंकि जल्दी कदम उठाने में नुकसान कम है।"}
INCIDENT_QUESTIONS = {
    "paid_unconfirmed": {"en": "Your text says you made a payment. Was it to someone you do not know, or because of this message, call or offer? If yes, choose \"I already sent money\" below and check again.",
                         "hi": "आपके पाठ के अनुसार आपने भुगतान किया है। क्या यह किसी अनजान व्यक्ति को था, या इस संदेश, कॉल या ऑफ़र की वजह से? यदि हाँ, तो नीचे \"मैंने पैसे भेज दिए हैं\" चुनें और फिर जाँचें।"},
    "unclear": {"en": "Please check your bank or UPI app's transaction history now: did the money, or the code you shared, actually leave? If it did, or if you cannot tell, use the steps below.",
                "hi": "कृपया अभी अपने बैंक या UPI ऐप का लेन-देन इतिहास देखें: क्या पैसे, या आपका बताया कोड, सच में चले गए? यदि हाँ, या आप पक्का नहीं कह सकते, तो नीचे दिए कदम अपनाएँ।"},
    "third_party": {"en": "Your text describes a payment made by someone else. If it may have gone to a scammer, that person should use the steps below with their own bank. You can also check again choosing what applies to you.",
                    "hi": "आपके पाठ में किसी और के किए भुगतान का ज़िक्र है। यदि वह किसी ठग को गया हो सकता है, तो उस व्यक्ति को अपने बैंक के साथ नीचे दिए कदम अपनाने चाहिए। आप अपने लिए जो लागू हो वह चुनकर फिर जाँच भी सकते हैं।"},
}
INCIDENT_UI_HEAD = {"en": "How your text was read", "hi": "आपका पाठ कैसे पढ़ा गया"}
FOLLOWUP_QUESTIONS = {
    "en": ["Have you sent any money to this person or account?", "Have you shared an OTP, PIN, password, card or login details?",
           "Have you clicked a link, opened a file, installed an app, or let someone control your phone or computer?"],
    "hi": ["क्या आपने इस व्यक्ति या खाते को कोई पैसा भेजा है?", "क्या आपने OTP, पिन, पासवर्ड, कार्ड या लॉगिन जानकारी साझा की है?",
           "क्या आपने लिंक पर क्लिक किया, फ़ाइल खोली, ऐप इंस्टॉल किया, या किसी को अपना फ़ोन या कंप्यूटर चलाने दिया?"],
}
COND_PREFIX = {"en": "If you have already paid, shared a code or password, or clicked or installed something: ",
               "hi": "यदि आप पैसे भेज चुके हैं, कोड या पासवर्ड साझा कर चुके हैं, या कुछ क्लिक या इंस्टॉल कर चुके हैं: "}

# The conditional block ("if you have already paid ...") is three separate steps. Only the FIRST carries the full condition (COND_PREFIX); the next two
# start with COND_FOLLOW instead of repeating it. A_CALL_1930 also uses COND_TEXT inside the block, because its own "If money has already gone ..." clause
# would otherwise state a second condition in the same sentence. Before this change all three steps repeated the full prefix and the 1930 step carried both.
COND_FOLLOW = {"en": "In that case, also ", "hi": "ऐसी स्थिति में यह भी करें: "}
COND_TEXT = {"A_CALL_1930": {"en": "call 1930 (national cyber-fraud helpline) or report at cybercrime.gov.in as soon as possible.",
                             "hi": "तुरंत 1930 (राष्ट्रीय साइबर-धोखाधड़ी हेल्पलाइन) पर कॉल करें या cybercrime.gov.in पर रिपोर्ट करें।"}}

# ---- actions: core actions + two new ones (sources are existing corpus passages)
ACTIONS = dict(CORE_ACTIONS)
ACTIONS["A_STOP_PAYMENT"] = dict(sources=["SEBI-PR14-2026-b", "RBI-LIMITED-LIABILITY"],
    en="Do not complete this payment. If you have already approved it or entered your PIN, contact your bank at once through its official number or app.",
    hi="यह भुगतान पूरा न करें। यदि आप इसे मंज़ूर कर चुके हैं या पिन डाल चुके हैं, तो तुरंत बैंक के आधिकारिक नंबर या ऐप से संपर्क करें।")
ACTIONS["A_HAVE_DETAILS"] = dict(sources=["NCRP-FIN-MANUAL"],
    en="Keep these ready when you call 1930: your mobile number, the name of the bank or wallet that was debited, the account or UPI ID it was debited from, the transaction ID and date, and a screenshot of the transaction if you have one. Also useful if you know them, though the official guide does not list them: the exact amount and time, and the receiving UPI ID, account or wallet.",
    hi="1930 पर कॉल करते समय ये तैयार रखें: आपका मोबाइल नंबर, जिस बैंक या वॉलेट से पैसे कटे उसका नाम, जिस खाते या UPI आईडी से पैसे कटे वह, लेन-देन आईडी और तारीख, और लेन-देन का स्क्रीनशॉट (यदि हो)। यदि पता हो तो ये भी उपयोगी हैं, हालाँकि आधिकारिक मार्गदर्शिका में इनका उल्लेख नहीं है: सटीक राशि और समय, और पाने वाली UPI आईडी, खाता या वॉलेट।")
ESCALATION_SET = ["A_CONTACT_BANK", "A_CALL_1930", "A_PRESERVE_EVIDENCE"]
URGENT_REQUIRED = {"A_CONTACT_BANK", "A_CALL_1930"}
ESCALATE_STEPS = ["A_CONTACT_BANK", "A_CALL_1930", "A_HAVE_DETAILS", "A_PRESERVE_EVIDENCE", "A_NO_PAY_NO_SHARE"]

HEADLINE = {
    "NEEDS_SITUATION": {"en": "Before anything else, tell us what has already happened. The answer changes what you should do first.",
                        "hi": "सबसे पहले बताइए कि अब तक क्या हुआ है। इसी से तय होता है कि आपको सबसे पहले क्या करना चाहिए।"},
    "ESCALATE": {"en": "Act now. Money or access may already be at risk. Do the steps below in this order: your bank, then 1930 or cybercrime.gov.in, then keep your evidence. Official channels cannot promise that money will be returned.",
                 "hi": "अभी कदम उठाइए। पैसे या खाते की पहुँच खतरे में हो सकती है। नीचे के कदम इसी क्रम में करें: पहले आपका बैंक, फिर 1930 या cybercrime.gov.in, फिर सबूत सुरक्षित रखें। आधिकारिक माध्यम पैसे लौटने का वादा नहीं कर सकते।"},
    "ASK_FOLLOWUP": {"en": "One question first: have you already paid, shared a code or password, or clicked or installed anything? If the answer to any question below is yes, do the urgent steps in order (your bank, then 1930 or cybercrime.gov.in, then evidence), then choose that option in the form and check again.",
                     "hi": "पहले एक सवाल: क्या आप पैसे भेज चुके हैं, कोड या पासवर्ड साझा कर चुके हैं, या कुछ क्लिक या इंस्टॉल कर चुके हैं? नीचे के किसी भी सवाल का जवाब हाँ हो तो ज़रूरी कदम इसी क्रम में करें (पहले आपका बैंक, फिर 1930 या cybercrime.gov.in, फिर सबूत), फिर फ़ॉर्म में वही विकल्प चुनकर दोबारा जाँचें।"},
    "HIGH_CONCERN": {"en": "Several warning signs were found. Do not pay or share anything until you have checked this through official channels.",
                     "hi": "कई चेतावनी संकेत मिले हैं। आधिकारिक माध्यम से जाँच किए बिना कुछ भी न भेजें और कोई जानकारी साझा न करें।"},
    "SOME_CONCERN": {"en": "Some warning signs were found. Check through official channels before you act.", "hi": "कुछ चेतावनी संकेत मिले हैं। कदम उठाने से पहले आधिकारिक माध्यम से जाँच करें।"},
    "CANNOT_ASSESS": {"en": "This tool cannot tell whether this message is genuine or a scam, and it never gives a clean result. Do not act on any request in it until you have checked with the sender through a phone number or app you already have.",
                      "hi": "यह टूल नहीं बता सकता कि यह संदेश असली है या धोखाधड़ी, और यह कभी 'सब ठीक है' जैसा नतीजा नहीं देता। इसमें दिए किसी भी अनुरोध पर तब तक कुछ न करें जब तक आप भेजने वाले से उस नंबर या ऐप के ज़रिए पूछ न लें जो आपके पास पहले से है।"},
    "ABSTAIN": {"en": "This tool cannot assess this text, so it gives no assessment. That is not a sign that the text is fine. If it asks you to do anything about money or accounts, check it as described below.",
                "hi": "यह टूल इस पाठ का आकलन नहीं कर सकता, इसलिए कोई आकलन नहीं दे रहा। इसका मतलब यह नहीं कि पाठ ठीक है। यदि इसमें पैसे या खातों के बारे में कुछ करने को कहा गया है, तो नीचे बताए अनुसार जाँचें।"},
}
STATE_LABEL = {"SUPPORTED": {"en": "Supported by trusted sources (this does not verify the message)", "hi": "विश्वसनीय स्रोतों से समर्थित (इससे संदेश की पुष्टि नहीं होती)"},
               "CONTRADICTED": {"en": "Contradicted by trusted sources", "hi": "विश्वसनीय स्रोतों से विरोधाभासी"},
               "MIXED": {"en": "Mixed / partly supported", "hi": "मिश्रित / आंशिक"},
               "INSUFFICIENT": {"en": "Insufficient evidence", "hi": "अपर्याप्त प्रमाण"},
               "NOT_ASSESSED": {"en": "Not assessed", "hi": "आकलन नहीं किया गया"}}
SURFACE_PHRASE = {
    "en": {"url": "a link", "phone_number": "a phone number", "upi_id_shape": "a payment ID", "credential_terms": "a code, password or ID detail", "money_terms": "money",
           "request_verbs": "an action to take", "pressure_terms": "pressure or a deadline", "return_figures": "promised or large returns", "other_script": "text in a language this tool cannot read"},
    "hi": {"url": "एक लिंक", "phone_number": "एक फ़ोन नंबर", "upi_id_shape": "एक भुगतान आईडी", "credential_terms": "कोड, पासवर्ड या पहचान की जानकारी", "money_terms": "पैसे",
           "request_verbs": "कुछ करने का अनुरोध", "pressure_terms": "दबाव या समय-सीमा", "return_figures": "वादा किया या बड़ा रिटर्न", "other_script": "ऐसी भाषा का पाठ जिसे यह टूल पढ़ नहीं सकता"},
}
WHY = {"en": {"prefix": "Why this is not a clean result: ", "surface": "the message contains %s", "unresolved": "some findings could not be confirmed from the sources", "lang": "language support is limited",
              "none": "this tool can only recognise a limited set of warning patterns, so it cannot confirm that any message is genuine"},
       "hi": {"prefix": "यह 'सब ठीक' नतीजा क्यों नहीं है: ", "surface": "संदेश में %s है", "unresolved": "कुछ निष्कर्ष स्रोतों से पुष्ट नहीं हो सके", "lang": "भाषा का समर्थन सीमित है",
             "none": "यह टूल केवल सीमित चेतावनी-पैटर्न पहचान सकता है, इसलिए किसी भी संदेश के असली होने की पुष्टि नहीं कर सकता"}}
PAUSE_HEAD = {"en": "Pause before paying. Nothing has been lost yet; this is the moment when stopping matters most.",
              "hi": "भुगतान करने से पहले रुकिए। अभी कुछ नहीं गया है; रुकना सबसे ज़रूरी अभी ही है।"}
UNAVAILABLE_TEXT = {
    "en": {"REGISTRY_NOT_CHECKED": "A SEBI registration number appears in the text. It has not been checked against SEBI. This release offers only an optional demo checker below, which uses invented sample data and does not contact SEBI.",
           "LINK_NOT_OPENED": "Links in the message were not opened or tested.", "PAYEE_NOT_CHECKED": "Phone numbers and payment IDs in the message were not checked against any list.",
           "SOURCES_STALE": "The sources behind this tool are old, so claim results are shown as not enough evidence.", "SOURCES_AGING": "The sources behind this tool were collected some time ago; guidance may have changed.",
           "LANGUAGE_LIMITED": "Support for this language is limited: warning signs may be missed.", "LANGUAGE_UNSUPPORTED": "This language is not supported: only language-independent signs such as links can be seen.",
           "IMAGE_NOT_READ": "Images are not read. Type or paste the text of the message.",
           "OUTPUT_LANGUAGE_FALLBACK": "The language you asked for is not available. This result is shown in English; Hindi is also available."},
    "hi": {"REGISTRY_NOT_CHECKED": "पाठ में सेबी पंजीकरण संख्या है। इसे सेबी से नहीं जाँचा गया है। इस संस्करण में नीचे केवल एक वैकल्पिक डेमो जाँच है, जो काल्पनिक नमूना डेटा का उपयोग करती है और सेबी से संपर्क नहीं करती।",
           "LINK_NOT_OPENED": "संदेश के लिंक खोले या जाँचे नहीं गए।", "PAYEE_NOT_CHECKED": "संदेश के फ़ोन नंबर और भुगतान आईडी किसी सूची से नहीं मिलाए गए।",
           "SOURCES_STALE": "इस टूल के स्रोत पुराने हैं, इसलिए दावों के नतीजे 'पर्याप्त प्रमाण नहीं' दिखाए गए हैं।", "SOURCES_AGING": "इस टूल के स्रोत कुछ समय पहले जुटाए गए थे; मार्गदर्शन बदल चुका हो सकता है।",
           "LANGUAGE_LIMITED": "इस भाषा का समर्थन सीमित है: चेतावनी संकेत छूट सकते हैं।", "LANGUAGE_UNSUPPORTED": "इस भाषा का समर्थन नहीं है: केवल भाषा-निरपेक्ष संकेत, जैसे लिंक, देखे जा सकते हैं।",
           "IMAGE_NOT_READ": "चित्र नहीं पढ़े जाते। संदेश का पाठ टाइप या चिपकाएँ।",
           "OUTPUT_LANGUAGE_FALLBACK": "आपकी माँगी हुई भाषा उपलब्ध नहीं है। यह परिणाम अंग्रेज़ी में दिखाया गया है; हिंदी भी उपलब्ध है।"},
}
LIMITS = {
    "en": ["Warning signs are pattern matches, not proof of fraud. This tool recognises a limited set of patterns and checks a small fixed set of sources.",
           "This tool never says a message is genuine or safe. A message that triggers no warning is still unverified.",
           "This tool does not give investment advice, stock tips or price predictions.",
           "Your text is analysed in memory and is not stored or logged by this tool."],
    "hi": ["चेतावनी संकेत पैटर्न-मिलान हैं, धोखाधड़ी का प्रमाण नहीं। यह टूल सीमित पैटर्न पहचानता है और स्रोतों के एक छोटे निश्चित समूह से जाँचता है।",
           "यह टूल कभी नहीं कहता कि कोई संदेश असली या सुरक्षित है। जिस संदेश में कोई चेतावनी न मिले वह भी अपुष्ट ही है।",
           "यह टूल निवेश सलाह, स्टॉक टिप्स या मूल्य अनुमान नहीं देता।", "आपका पाठ केवल मेमोरी में जाँचा जाता है; इस टूल द्वारा सहेजा या लॉग नहीं किया जाता।"],
}
HI_NOTES = ["यह हिंदी पाठ किसी मातृभाषी या विशेषज्ञ द्वारा जाँचा नहीं गया है।", "दावों के स्पष्टीकरण अंग्रेज़ी में हैं।"]
LANG_LIMIT_TEXT = {"mr": "Marathi support is limited (small keyword list only); results may miss warning signs.", "ta": "Tamil support is limited (small keyword list only); results may miss warning signs.",
                   "hinglish": "Romanised Hindi (Hinglish) is handled with a small hand-written word list; results may miss warning signs."}

# Fixed sentences that contain a reassurance word only inside an explicit NEGATION. The validator removes exactly these strings (exact match)
# before looking for reassurance words, so any OTHER sentence containing such a word is rejected. Evidence quotes are not checked (they quote sources).
APPROVED_NEGATIVE = [HEADLINE["CANNOT_ASSESS"]["en"], HEADLINE["CANNOT_ASSESS"]["hi"], LIMITS["en"][1], LIMITS["hi"][1], WHY["en"]["none"], WHY["hi"]["none"]]
REASSURE_RE = re.compile(r"(?i)\b(safe|safely|legit|legitimate|genuine|trustworthy|authentic|no risk|nothing to worry|looks fine|all good|no warning signs|nothing (was )?found|no red flags?)\b|सुरक्षित(?!\s*रख)|भरोसेमंद|असली|वैध")
NO_SIGNAL_RE = re.compile(r"(?i)no (warning|red) (signs?|flags?)|nothing (in this message )?matched|no indicators|कुछ नहीं मिला")
