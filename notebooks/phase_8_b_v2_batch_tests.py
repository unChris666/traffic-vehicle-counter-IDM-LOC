"""B v2 transport/source guards and a real synthetic cache-to-ledger replay."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import phase_8_b_v2_batch as batch


IDENTITY = {"video_sha256": "1" * 64, "records_sha256": "2" * 64,
    "geometry_sha256": "3" * 64, "width": 100, "height": 100,
    "variant": "raw", "parent_run_id": "synthetic-source-not-actual-video"}
POLICY = {"line_margin_half_width_px": 25, "timeout_frames": 60,
    "timeout_clock": "last_observed_origin", "category_policy": "band_majority_ties_pending"}


def fixture(frame, x=20):
    detection = {"class_name": "car", "class_id": 2, "confidence": .9,
                 "bbox_xyxy_pixels": [x - 2, 40, x + 2, 50]}
    observation = {"track_id": 1, "frame_index": frame, "raw_bbox": detection["bbox_xyxy_pixels"],
        "original_detection_index": 0, "class_name": "car", "class_id": 2, "confidence": .9,
        "emitted": True, "measurement_provenance": "retained_phase_8_detection"}
    return {**IDENTITY, "frame_index": frame, "raw_detections": [detection], "emitted_tracks": [observation]}


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path = self.root / "records.jsonl.gz"

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, rows):
        with gzip.open(self.path, "wt") as stream:
            for row in rows:
                stream.write(json.dumps(row) + "\n")

    def adapt(self, rows, **kwargs):
        self.write(rows)
        return list(batch.adapted_frames(self.path, IDENTITY, len(rows), **kwargs))

    def test_empty_source_frames_are_not_removed(self):
        empty = fixture(1); empty.update(raw_detections=[], emitted_tracks=[])
        rows = self.adapt([fixture(0), empty, fixture(2)])
        self.assertEqual([r["frame_index"] for r in rows], [0, 1, 2])
        self.assertEqual(rows[1]["observations"], [])

    def test_source_links_preserved_and_known_unit_local_conflict_attached(self):
        row = fixture(0)
        output = self.adapt([row], relationships={"unit_by_track": {1: "known:1,2"},
            "identity_conflicts_by_frame": {0: {1}}})[0]["observations"][0]
        self.assertEqual(output["raw_bbox"], row["emitted_tracks"][0]["raw_bbox"])
        self.assertEqual(output["unit_id"], "known:1,2")
        self.assertTrue(output["identity_conflict"])
        self.assertNotIn("observed", row["emitted_tracks"][0])

    def test_broken_raw_link_rejected(self):
        row = fixture(0); row["emitted_tracks"][0]["raw_bbox"] = [1, 2, 3, 4]
        with self.assertRaisesRegex(ValueError, "original detection"):
            self.adapt([row])

    def test_foreign_source_rejected(self):
        row = fixture(0); row["video_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "identity"):
            self.adapt([row])

    def test_prediction_cannot_become_measured_vehicle(self):
        row = fixture(0); row["emitted_tracks"][0]["emitted"] = False
        with self.assertRaisesRegex(ValueError, "measured emitted"):
            self.adapt([row])

    def test_duplicate_detection_link_rejected(self):
        row = fixture(0); row["emitted_tracks"].append(deepcopy(row["emitted_tracks"][0]))
        row["emitted_tracks"][1]["track_id"] = 2
        with self.assertRaisesRegex(ValueError, "Repeated"):
            self.adapt([row])

    def test_omitted_frame_and_truncated_cache_rejected(self):
        with self.assertRaisesRegex(ValueError, "continuous"):
            self.adapt([fixture(0), fixture(2)])
        self.write([fixture(0)])
        with self.assertRaisesRegex(ValueError, "frame count"):
            list(batch.adapted_frames(self.path, IDENTITY, 2))

    def test_nonvehicle_component_does_not_enter_counting(self):
        row = fixture(0)
        row["raw_detections"][0].update(class_name="person", class_id=0)
        row["emitted_tracks"][0].update(class_name="person", class_id=0)
        self.assertEqual(self.adapt([row])[0]["observations"], [])

    def relation(self, first, second, *, status="SUPPORTED", kind="SAME_VEHICLE"):
        return {"type": kind, "status": status, "first_track_id": first, "second_track_id": second,
            "relation_id": f"r:{first}:{second}:{status}", "features": {"common_frame_indices": [1, 2, 3]}}

    def relations(self, rows):
        path = self.root / "relations.json.gz"
        with gzip.open(path, "wt") as stream:
            json.dump(rows, stream)
        return batch.retained_relationships(path)

    def test_positive_duplicate_pair_groups_without_proximity_inference(self):
        value = self.relations([self.relation(1, 2)])
        self.assertEqual(value["unit_by_track"][1], value["unit_by_track"][2])

    def test_transitive_chain_is_not_a_duplicate_clique(self):
        self.assertEqual(self.relations([self.relation(1, 2), self.relation(2, 3)])["unit_by_track"], {})

    def test_unresolved_relation_stays_frame_local_and_prevents_pair_merge(self):
        value = self.relations([self.relation(1, 2), self.relation(1, 2, status="UNRESOLVED")])
        self.assertEqual(value["unit_by_track"], {})
        self.assertEqual(value["identity_conflicts_by_frame"][2], {1, 2})
        self.assertNotIn(0, value["identity_conflicts_by_frame"])

    def test_rider_mapping_uses_only_retained_support_frames(self):
        value = self.relations([self.relation(7, 1, kind="COMPONENT_OF")])
        self.assertEqual(value["component_links"][0]["vehicle_track_id"], 1)
        self.assertEqual(value["component_links"][0]["component_track_id"], 7)
        self.assertEqual(value["component_links"][0]["support_frames"], [1, 2, 3])
        self.assertEqual(value["unit_by_track"], {})

    def test_traversal_and_changed_geometry_bytes_rejected(self):
        with self.assertRaises(ValueError):
            batch._bound(self.root, "../escape.json", "0" * 64)
        local = self.root / "geometry.json"; local.write_text("{}")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            batch._bound(self.root, "geometry.json", "0" * 64)

    def prepared(self):
        self.write([fixture(0, 20), fixture(1, 50), fixture(2, 80)])
        geo = self.root / "geometry.json"
        geo.write_text(json.dumps({"normalized": {"line": {"P1": [.5, 0], "P2": [.5, 1]},
            "side_a_polygon": [[0, 0], [.4, 0], [.4, 1], [0, 1]],
            "side_b_polygon": [[.6, 0], [1, 0], [1, 1], [.6, 1]]}}))
        relations = self.root / "relations.json"; relations.write_text("[]")
        original = self.root / "original"; original.mkdir()
        job = {"video_id": "weekday_pagi", "b_v2_geometry_path": geo, "b_v2_source_identity": IDENTITY,
            "paths": {"records": self.path, "relations": relations}, "metadata": {"frame_count": 3, "fps": 30},
            "expected_pivot": {"accepted_total": 0}, "expected_pending": 0}
        return {"jobs": [job], "policy": POLICY, "policy_sha256": "a" * 64,
            "geometry_manifest_sha256": "b" * 64, "source_run_root": original,
            "selected_video_ids": ["weekday_pagi"], "all_eight_selected": False}

    def test_actual_synthetic_cache_to_ledger_batch_replay(self):
        with patch.object(batch, "prepare_b_v2_batch", return_value=self.prepared()):
            report = batch.run_b_v2_batch(repo_root=self.root, output_root=self.root / "outputs",
                run_id="synthetic", render=False, progress=None)
        self.assertTrue(report["all_selected_completed"])
        self.assertFalse(report["all_eight_completed"])
        self.assertEqual(report["operational_total"], 1)
        self.assertEqual(report["frames_processed"], 3)
        self.assertTrue((Path(report["output_directory"]) / "retention_manifest.json").is_file())

    def test_failed_replay_preserves_partial_and_cannot_claim_completion(self):
        with patch.object(batch, "prepare_b_v2_batch", return_value=self.prepared()), \
             patch("phase_8_b_v2_counting.replay_frames", side_effect=ValueError("fixture failure")):
            with self.assertRaisesRegex(ValueError, "fixture failure"):
                batch.run_b_v2_batch(repo_root=self.root, output_root=self.root / "outputs",
                    run_id="failed", render=False, progress=None)
        report = json.loads((self.root / "outputs/failed/batch_report.json").read_text())
        self.assertEqual(report["status"], "failed_or_partial")
        self.assertFalse(report["all_eight_completed"])
        self.assertTrue((self.root / "outputs/failed/retention_manifest.json").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
