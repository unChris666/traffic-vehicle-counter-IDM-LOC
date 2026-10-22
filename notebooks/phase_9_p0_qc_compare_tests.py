"""Audit comparator tests: source membership must never imply physical accuracy."""
import copy
import unittest

from phase_9_p0_qc_compare import SourceIndex, source_key, expected_case_matrix, compare_results


def ref(track=73, frame=219, index=2, box=None):
    return {"track_id": track, "frame_index": frame,
            "original_detection_index": index, "raw_bbox": box or [10.0, 20.0, 40.0, 60.0]}


def event(event_id, refs, **extra):
    return {"event_id": event_id, "category": "car", "direction": "B_TO_A",
            "evidence": {"source_refs": refs, "measured_crossing": True}, **extra}


class SourceComparisonTests(unittest.TestCase):
    def test_same_raw_id_frame_with_different_detection_is_not_counterpart(self):
        first, second = ref(), ref(index=3)
        index = SourceIndex({"events": [event("new", [second])]})
        self.assertEqual(index.candidates(first), [])

    def test_same_raw_id_frame_with_other_physical_box_is_not_counterpart(self):
        first, second = ref(), ref(box=[80.0, 90.0, 100.0, 120.0])
        index = SourceIndex({"events": [event("new", [second])]})
        self.assertEqual(index.candidates(first), [])

    def test_changed_event_hash_still_matches_exact_source_measurement(self):
        index = SourceIndex({"events": [event("completely-new-version-hash", [ref()])]})
        result = index.candidates(event("old-hash", [ref()]))
        self.assertEqual(result[0]["event_id"], "completely-new-version-hash")
        self.assertEqual(result[0]["shared_source_measurements"], 1)
        self.assertTrue(result[0]["is_documentary_counterpart_not_physical_gt"])

    def test_one_canonical_event_can_contain_two_aliases(self):
        index = SourceIndex({"events": [event("canonical", [ref(73, 219), ref(93, 221)])]})
        self.assertEqual(index.candidates(ref(73, 219))[0]["event_id"], "canonical")
        self.assertEqual(index.candidates(ref(93, 221))[0]["event_id"], "canonical")

    def test_repeated_nested_source_refs_do_not_inflate_overlap(self):
        index = SourceIndex({"events": [event("new", [ref(), copy.deepcopy(ref())])]})
        result = index.candidates({"source_ref": ref(), "other": [ref()]})
        self.assertEqual(result[0]["shared_source_measurements"], 1)

    def test_two_real_events_remain_two_documentary_candidates(self):
        index = SourceIndex({"events": [event("first", [ref()]), event("second", [ref()])]})
        result = index.candidates(ref())
        self.assertEqual(len(result), 2)
        self.assertTrue(all(row["is_documentary_counterpart_not_physical_gt"] for row in result))

    def test_incomplete_reference_does_not_reduce_to_raw_id_match(self):
        self.assertIsNone(source_key({"frame_index": 219, "track_id": 73}))

    def test_retained_inventory_has_all_three_groups_and_discovery_cases(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "results/phase_9/20261020_QC_BV4_SIANG"
        matrix = expected_case_matrix(root)
        self.assertEqual(len(matrix["pending"]), 68)
        self.assertEqual(len(matrix["cancellations"]), 16)
        self.assertEqual(len(matrix["discovery"]), 10)

    def test_frozen_self_comparison_preserves_timeout_source_witnesses(self):
        import gzip
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        baseline = json.loads(gzip.decompress((root / "results/b_v4/execution/pilot_machine_final/weekday_siang/counting_result.json.gz").read_bytes()))
        result = compare_results(baseline, baseline, root / "results/phase_9/20261020_QC_BV4_SIANG")
        self.assertEqual(result["pending_documentary_status_counts"], {"DECISION_CONTAINS_EXACT_BASELINE_MEASUREMENT": 68})
        self.assertEqual(result["cancellation_documentary_status_counts"], {"SOURCE_WITNESS_STILL_REPRESENTED_CHECK_CANONICAL_UNIT": 16})
        self.assertFalse(result["all_121_old_measured_events_required_to_survive"])


if __name__ == "__main__":
    unittest.main()
