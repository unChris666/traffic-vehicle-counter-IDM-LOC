"""B v3 notebook counting experiment on retained measured tracks only.

This does not run detection/tracking/ReID and does not modify the frozen B v1/B v2
resolvers. Three explicitly different evidence routes share one passage ledger.
An estimated timeout is an operational count, never evidence of an ID change.
The source adapter must validate retained detection links before calling this
module; this module additionally rejects non-observed/non-emitted inputs.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math
from numbers import Real

from phase_5_geometry_helpers import Geometry, segment_intersection, signed_distance


SUPPORTED_CATEGORIES = frozenset(("motorcycle", "car", "truck", "pedestrian"))
VEHICLE_CLASSES = frozenset(("motorcycle", "car", "truck", "bus"))
ROLES = frozenset(("vehicle", "pedestrian", "rider", "unknown_person"))
DISPLAY_PREFIXES = {"pedestrian": "P", "motorcycle": "M", "car": "C", "truck": "T"}


def passage_display_id(category, direction, ordinal, *, category_prefixes=None):
    """Deterministic one-based ordinal in a per-video category/direction scope.

    Four numeric digits: even first digit A_TO_B, odd first digit B_TO_A;
    zero is never a leading digit. Exhaustion is explicit, never a wrap.
    """
    prefixes = DISPLAY_PREFIXES if category_prefixes is None else category_prefixes
    _require(category in prefixes, "Display category has no agreed prefix")
    _require(direction in ("A_TO_B", "B_TO_A"), "Display direction must be explicit")
    _require(isinstance(ordinal, int) and not isinstance(ordinal, bool) and ordinal > 0,
             "Display ordinal must be a positive integer")
    first_digits = (2, 4, 6, 8) if direction == "A_TO_B" else (1, 3, 5, 7, 9)
    _require(ordinal <= len(first_digits) * 1000,
             "Four-digit passage display ID space exhausted; no IDs may be reused")
    offset = ordinal - 1
    return f"{prefixes[category]}{first_digits[offset // 1000]}{offset % 1000:03d}"


def _effective_category(observation):
    return observation["effective_class_name"]


def _episode_key(observation):
    return observation["unit_id"], observation.get("episode_id")


def _verified_link(first, second):
    return (first.get("association_verified") is True
            and second.get("association_verified") is True
            and first.get("association_id") is not None
            and first.get("association_id") == second.get("association_id"))


def _unresolved_handoffs(state):
    return any(not change["association_verified"] for change in state["raw_track_changes"])


ROUTE_LABELS = {
    "LINE_MARGIN": "CROSSING_LINE",
    "OCCLUSION_DIFF_POLYGON": "OCCLUSION_DIFF_POLYGON",
    "ESTIMATED_TIMEOUT": "CHANGE_ID",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, name):
    _require(isinstance(value, int) and not isinstance(value, bool) and value >= 0,
             f"{name} must be a nonnegative source-frame integer")
    return value


def _number(value, name):
    _require(isinstance(value, Real) and not isinstance(value, bool)
             and math.isfinite(float(value)), f"{name} must be finite numeric")
    return float(value)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(value):
    _require(isinstance(value, (str, int)) and not isinstance(value, bool)
             and str(value) != "", "Track/unit identities must be nonempty strings or integers")
    return str(value)


def _bbox(value):
    _require(isinstance(value, (list, tuple)) and len(value) == 4,
             "raw_bbox requires four measured coordinates")
    result = [_number(v, "raw_bbox") for v in value]
    _require(result[0] < result[2] and result[1] < result[3], "raw_bbox has no positive area")
    return result


def finite_band(point, geometry, half_width):
    """Flat-capped finite rectangular band; no extension beyond P1/P2."""
    p1, p2 = geometry.p1, geometry.p2
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    projection = ((point[0] - p1[0]) * dx + (point[1] - p1[1]) * dy) / (dx * dx + dy * dy)
    distance = signed_distance(point, p1, p2)
    return {"inside": 0 <= projection <= 1 and abs(distance) <= half_width,
            "projection": projection, "signed_distance_px": distance}


def _side_signs(geometry):
    # Polygon mean signed distance establishes orientation only, never an ROI
    # membership test. Membership itself always uses Geometry.side().
    means = {side: sum(signed_distance(p, geometry.p1, geometry.p2) for p in polygon) / len(polygon)
             for side, polygon in (("A", geometry.side_a), ("B", geometry.side_b))}
    _require(means["A"] * means["B"] < 0,
             "A/B polygons must have opposite mean line sides for direction mapping")
    return {side: 1 if distance > 0 else -1 for side, distance in means.items()}


def _observation(raw, frame, geometry, margin):
    _require(isinstance(raw, dict), "Each observation must be a dictionary")
    _require(raw.get("observed") is True and raw.get("emitted") is True,
             "Only observed, emitted, raw detector-linked tracks can be replayed")
    track = raw.get("track_id")
    _identity(track)
    index = _integer(raw.get("original_detection_index"), "original_detection_index")
    if "frame_index" in raw:
        _require(raw["frame_index"] == frame, "Observation frame differs from source frame")
    box = _bbox(raw.get("raw_bbox"))
    category = raw.get("class_name")
    _require(isinstance(category, str) and category, "Raw class_name must be explicit")
    _require(isinstance(raw.get("identity_conflict", False), bool), "identity_conflict must be boolean")
    unit = _identity(raw.get("unit_id", f"track:{track}"))
    role = raw.get("role", "vehicle" if category in VEHICLE_CLASSES else "unknown_person" if category == "person" else None)
    _require(role in ROLES or role is None, "Unknown physical observation role")
    association_verified = raw.get("association_verified", False)
    _require(isinstance(association_verified, bool), "association_verified must be boolean")
    association_id = raw.get("association_id")
    if association_id is not None:
        association_id = _identity(association_id)
    _require(not association_verified or association_id is not None,
             "A verified association requires association_id")
    episode_id = raw.get("episode_id")
    if episode_id is not None:
        episode_id = _identity(episode_id)
    resolved = raw.get("resolved_class_name")
    _require(resolved is None or isinstance(resolved, str) and bool(resolved),
             "resolved_class_name must be explicit nonempty category")
    if role == "pedestrian":
        _require(category == "person", "Pedestrian BC must come from a raw person measurement")
        _require(resolved in (None, "pedestrian"), "Pedestrian role/category conflict")
        effective = "pedestrian"
    elif role == "vehicle":
        _require(category in VEHICLE_CLASSES, "Vehicle BC requires a raw vehicle-class measurement")
        _require(resolved != "pedestrian", "Pedestrian requires a positive pedestrian role")
        effective = resolved or category
    else:
        effective = resolved or category
    point = ((box[0] + box[2]) / 2, box[3])
    band = finite_band(point, geometry, margin)
    result = {"frame_index": frame, "track_id": track, "unit_id": unit,
              "original_detection_index": index, "raw_bbox": box, "point": list(point),
              "class_name": category, "effective_class_name": effective,
              "resolved_class_name": resolved, "role": role, "episode_id": episode_id,
              "association_verified": association_verified, "association_id": association_id,
              "observed": True, "emitted": True,
              "identity_conflict": raw.get("identity_conflict", False),
              "polygon": geometry.side(point), "band": band["inside"],
              "signed_distance_px": band["signed_distance_px"],
              "line_projection": band["projection"]}
    for key in ("class_id", "confidence", "measurement_provenance", "source_ref", "review_ref", "review_refs"):
        if key in raw:
            result[key] = deepcopy(raw[key])
    return result


def _ref(observation):
    return {key: deepcopy(observation[key]) for key in
            ("frame_index", "track_id", "original_detection_index", "raw_bbox", "point",
             "class_name", "effective_class_name", "resolved_class_name", "role", "episode_id",
             "association_verified", "association_id", "observed", "emitted")
            if key in observation} | {key: deepcopy(observation[key]) for key in
                                      ("review_ref", "review_refs", "class_id", "confidence",
                                       "measurement_provenance", "source_ref") if key in observation}


def _direction(origin):
    return "A_TO_B" if origin == "A" else "B_TO_A"


def _new_passage(observation, origin, ordinal):
    return {"origin": origin, "ordinal": ordinal, "origin_ref": _ref(observation),
            "last_origin_ref": _ref(observation) if observation["polygon"] == origin else None,
            "origin_is_roi": observation["polygon"] == origin,
            "origin_track": observation["track_id"], "origin_category": _effective_category(observation),
            "band_refs": [_ref(observation)] if observation["band"] else [],
            "band_votes": Counter({_effective_category(observation): 1}) if observation["band"] else Counter(),
            "crossing_pairs": [], "zero_contact": None,
            "gaps": [], "raw_track_changes": [], "approaching": False,
            "identity_conflicts": [_ref(observation)] if observation["identity_conflict"] else [],
            "destination_observed_ref": None,
            "turned_away": False, "event": None, "pending_reasons": set(),
            "pending_decision": None,
            "last": observation}


def _category(state, destination=None, *, timeout=False, supported_categories=SUPPORTED_CATEGORIES):
    if state["last"]["role"] == "unknown_person":
        return None, {"policy": "positive_role_required", "raw_class_name": state["last"]["class_name"]}, "PERSON_ROLE_UNRESOLVED"
    if state["band_votes"]:
        votes = state["band_votes"]
        maximum = max(votes.values())
        winners = sorted(category for category, count in votes.items() if count == maximum)
        basis = {"policy": "band_majority_ties_pending", "votes": dict(sorted(votes.items())),
                 "source": "observed_object_BC_inside_finite_band",
                 "reviewed_category_attribution": any(ref.get("resolved_class_name") is not None for ref in state["band_refs"])}
        if len(winners) != 1:
            return None, basis, "CATEGORY_TIE_IN_BAND"
        category = winners[0]
    else:
        origin = state["last_origin_ref"] or state["origin_ref"]
        latest = destination or state["last"]
        basis = {"policy": "matching_observed_endpoints", "origin_class": _effective_category(origin),
                 "destination_class": _effective_category(latest),
                 "origin_raw_class": origin["class_name"], "destination_raw_class": latest["class_name"],
                 "source": "timeout_origin_and_latest" if timeout else "measured_endpoints_no_sample_in_band"}
        if _effective_category(origin) != _effective_category(latest):
            return None, basis, "CATEGORY_ENDPOINT_CONFLICT"
        category = _effective_category(origin)
    if category not in supported_categories:
        return None, basis, "UNSUPPORTED_CATEGORY_TAXONOMY_OPEN"
    return category, basis, None


def replay_frames(frames, geometry, *, source_identity, policy):
    """Return a deterministic offline B v3 ledger from contiguous source frames.

    Required policy values are line_margin_half_width_px, timeout_frames,
    timeout_clock='last_observed_origin', and
    category_policy='band_majority_ties_pending'. Frames include empty source
    frames; no synthetic post-EOF frames are generated. Known unit_id groups
    may deduplicate supported components/duplicate tracks. Otherwise raw track
    identity is an explicitly unverified physical-unit assumption.
    """
    _require(isinstance(geometry, Geometry), "geometry must be a validated Phase 5 Geometry")
    _require(isinstance(policy, dict), "Explicit experimental policy is required")
    margin = _number(policy.get("line_margin_half_width_px"), "line_margin_half_width_px")
    _require(margin >= 0, "Margin half-width cannot be negative")
    timeout = _integer(policy.get("timeout_frames"), "timeout_frames")
    _require(timeout > 0, "timeout_frames must be positive")
    _require(policy.get("timeout_clock") == "last_observed_origin", "Unknown timeout clock")
    _require(policy.get("category_policy") == "band_majority_ties_pending", "Unknown category policy")
    supported_categories = policy.get("supported_categories", sorted(SUPPORTED_CATEGORIES))
    _require(isinstance(supported_categories, list) and bool(supported_categories)
             and all(isinstance(item, str) for item in supported_categories)
             and len(set(supported_categories)) == len(supported_categories)
             and set(supported_categories) <= VEHICLE_CLASSES | {"pedestrian"},
             "supported_categories must be an explicit unique list of known raw product categories")
    supported_categories = frozenset(supported_categories)
    display_prefixes = policy.get("display_category_prefixes", DISPLAY_PREFIXES)
    _require(isinstance(display_prefixes, dict)
             and display_prefixes in (DISPLAY_PREFIXES, {**DISPLAY_PREFIXES, "bus": "B"}),
             "Display prefix mapping must retain agreed P/M/C/T; optional bus B requires explicit policy")
    _require(supported_categories <= set(display_prefixes),
             "Every supported category requires an explicit agreed display prefix")
    pedestrian_routes = policy.get("pedestrian_routes", "measured_only")
    _require(pedestrian_routes in ("measured_only", "all_operational"),
             "pedestrian_routes must be measured_only or all_operational")
    return_timeout_policy = policy.get("return_timeout_policy", "allow_operational_estimate")
    _require(return_timeout_policy in ("allow_operational_estimate", "require_new_passage_evidence"),
             "return_timeout_policy must be allow_operational_estimate or require_new_passage_evidence")
    _require(isinstance(source_identity, dict), "source_identity must be explicit")
    for key in ("video_sha256", "records_sha256", "geometry_sha256"):
        value = source_identity.get(key)
        _require(isinstance(value, str) and len(value) == 64
                 and all(c in "0123456789abcdef" for c in value), f"Invalid source identity {key}")
    for key in ("width", "height"):
        _require(isinstance(source_identity.get(key), int) and not isinstance(source_identity[key], bool)
                 and source_identity[key] > 0, f"Invalid source {key}")
    if geometry.width is not None:
        _require((geometry.width, geometry.height) == (source_identity["width"], source_identity["height"]),
                 "Geometry and source dimensions differ")
    # Include the full effective geometry as well as the retained geometry-file
    # SHA, so an accidentally mismatched caller object cannot reuse event IDs.
    namespace = hashlib.sha256(_canonical({"source_identity": source_identity,
                                           "policy": policy, "geometry": geometry.as_dict(),
                                           "version": "b_v3_reviewed_physical_passage_v1"}).encode()).hexdigest()
    signs = _side_signs(geometry)
    states, accepted, cancelled, decisions, logs = {}, {}, {}, [], []
    decision_by_passage = {}
    frame_count = 0
    first_frame = last_frame = None
    counters = Counter()

    def log(state, frame, status, *, event=None, reason=None, count_delta=0):
        observation = state["last"]
        row = {"frame_index": frame, "physical_unit_id": observation["unit_id"],
               "track_id": observation["track_id"], "passage_id": passage_id(state),
               "category": event["category"] if event else _effective_category(observation),
               "episode_id": observation.get("episode_id"), "role": observation["role"],
               "direction": _direction(state["origin"]), "route": event["route"] if event else None,
               "status": status, "event_id": event["event_id"] if event else None,
               "requested_label": ROUTE_LABELS[event["route"]] if event else None,
               "count_delta": count_delta,
               "measured_crossing": event["evidence"]["measured_crossing"] if event else False,
               "message": reason or (f"ID {observation['track_id']} {event['category']}; "
                                      f"{_direction(state['origin'])}; {ROUTE_LABELS[event['route']]}")}
        logs.append(row)

    def passage_id(state):
        observation = state["last"]
        episode = observation.get("episode_id")
        scope = observation["unit_id"] if episode is None else f"{observation['unit_id']}:episode:{episode}"
        return f"{scope}:passage:{state['ordinal']}"

    def pending(state, frame, reason):
        key = (state["last"]["unit_id"], passage_id(state))
        decision = decision_by_passage.get(key)
        if decision is None:
            decision = {"frame_index": frame, "track_id": state["last"]["track_id"],
                        "physical_unit_id": state["last"]["unit_id"], "passage_id": passage_id(state),
                        "episode_id": state["last"].get("episode_id"), "role": state["last"]["role"],
                        "status": "pending", "reasons": [], "source_ref": _ref(state["last"]),
                        "reason_evidence": []}
            decisions.append(decision)
            decision_by_passage[key] = decision
        # A later offline cancellation can reopen a previously superseded
        # decision on this same canonical passage. Do not retain a stale event.
        decision["status"] = "pending"
        decision.pop("event_id", None)
        decision.pop("display_id", None)
        state["pending_decision"] = decision
        state["pending_reasons"].add(reason)
        decision["latest_frame_index"] = frame
        if reason in decision["reasons"]:
            return
        decision["reasons"].append(reason)
        decision["reason_evidence"].append({"reason": reason, "frame_index": frame,
                                           "source_ref": _ref(state["last"])})
        log(state, frame, "pending", reason=reason)

    def cancel(state, frame, reason):
        previous = state["event"]
        if previous is None:
            return
        previous = deepcopy(previous)
        previous.update(status="cancelled", accepted_count_event=False, decision_frame=frame,
                        cancellation_reason=reason)
        previous["evidence"]["cancellation_source_ref"] = _ref(state["last"])
        accepted.pop(previous["event_id"], None)
        cancelled[previous["event_id"]] = previous
        state["event"] = None
        log(state, frame, "cancelled", event=previous, reason=reason, count_delta=-1)

    def emit(state, frame, route, category, basis, measured, destination=None):
        previous = state["event"]
        material = {"namespace": namespace, "unit_id": state["last"]["unit_id"],
                    "passage_id": passage_id(state)}
        event_id = "b_v3_" + hashlib.sha256(_canonical(material).encode()).hexdigest()[:24]
        refs = [state["origin_ref"]]
        if state["last_origin_ref"]:
            refs.append(state["last_origin_ref"])
        refs.extend(state["band_refs"])
        refs.append(_ref(state["last"]))
        refs = list({_canonical(ref): ref for ref in refs}.values())
        event = {"event_id": event_id, "physical_unit_id": state["last"]["unit_id"],
                 "passage_id": passage_id(state), "track_id": state["last"]["track_id"],
                 "episode_id": state["last"].get("episode_id"), "role": state["last"]["role"],
                 "category": category, "direction": _direction(state["origin"]),
                 "route": route, "status": "accepted", "accepted_count_event": True,
                 "activation_frame": previous["activation_frame"] if previous else frame,
                 "decision_frame": frame, "source_identity": deepcopy(source_identity),
                 "namespace": namespace,
                 "evidence": {"measured_crossing": measured, "band_observed": bool(state["band_refs"]),
                              "category_basis": basis, "source_refs": refs,
                              "source_frames": sorted({ref["frame_index"] for ref in refs}),
                              "crossing_pairs": deepcopy(state["crossing_pairs"]),
                              "gaps": deepcopy(state["gaps"]),
                              "raw_track_changes": deepcopy(state["raw_track_changes"]),
                              "identity_conflicts": deepcopy(state["identity_conflicts"]),
                              "origin_polygon": state["origin"],
                              "destination_polygon": destination["polygon"] if destination else None,
                              "destination_observed_ref": deepcopy(state["destination_observed_ref"]),
                              "last_observed_origin_frame": (state["last_origin_ref"] or {}).get("frame_index"),
                              "timeout_frames": timeout if route == "ESTIMATED_TIMEOUT" else None,
                              "direction_assumed": route == "ESTIMATED_TIMEOUT",
                              "id_change_proven": False,
                              "physical_identity_basis": ("explicit_verified_association" if all(_verified_link(refs[0], ref) for ref in refs) else "raw_track_assumption"),
                              "association_id": state["last"].get("association_id"),
                              "reviewed_category_attribution": any(ref.get("resolved_class_name") is not None for ref in refs),
                              "finite_segment_crossing_unobserved": not measured,
                              "anchor": "raw_person_bbox_bottom_center" if category == "pedestrian" else "raw_vehicle_bbox_bottom_center"}}
        if previous:
            event["previous_evidence_route"] = previous["route"]
        state["event"] = event
        accepted[event_id] = event
        cancelled.pop(event_id, None)
        for decision in decisions:
            if decision["physical_unit_id"] == event["physical_unit_id"] and decision["passage_id"] == event["passage_id"]:
                decision["status"] = "superseded_by_accepted"
                decision["event_id"] = event_id
        log(state, frame, "upgraded" if previous else "accepted", event=event,
            count_delta=0 if previous else 1)

    def normal_side(observation):
        distance = observation["signed_distance_px"]
        if abs(distance) <= margin:
            return None
        return "A" if distance * signs["A"] > 0 else "B"

    for record in frames:
        _require(isinstance(record, dict), "Each source frame must be a dictionary")
        frame = _integer(record.get("frame_index"), "frame_index")
        _require(last_frame is None or frame == last_frame + 1,
                 "Source frames must be sorted and contiguous; retain empty source frames")
        if first_frame is None:
            first_frame = frame
        last_frame = frame
        frame_count += 1
        raw_observations = record.get("observations")
        _require(isinstance(raw_observations, list), "Frame observations must be a list")
        grouped = defaultdict(list)
        seen_tracks, seen_detections = set(), set()
        for raw in raw_observations:
            observation = _observation(raw, frame, geometry, margin)
            track_key = _identity(observation["track_id"])
            _require(track_key not in seen_tracks, "Duplicate track measurement in one source frame")
            _require(observation["original_detection_index"] not in seen_detections,
                     "Repeated original detection link in one source frame")
            seen_tracks.add(track_key)
            seen_detections.add(observation["original_detection_index"])
            if observation["role"] == "rider":
                counters["rider_observations_excluded_plus_zero"] += 1
                continue
            if observation["role"] is None:
                counters["ignored_nontraffic_observations"] += 1
                continue
            grouped[_episode_key(observation)].append(observation)
            counters[f"{observation['role']}_observations"] += 1

        for unit in sorted(grouped, key=lambda key: (key[0], key[1] or "")):
            options = sorted(grouped[unit], key=lambda item: (
                (0, item["track_id"]) if isinstance(item["track_id"], int)
                else (1, _identity(item["track_id"])), item["original_detection_index"]))
            old = states.get(unit)
            if old:
                preferred = [item for item in options if item["track_id"] == old["last"]["track_id"]]
                # A supported known-unit duplicate is suppressed, but its bbox
                # is never averaged/unioned into the measured vehicle anchor.
                observation = preferred[0] if preferred else options[0]
            else:
                observation = options[0]
            _require(len({item["role"] for item in options}) == 1,
                     "Non-rider measurements require separate role-specific physical episodes")
            if len(options) > 1 and not all(_verified_link(options[0], item) for item in options[1:]):
                # The caller's matching unit name alone is not positive evidence
                # that simultaneous raw boxes represent the same physical object.
                for item in options:
                    item["identity_conflict"] = True
            counters["known_unit_duplicate_observations_suppressed"] += len(options) - 1
            side = observation["polygon"] or normal_side(observation)
            if old is None:
                if side is not None:
                    states[unit] = _new_passage(observation, side, 1)
                    states[unit]["identity_conflicts"] = [_ref(item) for item in options if item["identity_conflict"]]
                else:
                    counters["unarmed_band_only_observations"] += 1
                continue
            state = old
            previous = state["last"]
            _require(previous["role"] == observation["role"],
                     "Cross-frame role changes require a separate physical episode")
            same_track = previous["track_id"] == observation["track_id"]
            verified_handoff = not same_track and _verified_link(previous, observation)
            same_identity = same_track or verified_handoff
            delta_frames = frame - previous["frame_index"]
            if delta_frames > 1:
                state["gaps"].append({"from_frame": previous["frame_index"], "to_frame": frame,
                                      "missing_source_frames": delta_frames - 1})
            if not same_track:
                state["raw_track_changes"].append({"from_track_id": previous["track_id"],
                                                   "to_track_id": observation["track_id"], "frame_index": frame,
                                                   "association_verified": verified_handoff,
                                                   "association_id": observation.get("association_id"),
                                                   "first": _ref(previous), "second": _ref(observation)})
            toward = -(observation["signed_distance_px"] - previous["signed_distance_px"]) * signs[state["origin"]]
            state["last"] = observation
            opposite = "B" if state["origin"] == "A" else "A"
            if observation["polygon"] == opposite:
                state["destination_observed_ref"] = _ref(observation)
            # A retained unresolved duplicate relation is different from mere
            # overlapping boxes. Block only its explicitly source-linked local
            # identity conflict; do not reintroduce B v1's blanket overlap gate.
            conflicts = [item for item in options if item["identity_conflict"]]
            state["identity_conflicts"].extend(_ref(item) for item in conflicts)
            if same_identity and toward > 0:
                state["approaching"] = True
                # A measured new approach after an aborted pre-band turn can
                # start a new attempt; elapsed time alone never rearms it.
                state["turned_away"] = False
            elif same_identity and toward < 0 and state["approaching"] and not state["band_refs"]:
                state["turned_away"] = True
                cancel(state, frame, "MEASURED_U_TURN_BEFORE_BAND")
            if observation["band"]:
                state["band_refs"].append(_ref(observation))
                state["band_votes"][_effective_category(observation)] += 1
            if state["event"] is not None and state["event"]["route"] == "ESTIMATED_TIMEOUT":
                # A timeout is provisional in an offline ledger. Later source
                # evidence can contradict its identity/category prerequisites;
                # keep a cancellation/update rather than freezing a stale +1.
                if state["identity_conflicts"] or _unresolved_handoffs(state):
                    reason = ("UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE" if state["identity_conflicts"]
                              else "TIMEOUT_RAW_TRACK_HANDOFF_UNRESOLVED")
                    cancel(state, frame, reason)
                    pending(state, frame, reason)
                else:
                    revised_category, revised_basis, category_error = _category(state, timeout=True, supported_categories=supported_categories)
                    if category_error:
                        cancel(state, frame, category_error)
                        pending(state, frame, category_error)
                    elif revised_category != state["event"]["category"]:
                        emit(state, frame, "ESTIMATED_TIMEOUT", revised_category, revised_basis, False)
            if same_track and delta_frames == 1:
                intersection = segment_intersection(previous["point"], observation["point"], geometry.p1, geometry.p2)
                distances = previous["signed_distance_px"], observation["signed_distance_px"]
                if intersection["kind"] == "proper" and distances[0] * distances[1] < 0:
                    state["crossing_pairs"].append({"first": _ref(previous), "second": _ref(observation),
                                                    "intersection": intersection,
                                                    "proof": "opposite_signed_measured_endpoints"})
                    state["zero_contact"] = None
                elif (distances[0] != 0 and distances[1] == 0
                      and intersection["kind"] == "touch"):
                    state["zero_contact"] = {"entry": _ref(previous), "contacts": [_ref(observation)]}
                elif distances[0] == 0 and distances[1] == 0:
                    if state["zero_contact"] is not None and 0 < observation["line_projection"] < 1:
                        state["zero_contact"]["contacts"].append(_ref(observation))
                    else:
                        state["zero_contact"] = None
                elif distances[0] == 0 and distances[1] != 0:
                    contact = state["zero_contact"]
                    if contact is not None and intersection["kind"] == "touch":
                        entry_distance = signed_distance(contact["entry"]["point"], geometry.p1, geometry.p2)
                        if entry_distance * distances[1] < 0:
                            state["crossing_pairs"].append({"first": contact["entry"],
                                                            "second": _ref(observation),
                                                            "contact_refs": contact["contacts"],
                                                            "intersection": intersection,
                                                            "proof": "opposite_sides_bracket_contiguous_zero_contact"})
                    state["zero_contact"] = None
                else:
                    state["zero_contact"] = None
            else:
                state["zero_contact"] = None
            outside_side = normal_side(observation)
            # ROI arrival counts as completion only outside the margin, so a
            # polygon touching/overlapping the band cannot count mere contact.
            arrived = observation["polygon"] == opposite and outside_side == opposite
            crossed_outside = outside_side == opposite
            if crossed_outside:
                category, basis, error = _category(state, observation, supported_categories=supported_categories)
                same_origin_identity = (state["origin_track"] == observation["track_id"]
                                        or _verified_link(state["origin_ref"], observation))
                # A later reverse crossing invalidates an earlier forward
                # crossing as proof for this still-unconfirmed passage. Keep
                # all pairs for audit, but use the latest oriented one.
                latest_pair = state["crossing_pairs"][-1] if state["crossing_pairs"] else None
                measured = bool(latest_pair is not None
                    and signed_distance(latest_pair["first"]["point"], geometry.p1, geometry.p2) * signs[state["origin"]] > 0
                    and signed_distance(latest_pair["second"]["point"], geometry.p1, geometry.p2) * signs[state["origin"]] < 0
                    and not any(gap["from_frame"] >= latest_pair["first"]["frame_index"]
                                and gap["to_frame"] <= frame for gap in state["gaps"])
                    and not any(change["frame_index"] >= latest_pair["first"]["frame_index"]
                                for change in state["raw_track_changes"]))
                route = None
                if measured:
                    route = "LINE_MARGIN"
                elif state["band_refs"] and (state["gaps"] or state["raw_track_changes"]) and arrived and same_origin_identity and not _unresolved_handoffs(state):
                    route = "LINE_MARGIN"
                elif (not state["band_refs"] and state["gaps"] and arrived and state["origin_is_roi"]
                      and same_origin_identity and not _unresolved_handoffs(state)
                      and state["origin_category"] == _effective_category(observation)
                      and state["approaching"] and not state["turned_away"] and toward >= 0):
                    route = "OCCLUSION_DIFF_POLYGON"
                if state["identity_conflicts"]:
                    error = "UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE"
                elif _unresolved_handoffs(state):
                    error = "RAW_TRACK_CHANGED_DURING_PASSAGE"
                if route and not error and category == "pedestrian" and not measured and pedestrian_routes != "all_operational":
                    error = "PEDESTRIAN_INFERRED_ROUTE_REQUIRES_POLICY_APPROVAL"
                if route and not error:
                    emit(state, frame, route, category, basis, measured, destination=observation)
                    states[unit] = _new_passage(observation, opposite, state["ordinal"] + 1)
                    continue
                if arrived:
                    reason = error or ("RAW_TRACK_CHANGED_DURING_PASSAGE" if _unresolved_handoffs(state)
                                       else "NO_VALID_FINITE_LINE_OR_OCCLUSION_EVIDENCE")
                    if state["event"] is not None and state["event"]["route"] == "ESTIMATED_TIMEOUT":
                        cancel(state, frame, "DESTINATION_ARRIVAL_DOES_NOT_SUPPORT_VALID_PASSAGE")
                    pending(state, frame, reason)
            if observation["polygon"] == state["origin"]:
                if state["event"] is not None and state["event"]["route"] == "ESTIMATED_TIMEOUT" and toward < 0:
                    cancel(state, frame, "MEASURED_RETURN_TO_ORIGIN_CONTRADICTS_TIMEOUT")
                # The user-selected timer resets on EVERY observed origin ROI
                # frame, including stationary vehicles, not just first entry.
                state["last_origin_ref"] = _ref(observation)
                state["origin_is_roi"] = True
                if outside_side == state["origin"] and state["band_refs"]:
                    if state["event"] is not None:
                        cancel(state, frame, "RETURNED_TO_ORIGIN_WITHOUT_CONFIRMED_PASSAGE")
                    states[unit] = _new_passage(observation, state["origin"], state["ordinal"])
            elif outside_side == state["origin"] and state["band_refs"]:
                # Returning beyond the origin margin aborts a contact attempt
                # even in a neutral strip outside either ROI. A stale touch or
                # crossing cannot validate a later trip around an endpoint.
                if state["event"] is not None:
                    cancel(state, frame, "RETURNED_TO_ORIGIN_SIDE_WITHOUT_CONFIRMED_PASSAGE")
                states[unit] = _new_passage(observation, state["origin"], state["ordinal"])

        # Check source-frame time even when no measurements exist. Never extend
        # this loop beyond actual EOF to manufacture an elapsed timeout.
        for unit in sorted(states, key=lambda key: (key[0], key[1] or "")):
            state = states[unit]
            origin_ref = state["last_origin_ref"]
            if (origin_ref is None or state["event"] is not None or state["destination_observed_ref"] is not None
                    or frame - origin_ref["frame_index"] < timeout):
                continue
            if not state["approaching"] or state["turned_away"]:
                continue
            if _unresolved_handoffs(state):
                pending(state, frame, "TIMEOUT_RAW_TRACK_HANDOFF_UNRESOLVED")
                continue
            if state["identity_conflicts"]:
                pending(state, frame, "UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE")
                continue
            category, basis, error = _category(state, timeout=True, supported_categories=supported_categories)
            if error:
                pending(state, frame, error)
                continue
            if category == "pedestrian" and pedestrian_routes != "all_operational":
                pending(state, frame, "PEDESTRIAN_INFERRED_ROUTE_REQUIRES_POLICY_APPROVAL")
                continue
            if state["ordinal"] > 1 and return_timeout_policy == "require_new_passage_evidence":
                pending(state, frame, "RETURN_TIMEOUT_REQUIRES_NEW_PASSAGE_EVIDENCE")
                continue
            emit(state, frame, "ESTIMATED_TIMEOUT", category, basis, False)

    events = sorted(accepted.values(), key=lambda event: (event["activation_frame"], event["event_id"]))
    # IDs describe final active passages, never replace detector/tracker IDs.
    display_ordinals = Counter()
    for event in events:
        key = event["category"], event["direction"]
        display_ordinals[key] += 1
        event["display_id"] = passage_display_id(*key, display_ordinals[key], category_prefixes=display_prefixes)
    displays = {event["event_id"]: event["display_id"] for event in events}
    for event in cancelled.values():
        event["display_id"] = None
    for row in logs:
        row["display_id"] = displays.get(row.get("event_id"))
        row["display_status"] = "final_active_passage" if row["display_id"] else "no_final_active_passage_id"
    for decision in decisions:
        decision["display_id"] = displays.get(decision.get("event_id"))
    display_assignments = [{key: deepcopy(event[key]) for key in
                            ("event_id", "physical_unit_id", "episode_id", "passage_id", "display_id",
                             "category", "direction", "activation_frame", "decision_frame")}
                           | {"source_frames": deepcopy(event["evidence"]["source_frames"])}
                           for event in events]
    final_pending = [decision for decision in decisions if decision["status"] == "pending"]
    by_category = Counter(event["category"] for event in events)
    by_direction = Counter(event["direction"] for event in events)
    by_route = Counter(event["route"] for event in events)
    measured_total = sum(event["evidence"]["measured_crossing"] for event in events)
    open_passages = []
    for unit, state in sorted(states.items(), key=lambda item: (item[0][0], item[0][1] or "")):
        if state["event"] is not None:
            disposition = "ACCEPTED_ESTIMATE_AWAITING_STRONGER_EVIDENCE"
        elif decision_by_passage.get((state["last"]["unit_id"], passage_id(state)), {}).get("status") == "pending":
            disposition = "PENDING"
        elif state["turned_away"]:
            disposition = "TURNED_AWAY_WITHOUT_CONFIRMED_PASSAGE"
        elif not state["approaching"]:
            disposition = "NO_NEW_PASSAGE_EVIDENCE"
        elif state["last_origin_ref"] is None:
            disposition = "NO_ORIGIN_ROI_FOR_TIMEOUT"
        else:
            disposition = "EOF_WITHOUT_DESTINATION_OR_ELIGIBLE_TIMEOUT"
        open_passages.append({"physical_unit_id": state["last"]["unit_id"], "episode_id": state["last"].get("episode_id"),
                              "passage_id": passage_id(state),
                              "track_id": state["last"]["track_id"], "disposition": disposition,
                              "last_observed_frame": state["last"]["frame_index"],
                              "last_origin_frame": (state["last_origin_ref"] or {}).get("frame_index"),
                              "destination_observed": state["destination_observed_ref"] is not None,
                              "band_observed": bool(state["band_refs"])})
    aggregate = {"total": len(events), "by_category": dict(sorted(by_category.items())),
                 "by_direction": dict(sorted(by_direction.items())), "by_route": dict(sorted(by_route.items())),
                 "measured_total": measured_total, "inferred_total": len(events) - measured_total,
                 "pending": len(final_pending), "cancelled": len(cancelled),
                 "vehicle_total": sum(event["category"] != "pedestrian" for event in events),
                 "pedestrian_total": by_category.get("pedestrian", 0)}
    report = {"version": "b_v3_reviewed_physical_passage_v1", "namespace": namespace,
              "frame_count": frame_count, "first_frame_index": first_frame, "last_frame_index": last_frame,
              "observed_units": len(states), "observed_physical_episodes": len(states), "counters": dict(sorted(counters.items())),
              "open_passage_diagnostic_counts": dict(sorted(Counter(
                  item["disposition"] for item in open_passages).items())),
              "policy": deepcopy(policy), "source_identity": deepcopy(source_identity),
              "no_model_inference": True, "post_eof_frames_generated": 0,
              "physical_identity_assumption": "unreviewed retained raw track/episode denotes one unit; only explicit scoped associations permit handoff",
              "pedestrian_policy": "positive pedestrian role only; rider plus zero; unknown person role unresolved",
              "pedestrian_routes": pedestrian_routes,
              "return_timeout_policy": return_timeout_policy,
              "return_timeout_policy_basis": "explicit_policy" if "return_timeout_policy" in policy else "legacy_operational_estimate_default",
              "pedestrian_route_policy_basis": "explicit_policy" if "pedestrian_routes" in policy else "conservative_research_default_pending_user_decision",
              "supported_categories": sorted(supported_categories), "display_category_prefixes": deepcopy(display_prefixes),
              "display_id_semantics": "per-video final active passage; raw tracker IDs remain unchanged",
              "timeout_semantics": "automatic operational estimate, not proof of crossing or ID change",
              "unsupported_taxonomy": ["bus_angkot", "pickup_business_mapping"],
              "evaluation_limit": "Software ledger; no ground-truth counting performance claim"}
    return {"source_identity": deepcopy(source_identity), "policy": deepcopy(policy),
            "events": events, "cancelled_events": sorted(cancelled.values(), key=lambda event: event["event_id"]),
            "decisions": decisions, "passage_log": logs, "open_passage_diagnostics": open_passages,
            "display_assignments": display_assignments, "aggregate": aggregate, "report": report}
