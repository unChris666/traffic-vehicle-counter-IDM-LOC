"""Documentary comparison of frozen B v6 and B v7 results; no inference.

Exact retained measurements identify event counterparts. Their presence does
not prove physical identity, correct classification, or counting accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path

from phase_9_v6_qc_review import ledger_checks


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _witnesses(event):
    refs = event.get("evidence", {}).get("source_refs", [])
    _require(bool(refs), "Event needs retained measured source witnesses")
    witnesses = set()
    for ref in refs:
        _require(type(ref.get("frame_index")) is int
                 and type(ref.get("track_id")) is int
                 and type(ref.get("original_detection_index")) is int
                 and len(ref.get("raw_bbox", [])) == 4,
                 "Source witness requires frame, raw track, detection index, and raw bbox")
        witnesses.add(_json([ref["frame_index"], ref["track_id"],
                             ref["original_detection_index"], ref["raw_bbox"]]))
    return frozenset(witnesses)


def _signature(event):
    return _digest(sorted(_witnesses(event)))


def _event_map(result):
    mapping = {}
    for event in result.get("events", []) + result.get("cancelled_events", []):
        event_id = event.get("event_id")
        _require(isinstance(event_id, str) and bool(event_id), "Event ID required")
        signature = "source-witness:" + _signature(event)
        _require(event_id not in mapping or mapping[event_id] == signature,
                 "Event ID refers to conflicting source witnesses")
        mapping[event_id] = signature
    return mapping


def _normalize(value, mapping):
    if isinstance(value, dict):
        return {key: _normalize(item, mapping) for key, item in value.items()
                if key != "namespace"}
    if isinstance(value, list):
        return [_normalize(item, mapping) for item in value]
    if isinstance(value, str):
        return mapping.get(value, value)
    return value


def _event_body(event, mapping):
    # ID/namespace are versioned outputs. Display ID changes are reported
    # separately; they cannot turn the same source event into another passage.
    return _normalize({key: value for key, value in event.items()
                       if key not in ("event_id", "namespace", "display_id")}, mapping)


def _summary(event):
    evidence = event["evidence"]
    times = [ref["frame_index"] for ref in evidence["source_refs"]]
    return {**{key: event.get(key) for key in ("event_id", "display_id", "track_id",
        "physical_unit_id", "episode_id", "passage_id", "role", "category",
        "direction", "route", "activation_frame", "decision_frame")},
        "measured_crossing": bool(evidence.get("measured_crossing")),
        "source_witness_sha256": _signature(event),
        "source_witness_count": len(_witnesses(event)),
        "first_source_frame": min(times), "last_source_frame": max(times)}


def _totals(result):
    events = result.get("events", [])
    estimated = [e for e in events if not e["evidence"].get("measured_crossing")]
    return {"accepted": len(events), "measured": len(events) - len(estimated),
        "estimated": len(estimated),
        "estimated_by_route": dict(sorted(Counter(e["route"] for e in estimated).items())),
        "pending": result["aggregate"]["pending"],
        "invalid": result["aggregate"].get("invalid", 0),
        "declared_aggregate": result["aggregate"]}


def _index(events):
    index = {}
    for i, event in enumerate(events):
        signature = _signature(event)
        _require(signature not in index,
                 "Repeated active source-witness signature; ambiguous documentary comparison")
        index[signature] = i
    return index


def compare_results(old, new):
    """Join exact witnesses first, then only unique overlapping source scopes.

    A category/evidence change on the same measurements is a changed event.
    Multiple possible overlap counterparts are rejected instead of guessed.
    """
    checks = {"baseline": ledger_checks(old), "candidate": ledger_checks(new)}
    source = old.get("source_identity", {})
    for key in ("video_sha256", "records_sha256", "geometry_sha256"):
        value = source.get(key)
        _require(isinstance(value, str) and len(value) == 64
                 and all(c in "0123456789abcdef" for c in value),
                 "Missing valid frozen source identity: " + key)
    _require(source == new.get("source_identity"), "Frozen replay source identities differ")
    previous, candidate = old.get("events", []), new.get("events", [])
    a, b = _index(previous), _index(candidate)
    pairs = [(a[key], b[key], "EXACT_SOURCE_WITNESS_SET") for key in sorted(a.keys() & b.keys())]
    used_a, used_b = {p[0] for p in pairs}, {p[1] for p in pairs}
    remaining_a = set(range(len(previous))) - used_a
    remaining_b = set(range(len(candidate))) - used_b
    overlaps = {(i, j) for i in remaining_a for j in remaining_b
                if _witnesses(previous[i]) & _witnesses(candidate[j])}
    degree_a = Counter(i for i, _ in overlaps)
    degree_b = Counter(j for _, j in overlaps)
    _require(all(value == 1 for value in degree_a.values())
             and all(value == 1 for value in degree_b.values()),
             "Ambiguous source overlap; explicit event-scope review required")
    pairs.extend((i, j, "UNIQUE_OVERLAPPING_EXACT_MEASUREMENTS") for i, j in sorted(overlaps))
    used_a.update(i for i, _ in overlaps)
    used_b.update(j for _, j in overlaps)
    maps = [_event_map(old), _event_map(new)]
    unchanged, changed, display_changes, evidence_transitions = [], [], [], []
    for i, j, method in sorted(pairs):
        first, second = previous[i], candidate[j]
        row = {"old": _summary(first), "new": _summary(second), "join": method,
               "physical_identity_verdict": "NOT_INFERRED_FROM_DOCUMENTARY_JOIN"}
        body_a, body_b = _event_body(first, maps[0]), _event_body(second, maps[1])
        differences = {key: {"old": body_a.get(key), "new": body_b.get(key)}
                       for key in sorted(body_a.keys() | body_b.keys())
                       if body_a.get(key) != body_b.get(key)}
        if differences:
            changed.append({**row, "changed_fields": sorted(differences), "changes": differences})
        else:
            unchanged.append(row)
        if first.get("display_id") != second.get("display_id"):
            display_changes.append(row)
        first_measured = bool(first["evidence"].get("measured_crossing"))
        second_measured = bool(second["evidence"].get("measured_crossing"))
        if first_measured != second_measured:
            evidence_transitions.append({**row, "transition": (
                "UPGRADED_TO_MEASURED" if second_measured else "DOWNGRADED_TO_ESTIMATE")})
    cancelled_by_source = {_signature(e): e for e in new.get("cancelled_events", [])}
    removed = [{"old": _summary(event), "source_evidence": event["evidence"],
                "candidate_cancelled_counterpart": cancelled_by_source.get(_signature(event)),
                "physical_count_verdict": "REMOVAL_IS_NOT_PROOF_OF_ERROR_OR_TRAFFIC_ABSENCE"}
               for i, event in enumerate(previous) if i not in used_a]
    added = [{"new": _summary(event), "source_evidence": event["evidence"],
              "physical_count_verdict": "ADDITION_REQUIRES_SOURCE_REVIEW"}
             for j, event in enumerate(candidate) if j not in used_b]
    pending = []
    for result, mapping in zip((old, new), maps):
        pending.append(Counter(_json(_normalize(row, mapping)) for row in result.get("decisions", [])
                               if row.get("status") == "pending"))
    old_cancelled = {_signature(e) for e in old.get("cancelled_events", [])}
    newly_cancelled = [e for e in new.get("cancelled_events", []) if _signature(e) not in old_cancelled]
    return {"schema_version": "phase9_b_v7_documentary_comparison_v1",
        "claim_type": "EXACT_SOURCE_WITNESS_COMPARISON_NOT_PHYSICAL_GROUND_TRUTH",
        "source_identity": source, "ledger_checks": checks,
        "baseline": _totals(old), "candidate": _totals(new),
        "event_counts": {"unchanged": len(unchanged), "changed": len(changed),
                         "removed": len(removed), "added": len(added)},
        "unchanged": unchanged, "changed": changed, "removed": removed, "added": added,
        "display_id_changes": display_changes, "new_cancellations": newly_cancelled,
        "evidence_level_transitions": evidence_transitions,
        "evidence_transition_counts": dict(sorted(Counter(
            row["transition"] for row in evidence_transitions).items())),
        "pending_semantically_unchanged": pending[0] == pending[1],
        "pending_removed": [json.loads(row) for row in (pending[0] - pending[1]).elements()],
        "pending_added": [json.loads(row) for row in (pending[1] - pending[0]).elements()],
        "frame_assignments_unchanged": old.get("frame_assignments") == new.get("frame_assignments"),
        "component_links_unchanged": old.get("component_links") == new.get("component_links"),
        "category_changed_events": sum("category" in row["changed_fields"] for row in changed),
        "direction_changed_events": sum("direction" in row["changed_fields"] for row in changed),
        "physical_accuracy_established": False,
        "new_model_execution": False}


def _read(path):
    data = Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith(".gz") else data)


def write_comparison(report, output, *, repo_root):
    output, root = Path(output).resolve(), Path(repo_root).resolve()
    _require(output.is_relative_to(root / "results/b_v7")
             and output != root / "results/b_v7" and not output.exists(),
             "Comparison output must be a new directory below results/b_v7")
    output.mkdir(parents=True)
    (output / "comparison.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    fields = ["change", "old_event_id", "new_event_id", "raw_track_id", "category", "direction",
              "route", "measured_crossing", "first_source_frame", "last_source_frame", "changed_fields"]
    with (output / "event_deltas.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for status in ("removed", "added", "changed"):
            for item in report[status]:
                old, new = item.get("old", {}), item.get("new", {})
                ref = new or old
                writer.writerow({"change": status, "old_event_id": old.get("event_id"),
                    "new_event_id": new.get("event_id"), "raw_track_id": ref["track_id"],
                    **{key: ref[key] for key in ("category", "direction", "route", "measured_crossing",
                                                "first_source_frame", "last_source_frame")},
                    "changed_fields": ";".join(item.get("changed_fields", []))})
    rows = [{"path": p.name, "bytes": p.stat().st_size,
             "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(output.iterdir())]
    (output / "retention_manifest.json").write_text(json.dumps({"files": rows,
        "self_excluded": True}, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = compare_results(_read(args.old), _read(args.new))
    report["input_artifacts"] = {name: {"path": str(Path(path).resolve()),
        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
        for name, path in (("baseline", args.old), ("candidate", args.new))}
    write_comparison(report, args.output, repo_root=args.repo_root)
    print(json.dumps({"event_counts": report["event_counts"],
                      "pending_semantically_unchanged": report["pending_semantically_unchanged"]}))


if __name__ == "__main__":
    main()
