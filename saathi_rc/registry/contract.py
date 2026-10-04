"""Closed vocabularies and fixed templates. Registered names are never placed into templates (separate field), so the reassurance-word
check (I6) can run over every template string."""
import re

SITUATIONS = ("NO_ACTION_YET", "PAID_MONEY", "SHARED_CREDENTIALS", "ACCESS_GRANTED", "UNSURE")
HARM = ("PAID_MONEY", "SHARED_CREDENTIALS", "ACCESS_GRANTED")
SV_STATUSES = ("CONFIRMED_IN_REGISTER", "LISTED_NAME_NOT_COMPARED", "NAME_DIFFERS", "AMBIGUOUS", "INACTIVE_IN_REGISTER", "NOT_FOUND",
               "SOURCE_STALE", "SOURCE_UNAVAILABLE", "SOURCE_ERROR", "NOT_CHECKABLE")
POSITIVE = ("CONFIRMED_IN_REGISTER", "LISTED_NAME_NOT_COMPARED")
DEFINITIVE = POSITIVE + ("NAME_DIFFERS", "INACTIVE_IN_REGISTER", "NOT_FOUND", "AMBIGUOUS")  # statements about register content
SOURCE_PROBLEM = ("SOURCE_STALE", "SOURCE_UNAVAILABLE", "SOURCE_ERROR")
NOT_CHECKABLE_REASONS = ("NO_REGISTRATION_NUMBER", "MALFORMED_NUMBER", "UNSUPPORTED_REGISTRATION_TYPE", "TOO_MANY_NUMBERS", "UNSUPPORTED_CLAIM", "NAME_TOO_GENERIC")
AMBIGUOUS_REASONS = ("NAME_ONLY", "LEGAL_FORM_DIFFERS", "NAME_SIMILAR", "PROPRIETOR_RECORD")
NOT_FOUND_REASONS = ("NUMBER_ABSENT", "NAME_ONLY_NO_HIT", "NAME_LISTED_UNDER_OTHER_NUMBER")
STALE_DAYS = 7
MAX_CANDIDATES = 5
LANGS = ("en", "hi")

# I6: words that must not appear in any generated sentence (register-sourced names are exempt: they live in separate fields)
FORBIDDEN_RE = re.compile(r"(?i)\b(safe|safely|legit|legitimate|genuine|trustworthy|trusted|authentic|approved|recommend(ed)?|guarantee[sd]?|verified|no risk|looks fine|all good)\b")

CATEGORY = {"INA": {"en": "Investment Advisers", "hi": "निवेश सलाहकारों"}, "INH": {"en": "Research Analysts", "hi": "रिसर्च एनालिस्ट"}}

_LIST_ONLY_EN = ("This is only a list check. It says nothing about who contacted you, or about any offer, return figure, app, link or payment account.")
_LIST_ONLY_HI = ("यह केवल सूची की जाँच है। इससे यह पता नहीं चलता कि आपसे संपर्क करने वाला कौन है, या कोई ऑफ़र, रिटर्न, ऐप, लिंक या भुगतान खाता कैसा है।")

T = {
 "en": {
  "CONFIRMED_IN_REGISTER": dict(h="Listed on SEBI's register under this name",
      m="On {as_of}, SEBI's current list of {category} has one entry with this registration number and this name (see the register record below).", n=_LIST_ONLY_EN),
  "LISTED_NAME_NOT_COMPARED": dict(h="This number is on SEBI's register: compare the name",
      m="On {as_of}, SEBI's current list of {category} has one entry with this number. No name was given, so nothing was compared. The registered name is shown below.",
      n=_LIST_ONLY_EN + " If the name used by the sender differs from the registered name, treat the claim as unconfirmed."),
  "NAME_DIFFERS": dict(h="This number is listed under a different name",
      m="On {as_of}, SEBI's current list of {category} has this number, registered under a name that does not match the name you gave (see below).",
      n="This is not proof of wrongdoing, because a business may use a trade name, and it is not a match. Ask the sender for the exact registered name and compare it yourself on sebi.gov.in."),
  "AMBIGUOUS:NAME_ONLY": dict(h="A name alone does not point to one register entry",
      m="Searching the name on SEBI's current lists gave {n} entries as of {as_of}. Anyone can use a name; a registration number is needed.",
      n="No match has been established. Ask the sender for the registration number and check it."),
  "AMBIGUOUS:LEGAL_FORM_DIFFERS": dict(h="The name is close but the legal form differs",
      m="The number is on SEBI's current list, but the registered name differs from the name you gave in its legal form (see below).",
      n="No match has been established. Compare the exact registered name with what the sender gave."),
  "AMBIGUOUS:PROPRIETOR_RECORD": dict(h="The name matches part of an individual's entry",
      m="The number is on SEBI's current list, but the registered entry is an individual trading under a business name, and the name you gave matches only one part of it (see below).",
      n="No match has been established. Compare the exact registered name with what the sender gave."),
  "AMBIGUOUS:NAME_SIMILAR": dict(h="The name is similar but not the same",
      m="The number is on SEBI's current list, but the registered name is similar to, not the same as, the name you gave (see below).",
      n="No match has been established. Compare the exact registered name with what the sender gave."),
  "INACTIVE_IN_REGISTER": dict(h="This number is on SEBI's list of ended or restricted registrations",
      m="SEBI's list of cancelled, surrendered, expired or suspended registrations has this number. The status shown there is in the register record below.",
      n="This list does not say what the entity is doing now. A registration that has ended or is restricted does not support the sender's claim."),
  "NOT_FOUND:NUMBER_ABSENT": dict(h="Not found in the SEBI lists searched",
      m="No entry with this number was found in SEBI's current {category} list or in its list of cancelled, surrendered, expired or suspended registrations (retrieval date {as_of}).",
      n="This does not show that the entity is unregistered, or anything else. The number may be mistyped, belong to another registration type, or be very new. Do not treat the claim as supported; check on sebi.gov.in."),
  "NOT_FOUND:NAME_LISTED_UNDER_OTHER_NUMBER": dict(h="This number was not found, but the name is listed under another number",
      m="No entry with this number was found in the lists searched (retrieval date {as_of}), while the name you gave appears on SEBI's current list under a different number.",
      n="Do not treat the claim as supported. Ask the sender for the exact registered name and number and compare them on sebi.gov.in."),
  "NOT_FOUND:NAME_ONLY_NO_HIT": dict(h="No register entry contains this name",
      m="No entry containing this name was found in SEBI's current Investment Adviser and Research Analyst lists (retrieval date {as_of}).",
      n="The business may use another legal name or be in a category not searched. Do not treat the claim as supported; ask for the registration number."),
  "SOURCE_STALE": dict(h="SEBI's data may be out of date: no result given",
      m="The register data available is older than 7 days or shows no date, so no result is given for this claim.", n="No conclusion can be drawn about this claim. Check on sebi.gov.in."),
  "SOURCE_UNAVAILABLE": dict(h="Could not reach SEBI's register: no result given",
      m="SEBI's website did not answer in time.", n="No conclusion can be drawn about this claim. Try again later or check on sebi.gov.in."),
  "SOURCE_ERROR": dict(h="SEBI's page gave an unexpected answer: no result given",
      m="The answer from SEBI's website did not have the expected form, so it was not used.", n="No conclusion can be drawn about this claim. Check on sebi.gov.in."),
  "NOT_CHECKABLE:NO_REGISTRATION_NUMBER": dict(h="This claim cannot be checked without a registration number",
      m="No registration number was entered or found in the pasted text.", n="A statement that someone is registered cannot be checked here without a number."),
  "NOT_CHECKABLE:MALFORMED_NUMBER": dict(h="The number is not in a form this check accepts",
      m="Accepted form: INA or INH followed by 9 digits. The number was not corrected or guessed.", n="Re-read the number exactly as the sender wrote it."),
  "NOT_CHECKABLE:UNSUPPORTED_REGISTRATION_TYPE": dict(h="This number type is outside this check",
      m="This check covers only Investment Adviser (INA) and Research Analyst (INH) numbers.", n="Other registration types can be searched on sebi.gov.in."),
  "NOT_CHECKABLE:TOO_MANY_NUMBERS": dict(h="More than one number was found",
      m="Enter the single number you want checked.", n="Nothing was checked."),
  "NOT_CHECKABLE:UNSUPPORTED_CLAIM": dict(h="This kind of claim cannot be checked here",
      m="Only a registration number (and name) can be compared with SEBI's lists.", n="General statements about status, awards, endorsements or ratings are not checked."),
  "NOT_CHECKABLE:NAME_TOO_GENERIC": dict(h="The name is too short or general to search",
      m="A name needs at least two words and five letters to be searched.", n="Nothing was checked. A registration number is the better thing to enter."),
 },
 "hi": {
  "CONFIRMED_IN_REGISTER": dict(h="सेबी के रजिस्टर में इसी नाम से सूचीबद्ध",
      m="{as_of} को सेबी की {category} की मौजूदा सूची में इस पंजीकरण संख्या और इसी नाम की एक प्रविष्टि है (नीचे रजिस्टर रिकॉर्ड देखें)।", n=_LIST_ONLY_HI),
  "LISTED_NAME_NOT_COMPARED": dict(h="यह संख्या सेबी के रजिस्टर में है: नाम मिलाकर देखें",
      m="{as_of} को सेबी की {category} की मौजूदा सूची में इस संख्या की एक प्रविष्टि है। कोई नाम नहीं दिया गया, इसलिए कुछ मिलाया नहीं गया। पंजीकृत नाम नीचे है।",
      n=_LIST_ONLY_HI + " यदि भेजने वाले का बताया नाम पंजीकृत नाम से अलग है, तो दावे को अपुष्ट मानें।"),
  "NAME_DIFFERS": dict(h="यह संख्या किसी दूसरे नाम से सूचीबद्ध है",
      m="{as_of} को सेबी की {category} की मौजूदा सूची में यह संख्या ऐसे नाम से दर्ज है जो आपके दिए नाम से मेल नहीं खाता (नीचे देखें)।",
      n="यह गड़बड़ी का सबूत नहीं है, क्योंकि कारोबार किसी व्यापारिक नाम का उपयोग कर सकता है, पर यह मिलान भी नहीं है। भेजने वाले से सटीक पंजीकृत नाम पूछकर sebi.gov.in पर खुद मिलाएँ।"),
  "AMBIGUOUS:NAME_ONLY": dict(h="केवल नाम से एक प्रविष्टि तय नहीं होती",
      m="{as_of} तक सेबी की मौजूदा सूचियों में इस नाम की {n} प्रविष्टियाँ मिलीं। नाम कोई भी इस्तेमाल कर सकता है; पंजीकरण संख्या ज़रूरी है।",
      n="कोई मिलान स्थापित नहीं हुआ। भेजने वाले से पंजीकरण संख्या माँगकर जाँचें।"),
  "AMBIGUOUS:LEGAL_FORM_DIFFERS": dict(h="नाम मिलता-जुलता है पर कानूनी रूप अलग है",
      m="संख्या सेबी की मौजूदा सूची में है, पर पंजीकृत नाम का कानूनी रूप आपके दिए नाम से अलग है (नीचे देखें)।",
      n="कोई मिलान स्थापित नहीं हुआ। पंजीकृत नाम को भेजने वाले के बताए नाम से ध्यान से मिलाएँ।"),
  "AMBIGUOUS:PROPRIETOR_RECORD": dict(h="नाम किसी व्यक्ति की प्रविष्टि के एक हिस्से से मिलता है",
      m="संख्या सेबी की मौजूदा सूची में है, पर पंजीकृत प्रविष्टि किसी व्यक्ति की है जो व्यावसायिक नाम से काम करता है, और आपका दिया नाम उसके केवल एक हिस्से से मिलता है (नीचे देखें)।",
      n="कोई मिलान स्थापित नहीं हुआ। पंजीकृत नाम को भेजने वाले के बताए नाम से ध्यान से मिलाएँ।"),
  "AMBIGUOUS:NAME_SIMILAR": dict(h="नाम मिलता-जुलता है, वही नहीं",
      m="संख्या सेबी की मौजूदा सूची में है, पर पंजीकृत नाम आपके दिए नाम जैसा है, वही नहीं (नीचे देखें)।",
      n="कोई मिलान स्थापित नहीं हुआ। पंजीकृत नाम को भेजने वाले के बताए नाम से ध्यान से मिलाएँ।"),
  "INACTIVE_IN_REGISTER": dict(h="यह संख्या सेबी की समाप्त या प्रतिबंधित पंजीकरणों की सूची में है",
      m="सेबी की रद्द, समर्पित, समाप्त या निलंबित पंजीकरणों की सूची में यह संख्या है। वहाँ दिखी स्थिति नीचे रजिस्टर रिकॉर्ड में है।",
      n="यह सूची नहीं बताती कि संस्था अब क्या कर रही है। समाप्त या प्रतिबंधित पंजीकरण भेजने वाले के दावे का समर्थन नहीं करता।"),
  "NOT_FOUND:NUMBER_ABSENT": dict(h="खोजी गई सेबी सूचियों में नहीं मिला",
      m="सेबी की {category} की मौजूदा सूची या रद्द, समर्पित, समाप्त या निलंबित पंजीकरणों की सूची में इस संख्या की कोई प्रविष्टि नहीं मिली (प्राप्ति तिथि {as_of})।",
      n="इससे यह सिद्ध नहीं होता कि संस्था अपंजीकृत है या कुछ और। संख्या गलत लिखी हो सकती है, किसी और प्रकार की हो सकती है, या बहुत नई हो सकती है। दावे को समर्थित न मानें; sebi.gov.in पर जाँचें।"),
  "NOT_FOUND:NAME_LISTED_UNDER_OTHER_NUMBER": dict(h="यह संख्या नहीं मिली, पर नाम किसी और संख्या से सूचीबद्ध है",
      m="खोजी गई सूचियों में यह संख्या नहीं मिली (प्राप्ति तिथि {as_of}), जबकि आपका दिया नाम सेबी की मौजूदा सूची में किसी दूसरी संख्या से दर्ज है।",
      n="दावे को समर्थित न मानें। भेजने वाले से सटीक पंजीकृत नाम और संख्या पूछकर sebi.gov.in पर मिलाएँ।"),
  "NOT_FOUND:NAME_ONLY_NO_HIT": dict(h="किसी रजिस्टर प्रविष्टि में यह नाम नहीं है",
      m="सेबी की निवेश सलाहकार और रिसर्च एनालिस्ट की मौजूदा सूचियों में इस नाम वाली कोई प्रविष्टि नहीं मिली (प्राप्ति तिथि {as_of})।",
      n="कारोबार किसी और कानूनी नाम का उपयोग कर सकता है या ऐसी श्रेणी में हो सकता है जो नहीं खोजी गई। दावे को समर्थित न मानें; पंजीकरण संख्या माँगें।"),
  "SOURCE_STALE": dict(h="सेबी का डेटा पुराना हो सकता है: कोई परिणाम नहीं",
      m="उपलब्ध रजिस्टर डेटा 7 दिन से पुराना है या उस पर तारीख नहीं है, इसलिए इस दावे पर कोई परिणाम नहीं दिया गया।", n="इस दावे पर कोई निष्कर्ष नहीं निकाला जा सकता। sebi.gov.in पर जाँचें।"),
  "SOURCE_UNAVAILABLE": dict(h="सेबी का रजिस्टर नहीं खुल सका: कोई परिणाम नहीं",
      m="सेबी की वेबसाइट समय पर नहीं चली।", n="इस दावे पर कोई निष्कर्ष नहीं निकाला जा सकता। बाद में फिर कोशिश करें या sebi.gov.in पर जाँचें।"),
  "SOURCE_ERROR": dict(h="सेबी के पेज से अनपेक्षित उत्तर मिला: कोई परिणाम नहीं",
      m="सेबी की वेबसाइट का उत्तर अपेक्षित रूप में नहीं था, इसलिए उसका उपयोग नहीं किया गया।", n="इस दावे पर कोई निष्कर्ष नहीं निकाला जा सकता। sebi.gov.in पर जाँचें।"),
  "NOT_CHECKABLE:NO_REGISTRATION_NUMBER": dict(h="पंजीकरण संख्या के बिना यह दावा जाँचा नहीं जा सकता",
      m="कोई पंजीकरण संख्या दर्ज नहीं हुई या चिपकाए गए पाठ में नहीं मिली।", n="किसी के पंजीकृत होने का कथन संख्या के बिना यहाँ जाँचा नहीं जा सकता।"),
  "NOT_CHECKABLE:MALFORMED_NUMBER": dict(h="संख्या ऐसे रूप में नहीं है जो यह जाँच स्वीकार करती है",
      m="स्वीकृत रूप: INA या INH के बाद 9 अंक। संख्या को न सुधारा गया, न अनुमान लगाया गया।", n="संख्या को ठीक वैसे दोबारा पढ़ें जैसी भेजने वाले ने लिखी है।"),
  "NOT_CHECKABLE:UNSUPPORTED_REGISTRATION_TYPE": dict(h="यह संख्या-प्रकार इस जाँच के बाहर है",
      m="यह जाँच केवल निवेश सलाहकार (INA) और रिसर्च एनालिस्ट (INH) संख्याओं के लिए है।", n="अन्य पंजीकरण प्रकार sebi.gov.in पर खोजे जा सकते हैं।"),
  "NOT_CHECKABLE:TOO_MANY_NUMBERS": dict(h="एक से अधिक संख्याएँ मिलीं", m="जो एक संख्या जाँचनी है वही दर्ज करें।", n="कुछ भी जाँचा नहीं गया।"),
  "NOT_CHECKABLE:UNSUPPORTED_CLAIM": dict(h="इस प्रकार का दावा यहाँ नहीं जाँचा जा सकता",
      m="केवल पंजीकरण संख्या (और नाम) को सेबी की सूचियों से मिलाया जा सकता है।", n="स्थिति, पुरस्कार, समर्थन या रेटिंग के सामान्य कथन नहीं जाँचे जाते।"),
  "NOT_CHECKABLE:NAME_TOO_GENERIC": dict(h="नाम खोज के लिए बहुत छोटा या सामान्य है",
      m="खोज के लिए नाम में कम से कम दो शब्द और पाँच अक्षर चाहिए।", n="कुछ भी जाँचा नहीं गया। पंजीकरण संख्या दर्ज करना बेहतर है।"),
 },
}

MESSAGE_ASSESSMENT = {"en": "No assessment of the message, offer, returns, link, app or payee was made.",
                      "hi": "संदेश, ऑफ़र, रिटर्न, लिंक, ऐप या भुगतान पाने वाले का कोई आकलन नहीं किया गया।"}
NOT_CHECKED = {"en": ["The content or wording of the message or offer", "Return figures or promises", "Links, apps and websites", "Payment accounts and UPI IDs (SEBI Check is SEBI's tool for these)",
                      "Whether the person contacting you is who they say they are", "Whether any product or entity suits you"],
               "hi": ["संदेश या ऑफ़र की सामग्री या शब्दावली", "रिटर्न के आँकड़े या वादे", "लिंक, ऐप और वेबसाइट", "भुगतान खाते और UPI आईडी (इनके लिए सेबी का साधन SEBI Check है)",
                      "क्या आपसे संपर्क करने वाला वही है जो वह बताता है", "क्या कोई उत्पाद या संस्था आपके लिए उपयुक्त है"]}
OFFICIAL_CHECK = {"en": "To check yourself: sebi.gov.in > Intermediaries / Market Infrastructure Institutions > Recognised Intermediaries.",
                  "hi": "खुद जाँचने के लिए: sebi.gov.in > Intermediaries / Market Infrastructure Institutions > Recognised Intermediaries।"}
LIMITS = {"en": ["Hindi text in this tool has not been reviewed by a native speaker.", "This tool checks one list entry; it is not a fraud check."],
          "hi": ["इस साधन का हिंदी पाठ किसी मातृभाषी द्वारा जाँचा नहीं गया है।", "यह साधन रजिस्टर की एक प्रविष्टि जाँचता है; यह धोखाधड़ी की जाँच नहीं है।"]}
QUESTIONS = {"en": ["Have you sent money to anyone because of this message or call?", "Have you shared an OTP, PIN, password or card details?",
                    "Have you installed an app or allowed screen sharing at someone's request?"],
             "hi": ["क्या आपने इस संदेश या कॉल के कारण किसी को पैसे भेजे हैं?", "क्या आपने OTP, पिन, पासवर्ड या कार्ड की जानकारी साझा की है?",
                    "क्या आपने किसी के कहने पर कोई ऐप इंस्टॉल किया है या स्क्रीन साझा करने दी है?"]}
COND_PREFIX = {"en": "If you answered yes to any question: ", "hi": "यदि आपने किसी भी प्रश्न का उत्तर हाँ दिया: "}
SOURCE_INFO = {"name": "SEBI Recognised Intermediaries (sebi.gov.in)", "url_current": "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes",
               "url_inactive": "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpiFilter2=yes"}
