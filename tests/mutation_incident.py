"""S4 mutation checks: break the incident handling in one specific way and confirm tests/test_incident_state.py notices.
Run from rc/: python3 -B tests/mutation_incident.py <name> | all. Names: reader_off, actor_blind, negation_blind, panel_hidden, validator_rules_off, no_stop_payment, no_escalation, unsure_ignores_text"""
import io, os, subprocess, sys, unittest
sys.dont_write_bytecode = True; sys.path.insert(0, "."); sys.path.insert(0, "tests")
NAMES = ["reader_off", "actor_blind", "negation_blind", "panel_hidden", "validator_rules_off", "no_stop_payment", "no_escalation", "unsure_ignores_text"]
# Phase 5: mutations of the new rules, caught by tests/test_final_regressions.py (module chosen by the "@final" suffix)
NAMES += ["unauth_off@final", "context_rules_off@final", "unsure_drops_stop@final", "negation_blind@final", "panel_hidden@final", "no_stop_payment@final", "no_escalation@final"]


def apply(which):
    import re
    which = which.split("@")[0]
    from saathi_rc import incident, engine, validate as V
    from saathi_rc.web import views
    if which == "reader_off":
        o = incident.read; incident.read = lambda text, mask=None: dict(o("", mask))
    elif which == "actor_blind":
        incident.actor_before = lambda *a, **k: incident.USER
    elif which == "negation_blind":   # every negation / denial marker is treated as a completed action
        o = incident._summarise
        incident._summarise = lambda events, reversal, ab: o([dict(e, status=incident.COMPLETED) if e["status"] == incident.DENIED else e for e in events], reversal, ab)
    elif which == "panel_hidden":
        views.incident_html = lambda res, lang: ""
    elif which == "validator_rules_off":
        o = V.validate; V.validate = lambda res, corpus, ctx: [e for e in o(res, corpus, ctx) if not any(k in e for k in ("incident", "reported payment", "escalat", "UNSURE"))]
        engine.validate = V.validate
    elif which == "no_stop_payment":
        o = engine._escalation_urgent; engine._escalation_urgent = lambda lang, pending: o(lang, False)
    elif which == "no_escalation":
        engine._escalate_from_text = lambda req, lang, situation, inc, reasons, pending: engine._base(req, lang, situation, "CANNOT_ASSESS", steps=[engine.step("A_NO_PAY_NO_SHARE", lang)], summary="Could not assess.")
    elif which == "unsure_ignores_text":
        o = engine._analyze
        def a(req, lang, situation, corpus):
            if situation == "UNSURE": req = dict(req, text="")
            return o(req, lang, situation, corpus)
        engine._analyze = a
    elif which == "unauth_off":
        incident._MONEY_OUT = re.compile(r"(?!x)x")
    elif which == "context_rules_off":
        incident._SCAM_PURPOSE = incident._RETURNS_WITHHELD = incident._UNKNOWN_RECIPIENT = re.compile(r"(?!x)x")
    elif which == "unsure_drops_stop":
        o = engine._base
        def b(req, lang, situation, posture, *a, **k):
            if situation == "UNSURE" and posture == "ASK_FOLLOWUP": k["urgent"] = []
            return o(req, lang, situation, posture, *a, **k)
        engine._base = b
    else: raise SystemExit("unknown mutation")


if len(sys.argv) > 1 and sys.argv[1] == "all":
    bad = 0
    for n in NAMES:
        out = subprocess.run([sys.executable, "-B", __file__, n], capture_output=True, text=True).stdout.strip(); print(out); bad += ("failures caught: 0" in out)
    print("mutations NOT caught:", bad); sys.exit(1 if bad else 0)
which = sys.argv[1]; apply(which)
import importlib
T = importlib.import_module("tests.test_final_regressions" if which.endswith("@final") else "tests.test_incident_state")
r = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestLoader().loadTestsFromModule(T))
print(which, "-> failures caught:", len(r.failures) + len(r.errors))
