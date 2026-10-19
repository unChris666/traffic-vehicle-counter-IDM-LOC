#!/usr/bin/env python3
"""Verify retained B v3 bytes and accounting without importing the pipeline.

Run from any directory with Python's standard library. Optional --source-run-root
also checks every retained event measurement against the original read-only cache.
This is artifact/software verification, never evidence of physical counting accuracy.
"""
from __future__ import annotations

import argparse
import ast
import base64
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sys

EXECUTION = "results/b_v3/execution/final_20261019T045405_106031Z"
VIDEOS = {f"{day}_{period}" for day in ("weekday", "weekend")
          for period in ("pagi", "siang", "sore", "malam")}
SOURCES = {"notebooks/" + name + ".py" for name in (
    "phase_5_geometry_helpers", "phase_8_annotation_batch", "phase_8_annotation_helpers",
    "phase_8_b_v2_batch", "phase_8_b_v2_annotation", "phase_8_b_v2_counting",
    "phase_8_b_v3_batch", "phase_8_b_v3_annotation", "phase_8_b_v3_counting")}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode()


def passage_key(item):
    return tuple(item[key] for key in ("physical_unit_id", "episode_id", "passage_id"))


class Audit:
    def __init__(self):
        self.check_count = 0
        self.failures = []

    def check(self, condition, message):
        self.check_count += 1
        if not condition:
            self.failures.append(message)


def retained_bytes(root, execution, audit):
    manifest = json.loads((execution / "retained_bytes_manifest.json").read_bytes())
    originals = {}
    for item in manifest["files"]:
        name = item["source_relative_path"]
        path = (root / item["retained_path"]).resolve()
        audit.check(path.is_relative_to(execution), f"retention path containment: {name}")
        stored = path.read_bytes()
        data = gzip.decompress(stored)
        audit.check(len(stored) == item["retained_bytes"] and sha(stored) == item["retained_sha256"],
                    f"compressed bytes: {name}")
        audit.check(len(data) == item["source_bytes"] and sha(data) == item["source_sha256"],
                    f"original bytes: {name}")
        audit.check(name not in originals, f"unique original name: {name}")
        originals[name] = data
    audit.check(len(originals) == 53, "53 exact local artifacts retained")
    retention = json.loads(originals["retention_manifest.json"])
    audit.check({x["path"] for x in retention["artifacts"]} == set(originals) - {"retention_manifest.json"},
                "original retention manifest covers all other artifacts")
    for item in retention["artifacts"]:
        data = originals[item["path"]]
        audit.check(sha(data) == item["sha256"] and len(data) == item["size_bytes"],
                    "original retention manifest: " + item["path"])
    return originals


def check_packets(root, audit):
    results = []
    for folder, current in (("submitted_packet", False), ("submitted_packet_v2", True)):
        packet = root / "results/b_v3/verification" / folder
        report = json.loads((packet / "source_bundle_manifest.json").read_bytes())
        proof = json.loads((packet / "verification.json").read_bytes())
        raw = gzip.decompress((packet / "submitted_notebook.ipynb.gz").read_bytes())
        notebook = json.loads(raw)
        audit.check(sha(raw) == report["submitted_notebook"]["sha256"] == proof["submitted_notebook_sha256"],
                    f"{folder} exact submitted notebook")
        audit.check(len(raw) == report["submitted_notebook"]["bytes"], f"{folder} submitted length")
        metadata = (packet / "kernel-metadata.json").read_bytes()
        audit.check(sha(metadata) == proof["kernel_metadata_sha256"], f"{folder} metadata hash")
        bindings = report["source_files"]
        audit.check(sha(canonical(bindings)) == report["source_bundle_binding_sha256"] == proof["source_bundle_binding_sha256"],
                    f"{folder} source bundle binding")
        source = "".join(notebook["cells"][1]["source"])
        tree = ast.parse(source)
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "B_V3_SOURCE_BUNDLE" for t in node.targets))
        payload = json.loads(ast.literal_eval(assignment.value.args[0]))
        audit.check(set(payload) == set(bindings) and len(payload) == 40, f"{folder} exact 40-file set")
        for name, entry in payload.items():
            data = gzip.decompress(base64.b64decode(entry["gzip_base64"], validate=True))
            audit.check(sha(data) == bindings[name]["sha256"] and len(data) == bindings[name]["bytes"],
                        f"{folder} embedded bytes: {name}")
            if current:
                audit.check(data == (root / name).read_bytes(), f"current packet source: {name}")
        audit.check(all(c.get("execution_count") is None and not c.get("outputs")
                        for c in notebook["cells"] if c["cell_type"] == "code"),
                    f"{folder} submission has no fabricated execution")
        results.append({"packet": folder, "source_bundle_binding_sha256": report["source_bundle_binding_sha256"],
                        "submitted_notebook_sha256": sha(raw), "matches_current_sources": current})
    failure_path = root / "results/b_v3/verification/kaggle_v1_failure"
    failure = json.loads((failure_path / "failure.json").read_bytes())
    log = gzip.decompress((failure_path / "actual_kernel.log.gz").read_bytes())
    audit.check(sha(log) == failure["original_log_sha256"] and len(log) == failure["original_log_bytes"],
                "Kaggle v1 actual failure log exact bytes")
    audit.check(failure["version"] == 1 and failure["status"] == "ERROR"
                and not failure["counting_started"] and not failure["annotation_started"],
                "Kaggle v1 historical failure remains explicit before counting/rendering")
    audit.check(failure["source_bundle_binding_sha256"] == results[0]["source_bundle_binding_sha256"],
                "Kaggle v1 failure bound to historical packet")
    return results


def refs_in_event(event):
    evidence = event["evidence"]
    refs = list(evidence["source_refs"])
    for pair in evidence["crossing_pairs"]:
        refs.extend((pair["first"], pair["second"]))
    for key in ("destination_observed_ref", "cancellation_source_ref"):
        if evidence.get(key):
            refs.append(evidence[key])
    return refs


def verify_video(video_id, row, data, pending, queue, geometry, audit):
    events, cancelled = data["events"], data["cancelled_events"]
    active = {passage_key(e) for e in events}
    decisions = [d for d in data["decisions"] if d["status"] == "pending"]
    keys = {passage_key(d) for d in decisions}
    assignment = {(x["frame_index"], x["track_id"]): x for x in data["frame_assignments"]}
    audit.check(len(active) == len(events), f"{video_id} one active event per unit/episode/passage")
    audit.check(len(keys) == len(decisions) == pending["unique_unit_episode_passages"],
                f"{video_id} canonical unique pending keys")
    audit.check(not active & keys, f"{video_id} pending excluded from accepted")
    audit.check({passage_key(c) for c in pending["cases"]} == keys, f"{video_id} pending groups exact membership")
    audit.check({e["event_id"] for e in events}.isdisjoint(e["event_id"] for e in cancelled),
                f"{video_id} cancelled excluded from active")
    audit.check(all(e["status"] == "cancelled" and not e["accepted_count_event"] for e in cancelled),
                f"{video_id} cancelled status")
    display_ids = [e["display_id"] for e in events]
    audit.check(len(display_ids) == len(set(display_ids)), f"{video_id} unique passage display IDs")
    audit.check({x["event_id"]: x["display_id"] for x in data["display_assignments"]}
                == {x["event_id"]: x["display_id"] for x in events}, f"{video_id} final display assignment matches ledger")
    aggregate = data["aggregate"]
    measured = sum(bool(e["evidence"]["measured_crossing"]) for e in events)
    expected = {"total": len(events), "by_category": dict(Counter(e["category"] for e in events)),
                "by_direction": dict(Counter(e["direction"] for e in events)),
                "by_route": dict(Counter(e["route"] for e in events)),
                "measured_total": measured, "inferred_total": len(events) - measured,
                "pending": len(keys), "cancelled": len(cancelled),
                "vehicle_total": sum(e["role"] == "vehicle" for e in events),
                "pedestrian_total": sum(e["role"] == "pedestrian" for e in events)}
    audit.check(aggregate == expected == row["aggregate"], f"{video_id} independent aggregate reconciliation")
    audit.check(sum(x.get("count_delta", 0) for x in data["passage_log"]) == len(events),
                f"{video_id} log delta reconciliation including cancellation/upgrades")
    audit.check(row["frames"] == data["report"]["frame_count"] and data["report"]["first_frame_index"] == 0
                and data["report"]["last_frame_index"] == row["frames"] - 1,
                f"{video_id} complete frame range")
    audit.check(data["report"]["no_model_inference"] and data["report"]["post_eof_frames_generated"] == 0,
                f"{video_id} no new inference or fabricated tail")
    audit.check(data["source_identity"] == row["source_identity"], f"{video_id} source identity binding")
    groups = Counter(g for case in pending["cases"] for g in case["case_groups"])
    audit.check(dict(groups) == pending["case_group_memberships"] == row["pending_group_memberships"],
                f"{video_id} overlapping group counts reconciled")
    roles = Counter(case["role"] for case in pending["cases"])
    audit.check(roles["unknown_person"] == pending["unknown_person_candidate_keys"],
                f"{video_id} unknown-person keys separate")
    audit.check(roles["vehicle"] + roles["pedestrian"] == pending["vehicle_or_reviewed_pedestrian_pending_keys"],
                f"{video_id} vehicle/positive-pedestrian pending subtotal")
    audit.check(len(queue) == row["unknown_person_role_keys"], f"{video_id} role queue distinct from passage pending")
    refs = {}
    for event in events + cancelled:
        evidence = event["evidence"]
        for ref in refs_in_event(event):
            tag = f"{video_id}/{event['event_id']}/{ref['frame_index']}/{ref['track_id']}"
            bbox, point = ref["raw_bbox"], ref["point"]
            audit.check(point == [(bbox[0] + bbox[2]) / 2, bbox[3]], "raw BC not display union: " + tag)
            audit.check(ref["observed"] and ref["emitted"] and ref["measurement_provenance"] == "retained_phase_8_detection",
                        "observed emitted retained source: " + tag)
            audit.check(0 <= ref["frame_index"] < row["frames"] and isinstance(ref["original_detection_index"], int)
                        and ref["original_detection_index"] >= 0, "valid source index: " + tag)
            own = assignment.get((ref["frame_index"], ref["track_id"]))
            audit.check(own is not None and own["physical_unit_id"] == event["physical_unit_id"]
                        and own["episode_id"] == event["episode_id"], "source measurement belongs to event episode: " + tag)
            audit.check((event["role"] == "vehicle" and ref["class_name"] in {"motorcycle", "car", "truck", "bus"}
                         and ref["role"] == "vehicle") or
                        (event["role"] == "pedestrian" and ref["class_name"] == "person" and ref["role"] == "pedestrian"),
                        "rider/person cannot supply vehicle BC: " + tag)
            refs[(ref["frame_index"], ref["track_id"], ref["original_detection_index"])] = ref
        if event["status"] != "accepted":
            continue
        audit.check(event["accepted_count_event"] and event["role"] in {"vehicle", "pedestrian"},
                    f"{video_id} accepted role")
        display = event["display_id"]
        audit.check(bool(re.fullmatch(r"[PMCT][1-9][0-9]{3}", display)) and
                    display[0] == data["policy"]["display_category_prefixes"][event["category"]] and
                    int(display[1]) % 2 == (0 if event["direction"] == "A_TO_B" else 1),
                    f"{video_id} category/direction display format: {display}")
        audit.check(evidence["anchor"] == ("raw_pedestrian_bbox_bottom_center" if event["role"] == "pedestrian"
                                           else "raw_vehicle_bbox_bottom_center"), f"{video_id} anchor source")
        audit.check(not evidence["measured_crossing"] or bool(evidence["crossing_pairs"]),
                    f"{video_id} measured requires crossing pair")
        for pair in evidence["crossing_pairs"]:
            first, second = pair["first"], pair["second"]
            audit.check(second["frame_index"] == first["frame_index"] + 1,
                        f"{video_id} crossing never spans observation gap")
            audit.check(0 < pair["intersection"]["u"] < 1 and pair["intersection"]["kind"] == "proper",
                        f"{video_id} crossing is within finite segment endpoints")
            a, b = first["point"], second["point"]
            p, q = (geometry["rendered_native_pixels"]["line"][key] for key in ("P1", "P2"))
            d, e, offset = [b[i] - a[i] for i in (0, 1)], [q[i] - p[i] for i in (0, 1)], [p[i] - a[i] for i in (0, 1)]
            cross = lambda x, y: x[0] * y[1] - x[1] * y[0]
            denominator = cross(d, e)
            if denominator:
                t, u = cross(offset, e) / denominator, cross(offset, d) / denominator
                audit.check(0 < t < 1 and 0 < u < 1 and
                            math.isclose(t, pair["intersection"]["t"], rel_tol=1e-9, abs_tol=1e-9) and
                            math.isclose(u, pair["intersection"]["u"], rel_tol=1e-9, abs_tol=1e-9),
                            f"{video_id} independent finite segment intersection arithmetic")
            else:
                audit.check(False, f"{video_id} recorded proper crossing cannot have parallel segments")
            if first["track_id"] != second["track_id"]:
                audit.check(first["association_verified"] and second["association_verified"] and
                            first["association_id"] == second["association_id"] is not None,
                            f"{video_id} raw ID handoff requires local verified association")
        if event["route"] == "ESTIMATED_TIMEOUT":
            audit.check(not evidence["measured_crossing"] and evidence["direction_assumed"]
                        and not evidence["id_change_proven"] and event["activation_frame"]
                        >= evidence["last_observed_origin_frame"] + data["policy"]["timeout_frames"],
                        f"{video_id} timeout clock and inferred semantics")
    return expected, roles, refs


def check_original_cache(cache_root, video_id, source, refs, frames, audit):
    path = cache_root / video_id / "track_records.jsonl.gz"
    audit.check(sha(path.read_bytes()) == source["records_sha256"], f"{video_id} actual raw cache compressed hash")
    found = set()
    frame_count = 0
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            audit.check(record["frame_index"] == frame_count, f"{video_id} original cache sequential frame {frame_count}")
            frame_count += 1
            for track in record["emitted_tracks"]:
                key = (record["frame_index"], track["track_id"], track["original_detection_index"])
                if key not in refs:
                    continue
                ref = refs[key]
                detection = record["raw_detections"][track["original_detection_index"]]
                audit.check(ref["raw_bbox"] == track["raw_bbox"] == detection["bbox_xyxy_pixels"]
                            and ref["class_name"] == track["class_name"] == detection["class_name"]
                            and ref["class_id"] == track["class_id"] == detection["class_id"],
                            f"{video_id} event BC exactly original emitted/raw detector measurement: {key}")
                found.add(key)
    audit.check(frame_count == frames and found == set(refs), f"{video_id} all event measurements found in complete source cache")


def run(root, execution, cache_root=None):
    audit = Audit()
    originals = retained_bytes(root, execution, audit)
    batch = json.loads(originals["batch_report.json"])
    audit.check(batch["all_eight_selected"] and batch["all_eight_completed"] and batch["all_selected_completed"]
                and set(batch["selected_video_ids"]) == VIDEOS and len(batch["videos"]) == 8,
                "all eight actual selected slots completed")
    for key in ("source_files_unchanged_during_execution", "original_inputs_and_reviews_unchanged_during_execution",
                "original_videos_sha_verified"):
        audit.check(batch[key] is True, key)
    for key in ("original_model_caches_modified", "new_detector_tracker_reid_execution", "render_requested",
                "physical_identity_or_counting_accuracy_established"):
        audit.check(batch[key] is False, "local replay: " + key)
    snapshot = json.loads(originals["source_snapshot.json"])
    normalized = {"notebooks/" + Path(name).name: item for name, item in snapshot.items()}
    audit.check(set(normalized) == SOURCES and snapshot == batch["executed_source_files"], "exact nine executed source files")
    for name, item in normalized.items():
        data = gzip.decompress(originals[item["retained_path"]])
        audit.check(data == (root / name).read_bytes() and sha(data) == item["sha256"]
                    and len(data) == item["size_bytes"], "current source equals actual execution: " + name)
    for name, field in (("results/b_v3/config/policy.json", "policy_sha256"),
                        ("results/b_v3/input/review_decisions.json", "reviews_sha256"),
                        ("results/b_v2/config/geometry_manifest.json", "geometry_manifest_sha256")):
        audit.check(sha((root / name).read_bytes()) == batch[field], "current configuration binding: " + name)
    audit.check(originals["review_decisions.json"] == (root / "results/b_v3/input/review_decisions.json").read_bytes(),
                "actual retained review manifest equals current")
    totals, roles, video_results = Counter(), Counter(), []
    for row in batch["videos"]:
        video_id = row["video_id"]
        audit.check(row["status"] == "completed", video_id + " completed")
        data = json.loads(originals[f"{video_id}/counting_result.json"])
        pending = json.loads(originals[f"{video_id}/pending_groups.json"])
        queue = json.loads(originals[f"{video_id}/person_role_review_queue.json"])
        geometry = json.loads(originals[f"{video_id}/geometry.json"])
        audit.check(sha(originals[f"{video_id}/geometry.json"]) == row["source_identity"]["geometry_sha256"],
                    video_id + " actual geometry hash")
        expected, pending_roles, refs = verify_video(video_id, row, data, pending, queue, geometry, audit)
        if cache_root:
            check_original_cache(cache_root, video_id, row["source_identity"], refs, row["frames"], audit)
        totals.update({k: expected[k] for k in ("total", "measured_total", "inferred_total", "pending", "vehicle_total", "pedestrian_total")})
        totals["timeout"] += expected["by_route"].get("ESTIMATED_TIMEOUT", 0)
        totals["frames"] += row["frames"]
        roles.update(pending_roles)
        video_results.append({"video_id": video_id, "frames": row["frames"], "aggregate": expected,
                              "pending_roles": dict(pending_roles), "source_refs_checked": len(refs)})
    audit.check(dict(totals) == {"total": 3500, "measured_total": 895, "inferred_total": 2605,
                                "pending": 2890, "vehicle_total": 3500, "pedestrian_total": 0,
                                "timeout": 2454, "frames": 72590}, "frozen actual final aggregate")
    audit.check(dict(roles) == {"unknown_person": 2427, "pedestrian": 1, "vehicle": 462}, "pending role decomposition")
    audit.check(totals["total"] == batch["operational_total"] and totals["frames"] == batch["frames_processed"]
                and totals["pending"] == batch["pending_unique_unit_episode_passages"], "batch aggregate independent reconciliation")
    packets = check_packets(root, audit)
    return {"claim_type": "ACTUAL_ARTIFACT_INTEGRITY_AND_ACCOUNTING_NOT_PHYSICAL_ACCURACY",
            "status": "PASS" if not audit.failures else "FAIL", "check_count": audit.check_count,
            "failures": audit.failures, "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "checker_sha256": sha(Path(__file__).read_bytes()), "run_id": batch["run_id"],
            "execution_path": execution.relative_to(root).as_posix(), "aggregate": dict(totals),
            "pending_roles": dict(roles), "videos": video_results, "submitted_packets": packets,
            "original_cache_membership_checked": cache_root is not None,
            "source_cache_path": str(cache_root) if cache_root else None,
            "new_counting_detector_tracker_reid_execution": False,
            "physical_vehicle_identity_or_accuracy_established": False,
            "limitations": ["Arithmetic and source measurements do not verify physical passage truth.",
                            "Retained identity/category reviews and operational estimates still require Phase 9 visual audit.",
                            "Kaggle rendering/publication are separate retained execution stages."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--execution", default=EXECUTION)
    parser.add_argument("--source-run-root", type=Path)
    parser.add_argument("--proof-path", type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    result = run(root, (root / args.execution).resolve(),
                 args.source_run_root.resolve() if args.source_run_root else None)
    if args.proof_path:
        args.proof_path.parent.mkdir(parents=True, exist_ok=True)
        args.proof_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "check_count", "failures", "aggregate",
                                          "pending_roles", "original_cache_membership_checked")}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
