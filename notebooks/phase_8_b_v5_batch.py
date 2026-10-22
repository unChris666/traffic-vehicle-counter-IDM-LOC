"""Source-bound B v5 P0 research replay; immutable B v4 is the comparator.

This helper reuses validated input loading, not the old grouping/counting
decisions. It loads no model. Model experiments have their own notebook/output.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import time

import phase_8_b_v4_batch as previous
from phase_5_geometry_helpers import Geometry


POLICY_PATH = "results/b_v5/config/policy.json"
QC_ROOT = "results/phase_9/20261020_QC_BV4_SIANG"
BASELINE_ROOT = "results/b_v4/execution/pilot_machine_final"
FROZEN_KEYS = ("line_margin_half_width_px", "timeout_frames", "timeout_clock",
               "category_policy", "supported_categories", "passage_display_id")
NEW_SOURCES = ("phase_8_b_v5_identity.py", "phase_8_b_v5_counting.py",
               "phase_8_b_v5_batch.py", "phase_9_p0_qc_compare.py",
               "09a_p0_qc_replay.ipynb")


def _hash(path):
    return previous.donor.sha256_file(path)


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == ".gz" else data)


def _read(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def build_policy(repo_root):
    import phase_8_b_v5_identity as identity
    import phase_8_b_v5_counting as counting
    root = Path(repo_root).resolve()
    old_path = root / previous.POLICY
    policy = _read(old_path)
    policy.update(schema_version="phase8_b_v5_p0_policy_v1",
                  policy_version="phase9_p0_research_v1",
                  base_b_v4_policy_sha256=_hash(old_path),
                  status="EXPERIMENTAL_NOT_PRODUCTION_VALIDATED",
                  identity=identity.experimental_identity_policy(),
                  p0_counting=counting.experimental_counting_policy(),
                  qc_adjudications_used_as_machine_predictions=False)
    return policy


def prepare_b_v5_batch(*, repo_root, policy_path=None, **kwargs):
    prepared = previous.prepare_b_v4_batch(repo_root=repo_root, **kwargs)
    root = Path(repo_root).resolve()
    path = Path(policy_path).resolve() if policy_path else root / POLICY_PATH
    policy = _read(path)
    previous.donor._require(policy.get("schema_version") == "phase8_b_v5_p0_policy_v1"
        and policy.get("base_b_v4_policy_sha256") == prepared["policy_sha256"],
        "B v5 must bind the exact immutable B v4 policy")
    previous.donor._require(all(policy.get(key) == prepared["policy"].get(key)
        for key in FROZEN_KEYS), "B v5 changed frozen geometry/counting controls")
    previous.donor._require(policy.get("qc_adjudications_used_as_machine_predictions") is False,
        "QC decisions must not be substituted for automatic inference")
    for key in ("review_manifest_sha256", "review_overlay_sha256", "execution_branch"):
        policy[key] = prepared["policy"][key]
    prepared["guarded_inputs"].append({"path": str(path), "sha256": _hash(path)})
    prepared.update(policy=policy, policy_path=path, policy_sha256=_hash(path),
                    effective_policy_sha256=previous._digest_json(policy))
    return prepared


def _retention(output):
    files = [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size,
              "sha256": _hash(p)} for p in sorted(output.rglob("*"))
             if p.is_file() and p.name != "retention_manifest.json"]
    _write(output / "retention_manifest.json", {"files": files, "self_excluded": True})


def _snapshot(output):
    module_dir = Path(__file__).resolve().parent
    rows = {}
    for name in dict.fromkeys(previous.SOURCE_NAMES + NEW_SOURCES):
        path = module_dir / name
        previous.donor._require(path.is_file(), "Missing reproducibility source: " + name)
        data = path.read_bytes()
        target = output / "source_snapshot" / (name + ".gz")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(gzip.compress(data, mtime=0))
        rows[str(path)] = {"sha256": hashlib.sha256(data).hexdigest(),
                           "retained_path": target.relative_to(output).as_posix()}
    _write(output / "source_snapshot.json", rows)
    return rows


def run_b_v5_batch(*, repo_root, output_root="results/b_v5/execution",
                  run_id=None, progress=print, **kwargs):
    import phase_8_b_v5_identity as identity
    import phase_8_b_v5_counting as counting
    from phase_9_p0_qc_compare import compare_results
    prepared = prepare_b_v5_batch(repo_root=repo_root, **kwargs)
    identifier = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    previous.donor._require(isinstance(identifier, str) and identifier not in ("", ".", "..")
        and Path(identifier).name == identifier and "\\" not in identifier, "Unsafe run ID")
    root = Path(repo_root).resolve()
    output = Path(output_root).resolve() / identifier
    forbidden = [root / "results" / name for name in ("b_v2", "b_v3", "b_v4", "phase_9")]
    forbidden += [Path(prepared["source_run_root"]).resolve(),
                  *[job["video_path"].parent for job in prepared["jobs"]]]
    previous.donor._require(not output.exists() and not any(output.is_relative_to(p)
        for p in forbidden), "Output must be new and outside immutable evidence/raw input")
    output.mkdir(parents=True)
    snapshots = _snapshot(output)
    _write(output / "policy.json", prepared["policy"])
    report = {"schema_version": "phase9_p0_batch_v1", "run_id": identifier,
        "status": "running", "branch": prepared["branch"], "videos": [],
        "python": platform.python_version(), "policy_sha256": prepared["policy_sha256"],
        "effective_policy_sha256": prepared["effective_policy_sha256"],
        "new_detector_tracker_reid_execution": False, "new_enhancement_execution": False,
        "new_counting_policy_replay": True, "qc_decisions_applied_to_machine": False,
        "production_ready": False, "physical_accuracy_established": False,
        "source_scope": "FULL_SELECTED_SOURCE_HISTORY", "output_directory": str(output)}
    _write(output / "batch_report.json", report)
    started = time.perf_counter()
    try:
        for job in prepared["jobs"]:
            vid = job["video_id"]
            target = output / vid
            source = job["b_v2_source_identity"]
            geometry = Geometry.from_draft(job["b_v2_geometry_path"], source["width"], source["height"])
            links = previous.previous.relationship_evidence(job["paths"]["relations"])
            old_reviews = prepared["base_reviews"][vid].get("reviews", [])
            overlay = prepared["review_overlay"].get(vid, {}).get("reviews", [])
            proof = {}
            frames = previous.previous.adapted_frames(job["paths"]["records"], source,
                job["metadata"]["frame_count"], relationships=links,
                reviews=old_reviews + overlay, reviews_sha256=prepared["reviews_sha256"],
                application_proof=proof)
            frames = previous._attach_overlay_provenance(frames, overlay,
                prepared["review_overlay_sha256"])
            resolved = identity.prepare_identity_frames(frames, geometry,
                prepared["policy"], relationships=links)
            previous._validate_overlay_application(proof, overlay)
            effective = deepcopy(prepared["policy"])
            effective["episode_relations"] = resolved.get("unit_relations", [])
            result = counting.replay_frames(resolved["frames"], geometry,
                source_identity=source, policy=effective)
            result.update(video_id=vid, source_identity=source, branch=prepared["branch"],
                          frame_assignments=resolved["assignments"])
            _write(target / "counting_result.json.gz", result)
            _write(target / "geometry.json", _read(job["b_v2_geometry_path"]))
            _write(target / "adapter_audit.json", proof)
            _write(target / "frame_assignments.json.gz", resolved["assignments"])
            for name in ("episode_audit", "role_audit", "handoff_audit", "alias_context_audit", "unit_relations",
                         "historical_hypothesis_audit", "inherited_episode_audit", "cross_category_audit",
                         "retained_component_parent_remap_audit"):
                _write(target / (name + ".json.gz"), resolved.get(name, []))
            for name in ("eligibility_audit", "finalization_audit"):
                _write(target / (name + ".json.gz"), result.get(name, []))
            old = _read(root / BASELINE_ROOT / vid / "counting_result.json.gz")
            comparison = compare_results(old, result, root / QC_ROOT)
            _write(target / "qc_comparison.json", comparison)
            row = {"video_id": vid, "status": "completed", "frames": job["metadata"]["frame_count"],
                   "aggregate": result["aggregate"], "source_identity": source,
                   "qc_comparison_path": (target / "qc_comparison.json").relative_to(output).as_posix()}
            report["videos"].append(row)
            _write(output / "batch_report.json", report)
            if progress:
                progress({"video_id": vid, "aggregate": result["aggregate"]})
        report.update(status="completed_scoped_research_replay_pending_qc",
                      frames_processed=sum(row["frames"] for row in report["videos"]),
                      all_selected_completed=True, all_eight_completed=len(report["videos"]) == 8)
    except Exception as error:
        report.update(status="failed_or_partial", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        changed = [p for p, meta in snapshots.items() if _hash(p) != meta["sha256"]]
        changed += [meta["path"] for meta in prepared["guarded_inputs"]
                    if _hash(meta["path"]) != meta["sha256"]]
        report.update(wall_seconds=time.perf_counter() - started,
                      inputs_and_source_unchanged_during_execution=not changed)
        if changed:
            report.update(status="failed_or_partial", changed_files=changed)
        _write(output / "batch_report.json", report)
        _retention(output)
        if changed:
            raise RuntimeError("Inputs or executed source changed during replay")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-run-root")
    parser.add_argument("--source-video-root")
    parser.add_argument("--input-root", default="/kaggle/input")
    parser.add_argument("--video-ids", nargs="+", default=["weekday_siang"])
    parser.add_argument("--branch", choices=previous.BRANCHES, default="machine")
    parser.add_argument("--policy-path")
    parser.add_argument("--output-root", default="results/b_v5/execution")
    parser.add_argument("--run-id")
    args = vars(parser.parse_args())
    result = run_b_v5_batch(**args)
    print(json.dumps({key: result[key] for key in ("status", "output_directory", "frames_processed")}))


if __name__ == "__main__":
    main()
