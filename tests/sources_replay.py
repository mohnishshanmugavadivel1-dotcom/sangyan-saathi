"""Test sources for the register step: replay of REAL lookups recorded on 2026-10-02 (copied from v0_3/results/run1) and a fault injector."""
import copy, json, os
from saathi_rc.registry.source import LookupResult as _RcLookupResult
HERE = os.path.dirname(os.path.abspath(__file__))
RECORDED = os.path.join(HERE, "fixtures", "recorded_lookups_2026-10-02.jsonl")


class RecordedSource:
    def __init__(self, path=RECORDED, result_cls=_RcLookupResult):
        self.cls = result_cls
        self.d = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                x = json.loads(line); self.d.setdefault((x["list_id"], x["kind"], x["query"]), x)

    def lookup(self, list_id, kind, value):
        x = self.d.get((list_id, kind, value))
        if x is None:
            return self.cls(list_id, kind, value, "UNAVAILABLE", detail="not recorded")
        return self.cls(**copy.deepcopy(x))


class FaultSource:
    def __init__(self, inner, faults):
        self.inner, self.faults = inner, faults

    def lookup(self, list_id, kind, value):
        r = self.inner.lookup(list_id, kind, value); m = self.faults.get(list_id)
        if not m: return r
        r = copy.deepcopy(r)
        if m == "stale": r.as_of = "2026-09-01"
        elif m == "no_as_of": r.as_of = None
        elif m == "future_as_of": r.as_of = "2026-12-31"
        elif m == "unavailable": r.status, r.records, r.total, r.http_status, r.detail = "UNAVAILABLE", [], 0, None, "injected: timeout"
        elif m == "error": r.status, r.records, r.total, r.detail = "ERROR", [], 0, "injected: unparseable page"
        elif m == "dup" and r.records: r.records = r.records + [dict(r.records[0])]; r.total = len(r.records)
        elif m == "wrong_record": r.records = [{"name": "OTHER ENTITY PRIVATE LIMITED", "reg_no": "INH000000001", "validity": "Jan 01, 2020 - Perpetual"}]; r.total = 1
        return r
