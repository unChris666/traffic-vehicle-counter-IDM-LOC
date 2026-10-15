"""Synthetic review guards only; no actual video labels or GPU execution.

Tests inherit the frozen review implementation's category, gap, BC, endpoint,
identity, duplicate and return guards, then exercise fresh-scope and exact native
raw-photo binding. File-writing fixtures explicitly bypass actual-source loading
so they cannot be mistaken for retained video evidence.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

import phase_8_review_helpers as review


ROOT = Path(__file__).resolve().parents[1]
ACTUAL_PILOT = ROOT / "docs/evidence/phase_8/cache_pilot/TOR3-MALAM-full-scope-v1"


def _fixture(repo, directory):
    """Capture the old synthetic fixture, preserving its existing hard guards."""
    module, _, _ = review.load_review_adapter(repo)
    captured = []
    original = module.build_reviewed_snapshot

    def capture(*args, **kwargs):
        if not captured:
            captured.append((deepcopy(args), kwargs["geometry"]))
        return original(*args, **kwargs)

    module.build_reviewed_snapshot = capture
    inherited = module.self_test(repo)
    args, geometry = captured[0]
    candidates, episodes, events, config, reviews = args
    root = Path(directory)
    (root / "notebooks").symlink_to(Path(repo) / "notebooks", target_is_directory=True)
    (root / "docs").symlink_to(Path(repo) / "docs", target_is_directory=True)
    photo = root / "native_raw.png"
    rgb = bytes((x * 3 + y * 7) % 256 for y in range(100) for x in range(300))
    Image.frombytes("RGB", (100, 100), rgb).save(photo)
    bgr = bytearray(rgb)
    bgr[0::3], bgr[2::3] = bgr[2::3], bgr[0::3]
    pixel_hash = hashlib.sha256(bgr).hexdigest()
    identity = config["input_identity"]
    rawrefs = [{"kind": "native_raw_source_frame", "path": "native_raw.png",
        "sha256": review.sha256_file(photo), "source_video_sha256": identity["video_sha256"],
        "width": 100, "height": 100, "frame_index": frame, "frame_indices": [frame],
        "frame_bgr_sha256": pixel_hash, "observation": "SYNTHETIC software fixture, not actual video"}
        for frame in (0, 1, 2)]
    reviews["decisions"][0]["evidence"] = rawrefs
    run = root / "machine_fixture"
    run.mkdir()
    review._write_json(run / "counting_configuration.json", config)
    review._write_json(run / "counting_report.json", {"claim_type": "SYNTHETIC_FIXTURE_NOT_ACTUAL_EXECUTION"})
    for name, data in (("episodes.json.gz", episodes), ("machine_passage_decisions.json.gz", candidates),
                       ("machine_count_events.json.gz", events)):
        review._write_gzip(run / name, data)
    review._write_json(run / "machine_aggregate.json", {"total": 0})
    review._write_json(run / "retention_manifest.json", {"phase": 8, "artifacts": [
        {"path": path.name, "sha256": review.sha256_file(path), "bytes": path.stat().st_size}
        for path in sorted(run.iterdir()) if path.is_file()]})
    bindings = review.verify_machine_manifest(run)
    binding = {"schema_version": review.SCHEMA_VERSION, "source_run_id": "p8_synthetic_fixture",
        "source_identity": deepcopy(identity), "source_snapshot_kind": "machine", "scope": "full_video",
        "source_machine_decisions_sha256": bindings["machine_passage_decisions.json.gz"],
        "source_machine_events_sha256": bindings["machine_count_events.json.gz"],
        "source_episodes_sha256": bindings["episodes.json.gz"],
        "source_configuration_sha256": bindings["counting_configuration.json"],
        "source_machine_manifest_sha256": bindings["retention_manifest.json"],
        "source_processing_profile_sha256": "e" * 64}
    reviews.update(deepcopy(binding))
    cache = root / "cache_not_video.txt"
    cache.write_text("SYNTHETIC no detector or decoder execution\n", encoding="utf-8")
    # File snapshot tests still enforce postprocessing cache-byte immutability.
    identity["records_sha256"] = review.sha256_file(cache)
    for episode in episodes:
        episode["source_identity"]["records_sha256"] = identity["records_sha256"]
    for candidate in candidates:
        for field in ("origin_observation",):
            candidate["diagnostic"][field]["metadata"]["records_sha256"] = identity["records_sha256"]
        diagnostic = candidate["diagnostic"]
        diagnostic["metadata"]["records_sha256"] = identity["records_sha256"]
        for obs in diagnostic["confirmation_observations"]:
            obs["metadata"]["records_sha256"] = identity["records_sha256"]
        for obs in (diagnostic["crossing_evidence"]["start_observation"], diagnostic["crossing_evidence"]["end_observation"]):
            obs["metadata"]["records_sha256"] = identity["records_sha256"]
    binding["source_identity"] = deepcopy(identity)
    reviews["source_identity"] = deepcopy(identity)
    config["scope"] = {"track_ids": None, "association_frame_windows": None}
    review._write_json(run / "counting_configuration.json", config)
    review._write_gzip(run / "episodes.json.gz", episodes)
    review._write_gzip(run / "machine_passage_decisions.json.gz", candidates)
    _, _, _, aggregate_events = module.geometry_imports(repo)
    review._write_json(run / "machine_aggregate.json", aggregate_events([]))
    review._write_json(run / "retention_manifest.json", {"phase": 8, "artifacts": [
        {"path": path.name, "sha256": review.sha256_file(path), "bytes": path.stat().st_size}
        for path in sorted(run.iterdir()) if path.is_file() and path.name != "retention_manifest.json"]})
    bindings = review.verify_machine_manifest(run)
    for field, name in (("source_machine_decisions_sha256", "machine_passage_decisions.json.gz"),
        ("source_episodes_sha256", "episodes.json.gz"), ("source_configuration_sha256", "counting_configuration.json"),
        ("source_machine_manifest_sha256", "retention_manifest.json")):
        binding[field] = bindings[name]
    reviews.update(deepcopy(binding))
    source = {"run": run, "config": config, "report": {"run_id": binding["source_run_id"], "source_frame_count": 3},
        "identity": identity, "bindings": bindings, "binding": binding, "episodes": episodes,
        "decisions": candidates, "events": events, "geometry": geometry, "geometry_path": root / "unused_geometry.json",
        "donors": {frame: pixel_hash for frame in (0, 1, 2)}, "records_path": cache}
    return source, reviews, inherited


class ReviewGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir="/tmp")
        cls.root = Path(cls.temp.name)
        cls.source, cls.reviews, cls.inherited = _fixture(ROOT, cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_inherited_geometry_category_identity_duplicate_return_guards(self):
        self.assertEqual(self.inherited["failed"], 0)
        self.assertGreaterEqual(self.inherited["passed"], 24)

    def test_exact_one_production_guard_adapter_and_immutable_original(self):
        _, adapted, proof = review.load_review_adapter(ROOT)
        self.assertEqual(proof["production_substitution_count"], 1)
        self.assertEqual(review.sha256_file(ROOT / review.BASE_PATH), review.BASE_SHA256)
        self.assertEqual(adapted.replace(review.NEW_GUARD, review.OLD_GUARD, 1), (ROOT / review.BASE_PATH).read_text())

    def test_exact_native_png_bgr_matches_cache_donor(self):
        review._verify_raw_photos(self.reviews, self.source, self.root)

    def test_raw_rgb_hash_cannot_be_substituted_for_bgr(self):
        changed = deepcopy(self.reviews)
        with Image.open(self.root / "native_raw.png") as image:
            wrong = hashlib.sha256(image.tobytes()).hexdigest()
        changed["decisions"][0]["evidence"][0]["frame_bgr_sha256"] = wrong
        with self.assertRaises(ValueError):
            review._verify_raw_photos(changed, self.source, self.root)

    def test_crop_cannot_supply_required_native_frames(self):
        changed = deepcopy(self.reviews)
        for item in changed["decisions"][0]["evidence"]:
            item["kind"] = "cropped_contact_sheet"
        with self.assertRaisesRegex(ValueError, "exact native raw"):
            review._verify_raw_photos(changed, self.source, self.root)

    def test_missing_origin_evidence_rejected(self):
        changed = deepcopy(self.reviews)
        changed["decisions"][0]["evidence"] = changed["decisions"][0]["evidence"][1:]
        with self.assertRaises(ValueError):
            review._verify_raw_photos(changed, self.source, self.root)

    def test_wrong_photo_video_frame_size_or_pixels_rejected(self):
        for field, value in (("source_video_sha256", "f" * 64), ("frame_index", 999),
                             ("width", 960), ("height", 540), ("frame_indices", [0, 1]),
                             ("frame_bgr_sha256", "f" * 64), ("sha256", "f" * 64)):
            with self.subTest(field=field):
                changed = deepcopy(self.reviews)
                changed["decisions"][0]["evidence"][0][field] = value
                with self.assertRaises(ValueError):
                    review._verify_raw_photos(changed, self.source, self.root)

    def test_annotated_native_sized_png_still_requires_raw_pixel_hash(self):
        annotated = self.root / "annotated.png"
        with Image.open(self.root / "native_raw.png") as image:
            image.putpixel((50, 50), (255, 0, 0)); image.save(annotated)
        changed = deepcopy(self.reviews)
        changed["decisions"][0]["evidence"][0].update(path="annotated.png", sha256=review.sha256_file(annotated))
        with self.assertRaisesRegex(ValueError, "donor pixels"):
            review._verify_raw_photos(changed, self.source, self.root)

    def test_cache_without_pixel_donor_cannot_authorize_positive_review(self):
        source = deepcopy(self.source); source["donors"][0] = None
        with self.assertRaisesRegex(ValueError, "donor pixels"):
            review._verify_raw_photos(self.reviews, source, self.root)

    def test_fresh_full_scope_bindings_accepted(self):
        review._validate_review_bindings(self.reviews, self.source)

    def test_stale_historical_or_other_profile_run_cache_configuration_rejected(self):
        for field, value in (("schema_version", "phase7_explicit_physical_review_input_v1"),
            ("source_run_id", "20261014T062858_002323Z"), ("scope", "five_windows"),
            ("source_machine_decisions_sha256", "f" * 64), ("source_machine_events_sha256", "f" * 64),
            ("source_episodes_sha256", "f" * 64), ("source_configuration_sha256", "f" * 64),
            ("source_machine_manifest_sha256", "f" * 64), ("source_processing_profile_sha256", "f" * 64),
            ("source_snapshot_kind", "reviewed")):
            with self.subTest(field=field):
                changed = deepcopy(self.reviews); changed[field] = value
                with self.assertRaisesRegex(ValueError, "Stale/mixed-scope"):
                    review._validate_review_bindings(changed, self.source)

    def test_mismatched_source_video_cache_or_geometry_hash_rejected(self):
        for field in ("video_sha256", "records_sha256", "geometry_sha256"):
            changed = deepcopy(self.reviews); changed["source_identity"][field] = "f" * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                review._validate_review_bindings(changed, self.source)

    def test_empty_template_keeps_unreviewed_queue_without_confirmations(self):
        with patch.object(review, "_load_machine", return_value=self.source):
            template = review.make_review_template(self.source["run"], repo_root=self.root)
        self.assertEqual(template["decisions"], [])
        self.assertEqual(len(template["review_queue"]), 1)
        self.assertIsNone(template["review_queue"][0]["disposition"])
        self.assertFalse(template["review_queue"][0]["identity_confirmed"])

    def test_manifest_tampering_duplicate_entry_and_path_escape_rejected(self):
        source = self.root / "manifest_checks"; source.mkdir(exist_ok=True)
        for file in self.source["run"].iterdir():
            (source / file.name).write_bytes(file.read_bytes())
        manifest = review._json(source / "retention_manifest.json")
        changed = deepcopy(manifest); changed["artifacts"].append(deepcopy(changed["artifacts"][0]))
        review._write_json(source / "retention_manifest.json", changed)
        with self.assertRaises(ValueError): review.verify_machine_manifest(source)
        changed = deepcopy(manifest); changed["artifacts"][0]["path"] = "../native_raw.png"
        review._write_json(source / "retention_manifest.json", changed)
        with self.assertRaises(ValueError): review.verify_machine_manifest(source)
        review._write_json(source / "retention_manifest.json", manifest)
        (source / "episodes.json.gz").write_bytes(b"tampered")
        with self.assertRaises(ValueError): review.verify_machine_manifest(source)

    def test_actual_source_loader_rejects_synthetic_machine_report(self):
        with self.assertRaisesRegex(ValueError, "completed full-video"):
            review._load_machine(self.source["run"], self.root)

    def test_namespaces_keep_rider_category_gap_and_duplicate_guards(self):
        module, _, _ = review.load_review_adapter(ROOT)
        for namespace in review.MEASUREMENT_NAMESPACES:
            candidates, episodes = deepcopy(self.source["decisions"]), deepcopy(self.source["episodes"])
            def replace(value):
                if isinstance(value, dict):
                    if "measurement_provenance" in value: value["measurement_provenance"] = namespace
                    for item in value.values(): replace(item)
                elif isinstance(value, list):
                    for item in value: replace(item)
            replace(candidates); replace(episodes)
            result = module.build_reviewed_snapshot(candidates, episodes, [], self.source["config"], self.reviews,
                repo=self.root, geometry=self.source["geometry"])
            self.assertEqual(result["aggregate"]["total"], 1)
            for mutate in (lambda c, e: c[0]["hard_block_reasons"].append("AMBIGUOUS_GAP"),
                           lambda c, e: e[0].update(family="person"),
                           lambda c, e: c[0].update(category="car")):
                bad, bad_episodes = deepcopy(candidates), deepcopy(episodes); mutate(bad, bad_episodes)
                with self.subTest(namespace=namespace), self.assertRaises(ValueError):
                    module.build_reviewed_snapshot(bad, bad_episodes, [], self.source["config"], self.reviews,
                        repo=self.root, geometry=self.source["geometry"])

    def test_empty_overlay_writes_pending_snapshot_and_does_not_append_machine_events(self):
        review_path = self.root / "empty_review.json"
        empty = deepcopy(self.reviews); empty["decisions"] = []
        review._write_json(review_path, empty)
        output = self.root / "empty_review_output"
        with patch.object(review, "_load_machine", return_value=self.source):
            result = review.apply_review(self.source["run"], review_path, output, repo_root=self.root)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["snapshot"]["kind"], "reviewed")
        self.assertEqual(result["snapshot"]["run_id"], self.source["report"]["run_id"])
        self.assertFalse(result["report"]["formal_ground_truth"])
        self.assertFalse(result["report"]["geometry_resolver_detector_tracker_encoder_rerun"])
        self.assertEqual(review._array(output / "resolved_decisions.json.gz")[0]["status"], "pending_review")
        with patch.object(review, "_load_machine", return_value=self.source), self.assertRaisesRegex(ValueError, "overwrite"):
            review.apply_review(self.source["run"], review_path, output, repo_root=self.root)

    def _machine_snapshot(self):
        result = {"kind": "machine", "run_id": self.source["report"]["run_id"], "source_identity": self.source["identity"]}
        for prefix, name in (("configuration", "counting_configuration.json"),
            ("events", "machine_count_events.json.gz"), ("decisions", "machine_passage_decisions.json.gz")):
            path = self.source["run"] / name
            result[prefix + "_path"] = str(path); result[prefix + "_sha256"] = review.sha256_file(path)
        return result

    def test_selected_machine_snapshot_exact_original_and_pending_retained(self):
        with patch.object(review, "_load_machine", return_value=self.source):
            validated = review.validate_selected_snapshot(self._machine_snapshot(), repo_root=self.root)
        self.assertEqual(validated["snapshot_kind"], "machine")
        self.assertEqual(validated["aggregate"]["total"], 0)
        self.assertFalse(validated["model_geometry_resolver_rerun"])

    def test_selected_machine_stale_run_and_hash_rejected(self):
        for field, bad in (("run_id", "p8_old_run"), ("events_sha256", "f" * 64)):
            snapshot = self._machine_snapshot(); snapshot[field] = bad
            with self.subTest(field=field), patch.object(review, "_load_machine", return_value=self.source), self.assertRaises(ValueError):
                review.validate_selected_snapshot(snapshot, repo_root=self.root)

    def test_selected_machine_forged_decisions_rejected_even_with_updated_descriptor_hash(self):
        decisions = deepcopy(self.source["decisions"]); decisions[0]["status"] = "accepted"
        path = self.root / "forged_decisions.json.gz"; review._write_gzip(path, decisions)
        snapshot = self._machine_snapshot(); snapshot.update(decisions_path=str(path), decisions_sha256=review.sha256_file(path))
        with patch.object(review, "_load_machine", return_value=self.source), self.assertRaisesRegex(ValueError, "retained machine"):
            review.validate_selected_snapshot(snapshot, repo_root=self.root)

    def test_selected_reviewed_snapshot_guarded_reconstruction(self):
        path = self.root / "positive_review.json"; review._write_json(path, self.reviews)
        output = self.root / "positive_selected_output"
        with patch.object(review, "_load_machine", return_value=self.source):
            result = review.apply_review(self.source["run"], path, output, repo_root=self.root)
            validated = review.validate_selected_snapshot(result["snapshot"], repo_root=self.root)
        self.assertEqual(validated["aggregate"]["total"], 1)
        self.assertTrue(validated["events"][0]["manual_review_applied"])
        self.assertFalse(validated["events"][0]["automatic_acceptance"])
        self.assertTrue(validated["events"][0]["policy_identity"].startswith("cfg6br_"))

    def test_selected_reviewed_artifact_tamper_cannot_pass_reconstruction(self):
        path = self.root / "review_tamper_input.json"; review._write_json(path, self.reviews)
        output = self.root / "review_tamper_output"
        with patch.object(review, "_load_machine", return_value=self.source):
            result = review.apply_review(self.source["run"], path, output, repo_root=self.root)
        events = review._array(output / "accepted_events.json.gz"); events[0]["category"] = "car"
        review._write_gzip(output / "accepted_events.json.gz", events)
        result["snapshot"]["events_sha256"] = review.sha256_file(output / "accepted_events.json.gz")
        with patch.object(review, "_load_machine", return_value=self.source), self.assertRaisesRegex(ValueError, "manifest"):
            review.validate_selected_snapshot(result["snapshot"], repo_root=self.root)

    def test_typed_manual_policy_or_sourcebc_tamper_rejected(self):
        module, _, _ = review.load_review_adapter(ROOT)
        canonical = module.build_reviewed_snapshot(self.source["decisions"], self.source["episodes"], [],
            self.source["config"], self.reviews, repo=self.root, geometry=self.source["geometry"])
        for field, bad in (("policy_identity", "cfg6b_" + "f" * 64), ("event_id", "ce6br_" + "f" * 64),
                           ("geometry_evidence", {}), ("measurement_support", [])):
            events = deepcopy(canonical["accepted_events"]); events[0][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                review._validate_typed_events(events, canonical["resolved_decisions"], self.source, module, self.root, "reviewed")

    @unittest.skipUnless(ACTUAL_PILOT.is_dir(), "Retained actual cache pilot is not bundled; no model rerun")
    def test_actual_retained_cache_loader_and_machine_snapshot_without_loader_mock(self):
        source = review._load_machine(ACTUAL_PILOT, ROOT)
        snapshot = review._json(ACTUAL_PILOT / "phase_8_snapshot.json")
        validated = review.validate_selected_snapshot(snapshot, repo_root=ROOT)
        self.assertEqual(validated["source_identity"], source["identity"])
        self.assertEqual(len(validated["events"]), len(source["events"]))
        self.assertFalse(validated["model_geometry_resolver_rerun"])

    @unittest.skipUnless(ACTUAL_PILOT.is_dir(), "Retained actual cache pilot is not bundled; no model rerun")
    def test_fresh_donor_wrong_detector_controls_rejected_without_loader_mock(self):
        # Deliberately forged wire envelope: it is expected to FAIL. No GPU
        # result, geometry approval or physical-object label is manufactured.
        original = review._json(ACTUAL_PILOT / "counting_report.json")
        parent = self.root / "forged_fresh_envelope_expected_reject"; parent.mkdir()
        run = parent / "counting"; shutil.copytree(ACTUAL_PILOT, run)
        records = parent / "track_records.jsonl.gz"
        shutil.copyfile(original["records_path"], records)
        donor = {"phase": 8, "claim_type": "SYNTHETIC_ADVERSARIAL_ENVELOPE_EXPECTED_REJECT",
            "run_id": original["source_identity"]["parent_run_id"], "execution_kind": "ACTUAL_MODEL_EXECUTION",
            "source_identity": original["source_identity"], "configuration": deepcopy(original["configuration"]),
            "source_helper_sha256": review.sha256_file(ROOT / "notebooks/phase_8_pipeline_helpers.py"),
            "inference_status": "completed", "track_records_sha256": original["source_identity"]["records_sha256"],
            "frames_processed": original["cache_provenance"]["frame_count"],
            "observed_diagnostics": {"raw_detections": 1},
            "appearance_diagnostics": {"encoder_calls": 1, "finite_nonzero_features_produced": 1},
            "cuda_execution_evidence": {"actual_cuda_execution_confirmed": True}}
        donor["configuration"]["detector"]["settings"]["conf"] = .3
        review._write_json(parent / "report.json", donor)
        review._write_json(parent / "retention_manifest.json", {"phase": 8, "artifacts": [
            {"path": file.name, "sha256": review.sha256_file(file), "bytes": file.stat().st_size}
            for file in (parent / "report.json", records)]})
        original["records_path"] = str(records)
        original["cache_provenance"] = {"source_phase": 8, "new_detector_tracker_encoder_inference": True,
            "source_report_path": str(parent / "report.json"), "measurement_provenance": "retained_phase_8_detection",
            "frame_count": original["cache_provenance"]["frame_count"]}
        review._write_json(run / "counting_report.json", original)
        manifest = review._json(run / "retention_manifest.json")
        for item in manifest["artifacts"]:
            if item["path"] == "counting_report.json":
                file = run / item["path"]; item.update(sha256=review.sha256_file(file), bytes=file.stat().st_size)
        review._write_json(run / "retention_manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "detector controls"):
            review._load_machine(run, ROOT)


def run_tests(output_json=None):
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReviewGuards)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    inherited = ReviewGuards.inherited
    report = {"phase": 8, "claim_type": "SYNTHETIC_REVIEW_GUARDS_NOT_ACTUAL_VIDEO_EVIDENCE",
        "tests_run": result.testsRun, "inherited_guard_checks": inherited["passed"],
        "failures": len(result.failures), "errors": len(result.errors), "passed": result.wasSuccessful(),
        "skipped": len(result.skipped),
        "detector_tracker_encoder_video_decoder_executed": False, "formal_ground_truth": False,
        "limits": "Native PNGs and trajectories are constructed fixtures; actual-source loading is bypassed only for file-writing fixture tests"}
    if output_json: review._write_json(output_json, report)
    if not result.wasSuccessful(): raise AssertionError("Phase8 guarded manual review test failed")
    return report


if __name__ == "__main__":
    run_tests(sys.argv[1] if len(sys.argv) > 1 else None)
