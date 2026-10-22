"""User-authorized invalid/+0 policy on the immutable B v5 measured-track engine.

No detector, tracker, ReID or enhancement executes here. A rejected ambiguous
passage is an intentional exclusion, not proof that no traffic passed. Raw BC,
the 60-source-frame clock and genuine measured-return semantics stay in B v5.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json

import phase_8_b_v5_counting as previous


SUPPORTED_CATEGORIES = frozenset(("motorcycle", "car", "truck", "bus", "pedestrian"))
DISPLAY_PREFIXES = {**previous.DISPLAY_PREFIXES, "bus": "B"}
BUSINESS_TAXONOMY = {"pickup": "truck", "cargo_van": "car", "minivan": "car",
                     "angkot": "car", "bus": "bus"}
AMBIGUOUS_KINDS = frozenset(("POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT",
    "POSSIBLE_SCOPED_UNIT_OR_COMPONENT_AMBIGUITY", "UNVERIFIED_ORIGIN_HANDOFF"))
IDENTITY_REASONS = frozenset(("UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE",
    "IDENTITY_CONTINUITY_UNRESOLVED_FOR_TIMEOUT", "RAW_TRACK_CHANGED_DURING_PASSAGE",
    "TIMEOUT_RAW_TRACK_HANDOFF_UNRESOLVED", "RAW_CONTEXT_CHANGED_WITHOUT_PHYSICAL_CONTINUITY_PROOF",
    "ORIGIN_TIMER_CONTEXT_CONTINUITY_UNRESOLVED", "CROSS_CATEGORY_UNIT_OR_COMPONENT_UNRESOLVED",
    "SCOPED_UNIT_AMBIGUITY", "UNVERIFIED_ORIGIN_HANDOFF"))


def experimental_counting_policy():
    return {"schema_version": "phase8_b_v6_counting_policy_v1",
        "status": "USER_POLICY_IMPLEMENTED_RESEARCH_NOT_PRODUCTION_VALIDATED",
        "ambiguous_unit_decision": "INVALID_PLUS_ZERO_PER_PASSAGE",
        "opposite_direction": "DISTINCT_VALID_PASSAGES_NOT_DUPLICATES",
        "timeout": "ELIGIBLE_LAST_ORIGIN_PLUS60_NO_RELEVANT_IDENTITY_CONFLICT",
        "appearing_away": "NOT_ELIGIBLE_FROM_APPEARANCE_ALONE",
        "unknown_person": "KEEP_PENDING_NOT_AUTOMATIC_PEDESTRIAN_OR_INVALID",
        "business_taxonomy": deepcopy(BUSINESS_TAXONOMY),
        "subtype_recognition": "POSITIVE_SOURCE_BOUND_EVIDENCE_REQUIRED",
        "bus_display_prefix": "B"}


def _controls(policy):
    value = policy.get("v6_counting")
    expected = experimental_counting_policy()
    previous._require(isinstance(value, dict) and all(value.get(key) == wanted
        for key, wanted in expected.items()), "Explicit supported B v6 counting policy required")
    previous._require("bus" in policy.get("supported_categories", [])
        and policy.get("display_category_prefixes") == DISPLAY_PREFIXES,
        "BUS category and B passage prefix must be explicitly configured")
    previous._require(policy.get("timeout_frames") == 60
        and policy.get("timeout_clock") == "last_observed_origin",
        "B v6 must preserve the agreed 60 source-frame last-origin clock")
    return deepcopy(value)


def business_category(raw_class_name, *, vehicle_subtype=None, subtype_evidence=None):
    """Map only a known positive subtype; do not infer it from a raw car label."""
    if vehicle_subtype is None:
        return raw_class_name
    previous._require(vehicle_subtype in BUSINESS_TAXONOMY, "Unknown business vehicle subtype")
    previous._require(isinstance(subtype_evidence, dict)
        and subtype_evidence.get("verified") is True
        and subtype_evidence.get("claim_type") in ("USER_REVIEW", "SOURCE_BOUND_SUBTYPE_REVIEW",
            "ADJUDICATED_AI_PIXELS_REVIEW") and bool(subtype_evidence.get("evidence_ref")),
        "Business subtype requires positive, explicit source-bound evidence")
    previous._require(raw_class_name in previous.VEHICLE_CLASSES,
        "Business vehicle subtype cannot relabel person or rider measurements")
    return BUSINESS_TAXONOMY[vehicle_subtype]


def _map_subtypes(frames, source_identity):
    audit = []
    for row in frames:
        for item in row.get("observations", []):
            subtype = item.get("vehicle_subtype")
            if subtype is None:
                continue
            evidence = item.get("vehicle_subtype_evidence")
            resolved = business_category(item.get("class_name"), vehicle_subtype=subtype,
                subtype_evidence=evidence)
            previous._require(evidence.get("video_sha256") == source_identity.get("video_sha256")
                and evidence.get("track_id") == item.get("track_id")
                and evidence.get("frame_index") == row.get("frame_index"),
                "Business subtype evidence belongs to another source/observation")
            previous._require(item.get("role", "vehicle") == "vehicle",
                "Business subtype evidence must target a vehicle measurement")
            previous._require(item.get("resolved_class_name") in (None, resolved),
                "Business subtype conflicts with an existing resolved category")
            item["resolved_class_name"] = resolved
            ref = {"claim_type": evidence["claim_type"], "review_id": evidence["evidence_ref"],
                "source_frame": row["frame_index"], "track_id": item["track_id"],
                "vehicle_subtype": subtype, "business_category": resolved,
                "source_video_sha256": source_identity["video_sha256"]}
            item.setdefault("review_refs", []).append(ref)
            audit.append(ref)
    return audit


def passage_display_id(category, direction, ordinal, *, category_prefixes=None):
    return previous.passage_display_id(category, direction, ordinal,
        category_prefixes=DISPLAY_PREFIXES if category_prefixes is None else category_prefixes)


def _refs(value):
    result = []
    def walk(item):
        if isinstance(item, dict):
            if type(item.get("track_id")) is int and type(item.get("frame_index")) is int:
                result.append(item)
            for nested in item.values():
                walk(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                walk(nested)
    walk(value)
    return result


def _relation_matches(refs, relation, prefix):
    return [ref for ref in refs if ref.get("track_id") == relation.get(prefix + "_track_id")
        and ref.get("physical_episode_id") == relation.get(prefix + "_physical_episode_id")]


def _supported_candidate(value, relation, prefix):
    refs = _refs(value.get("evidence", value))
    matched = _relation_matches(refs, relation, prefix)
    if not matched or not refs:
        return False
    first, last = min(ref["frame_index"] for ref in matched), max(ref["frame_index"] for ref in matched)
    support = relation.get("support_frames", [])
    # The scope may contain disjoint support observations. Only actual support
    # inside the candidate's own measured window can implicate that candidate.
    return any(first <= frame <= last for frame in support)


def _key(row):
    return row.get("physical_unit_id"), row.get("episode_id"), row.get("passage_id")


def _direction(row):
    return row.get("direction")


def _proven_opposite(first, second):
    return (first and second and all(a.get("direction") in ("A_TO_B", "B_TO_A")
        and b.get("direction") in ("A_TO_B", "B_TO_A")
        and a["direction"] != b["direction"]
        and not a.get("evidence", {}).get("direction_assumed", False)
        and not b.get("evidence", {}).get("direction_assumed", False)
        for a in first for b in second))


def _refresh(result):
    active = sorted(result["events"], key=lambda e: (e["activation_frame"], e["event_id"]))
    ordinals = Counter()
    for event in active:
        pair = event["category"], event["direction"]
        ordinals[pair] += 1
        event["display_id"] = passage_display_id(*pair, ordinals[pair])
    displays = {e["event_id"]: e["display_id"] for e in active}
    for row in result["passage_log"] + result["decisions"]:
        row["display_id"] = displays.get(row.get("event_id"))
        if "display_status" in row:
            row["display_status"] = "final_active_passage" if row["display_id"] else "no_final_active_passage_id"
    for event in result.get("cancelled_events", []):
        event["display_id"] = None
    result["events"] = active
    result["invalid_decisions"] = [deepcopy(row) for row in result["decisions"] if row["status"] == "invalid"]
    result["display_assignments"] = [{key: deepcopy(e[key]) for key in
        ("event_id", "physical_unit_id", "episode_id", "passage_id", "display_id", "category",
         "direction", "activation_frame", "decision_frame")}
        | {"source_frames": deepcopy(e["evidence"]["source_frames"])} for e in active]
    categories = Counter(e["category"] for e in active)
    measured = sum(bool(e["evidence"]["measured_crossing"]) for e in active)
    result["aggregate"] = {"total": len(active), "by_category": dict(sorted(categories.items())),
        "by_direction": dict(sorted(Counter(e["direction"] for e in active).items())),
        "by_route": dict(sorted(Counter(e["route"] for e in active).items())),
        "measured_total": measured, "inferred_total": len(active) - measured,
        "pending": sum(row["status"] == "pending" for row in result["decisions"]),
        "invalid": len(result["invalid_decisions"]),
        "invalid_reasons": dict(Counter(row["invalid_reason"] for row in result["invalid_decisions"])),
        "cancelled": len(result.get("cancelled_events", [])),
        "vehicle_total": len(active) - categories["pedestrian"], "pedestrian_total": categories["pedestrian"]}


def _apply_invalid_policy(result, relations):
    output = deepcopy(result)
    events = {e["event_id"]: e for e in output["events"]}
    audits, implicated = [], {}
    decisions = output["decisions"]
    decision_by_key = {_key(row): row for row in decisions}

    def implicate(row, relation_id=None):
        key = _key(row)
        implicated.setdefault(key, {"row": row, "relation_ids": set()})
        if relation_id:
            implicated[key]["relation_ids"].add(relation_id)

    for index, relation in enumerate(relations):
        kind = relation.get("candidate_kind")
        if relation.get("verified") is not False or kind not in AMBIGUOUS_KINDS:
            continue
        previous._require(relation.get("relation_type", relation.get("type")) == "SAME_UNIT",
            "An ambiguity hypothesis must use a scoped SAME_UNIT relation")
        support = relation.get("support_frames", [])
        previous._require(isinstance(support, list) and all(type(frame) is int and frame >= 0 for frame in support),
            "Ambiguity support requires actual source frames")
        rid = relation.get("relation_id", f"ambiguity:{index}")
        first = [e for e in events.values() if _supported_candidate(e, relation, "first")]
        second = [e for e in events.values() if _supported_candidate(e, relation, "second")]
        audit = {"relation_id": rid, "candidate_kind": kind, "support_frames": support,
                 "physical_episodes_merged": False, "status": "NO_ELIGIBLE_SCOPED_CANDIDATE"}
        audits.append(audit)
        if _proven_opposite(first, second):
            audit.update(status="OPPOSITE_DIRECTIONS_NOT_DUPLICATE",
                         event_ids=sorted(e["event_id"] for e in first + second))
            continue
        selected = first + second
        for event in selected:
            implicate(event, rid)
        for decision in decisions:
            if decision.get("status") != "pending" or decision.get("role") == "unknown_person":
                continue
            if any(_supported_candidate(decision, relation, prefix) for prefix in ("first", "second")):
                implicate(decision, rid)
        keys = sorted({str(_key(row)) for row in selected})
        if selected or any(rid in value["relation_ids"] for value in implicated.values()):
            audit.update(status="INVALID_PLUS_ZERO_SCOPED_AMBIGUITY", candidate_keys=keys)

    for decision in decisions:
        if (decision.get("status") == "pending" and decision.get("role") != "unknown_person"
                and IDENTITY_REASONS.intersection(decision.get("reasons", []))):
            implicate(decision)

    for key, value in implicated.items():
        original = value["row"]
        event = events.pop(original.get("event_id"), None)
        decision = decision_by_key.get(key)
        if decision is None:
            previous._require(event is not None, "Invalid candidate lacks event or source decision")
            decision = {"frame_index": event["decision_frame"], "track_id": event["track_id"],
                "physical_unit_id": event["physical_unit_id"], "episode_id": event.get("episode_id"),
                "passage_id": event["passage_id"], "role": event.get("role"),
                "category": event["category"], "direction": event["direction"],
                "source_ref": deepcopy(event["evidence"]["source_refs"][-1]),
                "reasons": [], "reason_evidence": []}
            decisions.append(decision)
            decision_by_key[key] = decision
        if event is not None:
            event.update(status="cancelled", accepted_count_event=False, display_id=None,
                         cancellation_reason="INVALID_AMBIGUOUS_UNIT")
            output["cancelled_events"].append(event)
            decision.update(source_event_id=event["event_id"], cancelled_candidate_event_id=event["event_id"],
                            category=event["category"], direction=event["direction"])
            output["passage_log"].append({"frame_index": output["report"]["last_frame_index"],
                "track_id": event["track_id"], "physical_unit_id": event["physical_unit_id"],
                "episode_id": event.get("episode_id"), "passage_id": event["passage_id"],
                "category": event["category"], "direction": event["direction"], "route": event["route"],
                "event_id": event["event_id"], "status": "cancelled", "count_delta": -1,
                "message": "INVALID_AMBIGUOUS_UNIT", "measured_crossing": event["evidence"]["measured_crossing"]})
        decision.update(status="invalid", invalid_reason="INVALID_AMBIGUOUS_UNIT",
            count_delta=0, accepted_count_event=False, physical_episodes_merged=False,
            invalid_scope="THIS_CANDIDATE_PASSAGE_NOT_GLOBAL_RAW_ID",
            relation_ids=sorted(value["relation_ids"]))
        decision.pop("event_id", None)
        decision["display_id"] = None
        if "INVALID_AMBIGUOUS_UNIT" not in decision.setdefault("reasons", []):
            decision["reasons"].append("INVALID_AMBIGUOUS_UNIT")
        decision.setdefault("reason_evidence", []).append({"reason": "INVALID_AMBIGUOUS_UNIT",
            "relation_ids": sorted(value["relation_ids"]), "intentional_exclusion_not_zero_traffic": True})
        output["passage_log"].append({"frame_index": decision["frame_index"],
            **{field: decision.get(field) for field in ("track_id", "physical_unit_id", "episode_id", "passage_id",
                                                       "category", "direction")},
            "event_id": None, "status": "invalid", "count_delta": 0,
            "message": "INVALID_AMBIGUOUS_UNIT", "invalid_scope": "THIS_CANDIDATE_PASSAGE_NOT_GLOBAL_RAW_ID"})
    output["events"] = list(events.values())
    for row in output.get("open_passage_diagnostics", []):
        if _key(row) in implicated:
            row.update(disposition="INVALID_AMBIGUOUS_UNIT", timeout_eligible=False)
    output["report"]["open_passage_diagnostic_counts"] = dict(sorted(Counter(
        row["disposition"] for row in output.get("open_passage_diagnostics", [])).items()))
    output["ambiguity_invalid_audit"] = audits
    _refresh(output)
    return output


def _rename_event_ids(result):
    mapping = {row["event_id"]: row["event_id"].replace("b_v5_", "b_v6_", 1)
               for row in result["events"] + result.get("cancelled_events", [])}
    def walk(value):
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str):
            return mapping.get(value, value)
        return value
    return walk(result)


def replay_frames(frames, geometry, *, source_identity, policy):
    controls = _controls(policy)
    copied = deepcopy(list(frames))
    subtype_audit = _map_subtypes(copied, source_identity)
    projected = deepcopy(policy)
    relations = deepcopy(projected.get("episode_relations", []))
    # Ambiguities are finalized below under the new invalid/+0 contract. Keep
    # the old engine's positive duplicate/component decisions unchanged.
    projected["episode_relations"] = [r for r in relations if not
        (r.get("verified") is False and r.get("candidate_kind") in AMBIGUOUS_KINDS)]
    result = previous.replay_frames(copied, geometry, source_identity=source_identity, policy=projected)
    result = _apply_invalid_policy(result, relations)
    result["business_taxonomy_audit"] = subtype_audit
    result["report"].update(version="b_v6_user_invalid_policy_v1",
        previous_engine_version="b_v5_p0_eligibility_finalization_v1",
        invalid_means_intentional_exclusion_not_no_traffic=True,
        v6_counting_policy=controls, business_subtypes_not_automatically_recognized=True,
        model_or_tracking_rerun=False, source_observations_unchanged_except_explicit_subtype_resolution=True)
    result = _rename_event_ids(result)
    previous._require(len({_key(row) for row in result["invalid_decisions"]}) == len(result["invalid_decisions"]),
        "One invalid record required per original candidate passage")
    previous._require(sum(row.get("count_delta", 0) for row in result["passage_log"])
        == result["aggregate"]["total"], "Passage log does not reconcile after invalid finalization")
    return result
