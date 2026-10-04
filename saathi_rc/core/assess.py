"""Step 5: evidence-to-claim assessment (rule-based over a CURATED claim->passage relation table).

There is deliberately NO free-text inference model here: the relation between a claim type and a source
passage is hand-curated and auditable. Consequences (documented as limitations): the system can only assess claim
types it knows; it cannot reason about novel claims; it states NOT_ASSESSED / INSUFFICIENT instead.
"""
import re
from datetime import date

from .contracts import SUPPORTED, CONTRADICTED, MIXED, INSUFFICIENT, NOT_ASSESSED
from .normalize import mask_identifier
from .retrieve import retrieve

from .. import clock
OUTDATED_AFTER_DAYS = 90   # RC change CH-05: the hard-coded TODAY was removed; the date now comes from saathi_rc.clock (injectable)

REL = {
    "GUARANTEED_RETURNS": {"contradicts": ["MONEYLIFE-PR27-a", "UNIVEST-b", "MOF-SEBI-REG-WARN"]},
    "OFFICIAL_PLATFORM_CLAIM": {"contradicts": ["MONEYLIFE-PR27-b", "TEAMLEASE-PR27-b"]},
    "ACCOUNT_HANDLING": {"contradicts": ["SEBI-PR14-2026-a", "SEBI-PR14-2026-b", "SEBI-PR14-2026-d"]},
    "UPI_PIN_TO_RECEIVE": {"contradicts": ["FRIENDSTAXI-UPIPIN", "CASHFREE-UPIPIN"]},
    "BANK_ASKS_OTP_CLAIM": {"contradicts": ["TOI-RBI-BEAWARE", "TIMESNOW-RBI-OTP", "ANALYTICS-RBI-OTP"]},
    "AUTHORITY_THREAT": {"context": ["SANCHAR-FAQ-EXAMPLES", "ETGOV-DOT-CALLS", "ANALYTICS-SAFEACCT"]},
    "ACCOUNT_BLOCK_KYC": {"context": ["TOI-RBI-BEAWARE-URG", "TIMESNOW-RBI-OTP"]},
    "REFUND_CLAIM": {"context": ["TOI-RBI-BEAWARE-URG", "CASHFREE-UPIPIN"]},
    "ENDORSEMENT_CLAIM": {"context": ["TEAMLEASE-PR27-c"]},
    "SEBI_REG_CLAIM": {"format": ["INDBUS-REGFMT", "INVSIFY-REGFMT"], "verify": ["SEBI-PR14-2026-c"]},
    "CHAKSHU_SCOPE_CLAIM": {"contradicts_loss": ["SANCHAR-FAQ-SCOPE", "SANCHAR-SFC"], "window": ["SANCHAR-SFC-30"]},
    "SCORES_SCOPE_CLAIM": {"contradicts": ["MONEYLIFE-PR27-c"], "supports": ["UNIVEST-a"]},
    "VALID_HANDLE_CLAIM": {"supports": ["INVESTING-VALID-RULE", "REDIFF-SEBICHECK"], "contradicts": ["SCC-VALID-ADDITIONAL"]},
    "VERIFIED_BADGE_CLAIM": {"context": ["NIE-BADGE", "TIMESNOW-BADGE"]},
    "LINK_OFFICIAL_CLAIM": {"supports": ["SEBI-HOME-LINKS", "SEBI-PR14-2026-c"]},
}
FD_CONTEXT = re.compile(r"(?i)\b(fixed deposit|fd|deposit scheme|nbfc|p\.a\.|per annum|recurring deposit)\b")
SECURITIES_CONTEXT = re.compile(r"(?i)\b(stock|share|shares|nifty|sensex|ipo|trading|trade|mutual fund|mutual funds|demat|f&o|options|calls|tips|analyst|telegram|whatsapp)\b")


def _ev(corpus, pid, relation, score=None):
    p = corpus.get(pid)
    return {"passage_id": pid, "publisher": p["publisher"], "title": p["title"], "url": p["url"], "tier": p["tier"],
            "date_of_source": p["date_of_source"], "retrieved_at": p["retrieved_at"], "quote": p["text"],
            "relation": relation}


def _age_days(corpus, pids):
    ds = []
    for pid in pids:
        d = corpus.get(pid)["date_of_source"]
        y, m, dd = [int(x) for x in d.split("-")]
        ds.append((clock.today() - date(y, m, dd)).days)
    return max(ds) if ds else 0


def _finish(corpus, state, ev_items, explanation, limitation=None, require_eligible=True, tier_override=None):
    """Apply eligibility rule to SUPPORTED/CONTRADICTED and return (state, evidence, explanation, limitations)."""
    lim = []
    if limitation:
        lim.append(limitation)
    if state in (SUPPORTED, CONTRADICTED) and require_eligible and tier_override is None:
        pids = [e["passage_id"] for e in ev_items if e["relation"] in ("contradicts", "supports", "format_rule")]
        if not corpus.eligible(pids):
            lim.append("Evidence below eligibility threshold (needs a T1/T2 source or two distinct T3 publishers); downgraded.")
            state = INSUFFICIENT
    if any(e["tier"] == "T3" for e in ev_items) and not any(e["tier"] in ("T1", "T2") for e in ev_items):
        lim.append("Supporting passages are secondary reports (news/blog) of official statements, not the official documents themselves.")
    return state, ev_items, explanation, lim


def assess_claim(corpus, claim, norm, registry=None):
    ct = claim["claim_type"]
    text = norm["text"]
    sent = claim.get("sentence", "")
    q = claim.get("sentence", "") + " " + claim.get("snippet", "")
    hits = {h["passage_id"]: h for h in retrieve(corpus, ct, q)} if ct != "LINK_OFFICIAL_CLAIM" else {}
    rel = REL.get(ct, {})
    ev = lambda key, relname: [_ev(corpus, pid, relname) for pid in rel.get(key, []) if (pid in hits or ct in ("LINK_OFFICIAL_CLAIM",))]

    if ct in ("PERFORMANCE_CLAIM", "MARKET_PREDICTION"):
        msg = ("A personal profit/return figure or a market forecast cannot be verified from trusted sources, so it is not assessed. "
               "This tool does not give investment advice, stock tips or price predictions.") if ct == "MARKET_PREDICTION" else \
              ("A personal profit/return figure cannot be verified from trusted sources, so it is not assessed. Screenshots and testimonials are easy to fake.")
        return dict(state=NOT_ASSESSED, evidence=[], explanation=msg, limitations=["No verifiable source exists for this kind of claim."])

    if ct == "GUARANTEED_RETURNS":
        if FD_CONTEXT.search(text) and not SECURITIES_CONTEXT.search(text):
            return dict(state=INSUFFICIENT, evidence=[], explanation="This looks like a fixed-rate deposit, not a market investment. The retrieved sources are about securities-market 'guaranteed/assured returns', so they do not settle this claim. Check the issuer's credit rating and regulator status independently.",
                        limitations=["Domain mismatch: corpus does not cover deposits/NBFC schemes."])
        e = ev("contradicts", "contradicts")
        s, e, x, lim = _finish(corpus, CONTRADICTED, e,
                               "Sources reporting SEBI's cautions say promises of assured / risk-free / guaranteed returns are not feasible in regulated market practice and are a red flag. This does NOT by itself prove the sender is fraudulent.")
        return dict(state=s, evidence=e, explanation=x, limitations=lim)

    if ct == "OFFICIAL_PLATFORM_CLAIM":
        strong = re.search(r"(?i)guarantee|institutional", claim.get("sentence", ""))
        if strong:
            e = ev("contradicts", "contradicts")
            s, e, x, lim = _finish(corpus, CONTRADICTED, e,
                                   "SEBI cautions (as reported) describe 'institutional trading accounts' and 'guaranteed IPO allotments' offered via messaging groups as baseless and designed to deceive.")
            return dict(state=s, evidence=e, explanation=x, limitations=lim)
        return dict(state=INSUFFICIENT, evidence=ev("contradicts", "context"), explanation="Offers of special IPO/block-deal access cannot be verified from the text. Use only SEBI-registered intermediaries.", limitations=["Claim wording not covered precisely by the sources."])

    if ct == "ACCOUNT_HANDLING":
        e = ev("contradicts", "contradicts")
        s, e, x, lim = _finish(corpus, CONTRADICTED, e,
                               "SEBI's press release PR 14/2026 says people offering 'account handling' with risk-free profits are not registered with SEBI, and advises investors not to trust such claims or share account credentials.")
        return dict(state=s, evidence=e, explanation=x, limitations=lim)

    if ct == "UPI_PIN_TO_RECEIVE":
        e = ev("contradicts", "contradicts")
        s, e, x, lim = _finish(corpus, CONTRADICTED, e, "A UPI PIN is used to send/authorise money, never to receive it.")
        return dict(state=s, evidence=e, explanation=x, limitations=lim)

    if ct == "BANK_ASKS_OTP_CLAIM":
        e = ev("contradicts", "contradicts")
        s, e, x, lim = _finish(corpus, CONTRADICTED, e, "As reported from RBI guidance, banks do not ask customers for OTPs/PINs.")
        return dict(state=s, evidence=e, explanation=x, limitations=lim)

    if ct == "SEBI_REG_CLAIM":
        regs = norm["entities"]["reg_numbers"]
        fmt_ev = [_ev(corpus, pid, "format_rule") for pid in rel["format"]]
        ver_ev = [_ev(corpus, pid, "context") for pid in rel["verify"]]
        if not regs:
            return dict(state=INSUFFICIENT, evidence=ver_ev, explanation="A claim of SEBI registration was made without a registration number. Registration cannot be checked from the text; look the name up on SEBI's intermediaries page.",
                        limitations=["Registry lookup is not available in this prototype."])
        bad = [r for r in regs if not r["well_formed"]]
        if bad:
            s, e, x, lim = _finish(corpus, CONTRADICTED, fmt_ev + ver_ev,
                                   "The registration number is not in the standard format (prefix INZ/INH/INA followed by 9 digits per secondary sources), so it cannot be a valid SEBI registration number as written.",
                                   limitation="Format check only; a mistyped but real number would also fail. Verify on SEBI's site.")
            return dict(state=s, evidence=e, explanation=x, limitations=lim)
        if registry is not None:
            worst, notes = SUPPORTED, []
            for r in regs:
                rec = registry.lookup(r["raw"])
                if rec is None:
                    worst, notes = CONTRADICTED, notes + ["%s not found in registry" % r["raw"]]
                    continue
                name_tokens = set(re.findall(r"[a-z]+", rec["name"].lower())) - {"pvt", "ltd", "llp", "private", "limited"}
                msg_tokens = set(re.findall(r"[a-z]+", text.lower()))
                overlap = len(name_tokens & msg_tokens) / max(1, len(name_tokens))
                if rec["status"] != "ACTIVE":
                    worst = CONTRADICTED; notes.append("%s status %s" % (r["raw"], rec["status"]))
                elif overlap < 0.5:
                    if worst == SUPPORTED:
                        worst = MIXED
                    notes.append("%s is ACTIVE but registered to a different name than claimed" % r["raw"])
                else:
                    notes.append("%s ACTIVE, name consistent" % r["raw"])
            fx = {"passage_id": "FIXTURE-REGISTRY", "publisher": "FIXTURE (fictional registry for testing)", "title": "Test fixture", "url": "n/a",
                  "tier": "FIXTURE", "date_of_source": "2026-10-02", "retrieved_at": "2026-10-02T00:00:00Z", "quote": "; ".join(notes),
                  "relation": "supports" if worst == SUPPORTED else "contradicts"}
            return dict(state=worst, evidence=[fx] + ver_ev, explanation="Registry fixture result: " + "; ".join(notes),
                        limitations=["PRIVILEGED TEST FIXTURE: not a real SEBI lookup. Live lookups are not implemented."])
        return dict(state=INSUFFICIENT, evidence=ver_ev, explanation="The registration number is well-formed, but this prototype cannot look it up on SEBI's register, so it is neither confirmed nor refuted. A well-formed number can still be copied from someone else.",
                    limitations=["Live SEBI registry lookup not available (offline prototype)."])

    if ct in ("AUTHORITY_THREAT", "ACCOUNT_BLOCK_KYC", "REFUND_CLAIM", "ENDORSEMENT_CLAIM"):
        e = [_ev(corpus, pid, "context") for pid in rel.get("context", [])]
        msgs = {
            "AUTHORITY_THREAT": "Threats of arrest/penalty/disconnection in the name of an authority are a recognised fraud pattern, but this specific message's sender cannot be verified from the text. Verify only through an official channel you look up yourself.",
            "ACCOUNT_BLOCK_KYC": "The claim that an account will be blocked cannot be verified from the text. Banks/brokers do not ask for OTPs or PINs; contact the institution through its official app or number.",
            "REFUND_CLAIM": "A refund claim cannot be verified from the text. Receiving money never requires sharing an OTP or entering a UPI PIN.",
            "ENDORSEMENT_CLAIM": "Endorsement by an official, celebrity or institution cannot be verified from the text; impersonated profiles and manipulated content are reported by SEBI-related sources.",
        }
        return dict(state=INSUFFICIENT, evidence=e, explanation=msgs[ct], limitations=["Context sources describe the pattern; they do not verify this particular message."])

    if ct == "CHAKSHU_SCOPE_CLAIM":
        if re.search(r"(?i)lost|loss|already (paid|transferred)", sent):
            e = [_ev(corpus, pid, "contradicts") for pid in rel["contradicts_loss"]]
            s, e, x, lim = _finish(corpus, CONTRADICTED, e, "The official Sanchar Saathi page says Chakshu is not for reporting financial fraud/loss: if you have already lost money, report to 1930 or cybercrime.gov.in.")
            return dict(state=s, evidence=e, explanation=x, limitations=lim)
        m = re.search(r"(?i)within\s+(\d+)\s+days", sent)
        if m:
            e = [_ev(corpus, pid, "contradicts" if m.group(1) != "30" else "supports") for pid in rel["window"]]
            if m.group(1) == "30":
                s, e, x, lim = _finish(corpus, SUPPORTED, e, "Official page: report suspected fraud communication within 30 days for action.")
            else:
                s, e, x, lim = MIXED, e, "A reporting window exists, but the official page says 30 days for action (not %s)." % m.group(1), []
            return dict(state=s, evidence=e, explanation=x, limitations=lim)
        return dict(state=INSUFFICIENT, evidence=[], explanation="Claim about Chakshu could not be matched to a specific official statement.", limitations=[])

    if ct == "SCORES_SCOPE_CLAIM":
        e = [_ev(corpus, pid, "contradicts") for pid in rel["contradicts"]] + [_ev(corpus, pid, "conflicts") for pid in rel["supports"]]
        return dict(state=MIXED, evidence=e, explanation="Sources conflict: one reports that dealings with unregistered entities are outside SEBI's investor protection framework (including SCORES), another suggests reporting fraudulent advisers on SCORES. No source supports a promise of money recovery.",
                    limitations=["Conflicting secondary sources; official SCORES scope document not retrieved.", "No recovery guarantee exists in the sources."])

    if ct == "VALID_HANDLE_CLAIM":
        if re.search(r"(?i)\b(only|must|every|all|definitely|any other)\b", sent):
            e = [_ev(corpus, pid, "supports") for pid in rel["supports"]] + [_ev(corpus, pid, "contradicts") for pid in rel["contradicts"]]
            return dict(state=MIXED, evidence=e, explanation="Reports say SEBI-registered intermediaries collecting funds via UPI must use validated '@valid' IDs, but also that @valid is 'an additional payment option, not a replacement'. A non-@valid ID is a reason to verify, not proof of a scam.",
                        limitations=["Secondary reports; SEBI circular text not retrieved."])
        return dict(state=INSUFFICIENT, evidence=[], explanation="Claim about @valid handles is not specific enough to assess.", limitations=[])

    if ct == "VERIFIED_BADGE_CLAIM":
        e = [_ev(corpus, pid, "context") for pid in rel["context"]]
        if re.search(r"(?i)guarantee|cannot lose|can't lose", sent):
            return dict(state=MIXED, evidence=e, explanation="A 'verified' badge exists for SEBI-registered stockbroker apps on Google Play (as reported in March 2026). Nothing in the sources says it guarantees against market loss.",
                        limitations=["Secondary reports from March 2026."])
        if re.search(r"(?i)\b(all|every|now covers|including)\b", sent):
            age = _age_days(corpus, rel["context"])
            return dict(state=INSUFFICIENT, evidence=e, explanation="As of the March 2026 reports, the badge was rolled out for stockbroker apps 'for now', with extension to other intermediaries planned. The current coverage is not in the corpus.",
                        limitations=["Evidence is %d days old (> %d): possibly outdated." % (age, OUTDATED_AFTER_DAYS)])
        return dict(state=INSUFFICIENT, evidence=e, explanation="Not specific enough to assess.", limitations=[])

    if ct == "LINK_OFFICIAL_CLAIM":
        d = claim["_domain"]
        e = [_ev(corpus, pid, "supports") for pid in rel["supports"]]
        if d["kind"] == "observed_official":
            s, e, x, lim = _finish(corpus, SUPPORTED, e,
                                   "The link's registrable domain (%s) is a domain observed as official on pages fetched for this sprint. This does not verify that the MESSAGE itself came from that organisation." % d["registrable"])
            return dict(state=s, evidence=e, explanation=x, limitations=lim)
        if d["kind"] == "assumed_official":
            return dict(state=INSUFFICIENT, evidence=[], explanation="Domain %s is plausibly official but was not verified in this prototype's corpus." % d["registrable"], limitations=["Domain not in observed list."])
        why = "; ".join(d["reasons"]) or "domain not found in the list of official domains observed"
        return dict(state=INSUFFICIENT, evidence=e[:1], explanation="The link is NOT on a domain observed as official (%s). Absence from the list is not proof of fraud (SEBI also links services outside sebi.gov.in), so this is INSUFFICIENT rather than contradicted." % why,
                    limitations=["Domain list is not exhaustive."])
    return dict(state=NOT_ASSESSED, evidence=[], explanation="Claim type not supported by the assessor.", limitations=[])


# ----------------------------- entity-derived claims / indicators -----------------------------
def classify_domain(corpus, u):
    cfg = corpus.domains
    host = u["host"]
    reasons = []
    full = u["full_text"]
    kws = cfg["org_keywords"]
    official_strings = ["sebi.gov.in", "sancharsaathi.gov.in", "cybercrime.gov.in"]
    for suf in cfg["observed_suffix"]:
        if host == suf or host.endswith("." + suf):
            if u["userinfo"]:
                reasons.append("userinfo '%s@' placed before the real host" % u["userinfo"])
                break
            return {"kind": "observed_official", "registrable": u["registrable"], "reasons": []}
    if host in cfg["observed_exact"]:
        return {"kind": "observed_official", "registrable": u["registrable"], "reasons": []}
    for suf in cfg["assumed_suffix"]:
        if host == suf or host.endswith("." + suf):
            return {"kind": "assumed_official", "registrable": u["registrable"], "reasons": []}
    if u["userinfo"] and "." in u["userinfo"]:
        reasons.append("deceptive 'userinfo@' prefix: real host is %s" % host)
    for s in official_strings:
        if s in full and not (host == s or host.endswith("." + s)):
            reasons.append("contains '%s' but real host is %s" % (s, host))
    hostcheck = (u["host_decoded"] + " " + host).lower()
    if any(k in hostcheck for k in kws):
        reasons.append("host contains an official-organisation keyword but is not an observed official domain")
    return {"kind": "unlisted", "registrable": u["registrable"], "reasons": reasons, "lookalike": bool(reasons)}


def derive(corpus, norm, ext):
    """Add claims/indicators that come from entities (links, reg numbers) and normalisation flags."""
    ents = norm["entities"]
    text_no_urls = norm["text"]
    for u in ents["urls"]:
        text_no_urls = text_no_urls.replace(u["raw"], " ")
    org_in_prose = bool(re.search(r"(?i)\b(sebi|nsdl|cdsl|rbi|npci|scores|nse|bse)\b|सेबी|செபி", text_no_urls))
    claims, inds = [], []
    for u in ents["urls"]:
        d = classify_domain(corpus, u)
        full = u["full_text"]
        names_org = org_in_prose or any(s in full for s in ("sebi.gov.in", "sancharsaathi.gov.in", "cybercrime.gov.in")) or d.get("lookalike")
        if u["shortener"]:
            inds.append({"indicator": "SHORTENED_LINK", "snippet": u["raw"][:80], "note": "link hides its real destination"})
        if d.get("lookalike"):
            inds.append({"indicator": "LOOKALIKE_DOMAIN", "snippet": u["raw"][:80], "note": "; ".join(d["reasons"])})
        if names_org and not u["shortener"] and u["host"] not in ("t.me", "chat.whatsapp.com", "wa.me"):
            claims.append({"claim_type": "LINK_OFFICIAL_CLAIM", "snippet": u["raw"][:80], "sentence": "", "match": u["raw"], "_domain": d})
    if norm["flags"]["zero_width_inside_word"] or norm["flags"]["mixed_script_token"] or norm["flags"].get("leet_folded"):
        inds.append({"indicator": "OBFUSCATION", "snippet": "(characters)", "note": "hidden/look-alike characters inside words were normalised before analysis"})
    if ents["reg_numbers"] and not any(c["claim_type"] == "SEBI_REG_CLAIM" for c in ext["claims"]):
        claims.append({"claim_type": "SEBI_REG_CLAIM", "snippet": ents["reg_numbers"][0]["raw"], "sentence": "", "match": ents["reg_numbers"][0]["raw"]})
    return claims, inds
