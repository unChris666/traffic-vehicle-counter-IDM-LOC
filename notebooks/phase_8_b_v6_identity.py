"""Source-scoped ambiguity candidates for the user's conservative +0 policy.

This helper never merges geometric candidates, classifies rider from co-motion
alone, or creates gap measurements. It extends the existing high-overlap
conflict control to same-category tracks; candidate identity remains UNKNOWN.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy

import phase_8_b_v5_identity as previous
from phase_5_geometry_helpers import signed_distance


VEHICLES = previous.VEHICLES
AMBIGUITY_KIND = "POSSIBLE_SCOPED_UNIT_OR_COMPONENT_AMBIGUITY"
HANDOFF_KIND = "UNVERIFIED_ORIGIN_HANDOFF"


def experimental_identity_policy(*, component_profile="median_temporal_v1"):
    controls = previous.experimental_identity_policy(component_profile=component_profile)
    controls.update(
        schema_version="phase8_b_v6_identity_policy_v1",
        ambiguity_policy="SCOPED_HIGH_IOU_ALL_VEHICLE_CLASSES_NO_AUTOMATIC_ALIAS",
        ambiguity_disposition="INVALID_PLUS_ZERO_BY_COUNTING_POLICY_NOT_IDENTITY_TRUTH",
        direction_policy="OPPOSITE_OBSERVED_DIRECTION_NOT_DUPLICATE",
        unverified_handoff_policy="EXACT_OBSERVED_ENDPOINTS_NO_GAP_CROSSING_PROOF",
        numeric_provenance_v6="REUSE_BV5_POSSIBLE_HANDOFF_IOU_AND_COMPONENT_CENTER_CONTROLS_NO_NEW_THRESHOLD",
    )
    return controls


def _controls(policy):
    value = deepcopy(policy.get("identity", policy))
    expected = experimental_identity_policy()
    previous.previous._require(isinstance(value, dict)
        and value.get("schema_version") == expected["schema_version"],
        "Explicit B v6 identity policy required")
    for key in ("ambiguity_policy", "ambiguity_disposition", "direction_policy", "unverified_handoff_policy"):
        previous.previous._require(value.get(key) == expected[key], "Unsupported B v6 identity control " + key)
    inherited = deepcopy(value)
    inherited["schema_version"] = "phase8_b_v5_identity_policy_v1"
    previous._controls(inherited)
    return value, inherited


def _point(item):
    box = item["raw_bbox"]
    return ((box[0] + box[2]) / 2, box[3])


def _identity_review_proof(item):
    """Require typed identity provenance, never a role/category review alone.

    The retained adapter predates typed refs. Its SAME_VEHICLE assignment is
    identifiable by the exact matching verified association/review ID. A split
    needs an explicit review type; a custom unit name alone proves nothing.
    """
    if str(item["unit_id"]).startswith(("retained-clique:", "track:", "person-track:")):
        return []
    refs = list(item.get("review_refs", []))
    if isinstance(item.get("review_ref"), dict):
        refs.append(item["review_ref"])
    evidence = []
    for ref in refs:
        kind = ref.get("review_type", ref.get("type"))
        exact = (ref.get("source_frame") == item["frame_index"]
            and ref.get("track_id") == item["track_id"]
            and isinstance(ref.get("review_id"), str) and bool(ref["review_id"])
            and isinstance(ref.get("reviews_sha256"), str) and bool(ref["reviews_sha256"]))
        typed = kind in ("SAME_VEHICLE", "SPLIT_IDENTITY")
        legacy_same = (kind is None and item.get("association_verified") is True
            and item.get("association_id") == ref.get("review_id"))
        if exact and (typed or legacy_same):
            evidence.append({"review_id": ref["review_id"], "source_frame": ref["source_frame"],
                "track_id": item["track_id"], "reviews_sha256": ref["reviews_sha256"],
                "identity_review_type": kind if typed else "LEGACY_VERIFIED_SAME_VEHICLE_ASSIGNMENT",
                "scope_extent_is_engineering_assumption": ref.get("scope_extent_is_engineering_assumption")})
    return evidence


def _negative_matches(relation, first, second):
    if (relation.get("verified") is not True
            or relation.get("relation_type", relation.get("type")) != "DIFFERENT_UNIT"
            or not {first["frame_index"], second["frame_index"]}.issubset(set(relation.get("support_frames", [])))):
        return False

    def matches(prefix, item):
        if relation.get(prefix + "_track_id") != item["track_id"]:
            return False
        context = relation.get(prefix + "_physical_episode_id")
        return ((context is not None and context == item["physical_episode_id"])
            or (relation.get(prefix + "_unit_id") == item["unit_id"]
                and relation.get(prefix + "_episode_id") == item["episode_id"]))

    return ((matches("first", first) and matches("second", second))
        or (matches("first", second) and matches("second", first)))


def _proven_distinct(first, second, negative_relations):
    for relation in negative_relations:
        if _negative_matches(relation, first, second):
            return {"basis": "EXACT_VERIFIED_DIFFERENT_UNIT_RELATION",
                "relation_id": relation.get("relation_id"),
                "support_frames": [first["frame_index"], second["frame_index"]]}
    a, b = _identity_review_proof(first), _identity_review_proof(second)
    if first["unit_id"] != second["unit_id"] and a and b:
        return {"basis": "DIFFERENT_SOURCE_BOUND_REVIEWED_PHYSICAL_UNITS",
            "first_identity_review_proof": a, "second_identity_review_proof": b}
    return None


def _distinct_audit(first, second, proof, kind):
    return {"first_track_id": first["track_id"], "second_track_id": second["track_id"],
        "first_physical_episode_id": first["physical_episode_id"],
        "second_physical_episode_id": second["physical_episode_id"],
        "support_frames": sorted({first["frame_index"], second["frame_index"]}),
        "vetoed_candidate_kind": kind, "disposition": "PROVEN_DISTINCT_AUDIT_ONLY",
        "proof": proof, "source_measurements_changed": False}


def _veto_inherited_cross_category(result, negative_relations, distinct_audit):
    """Trim only disproved exact support, retaining unrelated identity holds."""
    present = {(row["frame_index"], item["track_id"]): item
        for row in result["frames"] for item in row["observations"]}
    protected, active, kept = set(), set(), []
    for relation in result["unit_relations"]:
        if relation.get("candidate_kind") != "POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT":
            kept.append(relation)
            continue
        support = []
        for frame in relation["support_frames"]:
            first, second = (present[(frame, relation[key + "_track_id"])] for key in ("first", "second"))
            proof = _proven_distinct(first, second, negative_relations)
            if proof:
                distinct_audit.append(_distinct_audit(first, second, proof, relation["candidate_kind"]))
                protected.update((frame, item["track_id"]) for item in (first, second))
            else:
                support.append(frame)
                active.update((frame, item["track_id"]) for item in (first, second))
        if support:
            relation["support_frames"] = support
            relation["start_frame"], relation["end_frame"] = support[0], support[-1]
            kept.append(relation)
    result["unit_relations"] = kept
    reason = "CROSS_CATEGORY_UNIT_OR_COMPONENT_UNRESOLVED"
    for key in protected - active:
        item = present[key]
        item["identity_timeout_hold"] = [value for value in item["identity_timeout_hold"] if value != reason]


def _opposite(run, geometry, minimum):
    """Only observed monotone line-normal motion can exclude a candidate.

    This is an audit constraint, not independent proof of either count. Actual
    event directions are checked again by the counting finalizer.
    """
    if len(run) < minimum:
        return False
    paths = [[signed_distance(_point(pair[index]), geometry.p1, geometry.p2)
              for pair in run] for index in (0, 1)]
    deltas = [[b - a for a, b in zip(path, path[1:])] for path in paths]
    signs = [1 if all(step > 0 for step in delta) else -1 if all(step < 0 for step in delta)
             else 0 for delta in deltas]
    return signs[0] * signs[1] == -1


def _same_category_ambiguity(frames, geometry, controls, negative_relations, distinct_audit):
    """High overlap can invalidate an ambiguity, never establish same-unit.

    The numerical limit is the frozen possible-handoff IoU control. Merely
    nearby/disjoint boxes, weak overlap and parallel movement are not enough.
    """
    pairs = defaultdict(list)
    base = previous.previous
    for row in frames:
        vehicles = [item for item in row["observations"] if item["role"] == "vehicle"]
        for index, first in enumerate(vehicles):
            for second in vehicles[index + 1:]:
                if first["class_name"] != second["class_name"]:
                    continue  # Cross-category candidates are preserved from B v5.
                a, b = sorted((first, second), key=lambda item: item["track_id"])
                if ((a["unit_id"], a["episode_id"]) == (b["unit_id"], b["episode_id"])
                        and a.get("association_verified") is True
                        and b.get("association_verified") is True
                        and a.get("association_id") is not None
                        and a.get("association_id") == b.get("association_id")):
                    continue
                scale = (base._diag(a["raw_bbox"]) + base._diag(b["raw_bbox"])) / 2
                center_distance = base._distance(base._center(a["raw_bbox"]),
                    base._center(b["raw_bbox"])) / scale
                if base._iou(a["raw_bbox"], b["raw_bbox"]) <= 0 or center_distance > controls["component_center_limit"]:
                    continue
                proof = _proven_distinct(a, b, negative_relations)
                if proof:
                    if base._iou(a["raw_bbox"], b["raw_bbox"]) >= controls["possible_handoff_min_iou"]:
                        distinct_audit.append(_distinct_audit(a, b, proof, AMBIGUITY_KIND))
                    continue
                key = (a["track_id"], b["track_id"], a["physical_episode_id"], b["physical_episode_id"])
                pairs[key].append((a, b))
    relations, audits = [], []
    for key, observations in sorted(pairs.items()):
        runs, current = [], []
        for pair in observations:
            if current and pair[0]["frame_index"] != current[-1][0]["frame_index"] + 1:
                runs.append(current)
                current = []
            current.append(pair)
        if current:
            runs.append(current)
        for run in runs:
            opposite = _opposite(run, geometry, controls["min_component_run"])
            selected = [pair for pair in run if base._iou(pair[0]["raw_bbox"], pair[1]["raw_bbox"])
                        >= controls["possible_handoff_min_iou"]]
            support = [pair[0]["frame_index"] for pair in selected]
            relation_id = base._hash("b6-unit-ambiguity:", [*key, support, opposite])
            audits.append({"relation_id": relation_id, "first_track_id": key[0],
                "second_track_id": key[1], "first_physical_episode_id": key[2],
                "second_physical_episode_id": key[3],
                "examined_source_frames": [pair[0]["frame_index"] for pair in run],
                "support_frames": support, "opposite_observed_direction": opposite,
                "ambiguity_supported": bool(selected) and not opposite,
                "physical_identity_merged": False,
                "numeric_control": "FROZEN_POSSIBLE_HANDOFF_MIN_IOU",
                "claim_type": "SCOPED_AMBIGUITY_NOT_POSITIVE_IDENTITY_OR_TRAFFIC_GROUND_TRUTH"})
            if not selected or opposite:
                continue
            a, b = selected[0]
            relation = {"type": "SAME_UNIT", "relation_type": "SAME_UNIT",
                "relation_id": relation_id, "candidate_kind": AMBIGUITY_KIND,
                "verified": False, "first_track_id": a["track_id"], "second_track_id": b["track_id"],
                "first_physical_episode_id": a["physical_episode_id"],
                "second_physical_episode_id": b["physical_episode_id"],
                "first_unit_id": a["unit_id"], "second_unit_id": b["unit_id"],
                "first_episode_id": a["episode_id"], "second_episode_id": b["episode_id"],
                "support_frames": support, "start_frame": support[0], "end_frame": support[-1],
                "verification_basis": "EXACT_OBSERVED_HIGH_OVERLAP_SAME_CATEGORY_CONFLICT_NOT_ALIAS",
                "claim_type": "USER_AUTHORIZED_INVALID_AMBIGUITY_NOT_SAME_PHYSICAL_UNIT_ASSERTION",
                "earlier_frames_reassigned": False}
            relations.append(relation)
            for first, second in selected:
                for item in (first, second):
                    if "SCOPED_UNIT_AMBIGUITY" not in item["identity_timeout_hold"]:
                        item["identity_timeout_hold"].append("SCOPED_UNIT_AMBIGUITY")
                    item.setdefault("v6_ambiguity_relation_ids", []).append(relation_id)
    return relations, audits


def _handoff_relations(result, negative_relations, distinct_audit):
    """Address inherited possible handoffs without inventing gap observations."""
    present = {(row["frame_index"], item["track_id"]): item
               for row in result["frames"] for item in row["observations"]}
    relations, audits, protected_scopes, unresolved_scopes = [], [], set(), set()
    for handoff in result["handoff_audit"]:
        first_key = (handoff["last_first_frame"], handoff["first_track_id"])
        second_key = (handoff["first_second_frame"], handoff["second_track_id"])
        first, second = present[first_key], present[second_key]
        if first["role"] != "vehicle" or second["role"] != "vehicle":
            continue
        scopes = {(item["track_id"], item["physical_episode_id"]) for item in (first, second)}
        proof = _proven_distinct(first, second, negative_relations)
        if proof:
            protected_scopes.update(scopes)
            distinct_audit.append(_distinct_audit(first, second, proof, HANDOFF_KIND))
            handoff["v6_disposition"] = "PROVEN_DISTINCT_NOT_A_HANDOFF"
            handoff["v6_distinct_proof"] = proof
            continue
        unresolved_scopes.update(scopes)
        support = [first_key[0], second_key[0]]
        rid = previous.previous._hash("b6-unverified-handoff:",
            [first_key, second_key, first["physical_episode_id"], second["physical_episode_id"]])
        relation = {"type": "SAME_UNIT", "relation_type": "SAME_UNIT", "relation_id": rid,
            "candidate_kind": HANDOFF_KIND, "verified": False,
            "first_track_id": first["track_id"], "second_track_id": second["track_id"],
            "first_physical_episode_id": first["physical_episode_id"],
            "second_physical_episode_id": second["physical_episode_id"],
            "first_unit_id": first["unit_id"], "second_unit_id": second["unit_id"],
            "first_episode_id": first["episode_id"], "second_episode_id": second["episode_id"],
            "first_endpoint_frame": support[0], "second_endpoint_frame": support[1],
            "support_frames": support, "start_frame": support[0], "end_frame": support[-1],
            "gap_source_frames": handoff["gap_source_frames"],
            "verification_basis": "INHERITED_POSSIBLE_HANDOFF_ENDPOINT_CONTROL_NOT_IDENTITY_PROOF",
            "claim_type": "UNVERIFIED_EPISODE_HANDOFF_NOT_OBSERVED_CROSSING",
            "gap_observations_created": False, "earlier_frames_reassigned": False}
        relations.append(relation)
        audits.append({"relation_id": rid, "support_frames": support,
            "first_track_id": first["track_id"], "second_track_id": second["track_id"],
            "gap_observations_created": False, "physical_identity_merged": False})
        for item in (first, second):
            if "UNVERIFIED_ORIGIN_HANDOFF" not in item["identity_timeout_hold"]:
                item["identity_timeout_hold"].append("UNVERIFIED_ORIGIN_HANDOFF")
            item.setdefault("v6_ambiguity_relation_ids", []).append(rid)
    # The inherited helper applied this generic hold before the distinct proof
    # was inspected. Remove it only from the exact proven endpoint contexts,
    # and only if no other unresolved handoff implicates that same context.
    reason = "POSSIBLE_UNVERIFIED_RAW_ID_HANDOFF_TIMEOUT_HELD"
    for row in result["frames"]:
        for item in row["observations"]:
            key = (item["track_id"], item["physical_episode_id"])
            if key in protected_scopes - unresolved_scopes:
                item["identity_timeout_hold"] = [value for value in item["identity_timeout_hold"] if value != reason]
    return relations, audits


def prepare_identity_frames(frames, geometry, policy, relationships=None):
    controls, inherited = _controls(policy)
    result = previous.prepare_identity_frames(frames, geometry,
        {"identity": inherited}, relationships=relationships)
    # Only source-adapter verified, explicitly scoped negative relations are
    # constraints. Bbox-derived DIFFERENT_UNIT hypotheses remain unverified.
    negative_relations = [relation for relation in
        list(result["unit_relations"]) + list((relationships or {}).get("unit_relations", []))
        if relation.get("verified") is True
        and relation.get("relation_type", relation.get("type")) == "DIFFERENT_UNIT"]
    distinct_audit = []
    _veto_inherited_cross_category(result, negative_relations, distinct_audit)
    new_relations, ambiguity_audit = _same_category_ambiguity(result["frames"], geometry,
        controls, negative_relations, distinct_audit)
    handoff_relations, handoff_audit = _handoff_relations(result, negative_relations, distinct_audit)
    result["unit_relations"] += new_relations + handoff_relations
    result["ambiguity_audit"] = ambiguity_audit
    result["unverified_handoff_relation_audit"] = handoff_audit
    result["known_distinct_constraint_audit"] = distinct_audit
    result["assignments"] = previous._assignments(result["frames"])
    raw = {(row["frame_index"], item["track_id"]): item for row in result["frames"]
           for item in row["observations"]}
    for assignment in result["assignments"]:
        refs = raw[(assignment["frame_index"], assignment["track_id"])].get("v6_ambiguity_relation_ids", [])
        if refs:
            assignment["v6_ambiguity_relation_ids"] = sorted(set(refs))
    result["policy"] = controls
    result["provenance"].update(v6_same_category_ambiguity_supported=True,
        geometric_ambiguity_is_not_verified_unit_identity=True,
        distinct_constraints_require_scoped_identity_proof_not_role_or_category_review=True,
        opposite_event_direction_must_be_checked_by_counting=True,
        unverified_handoff_does_not_create_gap_crossing=True)
    return result
