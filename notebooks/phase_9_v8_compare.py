"""Reconcile P1 reviewed decisions with the immutable B v7 machine baseline."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path

from phase_9_v7_compare import compare_results as compare_events


def _require(value, message):
    if not value:
        raise ValueError(message)


def _scope(row):
    return tuple(row.get(k) for k in ("track_id", "physical_unit_id", "episode_id", "passage_id"))


def _witness(ref):
    return (ref.get("frame_index"), ref.get("track_id"), ref.get("original_detection_index"),
            tuple(ref.get("raw_bbox", [])))


def _review_ids(value):
    if isinstance(value, dict):
        found = {value["review_id"]} if value.get("review_id") else set()
        return found | set().union(*(_review_ids(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_review_ids(v) for v in value)) if value else set()
    return set()


def reconcile_pending(before, after, inventory):
    pending = {_scope(d): d for d in before["decisions"] if d["status"] == "pending"}
    cases = inventory["cases"]
    _require(len(cases) == len(pending)
        and {_scope(c["baseline_candidate_scope"]) for c in cases} == set(pending),
        "Inventory must cover every baseline pending candidate exactly once")
    closures = {_scope(a["baseline_candidate_scope"]): a
                for a in after.get("v8_pending_finalization_audit", [])}
    _require(len(closures) == len(after.get("v8_pending_finalization_audit", [])),
        "Conflicting reviewed pending closures")
    assignments = {(a["frame_index"], a["track_id"]): a
                   for a in after.get("frame_assignments", [])}
    rows = []
    for case in cases:
        key = _scope(case["baseline_candidate_scope"])
        original, ref = pending[key], case["baseline_source_ref"]
        _require(ref == original["source_ref"], "Inventory witness differs from baseline")
        row = {"case_id": case["case_id"], "baseline_candidate_scope": case["baseline_candidate_scope"],
            "raw_track_id": ref["track_id"], "source_frame": ref["frame_index"],
            "baseline_source_ref": ref, "previous_status": "pending",
            "previous_reasons": original.get("reasons", []),
            "missing_evidence_and_next_action": case.get("missing_evidence_and_next_action"),
            "physical_count_is_not_inferred_from_status_total": True}
        if key in closures:
            audit = closures[key]
            _require(_witness(audit["baseline_source_ref"]) == _witness(ref),
                "Closure refers to another measured source sample")
            row.update(final_status=audit["final_status"], disposition="REVIEWED_COMPONENT_PLUS_ZERO",
                reason=audit["reason"], count_contribution=0, decision_origin=audit["decision_origin"],
                adjudication_id=audit["adjudication_id"], final_decision_frame=audit["decision_frame"],
                event_ids=[], proof_artifacts=audit["review"]["proof_artifacts"])
        else:
            retained = [d for d in after["decisions"] if d["status"] == "pending"
                and _scope(d) == key and _witness(d.get("source_ref", {})) == _witness(ref)]
            assignment = assignments.get((ref["frame_index"], ref["track_id"]), {})
            support_ids = _review_ids(assignment)
            accepted = ([e for e in after["events"]
                if e.get("physical_unit_id") == assignment.get("physical_unit_id")
                and e.get("episode_id") == assignment.get("episode_id")
                and e.get("role") == assignment.get("role")
                and support_ids & _review_ids(e.get("evidence", {}))]
                if assignment.get("physical_unit_id") and support_ids else [])
            _require(not (retained and accepted), "Same baseline candidate remains pending and accepted")
            if retained:
                row.update(final_status="pending", disposition="PENDING_RETAINED_REQUIRED_EVIDENCE_MISSING",
                    reason=";".join(retained[0].get("reasons", [])), count_contribution=0,
                    decision_origin="MACHINE_PENDING_NOT_OVERRIDDEN", event_ids=[])
            elif len(accepted) == 1:
                event = accepted[0]
                row.update(final_status="accepted", disposition="SOURCE_REVIEWED_ELIGIBLE_PASSAGE_REPLAY",
                    reason="POSITIVE_ROLE_AND_UNCHANGED_GEOMETRY_ENGINE",
                    count_contribution=1, decision_origin="SOURCE_REVIEW_ASSISTED_REPLAY",
                    event_ids=[event["event_id"]], evidence_type="MEASURED_RAW_BC" if
                        event["evidence"]["measured_crossing"] else "INFERRED",
                    review_ids=sorted(support_ids & _review_ids(event["evidence"])),
                    mapping_basis="EXACT_SOURCE_SAMPLE_ASSIGNMENT_TO_REVIEWED_UNIT_EPISODE_WITH_SHARED_REVIEW",
                    mapping_is_not_global_raw_id_alias=True)
            else:
                row.update(final_status="unresolved_reconciliation", disposition="EXPLICIT_CASE_REVIEW_REQUIRED",
                    reason="NO_UNIQUE_REVIEWED_COUNTERPART", count_contribution=0,
                    decision_origin="NO_AUTOMATIC_DISPOSITION", event_ids=[e["event_id"] for e in accepted])
        rows.append(row)
    matched_pending = {_scope(row["baseline_candidate_scope"]) for row in rows if row["final_status"] == "pending"}
    new_pending = [d for d in after["decisions"] if d["status"] == "pending" and _scope(d) not in matched_pending]
    return {"baseline_cases": len(rows), "rows": rows,
        "by_disposition": dict(sorted(Counter(r["disposition"] for r in rows).items())),
        "by_final_status": dict(sorted(Counter(r["final_status"] for r in rows).items())),
        "unmatched_new_pending": new_pending, "candidate_pending_total": after["aggregate"]["pending"],
        "reviewed_component_closures_are_recovered_vehicles": False}


def compare_results(before, after, inventory):
    _require(after.get("branch") == "review_assisted", "P1 comparison must retain reviewed branch identity")
    comparison = compare_events(before, after)
    comparison.update(schema_version="phase9_b_v8_p1_comparison_v1",
        baseline_branch="machine", candidate_branch="review_assisted",
        pending_reconciliation=reconcile_pending(before, after, inventory),
        automatic_model_improvement_established=False,
        branches_may_be_added_together=False)
    return comparison


def read(path):
    data = Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith(".gz") else data)


def write_report(report, output, root):
    output, root = Path(output).resolve(), Path(root).resolve()
    _require(output.is_relative_to(root / "results/b_v8") and not output.exists(),
        "Comparison output must be new and isolated below results/b_v8")
    output.mkdir(parents=True)
    (output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    fields = ["case_id", "raw_track_id", "source_frame", "previous_status", "final_status",
        "disposition", "reason", "count_contribution", "decision_origin", "event_ids"]
    with (output / "pending_dispositions.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for row in report["pending_reconciliation"]["rows"]:
            writer.writerow({key: ";".join(row[key]) if key == "event_ids" else row.get(key)
                             for key in fields})
    fields = ["change", "raw_track_id", "old_event_id", "new_event_id", "changed_fields"]
    with (output / "event_deltas.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for kind in ("changed", "removed", "added", "display_id_changes"):
            for row in report[kind]:
                old, new = row.get("old", {}), row.get("new", {})
                writer.writerow({"change": kind, "raw_track_id": (new or old)["track_id"],
                    "old_event_id": old.get("event_id"), "new_event_id": new.get("event_id"),
                    "changed_fields": ";".join(row.get("changed_fields", []))})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", required=True); parser.add_argument("--new", required=True)
    parser.add_argument("--inventory", default="results/b_v8/pending_review/pending_inventory.json")
    parser.add_argument("--repo-root", default="."); parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = compare_results(read(args.old), read(args.new), read(args.inventory))
    report["input_artifacts"] = {key: {"path": str(Path(path).resolve()),
        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
        for key, path in (("baseline", args.old), ("candidate", args.new), ("inventory", args.inventory))}
    write_report(report, args.output, args.repo_root)
    print(json.dumps({"events": report["event_counts"],
        "pending_dispositions": report["pending_reconciliation"]["by_final_status"]}))


if __name__ == "__main__":
    main()
