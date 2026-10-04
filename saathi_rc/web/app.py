#!/usr/bin/env python3
"""Sangyan Saathi rc web app (stdlib only; no network client of any kind).
Privacy: no accounts, database, cookies or analytics; request bodies are never logged or stored; access logging is off; exception logs contain the exception TYPE only.
Fail closed: any internal failure returns a page that still carries the urgent 'money already lost' guidance and says nothing was checked.
Env: PORT (8000), HOST (127.0.0.1), SAATHI_REGISTRY = fixture (default; labelled DEMO data) | off. There is no live SEBI mode in this release."""
import json, os, sys, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.dont_write_bytecode = True
from .. import VERSION, clock
from ..contract import SITUATIONS, LANGS
from ..engine import analyze
from ..journey import journey, journey_violations
from ..registry.api import check_registration
from . import views
from ..engine import get_corpus_rc

MAX_BODY = 90_000          # bytes (20,000 Hindi characters is ~60 KB in UTF-8)
MAX_TEXT = 20_000
REG_PER_IP, REG_GLOBAL, WINDOW = 6, 30, 60.0


class RateLimiter:
    def __init__(self, per_key, total, window, now=time.monotonic):
        self.per_key, self.total, self.window, self.now = per_key, total, window, now; self.k = {}; self.all = []; self.lock = threading.Lock()

    def allow(self, key):
        t = self.now()
        with self.lock:
            self.all = [x for x in self.all if t - x < self.window]
            hits = [x for x in self.k.get(key, []) if t - x < self.window]
            if len(hits) >= self.per_key or len(self.all) >= self.total:
                self.k[key] = hits; return False
            hits.append(t); self.all.append(t); self.k[key] = hits
            if len(self.k) > 2000: self.k = {a: b for a, b in self.k.items() if b}
            return True


class State:
    def __init__(self, mode=None, source=None, rate=None):
        self.mode = mode or os.environ.get("SAATHI_REGISTRY", "fixture")
        if self.mode not in ("fixture", "off"):   # this release has no live SEBI client; any other value (including "live") means off
            sys.stderr.write("SAATHI_REGISTRY=%s is not available in this release (no live SEBI client); register step is off.\n" % self.mode[:20].replace("\n", " "))
            self.mode = "off"
        self.lock = threading.Lock(); self.rate = rate or RateLimiter(REG_PER_IP, REG_GLOBAL, WINDOW)
        self._source = source

    def source(self):
        if self._source is None:
            if self.mode == "fixture":
                from ..registry.source import FixtureSource
                fx = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..", "eval", "registry_fixture.json"), encoding="utf-8"))
                self._source = FixtureSource(fx["entries"])
        return self._source


def clean_lang(x):
    return x if x in LANGS else "en"


def run_check(fields):
    """-> (result dict). fields: situation, text, output_language. Never raises (a failure becomes a fail-closed ESCALATE-style notice upstream)."""
    sit = fields.get("situation") or None
    return journey({"situation": sit if sit in SITUATIONS else None, "text": fields.get("text") or "", "output_language": (fields.get("output_language")[:12] if isinstance(fields.get("output_language"), str) else None)})   # S3 FIX-2: the engine adds a visible fallback notice for languages it does not offer


def run_registry(state, fields, client):
    """-> (res_for_situation, reg dict). The register step never touches message analysis."""
    lang = clean_lang(fields.get("output_language")); sit = fields.get("situation") or "UNSURE"
    res = analyze({"situation": sit if sit in SITUATIONS else "UNSURE", "text": "", "output_language": lang})
    if state.mode == "off" or not state.rate.allow(client):
        msg = "Register lookups are switched off on this server." if state.mode == "off" else "Too many lookups in the last minute. Nothing was checked. Please wait and try again."
        card = {"status": "NOT_CHECKABLE", "reason": "RATE_LIMITED" if state.mode != "off" else "DISABLED", "headline": "Nothing was checked", "means": msg, "does_not_mean": "No registration was checked, so nothing about the sender can be concluded.",
                "register_record": None, "candidates": [], "as_of": None, "provenance": [], "source": {}}
        from ..registry.api import REMINDER
        return res, {"card": card, "reminder": REMINDER[lang], "effect_on_message_result": "none", "language": lang}
    with state.lock:   # one register lookup at a time: polite to the upstream, bounded work
        reg = check_registration(fields.get("number"), fields.get("name"), None, state.source(), lang, now=clock.now_utc())
    return res, reg


class Handler(BaseHTTPRequestHandler):
    server_version = "SaathiRC"; sys_version = ""; timeout = 20; protocol_version = "HTTP/1.1"
    state = State()

    def log_message(self, *a):  # no access log: avoids recording anything about requests
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        for k, v in (("Content-Type", ctype), ("Content-Length", str(len(body))), ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"),
                     ("Content-Security-Policy", views.CSP), ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"), ("Connection", "close")):
            self.send_header(k, v)
        self.end_headers(); self.wfile.write(body); self.close_connection = True

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _read(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None, 400
        if n < 0 or n > MAX_BODY: return None, 413
        return self.rfile.read(n).decode("utf-8", "replace"), 200

    def _client(self):
        return self.client_address[0]

    def do_GET(self):
        try:
            u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query); lang = clean_lang((q.get("lang") or ["en"])[0])
            if u.path == "/": return self._send(200, views.form(lang))
            if u.path == "/about": return self._send(200, views.render_about(lang))
            if u.path == "/healthz": return self._json(200, {"status": "ok", "version": VERSION, "registry_mode": self.state.mode})
            return self._send(404, views.render_error(lang), "text/html; charset=utf-8")
        except Exception as ex:
            self._fail(ex)

    def do_POST(self):
        try:
            body, code = self._read()
            if body is None: return self._send(code, views.render_error("en"))
            path = urllib.parse.urlparse(self.path).path
            if path in ("/api/check", "/api/registry"):
                return self._api(path, body)
            f = {k: v[0] for k, v in urllib.parse.parse_qs(body, keep_blank_values=True).items()}
            lang = clean_lang(f.get("output_language"))
            if len(f.get("text", "")) > MAX_TEXT: return self._send(413, views.render_error(lang))
            if path == "/check": return self._send(200, views.render_result(run_check(f), text=f.get("text", "")))
            if path in ("/registry", "/registry-fragment"):
                res, reg = run_registry(self.state, f, self._client())
                card = views.registry_card_html(reg, lang, demo=self.state.mode == "fixture")
                return self._send(200, card.encode("utf-8") if path.endswith("fragment") else views.render_registry_page(res, reg, lang, demo=self.state.mode == "fixture"))
            return self._send(404, views.render_error(lang))
        except Exception as ex:
            self._fail(ex)

    def _api(self, path, body):
        try:
            d = json.loads(body or "{}")
            assert isinstance(d, dict)
        except Exception:
            return self._json(400, {"error": "invalid_json"})
        for k in ("situation", "text", "output_language", "number", "name"):
            if k in d and d[k] is not None and not isinstance(d[k], str): return self._json(400, {"error": "invalid_field", "field": k})
        if len(d.get("text") or "") > MAX_TEXT: return self._json(413, {"error": "text_too_long"})
        if path == "/api/check":
            res = run_check(d)
            res["journey_violations"] = journey_violations(res)
            return self._json(200, res)
        res, reg = run_registry(self.state, d, self._client())
        return self._json(200, {"situation_guidance": {"posture": res["posture"], "urgent_steps": res["urgent_steps"]}, "registry": reg})

    def _fail(self, ex):
        if isinstance(ex, (BrokenPipeError, ConnectionResetError, TimeoutError)): return   # client went away; nothing to report
        sys.stderr.write("internal error: %s\n" % type(ex).__name__)   # type only; never request content
        try:
            self._send(500, views.render_error("en"))
        except Exception:
            pass


def _index_sources():
    try:
        views.SOURCE_INDEX.update({k: {"publisher": v["publisher"], "url": v["url"]} for k, v in get_corpus_rc().passages.items()})
    except Exception:
        pass   # display only: links fall back to passage ids


_index_sources()


def make_server(host="0.0.0.0", port=8000, state=None):
    h = type("H", (Handler,), {"state": state or State()})
    s = ThreadingHTTPServer((host, port), h); s.daemon_threads = True
    return s


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000")); host = os.environ.get("HOST", "127.0.0.1")
    srv = make_server(host, port)
    sys.stderr.write("Sangyan Saathi %s on http://%s:%d  (register mode: %s)\n" % (VERSION, host, port, srv.RequestHandlerClass.state.mode))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
