"""Adapter exposing the rc engine to tests/issue_checks.py."""
import datetime as dt, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from saathi_rc import clock
from saathi_rc.engine import analyze
from saathi_rc.journey import journey
from saathi_rc.registry.source import FixtureSource
from saathi_rc.registry.engine import analyze_v03
from saathi_rc.registry.api import check_registration
from sources_replay import RecordedSource, FaultSource

NOW = dt.datetime(2026, 10, 3, 6, 0, tzinfo=dt.timezone.utc)
BAD = ("CONTRADICTED", "MIXED", "INSUFFICIENT", "NOT_ASSESSED")


class RCAdapter:
    supports_clock = True

    def message(self, situation, text, lang="en", today=None):
        with clock.frozen(today or "2026-10-03"):
            r = analyze({"situation": situation, "text": text, "output_language": lang})
        blob = "\n".join([r["headline"], r["summary"]] + [a["text"] for a in r["urgent_steps"] + r["steps"]] + [i["note"] for i in r["indicators"]] + [c["explanation"] for c in r["claims"]] + r["limitations"])
        return dict(posture=r["posture"], urgent_ids=[a["action_id"] for a in r["urgent_steps"]], step_ids=[a["action_id"] for a in r["steps"]], followup=r["posture"] == "ASK_FOLLOWUP",
                    clean=r["posture"] in ("NOT_VERIFIED", "NO_INDICATORS_FOUND", "ABSTAIN"), indicators=len(r["indicators"]), unresolved=any(c["state"] in BAD for c in r["claims"]),
                    claim_states=[c["state"] for c in r["claims"]], unavailable=[u["code"] for u in r["unavailable"]], text=blob, raw=r)

    def _src(self, entries, fault=None):
        s = FixtureSource([dict(e) for e in entries], as_of={"IA": "2026-10-02", "RA": "2026-10-02"}, retrieved_at="2026-10-03T00:00:00Z")
        return FaultSource(s, {k: fault for k in ("IA", "RA", "IA_INACTIVE", "RA_INACTIVE")}) if fault else s

    def registry(self, number, name, entries, fault=None):
        r = check_registration(number, name, None, self._src(entries, fault), "en", now=NOW)["card"]
        return {"status": r["status"], "reason": r.get("reason"), "record_exposed": bool(r.get("register_record") or r.get("candidates"))}

    def journey(self, situation, text, entries, number, name):
        with clock.frozen("2026-10-03"):
            src = self._src(entries)
            req = {"situation": situation, "text": text}
            with_reg = journey(req, src, {"number": number, "name": name})
            without = journey(req)
        reg = with_reg["registry"]
        return {"registry_status": reg["card"]["status"] if reg else None, "message_concern": with_reg["posture"] in ("SOME_CONCERN", "HIGH_CONCERN"),
                "reminder_present": bool(reg and "does not show who contacted you" in reg["reminder"]), "posture_same_without_registry": with_reg["posture"] == without["posture"]}

    def replay_pasted(self, text):
        r = analyze_v03({"situation": "NO_ACTION_YET", "pasted_text": text, "language": "en"}, RecordedSource(), now=NOW)
        return {"status": r["source_verification"]["status"], "validation_failed": r.get("validation_failed")}
