"""Isolated replay of the user's post-QC policy; no new model execution."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
from pathlib import Path
import time

import phase_8_b_v5_batch as old
from phase_5_geometry_helpers import Geometry


POLICY_PATH = "results/b_v6/config/policy.json"
DECISION_PATH = "docs/POST_P0_POLICY_DECISIONS.md"
QC_ROOT = "results/phase_9/20261020_QC_BV4_SIANG"
SOURCES = tuple(dict.fromkeys(old.previous.SOURCE_NAMES + old.NEW_SOURCES + (
    "phase_8_b_v6_identity.py", "phase_8_b_v6_counting.py", "phase_8_b_v6_annotation.py",
    "phase_8_b_v6_batch.py", "phase_9_v6_qc_review.py", "09c_user_policy_replay.ipynb")))


def build_policy(repo_root):
    import phase_8_b_v6_identity as identity
    import phase_8_b_v6_counting as counting
    root = Path(repo_root).resolve()
    path = root / old.POLICY_PATH
    policy = old._read(path)
    policy.update(schema_version="phase9_b_v6_user_policy_v1",
        policy_version="post_qc_user_policy_v1", status="RESEARCH_USER_POLICY_NOT_PRODUCTION_VALIDATED",
        base_b_v5_policy_sha256=old._hash(path),
        decision_document_sha256=old._hash(root / DECISION_PATH),
        identity=identity.experimental_identity_policy(),
        v6_counting=counting.experimental_counting_policy(),
        supported_categories=["motorcycle", "car", "truck", "bus", "pedestrian"],
        display_category_prefixes={"motorcycle": "M", "car": "C", "truck": "T", "bus": "B", "pedestrian": "P"})
    policy["passage_display_id"]["prefixes"] = deepcopy(policy["display_category_prefixes"])
    policy["passage_display_id"]["bus_prefix"] = "B"
    policy["selected_profile"] = "post_qc_ambiguity_invalid_scoped_timeout_bus"
    policy["selection_basis"] = "Explicit user decisions; exclusions are reported, not claimed as accuracy improvements"
    return policy


def prepare_b_v6_batch(*, repo_root, policy_path=None, **kwargs):
    prepared = old.prepare_b_v5_batch(repo_root=repo_root, **kwargs)
    root = Path(repo_root).resolve()
    path = Path(policy_path).resolve() if policy_path else root / POLICY_PATH
    policy = old._read(path)
    old.previous.donor._require(policy.get("schema_version") == "phase9_b_v6_user_policy_v1"
        and policy.get("base_b_v5_policy_sha256") == prepared["policy_sha256"],
        "B v6 must bind immutable B v5 policy")
    for key in ("line_margin_half_width_px", "timeout_frames", "timeout_clock", "category_policy", "p0_counting"):
        old.previous.donor._require(policy.get(key) == prepared["policy"].get(key),
            "B v6 changed frozen controls: " + key)
    old.previous.donor._require(set(policy.get("supported_categories", []))
        == set(prepared["policy"]["supported_categories"]) | {"bus"}, "Only explicit BUS coverage is added")
    old.previous.donor._require(policy.get("decision_document_sha256") == old._hash(root / DECISION_PATH)
        and policy.get("qc_adjudications_used_as_machine_predictions") is False,
        "User decision binding or machine provenance differs")
    for key in ("review_manifest_sha256", "review_overlay_sha256", "execution_branch"):
        policy[key] = prepared["policy"][key]
    prepared["guarded_inputs"].extend([
        {"path": str(path), "sha256": old._hash(path)},
        {"path": str(root / DECISION_PATH), "sha256": old._hash(root / DECISION_PATH)}])
    prepared.update(policy=policy, policy_path=path, policy_sha256=old._hash(path),
                    effective_policy_sha256=old.previous._digest_json(policy))
    return prepared


def _snapshot(output):
    directory, result = Path(__file__).resolve().parent, {}
    for name in SOURCES:
        source = directory / name
        old.previous.donor._require(source.is_file(), "Missing reproducibility source: " + name)
        data = source.read_bytes()
        target = output / "source_snapshot" / (name + ".gz")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(gzip.compress(data, mtime=0))
        result[str(source)] = {"sha256": hashlib.sha256(data).hexdigest(),
            "retained_path": target.relative_to(output).as_posix()}
    old._write(output / "source_snapshot.json", result)
    return result


def run_b_v6_batch(*, repo_root, output_root="results/b_v6/execution", run_id=None,
                  progress=print, **kwargs):
    import phase_8_b_v6_identity as identity
    import phase_8_b_v6_counting as counting
    from phase_9_v6_qc_review import review_results
    prepared = prepare_b_v6_batch(repo_root=repo_root, **kwargs)
    root = Path(repo_root).resolve()
    identifier = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    old.previous.donor._require(isinstance(identifier, str) and identifier not in ("", ".", "..")
        and Path(identifier).name == identifier and "\\" not in identifier, "Unsafe run ID")
    output = Path(output_root).resolve() / identifier
    forbidden = [root / "results" / name for name in ("b_v2", "b_v3", "b_v4", "b_v5", "phase_9", "model_experiments")]
    forbidden += [Path(prepared["source_run_root"]).resolve(), *[job["video_path"].parent for job in prepared["jobs"]]]
    old.previous.donor._require(not output.exists() and not any(output.is_relative_to(p) for p in forbidden),
        "Output must be new and outside frozen evidence/source")
    output.mkdir(parents=True)
    snapshots = _snapshot(output)
    old._write(output / "policy.json", prepared["policy"])
    report = {"schema_version": "phase9_b_v6_batch_v1", "status": "running",
        "run_id": identifier, "branch": prepared["branch"], "videos": [], "output_directory": str(output),
        "new_model_execution": False, "new_enhancement_execution": False,
        "new_counting_policy_replay": True, "old_results_modified": False,
        "production_ready": False, "physical_accuracy_established": False,
        "policy_sha256": prepared["policy_sha256"]}
    old._write(output / "batch_report.json", report)
    began = time.perf_counter()
    try:
        for job in prepared["jobs"]:
            vid, source = job["video_id"], job["b_v2_source_identity"]
            target = output / vid
            geometry_data = old._read(job["b_v2_geometry_path"])
            geometry = Geometry.from_draft(job["b_v2_geometry_path"], source["width"], source["height"])
            links = old.previous.previous.relationship_evidence(job["paths"]["relations"])
            reviews = prepared["base_reviews"][vid].get("reviews", [])
            overlay = prepared["review_overlay"].get(vid, {}).get("reviews", [])
            proof = {}
            frames = old.previous.previous.adapted_frames(job["paths"]["records"], source,
                job["metadata"]["frame_count"], relationships=links, reviews=reviews + overlay,
                reviews_sha256=prepared["reviews_sha256"], application_proof=proof)
            frames = old.previous._attach_overlay_provenance(frames, overlay, prepared["review_overlay_sha256"])
            resolved = identity.prepare_identity_frames(frames, geometry, prepared["policy"], relationships=links)
            old.previous._validate_overlay_application(proof, overlay)
            policy = deepcopy(prepared["policy"])
            policy["episode_relations"] = resolved.get("unit_relations", [])
            result = counting.replay_frames(resolved["frames"], geometry, source_identity=source, policy=policy)
            result.update(video_id=vid, source_identity=source, branch=prepared["branch"],
                frame_assignments=resolved["assignments"], component_links=resolved.get("component_links", []))
            old._write(target / "counting_result.json.gz", result)
            old._write(target / "geometry.json", geometry_data)
            old._write(target / "adapter_audit.json", proof)
            for name in ("assignments", "episode_audit", "role_audit", "handoff_audit", "alias_context_audit",
                         "unit_relations", "historical_hypothesis_audit", "cross_category_audit",
                         "retained_component_parent_remap_audit", "ambiguity_audit",
                         "unverified_handoff_relation_audit", "known_distinct_constraint_audit"):
                old._write(target / (name + ".json.gz"), resolved.get(name, []))
            for name in ("invalid_decisions", "eligibility_audit", "finalization_audit",
                         "ambiguity_invalid_audit", "business_taxonomy_audit"):
                old._write(target / (name + ".json.gz"), result.get(name, []))
            before = old._read(root / "results/b_v5/execution/pilot_p0_v2" / vid / "counting_result.json.gz")
            qc = review_results(before, result, root / QC_ROOT)
            old._write(target / "qc_review.json", qc)
            row = {"video_id": vid, "status": "completed", "frames": job["metadata"]["frame_count"],
                   "aggregate": result["aggregate"], "source_identity": source}
            report["videos"].append(row)
            if progress: progress(row)
        report.update(status="completed_scoped_user_policy_replay_pending_review",
            frames_processed=sum(row["frames"] for row in report["videos"]), all_selected_completed=True,
            all_eight_completed=len(report["videos"]) == 8)
    except Exception as error:
        report.update(status="failed_or_partial", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        changed = [path for path, meta in snapshots.items() if old._hash(path) != meta["sha256"]]
        changed += [row["path"] for row in prepared["guarded_inputs"] if old._hash(row["path"]) != row["sha256"]]
        report.update(wall_seconds=time.perf_counter() - began, inputs_and_sources_unchanged=not changed)
        if changed: report.update(status="failed_or_partial", changed_files=changed)
        old._write(output / "batch_report.json", report)
        old._retention(output)
        if changed: raise RuntimeError("Executed source or frozen input changed during replay")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-run-root")
    parser.add_argument("--source-video-root")
    parser.add_argument("--input-root", default="/kaggle/input")
    parser.add_argument("--video-ids", nargs="+", default=["weekday_siang"])
    parser.add_argument("--branch", choices=old.previous.BRANCHES, default="machine")
    parser.add_argument("--policy-path")
    parser.add_argument("--output-root", default="results/b_v6/execution")
    parser.add_argument("--run-id")
    result = run_b_v6_batch(**vars(parser.parse_args()))
    print(result["status"])


if __name__ == "__main__":
    main()
