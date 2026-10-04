# -*- coding: utf-8 -*-
"""Fresh generalisation probe (S4), authored AFTER the engine was tuned and run ONCE, with no engine change afterwards.
24 new sentences written by the engine's author (so NOT independent). Purpose: show roughly how the reader behaves on wording nobody tuned it on.
Acceptable routes per probe: E = ESCALATE, A = ASK_FOLLOWUP, N = normal analysis (not ESCALATE, no follow-up), P = stop-payment block first. Hindi/Hinglish: unreviewed by a fluent speaker.
Run: python3 -B eval/probe_fresh.py  (writes results/incident_state/fresh_probe/raw.jsonl and prints a summary)"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); RC = os.path.abspath(os.path.join(HERE, "..")); sys.path.insert(0, RC); sys.dont_write_bytecode = True
from saathi_rc import clock
from saathi_rc.journey import journey
P = [("F01", "I transferred 45,000 to the trader yesterday and now his phone is off.", "E", "E", "completed + trouble"),
     ("F02", "Paid 15k to an unknown account as a processing fee, they are asking for 15k more.", "EA", "E", "subject-less verb (designed limit: no user state)"),
     ("F03", "I gave my card number and CVV to the caller.", "E", "E", "credential"),
     ("F04", "I read out the OTP when the bank executive asked.", "E", "E", "credential"),
     ("F05", "My account was debited 20,000 and I did not authorise it.", "EA", "E", "unauthorised debit, no payment verb by user"),
     ("F06", "I sent Rs 8,000 to the Telegram admin and he wants a further 8,000 to withdraw.", "E", "E", "completed + demand"),
     ("F07", "मैंने अनजान व्यक्ति को 10,000 रुपये भेज दिए और अब वह और माँग रहा है", "E", "E", "Hindi"),
     ("F08", "maine OTP bata diya, ab paise kat gaye", "E", "E", "Hinglish"),
     ("F09", "My brother sent 5,000 to a scammer.", "AN", "N", "third party"),
     ("F10", "The caller claims I already paid the fee.", "AN", "N", "sender claim"),
     ("F11", "I haven't transferred a rupee and I won't.", "N", "N", "denial"),
     ("F12", "I refused to give the OTP.", "N", "N", "refusal"),
     ("F13", "I sent the rent to my landlord on the 1st.", "AN", "N", "legit"),
     ("F14", "I paid the electricity bill by UPI this morning.", "AN", "N", "legit"),
     ("F15", "She transferred the tuition money to the college.", "N", "N", "legit third party"),
     ("F16", "I was going to wire the money but my bank stopped me.", "N", "N", "aborted"),
     ("F17", "I will send 10,000 to the broker tomorrow.", "P", "P", "pending"),
     ("F18", "I shared the document with my CA.", "N", "N", "not a credential"),
     ("F19", "I told my wife about the offer.", "N", "N", "not a payment"),
     ("F20", "I am unsure if I paid twice for the same order.", "A", "A", "uncertain, legit-looking"),
     ("F21", "He wants me to deposit 25,000 today, should I?", "P", "P", "pending ask"),
     ("F22", "I put 30,000 into the scheme last month and they now say there is a withdrawal tax.", "E", "E", "completed + demand, no 'paid' verb"),
     ("F23", "They messaged that my payment was received. I did not make any payment.", "N", "N", "claim + denial"),
     ("F24", "I entered my UPI PIN on the page the caller sent.", "E", "E", "credential via page")]


def route(r):
    u = [s["action_id"] for s in r["urgent_steps"]]
    if r["posture"] == "ESCALATE": return "E"
    if r["posture"] == "ASK_FOLLOWUP": return "A"
    if u[:1] == ["A_STOP_PAYMENT"]: return "P"
    return "N"


def main():
    out = os.path.join(RC, "results", "incident_state", "fresh_probe"); os.makedirs(out, exist_ok=True); rows = []
    with clock.frozen("2026-10-03"):
        for pid, text, ok, ideal, note in P:
            r = journey({"situation": "NO_ACTION_YET", "text": text, "output_language": "en"}); rt = route(r); inc = r.get("incident")
            rows.append({"id": pid, "text": text, "acceptable": ok, "ideal": ideal, "note": note, "route": rt, "in_acceptable": rt in ok, "state": (inc or {}).get("state"), "posture": r["posture"], "urgent": [s["action_id"] for s in r["urgent_steps"]][:3]})
    with open(os.path.join(out, "raw.jsonl"), "w", encoding="utf-8") as f:
        for x in rows: f.write(json.dumps(x, ensure_ascii=False) + "\n")
    bad = [x for x in rows if not x["in_acceptable"]]
    print("fresh probe: %d/%d in acceptable set; ideal route exactly: %d/%d" % (len(rows) - len(bad), len(rows), sum(x["route"] == x["ideal"] for x in rows), len(rows)))
    for x in bad: print("  MISS", x["id"], x["route"], x["state"], "|", x["text"][:80], "|", x["note"])
    print("  false escalations (E where not acceptable):", [x["id"] for x in rows if x["route"] == "E" and "E" not in x["acceptable"]])


if __name__ == "__main__":
    main()
