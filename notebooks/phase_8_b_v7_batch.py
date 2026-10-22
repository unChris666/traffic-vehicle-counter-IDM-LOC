"""Isolated full-pilot B v7 replay of retained measurements; no model execution."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
from pathlib import Path
import time

import phase_8_b_v6_batch as previous
from phase_5_geometry_helpers import Geometry
from phase_8_b_v7_handoff import experimental_handoff_policy


POLICY_PATH = "results/b_v7/config/policy.json"
BASELINE_RESULT = "results/b_v6/execution/pilot_v6_machine_final/weekday_siang/counting_result.json.gz"
PILOT_VIDEO_ID = "weekday_siang"
PILOT_FRAME_COUNT = 9128
SOURCES = tuple(dict.fromkeys(previous.SOURCES + (
    "phase_8_b_v7_handoff.py", "phase_8_b_v7_counting.py", "phase_8_b_v7_batch.py",
    "phase_8_b_v7_handoff_tests.py", "phase_8_b_v7_counting_tests.py",
    "phase_8_b_v7_batch_tests.py", "09d_motion_handoff_replay.ipynb")))
_read, _write, _hash = previous.old._read, previous.old._write, previous.old._hash
_require = previous.old.previous.donor._require


def build_policy(repo_root):
    root = Path(repo_root).resolve()
    path = root / previous.POLICY_PATH
    policy = _read(path)
    policy.update(schema_version="phase9_b_v7_handoff_policy_v1",
        policy_version="bounded_unverified_handoff_publication_v1",
        status="RESEARCH_SCOPED_CONFLICT_NOT_PHYSICAL_IDENTITY_VALIDATION",
        base_b_v6_policy_sha256=_hash(path), v7_handoff=experimental_handoff_policy(),
        selected_profile="b_v7_offline_bounded_trajectory_conflict",
        selection_basis="Declared research controls; no model tuning or QC labels as predictions")
    return policy


def prepare_b_v7_batch(*, repo_root, policy_path=None, video_ids=None, branch="machine", **kwargs):
    selected = [PILOT_VIDEO_ID] if video_ids is None else list(video_ids)
    _require(selected == [PILOT_VIDEO_ID] and branch == "machine",
        "B v7 experiment is restricted to the full weekday_siang machine pilot")
    prepared = previous.prepare_b_v6_batch(repo_root=repo_root,
        video_ids=selected, branch=branch, **kwargs)
    root = Path(repo_root).resolve()
    path = Path(policy_path).resolve() if policy_path else root / POLICY_PATH
    policy = _read(path)
    _require(policy == build_policy(root),
        "B v7 must preserve frozen B v6 controls and bind the exact explicit handoff policy")
    _require(policy["base_b_v6_policy_sha256"] == prepared["policy_sha256"],
        "B v7 must bind immutable B v6 policy")
    _require(len(prepared["jobs"]) == 1
        and prepared["jobs"][0]["metadata"]["frame_count"] == PILOT_FRAME_COUNT,
        "Full 9128-source-frame pilot required; no cropped counting replay")
    baseline_path = root / BASELINE_RESULT
    baseline = _read(baseline_path)
    source = prepared["jobs"][0]["b_v2_source_identity"]
    _require(all(baseline["source_identity"].get(k) == source[k]
        for k in ("video_sha256", "records_sha256", "geometry_sha256")),
        "B v7 source/cache/geometry differs from the frozen B v6 comparator")
    for key in ("review_manifest_sha256", "review_overlay_sha256", "execution_branch"):
        policy[key] = prepared["policy"][key]
    prepared["guarded_inputs"].extend([
        {"path": str(path), "sha256": _hash(path)},
        {"path": str(baseline_path), "sha256": _hash(baseline_path)}])
    prepared.update(policy=policy, policy_path=path, policy_sha256=_hash(path),
        effective_policy_sha256=previous.old.previous._digest_json(policy),
        baseline_result_path=baseline_path, baseline_result_sha256=_hash(baseline_path))
    return prepared


def _new_output(repo_root, output_root, identifier, prepared):
    _require(isinstance(identifier, str) and identifier not in ("", ".", "..")
        and Path(identifier).name == identifier and "\\" not in identifier, "Unsafe run ID")
    root = Path(repo_root).resolve()
    directory = Path(output_root)
    directory = directory if directory.is_absolute() else root / directory
    output = (directory / identifier).resolve()
    results = root / "results"
    _require(not output.is_relative_to(results)
        or output.is_relative_to(results / "b_v7" / "execution"),
        "Outputs inside results must use new b_v7/execution; old results and fixtures are immutable")
    frozen = [Path(prepared["source_run_root"]).resolve(),
              *[Path(job["video_path"]).resolve().parent for job in prepared["jobs"]]]
    _require(not output.exists() and not any(output.is_relative_to(p) for p in frozen),
        "Output must be new and outside frozen source/cache")
    return output


def _snapshot(output):
    sources, directory = {}, Path(__file__).resolve().parent
    for name in SOURCES:
        source = directory / name
        _require(source.is_file(), "Missing reproducibility source: " + name)
        data = source.read_bytes()
        target = output / "source_snapshot" / (name + ".gz")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(gzip.compress(data, mtime=0))
        sources[str(source)] = {"sha256": hashlib.sha256(data).hexdigest(),
            "retained_path": target.relative_to(output).as_posix()}
    _write(output / "source_snapshot.json", sources)
    return sources


def run_b_v7_batch(*, repo_root, output_root="results/b_v7/execution", run_id=None,
                  progress=print, **kwargs):
    import phase_8_b_v6_identity as identity
    import phase_8_b_v7_counting as counting
    prepared = prepare_b_v7_batch(repo_root=repo_root, **kwargs)
    identifier = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = _new_output(repo_root, output_root, identifier, prepared)
    output.mkdir(parents=True)
    snapshots = _snapshot(output)
    _write(output / "policy.json", prepared["policy"])
    _write(output / "guarded_inputs.json", prepared["guarded_inputs"])
    report = {"schema_version": "phase9_b_v7_batch_v1", "run_id": identifier,
        "status": "running", "branch": "machine", "videos": [], "output_directory": str(output),
        "policy_sha256": prepared["policy_sha256"],
        "effective_policy_sha256": prepared["effective_policy_sha256"],
        "baseline_result_sha256": prepared["baseline_result_sha256"],
        "new_detector_tracker_reid_execution": False, "new_enhancement_execution": False,
        "new_counting_policy_replay": True, "qc_adjudications_used_as_machine_predictions": False,
        "old_results_modified": False, "production_ready": False, "physical_accuracy_established": False}
    _write(output / "batch_report.json", report)
    started = time.perf_counter()
    try:
        job = prepared["jobs"][0]
        source, vid = job["b_v2_source_identity"], job["video_id"]
        target = output / vid
        geometry = Geometry.from_draft(job["b_v2_geometry_path"], source["width"], source["height"])
        adapter = previous.old.previous.previous
        links = adapter.relationship_evidence(job["paths"]["relations"])
        reviews = prepared["base_reviews"][vid].get("reviews", [])
        overlay = prepared["review_overlay"].get(vid, {}).get("reviews", [])
        _require(not overlay, "No new QC overlay may become a machine prediction")
        proof = {}
        frames = adapter.adapted_frames(job["paths"]["records"], source,
            PILOT_FRAME_COUNT, relationships=links, reviews=reviews,
            reviews_sha256=prepared["reviews_sha256"], application_proof=proof)
        frames = previous.old.previous._attach_overlay_provenance(frames, overlay,
            prepared["review_overlay_sha256"])
        resolved = identity.prepare_identity_frames(frames, geometry, prepared["policy"], relationships=links)
        previous.old.previous._validate_overlay_application(proof, overlay)
        _require([row["frame_index"] for row in resolved["frames"]] == list(range(PILOT_FRAME_COUNT)),
            "Source frame history must be continuous and complete")
        policy = deepcopy(prepared["policy"])
        policy["episode_relations"] = resolved.get("unit_relations", [])
        result = counting.replay_frames(resolved["frames"], geometry, source_identity=source, policy=policy)
        result.update(video_id=vid, source_identity=source, branch="machine",
            frame_assignments=resolved["assignments"], component_links=resolved.get("component_links", []))
        _write(target / "counting_result.json.gz", result)
        _write(target / "geometry.json", _read(job["b_v2_geometry_path"]))
        _write(target / "adapter_audit.json", proof)
        _write(target / "source_identity.json", source)
        for name, value in resolved.items():
            if name != "frames":
                _write(target / (name + ".json.gz"), value)
        for name in ("invalid_decisions", "eligibility_audit", "finalization_audit",
                     "ambiguity_invalid_audit", "business_taxonomy_audit", "v7_handoff_relations",
                     "v7_handoff_audit", "v7_publication_audit", "events", "decisions", "passage_log"):
            _write(target / (name + ".json.gz"), result.get(name, []))
        row = {"video_id": vid, "status": "completed", "frames": PILOT_FRAME_COUNT,
            "aggregate": result["aggregate"], "source_identity": source,
            "v7_publication": result["report"]["v7_publication"]}
        report["videos"].append(row)
        report.update(status="completed_scoped_research_replay_pending_qc", frames_processed=PILOT_FRAME_COUNT,
            all_selected_completed=True, all_eight_completed=False)
        if progress:
            progress(row)
    except Exception as error:
        report.update(status="failed_or_partial", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        changed = [path for path, meta in snapshots.items() if _hash(path) != meta["sha256"]]
        changed += [row["path"] for row in prepared["guarded_inputs"]
                    if _hash(row["path"]) != row["sha256"]]
        report.update(wall_seconds=time.perf_counter() - started, inputs_and_sources_unchanged=not changed)
        if changed:
            report.update(status="failed_or_partial", changed_files=changed)
        _write(output / "batch_report.json", report)
        previous.old._retention(output)
        if changed:
            raise RuntimeError("Executed sources or frozen inputs changed during replay")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-run-root")
    parser.add_argument("--source-video-root")
    parser.add_argument("--input-root", default="/kaggle/input")
    parser.add_argument("--policy-path")
    parser.add_argument("--output-root", default="results/b_v7/execution")
    parser.add_argument("--run-id")
    print(run_b_v7_batch(**vars(parser.parse_args()))["status"])


if __name__ == "__main__":
    main()
