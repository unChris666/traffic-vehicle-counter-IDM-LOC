#!/usr/bin/env python3
"""Apply hash-bound night review to immutable retained machine snapshots.

No detector, tracker, encoder, resolver, video decoder or geometry replay is
called. Geometry predicates re-check the original measured transition. The
historical reviewed-snapshot implementation is loaded with exactly one
production provenance-literal substitution, recorded alongside its source.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import types


BASE_PATH = "docs/evidence/phase_6/option_b_verification/build_reviewed_comparison.py"
BASE_SHA256 = "663a52190f8c495533d50b36509232dad0d3fb64e0d31c0c3d669415fb38e81b"
FROZEN_PREDICATE_SOURCES = {
    "notebooks/phase_5_geometry_helpers.py": "c344aa5b73b8b75fcdd567355b867e977a3d8e170feb512cdf0d15ac61b123c9",
    "notebooks/phase_6_counting_helpers.py": "99a98807d315b42bd3995b8e68afc749e47c76b03b39329dbb5f4b867661f4c5",
}
OLD_GUARD = 'observation.get("measurement_provenance") != "retained_phase_2_detection"'
NEW_GUARD = 'observation.get("measurement_provenance") != "retained_phase_7_detection"'
OLD_FIXTURE = '"measurement_provenance": "retained_phase_2_detection", "class_name": "motorcycle"'
NEW_FIXTURE = '"measurement_provenance": "retained_phase_7_detection", "class_name": "motorcycle"'
ADAPTER_POLICY = "phase7_exact_review_measurement_provenance_adapter_v1"
OVERLAY_POLICY = "phase7_night_reviewed_snapshot_v1"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_json_gzip(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()).decode("utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True,
                                   ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_json_gzip(path, value):
    Path(path).write_bytes(gzip.compress((canonical(value) + "\n").encode("utf-8"), mtime=0))


def load_overlay(repo):
    """Load the original semantics; only new source-measurement provenance changes."""
    original = Path(repo) / BASE_PATH
    if sha256(original) != BASE_SHA256:
        raise ValueError("Frozen historical review overlay source changed")
    if any(sha256(Path(repo) / path) != expected for path, expected in FROZEN_PREDICATE_SOURCES.items()):
        raise ValueError("Frozen geometry predicates or aggregation source changed")
    source = original.read_text(encoding="utf-8")
    if source.count(OLD_GUARD) != 1:
        raise ValueError("Expected exactly one provenance validation guard")
    adapted = source.replace(OLD_GUARD, NEW_GUARD, 1)
    if adapted.replace(NEW_GUARD, OLD_GUARD, 1) != source:
        raise AssertionError("Provenance adapter changed additional semantics")
    module = types.ModuleType("phase7_review_overlay_provenance_adapted")
    module.__file__ = str(original)
    exec(compile(adapted, str(original) + "#phase7-provenance-adapter", "exec"), module.__dict__)
    provenance = {
        "policy": ADAPTER_POLICY,
        "base_path": BASE_PATH,
        "base_source_sha256": BASE_SHA256,
        "adapted_source_sha256": hashlib.sha256(adapted.encode("utf-8")).hexdigest(),
        "production_substitution_count": 1,
        "old_guard": OLD_GUARD,
        "new_guard": NEW_GUARD,
        "algorithm_category_geometry_identity_controls_changed": False,
        "historical_source_modified": False,
        "frozen_predicate_source_sha256": FROZEN_PREDICATE_SOURCES,
    }
    return module, adapted, provenance


def verify_machine_manifest(run):
    run = Path(run).resolve()
    manifest_path = run / "retention_manifest.json"
    manifest = read_json(manifest_path)
    if manifest.get("run_id") != run.name:
        raise ValueError("Machine manifest binds another run")
    before = {"retention_manifest.json": sha256(manifest_path)}
    entries = manifest.get("artifacts")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Machine manifest has no artifacts")
    for item in entries:
        path = (run / item["path"]).resolve()
        if not path.is_relative_to(run) or item["path"] in before:
            raise ValueError("Unsafe or duplicate machine-manifest entry")
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise ValueError("Machine source differs from retained manifest: " + item["path"])
        before[item["path"]] = item["sha256"]
    return before


def review_bindings(review, config, run_id, variant, decisions_sha256):
    if review.get("source_run_id") != run_id:
        raise ValueError("Review binds another run")
    if review.get("source_identity") != config.get("input_identity"):
        raise ValueError("Review binds another variant/source identity")
    if review.get("source_variant", variant) != variant:
        raise ValueError("Review names another variant")
    if review.get("source_machine_decisions_sha256") != decisions_sha256:
        raise ValueError("Review binds another machine-decision artifact")
    return True


def self_test(repo):
    """Synthetic software checks, including the unchanged historical hard guards."""
    module, adapted, provenance = load_overlay(repo)
    # Only the historical synthetic fixture donor is changed for this test;
    # production functions remain byte-identical to the retained adapter.
    if adapted.count(OLD_FIXTURE) != 1:
        raise AssertionError("Expected exactly one synthetic measurement fixture")
    test_source = adapted.replace(OLD_FIXTURE, NEW_FIXTURE, 1)
    fixture_module = types.ModuleType("phase7_review_overlay_synthetic_fixture")
    fixture_module.__file__ = module.__file__
    exec(compile(test_source, module.__file__ + "#phase7-synthetic-fixture", "exec"), fixture_module.__dict__)
    result = fixture_module.self_test(repo)
    checks = result["checks"]
    checks.append({"check": "exact_one_production_provenance_substitution", "pass": provenance["production_substitution_count"] == 1})
    checks.append({"check": "historical_overlay_source_immutable", "pass": sha256(Path(repo) / BASE_PATH) == BASE_SHA256})
    checks.append({"check": "historical_geometry_and_aggregation_sources_immutable", "pass": all(
        sha256(Path(repo) / path) == expected for path, expected in FROZEN_PREDICATE_SOURCES.items())})
    identity = {"video_sha256": "a" * 64, "records_sha256": "b" * 64, "variant": "raw"}
    review = {"source_run_id": "fixture_run", "source_identity": identity,
              "source_machine_decisions_sha256": "c" * 64}
    config = {"input_identity": identity}
    checks.append({"check": "correct_hash_bound_review_identity", "pass": review_bindings(review, config, "fixture_run", "raw", "c" * 64)})
    for name, field, bad in (
        ("wrong_review_run_rejected", "source_run_id", "other_run"),
        ("wrong_review_decision_sha_rejected", "source_machine_decisions_sha256", "d" * 64),
        ("wrong_review_variant_rejected", "source_variant", "gamma_070"),
        ("wrong_review_source_identity_rejected", "source_identity", {**identity, "records_sha256": "e" * 64}),
    ):
        changed = deepcopy(review)
        changed[field] = bad
        try:
            review_bindings(changed, config, "fixture_run", "raw", "c" * 64)
            passed = False
        except ValueError:
            passed = True
        checks.append({"check": name, "pass": passed})
    result.update({"claim_type": "EXECUTED_SYNTHETIC_PHASE7_REVIEW_OVERLAY_GUARDS_NOT_VIDEO_EVIDENCE",
                   "passed": sum(c["pass"] for c in checks), "failed": sum(not c["pass"] for c in checks),
                   "provenance_adapter": provenance,
                   "synthetic_fixture_only_substitution_count": 1,
                   "synthetic_fixture_source_sha256": hashlib.sha256(test_source.encode()).hexdigest(),
                   "model_geometry_resolver_rerun": False})
    if result["failed"]:
        raise AssertionError(canonical(result))
    return result


def execute(repo, run, variant, review_path):
    repo, run, review_path = (Path(p).resolve() for p in (repo, run, review_path))
    if variant not in {"raw", "gamma_070"}:
        raise ValueError("Only the frozen actual night branches are supported")
    if not run.is_relative_to(repo) or not review_path.is_relative_to(run / "temporal_review"):
        raise ValueError("Source run/review must be retained in this repository")
    output = run / (variant + "_reviewed")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Refusing to overwrite an existing reviewed snapshot")
    before = verify_machine_manifest(run)
    source = run / variant
    config = read_json(source / "counting_configuration.json")
    original_review_bytes = review_path.read_bytes()
    review = json.loads(original_review_bytes)
    source_report = read_json(run / "report.json")
    runtime_config = read_json(run / "configuration.json")
    if (source_report.get("run_id") != run.name
            or source_report.get("execution_kind") != "ACTUAL_MODEL_EXECUTION"
            or config["input_identity"].get("parent_run_id") != run.name
            or config["input_identity"].get("variant") != variant):
        raise ValueError("Source report/config do not bind the actual branch")
    identity = config["input_identity"]
    if sha256(source / "track_records.jsonl.gz") != identity["records_sha256"]:
        raise ValueError("Counting identity does not bind the retained source measurements")
    decisions_path = source / "machine_passage_decisions.json.gz"
    review_bindings(review, config, run.name, variant, sha256(decisions_path))
    geometry_path = (repo / runtime_config["geometry_path"]).resolve()
    if (not geometry_path.is_relative_to(repo)
            or sha256(geometry_path) != identity["geometry_sha256"]
            or runtime_config["expected_geometry_sha256"] != identity["geometry_sha256"]):
        raise ValueError("Counting/source configuration do not bind the same geometry")
    geometry_draft = read_json(geometry_path)
    if (geometry_draft.get("geometry_contract_accepted") is not True
            or geometry_draft.get("counting_execution_allowed") is not True):
        raise ValueError("Night geometry is not approved for this initial experiment")
    feedback = geometry_draft["approval_feedback"]
    feedback_path = (repo / feedback["path"]).resolve()
    if not feedback_path.is_relative_to(repo) or sha256(feedback_path) != feedback["sha256"]:
        raise ValueError("Accepted geometry review feedback hash mismatch")
    module, adapted, provenance = load_overlay(repo)
    Geometry, _, _, _ = module.geometry_imports(repo)
    geometry = Geometry.from_draft(geometry_path, identity["width"], identity["height"])
    machine_decisions = read_json_gzip(decisions_path)
    episodes = read_json_gzip(source / "episodes.json.gz")
    machine_events = read_json_gzip(source / "machine_count_events.json.gz")
    result = module.build_reviewed_snapshot(machine_decisions, episodes, machine_events,
                                           config, review, repo=repo, geometry=geometry)
    reviewed_by_id = {row["candidate_id"] for row in review["decisions"]}
    untouched = [event for event in machine_events if event["candidate_id"] not in reviewed_by_id]
    result_events = {event["event_id"]: event for event in result["accepted_events"]}
    if any(result_events.get(event["event_id"]) != event for event in untouched):
        raise AssertionError("Untouched automatic accepted payload changed")
    if verify_machine_manifest(run) != before or review_path.read_bytes() != original_review_bytes:
        raise AssertionError("Original source artifacts/review changed during postprocessing")
    synthetic_tests = self_test(repo)
    output.mkdir(parents=True, exist_ok=True)
    result["report"].update({
        "overlay_scope_policy": OVERLAY_POLICY,
        "source_run_id": run.name,
        "source_variant": variant,
        "source_artifact_sha256": before,
        "review_input_path": str(review_path.relative_to(repo)),
        "review_input_sha256": sha256(review_path),
        "method_path": str(Path(__file__).resolve().relative_to(repo)),
        "method_sha256": sha256(__file__),
        "provenance_adapter": provenance,
        "geometry_path": str(geometry_path.relative_to(repo)),
        "geometry_sha256": sha256(geometry_path),
        "geometry_approval_feedback_sha256": feedback["sha256"],
        "untouched_machine_accepted_payloads_preserved_verbatim": True,
        "preserved_machine_event_ids": [event["event_id"] for event in untouched],
        "source_manifest_artifacts_verified": len(before) - 1,
        "software_guard_tests_passed": synthetic_tests["passed"],
        "manual_review_is_formal_ground_truth": False,
        "automatic_improvement_established": False,
    })
    write_json_gzip(output / "resolved_decisions.json.gz", result["resolved_decisions"])
    write_json_gzip(output / "accepted_events.json.gz", result["accepted_events"])
    write_json(output / "aggregate.json", result["aggregate"])
    write_json(output / "report.json", result["report"])
    (output / "review_input.json").write_bytes(original_review_bytes)
    (output / "review_adapter.executed_source.py").write_text(adapted, encoding="utf-8")
    write_json(output / "review_adapter_provenance.json", provenance)
    write_json(output / "synthetic_tests.json", synthetic_tests)
    artifacts = sorted(path for path in output.iterdir() if path.is_file())
    write_json(output / "execution_manifest.json", {
        "claim_type": "EXECUTED_PHASE7_REVIEWED_OVERLAY_REPRODUCIBILITY_MANIFEST",
        "source_run_id": run.name,
        "source_variant": variant,
        "source_machine_retention_manifest_sha256": before["retention_manifest.json"],
        "source_artifact_sha256": before,
        "method_sha256": sha256(__file__),
        "artifacts": [{"path": p.name, "sha256": sha256(p), "size_bytes": p.stat().st_size} for p in artifacts],
        "accepted_unique_event_subtotal": result["aggregate"]["total"],
        "automatic_acceptance_claimed_for_manual_events": False,
        "model_geometry_resolver_rerun": False,
    })
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--variant", choices=("raw", "gamma_070"))
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(args.repo), indent=2))
    else:
        if args.run is None or args.variant is None or args.reviews is None:
            parser.error("--run, --variant and --reviews are required without --self-test")
        result = execute(args.repo, args.run, args.variant, args.reviews)
        print(json.dumps({"aggregate": result["aggregate"], "report": result["report"]}, indent=2))
