"""OPTIONAL real-browser check (headless Chromium via Playwright + axe-core). Not part of the default test run (needs: pip install playwright axe-playwright-python; playwright install chromium).
Starts its OWN server in fixture mode on an ephemeral port (no network), exercises the journey with JavaScript on, checks CSP violations / console errors, horizontal overflow at
mobile width and 200% zoom, runs axe-core, and saves screenshots to results/browser/. Usage: /path/to/venv/bin/python tests/browser_check.py"""
import json, os, sys, threading
HERE = os.path.dirname(os.path.abspath(__file__)); RC = os.path.abspath(os.path.join(HERE, "..")); sys.path.insert(0, RC); sys.dont_write_bytecode = True
from playwright.sync_api import sync_playwright
from axe_playwright_python.sync_playwright import Axe
from saathi_rc.registry.source import FixtureSource
from saathi_rc.web import app as webapp
OUT = os.path.join(RC, "results", "browser"); os.makedirs(OUT, exist_ok=True)
with open(os.path.join(RC, "eval", "registry_fixture.json"), encoding="utf-8") as f: FX = json.load(f)["entries"]
srv = webapp.make_server("127.0.0.1", 0, webapp.State(mode="fixture", source=FixtureSource([dict(x) for x in FX]), rate=webapp.RateLimiter(10 ** 6, 10 ** 6, 60)))
port = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start(); B = "http://127.0.0.1:%d" % port
MSG = "Guaranteed 40% monthly returns, SEBI registered INA000000201. Pay Rs 5000 now to join, limited seats. Download app http://x.co/a"
res = {"checks": [], "axe": {}}
def ok(c, m): res["checks"].append({"pass": bool(c), "check": m}); print(("PASS " if c else "FAIL ") + m)
with sync_playwright() as p:
    br = p.chromium.launch()
    for name, vp, scale in (("mobile", {"width": 375, "height": 800}, 1), ("desktop", {"width": 1200, "height": 900}, 1), ("zoom200", {"width": 640, "height": 800}, 2)):
        ctx = br.new_context(viewport=vp, device_scale_factor=scale); pg = ctx.new_page(); problems = []
        pg.on("console", lambda m: problems.append(m.text) if m.type in ("error", "warning") else None); pg.on("pageerror", lambda e: problems.append(str(e)))
        pg.goto(B + "/"); pg.screenshot(path=os.path.join(OUT, "%s_1_home.png" % name), full_page=True)
        ok(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "%s: home has no horizontal overflow" % name)
        pg.keyboard.press("Tab"); ok(pg.evaluate("document.activeElement.className") == "skip", "%s: first Tab stop is the skip link" % name)
        pg.check("input[value=NO_ACTION_YET]"); pg.fill("#text", MSG); pg.click("button[type=submit]"); pg.wait_for_load_state()
        pg.screenshot(path=os.path.join(OUT, "%s_2_result.png" % name), full_page=True)
        ok(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "%s: result has no horizontal overflow" % name)
        ok("high concern" in pg.inner_text("h1").lower(), "%s: result heading shows 'High concern'" % name)
        pg.click("summary#regh") if not pg.is_visible("#rn") else None
        pg.fill("#rn", "INA000000201"); pg.fill("#rm", "Gamma Wealth Advisers Private Limited"); pg.click("#regform button"); pg.wait_for_selector("#registry-card", timeout=10000)
        card = pg.inner_text("#regout"); pg.screenshot(path=os.path.join(OUT, "%s_3_registry.png" % name), full_page=True)
        ok("A match does not show who contacted you" in card, "%s: JS-loaded register card carries the reminder" % name)
        ok("high concern" in pg.inner_text("h1").lower(), "%s: message result still on page after register step" % name)
        ok(not [x for x in problems if "Content Security Policy" in x or "Refused" in x], "%s: no CSP violations (problems: %s)" % (name, problems[:2]))
        r = Axe().run(pg); v = r.response["violations"]; res["axe"][name + "_result_page"] = [{"id": x["id"], "impact": x["impact"], "nodes": len(x["nodes"])} for x in v]
        ok(not [x for x in v if x["impact"] in ("critical", "serious")], "%s: axe-core no critical/serious violations on result page (%s)" % (name, [x["id"] for x in v]))
        pg.goto(B + "/?lang=hi"); pg.screenshot(path=os.path.join(OUT, "%s_4_home_hi.png" % name), full_page=True)
        v2 = Axe().run(pg).response["violations"]; res["axe"][name + "_home_hi"] = [{"id": x["id"], "impact": x["impact"]} for x in v2]
        ok(not [x for x in v2 if x["impact"] in ("critical", "serious")], "%s: axe-core no critical/serious violations on Hindi home" % name)
        pg.goto(B + "/"); pg.check("input[value=PAID_MONEY]"); pg.click("button[type=submit]"); pg.wait_for_load_state(); pg.screenshot(path=os.path.join(OUT, "%s_5_paid.png" % name), full_page=True)
        first = pg.evaluate("document.querySelector('main').querySelector('section.urgent') !== null && document.querySelector('main').children[1].tagName"); ok(bool(first), "%s: PAID_MONEY page has an urgent section" % name)
        ctx.close()
    br.close()
srv.shutdown()
with open(os.path.join(OUT, "browser_check.json"), "w") as f: json.dump(res, f, indent=1)
bad = [c for c in res["checks"] if not c["pass"]]; print("\nFAILED:", [c["check"] for c in bad] if bad else "none"); sys.exit(1 if bad else 0)
