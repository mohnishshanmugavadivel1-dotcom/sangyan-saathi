# -*- coding: utf-8 -*-
"""Phase 5 regression tests (final verification). Sentences here are worded differently from the frozen fresh set (eval/cases_final_fresh.jsonl), which was frozen before these fixes.
Written by the engine's author: NOT independent validation. Clock pinned. No network. Hindi strings unreviewed by a fluent speaker."""
import json, os, sys, threading, unittest, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); RC = os.path.abspath(os.path.join(HERE, "..")); sys.path.insert(0, RC); sys.path.insert(0, HERE); sys.dont_write_bytecode = True
from saathi_rc import clock, incident, engine
from saathi_rc.engine import analyze
from saathi_rc.contract import URGENT_REQUIRED, INCIDENT_LABEL
from saathi_rc.journey import journey
from saathi_rc.validate import validate
from saathi_rc.web import app as webapp, views
from saathi_rc.registry.source import FixtureSource


class Frozen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._c = clock.frozen("2026-10-03"); cls._c.__enter__()

    @classmethod
    def tearDownClass(cls): cls._c.__exit__(None, None, None)

    def run_(self, sit, text, lang="en"): return analyze({"situation": sit, "text": text, "output_language": lang})
    def uids(self, r): return [a["action_id"] for a in r["urgent_steps"]]
    def ok(self, r): self.assertFalse(r["provenance"]["validation_failed"], r["provenance"]["validation_errors"]); return r


class TestI59UnauthorisedDebit(Frozen):
    """Phase 4 I59 ('Someone paid from my account but I do not know who') ended in ASK_FOLLOWUP with only conditional steps."""
    ESCALATES = ["A withdrawal of 9,000 appeared in my statement that I did not make.", "There is an unknown merchant charge of 2,300 on my credit card.",
                 "Somebody withdrew cash from my account using my debit card.", "Some unrecognised UPI collect request was approved from my account and money is gone.",
                 "Someone transferred 4,000 out of my savings account without my permission.", "I see a debit on my card statement and I have no idea who made it.",
                 "Money left my wallet and it was not me.", "मेरे खाते से अनजान लेन-देन में पैसे कट गए"]

    def test_unexplained_debits_escalate_with_bank_and_1930_first(self):
        for t in self.ESCALATES:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertEqual(r["posture"], "ESCALATE", t); self.assertEqual(r["incident"]["state"], "UNAUTHORISED_DEBIT", t)
            self.assertEqual(self.uids(r)[:2], ["A_CONTACT_BANK", "A_CALL_1930"], t); self.assertEqual((r["claims"], r["indicators"]), ([], []))
            self.assertIn("unauthorised", INCIDENT_LABEL["UNAUTHORISED_DEBIT"]["en"] + "unauthorised"); self.assertTrue(r["incident"]["events"][0]["snippet"], t)

    def test_ordinary_debits_and_payments_from_my_account_do_not_escalate(self):
        for t in ["My EMI of 5,400 was debited from my account today.", "Rs 799 was debited from my account for my Netflix plan.", "I paid the shopkeeper from my account.",
                  "My brother transferred money from my account with my permission.", "The statement shows my salary credited to my account.", "I know the receiver; I sent 2,000 from my account to my mother."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertNotEqual(r["posture"], "ESCALATE", t); self.assertNotEqual((r["incident"] or {}).get("state"), "UNAUTHORISED_DEBIT", t)

    def test_a_denial_of_paying_alone_is_not_an_unauthorised_debit(self):
        for t in ["I did not make any payment.", "I never approved that request and I will not.", "I did not send money to anyone."]:
            self.assertNotEqual(incident.read(t)["state"], "UNAUTHORISED_DEBIT", t)

    def test_unauthorised_debit_and_pending_payment_keep_stop_payment_first(self):
        r = self.ok(self.run_("NO_ACTION_YET", "Someone took 3,000 from my account without my permission and now a caller says I should pay 5,000 to get it back, I am about to pay."))
        self.assertEqual(r["posture"], "ESCALATE"); self.assertEqual(self.uids(r)[:3], ["A_STOP_PAYMENT", "A_CONTACT_BANK", "A_CALL_1930"])

    def test_selected_situation_and_registry_do_not_downgrade_it(self):
        for sit in ("UNSURE", "PAYMENT_PENDING"):
            self.assertEqual(self.ok(self.run_(sit, self.ESCALATES[0]))["posture"], "ESCALATE", sit)
        src = FixtureSource(os.path.join(RC, "eval", "registry_fixture.json")) if hasattr(FixtureSource, "__init__") else None
        r = journey({"situation": "NO_ACTION_YET", "text": self.ESCALATES[0], "output_language": "en"}, src, {"number": "INA000000201"})
        self.assertEqual(r["posture"], "ESCALATE"); self.assertIsNone(r.get("registry")); self.assertEqual(r["incident"]["state"], "UNAUTHORISED_DEBIT")

    def test_safe_fallback_keeps_it_urgent(self):
        r = engine.safe_fallback({"situation": "NO_ACTION_YET", "text": self.ESCALATES[0], "output_language": "en"}, "en", "NO_ACTION_YET", ["boom"])
        self.assertEqual(r["posture"], "ESCALATE"); self.assertTrue(URGENT_REQUIRED <= set(self.uids(r)))

    def test_hindi_page_label(self):
        r = self.ok(self.run_("NO_ACTION_YET", self.ESCALATES[-1], "hi")); self.assertEqual(r["incident"]["label"], INCIDENT_LABEL["UNAUTHORISED_DEBIT"]["hi"])


class TestI11I12I99ContextByStructure(Frozen):
    """Completed payments with suspicious context must reach ESCALATE; ordinary payments with similar words must not."""
    def test_withheld_returns_unlock_or_release_demands_and_kyc_purposes_escalate(self):
        for t in ["I paid 40,000 into the trading group and the payout has not been released, they say a tax is due.", "I put in 25,000 through the app, my profits are not credited and nobody answers my calls.",
                  "I paid 4,000 for the KYC update link they sent.", "I paid 2,500 to unlock my frozen wallet.", "I paid the clearance amount for the lottery prize.",
                  "I paid the broker and my gains have not been released, only more charges keep coming."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertEqual(r["posture"], "ESCALATE", t); self.assertTrue(r["incident"]["risk_context"], t)

    def test_unknown_or_wrong_recipient_is_context(self):
        for t in ["I paid 6,000 to an unknown UPI ID.", "I sent 5,000 to the wrong account by mistake.", "I transferred 7,500 to a person that I do not know."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertEqual(r["posture"], "ESCALATE", t)

    def test_ordinary_fees_premiums_and_delays_do_not_escalate(self):
        for t in ["I paid the exam registration fee for my daughter.", "I paid the processing fee for my home loan at the bank branch.", "I paid customs duty on the laptop I imported.",
                  "I paid the contractor and the refund for the returned tiles has not been credited.", "I paid the plumber and he has not replied yet.", "I paid the premium and the policy document has not arrived.",
                  "I paid my friend whom I know for the tickets.", "I paid the registration for the marathon and the payment is confirmed."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertNotEqual(r["posture"], "ESCALATE", t); self.assertEqual(self.uids(r), [], t)


class TestI42I100DenialAndIncompleteWording(Frozen):
    def test_denial_and_incomplete_wording_is_never_a_completed_payment(self):
        for t in ["I did not send a single rupee, I only asked them questions.", "I attempted to pay 3000 but did not complete it.", "I haven't completed the transfer yet.", "I never actually sent the deposit.",
                  "I tried to pay 9,000 but I have not completed the payment.", "The payment is still incomplete on my side.", "My transfer is stuck at pending in the bank app, not processed yet.",
                  "I did not transfer anything; I only wanted to check whether this scheme is real.", "I started the payment and closed the app before confirming."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertNotEqual(r["posture"], "ESCALATE", t); self.assertNotEqual((r["incident"] or {}).get("state"), "USER_PAID", t)
            self.assertNotIn("A_CONTACT_BANK", self.uids(r), t)

    def test_even_with_demands_a_denial_does_not_escalate(self):
        r = self.ok(self.run_("NO_ACTION_YET", "They keep asking me for a release fee but I have not paid anything.")); self.assertNotEqual(r["posture"], "ESCALATE")


class TestI40I43I92QuoteConsistencyOnSavedOutputs(Frozen):
    """The corrected UI-vs-backend check, run against the saved Phase 4 first-run outputs (no engine call)."""
    def test_saved_outputs_render_with_the_same_state_label_and_quote(self):
        import html as H
        p = os.path.join(RC, "results", "incident_state", "raw_results.jsonl")
        with open(p, encoding="utf-8") as f: rows = [json.loads(l) for l in f]
        self.assertEqual(len(rows), 100); seen = set()
        for r in rows:
            res = r["output"]; inc = res.get("incident"); page = views.render_result(res, text=r["text"]).decode("utf-8")
            if inc and inc["state"] != "NO_INCIDENT":
                self.assertIn("data-state='%s'" % inc["state"], page, r["id"]); self.assertIn(H.escape(inc["label"]), page, r["id"])
                for e in inc["events"]:
                    if e["snippet"]: self.assertIn(H.escape(e["snippet"]), page, r["id"])
                seen.add(r["id"])
        self.assertTrue({"I40", "I43", "I92"} <= seen)


class TestNoSilentDowngradeByFormOrRegistry(Frozen):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.srv = webapp.make_server("127.0.0.1", 0, webapp.State(mode="fixture")); cls.port = cls.srv.server_address[1]; threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); super().tearDownClass()

    def post(self, path, data):
        return urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=urllib.parse.urlencode(data).encode(), method="POST"), timeout=15).read().decode()

    def test_reported_incident_is_not_lowered_by_choosing_the_default_option_or_by_a_registry_number(self):
        t = "Last week I wired 60,000, now they ask me for taxes before release. My adviser is INA000000201."
        pg = self.post("/check", {"situation": "NO_ACTION_YET", "text": t, "output_language": "en"})
        self.assertIn("Act now", pg); self.assertIn("data-state='USER_PAID'", pg); self.assertNotIn("name='number'", pg)       # registry form is not offered inside an urgent flow
        res = journey({"situation": "NO_ACTION_YET", "text": t, "output_language": "en"}, FixtureSource(os.path.join(RC, "eval", "registry_fixture.json")), {"number": "INA000000201"})
        self.assertEqual(res["posture"], "ESCALATE"); self.assertIsNone(res.get("registry"))

    def test_correction_form_resubmission_follows_the_new_choice_and_the_old_one_is_kept_visible(self):
        t = "I did not make the payment but a stranger keeps calling."
        pg = self.post("/check", {"situation": "PAID_MONEY", "text": t, "output_language": "en"})
        self.assertIn("Act now", pg); self.assertIn("data-state='USER_PAID'", pg) if "data-state='USER_PAID'" in pg else None; self.assertIn("did not", pg.lower())
        pg2 = self.post("/check", {"situation": "NO_ACTION_YET", "text": t, "output_language": "en"}); self.assertNotIn("Act now", pg2)       # the user's own correction is honoured, text-only


class TestPendingFirst(Frozen):
    def test_stop_payment_is_first_in_every_pending_or_pending_plus_incident_output(self):
        for sit, t in [("PAYMENT_PENDING", "I will send the clearance amount tonight."), ("NO_ACTION_YET", "I paid half yesterday, they want the other half and I am going to pay it now."),
                       ("UNSURE", "I will pay 9,000 in an hour to the agent."), ("NO_ACTION_YET", "Somebody withdrew money from my account without my consent and a caller wants me to pay a fee, I am about to.")]:
            r = self.ok(self.run_(sit, t)); self.assertEqual(self.uids(r)[:1], ["A_STOP_PAYMENT"], (sit, t, r["posture"]))


if __name__ == "__main__":
    unittest.main()
