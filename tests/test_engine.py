"""Safety-logic regression, journey invariants, fuzz/robustness and the S1 gate. Clock pinned. No network."""
import itertools, json, os, random, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); RC = os.path.abspath(os.path.join(HERE, "..")); sys.path.insert(0, RC); sys.path.insert(0, HERE); sys.dont_write_bytecode = True
from saathi_rc import clock, engine
from saathi_rc.contract import SITUATIONS, HARM, POSTURES, REASSURE_RE, APPROVED_NEGATIVE, URGENT_REQUIRED
from saathi_rc.engine import analyze
from saathi_rc.journey import journey, journey_violations
from saathi_rc.registry.source import FixtureSource
from saathi_rc.validate import validate
from sources_replay import FaultSource

with open(os.path.join(RC, "eval", "registry_fixture.json"), encoding="utf-8") as _f:
    FX = json.load(_f)["entries"]
SCAM = "Guaranteed 40% monthly returns, SEBI registered INA000000201. Pay Rs 5000 now to join, limited seats. Download app http://x.co/a"
TEXTS = [SCAM, "", " ", "hello", "Pay now", "I paid Rs 5000 yesterday and they want more", "I did not pay anything", "Unless you pay, your account will be frozen", "Send OTP to verify your KYC http://bit.ly/x",
         "गारंटीड रिटर्न! अभी पैसे भेजें", "உத்தரவாத லாபம் இப்போது அனுப்புங்கள்", "आजच पैसे पाठवा, हमी परतावा", "আজই টাকা পাঠান", "A" * 20000, "\u202e\u200b" * 50, "pay\x00now\x1b[31m guaranteed", "<script>alert(1)</script> guaranteed 50% returns",
         "INA000000201 INA000000202 INH000000101", "UPI: scammer@okbank send 5000 now", "Join https://sebi.gov.in.verify-now.top/login now"]


class Frozen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._c = clock.frozen("2026-10-03"); cls._c.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._c.__exit__(None, None, None)


class TestInvariantsOverMatrix(Frozen):
    def test_every_output_is_valid_never_clean_and_gate_respected(self):
        n = 0
        for sit, text, lang in itertools.product(list(SITUATIONS) + [None, "BOGUS"], TEXTS, ("en", "hi", "zz")):
            r = analyze({"situation": sit, "text": text, "output_language": lang}); n += 1
            self.assertIn(r["posture"], POSTURES); self.assertFalse(r["provenance"]["validation_failed"], (sit, text[:30], r["provenance"]["validation_errors"]))
            self.assertEqual(r["block_order"], ["urgent_steps", "assessment", "steps", "registry", "unavailable", "limitations"])
            if sit in HARM:
                self.assertEqual(r["posture"], "ESCALATE"); self.assertTrue(URGENT_REQUIRED <= {s["action_id"] for s in r["urgent_steps"]}); self.assertEqual((r["claims"], r["indicators"]), ([], []))
            if sit not in SITUATIONS: self.assertEqual(r["posture"], "NEEDS_SITUATION")
            if sit == "UNSURE": self.assertIn(r["posture"], ("ASK_FOLLOWUP", "ESCALATE")); self.assertTrue(r["posture"] == "ASK_FOLLOWUP" or r["incident"]["applied"] == "escalated_from_text")   # S4: UNSURE reads the text too
            self.assertTrue(r["limitations"])
            # S4 amendment (documented in docs/CHANGELOG_RC.md): the old assertion was "NO_ACTION_YET never ESCALATE". It is now "only with an incident record
            # saying the text reported a payment or code share" (a text escalation); the stricter check is in test_incident_state.py.
            if sit == "NO_ACTION_YET" and r["posture"] == "ESCALATE": self.assertEqual((r.get("incident") or {}).get("applied"), "escalated_from_text", (text[:40], r["incident"]))
        self.assertEqual(n, 8 * len(TEXTS) * 3)

    def test_clean_result_impossible_for_any_text(self):
        blobs = []
        for text in TEXTS:
            r = analyze({"situation": "NO_ACTION_YET", "text": text, "output_language": "en"})
            blob = " ".join([r["headline"], r["summary"]] + [s["text"] for s in r["steps"]] + r["limitations"] + [c["explanation"] for c in r["claims"]] + [i["note"] for i in r["indicators"]])
            for a in APPROVED_NEGATIVE: blob = blob.replace(a, "")
            self.assertIsNone(REASSURE_RE.search(blob), (text[:40], REASSURE_RE.search(blob)))
            self.assertIn(r["posture"], ("HIGH_CONCERN", "SOME_CONCERN", "CANNOT_ASSESS", "ABSTAIN", "ASK_FOLLOWUP", "ESCALATE"))   # ASK_FOLLOWUP/ESCALATE (S4): text says money may already be gone
            if r["posture"] == "ESCALATE": self.assertEqual(r["incident"]["applied"], "escalated_from_text")

    def test_deterministic(self):
        for t in TEXTS[:8]:
            a = analyze({"situation": "NO_ACTION_YET", "text": t}); b = analyze({"situation": "NO_ACTION_YET", "text": t})
            for r in (a, b): r.pop("request_id", None)
            self.assertEqual(a, b)

    def test_fuzz_never_raises(self):
        rnd = random.Random(7); alpha = "abcdef 0123456789₹@:/.\u0905\u0915\u0bae\u200b\u202e%-_\n\t<>&\"'"
        for _ in range(300):
            t = "".join(rnd.choice(alpha) for _ in range(rnd.randint(0, 400)))
            r = analyze({"situation": rnd.choice(list(SITUATIONS)), "text": t, "output_language": rnd.choice(["en", "hi"])})
            self.assertFalse(r["provenance"]["validation_failed"], t[:60])
        for bad in (None, 5, [], {"text": 5}, {"situation": 5}, {"text": ["a"]}, {"situation": "PAID_MONEY", "text": {"x": 1}}):
            r = analyze(bad) if isinstance(bad, dict) else analyze({"text": bad}); self.assertIn(r["posture"], POSTURES)


class TestFailClosed(Frozen):
    def test_core_exception_falls_back_to_safe_output_with_guidance(self):
        orig = engine.analyze_core
        engine.analyze_core = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected"))
        try:
            r = analyze({"situation": "NO_ACTION_YET", "text": SCAM})
        finally:
            engine.analyze_core = orig
        self.assertIn(r["posture"], POSTURES); self.assertTrue(r["provenance"]["validation_failed"] or r["provenance"].get("error") or r["posture"] in ("CANNOT_ASSESS", "ABSTAIN"))
        self.assertNotIn("clean", r["posture"].lower()); self.assertTrue(r["steps"] or r["urgent_steps"] or r["limitations"])

    def test_core_abstain_does_not_hide_findings_CH01b(self):
        orig = engine.analyze_core
        def abstain(req, corpus=None):
            r = orig(req, corpus); r = dict(r); r["posture"] = "ABSTAIN"; return r
        engine.analyze_core = abstain
        try:
            r = analyze({"situation": "NO_ACTION_YET", "text": SCAM})
        finally:
            engine.analyze_core = orig
        self.assertNotEqual((r["posture"], bool(r["indicators"])), ("ABSTAIN", True)); self.assertFalse(r["provenance"]["validation_failed"] and r["posture"] == "ABSTAIN")

    def test_validator_rejects_hand_broken_outputs(self):
        corpus = engine.get_corpus_rc(); good = analyze({"situation": "NO_ACTION_YET", "text": SCAM})
        ctx = {"pending": False}
        self.assertEqual(validate(good, corpus, ctx), [])
        import copy
        for mut, name in ((lambda r: r.update(posture="NO_INDICATORS_FOUND"), "clean posture"), (lambda r: r.update(headline="This looks safe."), "headline"), (lambda r: r.update(block_order=["steps"]), "block order"),
                          (lambda r: r["claims"][0].update(state="SUPPORTED") if False else r.update(language="xx"), "lang")):
            r = copy.deepcopy(good); mut(r); self.assertTrue(validate(r, corpus, ctx), name)
        h = analyze({"situation": "PAID_MONEY", "text": ""}); h2 = copy.deepcopy(h); h2["urgent_steps"] = h2["urgent_steps"][2:]
        self.assertTrue(validate(h2, corpus, {"pending": False}))


class TestSnippetMasking(Frozen):
    def test_ch07_snippets_cut_at_tokens_and_never_show_sensitive_digits(self):
        text = "Hello. Your OTP is 482913, card 4111 1111 1111 1111, Aadhaar 2345 6789 0123. Guaranteed 40% monthly returns, pay Rs 5000 now to join, limited seats."
        r = analyze({"situation": "NO_ACTION_YET", "text": text})
        shown = " ".join(i["snippet"] for i in r["indicators"]) + " " + " ".join(c["snippet"] for c in r["claims"])
        for s in ("482913", "4111", "1111 1111", "2345 6789", "6789 0123", "0123"): self.assertNotIn(s, shown)
        for i in r["indicators"]:
            sn = i["snippet"].strip("."); self.assertFalse(sn[:1].isdigit() and not sn.split()[0].isalnum(), sn)
        import re; self.assertIsNone(re.search(r"(?<!\d)0 now", shown))   # the old mid-token cut produced "0 now" from "5000 now"


class TestNegationCuesRegression(Frozen):
    def test_threat_future_not_account_compromise_D02(self):
        r = analyze({"situation": "NO_ACTION_YET", "text": "If you do not complete KYC your account will be blocked. Update at http://kyc-bank.xyz"})
        self.assertNotEqual(r["posture"], "ESCALATE")

    def test_escalation_rules_CH02b(self):
        for t in ("Install AnyDesk and read me the code so I can help you recover profits", "Enter your net banking password at http://sbi-secure-login.top to claim reward",
                  "Download the APK from this link to receive your refund http://files.xyz/a.apk"):
            r = analyze({"situation": "NO_ACTION_YET", "text": t}); self.assertIn(r["posture"], ("HIGH_CONCERN", "ASK_FOLLOWUP", "ESCALATE"), t)


class TestPostHocFixesAfterS2(Frozen):
    """CH-08 / CH-08b / CH-09: added after S2 run1 exposed the gaps. Each has positive AND negative cases (precision matters: a legitimate OTP message must stay un-flagged)."""
    def test_credential_requests_flagged(self):
        for t in ("Send a photo of your debit card (both sides) and the OTP; our executive will activate your new credit limit.", "Dear customer, to receive your dividend of Rs 8,200 kindly share the 6-digit code sent to your phone.",
                  "अपना ओटीपी बताएं और इनाम पाएं", "Please tell me the PIN of your card so we can refund you"):
            r = analyze({"situation": "NO_ACTION_YET", "text": t}); self.assertEqual(r["posture"], "HIGH_CONCERN", t); self.assertIn("CREDENTIAL_REQUEST", [i["indicator"] for i in r["indicators"]], t)

    def test_prohibitions_and_plain_otp_messages_not_flagged(self):
        # Known, documented over-flags (NOT tested as clean; see KNOWN_LIMITATIONS): "Enter OTP 482913 to verify your login." and "Please do not send your password to anyone." are flagged by the
        # copied core's own CREDENTIAL_REQUEST rule (it deliberately keeps "please ..." sentences as requests).
        for t in ("Your OTP for login is 482913. Do not share this OTP with anyone. Bank staff never ask for it.", "Never share your OTP or PIN with anyone.", 
                  "Investor awareness: never share your OTP or trading password with anyone.", "ओटीपी किसी को न बताएं।"):
            r = analyze({"situation": "NO_ACTION_YET", "text": t}); self.assertNotIn("CREDENTIAL_REQUEST", [i["indicator"] for i in r["indicators"]], t); self.assertNotEqual(r["posture"], "HIGH_CONCERN", t)

    def test_first_person_intent_to_pay_gets_stop_payment_first(self):
        for t in ("They asked for Rs 12,000 for the tip package and I plan to transfer it in a few minutes.", "I'll pay the fee now, they said the offer ends soon.", "I am going to send the money tonight to join their group."):
            r = analyze({"situation": "NO_ACTION_YET", "text": t}); self.assertEqual([s["action_id"] for s in r["urgent_steps"]][:1], ["A_STOP_PAYMENT"], t)

    def test_negated_intent_is_not_pending(self):
        for t in ("I am not going to pay anything to this man.", "I'm not planning to pay, but they keep calling.", "I won't be paying anything to this man who is promising a 100% safe profit."):
            r = analyze({"situation": "NO_ACTION_YET", "text": t}); self.assertEqual(r["urgent_steps"], [], t)

    def test_s2_post_hoc_gate(self):
        out = tempfile.mkdtemp()
        p = subprocess.run([sys.executable, "-B", "run_suite.py", "cases_s2.jsonl", out, "--post-hoc"], cwd=os.path.join(RC, "eval"), capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])
        with open(os.path.join(out, "rc_results.json")) as f: s = json.load(f)["summary"]
        self.assertEqual((s["critical_unsafe"], s["technical_failure"], s["missing_guidance"]), (0, 0, 0), s)


class TestJourney(Frozen):
    def src(self, **kw):
        return FixtureSource([dict(x) for x in FX], as_of={"IA": "2026-10-02", "RA": "2026-10-02"}, retrieved_at="2026-10-03T00:00:00Z", **kw)

    def test_registry_never_changes_posture_or_findings_matrix(self):
        regs = [("INA000000201", "Gamma Wealth Advisers Private Limited"), ("INA000000999", ""), ("INH000000301", "Delta Capital Private Limited"), ("junk", "x"), (None, None), ("INA000000201", "Someone Else")]
        for sit, text in itertools.product(SITUATIONS, (SCAM, "hello", "")):
            base = journey({"situation": sit, "text": text}); self.assertIsNone(base["registry"])
            for n, nm in regs:
                for mode in (None, "unavailable", "error", "garbage"):
                    modes = {k: mode for k in ("IA", "RA", "IA_INACTIVE", "RA_INACTIVE")} if mode else None
                    s = FixtureSource([dict(x) for x in FX], modes=modes)
                    r = journey({"situation": sit, "text": text}, s, {"number": n, "name": nm})
                    self.assertEqual(journey_violations(r), [], (sit, n, mode))
                    for k in ("posture", "headline", "claims", "indicators", "urgent_steps", "steps"): self.assertEqual(r[k], base[k], (k, sit, n, mode))
                    if sit in ("PAID_MONEY", "SHARED_CREDENTIALS", "ACCESS_GRANTED", "UNSURE", None): self.assertIsNone(r["registry"])
                    elif r["registry"]: self.assertEqual(r["registry"]["effect_on_message_result"], "none"); self.assertIn("does not show who contacted you", r["registry"]["reminder"])

    def test_registered_intermediary_impersonation_stays_high_concern(self):
        r = journey({"situation": "NO_ACTION_YET", "text": SCAM}, self.src(), {"number": "INA000000201", "name": "Gamma Wealth Advisers Private Limited"})
        self.assertEqual(r["registry"]["card"]["status"], "CONFIRMED_IN_REGISTER"); self.assertEqual(r["posture"], "HIGH_CONCERN")

    def test_registry_failure_changes_nothing_else(self):
        base = journey({"situation": "NO_ACTION_YET", "text": SCAM})
        class Boom:
            def lookup(self, *a): raise RuntimeError("x")
        r = journey({"situation": "NO_ACTION_YET", "text": SCAM}, Boom(), {"number": "INA000000201"})
        self.assertEqual(r["posture"], base["posture"]); self.assertNotEqual(r["registry"]["card"]["status"] if r["registry"] else "NONE", "CONFIRMED_IN_REGISTER")


class TestS1Gate(unittest.TestCase):
    def test_s1_suite_has_no_critical_unsafe_and_no_technical_failure(self):
        """Development-set gate (79 internally authored cases, post-hoc fixes applied): must keep critical_unsafe == 0 and technical_failure == 0. NOT independent validation."""
        out = tempfile.mkdtemp()
        p = subprocess.run([sys.executable, "-B", "run_suite.py", "cases_s1.jsonl", out], cwd=os.path.join(RC, "eval"), capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])
        with open(os.path.join(out, "rc_results.json")) as f: s = json.load(f)["summary"]
        self.assertEqual(s["n"], 79); self.assertEqual(s["critical_unsafe"], 0, s["critical_unsafe_cases"]); self.assertEqual(s["technical_failure"], 0, s["technical_failure_cases"]); self.assertEqual(s["missing_guidance"], 0)
        self.assertLessEqual(s["incorrect_classification"], 6, s["incorrect_classification_cases"])


if __name__ == "__main__":
    unittest.main()
