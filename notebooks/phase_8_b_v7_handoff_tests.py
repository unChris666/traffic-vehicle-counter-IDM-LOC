"""Bounded B v7 motion-conflict controls; synthetic fixtures are not accuracy evidence.

Every provisional event below is emitted by the unchanged B v6 replay.  Motion
compatibility may propose an unverified conflict; it cannot prove identity,
merge physical episodes, or repair an unobserved crossing.
"""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import unittest

from phase_5_geometry_helpers import Geometry
from phase_8_b_v3_counting_tests import GEOMETRY, SOURCE, frames, observation
from phase_8_b_v5_counting_tests import relation
from phase_8_b_v6_counting_tests import POLICY as BASE_POLICY
from phase_8_b_v6_counting import replay_frames as baseline_replay
from phase_8_b_v7_handoff import experimental_handoff_policy, propose_handoff_conflicts


def policy(relations=()):
    return {**deepcopy(BASE_POLICY), "episode_relations": deepcopy(list(relations)),
            "v7_handoff": experimental_handoff_policy()}


def sample(frame, y, track=1, **extra):
    metadata = {"frame_index": frame, "physical_episode_id": f"physical:{track}",
                "role": "vehicle", "unit": f"track:{track}", "episode_id": None,
                "detection": track, **extra}
    return observation(y, track=track, **metadata)


def handoff_samples(first=1, second=2):
    """An eligible old origin and a motion-compatible, later measured crossing."""
    samples = {frame: [sample(frame, 5 + 5 * frame, first)] for frame in range(5)}
    samples.update({frame: [sample(frame, 5 + 5 * frame, second)]
                    for frame in range(6, 13)})
    return samples


def run(samples=None, end=64, constraints=(), geometry=GEOMETRY):
    controls = policy(constraints)
    observed = frames(handoff_samples() if samples is None else samples, end=end)
    baseline = baseline_replay(observed, geometry, source_identity=SOURCE, policy=controls)
    proposed = propose_handoff_conflicts(baseline, observed, geometry, controls)
    return baseline, proposed, observed, controls


def endpoints(proposed):
    return {(row["first_track_id"], row["second_track_id"])
            for row in proposed["relations"]}


class Bv7HandoffControls(unittest.TestCase):
    def test_motion_compatible_handoff_is_unverified_conflict_not_alias(self):
        baseline, proposed, _, _ = run()
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(baseline["aggregate"]["measured_total"], 1)
        self.assertEqual(baseline["aggregate"]["inferred_total"], 1)
        self.assertEqual(endpoints(proposed), {(1, 2)})
        candidate = proposed["relations"][0]
        self.assertEqual(candidate["candidate_kind"], "UNVERIFIED_ORIGIN_HANDOFF")
        self.assertIs(candidate["verified"], False)
        self.assertIs(candidate["identity_merged"], False)
        self.assertIs(candidate["predicted_crossing_is_measured"], False)
        self.assertEqual(candidate["first_physical_episode_id"], "physical:1")
        self.assertEqual(candidate["second_physical_episode_id"], "physical:2")

    def test_following_motorcycles_with_observed_copresence_stay_independent(self):
        samples = {frame: [sample(frame, 5 + 5 * frame)] for frame in range(7)}
        for frame in range(4, 17):
            samples.setdefault(frame, []).append(sample(frame, 5 + 5 * (frame - 4), 2))
        baseline, proposed, _, _ = run(samples, end=66)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertTrue(any(len(row) == 2 for row in samples.values()))
        self.assertEqual(proposed["relations"], [])

    def test_opposite_directions_cannot_be_same_passage(self):
        samples = {frame: [sample(frame, 5 + 5 * frame)] for frame in range(5)}
        samples.update({frame: [sample(frame, 95 - 5 * (frame - 6), 2)]
                        for frame in range(6, 20)})
        baseline, proposed, _, _ = run(samples)
        self.assertEqual({row["direction"] for row in baseline["events"]},
                         {"A_TO_B", "B_TO_A"})
        self.assertEqual(proposed["relations"], [])

    def test_overlapping_paths_with_source_scoped_distinct_proof_are_protected(self):
        distinct = relation(kind="DIFFERENT_UNIT", support=[4, 6])
        baseline, proposed, _, _ = run(constraints=[distinct])
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(proposed["relations"], [])

    def test_unverified_or_foreign_distinct_claim_cannot_veto_candidate(self):
        for change in ({"verified": False},
                       {"support_frames": [50, 51]},
                       {"first_physical_episode_id": "unrelated-physical-episode"},
                       {"first_track_id": 99}):
            with self.subTest(change=change):
                distinct = {**relation(kind="DIFFERENT_UNIT", support=[4, 6]), **change}
                self.assertEqual(endpoints(run(constraints=[distinct])[1]), {(1, 2)})

    def test_genuine_measured_return_is_not_a_handoff_pair(self):
        samples = {frame: [sample(frame, 5 + 5 * frame)] for frame in range(13)}
        samples.update({frame: [sample(frame, 65 - 5 * (frame - 12))]
                        for frame in range(13, 26)})
        baseline, proposed, _, _ = run(samples, end=85)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(baseline["aggregate"]["measured_total"], 2)
        self.assertEqual({row["direction"] for row in baseline["events"]},
                         {"A_TO_B", "B_TO_A"})
        self.assertEqual(proposed["relations"], [])

    def test_person_component_never_supplies_vehicle_motion_or_vehicle_bc(self):
        samples = handoff_samples()
        for frame in range(6, 13):
            samples[frame].append(sample(frame, 5 + 5 * frame, 3, category="person",
                                         role="rider", unit="track:2",
                                         association_verified=True,
                                         association_id="synthetic-parent-proof"))
        baseline, proposed, _, _ = run(samples)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(endpoints(proposed), {(1, 2)})
        self.assertTrue(all(row["track_id"] != 3 for row in baseline["events"]))
        for event in baseline["events"]:
            for ref in event["evidence"]["source_refs"]:
                box = ref["raw_bbox"]
                self.assertNotEqual(ref["track_id"], 3)
                self.assertEqual(ref["point"], [(box[0] + box[2]) / 2, box[3]])

    def test_fewer_than_five_old_observations_do_not_prove_motion(self):
        samples = {frame: [sample(frame, 5 + 5 * frame)] for frame in range(3)}
        samples.update({frame: [sample(frame, 5 + 5 * frame, 2)]
                        for frame in range(4, 13)})
        baseline, proposed, _, _ = run(samples, end=62)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(proposed["relations"], [])
        self.assertEqual(proposed["audit"][0]["reason"], "INSUFFICIENT_CONSECUTIVE_OBSERVATIONS")

    def test_stationary_last_window_cannot_supply_handoff_velocity(self):
        samples = {frame: [sample(frame, y)]
                   for frame, y in enumerate((5, 10, 15, 15, 15, 15, 15))}
        samples.update({frame: [sample(frame, 25 + 5 * (frame - 8), 2)]
                        for frame in range(8, 17)})
        baseline, proposed, _, _ = run(samples, end=66)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(proposed["relations"], [])
        self.assertEqual(proposed["audit"][0]["reason"], "OBSERVED_MOTION_DIRECTION_NOT_SUPPORTED")

    def test_future_observations_cannot_complete_candidate_motion_window(self):
        samples = {frame: [sample(frame, 5 + 5 * frame)] for frame in range(5)}
        samples.update({frame: [sample(frame, 35 + 10 * (frame - 6), 2)]
                        for frame in range(6, 12)})
        baseline, proposed, _, _ = run(samples)
        event = next(row for row in baseline["events"] if row["track_id"] == 2)
        self.assertEqual(event["decision_frame"], 9)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        # Only frames6..9 belong to this candidate; frames10..11 cannot
        # retroactively furnish the fifth observed point before its decision.
        self.assertEqual(proposed["relations"], [])
        self.assertEqual(proposed["audit"][0]["reason"], "INSUFFICIENT_CONSECUTIVE_OBSERVATIONS")

    def test_nonconsecutive_observations_are_not_a_contiguous_velocity_window(self):
        samples = {frame: [sample(frame, y)]
                   for frame, y in ((0, 5), (1, 10), (2, 15), (4, 20), (5, 25), (6, 30))}
        samples.update({frame: [sample(frame, 40 + 5 * (frame - 8), 2)]
                        for frame in range(8, 14)})
        baseline, proposed, _, _ = run(samples, end=66)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(proposed["relations"], [])
        self.assertEqual(proposed["audit"][0]["reason"], "INSUFFICIENT_CONSECUTIVE_OBSERVATIONS")

    def test_one_way_extrapolation_match_does_not_replace_bidirectional_gate(self):
        samples = {frame: [sample(frame, 5 + 5 * frame)] for frame in range(5)}
        samples.update({frame: [sample(frame, 35 + 3 * (frame - 6), 2)]
                        for frame in range(6, 17)})
        baseline, proposed, _, _ = run(samples)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(proposed["relations"], [])
        audit = proposed["audit"][0]
        self.assertEqual(audit["reason"], "BIDIRECTIONAL_OBSERVED_BOX_GATE_FAILED")
        self.assertIs(audit["forward_positive_area_overlap"], True)
        self.assertIs(audit["backward_positive_area_overlap"], False)

    def test_event_direction_does_not_override_opposite_observed_head_motion(self):
        samples = {frame: [sample(frame, 5 + 5 * frame)] for frame in range(5)}
        samples.update({frame: [sample(frame, y, 2)] for frame, y in
                        ((6, 35), (7, 32), (8, 29), (9, 26), (10, 23),
                         (11, 30), (12, 37), (13, 44), (14, 51), (15, 58), (16, 65))})
        baseline, proposed, _, _ = run(samples)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual({row["direction"] for row in baseline["events"]}, {"A_TO_B"})
        self.assertEqual(proposed["relations"], [])
        self.assertEqual(proposed["audit"][0]["reason"], "OBSERVED_MOTION_DIRECTION_NOT_SUPPORTED")

    def test_handoff_cannot_expand_existing_sixty_source_frame_horizon(self):
        samples = {frame: [sample(frame, 5 + 5 * frame)] for frame in range(5)}
        samples.update({frame: [sample(frame, 35 + 5 * (frame - 65), 2)]
                        for frame in range(65, 72)})
        baseline, proposed, _, _ = run(samples, end=80)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(proposed["relations"], [])

    def test_same_category_and_direction_alone_are_insufficient(self):
        samples = handoff_samples()
        for frame in range(6, 13):
            samples[frame][0]["raw_bbox"][0] += 25
            samples[frame][0]["raw_bbox"][2] += 25
        baseline, proposed, _, _ = run(samples)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(proposed["relations"], [])

    def test_parallel_boxes_that_only_touch_do_not_have_spatial_support(self):
        samples = handoff_samples()
        for frame in range(6, 13):
            samples[frame][0]["raw_bbox"][0] += 4
            samples[frame][0]["raw_bbox"][2] += 4
        baseline, proposed, _, _ = run(samples)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(proposed["relations"], [])
        audit = proposed["audit"][0]
        self.assertEqual(audit["reason"], "BIDIRECTIONAL_OBSERVED_BOX_GATE_FAILED")
        self.assertIs(audit["forward_positive_area_overlap"], False)
        self.assertIs(audit["backward_positive_area_overlap"], False)

    def test_separate_parallel_boxes_do_not_propose_an_identity_conflict(self):
        samples = handoff_samples()
        for frame in range(6, 13):
            samples[frame][0]["raw_bbox"][0] += 4.25
            samples[frame][0]["raw_bbox"][2] += 4.25
        baseline, proposed, _, _ = run(samples)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(proposed["relations"], [])
        self.assertEqual(proposed["audit"][0]["reason"],
                         "BIDIRECTIONAL_OBSERVED_BOX_GATE_FAILED")

    def test_raw_id_renaming_does_not_change_handoff_decision(self):
        original = run()[1]
        renamed = run(handoff_samples(87, 901))[1]
        self.assertEqual(endpoints(original), {(1, 2)})
        self.assertEqual(endpoints(renamed), {(87, 901)})
        self.assertEqual(len(original["relations"]), len(renamed["relations"]))

    def test_unset_resolved_class_preserves_measured_vehicle_class(self):
        samples = handoff_samples()
        for rows in samples.values():
            for row in rows:
                row["resolved_class_name"] = None
        baseline, proposed, _, _ = run(samples)
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(endpoints(proposed), {(1, 2)})

    def test_swapping_line_endpoints_does_not_swap_polygon_direction_semantics(self):
        reverse_line = Geometry(GEOMETRY.p2, GEOMETRY.p1,
                                GEOMETRY.side_a, GEOMETRY.side_b,
                                100, 100, "synthetic-horizontal-reversed-line")
        self.assertEqual(endpoints(run(geometry=reverse_line)[1]), {(1, 2)})

    def test_motion_proposal_preserves_inputs_and_gap_measurements(self):
        baseline, _, observed, controls = run()
        before = deepcopy((baseline, observed, controls))
        result = propose_handoff_conflicts(baseline, observed, GEOMETRY, controls)
        self.assertEqual((baseline, observed, controls), before)
        self.assertEqual(observed[5]["observations"], [])
        self.assertEqual(endpoints(result), {(1, 2)})
        self.assertEqual(sum(row["evidence"]["measured_crossing"]
                             for row in baseline["events"]), 1)

    def test_equivalent_input_order_has_deterministic_proposals(self):
        baseline, proposed, observed, controls = run()
        reordered = deepcopy(observed)
        for row in reordered:
            row["observations"].reverse()
        result = deepcopy(baseline)
        result["events"].reverse()
        self.assertEqual(propose_handoff_conflicts(result, reordered, GEOMETRY, controls),
                         proposed)


class Bv7RetainedSourceFixture(unittest.TestCase):
    """Retained development evidence only; not a full-video benchmark."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1] / "results/b_v7/fixtures/1049_1123_v1"
        manifest = json.loads((cls.root / "retention_manifest.json").read_text())
        for retained in manifest["files"]:
            path = cls.root / retained["path"]
            content = path.read_bytes()
            if len(content) != retained["bytes"] or hashlib.sha256(content).hexdigest() != retained["sha256"]:
                raise AssertionError(f"Retained source fixture changed: {path}")
        with gzip.open(cls.root / "counting_frames_selected_tracks.json.gz", "rt") as handle:
            cls.observed = json.load(handle)
        with gzip.open(cls.root / "baseline_fixture_result.json.gz", "rt") as handle:
            cls.retained = json.load(handle)
        cls.source = json.loads((cls.root / "source_identity.json").read_text())
        cls.controls = json.loads((cls.root / "policy.json").read_text())
        cls.controls["v7_handoff"] = experimental_handoff_policy()
        cls.geometry = Geometry.from_draft(cls.root / "geometry.json", 640, 480)

    def test_retained_baseline_reproduces_two_estimated_events_and_motion_conflict(self):
        baseline = baseline_replay(self.observed, self.geometry,
                                   source_identity=self.source, policy=self.controls)
        self.assertEqual(baseline["aggregate"], self.retained["aggregate"])
        self.assertEqual(baseline["aggregate"]["total"], 2)
        self.assertEqual(baseline["aggregate"]["measured_total"], 0)
        self.assertEqual(baseline["aggregate"]["inferred_total"], 2)
        self.assertEqual({(e["track_id"], e["route"], e["activation_frame"])
                          for e in baseline["events"]},
                         {(1049, "ESTIMATED_TIMEOUT", 1396), (1123, "LINE_MARGIN", 1396)})
        before = deepcopy((baseline, self.observed, self.controls))
        proposed = propose_handoff_conflicts(baseline, self.observed, self.geometry, self.controls)
        self.assertEqual(endpoints(proposed), {(1049, 1123)})
        candidate = proposed["relations"][0]
        self.assertEqual(candidate["gap_source_frames"], 13)
        self.assertEqual(candidate["first_support_frames"], list(range(1332, 1337)))
        self.assertEqual(candidate["second_support_frames"], list(range(1349, 1354)))
        self.assertIs(candidate["verified"], False)
        self.assertIs(candidate["identity_merged"], False)
        self.assertIs(candidate["predicted_crossing_is_measured"], False)
        self.assertEqual((baseline, self.observed, self.controls), before)

    def test_actual_handoff_is_finalized_before_publication_without_an_identity_merge(self):
        from phase_8_b_v7_counting import replay_frames

        snapshot = deepcopy((self.observed, self.controls))
        first = replay_frames(self.observed, self.geometry,
                              source_identity=self.source, policy=self.controls)
        second = replay_frames(self.observed, self.geometry,
                               source_identity=self.source, policy=self.controls)
        self.assertEqual(first, second)
        self.assertEqual((self.observed, self.controls), snapshot)
        self.assertEqual(first["aggregate"]["total"], 0)
        self.assertEqual(first["aggregate"]["measured_total"], 0)
        self.assertEqual(first["aggregate"]["inferred_total"], 0)
        self.assertEqual(first["aggregate"]["pending"], 0)
        self.assertEqual(first["aggregate"]["invalid"], 2)
        self.assertEqual({row["track_id"] for row in first["invalid_decisions"]}, {1049, 1123})
        self.assertEqual({row["candidate_decision_frame"] for row in first["invalid_decisions"]}, {1396})
        self.assertEqual({row["decision_frame"] for row in first["invalid_decisions"]}, {1424})
        self.assertEqual(first["report"]["v7_publication"]["physical_episodes_merged"], 0)
        self.assertEqual(first["report"]["v7_publication"]["inference_promoted_to_measured"], 0)
        self.assertEqual(sum(row["count_delta"] for row in first["passage_log"]), 0)
        retained_evidence = {row["track_id"]: row["evidence"] for row in self.retained["events"]}
        for row in first["cancelled_events"]:
            self.assertEqual(row["evidence"], retained_evidence[row["track_id"]])
            self.assertIs(row["never_published"], True)
            self.assertIs(row["evidence"]["measured_crossing"], False)


if __name__ == "__main__":
    unittest.main()
