"""The integrated journey: message check first (offline, never waits on the network), then an OPTIONAL, explicitly requested register step.
Invariants (tested): the register step never changes the message posture, claims or indicators; it is placed after urgent guidance and the assessment;
it always carries the 'registration is not identity or offer legitimacy' reminder; a failed lookup changes nothing else."""
import copy
from . import clock
from .engine import analyze
from .registry.api import check_registration

ORDER = ["urgent_steps", "assessment", "steps", "registry", "unavailable", "limitations"]


def journey(req, source=None, registry_request=None, corpus=None):
    res = analyze(req, corpus)
    res["registry"] = None
    res["provenance"]["posture_before_registry"] = res["posture"]
    if registry_request and source is not None and res["posture"] not in ("NEEDS_SITUATION", "ESCALATE", "ASK_FOLLOWUP"):
        before = copy.deepcopy({k: res[k] for k in ("posture", "headline", "claims", "indicators", "urgent_steps", "steps")})
        try:
            res["registry"] = check_registration(registry_request.get("number"), registry_request.get("name"), registry_request.get("category"), source, res["language"], now=clock.now_utc())
        except Exception:
            res["registry"] = None
        after = {k: res[k] for k in before}
        if after != before:   # defensive: can never happen by construction; if it did, discard the register result
            res.update(before); res["registry"] = None
    return res


def journey_violations(res):
    v = []
    if res.get("block_order") != ORDER: v.append("block order")
    reg = res.get("registry")
    if reg:
        if res["posture"] != res["provenance"].get("posture_before_registry"): v.append("registry changed posture")
        if reg.get("effect_on_message_result") != "none": v.append("registry effect not none")
        if "does not show who contacted you" not in reg.get("reminder", "") and "आपसे किसने संपर्क किया" not in reg.get("reminder", ""): v.append("registry reminder missing")
        if res["posture"] in ("NEEDS_SITUATION", "ESCALATE", "ASK_FOLLOWUP"): v.append("registry shown in urgent flow")
    return v
