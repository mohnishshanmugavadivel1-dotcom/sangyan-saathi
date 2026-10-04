# -*- coding: utf-8 -*-
"""Phase 1 reproduction/trace of S3b S30 on the FROZEN pre-incident engine. Read-only; writes results/incident_state/s30_trace.json.
Run with S3_ENGINE_RC=<dir> to point at an extracted pre-incident snapshot after the engine has changed."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); RC = os.environ.get("S3_ENGINE_RC") or os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, RC); sys.dont_write_bytecode = True
from saathi_rc import clock, cues
from saathi_rc.engine import analyze
from saathi_rc.core.normalize import normalize
from saathi_rc.core.pipeline import analyze as core, get_corpus
T = "Last week I wired 60,000, now they ask me for taxes before release."
out = {"engine_dir": RC, "text": T}
with clock.frozen("2026-10-03"):
    for sit in ("NO_ACTION_YET", "PAYMENT_PENDING", "PAID_MONEY", "UNSURE"):
        r = analyze({"situation": sit, "text": T, "output_language": "en"})
        out["final_" + sit] = {"posture": r["posture"], "urgent": [s["action_id"] for s in r["urgent_steps"]], "steps": [(s["action_id"], s["conditional"]) for s in r["steps"]], "indicators": [i["indicator"] for i in r["indicators"]], "summary": r["summary"], "provenance_keys": {k: r["provenance"].get(k) for k in ("pending", "pending_cues", "negated_statements_ignored", "followup_reason", "request_surface", "core_posture")}}
    n = normalize(T, "text")
    out["stage1_normalize"] = {"language": n.get("language"), "entities": {k: v for k, v in n["entities"].items() if v}}
    out["stage2_past_action_cues"] = list(cues.past_action_cues(n["text"]))
    out["stage2_situation_conflict_cues"] = [list(x) for x in cues.situation_conflict_cues(n["text"])]
    out["stage2_other_cues"] = cues.other_cues(n["text"])
    out["stage3_pending_cues"] = cues.pending_cues(n["text"])
    c = core({"text": T, "user_situation": "NO_ACTION_YET", "input_type": "text", "output_language": "en"}, get_corpus())
    out["stage4_core"] = {"posture": c["posture"], "indicators": [i["indicator"] for i in c["indicators"]], "claims": [x["claim_type"] for x in c["claims"]]}
    out["stage5_surface"] = cues.surface_of(n)
    # verb-coverage probe: which completed-payment phrasings does the legacy cue layer see? (exploratory, authored here, not an evaluation)
    probe = ["I paid 5000", "I sent 5000", "I transferred 5000", "I deposited 5000", "I wired 5000", "I remitted 5000", "I made a payment of 5000", "I settled the fee of 5000", "I did the transfer",
             "I credited the amount to their account", "I topped up the wallet with 5000", "I forwarded the money", "I cleared the dues", "I put in 5000", "I handed over 5000 in cash", "5000 left my account after I approved the request",
             "I have already paid", "main ne paise bhej diye", "maine paise transfer kar diye", "मैंने रकम जमा कर दी", "मैंने पैसे ट्रांसफर किए"]
    out["verb_coverage_probe"] = [{"text": p, "cues": cues.situation_conflict_cues(p)[0]} for p in probe]
    # attribution probe: the cue layer only checks that a first-person word appears within 70 characters BEFORE the verb
    attr = ["The broker transferred money to my account.", "My father paid the amount.", "They said they had already paid.", "I never paid them.", "I am about to pay. The account they gave me is new.",
            "He said I sent the money last week.", "I told them my brother paid it."]
    out["attribution_probe"] = [{"text": p, "cues": cues.situation_conflict_cues(p)[0], "negated": cues.situation_conflict_cues(p)[1]} for p in attr]
os.makedirs(os.path.join(HERE, "..", "results", "incident_state"), exist_ok=True)
json.dump(out, open(os.path.join(HERE, "..", "results", "incident_state", "s30_trace.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: out[k] for k in out if k.startswith("final_") or k.startswith("stage")}, ensure_ascii=False)[:1800])
for x in out["verb_coverage_probe"]: print("COVER", bool(x["cues"]), x["text"])
for x in out["attribution_probe"]: print("ATTR", x["cues"], x["negated"], x["text"])
