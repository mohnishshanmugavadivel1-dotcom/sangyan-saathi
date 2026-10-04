"""Register-lookup data types and the synthetic FixtureSource. This release contains NO client for SEBI's website: the live lookup code
of the development build was removed from this release candidate (see README). Every lookup returns a LookupResult and never raises."""
import datetime as dt, hashlib, html as _html, re, time
from dataclasses import dataclass, field

@dataclass
class LookupResult:
    list_id: str
    kind: str            # 'regNo' | 'name'
    query: str
    status: str          # 'OK' | 'UNAVAILABLE' | 'ERROR'
    records: list = field(default_factory=list)
    total: int = 0
    as_of: str = None    # ISO date from the page, or None
    retrieved_at: str = None  # ISO UTC
    http_status: int = None
    html_sha256: str = None
    detail: str = ""

    def prov(self):
        return {"list": self.list_id, "query_kind": self.kind, "query": self.query, "result": self.status, "record_count": self.total, "as_of": self.as_of,
                "retrieved_at_utc": self.retrieved_at, "http_status": self.http_status, "html_sha256": self.html_sha256, "detail": self.detail}


class FixtureSource:
    """Deterministic, synthetic demo register: regNo exact (case-insensitive, NOT trimmed), name substring.
    `entries`: list of dicts {list: 'IA'|'RA'|'IA_INACTIVE'|'RA_INACTIVE', name, reg_no, validity?, type?, status?}.
    `modes`: {list_id: 'ok'|'unavailable'|'error'|'dup'|'wrong_record'|'garbage'}; `as_of`: {list_id: ISO|None}."""
    def __init__(self, entries, as_of=None, modes=None, retrieved_at="2026-10-03T00:00:00Z"):
        self.entries = entries; self.as_of = as_of or {}; self.modes = modes or {}; self.retrieved_at = retrieved_at; self.calls = []

    def lookup(self, list_id, kind, value):
        self.calls.append((list_id, kind, value))
        mode = self.modes.get(list_id, "ok")
        res = LookupResult(list_id, kind, value, "OK", retrieved_at=self.retrieved_at, http_status=200, as_of=self.as_of.get(list_id, "2026-10-02" if not list_id.endswith("INACTIVE") else None))
        if mode == "unavailable":
            res.status, res.http_status, res.detail = "UNAVAILABLE", None, "timeout"; return res
        if mode == "error":
            res.status, res.detail = "ERROR", "parse: no recognisable result block"; return res
        if mode == "garbage":   # RC CH-R5: was documented but unimplemented in v0.3. A 200 response whose body is not a SEBI result page.
            res.status, res.detail, res.http_status = "ERROR", "parse: not a SEBI page", 200; return res
        pool = [e for e in self.entries if e["list"] == list_id]
        if kind == "regNo":
            hits = [e for e in pool if e["reg_no"].lower() == value.lower()]
        else:
            hits = [e for e in pool if value.lower() in e["name"].lower()]
        recs = [{k: v for k, v in e.items() if k != "list"} for e in hits]
        if mode == "dup" and recs:
            recs = recs + [dict(recs[0])]
        if mode == "wrong_record":
            recs = [{"name": "OTHER ENTITY PRIVATE LIMITED", "reg_no": "INH000000001", "validity": "Jan 01, 2020 - Perpetual"}]
        res.records, res.total = recs, len(recs)
        return res
