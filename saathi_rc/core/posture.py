"""Deterministic posture scoring. Weights are author-chosen heuristics (NOT calibrated); documented in the report."""
from .contracts import HIGH_CONCERN, SOME_CONCERN, NO_INDICATORS_FOUND, CONTRADICTED, MIXED, INSUFFICIENT

IND_WEIGHT = {"REMOTE_ACCESS_APP": 3, "CREDENTIAL_REQUEST": 3, "APK_DOWNLOAD": 3, "LOOKALIKE_DOMAIN": 3, "MULE_RECRUITMENT": 3,
              "PERSONAL_PAYEE": 2, "PAYMENT_DEMAND": 2, "UPFRONT_FEE": 2, "AUTHORITY_IMPERSONATION": 2, "SECRECY": 2,
              "PROMPT_INJECTION": 2, "OBFUSCATION": 2, "HIGH_RETURN_RATE": 2}
AUTHORITY_CLAIMS = {"SEBI_REG_CLAIM", "ENDORSEMENT_CLAIM", "AUTHORITY_THREAT", "LINK_OFFICIAL_CLAIM", "ACCOUNT_BLOCK_KYC"}
HC_AT, SC_AT = 4, 2


def score(claims, indicators):
    s = 0
    parts = []
    for i in sorted({x["indicator"] for x in indicators}):
        w = IND_WEIGHT.get(i, 1)
        s += w
        parts.append((i, w))
    for c in claims:
        if c["state"] == CONTRADICTED:
            s += 2
            parts.append((c["claim_type"] + ":CONTRADICTED", 2))
        elif c["state"] == "NOT_ASSESSED" and c["claim_type"] == "PERFORMANCE_CLAIM":
            s += 1
            parts.append(("PERFORMANCE_CLAIM:UNVERIFIABLE", 1))
        elif c["state"] == INSUFFICIENT and c["claim_type"] in AUTHORITY_CLAIMS:
            s += 1
            parts.append((c["claim_type"] + ":INSUFFICIENT", 1))
    return s, parts


def posture_for(claims, indicators):
    s, parts = score(claims, indicators)
    p = HIGH_CONCERN if s >= HC_AT else SOME_CONCERN if s >= SC_AT else NO_INDICATORS_FOUND
    if p == NO_INDICATORS_FOUND and any(c["claim_type"] == "SEBI_REG_CLAIM" and c["state"] in (MIXED, CONTRADICTED) for c in claims):
        p = SOME_CONCERN
    return p, s, parts
