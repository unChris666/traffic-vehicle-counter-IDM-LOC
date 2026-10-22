"""Real-source competing-vehicle control: preserve two distinct passages."""
import gzip
import json
from pathlib import Path
import unittest

import phase_8_b_v6_identity as identity
import phase_8_b_v7_counting as counting
from phase_5_geometry_helpers import Geometry

ROOT = Path(__file__).resolve().parent.parent


def read(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


class P1CompetingVehicleControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / "results/b_v8/verification/actual_fixture_probes_v4/blocker4843"
        cls.frames = read(cls.path / "reviewed_resolved_frames.json.gz")
        old = read(cls.path / "reviewed_result.json.gz")
        geometry = Geometry.from_draft(ROOT / "results/b_v8/fixtures/blocker4843/geometry.json",640,480)
        cls.result = counting.replay_frames(cls.frames,geometry,
            source_identity=old["source_identity"],policy=old["report"]["policy"])

    def test_reviewed_red_and_distinct_foreground_both_count_once(self):
        self.assertEqual(self.result["aggregate"]["total"],2)
        self.assertEqual({e["track_id"] for e in self.result["events"]},{4798,4843})
        self.assertEqual(len({e["physical_unit_id"] for e in self.result["events"]}),2)

    def test_existing_distinct_passage_keeps_measurements_geometry_and_time(self):
        baseline=read(self.path/"baseline_result.json.gz")
        before=next(e for e in baseline["events"] if e["track_id"]==4798)
        after=next(e for e in self.result["events"] if e["track_id"]==4798)
        for key in ("category","direction","route","activation_frame","decision_frame"):
            self.assertEqual(before[key],after[key])
        witness=lambda e:[(r["frame_index"],r["track_id"],r["original_detection_index"],r["raw_bbox"])
                          for r in e["evidence"]["source_refs"]]
        self.assertEqual(witness(before),witness(after))
        self.assertTrue(after["evidence"]["measured_crossing"])

    def test_only_source_verified_distinct_proof_vetoes_false_handoff(self):
        endpoints=[next(o for row in self.frames if row["frame_index"]==frame
            for o in row["observations"] if o["track_id"]==track)
            for frame,track in ((7903,4798),(7928,4843))]
        self.assertTrue(identity._proven_distinct(*endpoints,[]))
        audit=read(self.path/"reviewed_identity_audit.json.gz")
        self.assertTrue(any(r["first_track_id"]==4798 and r["second_track_id"]==4843
            and r["vetoed_candidate_kind"]=="UNVERIFIED_ORIGIN_HANDOFF"
            for r in audit["known_distinct_constraint_audit"]))

    def test_raw_unit_label_cannot_be_upgraded_to_identity_proof_by_name_only(self):
        old=read(ROOT/"results/b_v8/verification/actual_fixture_probes_v3/blocker4843/reviewed_resolved_frames.json.gz")
        raw=next(o for row in old if row["frame_index"]==7903
            for o in row["observations"] if o["track_id"]==4798)
        self.assertEqual(identity._identity_review_proof(raw),[])

    def test_red_gap_stays_inferred_and_blue_presence_cannot_add_an_event(self):
        red=next(e for e in self.result["events"] if e["track_id"]==4843)
        self.assertFalse(red["evidence"]["measured_crossing"])
        self.assertEqual({r["track_id"] for r in red["evidence"]["source_refs"]},{4808,4843})
        self.assertFalse(any(e["track_id"]==4913 for e in self.result["events"]))
        self.assertEqual(self.result["aggregate"]["by_route"].get("ESTIMATED_TIMEOUT",0),0)


if __name__=="__main__":unittest.main(verbosity=2)
