#!/usr/bin/env python3
"""Validate separately recorded N1 acceptance without modifying proposals."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    repo = args.repo.resolve()
    accepted_path = repo / "docs/evidence/phase_7/accepted_geometry/TOR3-MALAM-N1.json"
    accepted = json.loads(accepted_path.read_text())
    proposal_path = repo / accepted["source_proposal"]["path"]
    proposal = json.loads(proposal_path.read_text())
    feedback_path = repo / accepted["approval_feedback"]["path"]
    feedback = json.loads(feedback_path.read_text())
    checks = []

    def check(name: str, condition: bool) -> None:
        checks.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    check("accepted_artifact_source_hash", sha256(accepted_path) == "89ff1d6201fba37d6edb9501f1524a5c96781ff1b9f442f25b728cb4d543c7a4")
    check("proposal_source_hash_unchanged", sha256(proposal_path) == accepted["source_proposal"]["sha256"] == "4a70d56955cace14bac617c14935d8279dbe382942f17a8c417756e074448a53")
    check("feedback_hash_bound", sha256(feedback_path) == accepted["approval_feedback"]["sha256"])
    check("feedback_proposal_hash_bound", feedback["geometry_proposal"]["sha256"] == sha256(proposal_path))
    check("review_picture_hash_bound", sha256(repo / feedback["review_picture"]["path"]) == feedback["review_picture"]["sha256"] == "f01a517f3c49d9a95c653ca48382c4ff95dcfeacd145569b62a584e60cbe2958")
    check("explicit_geometry_answer_retained", feedback["questions_and_answers"][0]["answer"] == "Setuju untuk uji awal")
    check("explicit_direction_answer_retained", feedback["questions_and_answers"][1]["answer"] == "Ya, pemetaan arah benar")
    check("proposal_stays_unapproved_historical", proposal["geometry_contract_accepted"] is False and proposal["counting_execution_allowed"] is False)
    check("new_acceptance_flags", accepted["geometry_contract_accepted"] is True and accepted["counting_execution_allowed"] is True)
    check("status_initial_experiment_only", accepted["status"] == "ACCEPTED_PHASE7_INITIAL_GEOMETRY_BASELINE_NUMERIC_DEFAULTS_OPEN")
    for field in ("normalized", "line_endpoints_reference", "side_a_polygon_reference", "side_b_polygon_reference", "rendered_native_pixels", "line_polygon_endpoint_difference_reference", "source_video", "source_frame", "thresholds", "selected_anchor"):
        check("preserved_exact:"+field, accepted[field] == proposal[field])
    for key, expected in (("A_TO_B", "approaching camera"), ("B_TO_A", "moving away from camera"), ("scope", "TOR3-MALAM")):
        check("direction:"+key, accepted["confirmed_direction_metadata"][key] == expected)
    sample_path = repo / "docs/evidence/phase_7/sampling/TOR3-MALAM_sampling_plan_v1.json"
    check("sampling_plan_frozen_before_feedback", sha256(sample_path) == "23091cbc1afd5eb24f63bf6d81d2be0bdc1ab04b43a78b7d31e3e65882f6437f")
    geometry_path = repo / "notebooks/phase_5_geometry_helpers.py"
    spec = importlib.util.spec_from_file_location("retained_n1_geometry_validation", geometry_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    geometry = module.Geometry.from_draft(accepted_path, 1280, 720)
    check("from_draft_topology_valid", geometry.width == 1280 and geometry.height == 720)
    check("from_draft_exact_line", list(geometry.p1) == accepted["rendered_native_pixels"]["line"]["P1"] and list(geometry.p2) == accepted["rendered_native_pixels"]["line"]["P2"])
    check("from_draft_source_video", geometry.video_sha256 == accepted["source_video"]["sha256"])
    check("from_draft_accepted_status", geometry.source_draft_status == accepted["status"])
    result = {"status": "PASS", "passed": len(checks), "failed": 0, "checks": checks, "accepted_geometry": {"path": str(accepted_path.relative_to(repo)), "sha256": sha256(accepted_path)}, "verification_method": {"path": str(Path(__file__).resolve().relative_to(repo)), "sha256": sha256(Path(__file__).resolve())}, "retained_geometry_helper_sha256": sha256(geometry_path), "scope": "explicit feedback/source identity/exact coordinate/topology/API validation; no model or count performance"}
    output = accepted_path.parent / "acceptance_validation.json"
    output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"status": result["status"], "passed": result["passed"], "failed": 0}))


if __name__ == "__main__":
    main()
