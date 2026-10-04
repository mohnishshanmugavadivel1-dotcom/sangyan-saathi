# -*- coding: utf-8 -*-
"""Phase 4 regression tests: payment and credential incident handling (see results/incident_state/).
Written by the engine's author after the defect was confirmed; NOT independent validation. Clock pinned. No network.
Each defect is tested on the S3b S30 text AND on differently worded variants, plus negative tests so the fix does not widen into false escalation.
Hindi/Hinglish strings are author-written and unreviewed by a fluent speaker."""
import copy, json, os, re, sys, threading, unittest, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); RC = os.path.abspath(os.path.join(HERE, "..")); sys.path.insert(0, RC); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(RC, "eval")); sys.dont_write_bytecode = True
from saathi_rc import clock, engine, incident
from saathi_rc.engine import analyze
from saathi_rc.contract import URGENT_REQUIRED, INCIDENT_LABEL, INCIDENT_STATES
from saathi_rc.validate import validate
from saathi_rc.web import app as webapp, views
from saathi_rc.journey import journey, journey_violations
from run_incident import promise_wording

S30 = "Last week I wired 60,000, now they ask me for taxes before release."


class Frozen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._c = clock.frozen("2026-10-03"); cls._c.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._c.__exit__(None, None, None)

    def run_(self, sit, text, lang="en"): return analyze({"situation": sit, "text": text, "output_language": lang})
    def uids(self, r): return [a["action_id"] for a in r["urgent_steps"]]
    def ok(self, r): self.assertFalse(r["provenance"]["validation_failed"], r["provenance"]["validation_errors"]); return r


class TestJourney1ReportedPaymentWithDefaultSituation(Frozen):
    """S3b S30: with the situation left at the default the result was CANNOT_ASSESS with only conditional steps."""
    def test_s30_is_escalated_with_bank_and_1930_first(self):
        r = self.ok(self.run_("NO_ACTION_YET", S30))
        self.assertEqual(r["posture"], "ESCALATE"); self.assertTrue(URGENT_REQUIRED <= set(self.uids(r)))
        self.assertEqual(self.uids(r)[:2], ["A_CONTACT_BANK", "A_CALL_1930"]); self.assertEqual((r["claims"], r["indicators"]), ([], []))
        i = r["incident"]; self.assertEqual((i["state"], i["applied"], i["source"]), ("USER_PAID", "escalated_from_text", "text"))
        self.assertIn("wired 60,000", " ".join(e["snippet"] for e in i["events"])); self.assertIn("not certain", i["note"])

    def test_verb_variants_are_not_a_word_list_problem(self):
        for t in ["Two days ago I remitted 75,000 to their firm and today they asked for an additional charge to release the profit.",
                  "I sent them 12,000 via IMPS; the person on the phone keeps asking for more.",
                  "I deposited 40000 in the account they gave, now they want 20000 more as tax.",
                  "Yesterday I wired 60,000 and now they ask for taxes before release.",
                  "मैंने कल 25,000 रुपये भेज दिए, अब वे और पैसे मांग रहे हैं", "maine 25000 bhej diye, ab woh aur paise maang rahe hain"]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertEqual(r["posture"], "ESCALATE", t); self.assertEqual(r["incident"]["state"], "USER_PAID", t)

    def test_text_without_risk_context_asks_instead_of_escalating(self):
        for t in ["I wired the money.", "I sent the amount yesterday.", "I paid the school fee."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertEqual(r["posture"], "ASK_FOLLOWUP", t); self.assertEqual(self.uids(r), [], t)
            self.assertTrue(r["questions"] and r["steps"], t); self.assertIn("A_CALL_1930", [s["action_id"] for s in r["steps"]])
            self.assertTrue(all(s["conditional"] for s in r["steps"] if s["action_id"] in ("A_CONTACT_BANK", "A_CALL_1930")), t)

    def test_reported_credential_share_escalates(self):
        for t in ["I gave the caller my PIN.", "I told him the PIN and he said the refund would arrive.", "I shared the OTP with the agent.", "मैंने ओटीपी बता दिया"]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertEqual(r["posture"], "ESCALATE", t); self.assertEqual(r["incident"]["state"], "USER_SHARED_CREDENTIAL", t)

    def test_unsure_does_not_swallow_a_reported_credential_share(self):
        r = self.ok(self.run_("UNSURE", "I gave the caller my PIN.")); self.assertEqual(r["posture"], "ESCALATE")
        r = self.ok(self.run_("UNSURE", "")); self.assertEqual(r["posture"], "ASK_FOLLOWUP"); self.assertIsNone(r["incident"])


class TestJourney2To4ActorNegationPending(Frozen):
    def test_explicit_denial_is_not_treated_as_paid(self):
        for t in ["I never paid them.", "I have not paid anything and I will not.", "They asked me to read out a code, but I refused.", "I was about to pay but stopped.", "I did not share my OTP."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertNotEqual(r["posture"], "ESCALATE", t); self.assertEqual(self.uids(r), [], t)
            self.assertIn(r["incident"]["state"], ("USER_DENIES", "NO_INCIDENT"), t) if r["incident"] else None

    def test_third_party_and_sender_claim_are_not_attributed_to_the_user(self):
        for t, st in [("My father paid the amount.", "THIRD_PARTY_PAID"), ("They said they had already paid.", "SENDER_CLAIMS_PAYMENT"), ("The broker transferred money.", None),
                      ("The sender says I must pay a release fee.", None), ("I told them my brother paid it.", "THIRD_PARTY_PAID")]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertNotEqual(r["posture"], "ESCALATE", t)
            self.assertNotIn((r["incident"] or {}).get("state"), ("USER_PAID", "USER_SHARED_CREDENTIAL"), t)
            if st: self.assertEqual(r["incident"]["state"], st, t)

    def test_pending_payment_gets_stop_payment_first(self):
        for sit, t in [("PAYMENT_PENDING", "I will pay the release fee tomorrow."), ("NO_ACTION_YET", "I am about to transfer Rs 50,000 to this account to start trading, they say profit is guaranteed."),
                       ("NO_ACTION_YET", "I am going to pay 8000 tonight to the person who messaged me.")]:
            r = self.ok(self.run_(sit, t)); self.assertEqual(self.uids(r)[:1], ["A_STOP_PAYMENT"], (t, r["posture"]))
            self.assertNotEqual((r["incident"] or {}).get("state"), "USER_PAID", t)

    def test_intent_is_not_a_completed_payment(self):
        self.assertEqual(incident.read("I am about to transfer Rs 50,000 to this account")["state"], "NO_INCIDENT")
        self.assertEqual(incident.read("I paid half before. Now I plan to pay the rest.")["state"], "USER_PAID")

    def test_reader_events_carry_actor_action_status(self):
        e = incident.read("My father paid the amount.")["events"][0]; self.assertEqual((e["actor"], e["action"], e["status"]), ("THIRD", "PAYMENT", "COMPLETED"))
        e = incident.read("They said they had already paid.")["events"][0]; self.assertTrue(e["claimed"])
        e = incident.read("I never paid them.")["events"][0]; self.assertEqual((e["actor"], e["status"]), ("USER", "DENIED"))


class TestJourney5Uncertainty(Frozen):
    def test_unclear_reports_keep_uncertainty_and_still_give_steps(self):
        for t in ["I do not remember whether the transaction went through.", "Not sure whether the 5,000 went through or got reversed.", "I paid, but the recipient returned the money.", "maybe I sent it, I am not sure"]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertEqual(r["posture"], "ASK_FOLLOWUP", t); self.assertEqual(r["incident"]["state"], "PAYMENT_UNCLEAR", t)
            self.assertTrue(r["questions"], t); self.assertTrue({"A_CONTACT_BANK", "A_CALL_1930"} <= {s["action_id"] for s in r["steps"]}, t)
            self.assertIn("transaction history", r["questions"][0])


class TestJourney6LegitimatePayments(Frozen):
    def test_everyday_payments_do_not_escalate_or_get_a_stop_block(self):
        for t in ["Paid Rs 500 to Ramesh Stores via UPI", "Your electricity bill of Rs 1,200 has been paid.", "I paid my rent on the 1st, thanks for confirming.", "I will pay you back tomorrow.",
                  "I paid the school fee.", "Rs 5,000 was credited to your account.", "I paid the insurance premium last week and the receipt came."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertNotEqual(r["posture"], "ESCALATE", t)
            if "pay you back" not in t: self.assertNotIn("A_STOP_PAYMENT", self.uids(r), t)


class TestJourney7Coexistence(Frozen):
    def test_payment_and_credential_share_give_one_consistent_escalation(self):
        for t in ["I paid 20,000 and I also shared my OTP with them.", "I wired the money and told the agent my PIN."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); i = r["incident"]
            self.assertEqual(r["posture"], "ESCALATE"); self.assertEqual(i["state"], "USER_SHARED_CREDENTIAL"); self.assertIn("USER_PAID", i["active"]); self.assertTrue(i["also"])
            self.assertEqual(self.uids(r)[:2], ["A_CONTACT_BANK", "A_CALL_1930"]); self.assertEqual(validate(r, engine.get_corpus_rc(), {"pending": False}), [])

    def test_contradictory_denial_plus_share_still_escalates(self):
        r = self.ok(self.run_("NO_ACTION_YET", "I did not pay anything but I did share my password.")); self.assertEqual(r["posture"], "ESCALATE"); self.assertEqual(r["incident"]["state"], "USER_SHARED_CREDENTIAL")

    def test_selected_harm_wins_over_a_text_denial_and_says_so(self):
        r = self.ok(self.run_("PAID_MONEY", "I never paid them.")); self.assertEqual(r["posture"], "ESCALATE")
        self.assertTrue(r["incident"]["conflict_note"]); self.assertEqual(r["incident"]["source"], "form")
        r = self.ok(self.run_("PAID_MONEY", "")); self.assertEqual(r["incident"]["conflict_note"], "")

    def test_pending_selected_plus_completed_text_has_stop_payment_first(self):
        r = self.ok(self.run_("PAYMENT_PENDING", "I paid half yesterday, they now want the rest, and I am about to pay it.")); self.assertEqual(r["posture"], "ESCALATE")
        self.assertEqual(self.uids(r)[:3], ["A_STOP_PAYMENT", "A_CONTACT_BANK", "A_CALL_1930"])
        r = self.ok(self.run_("NO_ACTION_YET", "I paid half yesterday and they want the rest. I was about to pay it but stopped.")); self.assertNotIn("A_STOP_PAYMENT", self.uids(r))


class TestNeverPromisesRecovery(Frozen):
    def test_no_guarantee_wording_in_any_incident_output(self):
        for t in [S30, "I gave the caller my PIN.", "I wired the money.", "I do not remember whether the transaction went through.", "My father paid the amount."]:
            for lang in ("en", "hi"):
                self.assertFalse(promise_wording(self.run_("NO_ACTION_YET", t, lang)), (t, lang))


class TestValidatorInvariants(Frozen):
    def setUp(self):
        self.corpus = engine.get_corpus_rc(); self.good = self.run_("NO_ACTION_YET", S30)

    def errs(self, mut, ctx=None):
        r = copy.deepcopy(self.good); mut(r); return validate(r, self.corpus, ctx or {"pending": False})

    def test_good_output_is_valid(self): self.assertEqual(self.errs(lambda r: None), [])

    def test_escalation_without_incident_record_is_rejected(self): self.assertTrue(self.errs(lambda r: r.update(incident=None)))

    def test_reported_payment_ending_in_cannot_assess_is_rejected(self):
        def m(r): r.update(posture="CANNOT_ASSESS", headline=engine.HEADLINE["CANNOT_ASSESS"]["en"], urgent_steps=[]); r["incident"]["applied"] = "analysis"
        self.assertTrue([e for e in self.errs(m) if "reported payment" in e])

    def test_text_escalation_on_non_user_state_is_rejected(self):
        for st in ("USER_DENIES", "SENDER_CLAIMS_PAYMENT", "NO_INCIDENT", "THIRD_PARTY_PAID"):
            self.assertTrue(self.errs(lambda r: r["incident"].update(state=st)), st)

    def test_text_escalation_must_not_carry_findings(self): self.assertTrue(self.errs(lambda r: r.update(indicators=[{"indicator": "X", "note": "n", "snippet": "s"}])))

    def test_unknown_state_is_rejected(self): self.assertTrue(self.errs(lambda r: r["incident"].update(state="PAID_MAYBE")))

    def test_pending_escalation_needs_stop_payment_first(self):
        r = self.run_("NO_ACTION_YET", "I paid half yesterday and they want the rest, I am about to pay it.")
        r2 = copy.deepcopy(r); r2["urgent_steps"] = [s for s in r2["urgent_steps"] if s["action_id"] != "A_STOP_PAYMENT"]
        self.assertTrue(validate(r2, self.corpus, {"pending": True}))


class TestSafeFallback(Frozen):
    def test_validation_failure_does_not_turn_a_reported_payment_into_cannot_assess(self):
        r = engine.safe_fallback({"situation": "NO_ACTION_YET", "text": S30, "output_language": "en"}, "en", "NO_ACTION_YET", ["boom"])
        self.assertEqual(r["posture"], "ESCALATE"); self.assertTrue(URGENT_REQUIRED <= set(self.uids(r))); self.assertTrue(r["provenance"]["validation_failed"])
        r = engine.safe_fallback({"situation": "NO_ACTION_YET", "text": "hello there", "output_language": "en"}, "en", "NO_ACTION_YET", ["boom"])
        self.assertNotEqual(r["posture"], "ESCALATE")

    def test_exception_in_the_reader_degrades_to_the_fallback(self):
        orig = incident.read
        incident.read = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            r = self.run_("NO_ACTION_YET", S30)
        finally:
            incident.read = orig
        self.assertTrue(r["provenance"]["validation_failed"]); self.assertIn(r["posture"], ("CANNOT_ASSESS", "ASK_FOLLOWUP", "ABSTAIN", "HIGH_CONCERN", "SOME_CONCERN", "ESCALATE"))


class TestJourney8UiMatchesBackend(Frozen):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.srv = webapp.make_server("127.0.0.1", 0, webapp.State(mode="off")); cls.port = cls.srv.server_address[1]; threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); super().tearDownClass()

    def page(self, sit, text, lang="en"):
        data = urllib.parse.urlencode({"situation": sit, "text": text, "output_language": lang}).encode()
        return urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:%d/check" % self.port, data=data, method="POST"), timeout=15).read().decode()

    def test_page_shows_the_backend_state_label_quote_and_steps(self):
        import html as H
        for t in [S30, "I gave the caller my PIN.", "I do not remember whether the transaction went through.", "My father paid the amount.", "I never paid them.", "They said they had already paid."]:
            res = journey({"situation": "NO_ACTION_YET", "text": t, "output_language": "en"}); pg = self.page("NO_ACTION_YET", t); inc = res["incident"]
            self.assertIn("data-state='%s'" % inc["state"], pg, t); self.assertIn(H.escape(inc["label"]), pg)
            for e in inc["events"]:
                if e.get("snippet"): self.assertIn(H.escape(e["snippet"]), pg, t)
            for s in res["urgent_steps"]: self.assertIn(H.escape(s["text"], quote=True), pg.replace("&#x27;", "&#x27;"), t)
            self.assertIn(H.escape(res["headline"]), pg)
            self.assertEqual(("Act now" in pg), res["posture"] == "ESCALATE", t)

    def test_no_incident_panel_for_ordinary_text_and_never_reassures(self):
        pg = self.page("NO_ACTION_YET", "Guaranteed 40% monthly returns. Pay Rs 5000 now to join, limited seats."); self.assertNotIn("id='incident'", pg)

    def test_text_escalation_offers_a_correction_form_but_harm_form_does_not(self):
        pg = self.page("NO_ACTION_YET", S30); self.assertIn("name='situation'", pg); self.assertIn("id='t3'", pg)
        self.assertNotIn("id='t3'", self.page("PAID_MONEY", ""))

    def test_text_is_escaped_in_the_quote(self):
        pg = self.page("NO_ACTION_YET", "I paid <script>alert(1)</script> Rs 5000 yesterday and they want more"); self.assertNotIn("<script>alert", pg)

    def test_hindi_page_uses_the_hindi_label(self):
        res = journey({"situation": "NO_ACTION_YET", "text": S30, "output_language": "hi"}); pg = self.page("NO_ACTION_YET", S30, "hi")
        self.assertIn(INCIDENT_LABEL["USER_PAID"]["hi"], pg); self.assertEqual(res["incident"]["label"], INCIDENT_LABEL["USER_PAID"]["hi"])

    def test_journey_violations_clean(self):
        for t in [S30, "I wired the money.", "My father paid the amount."]: self.assertEqual(journey_violations(journey({"situation": "NO_ACTION_YET", "text": t})), [])


class TestDefectsFoundByThePostFixRun(Frozen):
    """Defects seen only after the first post-fix run on the frozen challenge set (results/incident_state/FAILURE_ANALYSIS.md). Each is tested on differently worded variants,
    not on the challenge texts alone, and has a negative test so the repair does not widen."""
    def test_light_verb_with_negation_is_a_denial_not_a_payment(self):
        for t in ["I did not transfer anything.", "I did not make the payment.", "I didn't send any money."]:
            self.assertEqual(incident.read(t)["state"], "USER_DENIES", t)

    def test_obligation_is_not_a_completed_payment(self):
        for t in ["The sender says I must pay a release fee.", "You must pay the fee today.", "They say I should pay 5000 more."]:
            self.assertEqual(incident.read(t)["state"], "NO_INCIDENT", t)

    def test_attempt_followed_by_not_completed_is_a_denial_but_a_failed_attempt_stays_unclear(self):
        self.assertEqual(incident.read("I tried to pay 5,000 but I have not completed the payment.")["state"], "USER_DENIES")
        self.assertEqual(incident.read("I tried to pay 5000 but the transaction failed.")["state"], "PAYMENT_UNCLEAR")

    def test_latin_hindi_intent_is_pending_not_completed(self):
        for t in ["Main aaj raat 20000 bhejne wala hoon.", "Main kal 5000 bhejne wali hoon."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertEqual(self.uids(r)[:1], ["A_STOP_PAYMENT"], t); self.assertNotEqual(r["incident"] and r["incident"]["state"], "USER_PAID", t)
        self.assertEqual(incident.read("मैंने कल 25,000 रुपये भेज दिए")["state"], "USER_PAID")      # 'kal' alone is not a future marker (yesterday or tomorrow)

    def test_unknown_person_paying_from_my_account_is_never_third_party(self):
        # Phase 4 behaviour was PAYMENT_UNCLEAR + ASK_FOLLOWUP. Phase 5 supersedes it (docs/CHANGELOG_RC.md CH-S5-01): an unknown person paying from the user's own account is an
        # UNAUTHORISED_DEBIT and escalates. What stays true is the point of this test: it is never read as a third party's own payment.
        for t in ["Someone paid from my account but I do not know who.", "A stranger transferred 9000 from my card."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertEqual(r["incident"]["state"], "UNAUTHORISED_DEBIT", t); self.assertEqual(r["posture"], "ESCALATE", t)
        r = self.ok(self.run_("NO_ACTION_YET", "A stranger transferred 9000 from his own card.")); self.assertNotEqual(r["posture"], "ESCALATE")
        self.assertEqual(incident.read("My father paid from his account.")["state"], "THIRD_PARTY_PAID")

    def test_coordinated_predicate_after_an_object_noun_stays_with_the_user(self):
        for t in ["I opened the app and paid my electricity bill.", "I logged in to my bank app and paid the rent.", "I installed the app and paid the premium.", "I clicked the pay button and paid the water bill of Rs 800."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertEqual(r["incident"]["state"], "USER_PAID", t); self.assertNotEqual(r["posture"], "ESCALATE", t)
        self.assertEqual(incident.read("My father opened the app and paid the fee.")["state"], "THIRD_PARTY_PAID")
        self.assertEqual(incident.read("The app paid the vendor.")["state"], "THIRD_PARTY_PAID")

    def test_paying_after_clicking_what_the_other_side_sent_escalates(self):
        for t in ["I clicked the link and paid 3,000 for the KYC update.", "I opened the file they sent and paid 5,000.", "I installed the apk he sent me and paid 7000."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertEqual(r["posture"], "ESCALATE", t)

    def test_after_payment_trouble_counts_as_context(self):
        for t in ["I made a payment of 18,500 via UPI to the number they sent, then the call got cut and nobody answers.", "I settled the unlock fee of Rs 9,999 and the company still has not released my profit."]:
            r = self.ok(self.run_("NO_ACTION_YET", t)); self.assertEqual(r["posture"], "ESCALATE", t)

    def test_ui_quote_check_survives_apostrophes_and_ampersands(self):
        import html as H
        t = "No, I haven't sent any money yet. Bob & Co's agent called."
        res = journey({"situation": "NO_ACTION_YET", "text": t}); srv = webapp.make_server("127.0.0.1", 0, webapp.State(mode="off")); port = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            data = urllib.parse.urlencode({"situation": "NO_ACTION_YET", "text": t, "output_language": "en"}).encode()
            pg = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:%d/check" % port, data=data, method="POST"), timeout=15).read().decode()
        finally:
            srv.shutdown(); srv.server_close()
        for e in (res["incident"] or {"events": []})["events"]: self.assertIn(H.escape(e["snippet"]), pg)


class TestRobustness(Frozen):
    def test_every_dev_case_in_every_situation_validates(self):
        with open(os.path.join(RC, "eval", "cases_incident_dev.jsonl"), encoding="utf-8") as f: cases = [json.loads(l) for l in f]
        for c in cases:
            for sit in ("NO_ACTION_YET", "PAYMENT_PENDING", "UNSURE", "PAID_MONEY", "SHARED_CREDENTIALS"):
                r = self.run_(sit, c["text"]); self.assertFalse(r["provenance"]["validation_failed"], (c["id"], sit, r["provenance"]["validation_errors"]))
                if r.get("incident"): self.assertIn(r["incident"]["state"], INCIDENT_STATES)

    def test_odd_inputs_never_raise(self):
        for t in ["", " ", "paid " * 500, "ʼ" * 50, "OTP " * 100, "\u0000\u0001", "I paid" + "," * 300, "9" * 5000, "भेज दिया " * 200]:
            for sit in ("NO_ACTION_YET", "PAYMENT_PENDING", "UNSURE"): self.ok(self.run_(sit, t))

    def test_deterministic(self):
        a = self.run_("NO_ACTION_YET", S30); b = self.run_("NO_ACTION_YET", S30); self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
