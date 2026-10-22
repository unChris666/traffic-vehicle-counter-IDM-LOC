"""Source-bound documentary comparison against the retained Phase 9 QC packet.

This is an audit helper, not a physical-identity resolver or a counting engine.
Shared measurements identify candidate counterparts; they do not establish that
the new physical-unit decision is correct. In particular, retaining an alias in
one canonical event can be the correct resolution of a duplicate QC event.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path


def _read(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def source_key(ref):
    """A raw ID/frame alone is insufficient: include detector index and bbox."""
    if not isinstance(ref, dict):
        return None
    if type(ref.get("frame_index")) is not int or type(ref.get("track_id")) is not int:
        return None
    box = ref.get("raw_bbox")
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    return (ref["frame_index"], ref["track_id"], ref.get("original_detection_index"), tuple(box))


def _refs(value):
    result = set()
    def walk(item):
        if isinstance(item, dict):
            key = source_key(item)
            if key is not None:
                result.add(key)
            for nested in item.values():
                walk(nested)
        elif isinstance(item, (tuple, list)):
            for nested in item:
                walk(nested)
    walk(value)
    return result


def _summary(event):
    return {key: event.get(key) for key in (
        "event_id", "track_id", "physical_unit_id", "episode_id", "passage_id",
        "category", "direction", "route", "activation_frame", "decision_frame",
    )} | {"measured_crossing": bool(event.get("evidence", {}).get("measured_crossing"))}


def _validate_ledger(result):
    events, aggregate = result.get("events", []), result.get("aggregate", {})
    event_ids = [event["event_id"] for event in events]
    _require(len(set(event_ids)) == len(event_ids), "Repeated active event ID")
    cancelled_ids = {event["event_id"] for event in result.get("cancelled_events", [])}
    _require(not (set(event_ids) & cancelled_ids), "Event is simultaneously active and cancelled")
    _require(aggregate.get("total") == len(events), "Aggregate total differs from active events")
    for field, key in (("category", "by_category"), ("direction", "by_direction"), ("route", "by_route")):
        _require(Counter(event[field] for event in events) == aggregate.get(key, {}), f"Aggregate {key} differs")
    measured = sum(bool(event.get("evidence", {}).get("measured_crossing")) for event in events)
    _require(aggregate.get("measured_total") == measured
             and aggregate.get("inferred_total") == len(events) - measured, "Measured/inferred aggregate differs")
    _require(aggregate.get("pending") == sum(row.get("status") == "pending" for row in result.get("decisions", [])),
             "Pending aggregate differs from decision ledger")


class SourceIndex:
    def __init__(self, result):
        self.events = result.get("events", [])
        self.event_refs = [_refs(event.get("evidence", {})) for event in self.events]
        self.by_ref = defaultdict(set)
        for index, refs in enumerate(self.event_refs):
            for ref in refs:
                self.by_ref[ref].add(index)
        self.decisions = result.get("decisions", [])
        self.decision_refs = [_refs(row) for row in self.decisions]
        self.assignments = defaultdict(list)
        for row in result.get("frame_assignments", []):
            self.assignments[row["track_id"], row["frame_index"]].append(row)

    def candidates(self, reference):
        refs = _refs(reference)
        matches = Counter(index for ref in refs for index in self.by_ref.get(ref, ()))
        return [dict(_summary(self.events[index]),
                     shared_source_measurements=count,
                     shared_source_frames=sorted({ref[0] for ref in refs & self.event_refs[index]}),
                     is_documentary_counterpart_not_physical_gt=True)
                for index, count in sorted(matches.items(), key=lambda row: (-row[1], row[0]))]


def expected_case_matrix(qc_root):
    qc_root = Path(qc_root)
    pending = _jsonl(qc_root / "review_decisions.jsonl")
    cancellations = _jsonl(qc_root / "accepted_event_actions.jsonl")
    discovery = _jsonl(qc_root / "unmatched/unmatched_passages.jsonl")
    _require(len(pending) == 68 and Counter(row["group"] for row in pending)
             == {"identity": 31, "roles": 29, "duplicates": 8}, "QC inventory must contain all 68 cases")
    _require(len({row["baseline_passage_id"] for row in pending}) == 68, "QC passage keys repeat")
    _require(len(cancellations) == len({row["event_id"] for row in cancellations}) == 16,
             "QC cancellation inventory must contain 16 unique events")
    _require(len(discovery) == 10 and len({row["case_id"] for row in discovery}) == 10,
             "QC discovery inventory differs")
    _require(Counter(row["qc_status"] for row in pending)
             == {"QC_RECOMMEND_CLOSE": 59, "UNRESOLVED": 9}, "QC pending dispositions differ")
    return {"pending": pending, "cancellations": cancellations, "discovery": discovery}


def compare_results(old, new, qc_root):
    """Compare one frozen-cache replay to all retained QC expectations.

    No inferred +1/+0 physical adjudication is made by this helper. A disappeared
    pending can be an unresolved coverage loss, and a shared source alias can be
    correctly absorbed by a canonical passage. Both remain visible in the output.
    """
    _validate_ledger(old)
    _validate_ledger(new)
    for key in ("video_sha256", "records_sha256", "geometry_sha256"):
        _require(old.get("source_identity", {}).get(key)
                 == new.get("source_identity", {}).get(key)
                 and old.get("source_identity", {}).get(key), f"Source identity differs: {key}")
    matrix = expected_case_matrix(qc_root)
    index = SourceIndex(new)
    old_pending = {row["passage_id"]: row for row in old.get("decisions", []) if row.get("status") == "pending"}
    _require(set(old_pending) == {row["baseline_passage_id"] for row in matrix["pending"]},
             "Old pending set differs from exact QC baseline")
    old_events = {row["event_id"]: row for row in old.get("events", [])}
    _require(len(old_events) == len(old.get("events", [])), "Repeated baseline event ID")

    pending_rows = []
    for case in matrix["pending"]:
        prior = old_pending[case["baseline_passage_id"]]
        anchor = prior.get("source_ref", {})
        anchors = _refs(anchor)
        decisions = [{"status": row.get("status"), "reasons": row.get("reasons"),
                      "passage_id": row.get("passage_id"), "track_id": row.get("track_id"),
                      "frame_index": row.get("frame_index")}
                     for row, refs in zip(index.decisions, index.decision_refs) if anchors & refs]
        assignment = index.assignments.get((case["raw_track_id"], anchor.get("frame_index")), [])
        candidates = index.candidates(anchor)
        if candidates:
            status = "ACCEPTED_EVENT_CONTAINS_EXACT_BASELINE_DECISION_MEASUREMENT"
        elif decisions:
            status = "DECISION_CONTAINS_EXACT_BASELINE_MEASUREMENT"
        elif assignment:
            status = "OBSERVED_ASSIGNMENT_RETAINED_NO_EVENT_OR_DECISION_AT_EXACT_ANCHOR"
        else:
            status = "EXACT_ANCHOR_NOT_FOUND_REQUIRES_COVERAGE_REVIEW"
        pending_rows.append({
            "case_id": case["case_id"], "group": case["group"], "raw_track_id": case["raw_track_id"],
            "baseline_passage_id": case["baseline_passage_id"],
            "qc_status": case["qc_status"], "qc_recommended_action": case["recommended_action"],
            "qc_proposed_count_delta": case["proposed_count_delta_vs_machine"],
            "baseline_decision_frame": case["baseline_decision_frame"],
            "documentary_status": status, "new_event_candidates": candidates,
            "new_exact_anchor_decisions": decisions, "new_frame_assignments": assignment,
            "physical_resolution": "NOT_AUTOMATICALLY_ADJUDICATED_BY_DOCUMENTARY_JOIN",
        })

    cancel_rows = []
    for case in matrix["cancellations"]:
        _require(case["event_id"] in old_events, "QC cancellation references a foreign baseline event")
        prior = old_events[case["event_id"]]
        candidates = index.candidates(prior.get("evidence", {}))
        keep = old_events.get(case.get("keep_event_id"))
        keep_refs = _refs(keep.get("evidence", {})) if keep else set()
        old_refs = _refs(prior.get("evidence", {}))
        witness_frame = prior.get("activation_frame")
        witness = {key for key in old_refs if key[0] == witness_frame}
        # Timeout activation has no new measurement. Its source witness is the
        # last retained observation, not a fabricated frame at timer expiry.
        witness_basis = "ACTIVATION_FRAME_SOURCE_MEASUREMENT"
        if not witness and old_refs:
            last_observed = max(key[0] for key in old_refs)
            witness = {key for key in old_refs if key[0] == last_observed}
            witness_basis = "LAST_OBSERVED_SOURCE_MEASUREMENT_BEFORE_ACTIVATION"
        for candidate in candidates:
            actual = next(event for event in index.events if event.get("event_id") == candidate["event_id"])
            refs = _refs(actual.get("evidence", {}))
            candidate["retains_old_source_decision_witness"] = bool(witness & refs)
            candidate["shares_qc_canonical_keep_source_measurement"] = bool(keep_refs & refs)
            candidate["same_direction_as_cancelled_baseline"] = actual.get("direction") == prior.get("direction")
            candidate["same_category_as_cancelled_baseline"] = actual.get("category") == prior.get("category")
        strong = [row for row in candidates if row["retains_old_source_decision_witness"]]
        cancel_rows.append({
            "case_id": case["case_id"], "baseline_event_id": case["event_id"],
            "raw_track_id": case["raw_track_id"], "qc_reason": case["reason"],
            "qc_keep_event_id": case.get("keep_event_id"),
            "source_witness_basis": witness_basis,
            "baseline_source_witness_frames": sorted({key[0] for key in witness}),
            "documentary_status": ("SOURCE_WITNESS_STILL_REPRESENTED_CHECK_CANONICAL_UNIT" if strong
                else "OTHER_SOURCE_OVERLAP_ONLY_REQUIRES_EPISODE_REVIEW" if candidates
                else "NO_ACCEPTED_SOURCE_COUNTERPART_CHECK_HELD_OR_REMOVED"),
            "new_event_candidates": candidates,
            "physical_resolution": "REQUIRES_SOURCE_REVIEW_NOT_EVENT_HASH_OR_RAW_ID_COMPARISON",
        })

    discovery_rows = []
    for case in matrix["discovery"]:
        tracks, frames = set(case["raw_track_ids"]), set(case.get("source_frames", []))
        frame_basis = "EXPLICIT_REVIEW_FRAME_LIST" if frames else "RETAINED_GEOMETRY_DIAGNOSTIC_PAIR_FRAMES"
        if not frames:
            frames = {pair[key] for pair in case.get("geometry_pairs", []) for key in ("first_frame", "second_frame")}
        if not frames and case.get("source_scope"):
            scope = case["source_scope"]
            frames = set(range(scope["start_frame"], scope["end_frame"] + 1))
            frame_basis = "RETAINED_SCOPE_RANGE_NOT_CONTINUOUS_VISUAL_REVIEW"
        assignments = [row for (track, frame), rows in index.assignments.items()
                       if track in tracks and frame in frames for row in rows]
        candidates = []
        for event, refs in zip(index.events, index.event_refs):
            local = [key for key in refs if key[1] in tracks and key[0] in frames]
            if local:
                candidates.append(_summary(event) | {"matching_reviewed_source_frames": sorted({key[0] for key in local})})
        units_per_frame = defaultdict(set)
        for row in assignments:
            units_per_frame[row["frame_index"]].add(row.get("physical_unit_id"))
        discovery_rows.append({"case_id": case["case_id"], "raw_track_ids": sorted(tracks),
            "qc_status": case["status"], "qc_action": case["action"],
            "comparison_source_frames": sorted(frames), "comparison_frame_basis": frame_basis,
            "assignment_count_in_reviewed_frames": len(assignments),
            "new_event_candidates": candidates,
            "physical_units_by_reviewed_frame": {str(key): sorted(value) for key, value in units_per_frame.items()},
            "physical_resolution": "POLICY_OR_SOURCE_REVIEW_REQUIRED_NO_AUTOMATIC_MISSED_PLUS_ONE"})

    return {"schema_version": "phase9_p0_qc_source_comparison_v1",
        "claim_type": "DOCUMENTARY_SOURCE_COMPARISON_NOT_PHYSICAL_GROUND_TRUTH_OR_ACCURACY",
        "source_identity": old["source_identity"], "old_branch": old.get("branch"), "new_branch": new.get("branch"),
        "branch_totals_must_not_be_added": True,
        "old_aggregate": old.get("aggregate"), "new_aggregate": new.get("aggregate"),
        "all_121_old_measured_events_required_to_survive": False,
        "reason_not_preservation_invariant": "Measured pairs can be duplicate components of one physical unit.",
        "pending_case_count": len(pending_rows), "cancellation_case_count": len(cancel_rows),
        "discovery_case_count": len(discovery_rows),
        "pending_documentary_status_counts": dict(Counter(row["documentary_status"] for row in pending_rows)),
        "cancellation_documentary_status_counts": dict(Counter(row["documentary_status"] for row in cancel_rows)),
        "pending": pending_rows, "cancellations": cancel_rows, "discovery": discovery_rows}


def write_comparison(report, output):
    output = Path(output)
    _require(not output.exists(), "Comparison output must be a new directory")
    output.mkdir(parents=True)
    (output / "comparison.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for key in ("pending", "cancellations", "discovery"):
        rows = report[key]
        scalar = [{name: (json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (list, dict)) else value)
                   for name, value in row.items()} for row in rows]
        with (output / (key + ".csv")).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(scalar[0]) if scalar else [])
            writer.writeheader()
            writer.writerows(scalar)
    files = [{"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "bytes": path.stat().st_size} for path in sorted(output.iterdir()) if path.is_file()]
    (output / "manifest.json").write_text(json.dumps({"files": files, "manifest_self_excluded": True}, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--qc-root", default="results/phase_9/20261020_QC_BV4_SIANG")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = compare_results(_read(args.old), _read(args.new), args.qc_root)
    write_comparison(report, args.output)
    print(json.dumps({key: report[key] for key in ("pending_case_count", "cancellation_case_count", "discovery_case_count")}))


if __name__ == "__main__":
    main()
