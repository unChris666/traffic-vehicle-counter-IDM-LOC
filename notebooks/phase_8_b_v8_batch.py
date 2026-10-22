"""P1 reviewed replay over frozen B v7 inputs; never a machine-model benchmark."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
from pathlib import Path
import time

import phase_8_b_v7_batch as previous
from phase_5_geometry_helpers import Geometry


POLICY_PATH = "results/b_v8/config/policy.json"
OVERLAY_PATH = "results/b_v8/config/review_overlay.json"
ADJUDICATIONS_PATH = "results/b_v8/config/pending_adjudications.json"
BASELINE_RESULT = "results/b_v7/execution/pilot_v7_machine_final/weekday_siang/counting_result.json.gz"
BASELINE_GATE = "results/b_v7/review/p0_gate.json"
SOURCES = tuple(dict.fromkeys(previous.SOURCES + (
    "phase_8_b_v8_review.py", "phase_8_b_v8_review_tests.py",
    "phase_8_b_v8_finalize.py", "phase_8_b_v8_finalize_tests.py",
    "phase_8_b_v8_batch.py", "phase_8_b_v8_batch_tests.py",
    "phase_8_b_v8_replay_tests.py",
    "09e_p1_pending_recovery.ipynb")))
_read, _write, _hash, _require = previous._read, previous._write, previous._hash, previous._require


def _resolve(root, value, default):
    path = Path(default if value is None else value)
    return (path if path.is_absolute() else root / path).resolve()


def load_machine_baseline(repo_root):
    """Read the exact retained B v7 output; this does not execute counting."""
    root = Path(repo_root).resolve()
    path = root / BASELINE_RESULT
    result, gate = _read(path), _read(root / BASELINE_GATE)
    _require(_hash(path) == gate.get("active_candidate_sha256"),
        "Retained B v7 machine baseline differs from its gate binding")
    return result, path, _hash(path)


def build_policy(repo_root, *, overlay_path=None, adjudications_path=None):
    root = Path(repo_root).resolve()
    policy = deepcopy(_read(root / previous.POLICY_PATH))
    overlay = _resolve(root, overlay_path, OVERLAY_PATH)
    adjudications = _resolve(root, adjudications_path, ADJUDICATIONS_PATH)
    policy.update(schema_version="phase9_b_v8_p1_review_policy_v1",
        policy_version="source_scoped_p1_reviewed_recovery_v1",
        base_b_v7_policy_sha256=_hash(root / previous.POLICY_PATH),
        status="RESEARCH_REVIEW_ASSISTED_NOT_AUTOMATIC_PRODUCTION",
        selected_profile="b_v8_p1_scoped_review_pending_recovery",
        selection_basis="Explicit source-bound review; not automatic model performance",
        execution_branch="review_assisted", review_overlay_sha256=_hash(overlay),
        v8_review={"schema_version": "phase9_b_v8_review_controls_v1",
            "branch": "review_assisted", "overlay_sha256": _hash(overlay),
            "pending_adjudications_sha256": _hash(adjudications),
            "finalization": "ACTUAL_SOURCE_EOF_OFFLINE",
            "baseline_is_retained_not_reexecuted": True,
            "qc_adjudications_used_as_machine_predictions": False,
            "source_bc_and_v7_duplicate_controls_unchanged": True})
    return policy


def prepare_b_v8_batch(*, repo_root, overlay_path=None, adjudications_path=None,
                      policy_path=None, branch="review_assisted", **kwargs):
    _require(branch == "review_assisted",
        "B v8 replay is review_assisted; the machine baseline is read-only B v7")
    root = Path(repo_root).resolve()
    prepared = previous.prepare_b_v7_batch(repo_root=root, branch="machine", **kwargs)
    baseline, baseline_path, baseline_hash = load_machine_baseline(root)
    job = prepared["jobs"][0]
    source = job["b_v2_source_identity"]
    _require(baseline.get("source_identity") == source,
        "B v8 source/cache/geometry differs from the retained B v7 comparator")
    overlay_file = _resolve(root, overlay_path, OVERLAY_PATH)
    adjudications_file = _resolve(root, adjudications_path, ADJUDICATIONS_PATH)
    overlay, adjudications = _read(overlay_file), _read(adjudications_file)
    _require(isinstance(overlay, dict) and isinstance(adjudications, dict),
        "P1 overlay and pending adjudications must be explicit manifests")
    _require(adjudications.get("schema_version") == "phase9_b_v8_pending_adjudications_v1",
        "Unknown P1 pending adjudication schema")
    _require(adjudications.get("baseline_result_sha256") == baseline_hash,
        "Pending adjudications must bind the exact B v7 result bytes")
    selected = [v for v in overlay.get("videos", []) if v.get("video_id") == job["video_id"]]
    _require(len(selected) == 1 and len(overlay.get("videos", [])) == 1,
        "P1 overlay must contain exactly the selected pilot video")
    for key in ("video_sha256", "records_sha256", "geometry_sha256"):
        _require(selected[0].get(key) == source[key]
            and adjudications.get("source_identity", {}).get(key) == source[key],
            "P1 review source binding differs: " + key)
    proof_rows = []
    for entry in adjudications.get("adjudications", []):
        for artifact in entry.get("proof_artifacts", []):
            relative = Path(artifact["path"])
            proof_path = (root / relative).resolve()
            _require(not relative.is_absolute() and proof_path.is_relative_to(root)
                and proof_path.is_file() and _hash(proof_path) == artifact.get("sha256"),
                "Pending source proof artifact binding differs")
            proof_rows.append({"path": str(proof_path), "sha256": artifact["sha256"]})
    path = _resolve(root, policy_path, POLICY_PATH)
    policy = _read(path)
    _require(policy == build_policy(root, overlay_path=overlay_file,
                                   adjudications_path=adjudications_file),
        "B v8 must preserve B v7 controls and bind exact review manifests")
    _require(policy["base_b_v7_policy_sha256"] == prepared["policy_sha256"],
        "B v8 must bind the immutable B v7 policy")
    for key in ("review_manifest_sha256",):
        policy[key] = prepared["policy"][key]
    prepared["guarded_inputs"].extend({"path": str(p), "sha256": _hash(p)}
        for p in (path, overlay_file, adjudications_file, baseline_path, root / BASELINE_GATE))
    prepared["guarded_inputs"].extend(proof_rows)
    prepared.update(policy=policy, policy_path=path, policy_sha256=_hash(path),
        effective_policy_sha256=previous.previous.old.previous._digest_json(policy),
        branch=branch, p1_overlay=overlay, p1_overlay_path=overlay_file,
        p1_overlay_sha256=_hash(overlay_file), adjudications=adjudications,
        adjudications_path=adjudications_file, baseline_result=baseline,
        baseline_result_path=baseline_path, baseline_result_sha256=baseline_hash)
    return prepared


def _new_output(repo_root, output_root, identifier, prepared):
    _require(isinstance(identifier, str) and identifier not in ("", ".", "..")
        and Path(identifier).name == identifier and "\\" not in identifier, "Unsafe run ID")
    root = Path(repo_root).resolve()
    output = (_resolve(root, output_root, "results/b_v8/execution") / identifier).resolve()
    results = root / "results"
    _require(not output.is_relative_to(results)
        or output.is_relative_to(results / "b_v8/execution"),
        "Outputs inside results must use new b_v8/execution; historical results are immutable")
    forbidden = [Path(prepared["source_run_root"]).resolve(),
                 *[Path(job["video_path"]).resolve().parent for job in prepared["jobs"]]]
    _require(not output.exists() and not any(output.is_relative_to(p) for p in forbidden),
        "Output must be new and outside frozen source/cache")
    return output


def _snapshot(output):
    result, directory = {}, Path(__file__).resolve().parent
    for name in SOURCES:
        source = directory / name
        _require(source.is_file(), "Missing reproducibility source: " + name)
        data = source.read_bytes()
        target = output / "source_snapshot" / (name + ".gz")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(gzip.compress(data, mtime=0))
        result[str(source)] = {"sha256": hashlib.sha256(data).hexdigest(),
            "retained_path": target.relative_to(output).as_posix()}
    _write(output / "source_snapshot.json", result)
    return result


def _rename_event_ids(result):
    mapping = {e["event_id"]: e["event_id"].replace("b_v7_", "b_v8_", 1)
        for e in result["events"] + result.get("cancelled_events", [])}
    def visit(value):
        if isinstance(value, dict):
            return {mapping.get(k, k): visit(v) for k, v in value.items()}
        if isinstance(value, list):
            return [visit(v) for v in value]
        return mapping.get(value, value) if isinstance(value, str) else value
    return visit(result)


def _decision_provenance(result, overlay, *, finalization_frame, overlay_sha256):
    """Keep review dependency per decision, including unchanged machine evidence."""
    reviews = {r["review_id"]: r for v in overlay["videos"] for r in v.get("reviews", [])}
    def dependencies(value):
        if isinstance(value, dict):
            found = {value["review_id"]} if value.get("review_id") in reviews else set()
            for child in value.values():
                found |= dependencies(child)
            return found
        if isinstance(value, list):
            return set().union(*(dependencies(child) for child in value)) if value else set()
        return set()
    rows = []
    for item in result.get("events", []) + result.get("decisions", []):
        if item.get("status") not in ("accepted", "pending", "invalid", "resolved_not_eligible"):
            continue
        ids = sorted(dependencies(item))
        origin = item.get("decision_origin") or (
            "SOURCE_REVIEW_ASSISTED_REPLAY" if ids else "REPLAYED_MACHINE_RULES")
        rows.append({"event_id": item.get("event_id"), "track_id": item.get("track_id"),
            "physical_unit_id": item.get("physical_unit_id"), "episode_id": item.get("episode_id"),
            "passage_id": item.get("passage_id"), "status": item.get("status"),
            "candidate_decision_frame": item.get("candidate_decision_frame", item.get("decision_frame")),
            "offline_finalization_frame": finalization_frame,
            "decision_origin": origin, "p1_review_ids": ids,
            "review_claim_types": sorted({reviews[rid].get("claim_type", "UNKNOWN") for rid in ids}),
            "overlay_sha256": overlay_sha256 if ids else None,
            "not_an_automatic_role_or_identity_prediction": bool(ids)})
    result["v8_decision_provenance"] = rows


def run_b_v8_batch(*, repo_root, output_root="results/b_v8/execution", run_id=None,
                  progress=print, **kwargs):
    import phase_8_b_v6_identity as identity
    import phase_8_b_v7_counting as counting
    from phase_8_b_v8_review import prepare_reviewed_frames
    from phase_8_b_v8_finalize import finalize_reviewed_pending
    prepared = prepare_b_v8_batch(repo_root=repo_root, **kwargs)
    root = Path(repo_root).resolve()
    identifier = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = _new_output(root, output_root, identifier, prepared)
    output.mkdir(parents=True)
    snapshots = _snapshot(output)
    _write(output / "policy.json", prepared["policy"])
    _write(output / "review_overlay.json", prepared["p1_overlay"])
    _write(output / "pending_adjudications.json", prepared["adjudications"])
    report = {"schema_version": "phase9_b_v8_p1_batch_v1", "run_id": identifier,
        "status": "running", "branch": "review_assisted", "videos": [],
        "output_directory": str(output), "policy_sha256": prepared["policy_sha256"],
        "effective_policy_sha256": prepared["effective_policy_sha256"],
        "baseline_result_sha256": prepared["baseline_result_sha256"],
        "machine_baseline_replayed": False, "machine_baseline_is_retained_b_v7": True,
        "new_detector_tracker_reid_execution": False, "new_enhancement_execution": False,
        "new_counting_policy_replay": True, "new_reviewed_adjudications_applied": True,
        "qc_adjudications_used_as_machine_predictions": False,
        "old_results_modified": False, "production_ready": False,
        "physical_accuracy_established": False}
    _write(output / "baseline_reference.json", {"path": str(prepared["baseline_result_path"]),
        "sha256": prepared["baseline_result_sha256"], "branch": "machine",
        "aggregate": prepared["baseline_result"]["aggregate"], "replayed_in_p1": False})
    _write(output / "batch_report.json", report)
    began = time.perf_counter()
    try:
        job = prepared["jobs"][0]
        source, vid = job["b_v2_source_identity"], job["video_id"]
        target = output / vid
        geometry = Geometry.from_draft(job["b_v2_geometry_path"], source["width"], source["height"])
        adapter = previous.previous.old.previous.previous
        links = adapter.relationship_evidence(job["paths"]["relations"])
        proof = {}
        frames = adapter.adapted_frames(job["paths"]["records"], source, previous.PILOT_FRAME_COUNT,
            relationships=links, reviews=prepared["base_reviews"][vid].get("reviews", []),
            reviews_sha256=prepared["reviews_sha256"], application_proof=proof)
        reviewed = prepare_reviewed_frames(frames, prepared["p1_overlay"], source_identity=source,
            repo_root=root, video_id=vid, frame_count=previous.PILOT_FRAME_COUNT,
            overlay_sha256=prepared["p1_overlay_sha256"], branch="review_assisted",
            source_records_path=job["paths"]["records"])
        prepared["guarded_inputs"].extend(reviewed.get("guarded_inputs", []))
        resolved = identity.prepare_identity_frames(reviewed["frames"], geometry,
            prepared["policy"], relationships=links)
        _require([row["frame_index"] for row in resolved["frames"]]
            == list(range(previous.PILOT_FRAME_COUNT)), "Full source frame history required")
        policy = deepcopy(prepared["policy"])
        policy["episode_relations"] = resolved.get("unit_relations", [])
        result = counting.replay_frames(resolved["frames"], geometry, source_identity=source, policy=policy)
        result = finalize_reviewed_pending(result, prepared["adjudications"],
            baseline_result=prepared["baseline_result"], source_identity=source,
            finalization_frame=previous.PILOT_FRAME_COUNT - 1, repo_root=root)
        result.update(video_id=vid, source_identity=source, branch="review_assisted",
            frame_assignments=resolved["assignments"], component_links=resolved.get("component_links", []))
        _decision_provenance(result, prepared["p1_overlay"],
            finalization_frame=previous.PILOT_FRAME_COUNT - 1,
            overlay_sha256=prepared["p1_overlay_sha256"])
        result = _rename_event_ids(result)
        result["report"].update(version="b_v8_p1_review_assisted_v1",
            reviewed_branch_not_machine_model_improvement=True)
        _write(target / "counting_result.json.gz", result)
        _write(target / "geometry.json", _read(job["b_v2_geometry_path"]))
        _write(target / "source_identity.json", source)
        _write(target / "adapter_audit.json", proof)
        for name in ("application_audit", "provenance"):
            _write(target / ("p1_review_" + name + ".json.gz"), reviewed[name])
        for name, value in resolved.items():
            if name != "frames":
                _write(target / (name + ".json.gz"), value)
        for name in ("invalid_decisions", "eligibility_audit", "finalization_audit",
                     "ambiguity_invalid_audit", "business_taxonomy_audit", "v7_handoff_relations",
                     "v7_handoff_audit", "v7_publication_audit", "v8_pending_finalization_audit",
                     "v8_decision_provenance", "events", "decisions", "passage_log"):
            _write(target / (name + ".json.gz"), result.get(name, []))
        report["videos"].append({"video_id": vid, "status": "completed",
            "frames": previous.PILOT_FRAME_COUNT, "aggregate": result["aggregate"],
            "source_identity": source, "branch": "review_assisted"})
        report.update(status="completed_p1_reviewed_replay_pending_qc",
            frames_processed=previous.PILOT_FRAME_COUNT, all_selected_completed=True,
            all_eight_completed=False)
        if progress:
            progress({"video_id": vid, "aggregate": result["aggregate"], "branch": "review_assisted"})
    except Exception as error:
        report.update(status="failed_or_partial", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        _write(output / "guarded_inputs.json", prepared["guarded_inputs"])
        changed = [path for path, meta in snapshots.items() if _hash(path) != meta["sha256"]]
        changed += [row["path"] for row in prepared["guarded_inputs"] if _hash(row["path"]) != row["sha256"]]
        report.update(wall_seconds=time.perf_counter() - began, inputs_and_sources_unchanged=not changed)
        if changed:
            report.update(status="failed_or_partial", changed_files=changed)
        _write(output / "batch_report.json", report)
        previous.previous.old._retention(output)
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
    parser.add_argument("--overlay-path")
    parser.add_argument("--adjudications-path")
    parser.add_argument("--output-root", default="results/b_v8/execution")
    parser.add_argument("--run-id")
    print(run_b_v8_batch(**vars(parser.parse_args()))["status"])


if __name__ == "__main__":
    main()
