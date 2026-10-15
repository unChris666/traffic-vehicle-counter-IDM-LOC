"""Synthetic contract checks; these fixtures are not video-count evidence."""
from __future__ import annotations

import copy
import csv
import hashlib
import gzip
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import phase_8_batch_helpers as batch
import phase_8_pipeline_helpers as pipeline
from phase_8_pipeline_tests import Fixture

REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class BatchContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="phase8-synthetic-batch-")
        self.root = Path(self.temp.name)
        self.manifest = {"schema_version": batch.SCHEMA_VERSION, "evidence_kind": "SYNTHETIC_TEST_FIXTURE",
                         "location": {"store_code": "SYNTHETIC", "store_name": "SYNTHETIC", "latitude": 0, "longitude": 0},
                         "videos": []}
        self.results = []
        self.fixtures = []
        for day in batch.DAY_TYPES:
            for period in batch.PERIODS:
                video_id = day + "_" + period
                fixture_root = self.root / video_id
                fixture_root.mkdir()
                (fixture_root / "notebooks").symlink_to(REPO_ROOT / "notebooks", target_is_directory=True)
                fixture = Fixture(fixture_root, positions=(20, 40, 60, 20, 40, 60))
                fixture.video_sha = _sha(video_id)
                fixture.geometry_data["source_video"]["sha256"] = fixture.video_sha
                for index, record in enumerate(fixture.records):
                    record["video_sha256"] = fixture.video_sha
                    if index >= 3:
                        x = (20, 40, 60)[index - 3]
                        box = [x - 15, 30, x + 15, 60]
                        record["raw_detections"] = [{"bbox_xyxy_pixels": box, "class_id": 2, "class_name": "car", "confidence": .8}]
                        record["emitted_tracks"] = [{"track_id": 5, "frame_index": index, "original_detection_index": 0,
                            "raw_bbox": box, "bbox": box, "class_id": 2, "class_name": "car", "confidence": .8,
                            "emitted": True, "measurement_provenance": pipeline.PROVENANCE}]
                fixture.save()
                result = fixture.replay(fixture_root / "machine")
                self.fixtures.append(fixture)
                video = {"video_id": video_id, "slot_id": video_id, "day_type": day, "recording_period": period,
                         "source_sha256": fixture.video_sha, "geometry_sha256": fixture.identity["geometry_sha256"],
                         "observed_metadata": {"width": 100, "height": 100, "frame_count": 6}, "snapshot_selection": {"kind": "machine"}}
                self.manifest["videos"].append(video)
                result["video_id"] = video_id
                self.results.append(result)

    def tearDown(self):
        self.temp.cleanup()

    def _report(self):
        return batch.aggregate_batch(self.manifest, self.results, repo_root=REPO_ROOT)

    def _edit(self, name, mutate, result_index=0):
        snapshot = self.results[result_index]["snapshot"]
        path = Path(snapshot[name + "_path"])
        value = batch._read_json(path)
        mutate(value)
        if path.suffix == ".gz":
            path.write_bytes(gzip.compress(json.dumps(value).encode(), mtime=0))
        else:
            path.write_text(json.dumps(value))
        snapshot[name + "_sha256"] = batch.sha256_file(path)

    def test_eight_slots_reconcile_and_namespace_local_ids(self):
        report = self._report()
        self.assertTrue(report["all_eight_videos_processed"])
        self.assertEqual(report["accepted_observed_event_count"], 8)
        self.assertEqual(len({item["batch_event_id"] for item in report["accepted_event_ledger"]}), 8)
        self.assertEqual(report["tables"]["weekday"][1]["total"], 4)
        self.assertEqual(report["tables"]["weekend"][1]["total"], 4)

    def test_pending_excluded_and_retained_separately(self):
        report = self._report()
        self.assertEqual(report["pending_observed_count"], 8)
        self.assertEqual(report["tables"]["weekday"][2]["total"], 0)
        self.assertEqual(len(report["audit_queue"]), 8)

    def test_unsupported_categories_are_null(self):
        report = self._report()
        for day in batch.DAY_TYPES:
            for index in (0, 3):
                self.assertTrue(all(report["tables"][day][index][field] is None for field in (*batch.PERIODS, "total")))
        self.assertFalse(report["business_category_coverage_complete"])

    def test_missing_slot_never_becomes_zero(self):
        self.results.pop(0)
        report = self._report()
        self.assertIsNone(report["tables"]["weekday"][1]["pagi"])
        self.assertIsNone(report["tables"]["weekday"][1]["total"])
        self.assertIsNone(report["complete_batch_accepted_total"])
        self.assertEqual(report["accepted_observed_event_count"], 7)

    def test_failure_retains_error_and_null(self):
        self.results[0] = {"video_id": "weekday_pagi", "status": "failed_partial_execution", "error": {"message": "SYNTHETIC failure"}}
        report = self._report()
        self.assertEqual(report["status"], "incomplete_batch")
        self.assertIsNone(report["per_video"][0]["accepted_event_count"])
        self.assertEqual(report["per_video"][0]["error"]["message"], "SYNTHETIC failure")

    def test_duplicate_event_id_rejected(self):
        self._edit("events", lambda value: value.append(copy.deepcopy(value[0])))
        with self.assertRaisesRegex(batch.BatchContractError, "Duplicate or missing accepted event"):
            self._report()

    def test_same_passage_with_new_event_id_rejected(self):
        def mutate(value):
            duplicate = copy.deepcopy(value[0]); duplicate["event_id"] = "different-event-id"; value.append(duplicate)
        self._edit("events", mutate)
        with self.assertRaisesRegex(batch.BatchContractError, "Duplicate physical passage"):
            self._report()

    def test_pending_car_is_not_promoted_by_a_new_event_identity(self):
        def mutate(value):
            returned = copy.deepcopy(value[0]); returned.update(event_id="forged-return-event", passage_id="forged-return-passage"); value.append(returned)
        self._edit("events", mutate)
        with self.assertRaisesRegex(batch.BatchContractError, "accepted representative decision"):
            self._report()

    def test_duplicate_rerun_results_rejected(self):
        self.results.append(copy.deepcopy(self.results[0]))
        with self.assertRaisesRegex(batch.BatchContractError, "Duplicate rerun"):
            self._report()

    def test_unknown_result_source_rejected(self):
        self.results[0]["video_id"] = "not-in-this-batch"
        with self.assertRaisesRegex(batch.BatchContractError, "outside this manifest"):
            self._report()

    def test_snapshot_rerun_mismatch_rejected(self):
        self.results[0]["snapshot"]["run_id"] = "another-run"
        with self.assertRaisesRegex(batch.BatchContractError, "Mixed rerun"):
            self._report()

    def test_reviewed_snapshot_selected_without_adding_machine(self):
        import phase_8_review_helpers as bridge
        first, fixture = self.results[0], self.fixtures[0]
        directory = Path(first["snapshot"]["configuration_path"]).parent
        config = batch._read_json(directory / "counting_configuration.json")
        decisions = batch._read_json(directory / "machine_passage_decisions.json.gz")
        episodes = batch._read_json(directory / "episodes.json.gz")
        events = batch._read_json(directory / "machine_count_events.json.gz")
        pending = next(item for item in decisions if item["status"] == "pending_review")
        reviews = {"source_identity": first["source_identity"], "decisions": [{
            "candidate_id": pending["candidate_id"], "disposition": "CONFIRM_PASSAGE", "reviewer": "SYNTHETIC_TEST_FIXTURE",
            "reason": "SYNTHETIC positive audit fixture, not a real video observation", "category": "car",
            "unit_confirmed": True, "category_confirmed": True, "identity_confirmed": True,
            "physical_unit_id": "SYNTHETIC_MANUAL_CAR_UNIT", "passage_id": "SYNTHETIC_MANUAL_CAR_PASSAGE",
            "evidence": [{"path": "frame.png", "sha256": batch.sha256_file(fixture.root / "frame.png"),
                "frame_indices": [3, 4, 5], "observation": "SYNTHETIC photo fixture, not actual vehicle labels"}]}]}
        adapter, _, _ = bridge.load_review_adapter(REPO_ROOT)
        _, geometry = pipeline.validate_geometry(fixture.geometry, fixture.identity, repo_root=REPO_ROOT, allow_synthetic=True)
        resolved = adapter.build_reviewed_snapshot(decisions, episodes, events, config, reviews, repo=fixture.root, geometry=geometry)
        self.assertEqual({event["manual_review_applied"] if "manual_review_applied" in event else False for event in resolved["accepted_events"]}, {False, True})
        output = fixture.root / "reviewed"; output.mkdir()
        (output / "review_input.json").write_text(json.dumps(reviews))
        reviewed = copy.deepcopy(first["snapshot"]); reviewed["kind"] = "reviewed"
        for key, value in (("events", resolved["accepted_events"]), ("decisions", resolved["resolved_decisions"])):
            path = output / (key + ".json.gz"); path.write_bytes(gzip.compress(json.dumps(value).encode(), mtime=0))
            reviewed[key + "_path"] = str(path); reviewed[key + "_sha256"] = batch.sha256_file(path)
        first["snapshots"] = {"machine": first["snapshot"], "reviewed": reviewed}
        self.manifest["videos"][0]["snapshot_selection"] = {"kind": "reviewed"}
        report = self._report()
        self.assertEqual(report["accepted_observed_event_count"], 9)
        self.assertEqual(report["pending_observed_count"], 7)
        self.assertEqual(report["accepted_event_ledger"][0]["snapshot_kind"], "reviewed")

    def test_reviewed_snapshot_unavailable_rejected(self):
        self.manifest["videos"][0]["snapshot_selection"] = {"kind": "reviewed"}
        with self.assertRaisesRegex(batch.BatchContractError, "kind mismatch"):
            self._report()

    def test_reviewed_event_cannot_be_silently_machine(self):
        self._edit("events", lambda value: value[0].update(manual_review_applied=True))
        with self.assertRaisesRegex(batch.BatchContractError, "Reviewed event silently"):
            self._report()

    def test_source_video_mismatch_rejected(self):
        self.results[0]["source_identity"]["video_sha256"] = _sha("foreign-video")
        with self.assertRaisesRegex(batch.BatchContractError, "does not match"):
            self._report()

    def test_geometry_mismatch_rejected(self):
        self.results[0]["source_identity"]["geometry_sha256"] = _sha("foreign-geometry")
        with self.assertRaisesRegex(batch.BatchContractError, "does not match"):
            self._report()

    def test_event_cache_source_mismatch_rejected(self):
        self._edit("events", lambda value: value[0]["source_identity"].update(records_sha256=_sha("another-cache")))
        with self.assertRaisesRegex(batch.BatchContractError, "different source"):
            self._report()

    def test_raw_gamma_mixture_rejected(self):
        self.results[0]["source_identity"]["variant"] = "gamma_070"
        with self.assertRaisesRegex(batch.BatchContractError, "requires raw"):
            self._report()

    def test_configuration_hash_tamper_rejected(self):
        path = Path(self.results[0]["snapshot"]["configuration_path"])
        path.write_text(path.read_text() + " ")
        with self.assertRaisesRegex(batch.BatchContractError, "SHA mismatch"):
            self._report()

    def test_configuration_input_mismatch_rejected(self):
        self._edit("configuration", lambda value: value["input_identity"].update(records_sha256=_sha("another-cache")))
        with self.assertRaisesRegex(batch.BatchContractError, "configuration and source"):
            self._report()

    def test_non_count_event_rejected(self):
        self._edit("events", lambda value: value[0].update(type="GEOMETRY_TRANSITION"))
        with self.assertRaisesRegex(batch.BatchContractError, "Only typed accepted"):
            self._report()

    def test_false_acceptance_rejected(self):
        self._edit("events", lambda value: value[0].update(accepted_count_event=False))
        with self.assertRaisesRegex(batch.BatchContractError, "Only typed accepted"):
            self._report()

    def test_unresolved_taxonomy_event_rejected(self):
        self._edit("events", lambda value: value[0].update(category="bus_angkot"))
        with self.assertRaisesRegex(batch.BatchContractError, "Unresolved/unsupported category"):
            self._report()

    def test_invalid_direction_rejected(self):
        self._edit("events", lambda value: value[0].update(direction="UNKNOWN"))
        with self.assertRaisesRegex(batch.BatchContractError, "direction is unresolved"):
            self._report()

    def test_mixed_policy_snapshot_rejected(self):
        self._edit("events", lambda value: value[0].update(policy_identity="foreign-policy"))
        with self.assertRaisesRegex(batch.BatchContractError, "policy identity differs"):
            self._report()

    def test_targeted_window_result_rejected(self):
        self.results[0]["scope"] = "five_declared_windows"
        with self.assertRaisesRegex(batch.BatchContractError, "Targeted windows"):
            self._report()

    def test_complete_decode_count_required(self):
        self.manifest["videos"][0]["verified_source"] = {"decoded_frame_count": 7}
        with self.assertRaisesRegex(batch.BatchContractError, "Incomplete decoded-frame"):
            self._report()

    def test_observed_frame_count_mismatch_without_verified_source(self):
        self.manifest["videos"][0]["observed_metadata"]["frame_count"] = 7
        with self.assertRaisesRegex(batch.BatchContractError, "Incomplete observed-frame"):
            self._report()

    def test_forged_event_for_absent_candidate_rejected(self):
        self._edit("events", lambda value: value[0].update(candidate_id="nonexistent-candidate", policy_identity="invented-policy", geometry_evidence={"type": "AMBIGUOUS_GAP"}))
        with self.assertRaisesRegex(batch.BatchContractError, "no retained candidate"):
            self._report()

    def test_pending_candidate_cannot_get_forged_accepted_event(self):
        decisions = batch._read_json(self.results[0]["snapshot"]["decisions_path"])
        pending = next(item for item in decisions if item["status"] == "pending_review")
        self._edit("events", lambda value: value[0].update(candidate_id=pending["candidate_id"]))
        with self.assertRaisesRegex(batch.BatchContractError, "not an accepted representative"):
            self._report()

    def test_forged_geometry_cannot_use_accepted_candidate(self):
        self._edit("events", lambda value: value[0].update(geometry_evidence={"type": "AMBIGUOUS_GAP"}))
        with self.assertRaisesRegex(batch.BatchContractError, "measured geometry/source BC"):
            self._report()

    def test_same_source_assigned_two_slots_rejected(self):
        self.manifest["videos"][1]["source_sha256"] = self.manifest["videos"][0]["source_sha256"]
        with self.assertRaisesRegex(batch.BatchContractError, "Same source video reused"):
            self._report()

    def test_duplicate_business_slot_rejected(self):
        self.manifest["videos"][1]["recording_period"] = self.manifest["videos"][0]["recording_period"]
        with self.assertRaisesRegex(batch.BatchContractError, "Duplicate slot"):
            self._report()

    def test_csv_null_is_blank_supported_zero_is_zero(self):
        report = self._report()
        output = batch.write_batch_outputs(self.root / "export", report)
        rows = list(csv.DictReader((output / "weekday.csv").open(newline="")))
        self.assertEqual(rows[0]["pagi"], "")
        self.assertEqual(rows[2]["pagi"], "0")
        retention = json.loads((output / "batch_retention_manifest.json").read_text())
        self.assertTrue(all(batch.sha256_file(output / artifact["path"]) == artifact["sha256"] for artifact in retention["artifacts"]))

    def test_synthetic_fixture_cannot_authorize_model_execution(self):
        path = self.root / "manifest.json"; path.write_text(json.dumps(self.manifest))
        profile = self.root / "profile.json"; profile.write_text("{}")
        with self.assertRaisesRegex(batch.BatchContractError, "Synthetic fixtures"):
            batch.run_batch(path, profile, self.root / "output", repo_root=self.root)

    def test_cache_requires_explicit_execution_mode(self):
        with self.assertRaisesRegex(batch.BatchContractError, "explicit verified_cache_replay"):
            batch.configured_execution_mode({"retained_cache": {"SYNTHETIC": True}})
        self.assertEqual(batch.configured_execution_mode({}), "new_inference")

    def test_cache_mode_requires_descriptor(self):
        with self.assertRaisesRegex(batch.BatchContractError, "retained_cache descriptor"):
            batch.configured_execution_mode({"execution_mode": "verified_cache_replay"})

    def _cache_video(self):
        video = copy.deepcopy(self.manifest["videos"][0])
        video.update(execution_mode="verified_cache_replay", source_path="synthetic.mp4", geometry_path="synthetic-geometry.json")
        video["observed_metadata"].update(fps=10)
        video["retained_cache"] = {"records_path": "synthetic-cache.jsonl.gz", "cache_identity": copy.deepcopy(self.results[0]["source_identity"]),
                                   "cache_provenance": {"SYNTHETIC_TEST_FIXTURE": True}}
        return video

    def test_cache_route_does_not_load_gpu_or_run_new_inference(self):
        fake = Mock()
        output = self.root / "cache-output"; output.mkdir()
        fake.replay_full_video_cache.return_value = copy.deepcopy(self.results[0])
        fake.render_annotated_video.return_value = {"claim_type": "SYNTHETIC_MOCK_NOT_REAL_VIDEO"}
        with patch.object(batch, "_module", return_value=fake):
            result = batch._run_configured_video(self._cache_video(), {}, output, repo_root=self.root)
        fake.replay_full_video_cache.assert_called_once()
        fake.render_annotated_video.assert_called_once()
        fake.run_full_video.assert_not_called()
        self.assertEqual(result["execution_kind"], "CACHE_REPLAY_NO_NEW_INFERENCE")

    def test_invalid_cache_does_not_fall_back_to_inference(self):
        fake = Mock(); fake.replay_full_video_cache.side_effect = ValueError("SYNTHETIC invalid donor proof")
        with patch.object(batch, "_module", return_value=fake):
            with self.assertRaisesRegex(ValueError, "invalid donor proof"):
                batch._run_configured_video(self._cache_video(), {}, self.root / "bad-cache", repo_root=self.root)
        fake.run_full_video.assert_not_called()
        fake.render_annotated_video.assert_not_called()

    def test_cache_from_foreign_video_rejected_before_replay(self):
        fake = Mock(); video = self._cache_video()
        video["retained_cache"]["cache_identity"]["video_sha256"] = _sha("SYNTHETIC foreign")
        with patch.object(batch, "_module", return_value=fake):
            with self.assertRaisesRegex(batch.BatchContractError, "Cache source/geometry"):
                batch._run_configured_video(video, {}, self.root / "foreign", repo_root=self.root)
        fake.replay_full_video_cache.assert_not_called()
        fake.run_full_video.assert_not_called()

    def test_recursive_retention_binds_per_video_outputs(self):
        output = self.root / "recursive-export"; (output / "video1").mkdir(parents=True)
        (output / "video1" / "synthetic-proof.json").write_text('{"evidence_kind":"SYNTHETIC_TEST_FIXTURE"}')
        batch.write_batch_outputs(output, self._report())
        artifacts = json.loads((output / "batch_retention_manifest.json").read_text())["artifacts"]
        self.assertIn("video1/synthetic-proof.json", {item["path"] for item in artifacts})

    def test_preparation_retains_unknown_dataset_without_traffic_tables(self):
        from phase_8_manifest_helpers import make_batch_manifest
        manifest_path = self.root / "unfilled.json"; manifest_path.write_text(json.dumps(make_batch_manifest()))
        profile_path = self.root / "profile.json"; profile_path.write_text(json.dumps(pipeline.make_processing_profile(REPO_ROOT)))
        preparation = batch.prepare_batch(manifest_path, repo_root=REPO_ROOT, dataset_root=self.root / "UNAVAILABLE_DATASET")
        guards = {name: {"evidence_kind": "SYNTHETIC_TEST_FIXTURE", "successful": True, "tests_run": 1}
                  for name in ("phase_8_manifest_tests", "phase_8_pipeline_tests", "phase_8_batch_tests", "phase_8_review_tests")}
        report = batch.write_preparation_outputs(preparation, guards, manifest_path, profile_path, self.root / "prepare", repo_root=REPO_ROOT,
                                                notebook_path="notebooks/08_end_to_end_batch.ipynb")
        output = Path(report["output_directory"])
        self.assertIsNone(report["discovered_video_count"])
        self.assertFalse(report["new_model_inference_executed"])
        self.assertFalse(report["traffic_result_created"])
        self.assertFalse((output / "weekday.csv").exists())
        manifest = batch._read_json(output / "retention_manifest.json")
        self.assertTrue(all(batch.sha256_file(output / row["path"]) == row["sha256"] for row in manifest["artifacts"]))
        self.assertEqual((output / "input_manifest.json").read_bytes(), manifest_path.read_bytes())

    def test_preparation_rejects_failed_guard(self):
        with self.assertRaisesRegex(batch.BatchContractError, "four Phase8 software"):
            batch.write_preparation_outputs({"mode": "prepare", "execution_kind": "NO_MODEL_EXECUTION"}, {}, "unused", "unused", self.root / "unused")

    def test_unavailable_gpu_probe_is_unknown_not_zero(self):
        with patch.object(batch.shutil, "which", return_value=None):
            runtime = batch.discover_runtime()
        self.assertIsNone(runtime["available_gpu_count"])
        self.assertIn("UNKNOWN", runtime["gpu_probe_status"])
        self.assertIn("NOT_PYTORCH_CUDA", runtime["gpu_visibility_semantics"])

    def test_successful_empty_gpu_query_records_observed_zero(self):
        completed = Mock(returncode=0, stdout="")
        with patch.object(batch.shutil, "which", return_value="SYNTHETIC_NVIDIA_SMI"), patch.object(batch.subprocess, "run", return_value=completed):
            runtime = batch.discover_runtime()
        self.assertEqual(runtime["available_gpu_count"], 0)

    def _research_metadata_fixture(self):
        import phase_8_manifest_helpers as manifest_helper
        (self.root / "notebooks").symlink_to(REPO_ROOT / "notebooks", target_is_directory=True)
        (self.root / "docs").symlink_to(REPO_ROOT / "docs", target_is_directory=True)
        self.manifest["claim_type"] = "SYNTHETIC_TEST_FIXTURE_NOT_REAL_DATASET"
        self.manifest["location"].update(store_name=None, latitude=None, longitude=None)
        self.manifest["execution_purpose"] = manifest_helper.RESEARCH_UNKNOWN_LOCATION_PURPOSE
        review = {"schema_version": "phase8_location_metadata_review_v1",
            "claim_type": "SYNTHETIC_TEST_FIXTURE_NOT_REAL_DATASET", "store_code": "SYNTHETIC",
            "unknown_fields": ["store_name", "latitude", "longitude"], "user_reply": "belum diketahui",
            "authorization": "CONTINUE_RESEARCH_WITH_UNKNOWN_LOCATION_METADATA", "reviewer": "SYNTHETIC_TEST_FIXTURE",
            "reviewed_at": "2026-10-15T00:00:00Z",
            "source_video_sha256_by_slot": {video["slot_id"]: video["source_sha256"] for video in self.manifest["videos"]}}
        path = self.root / "location_review.json"; path.write_text(json.dumps(review))
        self.manifest["location_metadata_review"] = {"path": path.name, "sha256": batch.sha256_file(path)}
        return path

    def test_research_acknowledgement_retains_null_facts_and_counts(self):
        self._research_metadata_fixture()
        report = batch.aggregate_batch(self.manifest, self.results, repo_root=self.root)
        self.assertTrue(report["research_only"])
        self.assertFalse(report["business_metadata_complete"])
        self.assertFalse(report["business_result_complete"])
        self.assertEqual(report["unknown_location_fields"], ["store_name", "latitude", "longitude"])
        self.assertEqual(report["location_metadata_status"], "UNKNOWN_DECLARED_RESEARCH_ONLY")
        self.assertEqual(report["status"], "completed_research_snapshots_pending_audit")
        self.assertEqual(report["accepted_observed_event_count"], 8)
        self.assertTrue(all(row["location"]["latitude"] is None and row["research_only"] for row in report["per_video"]))
        original = batch._read_json(self.results[0]["snapshot"]["events_path"])
        self.assertNotIn("location", original[0]["source_identity"])
        output = batch.write_batch_outputs(self.root / "research-output", report)
        coverage = batch._read_json(output / "coverage.json")
        self.assertIsNone(coverage["location"]["latitude"])
        self.assertFalse(coverage["business_metadata_complete"])

    def test_research_partial_failure_preserves_null_table_and_status(self):
        self._research_metadata_fixture()
        self.results[0] = {"video_id": "weekday_pagi", "status": "failed", "error": {"message": "SYNTHETIC failure"}}
        report = batch.aggregate_batch(self.manifest, self.results, repo_root=self.root)
        self.assertEqual(report["status"], "incomplete_research_batch")
        self.assertIsNone(report["tables"]["weekday"][1]["pagi"])
        self.assertIsNone(report["complete_batch_accepted_total"])
        self.assertIsNone(report["location"]["longitude"])

    def test_research_acknowledgement_cannot_invent_coordinates(self):
        self._research_metadata_fixture()
        self.manifest["location"]["latitude"] = 0
        with self.assertRaisesRegex(batch.BatchContractError, "acknowledgement invalid"):
            batch.aggregate_batch(self.manifest, self.results, repo_root=self.root)

    def test_research_acknowledgement_for_different_sources_rejected(self):
        path = self._research_metadata_fixture()
        review = json.loads(path.read_text()); review["source_video_sha256_by_slot"]["weekday_pagi"] = _sha("foreign source")
        path.write_text(json.dumps(review)); self.manifest["location_metadata_review"]["sha256"] = batch.sha256_file(path)
        with self.assertRaisesRegex(batch.BatchContractError, "acknowledgement invalid"):
            batch.aggregate_batch(self.manifest, self.results, repo_root=self.root)

    def test_complete_metadata_is_derived_not_caller_claimed(self):
        context = batch._business_context(self.manifest, REPO_ROOT)
        self.assertTrue(context["business_metadata_complete"])
        self.assertFalse(context["research_only"])
        self.manifest["business_metadata_complete"] = True
        self.manifest["location"]["store_name"] = None
        context = batch._business_context(self.manifest, REPO_ROOT)
        self.assertFalse(context["business_metadata_complete"])
        self.assertEqual(context["unknown_location_fields"], ["store_name"])


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BatchContracts)
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    return {"evidence_kind": "SYNTHETIC_TEST_FIXTURE", "claim_type": "SOFTWARE_CONTRACT_TESTS_NOT_REAL_TRAFFIC_RESULTS",
            "tests_run": result.testsRun, "tests_passed": result.testsRun - len(result.failures) - len(result.errors),
            "successful": result.wasSuccessful(), "failures": [{"test": str(test), "traceback": trace} for test, trace in result.failures],
            "errors": [{"test": str(test), "traceback": trace} for test, trace in result.errors], "log": output.getvalue()}


if __name__ == "__main__":
    report = run_tests()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["successful"] else 1)
