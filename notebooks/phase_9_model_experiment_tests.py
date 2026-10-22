"""Plan/identity guards, without running a detector or requiring CUDA."""
import copy
from pathlib import Path
import tempfile
import unittest

from phase_9_model_experiment import make_plan, validate_plan, sha256


class ExperimentGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / "profile.json"
        self.profile.write_text("{}\n")
        self.gate = Path(self.temp.name) / "p0_gate.json"
        self.gate.write_text('{"status": "PASS"}')
        self.plan = make_plan(self.profile, p0_gate_sha256=sha256(self.gate), p0_gate_path=self.gate,
                              video_path="source.mp4", output_path="new")

    def test_explicit_plan(self):
        self.assertEqual(validate_plan(self.plan), self.plan)

    def test_no_missing_p0_gate(self):
        plan = copy.deepcopy(self.plan)
        plan["p0_execution_gate"]["status"] = "NOT_RUN"
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_no_foreign_video(self):
        plan = copy.deepcopy(self.plan)
        plan["source_video_sha256"] = "b" * 64
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_p0_gate_is_bound_to_actual_evidence(self):
        self.gate.write_text('{"status": "NOT_RUN"}')
        with self.assertRaises(ValueError):
            validate_plan(self.plan)

    def test_no_simultaneous_enhancement(self):
        plan = copy.deepcopy(self.plan)
        plan["preprocessing"] = "gamma"
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_bound_profile(self):
        self.profile.write_text('{"changed": true}')
        with self.assertRaises(ValueError):
            validate_plan(self.plan)

    def test_no_unrecorded_threshold_or_window(self):
        for field, new in (("window", {}), ("variants", [])):
            plan = copy.deepcopy(self.plan)
            plan[field] = new
            with self.assertRaises(ValueError):
                validate_plan(plan)


if __name__ == "__main__":
    unittest.main()
