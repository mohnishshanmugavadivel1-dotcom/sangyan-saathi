# -*- coding: utf-8 -*-
"""Regression tests for the defects confirmed by the S3 adversarial run (see results/s3/FAILURE_ANALYSIS.md).
Each fix is tested on the S3 case that exposed it AND on differently worded variants, plus negative tests so the fix does not widen into new misses.
These are regression tests written by the engine's author, not independent validation. Clock pinned. No network."""
import copy, json, os, sys, threading, unittest, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); RC = os.path.abspath(os.path.join(HERE, "..")); sys.path.insert(0, RC); sys.path.insert(0, HERE); sys.dont_write_bytecode = True
from saathi_rc import clock
from saathi_rc.engine import analyze
from saathi_rc.contract import UNAVAILABLE_TEXT
from saathi_rc.cues import credential_request
from saathi_rc.validate import validate
from saathi_rc.web import app as webapp


class Frozen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._c = clock.frozen("2026-10-03"); cls._c.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._c.__exit__(None, None, None)

    def run_(self, sit, text, lang="en"):
        return analyze({"situation": sit, "text": text, "output_language": lang})

    def uids(self, r): return [a["action_id"] for a in r["urgent_steps"]]


class TestFix1PendingNeverLosesStopPayment(Frozen):
    """S3 D09/D18: PAYMENT_PENDING + a past-tense cue ('the account they gave me') produced ASK_FOLLOWUP with no stop-payment step."""
    TEXTS = ["I am about to pay Rs 30,000 to the account they gave me, they said the profit will be released after that.",   # S3 D09
             "I already paid yesterday, they are now asking for a release charge.",                                        # S3 D18
             "The number they sent me is for a 12000 deposit; I'm going to transfer it tonight.",
             "He told me to wire the fee, I paid half before. Now I plan to pay the rest.",
             "मैंने पहले कुछ भेजा था और अब बाकी भेजने वाला हूँ", "bhej diya tha pehle, ab phir bhejne wala hoon"]

    def test_stop_payment_first_for_every_pending_text(self):
        for t in self.TEXTS:
            r = self.run_("PAYMENT_PENDING", t)
            self.assertEqual(self.uids(r)[:1], ["A_STOP_PAYMENT"], (t, r["posture"]))

    def test_ask_followup_with_pending_keeps_questions_and_conditional_steps(self):
        # S4 amendment: TEXTS[0] ("the account they gave me") used to trigger ASK only through a false conflict (the verb 'gave' belongs to the sender); it now
        # gets normal analysis with the stop-payment step (covered by test_stop_payment_first_for_every_pending_text). The ASK path is tested on a text with a real conflict.
        r = self.run_("PAYMENT_PENDING", "I clicked the link and now I am about to pay Rs 30,000 to the account they gave me.")
        self.assertEqual(r["posture"], "ASK_FOLLOWUP"); self.assertTrue(r["questions"]); self.assertIn("A_CALL_1930", [a["action_id"] for a in r["steps"]])
        self.assertFalse(r["validation_failed"] if "validation_failed" in r else r["provenance"]["validation_failed"])

    def test_other_situations_do_not_gain_a_stop_payment_block(self):
        # S4 amendment: TEXTS[1] ("I already paid yesterday, they are now asking for a release charge") is now a text escalation (ESCALATE with bank + 1930 first); the original
        # point of the test, that a non-pending situation never gains a stop-payment block, is unchanged. The ASK-with-no-urgent-block case uses a text with an unexplained cue.
        r = self.run_("NO_ACTION_YET", self.TEXTS[1]); self.assertEqual(r["posture"], "ESCALATE"); self.assertNotIn("A_STOP_PAYMENT", self.uids(r))
        r = self.run_("NO_ACTION_YET", "I clicked the link and gave my details to the form."); self.assertEqual(r["posture"], "ASK_FOLLOWUP"); self.assertEqual(self.uids(r), [])
        self.assertEqual(self.uids(self.run_("UNSURE", "")), [])

    def test_validator_now_rejects_ask_followup_without_stop_payment_for_pending(self):
        from saathi_rc.engine import get_corpus_rc
        good = self.run_("PAYMENT_PENDING", self.TEXTS[0]); corpus = get_corpus_rc()
        self.assertEqual(validate(good, corpus, {"pending": False}), [])
        bad = copy.deepcopy(good); bad["urgent_steps"] = []
        self.assertTrue([v for v in validate(bad, corpus, {"pending": False}) if "stop-payment" in v])
        bad2 = copy.deepcopy(good); bad2["urgent_steps"] = bad2["urgent_steps"][:0] + [{"action_id": "A_CONTACT_BANK", "text": "x", "sources": [], "conditional": False, "urgent": True}]
        self.assertTrue([v for v in validate(bad2, corpus, {"pending": False}) if "stop-payment" in v])


class TestFix2LanguageDisclosure(Frozen):
    """S3 G02/G10/G11/G12/G14: an unavailable output language silently produced English; mixed-script Marathi got no limited-language notice."""
    def test_unavailable_output_language_is_announced_in_every_posture(self):
        cases = [("PAID_MONEY", ""), ("UNSURE", ""), ("NO_ACTION_YET", "Guaranteed returns of 20% every month, deposit Rs 10,000 now."), ("NO_ACTION_YET", "hello"), ("PAYMENT_PENDING", "about to pay 5000"), (None, "")]
        for lang in ("mr", "ta", "bn", "fr", "xx"):
            for sit, t in cases:
                r = self.run_(sit, t, lang)
                self.assertEqual(r["language"], "en")
                self.assertIn("OUTPUT_LANGUAGE_FALLBACK", [u["code"] for u in r["unavailable"]], (lang, sit))

    def test_supported_languages_get_no_fallback_notice(self):
        for lang in ("en", "hi"):
            self.assertNotIn("OUTPUT_LANGUAGE_FALLBACK", [u["code"] for u in self.run_("PAID_MONEY", "", lang)["unavailable"]])
        self.assertNotIn("OUTPUT_LANGUAGE_FALLBACK", [u["code"] for u in analyze({"situation": "PAID_MONEY", "text": ""})["unavailable"]])   # not requested at all

    def test_texts_exist_in_both_languages_and_do_not_reassure(self):
        self.assertEqual(set(UNAVAILABLE_TEXT["en"]), set(UNAVAILABLE_TEXT["hi"]))
        self.assertTrue(UNAVAILABLE_TEXT["en"]["OUTPUT_LANGUAGE_FALLBACK"] and UNAVAILABLE_TEXT["hi"]["OUTPUT_LANGUAGE_FALLBACK"])

    def test_mixed_script_text_carries_limited_language_notice(self):
        r = self.run_("NO_ACTION_YET", "तुमचे डिमॅट खाते आज बंद होईल. KYC अपडेट करण्यासाठी त्वरित ही लिंक उघडा: http://kyc-nsdl-update.top आणि OTP सांगा.")   # S3 G02
        self.assertIn("LANGUAGE_LIMITED", [u["code"] for u in r["unavailable"]])
        r2 = self.run_("NO_ACTION_YET", "Special offer! आज ही invest करें, मुनाफ़ा पक्का, अभी जमा करें ₹5,000")
        self.assertIn("LANGUAGE_LIMITED", [u["code"] for u in r2["unavailable"]])

    def test_web_page_shows_the_notice_and_never_echoes_the_raw_value(self):
        c = clock.frozen("2026-10-03"); c.__enter__()
        try:
            srv = webapp.make_server("127.0.0.1", 0, webapp.State(mode="off")); port = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
            for lang in ("mr", "<script>x</script>", "zz"):
                data = urllib.parse.urlencode({"situation": "PAID_MONEY", "text": "", "output_language": lang}).encode()
                page = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:%d/check" % port, data=data, method="POST"), timeout=10).read().decode()
                self.assertIn("This result is shown in English", page); self.assertNotIn("<script>x", page)
            srv.shutdown(); srv.server_close()
        finally:
            c.__exit__(None, None, None)


class TestFix3HindiScriptWithLatinCredentialTerm(Frozen):
    """S3 G15: 'अपना OTP बताइए' was not recognised as a credential request because only Devanagari terms were accepted in the Devanagari-verb branch."""
    REQUESTS = ["आपका KYC अधूरा है। तुरंत अपना OTP बताइए वरना खाता ब्लॉक हो जाएगा।", "अपना PIN भेजिए", "कृपया CVV बताओ और कार्ड की जानकारी दें", "अपना password साझा करें", "ओटीपी बताइए",
                "सर, आपका खाता बंद हो जाएगा, अपना OTP भेज दीजिए",   # S3b S05 (FIX-3b: compound verb form)
                "अपना CVV बता दो", "अपना PIN बता दीजिए", "रिफंड के लिए अपना UPI PIN बताइए"]
    PROHIBITIONS = ["OTP किसी को न बताएं", "अपना OTP कभी न बताएं", "कृपया PIN साझा न करें", "बैंक आपसे OTP नहीं मांगता", "अपना password किसी को मत बताइए", "OTP किसी को न भेज दीजिए", "OTP कभी किसी को न बता दें"]

    def test_requests_are_recognised(self):
        for t in self.REQUESTS: self.assertTrue(credential_request(t), t)
        self.assertEqual(self.run_("NO_ACTION_YET", self.REQUESTS[0], "hi")["posture"], "HIGH_CONCERN")

    def test_prohibitions_are_not_requests(self):
        for t in self.PROHIBITIONS: self.assertIsNone(credential_request(t), t)
        for t in self.PROHIBITIONS[:2]:
            r = self.run_("NO_ACTION_YET", t, "hi"); self.assertNotIn("CREDENTIAL_REQUEST", [i["indicator"] for i in r["indicators"]], t)


class TestFix4NegatedBankOtpClaim(Frozen):
    """S3 C10: 'we will never call to ask for your OTP' was extracted as the claim 'bank asks for OTP' (then shown as contradicted by sources)."""
    DENIALS = ["Reminder from your bank: we will never call to ask for your PIN, password or OTP. Do not share them with anyone, even if the caller claims to be from the bank.",
               "Banks will never call you to ask for your OTP.", "The bank does not ask for an OTP over the phone."]

    def test_denials_are_not_claims(self):
        for t in self.DENIALS:
            r = self.run_("NO_ACTION_YET", t)
            self.assertNotIn("BANK_ASKS_OTP_CLAIM", [c["claim_type"] for c in r["claims"]], t)
            self.assertNotIn(r["posture"], ("HIGH_CONCERN",), t)

    def test_credential_indicator_also_honours_denial_wording(self):
        for t in ["The bank does not ask for an OTP over the phone.", "Banks won't ask you for your PIN.", "Your broker will not ask for your password on a call."]:
            r = self.run_("NO_ACTION_YET", t); self.assertNotIn("CREDENTIAL_REQUEST", [i["indicator"] for i in r["indicators"]], t)
        for t in ["We do not ask lightly, but please share your OTP now.", "The bank does not call, however you must send your OTP to this number today."]:
            r = self.run_("NO_ACTION_YET", t); self.assertIn("CREDENTIAL_REQUEST", [i["indicator"] for i in r["indicators"]], t)

    def test_the_real_claim_is_still_extracted(self):
        for t in ["Our bank will call you to ask your OTP for verification.", "Your bank may ask for the OTP, please keep it ready."]:
            r = self.run_("NO_ACTION_YET", t)
            self.assertIn("BANK_ASKS_OTP_CLAIM", [c["claim_type"] for c in r["claims"]], t)

    def test_denial_followed_by_a_request_is_still_high_concern(self):
        r = self.run_("NO_ACTION_YET", "Your bank will never ask for your OTP. To verify your account, please share your OTP now.")   # S3 F07
        self.assertEqual(r["posture"], "HIGH_CONCERN")


if __name__ == "__main__":
    unittest.main()
