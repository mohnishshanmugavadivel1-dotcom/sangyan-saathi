"""Evidence freshness (CH-05). Real date from saathi_rc.clock. Two layers:
 1. per-claim: a SUPPORTED/CONTRADICTED state needs decisive passages that are not older than the limit for that kind of fact.
    'volatile' facts (coverage of badges/handles/scopes, domain lists, registration rules) 365 days; 'stable' facts 5 years.
 2. corpus snapshot: collected > 90 days ago -> notice; > 365 days ago (or collection date in the future = clock/data problem) -> every
    SUPPORTED/CONTRADICTED claim is shown as INSUFFICIENT. Staleness never removes urgent guidance and never lowers the concern posture:
    it only weakens what the sources are said to prove."""
import datetime as dt

VOLATILE = {"VERIFIED_BADGE_CLAIM", "VALID_HANDLE_CLAIM", "CHAKSHU_SCOPE_CLAIM", "SCORES_SCOPE_CLAIM", "LINK_OFFICIAL_CLAIM", "SEBI_REG_CLAIM"}
MAX_AGE = {"volatile": 365, "stable": 1825}
SNAPSHOT_AGING_DAYS = 90
SNAPSHOT_STALE_DAYS = 365
DECISIVE = ("supports", "contradicts", "format_rule")


def _d(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def snapshot_info(corpus, today):
    ret = _d(getattr(corpus, "retrieved_at_nominal", None) or corpus.passages and max(p["retrieved_at"] for p in corpus.passages.values()))
    if ret is None:
        return {"snapshot_date": None, "age_days": None, "status": "UNKNOWN"}
    age = (today - ret).days
    status = "STALE" if age > SNAPSHOT_STALE_DAYS or age < -1 else "AGING" if age > SNAPSHOT_AGING_DAYS else "OK"
    return {"snapshot_date": ret.isoformat(), "age_days": age, "status": status}


def apply(claims, corpus, today):
    """-> (claims', snapshot_info). Claims are copied; decisive states are downgraded to INSUFFICIENT when evidence is too old."""
    snap = snapshot_info(corpus, today)
    out = []
    for c in claims:
        c = dict(c)
        c["freshness"] = {"checked": True, "downgraded": False, "reason": None, "oldest_decisive_age_days": None}
        if c["state"] in ("SUPPORTED", "CONTRADICTED"):
            ages = []
            for e in c.get("evidence", []):
                if e.get("relation") in DECISIVE:
                    d = _d(e.get("date_of_source"))
                    ages.append(None if d is None else (today - d).days)
            limit = MAX_AGE["volatile" if c["claim_type"] in VOLATILE else "stable"]
            known = [a for a in ages if a is not None]
            newest = min(known) if known else None
            c["freshness"]["oldest_decisive_age_days"] = newest
            reason = None
            if snap["status"] in ("STALE", "UNKNOWN"):
                reason = "source snapshot is stale or undated"
            elif not known or newest is None:
                reason = "evidence has no usable date"
            elif newest > limit:
                reason = "newest decisive source is %d days old (limit %d for this kind of fact)" % (newest, limit)
            elif newest < -1:
                reason = "evidence is dated in the future relative to the system clock"
            if reason:
                c["freshness"].update(downgraded=True, reason=reason)
                c["state_before_freshness"] = c["state"]
                c["state"] = "INSUFFICIENT"
                c["explanation"] = "Not enough current evidence: " + reason + ". Earlier reading: " + c["explanation"]
        out.append(c)
    return out, snap
