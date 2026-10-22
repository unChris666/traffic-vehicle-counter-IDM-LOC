"""QC bookkeeping/reference-scope tests, not physical-model benchmarks."""
from collections import Counter
from copy import deepcopy
import unittest

from phase_9_v6_qc_review import ledger_checks, transition_rows, reference_controls


def ref(frame=1, track=1):
    return {"frame_index": frame, "track_id": track, "original_detection_index": 0,
            "raw_bbox": [10, 20, 30, 40], "point": [20, 40],
            "observed": True, "emitted": True}


def event(name="event1", *, frame=1, track=1, category="motorcycle", direction="A_TO_B"):
    return {"event_id": name, "physical_unit_id": "unit1", "passage_id": "passage:" + name,
            "episode_id": "episode1", "track_id": track, "status": "accepted",
            "accepted_count_event": True, "category": category, "direction": direction,
            "route": "LINE_MARGIN", "activation_frame": frame, "decision_frame": frame,
            "evidence": {"measured_crossing": True, "source_refs": [ref(frame, track)]}}


def result(events=None, decisions=None):
    events, decisions = events or [], decisions or []
    invalid = [row for row in decisions if row["status"] == "invalid"]
    return {"events": events, "decisions": decisions, "invalid_decisions": deepcopy(invalid),
            "aggregate": {"total": len(events), "by_category": dict(Counter(e["category"] for e in events)),
                "by_direction": dict(Counter(e["direction"] for e in events)),
                "by_route": dict(Counter(e["route"] for e in events)),
                "measured_total": len(events), "inferred_total": 0,
                "pending": sum(row["status"] == "pending" for row in decisions), "invalid": len(invalid)}}


def invalid(frame=1, track=1):
    return {"physical_unit_id": "unit1", "episode_id": "episode1", "passage_id": "invalid1",
            "track_id": track, "status": "invalid", "count_delta": 0,
            "accepted_count_event": False, "invalid_reason": "INVALID_AMBIGUOUS_UNIT",
            "source_ref": ref(frame, track)}


class V6QCContracts(unittest.TestCase):
    def test_bus_and_explicit_zero_category_do_not_fail_ledger(self):
        r = result([event(category="bus")])
        r["aggregate"]["by_category"]["truck"] = 0
        self.assertEqual(ledger_checks(r)["active_events"], 1)

    def test_invalid_list_and_decision_copy_are_not_counted_twice(self):
        r = result(decisions=[invalid()])
        check = ledger_checks(r)
        self.assertEqual(check["invalid_passage_scopes"], 1)
        self.assertEqual(check["active_events"], 0)

    def test_invalid_cannot_contribute_a_count(self):
        r = result(decisions=[invalid()]);r["decisions"][0]["count_delta"] = 1
        r["invalid_decisions"] = deepcopy(r["decisions"])
        with self.assertRaisesRegex(ValueError, "contribute"):
            ledger_checks(r)

    def test_invalid_scope_cannot_be_active_under_a_different_event_id(self):
        row = invalid();row["passage_id"] = "passage:event1"
        r = result([event()], [row])
        with self.assertRaisesRegex(ValueError, "both invalid and accepted"):
            ledger_checks(r)

    def test_aggregate_and_raw_bc_must_reconcile(self):
        r = result([event()]);r["aggregate"]["total"] = 2
        with self.assertRaisesRegex(ValueError, "Total"):
            ledger_checks(r)
        r = result([event()]);r["events"][0]["evidence"]["source_refs"][0]["point"] = [20, 30]
        with self.assertRaisesRegex(ValueError, "raw measured BC"):
            ledger_checks(r)

    def test_opposite_new_passage_does_not_share_old_source_scope(self):
        old = result([event()])
        new = result([event("return", frame=20, direction="B_TO_A")])
        rows = transition_rows(old, new)
        self.assertEqual(rows[0]["documentary_status"], "NO_DOCUMENTARY_COUNTERPART_REQUIRES_COVERAGE_REVIEW")
        ledger_checks(result([event(), event("return", frame=20, direction="B_TO_A")]))

    def test_invalid_source_is_explicit_exclusion_not_traffic_absence(self):
        rows = transition_rows(result([event()]), result(decisions=[invalid()]))
        self.assertEqual(rows[0]["documentary_status"], "INTENTIONALLY_EXCLUDED_BY_AMBIGUITY_POLICY")
        self.assertEqual(rows[0]["physical_count_verdict"], "NOT_INFERRED_FROM_SOURCE_JOIN")

    def test_raw_id_at_different_frame_does_not_hide_coverage_gap(self):
        rows = transition_rows(result([event()]), result([event("other", frame=40)]))
        self.assertEqual(rows[0]["new_event_candidates"], [])

    def test_reference_duplicate_blocked_even_when_event_ids_change(self):
        keep, duplicate = event("keep", track=1), event("duplicate", track=2)
        prior = result([keep, duplicate])
        cases = {"cancellations": [{"case_id": "physical-fixture", "baseline_event_id": "duplicate",
            "qc_keep_event_id": "keep", "raw_track_id": 2, "qc_reason": "DUPLICATE",
            "new_event_candidates": []}]}
        new = result([event("new1", track=1), event("new2", track=2)])
        controls = reference_controls(prior, new, cases)
        self.assertTrue(controls[0]["status"].startswith("BLOCKER"))

    def test_correct_canonical_event_with_alias_is_single_passage(self):
        keep, duplicate = event("keep", track=1), event("duplicate", track=2)
        prior = result([keep, duplicate]);canonical = event("new", track=1)
        canonical["evidence"]["source_refs"].append(ref(track=2))
        cases = {"cancellations": [{"case_id": "physical-fixture", "baseline_event_id": "duplicate",
            "qc_keep_event_id": "keep", "raw_track_id": 2, "qc_reason": "DUPLICATE",
            "new_event_candidates": [{"event_id": "new", "retains_old_source_decision_witness": True,
                                      "shares_qc_canonical_keep_source_measurement": True}]}]}
        controls = reference_controls(prior, result([canonical]), cases)
        self.assertEqual(controls[0]["status"], "NO_KNOWN_BAD_SOURCE_WITNESS_ACCEPTED")


if __name__ == "__main__":
    unittest.main()
