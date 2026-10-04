"""Trusted-source corpus loader + eligibility rules."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "sources")


class Corpus:
    def __init__(self, path=None):
        path = path or os.path.join(SRC, "corpus.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.version = data["corpus_version"]
        self.retrieved_at_nominal = data.get("retrieved_at_nominal")   # RC CH-05: needed for snapshot freshness
        self.passages = {p["passage_id"]: p for p in data["passages"]}
        with open(os.path.join(SRC, "official_domains.json"), encoding="utf-8") as f:
            self.domains = json.load(f)

    def get(self, pid):
        return self.passages.get(pid)

    def eligible(self, pids):
        """Eligibility rule: >=1 T1/T2 passage OR >=2 distinct publishers at T3."""
        ps = [self.passages[p] for p in pids if p in self.passages]
        if any(p["tier"] in ("T1", "T2") for p in ps):
            return True
        return len({p["publisher"] for p in ps if p["tier"] == "T3"}) >= 2
