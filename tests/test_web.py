"""Web app tests: real HTTP server on an ephemeral port, injected FixtureSource (no network). Checks that the UI shows the backend's output, hides no warning,
adds no reassurance, puts urgent guidance first, and fails closed. Clock pinned for determinism."""
import colorsys, contextlib, html, io, json, os, re, subprocess, sys, threading, unittest, urllib.error, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); RC = os.path.abspath(os.path.join(HERE, "..")); sys.path.insert(0, RC); sys.dont_write_bytecode = True
from saathi_rc import clock
from saathi_rc.contract import REASSURE_RE, APPROVED_NEGATIVE, SITUATIONS, LIMITS
from saathi_rc.registry.source import FixtureSource
from saathi_rc.web import app as webapp, views

with open(os.path.join(RC, "eval", "registry_fixture.json"), encoding="utf-8") as _f:
    FX = json.load(_f)["entries"]
SCAM = "Guaranteed 40% monthly returns, SEBI registered INA000000201. Pay Rs 5000 now to join, limited seats. Download app http://x.co/a"
e = html.escape


def visible(h):
    t = re.sub(r"<style>.*?</style>|<script>.*?</script>", "", h, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)))


def lum(h):
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class Base(unittest.TestCase):
    mode = "fixture"

    @classmethod
    def setUpClass(cls):
        cls._clk = clock.frozen("2026-10-03"); cls._clk.__enter__()
        cls.state = webapp.State(mode="fixture", source=FixtureSource([dict(x) for x in FX]), rate=webapp.RateLimiter(10 ** 6, 10 ** 6, 60))   # rate limit is tested separately
        cls.srv = webapp.make_server("127.0.0.1", 0, cls.state); cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); cls._clk.__exit__(None, None, None)

    def req(self, path, data=None, method=None, raw=None, headers=None):
        body = raw if raw is not None else (urllib.parse.urlencode(data).encode() if data is not None else None)
        r = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(r, timeout=20) as x:
                return x.status, x.read().decode("utf-8"), dict(x.headers)
        except urllib.error.HTTPError as ex:
            return ex.code, ex.read().decode("utf-8"), dict(ex.headers)

    def api(self, path, obj):
        c, b, h = self.req(path, raw=json.dumps(obj).encode(), headers={"Content-Type": "application/json"})
        return c, json.loads(b)


class TestPages(Base):
    def test_home_accessible_structure(self):
        c, h, hd = self.req("/")
        self.assertEqual(c, 200)
        self.assertIn("<html lang='en'>", h); self.assertEqual(h.count("<h1"), 1); self.assertIn("class='skip'", h); self.assertIn("<main id='main'", h)
        for i in re.findall(r"<(?:input|textarea)[^>]*\sid='(\w+)'", h): self.assertIn("for='%s'" % i, h)
        self.assertEqual(len(re.findall(r"type='radio'", h)), 6); self.assertIn("required", h)
        self.assertIn("1930", visible(h)); self.assertNotIn("<script src", h); self.assertNotIn("http://", re.sub(r"<style>.*?</style>", "", h, flags=re.S).replace("http://x", ""))
        self.assertLess(len(h.encode()), 20000)

    def test_hindi_pages(self):
        c, h, _ = self.req("/?lang=hi"); self.assertIn("<html lang='hi'>", h); self.assertIn("संदिग्ध", h)
        c, h, _ = self.req("/check", {"situation": "NO_ACTION_YET", "output_language": "hi", "text": "गारंटीड 40% मासिक रिटर्न। अभी पैसे भेजें।"})
        self.assertEqual(c, 200); self.assertIn("lang='hi'", h); self.assertIn("मातृभाषी", visible(h))  # the unreviewed-Hindi disclosure is shown

    def test_about_and_unknown(self):
        self.assertEqual(self.req("/about")[0], 200); self.assertEqual(self.req("/nope")[0], 404)
        self.assertIn("SEBI has not endorsed", visible(self.req("/about")[1]))

    def test_no_inline_style_attributes_or_event_handlers(self):
        """CSP (style-src/script-src hashes) blocks style="" attributes and on*= handlers: found by the real-browser check, now guarded here."""
        pages = [self.req("/")[1], self.req("/?lang=hi")[1], self.req("/about")[1]]
        for sit in SITUATIONS: pages.append(self.req("/check", {"situation": sit, "text": SCAM, "output_language": "en"})[1])
        pages.append(self.req("/registry-fragment", {"situation": "NO_ACTION_YET", "number": "INA000000201", "output_language": "en"})[1])
        for h in pages:
            self.assertIsNone(re.search(r"\sstyle\s*=", h)); self.assertIsNone(re.search(r"\son\w+\s*=", re.sub(r"<script>.*?</script>", "", h, flags=re.S)))

    def test_security_headers_no_external_loads(self):
        c, h, hd = self.req("/")
        for k in ("Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy", "Cache-Control"): self.assertIn(k, hd)
        self.assertEqual(hd["Cache-Control"], "no-store"); self.assertIn("default-src 'none'", hd["Content-Security-Policy"])
        self.assertNotIn("unsafe-inline", hd["Content-Security-Policy"]); self.assertNotIn("Set-Cookie", hd)
        self.assertEqual(self.req("/healthz")[0], 200)


class TestFaithfulRendering(Base):
    """Every backend string that matters appears in the page; nothing reassuring is added."""
    CASES = [("NO_ACTION_YET", SCAM), ("NO_ACTION_YET", "Hi, please share your meeting agenda for tomorrow."), ("NO_ACTION_YET", "Your KYC is expiring. Click http://kyc-update.xyz now and enter OTP."),
             ("PAYMENT_PENDING", "Transfer 40000 to this account to unlock profit"), ("PAID_MONEY", ""), ("SHARED_CREDENTIALS", "I gave my OTP 481516"), ("ACCESS_GRANTED", ""), ("UNSURE", "hello"),
             ("NO_ACTION_YET", "இன்றே முதலீடு செய்யுங்கள், உத்தரவாத லாபம்"), ("NO_ACTION_YET", "আজই টাকা পাঠান"), ("NO_ACTION_YET", "")]

    def test_backend_strings_all_present(self):
        for sit, text in self.CASES:
            for lang in ("en", "hi"):
                c, api = self.api("/api/check", {"situation": sit, "text": text, "output_language": lang})
                c2, page, _ = self.req("/check", {"situation": sit, "text": text, "output_language": lang})
                self.assertEqual((c, c2), (200, 200)); self.assertEqual(api["journey_violations"], [])
                must = [api["headline"]] + [s["text"] for s in api["urgent_steps"]] + [s["text"] for s in api["steps"]] + [i["note"] for i in api["indicators"] if i["note"]] + \
                       [c_["explanation"] for c_ in api["claims"]] + [c_["state_label"] for c_ in api["claims"]] + api["limitations"] + [u["text"] for u in api["unavailable"]]
                if api["posture"] in ("ASK_FOLLOWUP", "NEEDS_SITUATION"): must += api["questions"]
                for m in must:
                    self.assertIn(e(m), page, "missing from UI (%s/%s/%s): %s" % (sit, lang, api["posture"], m[:60]))
                self.assertIn(views.UI[lang]["banner"].replace("'", "&#x27;"), page)

    def test_urgent_block_is_first_content_for_harm_situations(self):
        for sit in ("PAID_MONEY", "SHARED_CREDENTIALS", "ACCESS_GRANTED"):
            for text in ("", SCAM, "random text"):
                c, page, _ = self.req("/check", {"situation": sit, "text": text, "output_language": "en"})
                body = page[page.index("<main"):]
                self.assertIn("role='alert'", body); self.assertIn("1930", visible(body))
                self.assertLess(body.index("role='alert'"), min(i for i in (body.find("Limits of this tool"), body.find("Checked against")) if i >= 0) if "Checked against" in body or "Limits" in body else 10 ** 9)
                self.assertNotIn("Checked against sources", body)   # message not assessed when harm may already have happened

    def test_no_reassurance_added_anywhere(self):
        approved = [e(a) for a in APPROVED_NEGATIVE]
        for sit, text in self.CASES:
            for lang in ("en", "hi"):
                _, page, _ = self.req("/check", {"situation": sit, "text": text, "output_language": lang})
                t = visible(page)
                for a in APPROVED_NEGATIVE + [views.UI[lang]["banner"], views.UI[lang]["reg_p"]] + sum(LIMITS.values(), []):
                    t = t.replace(html.unescape(a), "")
                # the page may quote the user's own text in masked snippets; reassurance words there are the user's, so strip quoted snippets
                t = re.sub(r"“[^”]*”", "", t)
                m = REASSURE_RE.search(t)
                if m:   # remaining hits must be inside approved explanatory text from the backend (claim explanations are validated by the backend validator)
                    ctx = t[max(0, m.start() - 80): m.end() + 80]
                    self.assertTrue(any(w in ctx.lower() for w in ("not ", "never", "no ", "cannot", "does not", "नहीं", "कभी")), "possible reassurance: " + ctx)

    def test_masking_of_sensitive_digits_in_page(self):
        text = "My OTP is 482913 and card 4111 1111 1111 1111 pay Rs 5000 now to join, guaranteed returns"
        for sit in ("NO_ACTION_YET", "UNSURE"):
            _, page, _ = self.req("/check", {"situation": sit, "text": text, "output_language": "en"})
            v = visible(page)
            for s in ("482913", "4111 1111 1111 1111", "4111"):
                if sit == "UNSURE": continue    # follow-up form re-shows the user's own pasted text so they can resend it; see test_followup_text_roundtrip
                self.assertNotIn(s, v)

    def test_followup_text_roundtrip_is_visible_and_escaped(self):
        _, page, _ = self.req("/check", {"situation": "UNSURE", "text": "<script>alert(1)</script> pay now", "output_language": "en"})
        self.assertNotIn("<script>alert(1)</script>", page); self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_xss_in_all_echoed_fields(self):
        x = "<img src=x onerror=alert(1)>"
        for path, f in (("/check", {"situation": "NO_ACTION_YET", "text": "pay now " + x + " guaranteed returns", "output_language": "en"}),
                        ("/registry", {"situation": "NO_ACTION_YET", "number": x, "name": x, "output_language": "en"}),
                        ("/registry-fragment", {"situation": "NO_ACTION_YET", "number": "INA000000201", "name": x, "output_language": "en"})):
            _, page, _ = self.req(path, f); self.assertNotIn(x, page)

    def test_evidence_tier_is_shown(self):
        _, page, _ = self.req("/check", {"situation": "NO_ACTION_YET", "text": SCAM, "output_language": "en"})
        v = visible(page); self.assertTrue("news or secondary report" in v or "official source" in v or "reproduction of an official statement" in v)
        self.assertIn("This does not verify the message itself", v)

    def test_four_kinds_are_visually_and_textually_distinct(self):
        _, page, _ = self.req("/check", {"situation": "NO_ACTION_YET", "text": SCAM, "output_language": "en"})
        for tag in ("Info", "Warning", "Not checked"): self.assertIn("<span class='tag'>%s</span>" % tag, page)
        for cls in ("box info", "box concern", "box unavail"): self.assertIn(cls, page)


class TestRegistryStep(Base):
    def card(self, number, name="", lang="en"):
        return self.req("/registry-fragment", {"situation": "NO_ACTION_YET", "number": number, "name": name, "output_language": lang})[1]

    def test_reminder_is_prominent_inside_card_and_not_muted(self):
        h = self.card("INA000000201", "Gamma Wealth Advisers Private Limited")
        self.assertIn("Even a match only shows", h); self.assertIn("A match does not show who contacted you", h)
        i = h.index("Even a match only shows"); seg = h[h.rfind("<div", 0, i):i]
        self.assertNotIn("muted", seg); self.assertIn("box concern", seg)
        self.assertLess(h.index("Register record") if "Register record" in h else 0, h.index("Even a match only shows"))

    def test_does_not_mean_text_not_muted_class(self):
        h = self.card("INA000000201", "Gamma Wealth Advisers Private Limited")
        for m in re.finditer(r"<p( class='muted')?>([^<]*)</p>", h):
            if "Even a match" in m.group(2) or "does not" in m.group(2).lower() and "shows" in m.group(2).lower(): self.assertIsNone(m.group(1), m.group(2)[:60])

    def test_states_render_and_demo_label(self):
        for num, name, expect in (("INA000000201", "Gamma Wealth Advisers Private Limited", "listed on sebi's register"), ("INA000000999", "", "not found"), ("INH000000301", "", "cancelled"), ("bad", "", "")):
            h = self.card(num, name); self.assertIn("DEMO DATA", h); self.assertIn("registry-card", h)
            if expect: self.assertIn(expect.lower(), visible(h).lower())

    def test_hindi_card_has_hindi_reminder(self):
        self.assertIn("आपसे किसने संपर्क किया", self.card("INA000000201", "", "hi"))

    def test_registry_page_no_js_path_has_emergency_or_urgent_first(self):
        _, p, _ = self.req("/registry", {"situation": "PAID_MONEY", "number": "INA000000201", "output_language": "en"})
        self.assertLess(p.index("role='alert'"), p.index("registry-card")); self.assertIn("1930", visible(p))
        _, p, _ = self.req("/registry", {"situation": "NO_ACTION_YET", "number": "INA000000201", "output_language": "en"})
        self.assertLess(p.index("Money already lost?"), p.index("registry-card"))

    def test_registry_offered_on_assessments_only(self):
        for sit, text, shown in (("NO_ACTION_YET", SCAM, True), ("PAID_MONEY", SCAM, False), ("UNSURE", SCAM, False)):
            _, p, _ = self.req("/check", {"situation": sit, "text": text, "output_language": "en"})
            self.assertEqual("id='regform'" in p, shown, sit)
        _, p, _ = self.req("/check", {"situation": "NO_ACTION_YET", "text": SCAM, "output_language": "en"})
        self.assertIn("value='INA000000201'", p); self.assertLess(p.index("What you can do next"), p.index("id='regform'"))

    def test_registry_does_not_change_message_result_api(self):
        c, a = self.api("/api/check", {"situation": "NO_ACTION_YET", "text": SCAM}); c2, r = self.api("/api/registry", {"situation": "NO_ACTION_YET", "number": "INA000000201", "name": "Gamma Wealth Advisers Private Limited"})
        self.assertEqual(r["registry"]["effect_on_message_result"], "none"); self.assertEqual(a["posture"], "HIGH_CONCERN"); self.assertIn("reminder", r["registry"])

    def test_rate_limit_fails_closed_with_clear_card(self):
        st = webapp.State(mode="fixture", source=FixtureSource([dict(x) for x in FX]), rate=webapp.RateLimiter(2, 100, 60))
        res = [webapp.run_registry(st, {"number": "INA000000201", "output_language": "en"}, "ip")[1]["card"]["status"] for _ in range(3)]
        self.assertNotIn("NOT_CHECKABLE", res[:2]); self.assertEqual(res[2], "NOT_CHECKABLE")
        h = views.registry_card_html(webapp.run_registry(st, {"number": "INA000000201"}, "ip")[1], "en"); self.assertIn("Nothing was checked", h)

    def test_off_mode(self):
        st = webapp.State(mode="off"); r = webapp.run_registry(st, {"number": "INA000000201"}, "ip")[1]
        self.assertEqual(r["card"]["status"], "NOT_CHECKABLE")

    def test_source_unavailable_is_shown_as_not_checked(self):
        st = webapp.State(mode="fixture", source=FixtureSource([dict(x) for x in FX], modes={"IA": "unavailable", "RA": "unavailable"}))
        r = webapp.run_registry(st, {"number": "INA000000201", "name": "x"}, "ip")[1]
        self.assertIn(r["card"]["status"], ("SOURCE_UNAVAILABLE", "SOURCE_ERROR", "NOT_CHECKABLE"))
        self.assertNotEqual(r["card"]["status"], "CONFIRMED_IN_REGISTER")


class TestRobustness(Base):
    def test_oversize_and_bad_input(self):
        self.assertEqual(self.req("/check", raw=b"x" * 100000)[0], 413)
        self.assertEqual(self.req("/check", {"situation": "NO_ACTION_YET", "text": "a" * 20001, "output_language": "en"})[0], 413)
        c, b = self.api("/api/check", {"text": "a" * 20001}); self.assertEqual(c, 413)
        self.assertEqual(self.req("/api/check", raw=b"not json")[0], 400); self.assertEqual(self.req("/api/check", raw=b"[1,2]")[0], 400)
        self.assertEqual(self.api("/api/check", {"text": 5})[0], 400)
        c, h, _ = self.req("/check", raw=b"\xff\xfe=%ff&situation=NO_ACTION_YET"); self.assertEqual(c, 200)
        c, r = self.api("/api/check", {"situation": "BOGUS", "text": "pay now to win"}); self.assertEqual((c, r["posture"]), (200, "NEEDS_SITUATION"))
        c, r = self.api("/api/check", {"situation": "NO_ACTION_YET", "text": "pay", "output_language": "zz"}); self.assertEqual(r["language"], "en")

    def test_internal_failure_is_fail_closed_with_guidance(self):
        orig = webapp.run_check
        webapp.run_check = lambda f: (_ for _ in ()).throw(RuntimeError("boom SECRET-123"))
        buf = io.StringIO()
        try:
            with contextlib.redirect_stderr(buf):
                c, h, _ = self.req("/check", {"situation": "NO_ACTION_YET", "text": "SECRET-123 pay now", "output_language": "en"})
        finally:
            webapp.run_check = orig
        self.assertEqual(c, 500); self.assertIn("Nothing was checked", visible(h)); self.assertIn("1930", visible(h)); self.assertNotIn("SECRET-123", h); self.assertNotIn("SECRET-123", buf.getvalue())

    def test_no_request_content_logged(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.req("/check", {"situation": "NO_ACTION_YET", "text": "MARKER-ZZ-OTP 482913 pay now", "output_language": "en"})
            self.req("/registry", {"situation": "NO_ACTION_YET", "number": "MARKER-ZZ", "output_language": "en"})
            self.api("/api/check", {"text": "MARKER-ZZ"})
        self.assertNotIn("MARKER-ZZ", out.getvalue() + err.getvalue())

    def test_concurrent_requests(self):
        res = []
        def go(i):
            res.append(self.req("/check", {"situation": "NO_ACTION_YET", "text": SCAM + str(i), "output_language": "en"})[0])
        ts = [threading.Thread(target=go, args=(i,)) for i in range(12)]; [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(res, [200] * 12)

    def test_slow_client_does_not_hang_server(self):
        import socket
        s = socket.create_connection(("127.0.0.1", self.port)); s.sendall(b"POST /check HTTP/1.1\r\nContent-Length: 50\r\n\r\nabc")
        self.assertEqual(self.req("/healthz")[0], 200); s.close()


class TestStaticDesign(unittest.TestCase):
    def test_contrast(self):
        for k, (t, b, c) in views.PALETTE.items():
            self.assertGreaterEqual(contrast(t, b), 7.0 if k != "button" else 7.0, k)
        self.assertGreaterEqual(contrast("#0b3d91", "#ffffff"), 7.0)    # links
        for k in ("urgent", "concern", "info", "unavail"): self.assertGreaterEqual(contrast(views.PALETTE[k][2], "#ffffff"), 3.0, k)   # borders (non-text UI, 3:1)

    def test_no_green_anywhere(self):
        for h in set(re.findall(r"#[0-9a-fA-F]{6}", views.CSS)):
            r, g, b = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            hh, s, v = colorsys.rgb_to_hsv(r, g, b)
            if s > 0.15: self.assertFalse(0.22 <= hh <= 0.47, "green-ish colour %s" % h)

    def test_js_syntax(self):
        if not subprocess.run(["which", "node"], capture_output=True).stdout: self.skipTest("node not installed")
        p = os.path.join(HERE, "_tmp_js_check.js")
        with open(p, "w") as f: f.write(views.JS)
        try:
            r = subprocess.run(["node", "--check", p], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            os.remove(p)

    def test_ui_strings_complete_in_both_languages(self):
        self.assertEqual(set(views.UI["en"]), set(views.UI["hi"]))
        for k in views.UI["en"]:
            if isinstance(views.UI["en"][k], dict): self.assertEqual(set(views.UI["en"][k]), set(views.UI["hi"][k]), k)
        for k in ("banner", "privacy"):   # interface strings never reassure
            for l in ("en", "hi"): self.assertIsNone(re.search(r"(?i)\byour message is (safe|genuine)", views.UI[l][k]))


if __name__ == "__main__":
    unittest.main()
