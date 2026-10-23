from copy import deepcopy
def _rename_event_ids(result):
    mapping = {e["event_id"]: e["event_id"].replace("b_v7_", "b_v8_", 1)
        for e in result["events"] + result.get("cancelled_events", [])}
    def visit(value):
        if isinstance(value, dict):
            return {mapping.get(k, k): visit(v) for k, v in value.items()}
        if isinstance(value, list):
            return [visit(v) for v in value]
        return mapping.get(value, value) if isinstance(value, str) else value
    return visit(result)

def _decision_provenance(result, overlay, *, finalization_frame, overlay_sha256):
    """Keep review dependency per decision, including unchanged machine evidence."""
    reviews = {r["review_id"]: r for v in overlay["videos"] for r in v.get("reviews", [])}
    def dependencies(value):
        if isinstance(value, dict):
            found = {value["review_id"]} if value.get("review_id") in reviews else set()
            for child in value.values():
                found |= dependencies(child)
            return found
        if isinstance(value, list):
            return set().union(*(dependencies(child) for child in value)) if value else set()
        return set()
    rows = []
    for item in result.get("events", []) + result.get("decisions", []):
        if item.get("status") not in ("accepted", "pending", "invalid", "resolved_not_eligible"):
            continue
        ids = sorted(dependencies(item))
        origin = item.get("decision_origin") or (
            "SOURCE_REVIEW_ASSISTED_REPLAY" if ids else "REPLAYED_MACHINE_RULES")
        rows.append({"event_id": item.get("event_id"), "track_id": item.get("track_id"),
            "physical_unit_id": item.get("physical_unit_id"), "episode_id": item.get("episode_id"),
            "passage_id": item.get("passage_id"), "status": item.get("status"),
            "candidate_decision_frame": item.get("candidate_decision_frame", item.get("decision_frame")),
            "offline_finalization_frame": finalization_frame,
            "decision_origin": origin, "p1_review_ids": ids,
            "review_claim_types": sorted({reviews[rid].get("claim_type", "UNKNOWN") for rid in ids}),
            "overlay_sha256": overlay_sha256 if ids else None,
            "not_an_automatic_role_or_identity_prediction": bool(ids)})
    result["v8_decision_provenance"] = rows
