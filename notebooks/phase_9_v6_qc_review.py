"""Independent documentary QC for the user's post-P0 invalid/+0 policy.

This tool never runs a model or a counting pipeline. Exact retained source
measurements locate counterparts; they are not newly created physical labels.
Intentional invalid exclusions are reported separately from missing coverage.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

from phase_9_p0_qc_compare import (
    SourceIndex, _refs, _summary, compare_results, expected_case_matrix,
)


def _require(value, message):
    if not value:
        raise ValueError(message)


def _read(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def _invalid_rows(result):
    """The display list and decision ledger may share rows; do not sum them."""
    rows = {}
    for row in result.get("decisions", []) + result.get("invalid_decisions", []):
        if row.get("status") != "invalid":
            continue
        key = (row.get("physical_unit_id"), row.get("episode_id"), row.get("passage_id"))
        _require(all(value is not None for value in key), "Invalid decision needs a passage scope")
        if key in rows:
            _require(rows[key] == row, "Conflicting duplicate invalid decision scope")
        rows[key] = row
    return list(rows.values())


def ledger_checks(result):
    """Software invariants only; these checks cannot establish physical truth."""
    events = result.get("events", [])
    aggregate = result.get("aggregate", {})
    ids = [event.get("event_id") for event in events]
    _require(len(set(ids)) == len(ids), "Repeated active event IDs")
    passages = [(event.get("physical_unit_id"), event.get("passage_id")) for event in events]
    _require(len(set(passages)) == len(passages), "Repeated active unit/passage key")
    for event in events:
        _require(event.get("status") == "accepted" and event.get("accepted_count_event") is True,
                 "Only accepted events may contribute to aggregates")
        evidence = event.get("evidence", {})
        for ref in evidence.get("source_refs", []):
            box, point = ref.get("raw_bbox"), ref.get("point")
            if box is not None and point is not None:
                _require(len(box) == 4 and len(point) == 2
                    and abs(point[0] - (box[0] + box[2]) / 2) < 1e-8
                    and abs(point[1] - box[3]) < 1e-8, "Crossing anchor differs from raw measured BC")
    _require(aggregate.get("total") == len(events), "Total differs from active ledger")
    for field, name in (("category", "by_category"), ("direction", "by_direction"), ("route", "by_route")):
        actual = Counter(event[field] for event in events)
        retained = {key: value for key, value in aggregate.get(name, {}).items() if value}
        _require(dict(actual) == retained, "Aggregate differs: " + name)
    measured = sum(bool(event.get("evidence", {}).get("measured_crossing")) for event in events)
    _require(aggregate.get("measured_total") == measured
        and aggregate.get("inferred_total") == len(events) - measured, "Evidence subtotal differs")
    pending = sum(row.get("status") == "pending" for row in result.get("decisions", []))
    _require(aggregate.get("pending") == pending, "Pending includes non-pending decisions")
    invalid = _invalid_rows(result)
    invalid_scopes = {(row["physical_unit_id"], row["passage_id"]) for row in invalid}
    _require(not (set(passages) & invalid_scopes), "A passage is both invalid and accepted")
    if "invalid" in aggregate:
        _require(aggregate["invalid"] == len(invalid), "Invalid aggregate differs from unique passage scopes")
    invalid_event_ids = {row.get("cancelled_candidate_event_id", row.get("source_event_id")) for row in invalid}
    _require(not (set(ids) & invalid_event_ids), "An invalid source event is still accepted")
    for row in invalid:
        _require(row.get("count_delta") == 0 and row.get("accepted_count_event") is False,
                 "Invalid decisions must contribute +0")
        _require(row.get("invalid_reason") == "INVALID_AMBIGUOUS_UNIT",
                 "Invalid decision needs the explicit user-approved ambiguity reason")
        _require(bool(_refs(row)), "Invalid exclusion needs measured source evidence")
    return {"status": "PASS_SOFTWARE_LEDGER_ONLY", "active_events": len(events),
            "pending": pending, "invalid_passage_scopes": len(invalid),
            "physical_accuracy_established": False}


def _decision_matches(reference, rows):
    keys = _refs(reference)
    return [deepcopy(row) for row in rows if keys & _refs(row)]


def transition_rows(old, new):
    """Classify old active source witnesses without labelling disappearance a fix."""
    index = SourceIndex(new)
    invalid = _invalid_rows(new)
    decisions = new.get("decisions", [])
    result = []
    for event in old.get("events", []):
        refs = event.get("evidence", {})
        counterparts = index.candidates(refs)
        excluded = _decision_matches(refs, invalid)
        pending = [row for row in _decision_matches(refs, decisions) if row.get("status") == "pending"]
        status = ("ACCEPTED_SOURCE_COUNTERPART_PRESENT" if counterparts
                  else "INTENTIONALLY_EXCLUDED_BY_AMBIGUITY_POLICY" if excluded
                  else "PENDING_SOURCE_COUNTERPART_PRESENT" if pending
                  else "NO_DOCUMENTARY_COUNTERPART_REQUIRES_COVERAGE_REVIEW")
        result.append({"old_event": _summary(event), "documentary_status": status,
                       "new_event_candidates": counterparts, "invalid_decisions": excluded,
                       "pending_decisions": pending,
                       "physical_count_verdict": "NOT_INFERRED_FROM_SOURCE_JOIN"})
    return result


def reference_controls(qc_baseline, new, original_comparison):
    """Known QC source scopes are fixtures, never global raw-ID runtime rules."""
    old_events = {event["event_id"]: event for event in qc_baseline["events"]}
    index = SourceIndex(new)
    invalid = _invalid_rows(new)
    controls = []
    for case in original_comparison["cancellations"]:
        source = old_events[case["baseline_event_id"]]
        keep = old_events.get(case.get("qc_keep_event_id"))
        reference = [source, keep] if keep is not None else source
        candidate_ids = {row["event_id"] for row in index.candidates(reference)}
        excluded = _decision_matches(reference, invalid)
        bad_witness = [row for row in case["new_event_candidates"]
            if row.get("retains_old_source_decision_witness")
            and not row.get("shares_qc_canonical_keep_source_measurement")]
        if keep is not None and len(candidate_ids) > 1:
            status = "BLOCKER_REFERENCE_ONE_PASSAGE_HAS_MULTIPLE_ACCEPTED_COUNTERPARTS"
        elif bad_witness:
            status = "UNRESOLVED_WRONG_REPRESENTATION_SOURCE_REVIEW_REQUIRED"
        elif keep is not None and not candidate_ids and excluded:
            status = "INTENTIONAL_AMBIGUITY_EXCLUSION_NOT_RECOVERED_TRAFFIC"
        elif keep is not None and not candidate_ids:
            status = "UNRESOLVED_REFERENCE_PASSAGE_COVERAGE"
        else:
            status = "NO_KNOWN_BAD_SOURCE_WITNESS_ACCEPTED"
        controls.append({"case_id": case["case_id"], "raw_track_id": case["raw_track_id"],
                         "qc_reason": case["qc_reason"], "status": status,
                         "accepted_source_counterpart_ids": sorted(candidate_ids),
                         "invalid_passage_scopes": len(excluded),
                         "source_reference_is_bounded_not_global_raw_id_label": True})
    return controls


def review_results(old, new, qc_root, *, qc_baseline=None):
    """Return policy-aware QC for a new replay, preserving the full 68+16+10 set."""
    old_checks, new_checks = ledger_checks(old), ledger_checks(new)
    for field in ("video_sha256", "records_sha256", "geometry_sha256"):
        _require(old.get("source_identity", {}).get(field)
            == new.get("source_identity", {}).get(field)
            and new.get("source_identity", {}).get(field), "Foreign replay input: " + field)
    qc_root = Path(qc_root).resolve()
    expected_case_matrix(qc_root)
    if qc_baseline is None:
        repo = qc_root.parents[2]
        qc_baseline = _read(repo / "results/b_v4/execution/pilot_machine_final/weekday_siang/counting_result.json.gz")
    # The older comparator permits sparse category aggregates. Strip only zero
    # entries from a private view if BUS-inclusive output emits explicit zeros.
    comparison_view = deepcopy(new)
    for name in ("by_category", "by_direction", "by_route"):
        comparison_view["aggregate"][name] = {key: value for key, value in new["aggregate"][name].items() if value}
    original = compare_results(qc_baseline, comparison_view, qc_root)
    invalid = _invalid_rows(new)
    prior_pending = {row["passage_id"]: row for row in qc_baseline["decisions"] if row["status"] == "pending"}
    for case in original["pending"]:
        source = prior_pending[case["baseline_passage_id"]].get("source_ref", {})
        case["new_invalid_source_counterparts"] = _decision_matches(source, invalid)
        case["invalid_is_intentional_exclusion_not_proven_absence"] = True
    transition = transition_rows(old, new)
    controls = reference_controls(qc_baseline, new, original)
    assignments = [row for row in new.get("frame_assignments", [])
                   if row.get("frame_index") == 7615 and row.get("track_id") in (4480, 4552)]
    separated = (len(assignments) == 2 and len({row["physical_unit_id"] for row in assignments}) == 2)
    blockers = [row for row in controls if row["status"].startswith("BLOCKER")]
    unresolved = [row for row in controls if row["status"].startswith("UNRESOLVED")]
    return {"schema_version": "phase9_v6_policy_qc_review_v1",
            "claim_type": "SOURCE_SCOPED_QC_NOT_FORMAL_GROUND_TRUTH_OR_ACCURACY",
            "old_ledger_checks": old_checks, "new_ledger_checks": new_checks,
            "old_aggregate": old["aggregate"], "new_aggregate": new["aggregate"],
            "policy_change": "AMBIGUOUS_UNIT_MAY_BE_INVALID_PLUS_ZERO_WITH_EXCLUSION_COVERAGE",
            "qc_inventory": {"pending": 68, "cancellations": 16, "discovery": 10},
            "original_qc_comparison": original, "old_active_transition_rows": transition,
            "old_active_transition_status_counts": dict(Counter(row["documentary_status"] for row in transition)),
            "reference_controls": controls, "reference_control_status_counts": dict(Counter(row["status"] for row in controls)),
            "source_coexistence_control_4552_4480": {"source_frame": 7615, "separated": separated,
                                                     "assignments": assignments},
            "known_reference_duplicate_blockers": len(blockers),
            "known_reference_controls_requiring_review": len(unresolved),
            "readiness": "BLOCKED_BY_REFERENCE_DUPLICATE" if blockers else "REQUIRES_SCOPED_PHYSICAL_AND_EXCLUSION_REVIEW",
            "full_production_or_all_video_acceptance": False,
            "numeric_accuracy_or_zero_mistakes_established": False,
            "taxonomy_mapping_decision_is_closed_but_subtype_recognition_not_fabricated": True}


def write_review(report, output):
    output = Path(output)
    _require(not output.exists(), "QC output must be a new directory")
    output.mkdir(parents=True)
    path = output / "review.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    (output / "manifest.json").write_text(json.dumps({"files": [{"path": path.name,
        "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}],
        "self_excluded": True}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--qc-root", default="results/phase_9/20261020_QC_BV4_SIANG")
    parser.add_argument("--qc-baseline")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = review_results(_read(args.old), _read(args.new), args.qc_root,
        qc_baseline=_read(args.qc_baseline) if args.qc_baseline else None)
    write_review(report, args.output)
    print(json.dumps({key: report[key] for key in (
        "new_aggregate", "known_reference_duplicate_blockers", "known_reference_controls_requiring_review", "readiness")}))
