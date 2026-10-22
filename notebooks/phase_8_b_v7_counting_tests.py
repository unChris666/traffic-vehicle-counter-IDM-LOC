"""B v7 publication and source-scope contracts; not counting-accuracy metrics."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import unittest

import phase_8_b_v6_counting as baseline
from phase_8_b_v6_counting_tests import POLICY, GEOMETRY, SOURCE, observation, frames
from phase_8_b_v7_counting import finalize_handoff_candidates


def samples():
    values = {f: [observation(10 + 3*f, track=1, physical_episode_id="physical:1")]
              for f in range(5)}
    values.update({f: [observation(10 + 3*f, track=2, physical_episode_id="physical:2")]
                   for f in range(6, 19)})
    return values


def provisional(values=None, end=64):
    source_frames = frames(samples() if values is None else values, end=end)
    result = baseline.replay_frames(source_frames, GEOMETRY,
        source_identity=SOURCE, policy=deepcopy(POLICY))
    return source_frames, result


def proposal(result, first_track=1, second_track=2, first_support=None, second_support=None):
    events = [next(e for e in result["events"]
                   if e["track_id"] == track and e["direction"] == "A_TO_B")
              for track in (first_track, second_track)]
    rel = {"relation_id": "synthetic-unverified-handoff", "relation_type": "SAME_UNIT",
        "candidate_kind": "UNVERIFIED_ORIGIN_HANDOFF", "verified": False,
        "event_ids": [e["event_id"] for e in events]}
    for prefix, event, support in zip(("first", "second"), events,
            (first_support or list(range(5)), second_support or list(range(6, 11)))):
        physical = next(ref["physical_episode_id"] for ref in event["evidence"]["source_refs"]
                        if ref["track_id"] == event["track_id"])
        rel.update({prefix + "_event_id": event["event_id"],
            prefix + "_track_id": event["track_id"], prefix + "_unit_id": event["physical_unit_id"],
            prefix + "_episode_id": event["episode_id"], prefix + "_physical_episode_id": physical,
            prefix + "_support_frames": support})
    rel["support_frames"] = sorted(set(rel["first_support_frames"] + rel["second_support_frames"]))
    return {"relations": [rel], "audit": [], "controls": {"test_fixture_only": True}}


class Bv7PublicationContracts(unittest.TestCase):
    def test_exact_pair_is_invalid_before_publication_without_identity_merge(self):
        source, old = provisional()
        self.assertEqual(old["aggregate"]["total"], 2)
        result = finalize_handoff_candidates(old, proposal(old), frames=source)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["aggregate"]["invalid"], 2)
        self.assertEqual(result["report"]["v7_publication"]["physical_episodes_merged"], 0)
        self.assertTrue(all(log["count_delta"] == 0 for log in result["passage_log"]))
        self.assertTrue(all(e["never_published"] for e in result["cancelled_events"]))
        self.assertEqual({d["decision_frame"] for d in result["invalid_decisions"]}, {64})
        self.assertEqual({d["candidate_decision_frame"] for d in result["invalid_decisions"]}, {16, 64})

    def test_inputs_and_vehicle_measurements_are_immutable(self):
        source, old = provisional()
        suggested = proposal(old)
        snapshots = deepcopy((source, old, suggested))
        result = finalize_handoff_candidates(old, suggested, frames=source)
        self.assertEqual((source, old, suggested), snapshots)
        source_events = {e["track_id"]: e for e in old["events"]}
        for cancelled in result["cancelled_events"]:
            self.assertEqual(cancelled["evidence"], source_events[cancelled["track_id"]]["evidence"])

    def test_unrelated_pending_person_and_category_conflict_are_unchanged(self):
        values = samples()
        for frame, y, category in ((0, 30, "car"), (1, 70, "truck")):
            values[frame].extend([
                observation(y, track=98, detection=1, category=category, physical_episode_id="category:98"),
                observation(y, track=99, detection=2, category="person", role="unknown_person",
                            physical_episode_id="person:99")])
        source, old = provisional(values)
        pending = [d for d in old["decisions"] if d["status"] == "pending"]
        self.assertEqual(len(pending), 2)
        result = finalize_handoff_candidates(old, proposal(old), frames=source)
        self.assertEqual([d for d in result["decisions"] if d["status"] == "pending"], pending)
        self.assertEqual(result["aggregate"]["pedestrian_total"], 0)

    def test_later_genuine_reverse_passage_is_not_poisoned(self):
        values = samples()
        values.update({19: [observation(52, track=2, physical_episode_id="physical:2")],
                       20: [observation(47, track=2, physical_episode_id="physical:2")],
                       21: [observation(30, track=2, physical_episode_id="physical:2")]})
        source, old = provisional(values)
        self.assertEqual(old["aggregate"]["total"], 3)
        result = finalize_handoff_candidates(old, proposal(old), frames=source)
        self.assertEqual(result["aggregate"]["total"], 1)
        self.assertEqual(result["events"][0]["direction"], "B_TO_A")
        self.assertTrue(result["events"][0]["evidence"]["measured_crossing"])

    def test_no_relation_means_no_new_exclusion(self):
        source, old = provisional()
        result = finalize_handoff_candidates(old, {"relations": []}, frames=source)
        self.assertEqual(result["aggregate"], old["aggregate"])

    def test_all_local_event_references_use_v7_prefix(self):
        source, old = provisional()
        result = finalize_handoff_candidates(old, proposal(old), frames=source)
        serialized = json.dumps(result)
        for event in old["events"]:
            self.assertNotIn(event["event_id"], serialized)
            self.assertIn(event["event_id"].replace("b_v6_", "b_v7_"), serialized)

    def test_future_only_support_cannot_reopen_old_passage(self):
        source, old = provisional()
        bad = proposal(old, first_support=list(range(30, 35)), second_support=list(range(36, 41)))
        with self.assertRaisesRegex(ValueError, "own measured window"):
            finalize_handoff_candidates(old, bad, frames=source)

    def test_foreign_physical_episode_is_rejected(self):
        source, old = provisional()
        bad = proposal(old)
        bad["relations"][0]["first_physical_episode_id"] = "foreign"
        with self.assertRaisesRegex(ValueError, "physical context"):
            finalize_handoff_candidates(old, bad, frames=source)

    def test_missing_actual_support_cannot_be_fabricated(self):
        source, old = provisional()
        source[2]["observations"] = []
        with self.assertRaisesRegex(ValueError, "actual vehicle observations"):
            finalize_handoff_candidates(old, proposal(old), frames=source)

    def test_rider_measurements_cannot_support_vehicle_handoff(self):
        source, old = provisional()
        source[2]["observations"][0]["role"] = "rider"
        with self.assertRaisesRegex(ValueError, "actual vehicle observations"):
            finalize_handoff_candidates(old, proposal(old), frames=source)

    def test_opposite_direction_relation_is_rejected(self):
        source, old = provisional()
        old["events"][0]["direction"] = "B_TO_A"
        bad = proposal(provisional()[1])
        with self.assertRaisesRegex(ValueError, "same-direction"):
            finalize_handoff_candidates(old, bad, frames=source)

    def test_two_measured_passages_cannot_be_suppressed_by_this_experiment(self):
        source, old = provisional()
        for event in old["events"]:
            event["evidence"]["measured_crossing"] = True
        with self.assertRaisesRegex(ValueError, "two measured passages"):
            finalize_handoff_candidates(old, proposal(old), frames=source)

    def test_premature_finalization_frame_is_rejected(self):
        source, old = provisional()
        with self.assertRaisesRegex(ValueError, "actual source EOF"):
            finalize_handoff_candidates(old, proposal(old), frames=source, finalization_frame=16)

    def test_verified_merge_is_not_fabricated_from_trajectory_fit(self):
        source, old = provisional()
        bad = proposal(old)
        bad["relations"][0]["verified"] = True
        with self.assertRaisesRegex(ValueError, "unverified handoff"):
            finalize_handoff_candidates(old, bad, frames=source)

    def test_actual_retained_duplicate_pair_stays_inferred_and_is_scoped_invalid(self):
        root = Path(__file__).resolve().parents[1] / "results/b_v7/fixtures/1049_1123_v1"
        with gzip.open(root / "baseline_fixture_result.json.gz", "rt") as handle:
            old = json.load(handle)
        with gzip.open(root / "counting_frames_selected_tracks.json.gz", "rt") as handle:
            source = json.load(handle)
        suggested = proposal(old, 1049, 1123, list(range(1332, 1337)), list(range(1349, 1354)))
        result = finalize_handoff_candidates(old, suggested, frames=source)
        self.assertEqual(old["aggregate"]["total"], 2)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["aggregate"]["invalid"], 2)
        self.assertEqual(result["aggregate"]["measured_total"], 0)
        self.assertTrue(all(not e["evidence"]["measured_crossing"] for e in result["cancelled_events"]))
        self.assertEqual({d["decision_frame"] for d in result["invalid_decisions"]}, {1424})
        self.assertEqual({d["candidate_decision_frame"] for d in result["invalid_decisions"]}, {1396})


if __name__ == "__main__":
    unittest.main()
