"""Deterministic synthetic B v4 contracts; no video accuracy claim."""
from copy import deepcopy
import unittest
from phase_8_b_v3_counting_tests import GEOMETRY, SOURCE, observation, frames
from phase_8_b_v4_counting import replay_frames

POLICY = {"line_margin_half_width_px": 5, "timeout_frames": 60,
          "timeout_clock": "last_observed_origin", "category_policy": "band_majority_ties_pending",
          "return_timeout_policy": "require_new_passage_evidence", "pedestrian_routes": "measured_only",
          "eligibility": {"schema_version": "phase8_b_v4_eligibility_policy_v1",
                          "min_toward_progress_px": 5,
                          "min_contiguous_observations": 3, "finite_projection_required": True}}

def run(samples, end=None, policy=None):
    return replay_frames(frames(samples, end=end), GEOMETRY,
                         source_identity=SOURCE, policy=policy or POLICY)


class Bv4CountingContracts(unittest.TestCase):
    def test_short_measured_crossing_not_gated_by_approach(self):
        r = run({0: 30, 1: 70})
        self.assertEqual(r["aggregate"]["measured_total"], 1)

    def test_two_directions_and_return_are_distinct_passages(self):
        r = run({0: 30, 1: 70, 2: 30})
        self.assertEqual(r["aggregate"]["total"], 2)
        self.assertEqual({e["direction"] for e in r["events"]}, {"A_TO_B", "B_TO_A"})

    def test_single_jitter_step_does_not_arm_timeout(self):
        self.assertEqual(run({0: 20, 1: 21}, 100)["aggregate"]["total"], 0)

    def test_three_small_steps_below_displacement_do_not_arm(self):
        self.assertEqual(run({0: 20, 1: 21, 2: 22}, 100)["aggregate"]["total"], 0)

    def test_distinct_contiguous_frames_required(self):
        self.assertEqual(run({0: 20, 2: 25, 4: 30}, 100)["aggregate"]["total"], 0)

    def test_timeout_exactly_last_origin_plus_sixty(self):
        self.assertEqual(run({0: 20, 1: 23, 2: 26}, 61)["aggregate"]["total"], 0)
        r = run({0: 20, 1: 23, 2: 26}, 62)
        self.assertEqual(r["events"][0]["activation_frame"], 62)
        self.assertFalse(r["events"][0]["evidence"]["measured_crossing"])

    def test_visible_origin_resets_clock_including_stationary(self):
        samples = {0: 20, 1: 23, **{f: 26 for f in range(2, 100)}}
        self.assertEqual(run(samples)["aggregate"]["total"], 0)

    def test_visible_before_gate_blocks_elapsed_timer(self):
        samples = {0: 20, 1: 30, 2: 40, **{f: 44 for f in range(3, 100)}}
        r = run(samples)
        self.assertEqual(r["aggregate"]["total"], 0)
        self.assertTrue(any(a["reason"] == "CURRENT_MEASUREMENT_CONTRADICTS_DISAPPEARANCE"
                            for a in r["eligibility_audit"]))

    def test_small_reverse_jitter_is_not_uturn(self):
        r = run({0: 20, 1: 23, 2: 26, 3: 25.5}, 63)
        self.assertEqual(r["aggregate"]["total"], 1)

    def test_positive_measured_retreat_disarms_timeout(self):
        r = run({0: 20, 1: 23, 2: 26, 3: 20}, 100)
        self.assertEqual(r["aggregate"]["total"], 0)

    def test_boundary_seen_as_rider_retires_old_vehicle_timer(self):
        rider = observation(30, category="person", role="rider", episode_id="new-person",
                            identity_episode_boundary=True, identity_episode_reason="CONTEXT_SWITCH")
        r = run({0: [observation(20, episode_id="old")],
                 1: [observation(23, episode_id="old")],
                 2: [observation(26, episode_id="old")], 3: [rider]}, 100)
        self.assertEqual(r["aggregate"]["total"], 0)
        self.assertEqual(r["report"]["counters"]["closed_physical_episode_candidates"], 1)

    def test_new_episode_does_not_inherit_old_origin(self):
        r = run({0: [observation(20, episode_id="old")],
                 1: [observation(23, episode_id="old")],
                 2: [observation(26, episode_id="old")],
                 3: [observation(70, episode_id="new", identity_episode_boundary=True)],
                 4: [observation(80, episode_id="new")],
                 5: [observation(90, episode_id="new")]}, 100)
        self.assertEqual(r["aggregate"]["total"], 0)

    def test_completed_then_new_departing_fragment_does_not_count_again(self):
        r = run({0: 30, 1: 70, 2: [observation(75, track=2)],
                 3: [observation(80, track=2)], 4: [observation(85, track=2)]}, 100)
        self.assertEqual(r["aggregate"]["total"], 1)

    def test_conflict_holds_only_related_timeout(self):
        samples = {f: [observation(y, track=1, detection=0, identity_timeout_hold=["POSSIBLE_HANDOFF"]),
                       observation(y, track=2, detection=1)] for f, y in enumerate((20, 23, 26))}
        r = run(samples, 62)
        self.assertEqual(r["aggregate"]["total"], 1)
        self.assertEqual(r["events"][0]["track_id"], 2)
        self.assertTrue(any("IDENTITY_CONTINUITY_UNRESOLVED_FOR_TIMEOUT" in d["reasons"]
                            for d in r["decisions"]))

    def test_verified_handoff_same_passage_and_clock(self):
        metadata = {"unit": "physical:1", "episode_id": "verified", "association_verified": True,
                    "association_id": "proof:1"}
        r = run({0: [observation(20, **metadata)], 1: [observation(23, **metadata)],
                 2: [observation(26, track=2, **metadata)],
                 10: [observation(26, track=2, **metadata)]}, 70)
        self.assertEqual(r["aggregate"]["total"], 1)
        self.assertEqual(r["events"][0]["activation_frame"], 70)

    def test_simultaneous_aliases_do_not_supply_three_source_frames(self):
        metadata = {"unit": "one", "association_verified": True, "association_id": "proof"}
        r = run({0: [observation(20, track=i, detection=i, **metadata) for i in (1, 2, 3)],
                 1: [observation(30, **metadata)]}, 100)
        self.assertEqual(r["aggregate"]["total"], 0)

    def test_suppressed_verified_alias_still_holds_timeout(self):
        m = {"unit": "one", "association_verified": True, "association_id": "proof"}
        samples = {f: [observation(y, track=1, detection=0, **m),
                       observation(y, track=2, detection=1, identity_timeout_hold=["CONFLICT"], **m)]
                   for f, y in enumerate((20, 23, 26))}
        r = run(samples, 62)
        self.assertEqual(r["aggregate"]["total"], 0)
        self.assertEqual(r["aggregate"]["pending"], 1)

    def test_local_raw_context_split_does_not_close_other_current_alias(self):
        m = {"unit": "physical", "episode_id": "episode", "association_verified": True,
             "association_id": "positive-proof"}
        samples = {0: [observation(30, track=1, **m)],
                   1: [observation(47, track=1, **m), observation(47, track=2, detection=1, **m)],
                   2: [observation(70, track=2, detection=1, **m),
                       observation(30, track=1, category="person", role="rider", episode_id="person",
                                   identity_episode_boundary=True)],
                   3: [observation(80, track=2, **m)]}
        r = run(samples, 100)
        self.assertEqual(r["aggregate"]["total"], 1)
        self.assertFalse(r["events"][0]["evidence"]["measured_crossing"])
        self.assertTrue(r["report"]["counters"]["episode_closure_deferred_current_alias_remains"])

    def test_later_identity_hold_cancels_provisional_estimate(self):
        r = run({0: 20, 1: 23, 2: 26,
                 65: [observation(26, identity_timeout_hold=["LATER_CONFLICT"])]}, 100)
        self.assertEqual(r["aggregate"]["total"], 0)
        self.assertEqual(r["aggregate"]["cancelled"], 1)
        self.assertEqual(sum(row["count_delta"] for row in r["passage_log"]), 0)

    def test_closed_counting_key_cannot_silently_revive(self):
        with self.assertRaisesRegex(ValueError, "fresh episode_id"):
            run({0: [observation(20, episode_id="old")],
                 1: [observation(23, episode_id="old")],
                 2: [observation(26, episode_id="old")],
                 3: [observation(30, category="person", role="rider", episode_id="bounded-role",
                                 identity_episode_boundary=True)],
                 4: [observation(30, episode_id="old", identity_episode_boundary=True)],
                 5: [observation(70, episode_id="old")]})

    def test_gap_cannot_be_claimed_as_measured_crossing(self):
        r = run({0: 20, 1: 25, 2: 30, 4: 70})
        self.assertEqual(r["aggregate"]["total"], 1)
        self.assertEqual(r["aggregate"]["measured_total"], 0)

    def test_endpoint_extension_never_becomes_measured(self):
        r = run({0: [observation(20, x=5)], 1: [observation(25, x=5)],
                 2: [observation(30, x=5)], 3: [observation(70, x=5)]}, 100)
        self.assertEqual(r["aggregate"]["total"], 0)

    def test_diagonal_measured_intersection_with_earlier_outside_projection(self):
        r = run({0: [observation(30, x=5)], 1: [observation(70, x=50)]})
        self.assertEqual(r["aggregate"]["measured_total"], 1)

    def test_timeout_upgrade_is_one_passage_not_second_count(self):
        r = run({0: 20, 1: 23, 2: 26, 65: 70}, 70)
        self.assertEqual(r["aggregate"]["total"], 1)
        self.assertEqual(sum(row["count_delta"] for row in r["passage_log"]), 1)

    def test_pedestrian_requires_positive_role_and_rider_is_zero(self):
        r = run({0: [observation(30, category="person", role="rider")],
                 1: [observation(70, category="person", role="rider")]})
        self.assertEqual(r["aggregate"]["total"], 0)
        p = run({0: [observation(30, category="person", role="pedestrian")],
                 1: [observation(70, category="person", role="pedestrian")]})
        self.assertEqual(p["aggregate"]["pedestrian_total"], 1)

    def test_nonobserved_prediction_is_rejected(self):
        with self.assertRaises(ValueError):
            run({0: [observation(30, observed=False)]})

    def test_configuration_is_explicit_and_inputs_unmodified(self):
        samples = {0: 20, 1: 23, 2: 26}
        p = deepcopy(POLICY)
        result = run(samples, 62, p)
        self.assertEqual(p, POLICY)
        self.assertEqual(result["report"]["version"], "b_v4_episode_eligibility_v1")
        p.pop("eligibility")
        with self.assertRaises(ValueError):
            run(samples, 62, p)


if __name__ == "__main__":
    unittest.main()
