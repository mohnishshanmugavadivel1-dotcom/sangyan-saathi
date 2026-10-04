# -*- coding: utf-8 -*-
"""Sprint Oct-4 regression tests for the safety-escalation fixes (rc2). Covers the 7 target cases, adjacent cases (negation, hypothetical, quoted, denied, pending, completed),
the validator rule, the label semantics and the page. Also pins the KNOWN trade-offs and the KNOWN unresolved case so a later change cannot silently alter them.
These are development tests against cases the fixes were built from; they are NOT independent validation."""
import json, os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); RC = os.path.abspath(os.path.join(HERE, "..")); sys.path.insert(0, RC); sys.dont_write_bytecode = True
from saathi_rc import clock, incident as I
from saathi_rc.contract import INCIDENT_LABEL, SUBJECTLESS_LABEL
from saathi_rc.engine import analyze, _analyze, get_corpus_rc
from saathi_rc.validate import validate
from saathi_rc.web import views


def run(text, sit="NO_ACTION_YET", lang="en"):
    with clock.frozen("2026-10-03"):
        r = analyze({"situation": sit, "text": text, "output_language": lang})
    urg = [s["action_id"] for s in r.get("urgent_steps", [])]
    return r, urg, (r.get("incident") or {}).get("state")


def esc(t, **k): r, u, s = run(t, **k); return r["posture"] == "ESCALATE"


class Targets(unittest.TestCase):
    def test_X13_subjectless_paid_now_wants_more(self): self.assertTrue(esc("Paid 15,000 to the account he gave me; now he wants more."))
    def test_X14_another_amount(self): self.assertTrue(esc("Transferred 25,000 as processing fee. They are asking for another 25,000."))
    def test_X15_unknown_number(self): self.assertTrue(esc("Rs 4,000 was sent from my phone to an unknown number."))
    def test_X40_credential_entered_on_sms_page(self): self.assertTrue(esc("I entered my card number and CVV on a page that opened from the SMS."))
    def test_X11_hinglish_trader_ko(self):
        t = "maine trader ko 50000 transfer kar diya, ab woh withdrawal ke liye aur paise maang raha hai"
        r, u, s = run(t); self.assertEqual(s, "USER_PAID"); self.assertEqual(r["posture"], "ESCALATE")
    def test_X08_repeated_charges(self): self.assertTrue(esc("After I paid the registration amount, the advisor kept finding new charges: first insurance, then tax."))
    def test_X24_pending_deadline(self):
        r, u, s = run("They gave me until tonight to pay 15,000 or lose the account; I am thinking of paying.")
        self.assertEqual(s, "USER_PAYMENT_PENDING"); self.assertEqual(u[:1], ["A_STOP_PAYMENT"])


class Semantics(unittest.TestCase):
    def test_subjectless_never_labelled_user_paid(self):
        r, u, s = run("Paid 15,000 to the account he gave me; now he wants more.")
        self.assertEqual(s, "PAYMENT_UNCLEAR"); self.assertEqual(r["incident"]["label"], SUBJECTLESS_LABEL["en"]); self.assertNotIn(r["incident"]["label"], [v for v in (INCIDENT_LABEL.values() if isinstance(INCIDENT_LABEL, dict) else [])] + [x for v in INCIDENT_LABEL.values() if isinstance(v, dict) for x in v.values()])
        self.assertIn("does not say who made it", r["incident"]["label"])
        self.assertEqual(r["incident"]["applied"], "escalated_from_text"); self.assertFalse(r["provenance"].get("validation_failed"))

    def test_subjectless_hindi_label_is_present(self):
        r, u, s = run("Paid 15,000 to the account he gave me; now he wants more.", lang="hi"); self.assertEqual(r["incident"]["label"], SUBJECTLESS_LABEL["hi"])

    def test_validator_accepts_only_the_explicit_subjectless_route(self):
        import copy
        t = "Paid 15,000 to the account he gave me; now he wants more."
        with clock.frozen("2026-10-03"):
            corpus = get_corpus_rc(); res, ctx = _analyze({"situation": "NO_ACTION_YET", "text": t, "output_language": "en"}, "en", "NO_ACTION_YET", corpus)
            self.assertEqual(validate(res, corpus, ctx), [])
            a = copy.deepcopy(res); a["provenance"]["incident_route"] = "escalated_from_text"
            self.assertTrue([e for e in validate(a, corpus, ctx) if "PAYMENT_UNCLEAR" in e])          # the generic route may not escalate PAYMENT_UNCLEAR
            b = copy.deepcopy(res); b["incident"]["risk_context"] = []
            self.assertTrue([e for e in validate(b, corpus, ctx) if "PAYMENT_UNCLEAR" in e])          # the subject-less route needs a non-empty risk context

    def test_validator_still_rejects_other_unclear_escalation(self):
        # PAYMENT_UNCLEAR may escalate only through the subject-less route; a plain unexplained debit keeps its earlier (ASK) behaviour
        r, u, s = run("There is a 12,500 debit in my savings account that I do not recognise.")
        self.assertFalse(r["provenance"].get("validation_failed"))

    def test_page_shows_urgent_steps_and_label(self):
        r, u, s = run("Paid 15,000 to the account he gave me; now he wants more.")
        h = views.render_result(r, text="Paid 15,000 to the account he gave me; now he wants more.")
        h = h.decode("utf-8") if isinstance(h, bytes) else h
        self.assertIn("does not say who made it", h.replace("&#x27;", "'")); self.assertIn("1930", h)

    def test_subjectless_promotion_unit(self):
        t = "Paid 15,000 to the account he gave me; now he wants more."
        self.assertEqual(I.read(t)["state"], "NO_INCIDENT"); self.assertTrue(I.subjectless_payment_context(I.read(t), t))
        t2 = "Paid for Telegram Premium."; self.assertEqual(I.subjectless_payment_context(I.read(t2), t2), [])


class Negation(unittest.TestCase):
    def test_not_entered(self): self.assertFalse(esc("I did not enter my CVV on the page they sent."))
    def test_never_paid(self): self.assertFalse(esc("I never paid the 15,000 they are demanding."))
    def test_not_sent(self): self.assertFalse(esc("Rs 4,000 was not sent to an unknown number."))
    def test_hinglish_not_sent(self): self.assertFalse(esc("maine trader ko paise nahi bheje, woh aur paise maang raha hai"))
    def test_have_not_entered(self):
        for t in ("I have not entered my card number on the page from the SMS.", "I haven't entered my CVV on the page they sent.", "I never entered my card number on that link from the SMS."): self.assertFalse(esc(t), t)
    def test_not_thinking_of_paying(self):
        r, u, s = run("I am not thinking of paying them anything."); self.assertNotEqual(u[:1], ["A_STOP_PAYMENT"])
    def test_not_paid_repeated_charges(self): self.assertFalse(esc("I did not pay the registration amount, the advisor keeps finding new charges."))


class Hypothetical(unittest.TestCase):
    def test_if_entered(self): self.assertFalse(esc("If I entered my card number on that link, what should I do?"))
    def test_if_enter(self): self.assertFalse(esc("If I enter my card number on the page from the SMS, will I lose money?"))
    def test_going_to(self): self.assertFalse(esc("I am going to enter my card details on the link they sent."))
    def test_almost(self): self.assertFalse(esc("I almost entered my CVV on the page they sent but closed it."))
    def test_attempt_not_completed(self): self.assertFalse(esc("I attempted to pay 3000 but did not complete it."))


class QuotedAndAdvice(unittest.TestCase):
    def test_sms_instruction(self): self.assertFalse(esc("The SMS said: enter your card number and CVV on this page."))
    def test_advice_never_enter(self): self.assertFalse(esc("Never enter your card number on a page opened from an SMS."))
    def test_dont_enter(self): self.assertFalse(esc("Don't enter your card number and CVV on a page that opened from an SMS."))
    def test_quoted_claim(self): self.assertFalse(esc('The message said "I entered my card number and CVV on the page from the SMS".'))
    def test_sender_claims_payment(self): self.assertFalse(esc("The agent said I paid 5,000 last week but I never did."))
    def test_screenshot_claim_no_new_demand(self):   # cross-set finding I30: a weak verb ("says") + an amount is not a demand
        r, u, s = run("The agent sent me a screenshot that says I paid 50,000, but I never made this payment."); self.assertEqual(r["posture"], "CANNOT_ASSESS")


class Denied(unittest.TestCase):
    def test_refused(self): self.assertFalse(esc("He asked me to enter my CVV on a page he sent; I refused."))
    def test_never_made_payment(self): self.assertFalse(esc("The agent said I paid 5,000 last week but I never did."))


class Ordinary(unittest.TestCase):
    """Ordinary events must not newly escalate."""
    CASES = ["Paid Rs 799 to Netflix.", "Paid 1,200 to Zomato via UPI.", "Rs 450 was sent to Ramesh for the cab share.", "Transferred 25,000 to my own savings account.",
             "Paid the electricity bill of 1,850. They are asking for a rating.", "Paid 3,000 rent to the landlord. He wants a receipt.", "I entered my PIN at the ATM and withdrew cash.",
             "I entered my card number on the Amazon checkout page to buy a book.", "Rs 4,000 was credited to your account.", "Rs 4,000 was sent to your account by Ravi.",
             "My brother paid 50,000 to the agent and now they want more.", "They gave me a receipt for 5,000.", "They gave me a receipt for the 15,000 I paid last month.",
             "The shopkeeper gave me until Friday to pick up the order.", "I paid for my insurance premium and the insurer added GST as shown on the invoice.",
             "I paid the hotel bill; they kept the extra charges off my invoice.", "maine dukaan ko 500 pay kar diya", "usne mujhe 1000 transfer kar diya", "Paid for Telegram Premium."]
    def test_no_escalation(self):
        for t in self.CASES: self.assertFalse(esc(t), t)
    def test_receipt_is_not_a_payment(self):
        for t in ("They gave me a receipt for 5,000.", "They gave me until tonight to pay."): self.assertNotEqual(run(t)[2], "THIRD_PARTY_PAID", t)


class Pending(unittest.TestCase):
    def test_stop_first(self):
        for t in ("They gave me until tonight to pay 15,000 or lose the account; I am thinking of paying.", "I am considering paying the 10,000 fee they asked for.",
                  "They gave me 48 hours to deposit 20,000 or the account closes.", "I will send the clearance amount tonight.", "The agent gave me 2 hours to pay 5,000; I have not paid.", "They gave me until tonight to pay 15,000 or lose the account.", "I have until midnight to transfer 5000 or my account is frozen."):
            self.assertEqual(run(t)[1][:1], ["A_STOP_PAYMENT"], t)
    def test_tradeoff_ordinary_bill_is_also_stopped(self):   # KNOWN limitation, pinned: stop-payment on an ordinary bill is the cost of the "thinking of paying" cue
        self.assertEqual(run("I am thinking of paying my electricity bill tonight.")[1][:1], ["A_STOP_PAYMENT"])


class Completed(unittest.TestCase):
    def test_explicit_completed_still_escalates(self):
        for t in ("I paid 60,000 to the advisor and now he asks for taxes before release.", "Sent Rs 12,000 to an unknown account from my UPI.",
                  "Rs 7,500 was transferred from my account to an unfamiliar UPI ID.", "I filled in my UPI PIN on the link the caller sent me.", "I submitted my login details on the website they sent.",
                  "I clicked the link in the message and typed my card number and CVV.", "After I paid the fee, the broker kept adding new charges every week.",
                  "maine agent ko 20000 transfer kar diya, ab woh aur paise maang raha hai"): self.assertTrue(esc(t), t)
    def test_modal_passive_is_not_completed(self):
        r, u, s = run("Deposited 50,000 on the platform. Now they say tax of 15,000 must be paid before withdrawal."); self.assertEqual(r["posture"], "ESCALATE")


class KnownTradeoffsAndGaps(unittest.TestCase):
    def test_tradeoff_small_extra_ask_escalates(self):   # NEW FALSE POSITIVES, disclosed: subject-less ordinary payment + "N more" now escalates
        self.assertTrue(esc("Paid 2,000 advance to the plumber; he asked for 300 more for parts."))
        self.assertTrue(esc("Sent 5,000 to the caterer. The caterer is asking for another 1,000 on the day."))
    def test_pre_existing_hypothetical_paid_escalates(self):   # PRE-EXISTING in rc (unchanged): "If I paid ..." is read as a completed payment
        self.assertTrue(esc("If I paid 15,000 would they ask for more?"))
    @unittest.expectedFailure
    def test_R03_unresolved_enumerated_charges_without_iterative_marker(self):
        self.assertTrue(esc("I paid the registration amount, then they added a GST charge, then a compliance fee."))


class SetFile(unittest.TestCase):
    """Table-driven: every scored case in the authored adjacent file, except the one documented unresolved case."""
    def test_all_scored_cases(self):
        bad = []
        with open(os.path.join(RC, "eval", "cases_sprint_adjacent.jsonl"), encoding="utf-8") as f: lines = f.read().splitlines()
        for l in lines:
            c = json.loads(l)
            if c["must"] == "TRADEOFF" or c["id"] == "R03": continue
            r, u, s = run(c["text"], sit=c["situation"])
            ok = {"ESC": r["posture"] == "ESCALATE", "NOT_ESC": r["posture"] != "ESCALATE", "STOP": u[:1] == ["A_STOP_PAYMENT"]}[c["must"]]
            if not ok: bad.append(c["id"])
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
