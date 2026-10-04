"""Source verification: a pure function of (structured claim, source results, clock). Imports no message-assessment code (I1)."""
import datetime as dt, re
from .contract import STALE_DAYS, MAX_CANDIDATES
from .inputs import classify_number, compare_names, name_searchable

KNOWN_INACTIVE = {"surrendered", "expired", "suspended", "cancelled"}  # statuses SEBI's filter offers; other values (e.g. "Destroyed", "Registered") occur on that page and are NOT interpreted
TYPE_RE = {"INA": re.compile(r"(?i)invest"), "INH": re.compile(r"(?i)research")}


def _result(status, reason=None, **kw):
    d = {"status": status, "reason": reason, "note": kw.pop("note", None), "claim": kw.pop("claim", {}), "register_record": None, "candidates": [], "match_count": None, "provenance": [], "as_of": None}
    d.update(kw); return d


def _parse_iso(s):
    try:
        return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def _source_problem(results, now, need_asof, number=None, prefix=None):
    """-> SOURCE_ERROR | SOURCE_UNAVAILABLE | SOURCE_STALE | None. Order: error > unavailable > stale."""
    for r in results:
        if r.status == "ERROR":
            return "SOURCE_ERROR"
    for r in results:
        if r.status == "UNAVAILABLE":
            return "SOURCE_UNAVAILABLE"
    for r in results:
        if r.status != "OK":
            return "SOURCE_ERROR"
        if r.total != len(r.records) and r.total <= 25:
            return "SOURCE_ERROR"
        if number is not None:
            if len(r.records) > 1:
                return "SOURCE_ERROR"
            for rec in r.records:
                if classify_number(rec.get("reg_no", ""))[1] != number:
                    return "SOURCE_ERROR"
                if rec.get("type") and prefix in TYPE_RE and not TYPE_RE[prefix].search(rec["type"]):
                    return "SOURCE_ERROR"
        ret = _parse_iso(r.retrieved_at)
        if ret is None:
            return "SOURCE_ERROR"
        if r.as_of:
            try:
                d = dt.date.fromisoformat(r.as_of)
            except ValueError:
                return "SOURCE_ERROR"
            if (d - now.date()).days > 1:
                return "SOURCE_ERROR"
    for r in results:
        ret = _parse_iso(r.retrieved_at)
        if (now - ret).days > STALE_DAYS or (now - ret).total_seconds() < -86400:
            return "SOURCE_STALE"
        if r.as_of is None and need_asof(r):
            return "SOURCE_STALE"
        if r.as_of and (now.date() - dt.date.fromisoformat(r.as_of)).days > STALE_DAYS:
            return "SOURCE_STALE"
    return None


def _is_current(r):
    return not r.list_id.endswith("_INACTIVE")


def _rec(rec, list_id):
    return {"name": rec.get("name"), "reg_no": rec.get("reg_no"), "list": list_id.replace("_INACTIVE", ""), "validity": rec.get("validity"), "register_status": rec.get("status")}


def verify_claim(number, name, category, claim_kind, source, now, too_many=False):
    claim = {"reg_no": None, "name_given": bool((name or "").strip())}
    if claim_kind == "OTHER":
        return _result("NOT_CHECKABLE", "UNSUPPORTED_CLAIM", claim=claim)
    if too_many:
        return _result("NOT_CHECKABLE", "TOO_MANY_NUMBERS", claim=claim)
    kind, n = classify_number(number)
    if kind == "NO_NUMBER":
        if (name or "").strip():
            return _name_only(name, category, source, now, claim)
        return _result("NOT_CHECKABLE", "NO_REGISTRATION_NUMBER", claim=claim)
    if kind != "OK":
        return _result("NOT_CHECKABLE", kind, claim=claim)
    claim["reg_no"] = n
    prefix = n[:3]; lid = "IA" if prefix == "INA" else "RA"
    cur = source.lookup(lid, "regNo", n)
    ina = source.lookup(lid + "_INACTIVE", "regNo", n)
    prov = [cur.prov(), ina.prov()]
    prob = _source_problem([cur, ina], now, lambda r: _is_current(r), number=n, prefix=prefix)
    if prob:
        return _result(prob, claim=claim, provenance=prov)
    as_of = cur.as_of
    note = None
    if ina.records:
        ist = (ina.records[0].get("status") or "").strip().lower()
        if ist in KNOWN_INACTIVE:
            if cur.records:
                return _result("SOURCE_ERROR", claim=claim, provenance=prov, note="listed as current and as " + ist)  # contradictory source
        elif ist == "registered" and cur.records:
            note = "inactive-list page shows status 'Registered' for a currently listed entry; ignored"
            ina.records = []   # consistent with the current list; not an ended registration
        else:
            return _result("SOURCE_ERROR", claim=claim, provenance=prov, note="unrecognised status on cancelled/surrendered/expired/suspended page: %s" % (ina.records[0].get("status") or "none"))
    if cur.records:
        rec = cur.records[0]; rr = _rec(rec, lid)
        if not claim["name_given"]:
            return _result("LISTED_NAME_NOT_COMPARED", claim=claim, register_record=rr, match_count=1, provenance=prov, as_of=as_of, note=note)
        cmp = compare_names(name, rec["name"])
        if cmp == "EXACT":
            return _result("CONFIRMED_IN_REGISTER", claim=claim, register_record=rr, match_count=1, provenance=prov, as_of=as_of, note=note)
        if cmp in ("LEGAL_FORM_DIFFERS", "SIMILAR", "PROPRIETOR_RECORD"):
            return _result("AMBIGUOUS", {"LEGAL_FORM_DIFFERS": "LEGAL_FORM_DIFFERS", "SIMILAR": "NAME_SIMILAR", "PROPRIETOR_RECORD": "PROPRIETOR_RECORD"}[cmp], claim=claim, register_record=rr, match_count=1, provenance=prov, as_of=as_of, note=note)
        return _result("NAME_DIFFERS", claim=claim, register_record=rr, match_count=1, provenance=prov, as_of=as_of, note=note)
    if ina.records:
        return _result("INACTIVE_IN_REGISTER", claim=claim, register_record=_rec(ina.records[0], ina.list_id), match_count=1, provenance=prov, as_of=as_of)
    reason = "NUMBER_ABSENT"
    if name_searchable(name or ""):  # secondary lookup: does the claimed name exist under another number? failures here never change the status
        nm = source.lookup(lid, "name", name.strip())
        prov.append(nm.prov())
        if nm.status == "OK" and not _source_problem([nm], now, lambda r: True):
            if any(compare_names(name, r.get("name", "")) in ("EXACT", "LEGAL_FORM_DIFFERS", "SIMILAR", "PROPRIETOR_RECORD") for r in nm.records):
                reason = "NAME_LISTED_UNDER_OTHER_NUMBER"
    return _result("NOT_FOUND", reason, claim=claim, match_count=0, provenance=prov, as_of=as_of)


def _name_only(name, category, source, now, claim):
    if not name_searchable(name):
        return _result("NOT_CHECKABLE", "NAME_TOO_GENERIC", claim=claim)
    lists = [category] if category in ("IA", "RA") else ["IA", "RA"]
    rs = [source.lookup(l, "name", name.strip()) for l in lists]
    prov = [r.prov() for r in rs]
    prob = _source_problem(rs, now, lambda r: True)
    if prob:
        return _result(prob, claim=claim, provenance=prov)
    total = sum(r.total for r in rs)
    as_of = min((r.as_of for r in rs if r.as_of), default=None)
    if total == 0:
        return _result("NOT_FOUND", "NAME_ONLY_NO_HIT", claim=claim, match_count=0, provenance=prov, as_of=as_of)
    cands = []
    if total <= MAX_CANDIDATES:
        cands = sorted(({"name": rec["name"], "reg_no": rec["reg_no"], "list": r.list_id} for r in rs for rec in r.records), key=lambda c: c["reg_no"])
    return _result("AMBIGUOUS", "NAME_ONLY", claim=claim, match_count=total, candidates=cands, provenance=prov, as_of=as_of)
