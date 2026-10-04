"""Run a suite (JSONL) against the rc engine with the shared scorer. Deterministic: clock frozen to 2026-10-03 unless a case sets `clock`.
Usage: python3 run_suite.py cases_s1.jsonl results/<name>   (from rc/eval)"""
import json, os, sys, hashlib, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
from saathi_rc import clock
from saathi_rc.journey import journey, journey_violations
from saathi_rc.validate import _strings
from saathi_rc.registry.source import FixtureSource
from score import classify, disclosure_check, summarize
import re

REG_FIXTURE = json.load(open(os.path.join(HERE, "registry_fixture.json")))
DEFAULT_DAY = "2026-10-03"


def tree_hash(root, skip_web=False):
    h = hashlib.sha256()
    for d, dirs, fs in sorted(os.walk(root)):
        if "__pycache__" in d: continue
        if skip_web and os.sep + "web" in d.replace(root, ""): continue
        for f in sorted(fs):
            if f.endswith((".py", ".json")):
                p = os.path.join(d, f); h.update(os.path.relpath(p, root).encode()); h.update(open(p, "rb").read())
    return h.hexdigest()


def fixture_source(mode=None):
    modes = {}
    if mode == "unavailable":
        modes = {k: "unavailable" for k in ("IA", "RA", "IA_INACTIVE", "RA_INACTIVE")}
    return FixtureSource([dict(e) for e in REG_FIXTURE["entries"]], as_of={"IA": "2026-10-02", "RA": "2026-10-02"}, modes=modes, retrieved_at="2026-10-03T00:00:00Z")


def blob_of(r):
    parts = _strings(r) + [c.get("explanation", "") for c in r.get("claims", [])]
    reg = r.get("registry")
    if reg:
        c = reg["card"]; parts += [c.get("headline", ""), c.get("means", ""), c.get("does_not_mean", ""), reg.get("reminder", "")]
    return "\n".join(parts)


def view(r):
    bad = ("CONTRADICTED", "MIXED", "INSUFFICIENT", "NOT_ASSESSED")
    b = blob_of(r)
    return dict(posture=r["posture"], urgent_ids=[a["action_id"] for a in r["urgent_steps"]], step_ids=[a["action_id"] for a in r["steps"]], blob=b, indicators=len(r["indicators"]),
                unresolved=any(c["state"] in bad for c in r["claims"]), validation_failed=r["provenance"].get("validation_failed", False), validation_errors=r["provenance"].get("validation_errors", []),
                urgent_first=r["block_order"][0] == "urgent_steps", disclosed_language_limit=bool(re.search(r"(?i)limited|not supported", b)),
                unavailable=[u["code"] for u in r["unavailable"]])


def run(suite):
    rows = []
    for c in [json.loads(l) for l in open(suite, encoding="utf-8")]:
        extra = {}
        try:
            with clock.frozen(c.get("clock") or DEFAULT_DAY):
                req = {"situation": c["situation"], "text": c["text"], "output_language": c.get("output_language", "en"), "request_id": c["id"]}
                plain = journey(req)
                rr = None
                if c.get("registry"):
                    rr = dict(c["registry"]); r = journey(req, fixture_source(c.get("registry_mode")), rr)
                else:
                    r = plain
            v = view(r)
        except Exception as e:
            r = {}; v = dict(posture="EXCEPTION", error=True, blob="", urgent_ids=[], step_ids=[]); extra["exception"] = repr(e)[:200]
        f = classify(c, v); disclosure_check(c, v, f)
        if not v.get("error"):
            jv = journey_violations(r)
            for x in jv: f["critical_unsafe"].append("journey invariant: " + x)
            for s in c.get("expect_no_echo", []):
                if s in json.dumps(r, ensure_ascii=False): f["critical_unsafe"].append("sensitive value echoed")
            if c.get("expect_stale") and "SOURCES_STALE" not in v["unavailable"]: f["incorrect_classification"].append("stale snapshot not flagged")
            if c.get("registry"):
                st = (r.get("registry") or {}).get("card", {}).get("status")
                want = c.get("expect_registry_after") or c.get("expect_registry")
                if st != want: f["incorrect_classification"].append("registry status %s, expected %s" % (st, want))
                if plain["posture"] != r["posture"] or plain["claims"] != r["claims"] or plain["indicators"] != r["indicators"]:
                    f["critical_unsafe"].append("register step changed the message result")
                if r.get("registry") and r["block_order"].index("registry") < r["block_order"].index("urgent_steps"): f["critical_unsafe"].append("registry above urgent steps")
            if c.get("expect_reg_numbers") and len(r.get("registry_offer", {}).get("numbers", [])) != c["expect_reg_numbers"]: f["incorrect_classification"].append("registry number not offered")
        rows.append({"id": c["id"], "category": c["category"], "truth": c["truth"], "posture": v["posture"], "findings": f, "extra": extra})
    return rows


if __name__ == "__main__":
    suite, outdir = sys.argv[1], sys.argv[2]; os.makedirs(outdir, exist_ok=True)
    code_hash = tree_hash(os.path.join(HERE, "..", "saathi_rc"))
    engine_hash = tree_hash(os.path.join(HERE, "..", "saathi_rc"), skip_web=True)
    fz_path = os.path.join(HERE, "FREEZE_" + os.path.basename(suite).split("_")[1].split(".")[0].upper() + ".json")
    post_hoc = "--post-hoc" in sys.argv   # re-run after fixes: allowed, but recorded as NOT a clean frozen-engine run
    if os.path.exists(fz_path) and not post_hoc:
        fz = json.load(open(fz_path)); 
        if fz.get("engine_tree_sha256_excl_web"):
            assert fz["suite_sha256"] == hashlib.sha256(open(suite, "rb").read()).hexdigest(), "suite changed after freeze"
            assert fz["engine_tree_sha256_excl_web"] == engine_hash, "engine code changed after the freeze recorded for this suite"
            marker = os.path.join(HERE, "RUN_DONE_" + os.path.basename(fz_path))
            assert not os.path.exists(marker), "single-run rule: this frozen suite has already been run"
            with open(marker, "w") as mf: mf.write("run at %s into %s\n" % (dt.datetime.now(dt.timezone.utc).isoformat(), outdir))
    rows = run(suite); s = summarize(rows)
    json.dump({"engine": "saathi_rc", "suite": os.path.basename(suite), "suite_sha256": hashlib.sha256(open(suite, "rb").read()).hexdigest(), "clock": DEFAULT_DAY, "engine_tree_sha256": code_hash, "post_hoc_rerun_after_fixes": post_hoc, "engine_tree_sha256_excl_web": engine_hash, "summary": s, "rows": rows},
              open(os.path.join(outdir, "rc_results.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in s.items() if not k.endswith("_cases")}))
    for b in ("critical_unsafe", "incorrect_classification", "missing_guidance", "technical_failure"):
        print(" ", b, s[b + "_cases"])
    if "-v" in sys.argv:
        for r in rows:
            fs = {k: v for k, v in r["findings"].items() if v and k != "correct_uncertainty"}
            if fs: print(r["id"], r["posture"], fs)
