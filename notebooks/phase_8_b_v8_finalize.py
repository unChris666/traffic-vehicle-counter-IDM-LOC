"""Exact reviewed pending closures; no passage creation or history relabeling.

Positive component review can close the recorded candidate with +0. It does
not label a whole tracker history, assign a parent identity, repair geometry,
or establish that later observations of the same raw ID are components.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path


SCHEMA = "phase9_b_v8_pending_adjudications_v1"
REASON = "REVIEWED_NON_INDEPENDENT_COMPONENT"
STATUS = "resolved_not_eligible"
ROLES = frozenset(("RIDER_PASSENGER", "VEHICLE_OCCUPANT", "CARGO"))
ORIGINS = frozenset(("AI_PIXELS_REVIEW", "USER_REVIEW"))
SCOPE_FIELDS = ("track_id", "physical_unit_id", "episode_id", "passage_id")
SOURCE_KEYS = ("video_sha256", "records_sha256", "geometry_sha256")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode()).hexdigest()


def _sha(value):
    return (isinstance(value, str) and len(value) == 64
            and all(character in "0123456789abcdef" for character in value))


def _scope(row):
    return tuple(row.get(field) for field in SCOPE_FIELDS)


def _pending_index(result):
    rows = [row for row in result.get("decisions", []) if row.get("status") == "pending"]
    index = {_scope(row): row for row in rows}
    _require(len(index) == len(rows), "Repeated pending candidate scope")
    return index


def _verify_artifacts(artifacts, root):
    _require(isinstance(artifacts, list) and bool(artifacts), "Positive review needs retained proof artifacts")
    paths, has_pixels = set(), False
    for item in artifacts:
        relative = item.get("path")
        _require(isinstance(relative, str) and bool(relative)
                 and not Path(relative).is_absolute(), "Proof artifact must use a repository-relative path")
        path = (root / relative).resolve()
        _require(path.is_relative_to(root) and path.is_file(), "Proof artifact is missing or outside repository")
        _require(relative not in paths and _sha(item.get("sha256")), "Proof artifacts need unique paths and SHA256")
        paths.add(relative)
        _require(hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], "Proof artifact SHA256 differs")
        has_pixels |= path.suffix.lower() in (".jpg", ".jpeg", ".png")
    _require(has_pixels, "A source pixel artifact is required for positive component review")


def _validate_review(review, baseline, source_identity, root):
    _require(isinstance(review, dict), "Adjudication must be an object")
    _require(isinstance(review.get("adjudication_id"), str) and review["adjudication_id"], "Stable adjudication ID required")
    scope = review.get("baseline_candidate_scope")
    _require(isinstance(scope, dict) and set(scope) == set(SCOPE_FIELDS), "Exact baseline candidate scope required")
    key = _scope(scope)
    _require(key in baseline, "Review does not target a baseline pending candidate")
    row = baseline[key]
    ref = review.get("baseline_source_ref")
    _require(ref == row.get("source_ref"), "Review witness differs from baseline candidate measurement")
    _require(isinstance(ref, dict) and ref.get("observed") is True
             and ref.get("emitted") is True and len(ref.get("raw_bbox", [])) == 4,
             "Review needs an actual emitted measured source witness")
    _require(ref.get("track_id") == scope["track_id"], "Review witness belongs to another raw track")
    frame = ref.get("frame_index")
    _require(type(frame) is int and type(ref.get("original_detection_index")) is int,
             "Review needs exact source frame and detection index")
    point, box = ref.get("point"), ref["raw_bbox"]
    _require(point == [(box[0] + box[2]) / 2, box[3]], "Review source point differs from measured raw BC")
    role = review.get("reviewed_role")
    _require(role in ROLES, "Only positive non-independent component roles may close +0")
    _require(review.get("reviewer_origin") in ORIGINS, "Explicit reviewed decision origin required")
    _require(review.get("final_status", STATUS) == STATUS
             and review.get("reason", REASON) == REASON,
             "This finalizer cannot promote accepted, invent invalid, or change disposition semantics")
    _require(review.get("previous_status", "pending") == "pending", "Review previous state must be pending")
    if role in ("RIDER_PASSENGER", "VEHICLE_OCCUPANT"):
        _require(ref.get("class_name") == "person", "Person-component review cannot relabel a vehicle measurement")
    else:
        parents = review.get("related_vehicle_raw_ids", [])
        _require(isinstance(parents, list) and bool(parents)
                 and all(type(t) is int and t != ref["track_id"] for t in parents),
                 "Cargo exclusion requires positively reviewed related vehicle context")
    scope = review.get("role_scope")
    _require(isinstance(scope, dict)
             and type(scope.get("start_frame")) is int and type(scope.get("end_frame")) is int
             and scope["start_frame"] <= frame <= scope["end_frame"],
             "Role proof must contain the candidate's own source frame")
    positive = review.get("positive_source_frames", [])
    _require(isinstance(positive, list) and frame in positive
             and all(type(f) is int and scope["start_frame"] <= f <= scope["end_frame"] for f in positive),
             "Positive review source frames do not support the exact candidate witness")
    for source_key in SOURCE_KEYS[:2]:
        review_key = "source_video_sha256" if source_key == "video_sha256" else "records_sha256"
        _require(review.get(review_key) == source_identity[source_key], "Review proof belongs to another video/cache")
    artifacts = review.get("proof_artifacts", [])
    _verify_artifacts(artifacts, root)
    if review["reviewer_origin"] == "USER_REVIEW":
        authority = review.get("reviewed_decision_authority", {})
        _require(authority.get("kind") == "EXPLICIT_USER_INSTRUCTION"
                 and any(item.get("path") == authority.get("path")
                         and item.get("sha256") == authority.get("sha256") for item in artifacts),
                 "USER_REVIEW must retain explicit user instruction authority")
        path = root / authority["path"]
        try:
            authority_text = path.read_text()
        except UnicodeError as error:
            raise ValueError("User instruction authority must contain retained text") from error
        excerpt = authority.get("exact_supporting_excerpt")
        _require(isinstance(excerpt, str) and bool(excerpt) and excerpt in authority_text,
                 "User review lacks its exact authority excerpt")
    return key


def finalize_reviewed_pending(result, adjudications, *, baseline_result,
                              source_identity, finalization_frame=None, repo_root=None):
    """Close only exact source-reviewed pending candidates with existing +0 state.

    The caller must bind ``baseline_result_sha256`` to the actual retained
    baseline file before loading it; this function verifies source identity,
    candidate records, and the retained proof bytes. It never creates events.
    """
    root = Path(repo_root or Path(__file__).resolve().parent.parent).resolve()
    _require(isinstance(adjudications, dict) and adjudications.get("schema_version") == SCHEMA,
             "Explicit supported P1 pending adjudication manifest required")
    _require(_sha(adjudications.get("baseline_result_sha256")), "Baseline file SHA256 binding required")
    for key in SOURCE_KEYS:
        _require(_sha(source_identity.get(key))
                 and adjudications.get("source_identity", {}).get(key) == source_identity[key]
                 and baseline_result.get("source_identity", {}).get(key) == source_identity[key]
                 and result.get("source_identity", result.get("report", {}).get("source_identity", {})).get(key) == source_identity[key],
                 "Baseline, candidate, review and input source identities must match")
    last = result["report"]["last_frame_index"]
    frame = last if finalization_frame is None else finalization_frame
    _require(type(frame) is int and frame == last, "Reviewed offline decision must use actual source EOF")
    reviews = adjudications.get("adjudications")
    _require(isinstance(reviews, list), "Adjudications must be an explicit list")
    baseline = _pending_index(baseline_result)
    candidate = _pending_index(result)
    validated, ids, scopes = [], set(), set()
    for review in reviews:
        key = _validate_review(review, baseline, source_identity, root)
        _require(review["adjudication_id"] not in ids and key not in scopes,
                 "Duplicate or conflicting pending adjudication")
        ids.add(review["adjudication_id"])
        scopes.add(key)
        _require(key in candidate, "Baseline candidate is no longer pending in this replay")
        _require(candidate[key].get("source_ref") == baseline[key].get("source_ref")
                 and candidate[key].get("role") == baseline[key].get("role"),
                 "Reviewed replay changed candidate source/context; explicit new review required")
        validated.append((key, review))

    output = deepcopy(result)
    pending = _pending_index(output)
    audits = []
    for key, review in validated:
        row = pending[key]
        original = deepcopy(row)
        source = deepcopy(row["source_ref"])
        origin = ("AI_ASSISTED_SOURCE_REVIEW" if review["reviewer_origin"] == "AI_PIXELS_REVIEW"
                  else "EXPLICIT_USER_SOURCE_REVIEW")
        row.update(status=STATUS, count_delta=0, accepted_count_event=False, display_id=None,
            candidate_decision_frame=original.get("frame_index"), decision_frame=frame,
            resolved_at_frame=frame, resolution_reason=REASON, reasons=[REASON],
            previous_status="pending", previous_reasons=deepcopy(original.get("reasons", [])),
            previous_reason_evidence=deepcopy(original.get("reason_evidence", [])),
            reviewed_role=review["reviewed_role"], adjudication_id=review["adjudication_id"],
            decision_origin=origin, finalization_mode="OFFLINE_REVIEWED_PLUS_ZERO",
            role_assignment_effect="EXACT_PENDING_SOURCE_SAMPLE_ONLY_NO_HISTORY_RELABEL_OR_PARENT_ALIAS",
            reason_evidence=[{"reason": REASON, "source_ref": source,
                "adjudication_id": review["adjudication_id"],
                "proof_artifacts": deepcopy(review["proof_artifacts"]),
                "role_scope": deepcopy(review["role_scope"])}])
        output["passage_log"].append({"frame_index": frame,
            "candidate_decision_frame": original.get("frame_index"),
            **{name: deepcopy(row.get(name)) for name in SCOPE_FIELDS},
            "status": STATUS, "count_delta": 0, "event_id": None,
            "source_ref": source, "message": REASON,
            "adjudication_id": review["adjudication_id"], "decision_origin": origin,
            "reviewed_role": review["reviewed_role"]})
        for diagnostic in output.get("open_passage_diagnostics", []):
            if _scope(diagnostic) == key:
                diagnostic.update(previous_disposition=diagnostic.get("disposition"),
                    disposition=REASON, timeout_eligible=False,
                    reviewed_pending_adjudication_id=review["adjudication_id"])
        audits.append({"adjudication_id": review["adjudication_id"],
            "baseline_candidate_scope": deepcopy(review["baseline_candidate_scope"]),
            "baseline_source_ref": source, "previous_decision": original,
            "final_status": STATUS, "reason": REASON, "reviewed_role": review["reviewed_role"],
            "candidate_decision_frame": original.get("frame_index"), "decision_frame": frame,
            "count_delta": 0, "decision_origin": origin, "review": deepcopy(review),
            "crossing_evidence_changed": False, "physical_identity_merged": False,
            "not_a_recovered_physical_passage": True})
    output["aggregate"]["pending"] = len(_pending_index(output))
    _require(output["events"] == result["events"]
             and output.get("cancelled_events") == result.get("cancelled_events")
             and output.get("invalid_decisions") == result.get("invalid_decisions"),
             "Reviewed pending closure must not change accepted or invalid passage decisions")
    _require(sum(item.get("count_delta", 0) for item in output["passage_log"])
             == output["aggregate"]["total"], "Published log no longer reconciles")
    output["v8_pending_finalization_audit"] = audits
    if "open_passage_diagnostic_counts" in output["report"]:
        output["report"]["open_passage_diagnostic_counts"] = dict(sorted(Counter(
            row["disposition"] for row in output.get("open_passage_diagnostics", [])).items()))
    output["report"]["v8_reviewed_pending_finalization"] = {
        "baseline_pending": len(baseline), "candidate_pending_before": len(candidate),
        "candidate_pending_after": output["aggregate"]["pending"],
        "resolved_not_eligible": len(audits), "resolved_to_invalid": 0,
        "accepted_events_added": 0, "actual_offline_decision_frame": frame,
        "roles": dict(sorted(Counter(a["reviewed_role"] for a in audits).items())),
        "review_manifest_sha256_semantic": _digest(adjudications),
        "baseline_result_sha256": adjudications["baseline_result_sha256"],
        "source_observations_or_histories_reassigned": False,
        "qc_adjudications_used_as_machine_predictions": False}
    return output
