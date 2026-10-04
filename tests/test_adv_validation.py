# -*- coding: utf-8 -*-
"""Regression tests for the two changes taken from the 2026-10-05 adversarial validation (docs/ADVERSARIAL_VALIDATION_NOTE.md):
P1 the S-2 consequence wording no longer includes plain expiry/lapse/cancellation (routine reminders with renewal links matched it);
P3 the dative pronoun 'unhe' (to them) is the RECIPIENT, not a third-party subject ("maine unhe OTP bhej diya" is the user's own share).
Each has positives and counterexamples. Written by the engine's author after seeing ADV-1; ADV-2 (held out) was run once on the prototype. Not independent validation."""
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

    def run_(self, text):
        return analyze({"situation": "NO_ACTION_YET", "text": text, "output_language": "en"})


class P3DativeRecipient(Base):
    def test_unhe_recipient_is_user_share(self):
        for t in ("maine unhe apna OTP bata diya", "maine unhe pin bhej diya", "mene unhe card number aur cvv bhej diya", "maine unhe apna CVV bhej diya"):
            r = self.run_(t)
            self.assertEqual(r["posture"], "ESCALATE", t)
            self.assertEqual(r["incident"]["state"], "USER_SHARED_CREDENTIAL", t)
            ids = [a["action_id"] for a in r["urgent_steps"]]
            self.assertIn("A_CONTACT_BANK", ids, t); self.assertIn("A_CALL_1930", ids, t)

    def test_negated_refused_or_third_party_does_not_escalate(self):
        for t in ("maine unhe OTP nahi bheja", "maine unhe OTP bhejne se mana kar diya", "unhe OTP bhejne ko bola gaya, maine nahi bheja", "bank ne unhe OTP bheja"):
            r = self.run_(t)
            self.assertNotEqual(r["posture"], "ESCALATE", t)
            self.assertNotEqual((r.get("incident") or {}).get("state"), "USER_SHARED_CREDENTIAL", t)


class P1ExpiryReminders(Base):
    def test_routine_expiry_reminders_are_not_flagged(self):
        for t in ("Your broadband plan expires on 12 Oct. Recharge via https://www.myjio.com/recharge.",
                  "Your gym membership expires on 31 Oct. Renew here: https://fitclub.example.com/renew",
                  "Aapki policy expire hone wali hai, renew karein: https://licindia.in",
                  "Your appointment will be cancelled if not confirmed by 6 pm. Confirm at https://clinic.example/confirm"):
            self.assertEqual(self.run_(t)["posture"], "CANNOT_ASSESS", t)

    def test_cut_block_suspend_threats_are_still_flagged_never_high(self):
        for t in ("Your electricity will be cut tonight unless you update your details through this link: http://power-bill-now.xyz",
                  "Gas supply will be cut within 3 hours. Click http://gas-line.xyz to confirm your consumer number",
                  "Your wallet is frozen. Tap http://wallet-unfreeze.top to restore access"):
            r = self.run_(t)
            self.assertEqual(r["posture"], "SOME_CONCERN", t)
            self.assertTrue(r["steps"])

    def test_outage_notice_without_requested_action_is_not_flagged(self):
        self.assertEqual(self.run_("Scheduled maintenance: power will be cut tomorrow 10 am to 2 pm in your area. Details at https://discom.example.in/outage")["posture"], "CANNOT_ASSESS")


if __name__ == "__main__":
    unittest.main()
