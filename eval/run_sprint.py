# -*- coding: utf-8 -*-
"""Runs eval/cases_sprint_adjacent.jsonl through an engine directory (default: this rc2). Usage: python3 -B run_sprint.py <engine_dir> <out.json>. Read-only on the engine dir. Clock pinned to 2026-10-03."""
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__)); eng = os.path.abspath(sys.argv[1]); out = sys.argv[2]
sys.dont_write_bytecode = True; sys.path.insert(0, eng)
from saathi_rc import clock
from saathi_rc.engine import analyze, VERSION
rows = []
with clock.frozen("2026-10-03"):
    for l in open(os.path.join(here, "cases_sprint_adjacent.jsonl"), encoding="utf-8"):
        c = json.loads(l)
        r = analyze({"situation": c["situation"], "text": c["text"], "output_language": "en"})
        post = r["posture"]; route = "ESCALATE" if post == "ESCALATE" else ("ASK" if post == "ASK_FOLLOWUP" else "NORMAL")
        urg = [s["action_id"] for s in r.get("urgent_steps", [])]
        inc = r.get("incident") or {}
        ok = {"ESC": route == "ESCALATE", "NOT_ESC": route != "ESCALATE", "STOP": bool(urg) and urg[0] == "A_STOP_PAYMENT", "TRADEOFF": None}[c["must"]]
        rows.append({"id": c["id"], "group": c["group"], "must": c["must"], "text": c["text"], "route": route, "posture": post, "urgent": urg, "state": inc.get("state"), "risk_context": inc.get("risk_context"), "pass": ok, "validation_failed": r.get("provenance", {}).get("validation_failed", False)})
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
json.dump({"engine_dir": eng, "version": VERSION, "rows": rows}, open(out, "w"), indent=1, ensure_ascii=False)
sc = [r for r in rows if r["pass"] is not None]
print(eng, VERSION, "scored", len(sc), "pass", sum(r["pass"] for r in sc), "fail", [r["id"] for r in sc if not r["pass"]], "tradeoff", [(r["id"], r["route"]) for r in rows if r["pass"] is None])
