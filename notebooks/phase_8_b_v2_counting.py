"""B v2 notebook counting experiment on retained measured tracks only.

This does not run detection/tracking/ReID and does not modify the frozen B v1
resolver. Three explicitly different evidence routes share one passage ledger.
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
from typing import Any

from phase_5_geometry_helpers import Geometry, segment_intersection, signed_distance


SUPPORTED_CATEGORIES = frozenset(("motorcycle", "car", "truck"))
VEHICLE_CLASSES = SUPPORTED_CATEGORIES | {"bus"}
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
    point = ((box[0] + box[2]) / 2, box[3])
    band = finite_band(point, geometry, margin)
    result = {"frame_index": frame, "track_id": track, "unit_id": unit,
              "original_detection_index": index, "raw_bbox": box, "point": list(point),
              "class_name": category, "observed": True, "emitted": True,
              "identity_conflict": raw.get("identity_conflict", False),
              "polygon": geometry.side(point), "band": band["inside"],
              "signed_distance_px": band["signed_distance_px"],
              "line_projection": band["projection"]}
    for key in ("class_id", "confidence", "measurement_provenance", "source_ref"):
        if key in raw:
            result[key] = deepcopy(raw[key])
    return result


def _ref(observation):
    return {key: deepcopy(observation[key]) for key in
            ("frame_index", "track_id", "original_detection_index", "raw_bbox", "point",
             "class_name", "observed", "emitted")}


def _direction(origin):
    return "A_TO_B" if origin == "A" else "B_TO_A"


def _new_passage(observation, origin, ordinal):
    return {"origin": origin, "ordinal": ordinal, "origin_ref": _ref(observation),
            "last_origin_ref": _ref(observation) if observation["polygon"] == origin else None,
            "origin_is_roi": observation["polygon"] == origin,
            "origin_track": observation["track_id"], "origin_category": observation["class_name"],
            "band_refs": [_ref(observation)] if observation["band"] else [],
            "band_votes": Counter({observation["class_name"]: 1}) if observation["band"] else Counter(),
            "crossing_pairs": [], "zero_contact": None,
            "gaps": [], "raw_track_changes": [], "approaching": False,
            "identity_conflicts": [_ref(observation)] if observation["identity_conflict"] else [],
            "destination_observed_ref": None,
            "turned_away": False, "event": None, "pending_reasons": set(),
            "pending_decision": None,
            "last": observation}


def _category(state, destination=None, *, timeout=False):
    if state["band_votes"]:
        votes = state["band_votes"]
        maximum = max(votes.values())
        winners = sorted(category for category, count in votes.items() if count == maximum)
        basis = {"policy": "band_majority_ties_pending", "votes": dict(sorted(votes.items())),
                 "source": "observed_vehicle_BC_inside_finite_band"}
        if len(winners) != 1:
            return None, basis, "CATEGORY_TIE_IN_BAND"
        category = winners[0]
    else:
        origin = state["last_origin_ref"] or state["origin_ref"]
        latest = destination or state["last"]
        basis = {"policy": "matching_observed_endpoints", "origin_class": origin["class_name"],
                 "destination_class": latest["class_name"],
                 "source": "timeout_origin_and_latest" if timeout else "measured_endpoints_no_sample_in_band"}
        if origin["class_name"] != latest["class_name"]:
            return None, basis, "CATEGORY_ENDPOINT_CONFLICT"
        category = origin["class_name"]
    if category not in SUPPORTED_CATEGORIES:
        return None, basis, "UNSUPPORTED_CATEGORY_TAXONOMY_OPEN"
    return category, basis, None


def replay_frames(frames, geometry, *, source_identity, policy):
    """Return a deterministic offline B v2 ledger from contiguous source frames.

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
                                           "version": "b_v2_three_routes_v1"}).encode()).hexdigest()
    signs = _side_signs(geometry)
    states, accepted, cancelled, decisions, logs = {}, {}, {}, [], []
    frame_count = 0
    first_frame = last_frame = None
    counters = Counter()

    def log(state, frame, status, *, event=None, reason=None, count_delta=0):
        observation = state["last"]
        row = {"frame_index": frame, "physical_unit_id": observation["unit_id"],
               "track_id": observation["track_id"], "passage_id": passage_id(state),
               "category": event["category"] if event else observation["class_name"],
               "direction": _direction(state["origin"]), "route": event["route"] if event else None,
               "status": status, "event_id": event["event_id"] if event else None,
               "requested_label": ROUTE_LABELS[event["route"]] if event else None,
               "count_delta": count_delta,
               "measured_crossing": event["evidence"]["measured_crossing"] if event else False,
               "message": reason or (f"ID {observation['track_id']} {event['category']}; "
                                      f"{_direction(state['origin'])}; {ROUTE_LABELS[event['route']]}")}
        logs.append(row)

    def passage_id(state):
        return f"{state['last']['unit_id']}:passage:{state['ordinal']}"

    def pending(state, frame, reason):
        if reason in state["pending_reasons"]:
            return
        state["pending_reasons"].add(reason)
        if state["pending_decision"] is None:
            decision = {"frame_index": frame, "track_id": state["last"]["track_id"],
                        "physical_unit_id": state["last"]["unit_id"], "passage_id": passage_id(state),
                        "status": "pending", "reasons": [], "source_ref": _ref(state["last"]),
                        "reason_evidence": []}
            decisions.append(decision)
            state["pending_decision"] = decision
        decision = state["pending_decision"]
        decision["reasons"].append(reason)
        decision["latest_frame_index"] = frame
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
        event_id = "b_v2_" + hashlib.sha256(_canonical(material).encode()).hexdigest()[:24]
        refs = [state["origin_ref"]]
        if state["last_origin_ref"]:
            refs.append(state["last_origin_ref"])
        refs.extend(state["band_refs"])
        refs.append(_ref(state["last"]))
        refs = list({_canonical(ref): ref for ref in refs}.values())
        event = {"event_id": event_id, "physical_unit_id": state["last"]["unit_id"],
                 "passage_id": passage_id(state), "track_id": state["last"]["track_id"],
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
                              "physical_identity_basis": "caller_known_unit_or_raw_track_assumption",
                              "finite_segment_crossing_unobserved": not measured,
                              "anchor": "raw_vehicle_bbox_bottom_center"}}
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
            if observation["class_name"] not in VEHICLE_CLASSES:
                counters["ignored_nonvehicle_observations"] += 1
                continue
            grouped[observation["unit_id"]].append(observation)
            counters["vehicle_observations"] += 1

        for unit in sorted(grouped):
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
            same_track = previous["track_id"] == observation["track_id"]
            delta_frames = frame - previous["frame_index"]
            if delta_frames > 1:
                state["gaps"].append({"from_frame": previous["frame_index"], "to_frame": frame,
                                      "missing_source_frames": delta_frames - 1})
            if not same_track:
                state["raw_track_changes"].append({"from_track_id": previous["track_id"],
                                                   "to_track_id": observation["track_id"], "frame_index": frame})
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
            if same_track and toward > 0:
                state["approaching"] = True
                # A measured new approach after an aborted pre-band turn can
                # start a new attempt; elapsed time alone never rearms it.
                state["turned_away"] = False
            elif same_track and toward < 0 and state["approaching"] and not state["band_refs"]:
                state["turned_away"] = True
                cancel(state, frame, "MEASURED_U_TURN_BEFORE_BAND")
            if observation["band"]:
                state["band_refs"].append(_ref(observation))
                state["band_votes"][observation["class_name"]] += 1
            if state["event"] is not None and state["event"]["route"] == "ESTIMATED_TIMEOUT":
                # A timeout is provisional in an offline ledger. Later source
                # evidence can contradict its identity/category prerequisites;
                # keep a cancellation/update rather than freezing a stale +1.
                if state["identity_conflicts"] or state["raw_track_changes"]:
                    reason = ("UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE" if state["identity_conflicts"]
                              else "TIMEOUT_RAW_TRACK_HANDOFF_UNRESOLVED")
                    cancel(state, frame, reason)
                    pending(state, frame, reason)
                else:
                    revised_category, revised_basis, category_error = _category(state, timeout=True)
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
                category, basis, error = _category(state, observation)
                same_origin_track = state["origin_track"] == observation["track_id"]
                # A later reverse crossing invalidates an earlier forward
                # crossing as proof for this still-unconfirmed passage. Keep
                # all pairs for audit, but use the latest oriented one.
                latest_pair = state["crossing_pairs"][-1] if state["crossing_pairs"] else None
                measured = bool(latest_pair is not None
                    and signed_distance(latest_pair["first"]["point"], geometry.p1, geometry.p2) * signs[state["origin"]] > 0
                    and signed_distance(latest_pair["second"]["point"], geometry.p1, geometry.p2) * signs[state["origin"]] < 0
                    and not any(gap["from_frame"] >= latest_pair["first"]["frame_index"]
                                and gap["to_frame"] <= frame for gap in state["gaps"])
                    and not state["raw_track_changes"])
                route = None
                if measured:
                    route = "LINE_MARGIN"
                elif state["band_refs"] and state["gaps"] and arrived and same_origin_track and not state["raw_track_changes"]:
                    route = "LINE_MARGIN"
                elif (not state["band_refs"] and state["gaps"] and arrived and state["origin_is_roi"]
                      and same_origin_track and not state["raw_track_changes"]
                      and state["origin_category"] == observation["class_name"]
                      and state["approaching"] and not state["turned_away"] and toward >= 0):
                    route = "OCCLUSION_DIFF_POLYGON"
                if state["identity_conflicts"]:
                    error = "UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE"
                if route and not error:
                    emit(state, frame, route, category, basis, measured, destination=observation)
                    states[unit] = _new_passage(observation, opposite, state["ordinal"] + 1)
                    continue
                if arrived:
                    reason = error or ("RAW_TRACK_CHANGED_DURING_PASSAGE" if state["raw_track_changes"]
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
        for unit in sorted(states):
            state = states[unit]
            origin_ref = state["last_origin_ref"]
            if (origin_ref is None or state["event"] is not None or state["destination_observed_ref"] is not None
                    or frame - origin_ref["frame_index"] < timeout):
                continue
            if not state["approaching"] or state["turned_away"]:
                continue
            if state["raw_track_changes"]:
                pending(state, frame, "TIMEOUT_RAW_TRACK_HANDOFF_UNRESOLVED")
                continue
            if state["identity_conflicts"]:
                pending(state, frame, "UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE")
                continue
            category, basis, error = _category(state, timeout=True)
            if error:
                pending(state, frame, error)
                continue
            emit(state, frame, "ESTIMATED_TIMEOUT", category, basis, False)

    events = sorted(accepted.values(), key=lambda event: (event["activation_frame"], event["event_id"]))
    final_pending = [decision for decision in decisions if decision["status"] == "pending"]
    by_category = Counter(event["category"] for event in events)
    by_direction = Counter(event["direction"] for event in events)
    by_route = Counter(event["route"] for event in events)
    measured_total = sum(event["evidence"]["measured_crossing"] for event in events)
    open_passages = []
    for unit, state in sorted(states.items()):
        if state["event"] is not None:
            disposition = "ACCEPTED_ESTIMATE_AWAITING_STRONGER_EVIDENCE"
        elif state["pending_decision"] is not None and state["pending_decision"]["status"] == "pending":
            disposition = "PENDING"
        elif state["turned_away"]:
            disposition = "TURNED_AWAY_WITHOUT_CONFIRMED_PASSAGE"
        elif not state["approaching"]:
            disposition = "NO_NEW_PASSAGE_EVIDENCE"
        elif state["last_origin_ref"] is None:
            disposition = "NO_ORIGIN_ROI_FOR_TIMEOUT"
        else:
            disposition = "EOF_WITHOUT_DESTINATION_OR_ELIGIBLE_TIMEOUT"
        open_passages.append({"physical_unit_id": unit, "passage_id": passage_id(state),
                              "track_id": state["last"]["track_id"], "disposition": disposition,
                              "last_observed_frame": state["last"]["frame_index"],
                              "last_origin_frame": (state["last_origin_ref"] or {}).get("frame_index"),
                              "destination_observed": state["destination_observed_ref"] is not None,
                              "band_observed": bool(state["band_refs"])})
    aggregate = {"total": len(events), "by_category": dict(sorted(by_category.items())),
                 "by_direction": dict(sorted(by_direction.items())), "by_route": dict(sorted(by_route.items())),
                 "measured_total": measured_total, "inferred_total": len(events) - measured_total,
                 "pending": len(final_pending), "cancelled": len(cancelled)}
    report = {"version": "b_v2_three_routes_v1", "namespace": namespace,
              "frame_count": frame_count, "first_frame_index": first_frame, "last_frame_index": last_frame,
              "observed_units": len(states), "counters": dict(sorted(counters.items())),
              "open_passage_diagnostic_counts": dict(sorted(Counter(
                  item["disposition"] for item in open_passages).items())),
              "policy": deepcopy(policy), "source_identity": deepcopy(source_identity),
              "no_model_inference": True, "post_eof_frames_generated": 0,
              "physical_identity_assumption": "ungrouped retained raw track denotes one unit; not independently proven",
              "timeout_semantics": "automatic operational estimate, not proof of crossing or ID change",
              "unsupported_taxonomy": ["bus_angkot", "pickup_business_mapping"],
              "evaluation_limit": "Software ledger; no ground-truth counting performance claim"}
    return {"source_identity": deepcopy(source_identity), "policy": deepcopy(policy),
            "events": events, "cancelled_events": sorted(cancelled.values(), key=lambda event: event["event_id"]),
            "decisions": decisions, "passage_log": logs, "open_passage_diagnostics": open_passages,
            "aggregate": aggregate, "report": report}
