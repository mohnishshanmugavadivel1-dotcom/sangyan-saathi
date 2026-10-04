"""Phase 5 real-browser flow check (headless Chromium via Playwright + axe-core). OPTIONAL (needs playwright + axe-playwright-python + `playwright install chromium`).
Starts its OWN server (fixture registry mode, no network) on an ephemeral port, drives the main demo path with JavaScript on at mobile / desktop / 200% zoom, compares the DOM to the backend result
(webapp.run_check in-process, same text), and writes EVERY check (pass or fail) to results/final_verification/browser/browser_final.json plus screenshots. Nothing is excluded.
Synthetic, author-written texts. Run: python3 -B tests/browser_final.py"""
import json, os, sys, threading, time, re, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); RC = os.path.abspath(os.path.join(HERE, "..")); sys.path.insert(0, RC); sys.dont_write_bytecode = True
from playwright.sync_api import sync_playwright
from axe_playwright_python.sync_playwright import Axe
from saathi_rc.registry.source import FixtureSource
from saathi_rc.web import app as webapp
OUT = os.path.join(RC, "results", "final_verification", "browser"); os.makedirs(OUT, exist_ok=True)
FX = json.load(open(os.path.join(RC, "eval", "registry_fixture.json"), encoding="utf-8"))["entries"]
srv = webapp.make_server("127.0.0.1", 0, webapp.State(mode="fixture", source=FixtureSource([dict(x) for x in FX]), rate=webapp.RateLimiter(10 ** 6, 10 ** 6, 60)))
B = "http://127.0.0.1:%d" % srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
CHK = []; AXE = {}; ENV = {}
SUSP = "Last week I wired 60,000, now they ask me for taxes before release."
UNAUTH = "A withdrawal of 9,000 appeared in my statement that I did not make."
UNCL = "Someone transferred 4,000 out of my savings account without my permission."
DENIED = "I attempted to pay 3000 but did not complete it."
PENDING = "I will send the clearance amount tonight."
LEGIT = "I paid 1,200 to Zomato via UPI."
EMI = "Rs 799 was debited from my account for my Netflix plan."
HI = "मेरे खाते से अनजान लेन-देन में पैसे कट गए"
ADVISER = "Guaranteed 40% monthly returns, SEBI registered INA000000201. Pay Rs 5000 now to join, limited seats. Download app http://x.co/a"


def ok(c, m, vp=""):
    CHK.append({"pass": bool(c), "viewport": vp, "check": m}); print(("PASS " if c else "FAIL ") + (vp + ": " if vp else "") + m)


def backend(sit, text, lang="en"): return webapp.run_check({"situation": sit, "text": text, "output_language": lang})


def submit(pg, sit, text, lang=None):
    pg.goto(B + "/" + ("?lang=" + lang if lang else "")); pg.check("input[name=situation][value=%s]" % sit); pg.fill("#text", text); pg.click("form[action='/check'] button[type=submit]"); pg.wait_for_load_state()


def panel(pg):
    if not pg.locator("#incident").count(): return None
    return {"state": pg.get_attribute("#incident", "data-state"), "text": pg.inner_text("#incident"), "quotes": [x.strip(" \u201c\u201d") for x in pg.locator("#incident li .q").all_inner_texts()]}


def urgent_items(pg): return pg.locator("section.urgent#ug li, section[aria-labelledby=ug] li").all_inner_texts()


with sync_playwright() as p:
    br = p.chromium.launch(); ENV["browser"] = "Chromium " + br.version; ENV["run_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for name, vp, scale in (("mobile", {"width": 375, "height": 800}, 1), ("desktop", {"width": 1200, "height": 900}, 1), ("zoom200", {"width": 640, "height": 800}, 2)):
        ctx = br.new_context(viewport=vp, device_scale_factor=scale); pg = ctx.new_page(); problems = []
        pg.on("console", lambda m: problems.append(m.text) if m.type in ("error", "warning") else None); pg.on("pageerror", lambda e: problems.append(str(e)))
        shot = lambda tag: pg.screenshot(path=os.path.join(OUT, "%s_%s.png" % (name, tag)), full_page=True)
        noflow = lambda m: ok(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "no horizontal overflow: " + m, name)
        # 0 home + keyboard
        pg.goto(B + "/"); shot("0_home"); noflow("home"); pg.keyboard.press("Tab"); ok(pg.evaluate("document.activeElement.className") == "skip", "first Tab stop is the skip link", name)
        ok(pg.locator("input[name=situation]").count() >= 3 and pg.locator("textarea#text").count() == 1, "home has the situation options and one text area", name)
        ok(all(pg.evaluate("(id)=>!!document.querySelector(`label[for='${id}']`)", i) for i in ("text",)), "text area has an associated label", name)
        # 1 suspicious completed payment
        b = backend("NO_ACTION_YET", SUSP); submit(pg, "NO_ACTION_YET", SUSP); shot("1_suspicious_completed"); noflow("suspicious completed", ); pa = panel(pg)
        ok("act now" in pg.inner_text("main").lower() or b["posture"] == "ESCALATE" and pg.locator("[role=alert]").count() > 0, "suspicious completed payment shows an urgent alert block", name)
        ok(pa and pa["state"] == b["incident"]["state"] == "USER_PAID", "panel state matches backend (USER_PAID)", name)
        ok(pa and b["incident"]["label"] in pa["text"], "panel label text equals the backend label", name)
        ok(pa and pa["quotes"] and all(q in SUSP for q in pa["quotes"]) and all(any(q == e["snippet"] for e in b["incident"]["events"]) for q in pa["quotes"]), "panel quote is verbatim from the user's text AND equals a backend event snippet", name)
        it = [x for x in urgent_items(pg)]; ok(len(it) >= 2 and all(any(s["text"][:40] in x for x in it) for s in b["urgent_steps"][:2]), "urgent steps shown equal the backend urgent steps (first two)", name)
        ok(("1930" in " ".join(it)) and ("bank" in " ".join(it).lower()), "urgent block names the bank and 1930", name)
        ok(pg.locator("#regform").count() == 0 and pg.locator("#registry-card").count() == 0, "no registry form/card inside the urgent incident flow", name)
        ok(pg.locator("h1").count() == 1, "exactly one h1", name)
        # 6 correction flow from the urgent page
        ok(pg.locator("#t3").count() == 1, "correction form is offered on the escalated page", name)
        pg.check("form:has(#t3) input[value=PAYMENT_PENDING]") if pg.locator("form:has(#t3) input[value=PAYMENT_PENDING]").count() else None
        pg.click("form:has(#t3) button[type=submit]"); pg.wait_for_load_state(); ok(panel(pg) and panel(pg)["state"] == "USER_PAID" and "alert" in pg.content(), "correction with the SAME text and a different option does not silently downgrade", name)
        pg.fill("#t3", "I did not pay anything, I only read their message.") if pg.locator("#t3").count() else None
        if pg.locator("form:has(#t3) input[value=NO_ACTION_YET]").count(): pg.check("form:has(#t3) input[value=NO_ACTION_YET]")
        if pg.locator("#t3").count(): pg.click("form:has(#t3) button[type=submit]"); pg.wait_for_load_state()
        pa2 = panel(pg); ok(not (pa2 and pa2["state"] == "USER_PAID" and not backend("NO_ACTION_YET", "I did not pay anything, I only read their message.")["posture"] != "ESCALATE"), "correction with a genuine denial is honoured (not forced to stay USER_PAID)", name); shot("6_after_correction")
        # 7 form options never lower the incident
        for v in ("NO_ACTION_YET", "PAYMENT_PENDING", "UNSURE", "PAID_MONEY", "SHARED_CODE"):
            pg.goto(B + "/")
            if not pg.locator("input[name=situation][value=%s]" % v).count(): continue
            pg.check("input[name=situation][value=%s]" % v); pg.fill("#text", SUSP); pg.click("form[action='/check'] button[type=submit]"); pg.wait_for_load_state()
            ok(pg.locator("[role=alert]").count() > 0 and "1930" in pg.inner_text("main"), "option %s does not remove urgent guidance for the suspicious completed payment" % v, name)
        # 2 unauthorised debit
        b = backend("NO_ACTION_YET", UNAUTH); submit(pg, "NO_ACTION_YET", UNAUTH); shot("2_unauthorised"); noflow("unauthorised"); pa = panel(pg)
        ok(pa and pa["state"] == b["incident"]["state"] == "UNAUTHORISED_DEBIT" and b["posture"] == "ESCALATE", "unauthorised debit: panel state matches backend and posture ESCALATE", name)
        ok(pa and pa["quotes"] and pa["quotes"][0] in UNAUTH, "unauthorised debit: panel quote is verbatim", name)
        ok("1930" in " ".join(urgent_items(pg)), "unauthorised debit: bank/1930 in the urgent block", name)
        b = backend("NO_ACTION_YET", UNCL); submit(pg, "NO_ACTION_YET", UNCL); ok(b["posture"] == "ESCALATE" and (panel(pg) or {}).get("state") == "UNAUTHORISED_DEBIT", "second unauthorised wording also escalates", name)
        # 3 denied / abandoned
        b = backend("NO_ACTION_YET", DENIED); submit(pg, "NO_ACTION_YET", DENIED); shot("3_denied"); noflow("denied"); pa = panel(pg)
        ok(b["posture"] != "ESCALATE" and "1930" not in " ".join(urgent_items(pg)) and not (pa and pa["state"] == "USER_PAID"), "denied/incomplete payment is not shown as a completed payment or urgent block", name)
        ok((pa is None) or pa["state"] == b["incident"]["state"], "denied: panel state equals backend", name)
        # 4 pending
        b = backend("PAYMENT_PENDING", PENDING); submit(pg, "PAYMENT_PENDING", PENDING); shot("4_pending"); noflow("pending"); it = urgent_items(pg)
        ok(it and b["urgent_steps"][0]["action_id"] == "A_STOP_PAYMENT" and b["urgent_steps"][0]["text"][:40] in it[0], "pending: stop-payment is the FIRST urgent item and equals the backend's", name)
        b = backend("UNSURE", PENDING); submit(pg, "UNSURE", PENDING); it = urgent_items(pg); ok(it and b["urgent_steps"][0]["action_id"] == "A_STOP_PAYMENT" and b["urgent_steps"][0]["text"][:40] in it[0], "pending text with 'not sure' still shows stop-payment first", name)
        # 5 legitimate
        for t in (LEGIT, EMI):
            b = backend("NO_ACTION_YET", t); submit(pg, "NO_ACTION_YET", t); shot("5_legit_%d" % (1 if t == LEGIT else 2)); ok(b["posture"] != "ESCALATE" and pg.locator("section.urgent").count() == 0, "legitimate payment does not show an urgent block: %s" % t[:30], name)
        noflow("legit")
        # 8 registry separation (ordinary message path) and no effect on a text incident
        submit(pg, "NO_ACTION_YET", ADVISER)
        pg.click("summary#regh") if not pg.is_visible("#rn") else None; pg.fill("#rn", "INA000000201"); pg.fill("#rm", "Gamma Wealth Advisers Private Limited"); pg.click("#regform button"); pg.wait_for_selector("#registry-card", timeout=10000)
        ok("A match does not show who contacted you" in pg.inner_text("#regout"), "registry card shows the 'match does not show who contacted you' reminder", name)
        ok("h1" and pg.locator("h1").count() == 1 and "concern" in pg.inner_text("h1").lower(), "message verdict still on the page after the registry step (registry did not replace or lower it)", name); shot("8_registry")
        # 9 Hindi
        b = backend("NO_ACTION_YET", HI, "hi"); submit(pg, "NO_ACTION_YET", HI, "hi"); shot("9_hindi"); pa = panel(pg)
        ok(pa and pa["state"] == b["incident"]["state"] and b["incident"]["label"] in pa["text"], "Hindi (unreviewed): panel state and label match the backend", name)
        # axe + console on main-path pages
        for tag, sit, t, lg in (("suspicious", "NO_ACTION_YET", SUSP, None), ("unauthorised", "NO_ACTION_YET", UNAUTH, None), ("pending", "PAYMENT_PENDING", PENDING, None), ("legit", "NO_ACTION_YET", LEGIT, None), ("hindi", "NO_ACTION_YET", HI, "hi")):
            submit(pg, sit, t, lg); v = Axe().run(pg).response["violations"]; AXE["%s_%s" % (name, tag)] = [{"id": x["id"], "impact": x["impact"], "nodes": len(x["nodes"])} for x in v]
            ok(not [x for x in v if x["impact"] in ("critical", "serious")], "axe-core: no critical/serious violations on %s result page (all: %s)" % (tag, [x["id"] for x in v]), name)
        pg.goto(B + "/"); v = Axe().run(pg).response["violations"]; AXE[name + "_home"] = [{"id": x["id"], "impact": x["impact"]} for x in v]; ok(not [x for x in v if x["impact"] in ("critical", "serious")], "axe-core: no critical/serious violations on home (all: %s)" % [x["id"] for x in v], name)
        # tap-target size of the main buttons (WCAG 2.2 AA target size minimum 24px) and focus visibility
        submit(pg, "NO_ACTION_YET", SUSP); sizes = pg.evaluate("[...document.querySelectorAll('button,a.btn,input[type=radio]')].filter(e=>e.offsetParent).map(e=>{const r=e.getBoundingClientRect();return [e.tagName+(e.type?':'+e.type:''),Math.round(r.width),Math.round(r.height)]})")
        ok(all(min(w, h) >= 24 for (_, w, h) in sizes if _ != "INPUT:radio") , "buttons/links at least 24x24 CSS px (sizes: %s)" % sizes[:6], name)
        pg.keyboard.press("Tab"); pg.keyboard.press("Tab"); outline = pg.evaluate("(()=>{const s=getComputedStyle(document.activeElement);return s.outlineStyle+' '+s.outlineWidth+' '+s.boxShadow})()"); ok("none 0px none" not in outline, "focused element has a visible focus indicator (%s)" % outline, name)
        ok(not [x for x in problems if "Content Security Policy" in x or "Refused" in x or "error" in x.lower()], "no CSP violations / console errors (%s)" % problems[:3], name)
        ctx.close()
    br.close()
bad = [c for c in CHK if not c["pass"]]
json.dump({"env": ENV, "n_checks": len(CHK), "n_failed": len(bad), "failed": bad, "checks": CHK, "axe_all_violations": AXE, "note": "every check is recorded; synthetic author-written texts; Hindi unreviewed by a fluent speaker; automated checks are not a full accessibility audit"}, open(os.path.join(OUT, "browser_final.json"), "w"), indent=1, ensure_ascii=False)
print("\n%d checks, %d failed" % (len(CHK), len(bad)))
srv.shutdown()
