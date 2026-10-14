#!/usr/bin/env python3
"""Deterministically derive the initial-night acceptance from retained feedback.

This replays a recorded decision; it does not approve a geometry automatically.
The proposal JSON, proposal pixels and frozen sampling plan are not modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args()
    repo = args.repo.resolve()
    proposal_path = Path("docs/evidence/phase_7/geometry_proposals/TOR3-MALAM-N1.json")
    feedback_path = Path("docs/evidence/phase_7/feedback/N1_review_001.json")
    feedback = json.loads((repo / feedback_path).read_text())
    if feedback["geometry_proposal"]["sha256"] != sha256(repo / proposal_path):
        raise ValueError("Feedback is not bound to the current retained proposal")
    answers = [item["answer"] for item in feedback["questions_and_answers"]]
    if answers != ["Setuju untuk uji awal", "Ya, pemetaan arah benar"]:
        raise ValueError("This replay requires the retained explicit N1 acceptance answers")
    value = json.loads((repo / proposal_path).read_text())
    value["draft_id"] = "TOR3-MALAM-N1-accepted-v1"
    value["status"] = "ACCEPTED_PHASE7_INITIAL_GEOMETRY_BASELINE_NUMERIC_DEFAULTS_OPEN"
    value["claim_type"] = "USER_CONFIRMED_INITIAL_EXPERIMENT_GEOMETRY"
    value["created_at_utc"] = feedback["recorded_at_utc"]
    value["source_proposal"] = {"path": str(proposal_path), "sha256": sha256(repo / proposal_path)}
    value["approval_feedback"] = {"path": str(feedback_path), "sha256": sha256(repo / feedback_path)}
    value["confirmed_direction_metadata"] = {
        "A_TO_B": "approaching camera", "B_TO_A": "moving away from camera",
        "scope": "TOR3-MALAM", "claim_type": "USER_CONFIRMED_PER_VIDEO",
    }
    value["geometry_contract_accepted"] = True
    value["counting_execution_allowed"] = True
    value["counting_execution_scope"] = "Controlled Phase7 TOR3-MALAM experiment using frozen geometry/counting contract; software tests and real source evidence still required"
    value["acceptance_limits"] = [
        "Initial per-video experiment only; reliable whole-video/production counting unproven",
        "No coordinate change or snapping from rounded question labels",
        "BC and b0_c1 remain measurement/parameter controls, not universal suitability claims",
        "No model/tracking/ReID/CountEvent results asserted by acceptance",
    ]
    value["review_questions"] = []
    output = repo / "docs/evidence/phase_7/accepted_geometry/TOR3-MALAM-N1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({"path": str(output.relative_to(repo)), "sha256": sha256(output)}))


if __name__ == "__main__":
    main()
