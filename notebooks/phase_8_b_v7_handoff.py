"""Bounded motion conflicts between provisional passages; never identity proof.

Five observed frames on each side support bidirectional linear extrapolation.
Predictions only propose uncertainty; raw boxes/BC and crossing evidence stay
unchanged. The 60-frame source horizon is inherited, not increased.
"""
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math

import phase_8_b_v6_identity as identity
from phase_8_b_v5_counting import _side_signs


KIND = "UNVERIFIED_ORIGIN_HANDOFF"


def experimental_handoff_policy():
    return {"schema_version": "phase8_b_v7_handoff_policy_v1",
        "window_observations": 5,
        "window_requirement": "CONSECUTIVE_OBSERVED_VEHICLE_MEASUREMENTS_BOTH_SIDES",
        "fit": "OLS_CENTER_CONSTANT_VELOCITY_BIDIRECTIONAL",
        "spatial_gate": "BIDIRECTIONAL_TRANSLATED_ENDPOINT_BOX_POSITIVE_AREA_OVERLAP",
        "gap_limit": "INHERIT_EXISTING_TIMEOUT_SOURCE_FRAMES",
        "direction_gate": "OBSERVED_LINE_NORMAL_MOTION_AND_EVENT_DIRECTIONS_AGREE",
        "scope": "ACTIVE_CANDIDATE_PAIR_AT_LEAST_ONE_ESTIMATE_NO_OVERLAPPING_CONTEXT_LIFETIMES",
        "identity_effect": "UNVERIFIED_CONFLICT_NO_ALIAS_NO_MEASURED_CROSSING_UPGRADE",
        "disposition": "EXISTING_INVALID_PLUS_ZERO_FOR_EXPLICIT_PAIR_ONLY",
        "window_rationale": "FIVE_IS_DECLARED_RESEARCH_SAMPLE_SUPPORT_NOT_TUNED_ON_TARGET_OR_PRODUCTION_DEFAULT",
        "spatial_rationale": "BOTH_OBSERVED_BOX_EXTENTS_BOUND_SPATIAL_CONFLICT_NOT_VALIDATED_IDENTITY_THRESHOLD"}


def _require(value, message):
    if not value:
        raise ValueError(message)


def _controls(policy):
    controls = policy.get("v7_handoff")
    _require(controls == experimental_handoff_policy(), "Explicit supported B v7 handoff policy required")
    _require(policy.get("timeout_frames") == 60, "Existing 60 source-frame clock must stay fixed")
    return deepcopy(controls)


def _center(item):
    x1, y1, x2, y2 = item["raw_bbox"]
    return ((x1+x2)/2, (y1+y2)/2)


def _bc(item):
    x1, _, x2, y2 = item["raw_bbox"]
    return ((x1+x2)/2, y2)


def _fit(items, point=_center):
    times = [i["frame_index"] for i in items]
    t0 = sum(times) / len(times)
    points = [point(i) for i in items]
    origin = [sum(p[k] for p in points) / len(points) for k in (0, 1)]
    denominator = sum((t-t0)**2 for t in times)
    _require(denominator > 0, "Motion fit requires distinct observation times")
    velocity = [sum((t-t0)*(p[k]-origin[k]) for t, p in zip(times, points))/denominator for k in (0, 1)]
    return {"reference_frame": t0, "center": origin, "velocity_px_per_source_frame": velocity}


def _predict(fit, frame):
    return [fit["center"][k] + (frame-fit["reference_frame"])*fit["velocity_px_per_source_frame"][k] for k in (0, 1)]


def _translated_box(item, predicted_center):
    center = _center(item)
    dx, dy = [predicted_center[k] - center[k] for k in (0, 1)]
    x1, y1, x2, y2 = item["raw_bbox"]
    return [x1 + dx, y1 + dy, x2 + dx, y2 + dy]


def _positive_overlap(first, second):
    return (min(first[2], second[2]) > max(first[0], second[0])
        and min(first[3], second[3]) > max(first[1], second[1]))


def _context(item):
    return item["track_id"], item.get("physical_episode_id")


def _window(event):
    refs = event.get("evidence", {}).get("source_refs", [])
    times = [r["frame_index"] for r in refs if type(r.get("frame_index")) is int]
    return (min(times), max(times)) if times else None


def _event_context(event):
    refs = event.get("evidence", {}).get("source_refs", [])
    contexts = {_context(ref) for ref in refs if ref.get("role") == "vehicle"}
    if len(contexts) != 1 or next(iter(contexts))[1] is None:
        return None
    return next(iter(contexts))


def _own_observations(event, context_items):
    window = _window(event)
    if window is None:
        return []
    return [item for item in context_items
        if window[0] <= item["frame_index"] <= window[1]
        and item.get("unit_id") == event["physical_unit_id"]
        and item.get("episode_id") == event.get("episode_id")
        and (item.get("resolved_class_name") or item["class_name"]) == event["category"]]


def _consecutive(items, count):
    return (len(items) == count and all(b["frame_index"] == a["frame_index"]+1
        for a, b in zip(items, items[1:])))


def _distinct_constraint(first, second, relations, contexts):
    """A scoped verified identity constraint may survive within its context.

    It cannot migrate to another physical episode or be inferred from role or
    category review. Retained relation inputs were verified by the source adapter.
    """
    proof = identity._proven_distinct(first, second, relations)
    if proof:
        return proof
    for rel in relations:
        if rel.get("verified") is not True or rel.get("relation_type", rel.get("type")) != "DIFFERENT_UNIT":
            continue
        support = rel.get("support_frames", [])
        if not support:
            continue
        for a, b in ((first, second), (second, first)):
            def matches(prefix, item):
                return (rel.get(prefix+"_track_id") == item["track_id"]
                    and rel.get(prefix+"_physical_episode_id") == item["physical_episode_id"])
            if matches("first", a) and matches("second", b):
                # The original proof must intersect both exact contexts; no
                # raw-ID-wide propagation from a different use of the ID.
                frame_sets = [{item["frame_index"] for item in contexts[_context(x)]} for x in (a, b)]
                if all(set(support) & values for values in frame_sets):
                    return {"basis": "VERIFIED_DIFFERENT_UNIT_WITHIN_SAME_PHYSICAL_CONTEXTS",
                            "relation_id": rel.get("relation_id"), "support_frames": support}
    return None


def propose_handoff_conflicts(provisional_result, frames, geometry, policy):
    controls = _controls(policy)
    count = controls["window_observations"]
    contexts = defaultdict(list)
    for row in frames:
        for item in row.get("observations", []):
            if item.get("role") != "vehicle":
                continue
            _require(item.get("observed") is True and item.get("emitted") is True,
                "Handoff fitting requires observed emitted source measurements")
            _require(item.get("frame_index", row["frame_index"]) == row["frame_index"], "Frame/source mismatch")
            _require(item.get("physical_episode_id") is not None, "Physical context must be explicit")
            _require(len(item["raw_bbox"]) == 4 and all(math.isfinite(x) for x in item["raw_bbox"]), "Invalid raw bbox")
            contexts[_context(item)].append(item)
    for items in contexts.values():
        items.sort(key=lambda i:i["frame_index"])
        _require(len({i["frame_index"] for i in items}) == len(items), "Repeated source context/frame")
    events = sorted(provisional_result.get("events", []), key=lambda e:(min(e["evidence"]["source_frames"]), e["event_id"]))
    signs = _side_signs(geometry)
    dx, dy = geometry.p2[0]-geometry.p1[0], geometry.p2[1]-geometry.p1[1]
    length = math.hypot(dx, dy)
    normal = (-dy/length, dx/length)
    relations, audits = [], []
    negative = policy.get("episode_relations", [])
    for index, old in enumerate(events):
        for new in events[index+1:]:
            if (old.get("role") != "vehicle" or new.get("role") != "vehicle"
                    or old["track_id"] == new["track_id"]
                    or old["category"] != new["category"]
                    or old["direction"] != new["direction"]
                    or old["direction"] not in ("A_TO_B", "B_TO_A")
                    or all(e["evidence"].get("measured_crossing") for e in (old,new))):
                continue
            ca, cb = _event_context(old), _event_context(new)
            if ca not in contexts or cb not in contexts or ca == cb:
                continue
            a, b = contexts[ca], contexts[cb]
            if a[0]["frame_index"] > b[0]["frame_index"]:
                continue
            audit = {"first_event_id": old["event_id"], "second_event_id": new["event_id"],
                "first_track_id": old["track_id"], "second_track_id": new["track_id"],
                "first_physical_episode_id": ca[1], "second_physical_episode_id": cb[1],
                "status": "REJECTED", "reason": None}
            gap = b[0]["frame_index"]-a[-1]["frame_index"]
            if gap <= 0:
                continue  # Co-present/overlapping lifetimes: not this handoff experiment.
            if gap > policy["timeout_frames"]:
                continue
            audits.append(audit)
            audit["gap_source_frames"] = gap
            first, second = _own_observations(old, a), _own_observations(new, b)
            if not first or not second or first[-1] is not a[-1] or second[0] is not b[0]:
                audit["reason"] = "EVENT_WINDOW_DOES_NOT_CONTAIN_CONTEXT_ENDPOINTS"
                continue
            tail, head = first[-count:], second[:count]
            if not _consecutive(tail,count) or not _consecutive(head,count):
                audit["reason"] = "INSUFFICIENT_CONSECUTIVE_OBSERVATIONS"
                continue
            proof = _distinct_constraint(tail[-1],head[0],negative,contexts)
            if proof:
                audit.update(reason="VERIFIED_DISTINCT_VETO", distinct_proof=proof)
                continue
            fits = [_fit(tail), _fit(head)]
            velocities = [fit["velocity_px_per_source_frame"] for fit in fits]
            bc_velocities = [_fit(items,_bc)["velocity_px_per_source_frame"] for items in (tail,head)]
            origin_sign = signs["A" if old["direction"] == "A_TO_B" else "B"]
            progress = [-origin_sign*sum(v[k]*normal[k] for k in (0,1)) for v in bc_velocities]
            dot = sum(velocities[0][k]*velocities[1][k] for k in (0,1))
            audit.update(first_fit=fits[0],second_fit=fits[1],observed_normal_progress=progress,
                         heading_dot=dot, first_support_frames=[i["frame_index"] for i in tail],
                         second_support_frames=[i["frame_index"] for i in head])
            if dot <= 1e-12 or any(value <= 1e-12 for value in progress):
                audit["reason"] = "OBSERVED_MOTION_DIRECTION_NOT_SUPPORTED"
                continue
            forward, backward = _predict(fits[0],head[0]["frame_index"]), _predict(fits[1],tail[-1]["frame_index"])
            forward_box = _translated_box(tail[-1], forward)
            backward_box = _translated_box(head[0], backward)
            checks = [_positive_overlap(forward_box, head[0]["raw_bbox"]),
                      _positive_overlap(backward_box, tail[-1]["raw_bbox"])]
            audit.update(forward_prediction=forward,backward_prediction=backward,
                forward_translated_box=forward_box, backward_translated_box=backward_box,
                forward_positive_area_overlap=checks[0], backward_positive_area_overlap=checks[1])
            if not all(checks):
                audit["reason"] = "BIDIRECTIONAL_OBSERVED_BOX_GATE_FAILED"
                continue
            material = [old["event_id"],new["event_id"],audit["first_support_frames"],audit["second_support_frames"],controls]
            rid = "b7-motion-conflict:"+hashlib.sha256(json.dumps(material,sort_keys=True).encode()).hexdigest()[:24]
            relation = {"type":"SAME_UNIT", "relation_type":"SAME_UNIT", "candidate_kind":KIND,
                "verified":False,"relation_id":rid,"event_ids":[old["event_id"],new["event_id"]],
                "first_event_id":old["event_id"],"second_event_id":new["event_id"],
                "first_track_id":old["track_id"],"second_track_id":new["track_id"],
                "first_physical_episode_id":ca[1],"second_physical_episode_id":cb[1],
                "first_unit_id":old["physical_unit_id"],"second_unit_id":new["physical_unit_id"],
                "first_episode_id":old.get("episode_id"),"second_episode_id":new.get("episode_id"),
                "first_support_frames":audit["first_support_frames"],"second_support_frames":audit["second_support_frames"],
                "support_frames":audit["first_support_frames"]+audit["second_support_frames"],
                "gap_source_frames":gap,"motion_provenance":"BIDIRECTIONAL_OLS_OBSERVED_WINDOWS",
                "first_source_refs":deepcopy(tail),"second_source_refs":deepcopy(head),
                "identity_merged":False,"predicted_crossing_is_measured":False,
                "claim_type":"UNVERIFIED_MOTION_CONFLICT_NOT_PHYSICAL_IDENTITY"}
            relations.append(relation)
            audit.update(status="PROPOSED_UNVERIFIED_CONFLICT",reason="BIDIRECTIONAL_MOTION_SUPPORTED",
                relation_id=rid)
    return {"relations":relations,"audit":audits,"controls":controls}
