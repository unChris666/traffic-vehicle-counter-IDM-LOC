"""Actual retained-source P1 regression fixtures, not accuracy measurements."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import unittest

import phase_8_b_v7_counting as counting
from phase_5_geometry_helpers import Geometry


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "results/b_v8/verification/actual_fixture_probes_v2"


def read(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


class P1ActualSourceReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geometry = Geometry.from_draft(
            ROOT / "results/b_v8/fixtures/blocker4843/geometry.json", 640, 480)
        cls.results = {}
        cls.inputs = {}
        for name in ("blocker4843", "pedestrian54"):
            frames = read(FIXTURES / name / "reviewed_resolved_frames.json.gz")
            old = read(FIXTURES / name / "reviewed_result.json.gz")
            cls.inputs[name] = (frames, old["report"]["policy"], old["source_identity"])
            cls.results[name] = counting.replay_frames(frames, cls.geometry,
                source_identity=old["source_identity"], policy=old["report"]["policy"])

    def test_reviewed_red_passage_has_exactly_one_active_event(self):
        result = self.results["blocker4843"]
        self.assertEqual(result["aggregate"]["total"], 1)
        event = result["events"][0]
        self.assertEqual(event["category"], "motorcycle")
        self.assertEqual(event["direction"], "A_TO_B")
        self.assertEqual(event["route"], "LINE_MARGIN")

    def test_red_origin_and_destination_use_clean_separate_raw_scopes(self):
        refs = self.results["blocker4843"]["events"][0]["evidence"]["source_refs"]
        self.assertEqual({ref["track_id"] for ref in refs}, {4808, 4843})
        self.assertTrue(all(ref["frame_index"] <= 7907 if ref["track_id"] == 4808
                            else ref["frame_index"] >= 7928 for ref in refs))

    def test_blue_presence_and_old_blue_origin_do_not_generate_counts(self):
        result = self.results["blocker4843"]
        self.assertEqual(result["aggregate"]["by_route"].get("ESTIMATED_TIMEOUT", 0), 0)
        self.assertFalse(any(event["track_id"] == 4913 for event in result["events"]))
        frames = self.inputs["blocker4843"][0]
        blue = next(obs for row in frames if row["frame_index"] == 7899
                    for obs in row["observations"] if obs["track_id"] == 4843)
        red = next(obs for row in frames if row["frame_index"] == 7935
                   for obs in row["observations"] if obs["track_id"] == 4843)
        self.assertNotEqual(blue["unit_id"], red["unit_id"])
        self.assertNotEqual(blue["physical_episode_id"], red["physical_episode_id"])

    def test_occlusion_recovery_remains_inferred_without_gap_measurements(self):
        evidence = self.results["blocker4843"]["events"][0]["evidence"]
        self.assertFalse(evidence["measured_crossing"])
        self.assertTrue(any(g["from_frame"] == 7907 and g["to_frame"] == 7928
                            for g in evidence["gaps"]))
        self.assertFalse(any(7907 < r["frame_index"] < 7928 for r in evidence["source_refs"]))

    def test_crossing_anchor_remains_measured_raw_bbox_bottom_center(self):
        for result in self.results.values():
            for event in result["events"]:
                for ref in event["evidence"]["source_refs"]:
                    x1, _, x2, y2 = ref["raw_bbox"]
                    self.assertEqual(ref["point"], [(x1 + x2) / 2, y2])
                    self.assertTrue(ref["observed"] and ref["emitted"])

    def test_pedestrian_requires_actual_geometry_replay_and_bounded_role(self):
        result = self.results["pedestrian54"]
        self.assertEqual(result["aggregate"]["total"], 1)
        event = result["events"][0]
        self.assertEqual((event["category"], event["direction"]), ("pedestrian", "B_TO_A"))
        self.assertTrue(event["evidence"]["measured_crossing"])
        self.assertTrue(event["evidence"]["crossing_pairs"])
        self.assertTrue(all(ref["frame_index"] <= 140 for ref in event["evidence"]["source_refs"]))
        later = [item for row in self.inputs["pedestrian54"][0] if row["frame_index"] > 140
                 for item in row["observations"]]
        self.assertTrue(later)
        self.assertTrue(all(item["role"] == "unknown_person" for item in later))

    def test_source_replay_is_deterministic_and_does_not_mutate_frames(self):
        frames, policy, source = self.inputs["blocker4843"]
        before = deepcopy(frames)
        result = counting.replay_frames(frames, self.geometry, source_identity=source, policy=policy)
        self.assertEqual(result, self.results["blocker4843"])
        self.assertEqual(frames, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
