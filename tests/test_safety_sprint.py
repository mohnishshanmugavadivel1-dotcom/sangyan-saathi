# -*- coding: utf-8 -*-
"""Regression tests for the 2026-10-05 safety-reliability sprint (docs/SAFETY_SPRINT_REPORT.md).
S-1: Hindi/Hinglish reports of a credential entered on an externally sourced link, a possessive credential shared, and an unauthorised debit stated in Hinglish/Hindi.
S-2: link + stated consequence + action moves CANNOT_ASSESS to SOME_CONCERN (never HIGH).
Each fix has differently worded positives AND benign / negated / future / advice counterexamples. Written by the engine's author; not independent validation. Clock pinned. No network."""
import os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); RC = os.path.abspath(os.path.join(HERE, "..")); sys.path.insert(0, RC); sys.dont_write_bytecode = True
from saathi_rc import clock
from saathi_rc.engine import analyze


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._c = clock.frozen("2026-10-03"); cls._c.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._c.__exit__(None, None, None)

    def run_(self, text, sit="NO_ACTION_YET", lang="en"):
        return analyze({"situation": sit, "text": text, "output_language": lang})

    def state(self, r):
        return (r.get("incident") or {}).get("state")

    def assertEscalates(self, text, state):
        r = self.run_(text)
        self.assertEqual(r["posture"], "ESCALATE", text)
        self.assertEqual(self.state(r), state, text)
        ids = [a["action_id"] for a in r["urgent_steps"]]
        self.assertIn("A_CONTACT_BANK", ids, text); self.assertIn("A_CALL_1930", ids, text)

    def assertNoEscalation(self, text):
        r = self.run_(text)
        self.assertNotEqual(r["posture"], "ESCALATE", text)
        self.assertNotIn(self.state(r), ("USER_SHARED_CREDENTIAL", "UNAUTHORISED_DEBIT"), text)


class S1Credential(Base):
    def test_entered_on_link(self):
        for t in ("maine apna card number aur CVV SMS ke link pe daal diya",
                  "maine link par click kiya aur password daal diya",
                  "maine whatsapp ke link pe apna OTP bhar diya",
                  "मैंने SMS के लिंक पर कार्ड नंबर डाल दिया",
                  "मैंने लिंक पर क्लिक किया और पासवर्ड डाल दिया"):
            self.assertEscalates(t, "USER_SHARED_CREDENTIAL")

    def test_possessive_share(self):
        for t in ("mera OTP unhe share kar diya", "apna password unko bata diya", "मेरा ओटीपी उन्हें बता दिया"):
            self.assertEscalates(t, "USER_SHARED_CREDENTIAL")

    def test_counterexamples_do_not_escalate(self):
        for t in ("maine OTP nahi daala SMS ke link pe",            # negation
                  "SMS link pe OTP mat daalna",                      # advice
                  "mera OTP kisi se share mat karna",                # advice
                  "agar maine link pe OTP daal diya to kya hoga",    # hypothetical
                  "maine kal link pe OTP daalne wala hoon",          # future
                  "usne kaha ki maine link pe OTP daal diya",        # reported speech
                  "unhone mera OTP share kar diya",                  # third-party subject
                  "bank ne mera OTP share kar diya",                 # third-party subject
                  "maine apna OTP merchant ki website pe daal diya", # no external-origin marker
                  "maine ATM me PIN daal diya"):                     # no external-origin marker
            self.assertNoEscalation(t)

    def test_existing_behaviour_preserved(self):
        for t in ("maine OTP bata diya", "I gave them my OTP", "I entered my card number and CVV on a page that opened from the SMS"):
            self.assertEscalates(t, "USER_SHARED_CREDENTIAL")
        self.assertEqual(self.state(self.run_("maine OTP nahi diya")), "USER_DENIES")
        self.assertEqual(self.state(self.run_("mera OTP kisi ko nahi diya")), "USER_DENIES")


class S1Debit(Base):
    def test_hinglish_unauthorised_debit(self):
        for t in ("mere account se 20000 nikal gaye bina mere bataye", "मेरे खाते से 5000 निकल गए, मुझे बताए बिना", "mere account se paise nikal gaye, maine nahi nikale"):
            self.assertEscalates(t, "UNAUTHORISED_DEBIT")

    def test_ambiguous_debit_stays_a_question(self):
        for t in ("mere account se paise kat gaye", "mere account se EMI ke paise kat gaye", "मेरे खाते से पैसे कट गए"):
            r = self.run_(t)
            self.assertEqual(r["posture"], "ASK_FOLLOWUP", t); self.assertIsNone(self.state(r), t)
        self.assertNoEscalation("maine khud mere account se paise nikale")


class S2LinkThreat(Base):
    def test_link_consequence_action(self):
        for t in ("Your electricity will be cut tonight unless you update your details through this link: http://pay-bill.top/x",
                  "Your gas connection will be disconnected today. Click http://gas-help.top to verify."):
            r = self.run_(t)
            self.assertEqual(r["posture"], "SOME_CONCERN", t)
            self.assertIn("REQUEST_PATTERN", [i["indicator"] for i in r["indicators"]])
            self.assertTrue(r["steps"]); self.assertTrue(r["limitations"])

    def test_never_high_from_this_rule(self):
        r = self.run_("Your electricity will be cut tonight unless you update your details through this link: http://pay-bill.top/x")
        self.assertNotEqual(r["posture"], "HIGH_CONCERN")

    def test_counterexamples_keep_abstaining(self):
        for t in ("Join the project meeting today, link: https://meet.google.com/abc-defg",   # urgency but no consequence
                  "Your electricity will be cut tonight. Call the office.",                  # consequence, no link
                  "Your bill is due. Click https://www.bescom.in to view.",                  # link, no consequence
                  "Hello, we offer investment opportunities, visit https://x.co"):           # link, no consequence
            self.assertEqual(self.run_(t)["posture"], "CANNOT_ASSESS", t)

    def test_unsupported_script_still_abstains(self):
        r = self.run_("আপনার বিদ্যুৎ আজ রাতে কেটে দেওয়া হবে। লিঙ্ক https://x.top")
        self.assertEqual(r["posture"], "CANNOT_ASSESS")


if __name__ == "__main__":
    unittest.main()
