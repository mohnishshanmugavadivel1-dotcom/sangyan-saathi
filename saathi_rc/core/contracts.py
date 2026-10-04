"""Input/output contracts, constants and a dependency-free validator.

States (spec): SUPPORTED, CONTRADICTED, MIXED, INSUFFICIENT, NOT_ASSESSED.
Postures never include a 'safe' verdict: NO_INDICATORS_FOUND is explicitly NOT a safety guarantee.
"""
SUPPORTED, CONTRADICTED, MIXED, INSUFFICIENT, NOT_ASSESSED = (
    "SUPPORTED", "CONTRADICTED", "MIXED", "INSUFFICIENT", "NOT_ASSESSED")
STATES = (SUPPORTED, CONTRADICTED, MIXED, INSUFFICIENT, NOT_ASSESSED)
HIGH_CONCERN, SOME_CONCERN, NO_INDICATORS_FOUND, ABSTAIN = (
    "HIGH_CONCERN", "SOME_CONCERN", "NO_INDICATORS_FOUND", "ABSTAIN")
POSTURES = (HIGH_CONCERN, SOME_CONCERN, NO_INDICATORS_FOUND, ABSTAIN)
INPUT_TYPES = ("text", "ocr_text", "image_stub")
SITUATIONS = ("NO_ACTION_YET", "PAID_MONEY", "SHARED_CREDENTIALS", "INSTALLED_REMOTE_APP", "CLICKED_LINK", "UNKNOWN")
LOSS_SITUATIONS = ("PAID_MONEY", "SHARED_CREDENTIALS", "INSTALLED_REMOTE_APP")
LANG_SUPPORT = ("supported", "limited", "unsupported")

REQUEST_SCHEMA = {
    "type": "object",
    "required": ["text"],
    "properties": {
        "request_id": {"type": "string"},
        "input_type": {"enum": list(INPUT_TYPES)},
        "text": {"type": "string", "maxLength": 20000},
        "user_situation": {"enum": list(SITUATIONS)},
        "output_language": {"enum": ["en", "hi"]},
        "registry_fixture": {"type": ["object", "null"]},
    },
    "additionalProperties": False,
}

RESULT_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "pipeline_version", "request_id", "posture", "headline", "language",
                 "claims", "indicators", "next_steps", "limitations", "abstention", "provenance"],
    "properties": {
        "posture": {"enum": list(POSTURES)},
        "claims": {"type": "array", "items": {"type": "object",
                   "required": ["claim_id", "claim_type", "snippet", "state", "evidence", "explanation"]}},
        "indicators": {"type": "array", "items": {"type": "object", "required": ["indicator", "snippet", "note"]}},
        "next_steps": {"type": "array", "items": {"type": "object", "required": ["action_id", "text", "sources"]}},
    },
}


class ContractError(ValueError):
    pass


def validate_request(req):
    if not isinstance(req, dict):
        raise ContractError("request must be an object")
    extra = set(req) - set(REQUEST_SCHEMA["properties"])
    if extra:
        raise ContractError("unknown request fields: %s" % sorted(extra))
    if "text" not in req or not isinstance(req["text"], str):
        raise ContractError("'text' (string) is required")
    if req.get("input_type", "text") not in INPUT_TYPES:
        raise ContractError("bad input_type")
    if req.get("user_situation", "UNKNOWN") not in SITUATIONS:
        raise ContractError("bad user_situation")
    if req.get("output_language", "en") not in ("en", "hi"):
        raise ContractError("bad output_language")
    return True


def validate_result_shape(res):
    """Structural validation without third-party libs (a jsonschema check is also run in tests if available)."""
    errs = []
    for k in RESULT_SCHEMA["required"]:
        if k not in res:
            errs.append("missing key " + k)
    if res.get("posture") not in POSTURES:
        errs.append("bad posture")
    for c in res.get("claims", []):
        for k in RESULT_SCHEMA["properties"]["claims"]["items"]["required"]:
            if k not in c:
                errs.append("claim missing " + k)
        if c.get("state") not in STATES:
            errs.append("bad state " + str(c.get("state")))
    for a in res.get("next_steps", []):
        if not a.get("sources"):
            errs.append("action without sources: " + str(a.get("action_id")))
    return errs
