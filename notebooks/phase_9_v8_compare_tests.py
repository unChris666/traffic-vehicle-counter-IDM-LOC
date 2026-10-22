"""Pending disposition joins must use source review, not raw-ID resemblance."""
from copy import deepcopy
import unittest

from phase_8_b_v8_finalize_tests import baseline, pending
from phase_9_v8_compare import compare_results, reconcile_pending


def inventory(before):
    return {"cases": [{"case_id": f"case:{d['track_id']}",
        "baseline_candidate_scope": {k: d[k] for k in
            ("track_id", "physical_unit_id", "episode_id", "passage_id")},
        "baseline_source_ref": deepcopy(d["source_ref"]),
        "missing_evidence_and_next_action": "Positive role/geometry review needed"}
        for d in before["decisions"] if d["status"] == "pending"]}


def accepted_mapping(after, *, role="pedestrian", support=True, count=1):
    after["decisions"][0]["status"] = "resolved_not_eligible"
    refs = [{"review_id": "positive-role", "review_type": "PEDESTRIAN_ROLE"}] if support else []
    after["frame_assignments"] = [{"track_id": 2, "frame_index": 10,
        "physical_unit_id": "reviewed:pedestrian", "episode_id": "bounded-role",
        "role": role, "review_refs": refs}]
    after["events"] = [{"event_id": f"reviewed:{i}", "physical_unit_id": "reviewed:pedestrian",
        "episode_id": "bounded-role", "role": "pedestrian",
        "evidence": {"measured_crossing": True, "source_refs": [
            {"frame_index": 8, "track_id": 2, "review_refs": refs}]}} for i in range(count)]


class P1PendingComparison(unittest.TestCase):
    def setUp(self):
        self.before = baseline()
        self.after = deepcopy(self.before)
        self.inventory = inventory(self.before)

    def test_necessary_unknown_stays_pending_with_next_action(self):
        report = reconcile_pending(self.before, self.after, self.inventory)
        self.assertEqual(report["by_final_status"], {"pending": 2})
        self.assertTrue(all(row["count_contribution"] == 0 for row in report["rows"]))

    def test_exact_component_closure_is_plus_zero_not_recovered_vehicle(self):
        case = self.inventory["cases"][0]
        self.after["decisions"][0]["status"] = "resolved_not_eligible"
        self.after["v8_pending_finalization_audit"] = [{
            **deepcopy(case), "final_status": "resolved_not_eligible",
            "reason": "REVIEWED_NON_INDEPENDENT_COMPONENT", "decision_origin": "AI_SOURCE_REVIEW",
            "adjudication_id": "component:2", "decision_frame": 100,
            "review": {"proof_artifacts": [{"path": "pixels.png"}]}}]
        report = reconcile_pending(self.before, self.after, self.inventory)
        self.assertEqual(report["by_final_status"], {"pending": 1, "resolved_not_eligible": 1})
        self.assertEqual(report["rows"][0]["count_contribution"], 0)
        self.assertFalse(report["reviewed_component_closures_are_recovered_vehicles"])

    def test_source_review_maps_earlier_event_without_inventing_a_new_passage(self):
        accepted_mapping(self.after)
        report = reconcile_pending(self.before, self.after, self.inventory)
        self.assertEqual(report["by_final_status"], {"accepted": 1, "pending": 1})
        self.assertTrue(report["rows"][0]["mapping_is_not_global_raw_id_alias"])

    def test_shared_raw_or_unit_without_positive_review_is_not_enough(self):
        accepted_mapping(self.after, support=False)
        report = reconcile_pending(self.before, self.after, self.inventory)
        self.assertEqual(report["rows"][0]["final_status"], "unresolved_reconciliation")

    def test_role_incompatible_assignment_cannot_claim_an_accepted_counterpart(self):
        accepted_mapping(self.after, role="rider")
        report = reconcile_pending(self.before, self.after, self.inventory)
        self.assertEqual(report["rows"][0]["final_status"], "unresolved_reconciliation")

    def test_multiple_return_events_need_explicit_scope_resolution(self):
        accepted_mapping(self.after, count=2)
        report = reconcile_pending(self.before, self.after, self.inventory)
        self.assertEqual(report["rows"][0]["final_status"], "unresolved_reconciliation")

    def test_foreign_candidate_measurement_is_rejected(self):
        self.inventory["cases"][0]["baseline_source_ref"]["raw_bbox"][0] += 1
        with self.assertRaisesRegex(ValueError, "witness differs"):
            reconcile_pending(self.before, self.after, self.inventory)

    def test_missing_or_duplicated_case_is_not_silently_dropped(self):
        self.inventory["cases"][1] = deepcopy(self.inventory["cases"][0])
        with self.assertRaisesRegex(ValueError, "every baseline pending"):
            reconcile_pending(self.before, self.after, self.inventory)

    def test_new_pending_is_reported_outside_the_old_inventory(self):
        self.after["decisions"].append(pending(4, 30))
        self.after["aggregate"]["pending"] = 3
        report = reconcile_pending(self.before, self.after, self.inventory)
        self.assertEqual(len(report["unmatched_new_pending"]), 1)

    def test_machine_branch_is_not_misreported_as_reviewed_improvement(self):
        self.after["branch"] = "machine"
        with self.assertRaisesRegex(ValueError, "reviewed branch"):
            compare_results(self.before, self.after, self.inventory)


if __name__ == "__main__":
    unittest.main(verbosity=2)
