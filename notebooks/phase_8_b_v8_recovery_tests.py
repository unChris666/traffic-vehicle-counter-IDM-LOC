"""Source-reviewed recovery must not weaken unreviewed duplicate safeguards."""
import gzip
import json
from pathlib import Path
import unittest

import phase_8_b_v7_counting as counting
from phase_5_geometry_helpers import Geometry

ROOT=Path(__file__).resolve().parent.parent


def read(p):
    data=p.read_bytes()
    return json.loads(gzip.decompress(data) if p.suffix==".gz" else data)


class ReviewedHandoffRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=ROOT/"results/b_v8/verification/actual_fixture_probes_v6/handoff_recovery"
        cls.frames=read(cls.directory/"reviewed_resolved_frames.json.gz")
        saved=read(cls.directory/"reviewed_result.json.gz")
        geometry=Geometry.from_draft(ROOT/"results/b_v8/fixtures/blocker4843/geometry.json",640,480)
        cls.result=counting.replay_frames(cls.frames,geometry,
            source_identity=saved["source_identity"],policy=saved["report"]["policy"])

    def test_positive_source_identity_recovers_one_passage_without_double_count(self):
        events=[e for e in self.result["events"] if e["physical_unit_id"]=="review:TGDI_SIANG:recovered_handoff_passage"]
        self.assertEqual(len(events),1)
        self.assertEqual({r["track_id"] for r in events[0]["evidence"]["source_refs"]},{1049,1123})
        self.assertFalse(events[0]["evidence"]["measured_crossing"])
        self.assertEqual(events[0]["route"],"LINE_MARGIN")

    def test_unreviewed_inputs_still_suppress_the_original_duplicate_pair(self):
        baseline=read(self.directory/"baseline_result.json.gz")
        self.assertFalse(any(e["track_id"] in (1049,1123) for e in baseline["events"]))
        self.assertEqual(sum(d["track_id"] in (1049,1123) for d in baseline["invalid_decisions"]),2)

    def test_later_raw_id_observations_are_not_globally_assigned_reviewed_identity(self):
        later=[o for row in self.frames if row["frame_index"]>1396
            for o in row["observations"] if o["track_id"]==1123]
        self.assertTrue(later)
        self.assertTrue(all(o["unit_id"]!="review:TGDI_SIANG:recovered_handoff_passage" for o in later))
        self.assertTrue(all(not o.get("association_verified") for o in later))

    def test_following_and_opposite_motorcycles_keep_separate_source_units(self):
        obs={o["track_id"]:o for row in self.frames if row["frame_index"]==1376 for o in row["observations"]}
        self.assertEqual(len({obs[t]["unit_id"] for t in (1070,1101,1123)}),3)
        baseline=read(self.directory/"baseline_result.json.gz")
        first=[e for e in baseline["events"] if e["track_id"]==1101]
        second=[e for e in self.result["events"] if e["track_id"]==1101]
        self.assertEqual(len(first),len(second))
        self.assertEqual(first[0]["route"],second[0]["route"])

    def test_no_missing_observation_or_synthetic_anchor_is_created(self):
        event=next(e for e in self.result["events"] if e["track_id"]==1123)
        self.assertFalse(any(1336<r["frame_index"]<1349 for r in event["evidence"]["source_refs"]))
        for ref in event["evidence"]["source_refs"]:
            x1,_,x2,y2=ref["raw_bbox"];self.assertEqual(ref["point"],[(x1+x2)/2,y2])


if __name__=="__main__":unittest.main(verbosity=2)
