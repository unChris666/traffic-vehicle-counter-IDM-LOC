#!/usr/bin/env python3
"""Read retained B v2 evidence; never run models, replay, tests, media or APIs.

With --capture, write an additive final manifest and this checker report only.
Run after publication with --require-published to require both remote stages.
"""
from __future__ import annotations

import argparse
import ast
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys


BASE_COMMIT = "06b7d287eeb8eb62c5761b2da2f87c155337c0f1"
EXECUTED_COMMIT = "24599e7cc2024750052e810ff470b7dc141fca9f"
TEMPLATE_SHA = "13f774f029c4d5e724d24ffb5fb6767b8cd62d96d3b1431e76bc0b849f9a064f"
BUNDLE_SHA = "d8ca2ed2dc9e3c59f4921a4c976348d4fdf11bbb093b1853a8173cc2c52b8e08"
PREFIX = "results/b_v2"
LOCAL = PREFIX + "/execution/local_20261018T030911_956653Z"
FINAL_MANIFEST = PREFIX + "/final_retention_manifest.json"
FINAL_VALIDATION = PREFIX + "/verification/final_validation.json"
EXCLUDED = {FINAL_MANIFEST, FINAL_VALIDATION}
VIDEO_IDS = {day + "_" + period for day in ("weekday", "weekend")
             for period in ("pagi", "siang", "sore", "malam")}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode()


class Checker:
    def __init__(self, root):
        self.root = root.resolve()
        self.checks = []
        self.facts = {}
        self.stages = {}

    def check(self, name, condition, detail=None):
        entry = {"name": name, "passed": bool(condition)}
        if detail is not None:
            entry["detail"] = detail
        self.checks.append(entry)

    def path(self, relative):
        path = self.root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("Unsafe retained path: " + str(relative))
        return path

    def raw(self, relative):
        return self.path(relative).read_bytes()

    def read(self, relative):
        data = self.raw(relative)
        return json.loads(gzip.decompress(data) if str(relative).endswith(".gz") else data)

    def git_bytes(self, commit, path):
        return subprocess.check_output(["git", "show", f"{commit}:{path}"],
                                       cwd=self.root, stderr=subprocess.PIPE)

    def section(self, name, function):
        try:
            function()
        except Exception as error:
            self.check(name + ":readable_complete_evidence", False,
                       type(error).__name__ + ": " + str(error))

    def geometry(self):
        manifest = self.read(PREFIX + "/config/geometry_manifest.json")
        template = self.read(manifest["template_path"])
        self.check("user_upload_exact_sha", digest(self.raw(manifest["template_path"]))
                   == manifest["template_sha256"] == TEMPLATE_SHA)
        review = template["videos"][0]
        self.check("original_export_preserved_not_rewritten", template["counting_policy_changed"] is False
                   and review["pipeline_approval"] is False and review["counting_execution_allowed"] is False)
        self.check("eight_unique_geometry_bindings", {x["video_id"] for x in manifest["videos"]}
                   == VIDEO_IDS and len(manifest["videos"]) == 8)
        self.check("shared_template_authorized", manifest["shared_template_application_user_authorized"] is True)
        self.geometries = {entry["video_id"]: entry for entry in manifest["videos"]}
        for video_id, entry in self.geometries.items():
            geometry = self.read(entry["geometry_path"])
            self.check(video_id + ":geometry_hash_source", digest(self.raw(entry["geometry_path"]))
                       == entry["geometry_sha256"] and geometry["source_video"]["sha256"] == entry["video_sha256"])
            self.check(video_id + ":native_points_no_rescale", entry["width"] == 640 and entry["height"] == 480
                       and geometry["rendered_native_pixels"] == review["geometry_native"]
                       and geometry["normalized"] == review["geometry_normalized"])
            self.check(video_id + ":finite_margin_25_50", entry["margin_half_width_px"] == 25
                       and geometry["line_margin_half_width_px"] == 25
                       and geometry["line_margin"] == review["line_margin"]
                       and geometry["line_margin"]["full_width_px"] == 50
                       and geometry["line_margin"]["cap"] == "flat"
                       and geometry["line_margin"]["extent"] == "finite_segment_only")
            self.check(video_id + ":template_anchor_direction", geometry["user_template"]["sha256"] == TEMPLATE_SHA
                       and geometry["selected_anchor"] == "bottom_center"
                       and geometry["anchor_source"] == "raw_detector_linked_emitted_vehicle_bbox"
                       and geometry["confirmed_direction_metadata"] == review["direction_metadata"])
        self.policy = self.read(PREFIX + "/config/policy.json")
        self.check("policy_matches_user_clock_margin", self.policy["line_margin_half_width_px"] == 25
                   and self.policy["timeout_frames"] == 60
                   and self.policy["timeout_clock"] == "last_observed_origin"
                   and self.policy["user_timer_clarification"] == "Sejak terakhir terlihat di polygon asal"
                   and self.policy["category_policy"] == "band_majority_ties_pending")

    def history(self):
        mapping = self.read(PREFIX + "/baseline/context_retention_mapping.json")
        self.check("baseline_commit_and_two_context_archives", mapping["source_commit"] == BASE_COMMIT
                   and {x["original_path"] for x in mapping["archives"]} == {"AGENTS.md", "docs/COUNTING_LOGIC.md"})
        for entry in mapping["archives"]:
            archive = self.raw(entry["archive_path"])
            original = gzip.decompress(archive)
            self.check("baseline:" + entry["original_path"], digest(archive) == entry["archive_sha256"]
                       and len(archive) == entry["archive_size_bytes"]
                       and digest(original) == entry["original_sha256"]
                       and len(original) == entry["original_size_bytes"]
                       and original == self.git_bytes(BASE_COMMIT, entry["original_path"]))
        names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE_COMMIT, "notebooks"],
                                        cwd=self.root, text=True).splitlines()
        frozen = [name for name in names if name.endswith(".py")]
        self.check("all_historical_python_sources_unchanged", bool(frozen) and all(
            self.raw(name) == self.git_bytes(BASE_COMMIT, name) for name in frozen), len(frozen))

    def exact_retention(self):
        entries = self.read(LOCAL + "/retained_bytes_manifest.json")["artifacts"]
        self.check("actual_local_25_exact_retained_artifacts", len(entries) == 25)
        self.originals = {}
        for entry in entries:
            raw = self.raw(entry["retained_path"])
            original = gzip.decompress(raw) if entry["encoding"] == "gzip_of_exact_original_bytes" else raw
            self.originals[entry["original_relative_path"]] = original
            self.check("retained:" + entry["original_relative_path"], digest(raw) == entry["retained_sha256"]
                       and digest(original) == entry["original_sha256"] and len(original) == entry["original_size_bytes"])
        for entry in json.loads(self.originals["retention_manifest.json"])["artifacts"]:
            raw = self.originals[entry["path"]]
            self.check("run_retention:" + entry["path"], digest(raw) == entry["sha256"]
                       and len(raw) == entry["size_bytes"])
        snapshot = json.loads(self.originals["source_snapshot.json"])
        self.check("six_executed_source_snapshots", len(snapshot) == 6)
        for old_absolute, entry in snapshot.items():
            relative = "notebooks/" + Path(old_absolute).name
            original = gzip.decompress(self.originals[entry["retained_path"]])
            self.check("executed_source:" + relative, digest(original) == entry["sha256"]
                       and len(original) == entry["size_bytes"] and original == self.raw(relative)
                       and original == self.git_bytes(EXECUTED_COMMIT, relative))
        self.batch = json.loads(self.originals["batch_report.json"])

    def ledger(self):
        batch = self.batch
        self.check("batch_all_eight_no_model_execution", batch["all_eight_selected"] is True
                   and batch["all_eight_completed"] is True and batch["all_selected_completed"] is True
                   and batch["new_detector_tracker_reid_execution"] is False
                   and batch["original_model_caches_modified"] is False
                   and batch["physical_identity_or_counting_accuracy_established"] is False
                   and batch["render_requested"] is False)
        self.check("batch_control_hashes", batch["policy_sha256"] == digest(self.raw(PREFIX + "/config/policy.json"))
                   and batch["geometry_manifest_sha256"] == digest(self.raw(PREFIX + "/config/geometry_manifest.json")))
        summary = self.read(PREFIX + "/execution/local_replay_summary.json")
        summary_rows = {row["video_id"]: row for row in summary["per_video"]}
        rows = {row["video_id"]: row for row in batch["videos"]}
        self.check("batch_video_ids", set(rows) == set(summary_rows) == VIDEO_IDS)
        total, measured_total, pending_total, pending_unique_total, frames_total = 0, 0, 0, 0, 0
        repeated_pending = []
        all_routes, all_categories = Counter(), Counter()
        self.results = {}
        for video_id, row in rows.items():
            result = json.loads(self.originals[video_id + "/counting_result.json"])
            self.results[video_id] = result
            events, cancelled = result["events"], result["cancelled_events"]
            identity = result["source_identity"]
            entry = self.geometries[video_id]
            self.check(video_id + ":source_identity_and_frame_scope", identity == row["source_identity"]
                       == result["report"]["source_identity"]
                       and identity["video_sha256"] == entry["video_sha256"]
                       and identity["geometry_sha256"] == entry["geometry_sha256"]
                       and result["report"]["first_frame_index"] == 0
                       and result["report"]["last_frame_index"] == row["frames"] - 1
                       and result["report"]["frame_count"] == row["frames"]
                       and result["report"]["post_eof_frames_generated"] == 0
                       and result["report"]["no_model_inference"] is True)
            self.check(video_id + ":policy_identity", result["policy"] == self.policy
                       and result["report"]["policy"] == self.policy)
            self.check(video_id + ":copied_geometry_exact", self.originals[video_id + "/geometry.json"]
                       == self.raw(entry["geometry_path"]))
            ids = [event["event_id"] for event in events]
            self.check(video_id + ":unique_active_events_and_passages", len(ids) == len(set(ids))
                       and len({(event["physical_unit_id"], event["passage_id"]) for event in events}) == len(events))
            event_flags, raw_refs = True, True
            for event in events:
                evidence = event["evidence"]
                event_flags &= (event["status"] == "accepted" and event["accepted_count_event"] is True
                    and event["source_identity"] == identity and event["category"] in ("motorcycle", "car", "truck")
                    and event["direction"] in ("A_TO_B", "B_TO_A")
                    and event["route"] in ("LINE_MARGIN", "OCCLUSION_DIFF_POLYGON", "ESTIMATED_TIMEOUT")
                    and 0 <= event["activation_frame"] <= event["decision_frame"] < row["frames"]
                    and evidence["anchor"] == "raw_vehicle_bbox_bottom_center"
                    and not evidence["identity_conflicts"] and not evidence["raw_track_changes"]
                    and evidence["id_change_proven"] is False
                    and evidence["finite_segment_crossing_unobserved"] == (not evidence["measured_crossing"]))
                if evidence["measured_crossing"]:
                    event_flags &= event["route"] == "LINE_MARGIN" and bool(evidence["crossing_pairs"])
                if event["route"] == "ESTIMATED_TIMEOUT":
                    event_flags &= (evidence["measured_crossing"] is False and evidence["direction_assumed"] is True
                        and evidence["timeout_frames"] == 60 and evidence["destination_observed_ref"] is None
                        and event["activation_frame"] >= evidence["last_observed_origin_frame"] + 60)
                if event["route"] == "OCCLUSION_DIFF_POLYGON":
                    event_flags &= (evidence["measured_crossing"] is False and evidence["band_observed"] is False
                        and bool(evidence["gaps"]) and evidence["destination_polygon"] in ("A", "B")
                        and evidence["destination_polygon"] != evidence["origin_polygon"])
                for ref in evidence["source_refs"]:
                    box = ref["raw_bbox"]
                    raw_refs &= (ref["observed"] is True and ref["emitted"] is True
                        and ref["point"] == [(box[0] + box[2]) / 2, box[3]]
                        and 0 <= ref["frame_index"] < row["frames"]
                        and 0 <= box[0] < box[2] <= identity["width"]
                        and 0 <= box[1] < box[3] <= identity["height"])
            self.check(video_id + ":event_routes_inference_flags", event_flags)
            self.check(video_id + ":raw_vehicle_BC_references", raw_refs)
            active, deltas, transitions = set(), Counter(), True
            for log in result["passage_log"]:
                delta, event_id = log["count_delta"], log["event_id"]
                transitions &= 0 <= log["frame_index"] < row["frames"]
                if log["status"] == "accepted":
                    transitions &= delta == 1 and event_id not in active
                    active.add(event_id)
                elif log["status"] == "upgraded":
                    transitions &= delta == 0 and event_id in active
                elif log["status"] == "cancelled":
                    transitions &= delta == -1 and event_id in active
                    active.discard(event_id)
                else:
                    transitions &= delta == 0
                deltas[event_id] += delta
            self.check(video_id + ":log_plus1_upgrade0_cancel_minus1_reconcile", transitions and active == set(ids)
                       and sum(deltas.values()) == len(events)
                       and all(delta == (1 if event_id in active else 0) for event_id, delta in deltas.items()))
            self.check(video_id + ":cancelled_excluded", all(event["status"] == "cancelled"
                       and event["accepted_count_event"] is False and event["event_id"] not in active for event in cancelled))
            pending = [decision for decision in result["decisions"] if decision["status"] == "pending"]
            pending_keys = defaultdict(list)
            for decision in pending:
                pending_keys[(decision["physical_unit_id"], decision["passage_id"])].append(decision)
            self.check(video_id + ":pending_reason_rows_well_formed", all(x["reasons"]
                       and len(x["reasons"]) == len(set(x["reasons"])) for x in pending))
            for (unit, passage), decisions in pending_keys.items():
                if len(decisions) > 1:
                    repeated_pending.append({"video_id": video_id, "physical_unit_id": unit,
                        "passage_id": passage, "pending_frames": [x["frame_index"] for x in decisions]})
            open_diagnostics = result["open_passage_diagnostics"]
            self.check(video_id + ":open_presence_EOF_diagnostics_retained", len(open_diagnostics)
                       == result["report"]["observed_units"] and dict(Counter(x["disposition"] for x in open_diagnostics))
                       == result["report"]["open_passage_diagnostic_counts"])
            measured = sum(event["evidence"]["measured_crossing"] for event in events)
            recomputed = {"total": len(events), "by_category": dict(Counter(event["category"] for event in events)),
                "by_direction": dict(Counter(event["direction"] for event in events)),
                "by_route": dict(Counter(event["route"] for event in events)), "measured_total": measured,
                "inferred_total": len(events) - measured, "pending": len(pending), "cancelled": len(cancelled)}
            self.check(video_id + ":recomputed_aggregates", recomputed == result["aggregate"]
                       == row["aggregate"] == summary_rows[video_id]["aggregate"])
            total += len(events); measured_total += measured; pending_total += len(pending)
            pending_unique_total += len(pending_keys); frames_total += row["frames"]
            all_routes.update(recomputed["by_route"]); all_categories.update(recomputed["by_category"])
        self.check("actual_summary_recomputed_72590_frames_3717_events", frames_total == batch["frames_processed"]
                   == summary["frames_processed"] == 72590 and total == batch["operational_total"]
                   == summary["operational_total"] == 3717 and measured_total == summary["measured_total"] == 898
                   and total - measured_total == summary["inferred_total"] == 2819
                   and all_routes["ESTIMATED_TIMEOUT"] == 2667
                   and pending_total == batch["pending_total"] == summary["pending_decision_rows"] == 244
                   and dict(all_routes) == summary["by_route"] and dict(all_categories) == summary["by_category"])
        self.check("summary_is_not_performance_or_same_pending_denominator", summary["performance_improvement_established"] is False
                   and summary["pending_denominator_differs_from_b_v1"] is True
                   and summary["new_model_inference"] is False and summary["rendered_full_videos_in_this_batch"] is False)
        expected_repeats = [
            {"video_id": "weekend_sore", "physical_unit_id": "retained-clique:3651,3670",
             "passage_id": "retained-clique:3651,3670:passage:1", "pending_frames": [5404, 5443]},
            {"video_id": "weekend_sore", "physical_unit_id": "track:4123",
             "passage_id": "track:4123:passage:1", "pending_frames": [6460, 6588]}]
        self.check("known_exact_two_repeated_pending_keys_visible_not_hidden", sorted(repeated_pending, key=canonical)
                   == sorted(expected_repeats, key=canonical) and pending_unique_total == 242
                   and pending_total - pending_unique_total == 2)
        audit = self.read(PREFIX + "/verification/pending_decision_audit.json")
        self.check("derived_pending_audit_244_rows_242_keys_exact_case_no_active_count", audit["pending_decision_rows"] == pending_total
                   and audit["unique_pending_unit_passage_keys"] == pending_unique_total
                   and audit["repeated_pending_excess_rows"] == 2
                   and audit["accepted_events"] == audit["passage_log_net_delta"] == total
                   and audit["raw_results_modified"] is False and audit["frozen_source_modified"] is False
                   and audit["model_or_replay_executed_for_this_audit"] is False
                   and [{key: case[key] for key in ("video_id", "physical_unit_id", "passage_id", "pending_frames")}
                        for case in audit["exact_repeated_pending_keys"]] == expected_repeats
                   and all(not case["accepted_event_ids"] and case["passage_log_net_delta"] == 0
                           for case in audit["exact_repeated_pending_keys"]))
        for case in audit["exact_repeated_pending_keys"]:
            result = self.results[case["video_id"]]
            selected = [row for row in result["passage_log"] if row["physical_unit_id"] == case["physical_unit_id"]
                        and row["passage_id"] == case["passage_id"]]
            transitions = [{key: row.get(key) for key in ("frame_index", "status", "event_id", "count_delta")}
                           for row in selected]
            self.check("pending_duplicate_bounded_log_case:" + case["physical_unit_id"],
                       transitions == case["passage_log_transitions"] and sum(row["count_delta"] for row in selected) == 0
                       and not any(event["physical_unit_id"] == case["physical_unit_id"]
                                   and event["passage_id"] == case["passage_id"] for event in result["events"]))
        for entry in audit["source_artifacts"]:
            raw = self.raw(entry["path"])
            self.check("pending_audit_source:" + entry["path"], digest(raw) == entry["retained_sha256"]
                       and digest(gzip.decompress(raw)) == entry["original_sha256"])
        self.facts["known_limitations"] = {
            "pending_diagnostic_reset_reuses_two_unit_passage_keys": expected_repeats,
            "pending_rows_are_not_unique_passage_count": True,
            "bounded_accepted_ledger_in_these_retained_outputs_has_no_duplicate_key": True}
        self.facts["actual_local_replay"] = {"frames": frames_total, "operational_events": total,
            "measured_events": measured_total, "inferred_events": total - measured_total,
            "estimated_timeout_events": all_routes["ESTIMATED_TIMEOUT"], "pending_decision_rows": pending_total,
            "unique_pending_unit_passage_keys": pending_unique_total}
        self.stages["local_cache_replay"] = "RETAINED_ACTUAL_EXECUTION_CHECKED"

    def software_and_bundle(self):
        software = self.read(PREFIX + "/verification/software_validation.json")
        suites = software["suites"]
        self.check("four_retained_suites_105_tests_no_failures_errors_skips", software["status"] == "PASS"
                   and software["total_tests"] == sum(x["tests"] for x in suites) == 105 and len(suites) == 4
                   and all(x["failures"] == x["errors"] == x["skipped"] == 0 for x in suites))
        for suite in suites:
            path = (PREFIX + "/verification/phase8_publication_tests.py" if suite["module"] == "b_v2_publication_tests"
                    else "notebooks/" + suite["module"] + ".py")
            self.check("tested_source:" + suite["module"], digest(self.raw(path)) == suite["source_sha256"])
        manifest = self.read(PREFIX + "/kaggle_submission/source_bundle_manifest.json")
        submission = self.read(PREFIX + "/kaggle_submission/submission.json")
        packet = self.read(PREFIX + "/verification/submitted_packet_verification.json")
        notebook_bytes = gzip.decompress(self.raw(PREFIX + "/kaggle_submission/submitted_notebook.ipynb.gz"))
        notebook = json.loads(notebook_bytes)
        canonical_notebook = self.read(manifest["canonical_notebook_path"])
        self.check("submitted_notebook_exact_sha_and_canonical_cells", digest(notebook_bytes)
                   == manifest["submitted_notebook"]["sha256"] == submission["submitted_notebook_sha256"]
                   and len(notebook_bytes) == manifest["submitted_notebook"]["bytes"]
                   and notebook["cells"][2:] == canonical_notebook["cells"]
                   and digest(self.raw(manifest["canonical_notebook_path"])) == manifest["canonical_notebook_sha256"])
        bootstrap = ast.parse("".join(notebook["cells"][1]["source"]))
        assignments = {node.targets[0].id: node.value for node in bootstrap.body
                       if isinstance(node, ast.Assign) and len(node.targets) == 1
                       and isinstance(node.targets[0], ast.Name)}
        bundle = json.loads(ast.literal_eval(assignments["B_V2_SOURCE_BUNDLE"].args[0]))
        declared_binding = ast.literal_eval(assignments["B_V2_SOURCE_BINDING_SHA256"])
        source_manifest = {name: {key: entry[key] for key in ("sha256", "bytes")} for name, entry in bundle.items()}
        self.check("exact_30_files_bundle_binding", len(bundle) == manifest["source_file_count"] == 30
                   and source_manifest == manifest["source_files"]
                   and digest(canonical(source_manifest)) == declared_binding == BUNDLE_SHA
                   == manifest["source_bundle_binding_sha256"] == packet["source_bundle_binding_sha256"])
        for name, entry in bundle.items():
            original = gzip.decompress(base64.b64decode(entry["gzip_base64"], validate=True))
            self.check("submitted_payload:" + name, original == self.raw(name)
                       and digest(original) == entry["sha256"] and len(original) == entry["bytes"])
        metadata = self.read(PREFIX + "/kaggle_submission/kernel-metadata.json")
        self.check("CPU_private_no_network_readonly_inputs_packet", metadata["enable_gpu"] is False
                   and metadata["enable_internet"] is False and metadata["is_private"] is True
                   and manifest["credentials_bundled"] is False and manifest["model_weights_bundled"] is False
                   and manifest["videos_bundled"] is False and manifest["original_input_mounts_read_only"] is True)
        self.check("retained_packet_checks_all_pass", len(packet["checks"]) == packet["check_count"]
                   and all(x["passed"] is True for x in packet["checks"]))
        self.check("bundle_builder_bound", digest(self.raw(PREFIX + "/verification/build_kaggle_bundle.py"))
                   == manifest["builder"]["sha256"])

    def previews(self):
        proof = self.read(PREFIX + "/previews/preview_proof.json")
        self.check("preview_actual_source_identity", proof["actual_source_identity"]
                   == self.results["weekday_pagi"]["source_identity"])
        self.check("three_actual_preview_routes", len(proof["previews"]) == 3
                   and {x["route_example"] for x in proof["previews"]}
                   == {"LINE_MARGIN", "OCCLUSION_DIFF_POLYGON", "ESTIMATED_TIMEOUT"})
        for entry in proof["previews"]:
            raw = self.raw(entry["path"])
            dimensions = struct.unpack(">II", raw[16:24]) if raw[:8] == b"\x89PNG\r\n\x1a\n" else None
            sections = entry["panel_sections_y"]
            self.check("preview:" + Path(entry["path"]).name, digest(raw) == entry["sha256"]
                       and dimensions == (entry["canvas_width"], entry["canvas_height"]) == (1160, 960)
                       and sections["accepted"] < sections["passage_log"] < sections["pending"]
                       and entry["source_pixel_sha_verified_by_renderer"] is True)

    def local_annotation(self):
        proof = self.read(PREFIX + "/execution/local_annotation/retention_proof.json")
        raw = self.raw(proof["retained_path"])
        report = json.loads(raw)
        result = self.results["weekday_pagi"]
        self.check("separate_actual_local_annotation_report_retained_exact", digest(raw) == proof["sha256"]
                   and len(raw) == proof["size_bytes"] and proof["video_in_git"] is False)
        self.check("local_annotation_full_9052_frames_and_unchanged_ledger", report["source_identity"] == result["source_identity"]
                   and report["output_video"]["frames_written"] == report["output_video"]["frames_redecoded"] == 9052
                   and report["output_video"]["width"] == 1160 and report["output_video"]["height"] == 960
                   and report["final_accepted"] == result["aggregate"]["total"]
                   and report["final_pending"] == result["aggregate"]["pending"]
                   and report["route_counts"] == result["aggregate"]["by_route"]
                   and report["new_detector_tracker_encoder_inference"] is False
                   and report["counting_rerun_by_renderer"] is False
                   and report["frame_pixel_and_raw_link_verified_every_frame"] is True
                   and report["inputs_unchanged_after_render"] is True
                   and report["source_image_region"]["resized"] is False
                   and report["software_source_sha256"] == digest(self.raw("notebooks/phase_8_b_v2_annotation.py")))

    def bounded_timeout_review(self):
        review = self.read(PREFIX + "/review/timeout_edge_car/review.json")
        scope = review["review_scope"]
        identity = self.results["weekday_pagi"]["source_identity"]
        self.check("bounded_review_is_sparse_evidence_not_ground_truth", scope["video_id"] == "weekday_pagi"
                   and scope["full_interval_visually_reviewed"] is False and scope["formal_ground_truth"] is False
                   and scope["frozen_source_or_counting_result_modified"] is False
                   and scope["model_tracker_reid_or_counting_rerun"] is False
                   and review["source_video"]["sha256"] == identity["video_sha256"]
                   and review["source_cache"]["sha256"] == identity["records_sha256"]
                   and all(row["claim_type"] == "HYPOTHESIS_UNTESTED" for row in review["hypotheses"]))
        for key in ("actual_counting_result", "actual_geometry"):
            proof = review[key]
            raw = self.raw(proof["path"])
            self.check("bounded_review_source:" + key, digest(raw) == proof["compressed_sha256"]
                       and digest(gzip.decompress(raw)) == proof["uncompressed_sha256"])
        sample_frames = [0, 16, 76, 110, 141, 201]
        self.check("bounded_review_six_actual_frames", scope["sampled_source_frame_indices"] == sample_frames
                   and [image["frame_index"] for image in review["sample_images"]] == sample_frames)
        for image in review["sample_images"]:
            raw = self.raw(image["path"])
            self.check("bounded_review_PNG:" + str(image["frame_index"]), digest(raw) == image["sha256"]
                       and raw[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", raw[16:24]) == (640, 480))
        actual_events = {event["event_id"]: event for event in self.results["weekday_pagi"]["events"]}
        sampled_events = review["retained_events"]
        self.check("bounded_review_two_actual_timeout_events_unmeasured", len(sampled_events) == 2
                   and {event["track_id"] for event in sampled_events} == {2, 34}
                   and all(actual_events[event["event_id"]] == event and event["route"] == "ESTIMATED_TIMEOUT"
                           and event["evidence"]["measured_crossing"] is False
                           and event["evidence"]["band_observed"] is False
                           and event["evidence"]["destination_observed_ref"] is None for event in sampled_events))
        observations = review["target_observations_within_bounded_scope"]
        links = True
        for item in observations:
            observation, raw = item["emitted_observation"], item["linked_raw_detection"]
            box = observation["raw_bbox"]
            links &= (observation["emitted"] is True and observation["measurement_provenance"] == "retained_phase_8_detection"
                      and box == raw["bbox_xyxy_pixels"]
                      and all(observation[key] == raw[key] for key in ("class_id", "class_name", "confidence"))
                      and item["measured_vehicle_bc"] == [(box[0] + box[2]) / 2, box[3]]
                      and item["inside_finite_25px_halfwidth_band"] is False)
        self.check("bounded_review_retained_89_measured_links_not_full_video_audit", len(observations) == 89 and links)
        self.facts["known_limitations"]["sampled_timeout_physical_validity_requires_further_audit"] = {
            "source": PREFIX + "/review/timeout_edge_car/review.json", "raw_track_ids": [2, 34],
            "two_actual_estimates_without_observed_band_or_destination": True,
            "stationary_vehicle_or_same_physical_identity_hypotheses_unconfirmed": True,
            "formal_ground_truth": False}

    def remote_stages(self, required):
        kaggle = self.path(PREFIX + "/kaggle_execution")
        self.stages["kaggle_render_execution"] = "NOT_RETAINED"
        if (kaggle / "execution_summary.json").is_file():
            self.section("kaggle_render_execution", self.kaggle_execution)
        elif required:
            self.check("kaggle_render_execution:required_actual_retained_stage", False,
                       "Kaggle evidence binding requires its actual completion receipt; no API call is made.")
        required_files = ("publication_receipt.json", "release_api_snapshot.json", "workflow_run.json")
        publication = PREFIX + "/publication/"
        if not all(self.path(publication + name).is_file() for name in required_files):
            self.stages["github_publication"] = "NOT_RETAINED"
            if required:
                self.check("github_publication:required_actual_retained_stage", False,
                           "Final publication receipt, release API snapshot and workflow run are required.")
            return
        self.section("github_publication", self.publication)

    def kaggle_execution(self):
        prefix = PREFIX + "/kaggle_execution/"
        summary = self.read(prefix + "execution_summary.json")
        proof = self.read(prefix + "retrieval_proof.json")
        mapping = self.read(summary["retention_mapping"])
        originals = {}
        for item in mapping["artifacts"]:
            retained = self.raw(item["retained_path"])
            original = gzip.decompress(retained) if item["encoding"] == "gzip" else retained
            name = item["original_relative_path"]
            self.check("kaggle:retained_exact_bytes:" + name,
                       digest(retained) == item["retained_sha256"]
                       and len(retained) == item["retained_size_bytes"]
                       and digest(original) == item["original_sha256"]
                       and len(original) == item["original_size_bytes"]
                       and item["original_kaggle_output_path"] == proof["actual_output_prefix"] + name)
            originals[name] = original
        self.check("kaggle:33_actual_artifacts_unique", len(originals) == len(mapping["artifacts"]) == 33)
        manifest_raw = originals["retention_manifest.json"]
        manifest = json.loads(manifest_raw)
        bound = {item["path"]: item for item in manifest["artifacts"]}
        for name, raw in originals.items():
            if name == "retention_manifest.json":
                continue  # The original run manifest cannot include its own digest.
            self.check("kaggle:original_run_manifest:" + name,
                       name in bound and digest(raw) == bound[name]["sha256"]
                       and len(raw) == bound[name]["size_bytes"])
        batch = json.loads(originals["batch_report.json"])
        self.check("kaggle:actual_complete_terminal_and_original_manifest",
                   proof["status"] == "completed_verified" and proof["terminal_status"] == "COMPLETE"
                   and proof["errors"] == [] and summary["terminal_status"] == "COMPLETE"
                   and proof["actual_run_id"] == summary["run_id"] == mapping["run_id"] == batch["run_id"]
                   and digest(manifest_raw) == proof["actual_retention_manifest_sha256"]
                   == summary["actual_retention_manifest_sha256"])
        self.check("kaggle:all_eight_rendered_redecoded_no_new_models",
                   batch["all_eight_completed"] is True and batch["render_requested"] is True
                   and batch["all_selected_completed"] is True
                   and batch["frames_processed"] == summary["frames_processed"] == 72590
                   and batch["operational_total"] == summary["operational_total"] == 3717
                   and batch["pending_total"] == summary["pending_decision_rows"] == 244
                   and batch["new_detector_tracker_reid_execution"] is False
                   and batch["source_files_unchanged_during_execution"] is True
                   and summary["physical_counting_accuracy_established"] is False
                   and summary["rendered_full_videos"] == 8)
        snapshot = json.loads(originals["source_snapshot.json"])
        self.check("kaggle:exact_six_executed_sources", len(snapshot) == 6
                   and snapshot == batch["executed_source_files"])
        for name, entry in snapshot.items():
            path = "notebooks/" + Path(name).name
            source = gzip.decompress(originals[entry["retained_path"]])
            self.check("kaggle:executed_source:" + path,
                       digest(source) == entry["sha256"] and len(source) == entry["size_bytes"]
                       and source == self.raw(path) == self.git_bytes(EXECUTED_COMMIT, path))
        supporting = self.read(prefix + "supporting_retention_manifest.json")
        restored = {}
        for entry in supporting["artifacts"]:
            saved = self.raw(entry["retained_path"])
            raw = gzip.decompress(saved)
            self.check("kaggle:supporting_exact_bytes:" + Path(entry["retained_path"]).name,
                       digest(saved) == entry["retained_sha256"] and digest(raw) == entry["original_sha256"]
                       and len(raw) == entry["original_size_bytes"])
            restored[Path(entry["original_path"]).name] = raw
        pulled = json.loads(restored["phase-8-tgdi-b-v2-review.ipynb"])
        submitted = self.read(PREFIX + "/kaggle_submission/submitted_notebook.ipynb.gz")
        cells = lambda notebook: [(cell["cell_type"], "".join(cell["source"])) for cell in notebook["cells"]]
        self.check("kaggle:pulled_notebook_normalized_json_same_all_cell_sources",
                   cells(pulled) == cells(submitted) and proof["pulled_notebook_contains_expected_binding"] is True)
        log = restored["kernel.log"]
        self.check("kaggle:actual_log_executed_source_binding",
                   digest(log) == proof["kernel_log"]["sha256"] and BUNDLE_SHA.encode() in log
                   and proof["source_bundle_binding_verified_from_log"] is True
                   and proof["expected_source_binding_sha256"] == summary["source_bundle_binding_sha256"] == BUNDLE_SHA)
        delivery = self.read(PREFIX + "/delivery_manifest.json")
        assets = {item["video_id"]: item for item in delivery["assets"]}
        rows = {row["video_id"]: row for row in batch["videos"]}
        self.check("kaggle:eight_video_sets_match", set(rows) == set(assets) == VIDEO_IDS)
        total_bytes, frame_total = 0, 0
        for video_id, row in rows.items():
            raw = originals[video_id + "/counting_result.json"]
            result, annotation = json.loads(raw), json.loads(originals[video_id + "/annotation_report.json"])
            video, asset = annotation["output_video"], assets[video_id]
            self.check("kaggle:counting_result_exact_equal_local:" + video_id,
                       raw == self.originals[video_id + "/counting_result.json"]
                       and result["aggregate"] == row["aggregate"]
                       and result["source_identity"] == row["source_identity"] == annotation["source_identity"])
            self.check("kaggle:actual_annotation_full_H264_frames:" + video_id,
                       video["codec"] == "h264" and video["pixel_format"] == "yuv420p"
                       and (video["width"], video["height"]) == (1160, 960)
                       and video["frames_written"] == video["frames_redecoded"] == row["frames"] == asset["frame_count"]
                       and annotation["source_image_region"]["resized"] is False
                       and annotation["frame_pixel_and_raw_link_verified_every_frame"] is True
                       and annotation["inputs_unchanged_after_render"] is True
                       and annotation["new_detector_tracker_encoder_inference"] is False
                       and annotation["counting_rerun_by_renderer"] is False)
            self.check("kaggle:render_ledger_reconciles:" + video_id,
                       annotation["final_accepted"] == result["aggregate"]["total"]
                       and annotation["final_pending"] == result["aggregate"]["pending"]
                       and annotation["final_measured"] == result["aggregate"]["measured_total"]
                       and annotation["final_inferred"] == result["aggregate"]["inferred_total"]
                       # The renderer shows all routes, including explicit zero;
                       # the ledger omits routes with no active event.
                       and Counter(annotation["route_counts"]) == Counter(result["aggregate"]["by_route"])
                       and annotation["pending_excluded_from_pivot"] is True)
            video_relative = video_id + "/" + video_id + "-b-v2-annotated.mp4"
            self.check("kaggle:MP4_actual_output_delivery_binding:" + video_id,
                       video["sha256"] == bound[video_relative]["sha256"] == asset["sha256"]
                       and video["size_bytes"] == bound[video_relative]["size_bytes"] == asset["size_bytes"]
                       and asset["source_output_path"] == proof["actual_output_prefix"] + video_relative)
            total_bytes += video["size_bytes"]
            frame_total += video["frames_redecoded"]
        self.check("kaggle:all_delivered_video_bytes_and_frames", total_bytes == summary["total_mp4_size_bytes"] == 872619576
                   and frame_total == 72590)
        self.stages["kaggle_render_execution"] = "ACTUAL_COMPLETE_EIGHT_VIDEO_RENDER_RETAINED_AND_CHECKED"
        self.facts["actual_kaggle_execution"] = {"run_id": batch["run_id"], "rendered_videos": 8,
            "frames_written_and_redecoded": frame_total, "video_bytes": total_bytes,
            "counting_results_exact_byte_equal_to_local": True, "new_model_inference": False}

    def publication(self):
        prefix = PREFIX + "/publication/"
        receipt = self.read(prefix + "publication_receipt.json")
        snapshot = self.read(prefix + "release_api_snapshot.json")
        workflow = self.read(prefix + "workflow_run.json")
        delivery_raw = self.raw(PREFIX + "/delivery_manifest.json")
        delivery = json.loads(delivery_raw)
        repo = "unChris666/traffic-vehicle-counter-IDM-LOC"
        tag = "phase8-b-v2-tgdi-review-v1"
        self.check("publication:actual_final_release_and_executed_source", receipt["schema_version"]
                   == "phase8_b_v2_publication_receipt_v1" and receipt["repository"] == repo
                   and receipt["draft"] is False and snapshot["draft"] is False
                   and receipt["release_id"] == snapshot["id"] and receipt["tag_name"] == snapshot["tag_name"] == tag
                   and receipt["executed_source_commit"] == receipt["resolved_tag_commit_sha"]
                   == snapshot["target_commitish"] == EXECUTED_COMMIT
                   and receipt["html_url"] == snapshot["html_url"]
                   == f"https://github.com/{repo}/releases/tag/{tag}")
        self.check("publication:workflow_completed_success", workflow["status"] == "completed"
                   and workflow["conclusion"] == "success" and str(workflow["id"]) == str(receipt["workflow_run_id"])
                   and workflow["head_sha"] == receipt["delivery_source_commit"])
        probe = receipt["credential_verification"]
        self.check("publication:actual_upload_probe_before_bulk_native_token", probe["status"] == "UPLOAD_AUTHORIZATION_VERIFIED"
                   and probe["bulk_download_started"] is False and probe["token_value_retained"] is False
                   and probe["temporary_owned_draft_deleted"] is True)
        self.check("publication:transport_only_no_models_counting_encoding", receipt["new_detector_tracker_reid_counting_or_encoding_execution"] is False
                   and receipt["signed_download_urls_retained"] is False and receipt["videos_committed_to_git"] is False)
        self.check("publication:delivery_manifest_and_six_executed_sources", receipt["delivery_manifest_sha256"] == digest(delivery_raw)
                   and delivery["source_commit"] == EXECUTED_COMMIT
                   and receipt["executed_source_files"] == delivery["executed_source_files"]
                   and len(delivery["executed_source_files"]) == 6)
        for source in delivery["executed_source_files"]:
            self.check("publication:executed_source:" + source["path"], digest(self.raw(source["path"])) == source["sha256"]
                       == digest(self.git_bytes(EXECUTED_COMMIT, source["path"])))
        for path in (".github/scripts/phase8_publish_b_v2.py", ".github/workflows/phase8-publish-b-v2.yml"):
            self.check("publication:delivery_commit_source:" + path, self.raw(path)
                       == self.git_bytes(receipt["delivery_source_commit"], path))
        server_assets = {asset["name"]: asset for asset in snapshot["assets"]}
        videos = {asset["video_id"]: asset for asset in receipt["assets"]}
        declared = {asset["video_id"]: asset for asset in delivery["assets"]}
        self.check("publication:exact_eight_videos_eleven_assets", set(videos) == set(declared) == VIDEO_IDS
                   and len(snapshot["assets"]) == len(server_assets) == receipt["expected_final_release_asset_count"] == 11
                   and receipt["video_asset_count"] == 8 and len(receipt["supplemental_assets"]) == 2)
        for video_id, item in declared.items():
            received = videos[video_id]
            server = server_assets[item["filename"]]
            self.check("publication:MP4_server_digest_size_final_URL:" + video_id,
                       received["name"] == item["filename"] == server["name"]
                       and received["id"] == server["id"] and received["size_bytes"] == item["size_bytes"] == server["size"]
                       and received["sha256"] == item["sha256"] and server["digest"] == "sha256:" + item["sha256"]
                       and received["state"] == server["state"] == "uploaded"
                       and received["browser_download_url"] == server["browser_download_url"]
                       == f"https://github.com/{repo}/releases/download/{tag}/{item['filename']}")
            result = self.results[video_id]
            self.check("publication:video_counts_from_actual_frozen_ledger:" + video_id,
                       item["operational_total"] == result["aggregate"]["total"]
                       and item["measured_total"] == result["aggregate"]["measured_total"]
                       and item["inferred_total"] == result["aggregate"]["inferred_total"]
                       and item["frame_count"] == result["report"]["frame_count"])
        downloaded = {item["video_id"]: item for item in receipt["verified_kaggle_downloads"]}
        self.check("publication:verified_actual_eight_Kaggle_downloads", set(downloaded) == VIDEO_IDS and all(
            downloaded[video_id]["sha256"] == asset["sha256"]
            and downloaded[video_id]["size_bytes"] == asset["size_bytes"]
            and downloaded[video_id]["http_status"] == 200
            and downloaded[video_id]["download_url_or_secret_retained"] is False
            for video_id, asset in declared.items()))
        for asset in receipt["supplemental_assets"]:
            server = server_assets[asset["name"]]
            self.check("publication:supplemental:" + asset["name"], server["id"] == asset["id"]
                       and server["size"] == asset["size_bytes"] and server["digest"] == "sha256:" + asset["sha256"]
                       and server["browser_download_url"] == asset["browser_download_url"]
                       == f"https://github.com/{repo}/releases/download/{tag}/{asset['name']}")
        own_asset = server_assets["publication_receipt.json"]
        self.check("publication:receipt_uploaded_exact_server_digest", own_asset["digest"]
                   == "sha256:" + digest(self.raw(prefix + "publication_receipt.json"))
                   and own_asset["size"] == len(self.raw(prefix + "publication_receipt.json")))
        self.check("publication:retained_totals_72590_3717_898_2819", receipt["frame_total"] == 72590
                   and receipt["operational_total"] == 3717 and receipt["measured_total"] == 898
                   and receipt["inferred_total"] == 2819)
        self.stages["github_publication"] = "ACTUAL_FINAL_PUBLICATION_RECEIPT_AND_SERVER_ASSETS_CHECKED"

    def capture_paths(self):
        paths = {path.relative_to(self.root).as_posix() for path in self.path(PREFIX).rglob("*") if path.is_file()
                 and "__pycache__" not in path.parts and path.suffix != ".pyc"}
        paths.update(path.relative_to(self.root).as_posix() for path in self.path("notebooks").glob("phase_8_b_v2_*.py"))
        paths.update(("notebooks/08b_counting_b_v2_replay.ipynb", "AGENTS.md", "docs/COUNTING_LOGIC.md",
                      "docs/B_V2_COUNTING_CONTRACT.md", "results/README.md"))
        paths.update(path.relative_to(self.root).as_posix() for directory in (".github/scripts", ".github/workflows")
                     for path in self.path(directory).iterdir() if path.is_file()
                     and ("b_v2" in path.name or "b-v2" in path.name))
        return sorted(paths - EXCLUDED)

    def retained_final_manifest(self):
        if not self.path(FINAL_MANIFEST).exists():
            self.stages["final_retention_manifest"] = "NOT_CAPTURED"
            return
        manifest = self.read(FINAL_MANIFEST)
        entries = manifest["artifacts"]
        self.check("final_manifest_exact_path_set", [x["path"] for x in entries] == self.capture_paths())
        for entry in entries:
            raw = self.raw(entry["path"])
            self.check("final_manifest:" + entry["path"], len(raw) == entry["size_bytes"] and digest(raw) == entry["sha256"])
        self.stages["final_retention_manifest"] = "RETAINED_MANIFEST_CHECKED"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--require-published", action="store_true")
    args = parser.parse_args()
    checker = Checker(args.repo_root)
    for name, function in (("geometry", checker.geometry), ("history", checker.history),
                           ("exact_retention", checker.exact_retention), ("ledger", checker.ledger),
                           ("software_and_bundle", checker.software_and_bundle), ("previews", checker.previews),
                           ("local_annotation", checker.local_annotation),
                           ("bounded_timeout_review", checker.bounded_timeout_review)):
        checker.section(name, function)
    checker.section("remote_stages", lambda: checker.remote_stages(args.require_published))
    if not args.capture:
        checker.section("final_manifest", checker.retained_final_manifest)
    failures = [entry for entry in checker.checks if not entry["passed"]]
    report = {"schema_version": "b_v2_retained_artifact_validation_v1",
              "claim_type": "READ_ONLY_INTEGRITY_OF_RETAINED_EVIDENCE_NOT_PERFORMANCE",
              "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": "PASS" if not failures else "FAIL", "require_published": args.require_published,
              "no_model_replay_media_tests_or_network_execution": True,
              "source_commit": EXECUTED_COMMIT, "stages": checker.stages, "facts": checker.facts,
              "check_count": len(checker.checks), "failed_count": len(failures), "checks": checker.checks}
    if args.capture:
        if failures:
            raise SystemExit(json.dumps({"status": "FAIL_CAPTURE_REFUSED", "failures": failures}, indent=2))
        artifacts = []
        for name in checker.capture_paths():
            raw = checker.raw(name)
            artifacts.append({"path": name, "size_bytes": len(raw), "sha256": digest(raw)})
        manifest = {"schema_version": "b_v2_final_retention_v1", "created_at_utc": report["checked_at_utc"],
                    "source_commit": EXECUTED_COMMIT, "excluded_recursive_outputs": sorted(EXCLUDED),
                    "artifacts": artifacts}
        checker.path(FINAL_MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
        checker.section("final_manifest", checker.retained_final_manifest)
        failures = [entry for entry in checker.checks if not entry["passed"]]
        report.update(status="PASS" if not failures else "FAIL",
                      check_count=len(checker.checks), failed_count=len(failures))
        checker.path(FINAL_VALIDATION).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "check_count", "failed_count", "stages", "facts")}, indent=2))
    if failures:
        print(json.dumps({"failures": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
