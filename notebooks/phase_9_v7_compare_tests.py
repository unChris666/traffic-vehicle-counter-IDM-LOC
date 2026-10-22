"""Documentary event comparison tests; no physical counting-accuracy claims."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from phase_8_b_v3_counting_tests import SOURCE
from phase_9_v6_qc_review_tests import event, ref
from phase_9_v7_compare import compare_results, write_comparison


def sample(name="source1", frame=1, track=1, category="motorcycle"):
    row = event("b_v6_" + name, frame=frame, track=track, category=category)
    row.update(physical_unit_id="unit:" + name, passage_id="passage:" + name,
               namespace="old-version-config", display_id="M2000")
    return row


def result(events=(), *, pending=(), cancelled=()):
    events = deepcopy(list(events))
    measured = sum(bool(e["evidence"]["measured_crossing"]) for e in events)
    return {"source_identity": deepcopy(SOURCE), "events": events,
        "cancelled_events": deepcopy(list(cancelled)), "decisions": deepcopy(list(pending)),
        "invalid_decisions": [], "frame_assignments": [{"frame_index": 1, "track_id": 1}],
        "component_links": [{"component_track_id": 2, "vehicle_track_id": 1}],
        "aggregate": {"total": len(events),
            "by_category": dict(Counter(e["category"] for e in events)),
            "by_direction": dict(Counter(e["direction"] for e in events)),
            "by_route": dict(Counter(e["route"] for e in events)),
            "measured_total": measured, "inferred_total": len(events) - measured,
            "pending": len(pending), "invalid": 0}}


class V7DocumentaryComparison(unittest.TestCase):
    def test_versioned_id_and_namespace_are_not_new_passages(self):
        old = result([sample()]); new = deepcopy(old)
        new["events"][0].update(event_id="b_v7_newhash", namespace="new-version-config")
        report = compare_results(old, new)
        self.assertEqual(report["event_counts"], {"unchanged": 1, "changed": 0, "removed": 0, "added": 0})
        self.assertTrue(report["frame_assignments_unchanged"])
        self.assertTrue(report["component_links_unchanged"])

    def test_category_change_is_not_disappearance_and_new_event(self):
        first, second = sample(), sample(category="truck")
        report = compare_results(result([first]), result([second]))
        self.assertEqual(report["event_counts"], {"unchanged": 0, "changed": 1, "removed": 0, "added": 0})
        self.assertEqual(report["changed"][0]["changed_fields"], ["category"])
        self.assertEqual(report["category_changed_events"], 1)

    def test_measured_downgrade_is_explicit_and_estimated_route_is_separate(self):
        first, second = sample(), sample()
        second["evidence"]["measured_crossing"] = False
        second["route"] = "ESTIMATED_TIMEOUT"
        report = compare_results(result([first]), result([second]))
        self.assertEqual(report["event_counts"]["changed"], 1)
        self.assertEqual(report["candidate"]["estimated_by_route"], {"ESTIMATED_TIMEOUT": 1})
        self.assertEqual(set(report["changed"][0]["changed_fields"]), {"evidence", "route"})
        self.assertEqual(report["evidence_transition_counts"], {"DOWNGRADED_TO_ESTIMATE": 1})
        upgraded = compare_results(result([second]), result([first]))
        self.assertEqual(upgraded["evidence_transition_counts"], {"UPGRADED_TO_MEASURED": 1})

    def test_added_source_event_is_reported_without_assuming_correctness(self):
        first, extra = sample(), sample("source2", frame=20, track=2, category="car")
        report = compare_results(result([first]), result([first, extra]))
        self.assertEqual(report["event_counts"]["added"], 1)
        self.assertEqual(report["added"][0]["new"]["track_id"], 2)
        self.assertFalse(report["physical_accuracy_established"])

    def test_removed_event_retains_full_cancelled_source_evidence(self):
        first = sample(); cancelled = deepcopy(first)
        cancelled.update(event_id="b_v7_changedhash", status="cancelled", accepted_count_event=False,
                         never_published=True, decision_frame=50)
        report = compare_results(result([first]), result(cancelled=[cancelled]))
        self.assertEqual(report["event_counts"]["removed"], 1)
        self.assertEqual(report["removed"][0]["candidate_cancelled_counterpart"], cancelled)
        self.assertEqual(report["new_cancellations"], [cancelled])
        self.assertEqual(report["removed"][0]["source_evidence"], first["evidence"])

    def test_pending_event_references_normalize_by_measurements(self):
        first = sample()
        old = result([first], pending=[{"status": "pending", "reason": "identity",
                                       "source_event_id": first["event_id"]}])
        new = deepcopy(old)
        new["events"][0]["event_id"] = "b_v7_newhash"
        new["decisions"][0]["source_event_id"] = "b_v7_newhash"
        self.assertTrue(compare_results(old, new)["pending_semantically_unchanged"])
        new["decisions"][0]["reason"] = "role"
        report = compare_results(old, new)
        self.assertFalse(report["pending_semantically_unchanged"])
        self.assertEqual(len(report["pending_added"]), 1)
        self.assertEqual(len(report["pending_removed"]), 1)

    def test_duplicate_source_witness_is_rejected_even_under_different_ids(self):
        first, duplicate = sample(), sample("separate-unit")
        duplicate["evidence"] = deepcopy(first["evidence"])
        with self.assertRaisesRegex(ValueError, "Repeated active source-witness"):
            compare_results(result([first]), result([first, duplicate]))

    def test_unique_partial_measurement_overlap_reports_changed_evidence(self):
        first, second = sample(), sample()
        second["evidence"]["source_refs"].append(ref(frame=2))
        report = compare_results(result([first]), result([second]))
        self.assertEqual(report["event_counts"]["changed"], 1)
        self.assertEqual(report["changed"][0]["join"], "UNIQUE_OVERLAPPING_EXACT_MEASUREMENTS")
        self.assertEqual(report["changed"][0]["changed_fields"], ["evidence"])

    def test_ambiguous_source_split_requires_review_instead_of_guessing(self):
        first = sample()
        first["evidence"]["source_refs"].append(ref(frame=2))
        left, right = sample("left"), sample("right")
        right["evidence"]["source_refs"] = [ref(frame=2)]
        with self.assertRaisesRegex(ValueError, "Ambiguous source overlap"):
            compare_results(result([first]), result([left, right]))

    def test_foreign_source_hash_cannot_be_compared_as_same_replay(self):
        old, new = result([sample()]), result([sample()])
        new["source_identity"]["records_sha256"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "source identities differ"):
            compare_results(old, new)

    def test_raw_id_reuse_on_different_measurements_is_not_joined(self):
        report = compare_results(result([sample()]), result([sample(frame=90)]))
        self.assertEqual(report["event_counts"]["changed"], 0)
        self.assertEqual(report["event_counts"]["removed"], 1)
        self.assertEqual(report["event_counts"]["added"], 1)

    def test_direction_and_component_changes_are_visible(self):
        first, second = sample(), sample()
        second["direction"] = "B_TO_A"
        old, new = result([first]), result([second])
        new["component_links"] = []
        new["frame_assignments"] = []
        report = compare_results(old, new)
        self.assertEqual(report["direction_changed_events"], 1)
        self.assertFalse(report["frame_assignments_unchanged"])
        self.assertFalse(report["component_links_unchanged"])

    def test_inputs_are_immutable_and_results_deterministic(self):
        old, new = result([sample()]), result([sample(category="car")])
        before = deepcopy((old, new))
        self.assertEqual(compare_results(old, new), compare_results(old, new))
        self.assertEqual((old, new), before)

    def test_exports_use_new_b_v7_directory_and_csv_contains_changes(self):
        report = compare_results(result([sample()]), result([sample(category="truck")]))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "results/b_v7/compare"
            write_comparison(report, output, repo_root=root)
            self.assertTrue((output / "comparison.json").is_file())
            self.assertIn("changed", (output / "event_deltas.csv").read_text())
            self.assertTrue((output / "retention_manifest.json").is_file())
            with self.assertRaisesRegex(ValueError, "new directory"):
                write_comparison(report, output, repo_root=root)
            with self.assertRaisesRegex(ValueError, "new directory"):
                write_comparison(report, root / "results/b_v6/rewrite", repo_root=root)


if __name__ == "__main__":
    unittest.main()
