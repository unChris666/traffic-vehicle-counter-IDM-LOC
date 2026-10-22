"""Do not confuse versioned guard IDs with changed physical source evidence."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parent.parent/"results/b_v8/review/run_result_qc.py"
spec=importlib.util.spec_from_file_location("p1_source_qc",PATH)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def relation():
    return {"relation_id":"config-A-hash","candidate_kind":"UNVERIFIED_ORIGIN_HANDOFF",
        "verified":False,"first_track_id":1,"second_track_id":2,
        "first_physical_episode_id":"context:A","second_physical_episode_id":"context:B",
        "first_support_frames":[1,2],"second_support_frames":[5,6],"gap_source_frames":3,
        "motion_provenance":"OBSERVED_FIT","identity_merged":False,
        "first_source_refs":[{"frame_index":2,"track_id":1,"original_detection_index":0,"raw_bbox":[1,2,3,4]}],
        "second_source_refs":[{"frame_index":5,"track_id":2,"original_detection_index":1,"raw_bbox":[3,4,5,6]}]}


def signature(r):return next(iter(module.source_relation_ids({"v7_handoff_relations":[r]}).values()))


class RelationSourceQC(unittest.TestCase):
    def test_different_config_hashes_can_refer_to_the_same_exact_source_constraint(self):
        a=relation();b=deepcopy(a);b["relation_id"]="config-B-hash"
        self.assertEqual(signature(a),signature(b))

    def test_changed_raw_measurement_is_not_normalized_away(self):
        a=relation();b=deepcopy(a);b["first_source_refs"][0]["raw_bbox"][0]+=1
        self.assertNotEqual(signature(a),signature(b))

    def test_changed_context_or_support_is_still_a_material_change(self):
        a=relation();b=deepcopy(a);b["first_physical_episode_id"]="other-object"
        self.assertNotEqual(signature(a),signature(b))

    def test_verified_identity_or_changed_gap_is_not_an_identifier_only_change(self):
        a=relation();b=deepcopy(a);b["verified"]=True
        self.assertNotEqual(signature(a),signature(b))


if __name__=="__main__":unittest.main(verbosity=2)
