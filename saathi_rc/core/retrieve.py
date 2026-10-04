"""Step 4: trusted-source retrieval. Topic filter + lightweight BM25-style lexical scoring. Deterministic.
Each hit records source identity and the retrieval timestamp."""
import math
import re
from collections import Counter

# claim type -> topics that may be relevant (language-independent after extraction)
CLAIM_TOPICS = {
    "GUARANTEED_RETURNS": ["guaranteed_returns"],
    "SEBI_REG_CLAIM": ["sebi_registration", "reg_format", "verify_registration"],
    "AUTHORITY_THREAT": ["authority_threat", "safe_account"],
    "ACCOUNT_BLOCK_KYC": ["urgency", "bank_asks_otp", "official_callback"],
    "OFFICIAL_PLATFORM_CLAIM": ["official_platform", "ipo_claim"],
    "ACCOUNT_HANDLING": ["account_handling"],
    "PERFORMANCE_CLAIM": [],
    "MARKET_PREDICTION": [],
    "ENDORSEMENT_CLAIM": ["endorsement", "impersonation"],
    "REFUND_CLAIM": ["upi_pin", "urgency"],
    "UPI_PIN_TO_RECEIVE": ["upi_pin"],
    "BANK_ASKS_OTP_CLAIM": ["bank_asks_otp"],
    "CHAKSHU_SCOPE_CLAIM": ["chakshu_scope", "chakshu_window"],
    "SCORES_SCOPE_CLAIM": ["scores_scope"],
    "VALID_HANDLE_CLAIM": ["valid_handle"],
    "VERIFIED_BADGE_CLAIM": ["verified_badge"],
    "LINK_OFFICIAL_CLAIM": ["official_domains"],
}


def _tok(s):
    return re.findall(r"[a-z0-9@\.]+", s.lower())


def retrieve(corpus, claim_type, query_text, k=6):
    topics = set(CLAIM_TOPICS.get(claim_type, []))
    cands = [p for p in corpus.passages.values() if topics & set(p["topics"])]
    if not cands:
        return []
    docs = [Counter(_tok(p["text"])) for p in cands]
    n = len(cands)
    avgdl = sum(sum(d.values()) for d in docs) / n
    df = Counter()
    for d in docs:
        for t in d:
            df[t] += 1
    q = _tok(query_text)
    scored = []
    for p, d in zip(cands, docs):
        dl = sum(d.values())
        s = 0.0
        for t in set(q):
            if t in d:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * d[t] * 2.2 / (d[t] + 1.2 * (0.25 + 0.75 * dl / avgdl))
        s += 0.01 * len(topics & set(p["topics"]))      # topic overlap tiebreak
        scored.append((s, p["passage_id"]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [{"passage_id": pid, "score": round(sc, 4), "retrieved_at": corpus.passages[pid]["retrieved_at"]} for sc, pid in scored[:k]]
