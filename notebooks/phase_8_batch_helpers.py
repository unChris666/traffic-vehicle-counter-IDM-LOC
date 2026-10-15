"""Sequential Phase 8 orchestration and accepted-event-only batch aggregation.

This prototype is intentionally independent of UI and GPU scheduling. Missing,
failed and unsupported coverage is represented by null, never a fabricated zero.
Snapshot selection is explicit: machine and reviewed results are alternatives.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import importlib
from importlib import metadata as package_metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "phase8_batch_v1"
CATEGORIES = ("pedestrian", "motorcycle", "car", "bus_angkot", "truck")
DAY_TYPES = ("weekday", "weekend")
PERIODS = ("pagi", "siang", "sore", "malam")
SUPPORTED_ACCEPTED_CATEGORIES = frozenset(("motorcycle", "car", "truck"))
COVERAGE = {
    "pedestrian": "UNSUPPORTED_IN_FROZEN_VEHICLE_RESOLVER",
    "motorcycle": "ACCEPTED_PASSAGES_ONLY_PENDING_AND_MISSES_EXCLUDED",
    "car": "ACCEPTED_PASSAGES_ONLY_PENDING_AND_MISSES_EXCLUDED",
    "bus_angkot": "BUS_ANGKOT_TAXONOMY_UNRESOLVED",
    "truck": "ACCEPTED_PASSAGES_ONLY_PENDING_AND_MISSES_EXCLUDED",
}


class BatchContractError(ValueError):
    """A batch/snapshot would change the meaning of its retained evidence."""


def _require(condition, message):
    if not condition:
        raise BatchContractError(message)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _resolve(path, repo_root):
    path = Path(path)
    return path if path.is_absolute() else Path(repo_root) / path


def _module(name, repo_root):
    source = str(Path(repo_root).resolve() / "notebooks")
    if source not in sys.path:
        sys.path.insert(0, source)
    return importlib.import_module(name)


def resolve_manifest_source_paths(manifest_path, output_root, *, dataset_root=None, input_root="/kaggle/input"):
    """Resolve a mount relocation by exact eight-source SHA identity only.

    Filenames are a secondary trace-consistency check; they never assign slots.
    Searches stay inside the explicit input root. The original configuration is
    immutable; the effective copy changes only videos[*].source_path.
    """
    manifest_path = Path(manifest_path).resolve()
    original_bytes = manifest_path.read_bytes()
    original = json.loads(original_bytes)
    videos = original.get("videos")
    _require(isinstance(videos, list) and len(videos) == 8, "Mount resolution requires exactly eight explicit video inputs")
    expected, expected_names = {}, {}
    for video in videos:
        digest, path = video.get("source_sha256"), video.get("source_path")
        _require(isinstance(digest, str) and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "Every source requires a measured SHA256 before mount resolution")
        _require(digest not in expected, "Manifest contains duplicate source SHA identities")
        _require(isinstance(path, str) and path and Path(path).name, "Every source requires its original path/filename trace")
        expected[digest] = video
        expected_names[digest] = Path(path).name
        declared = (video.get("metadata_confirmation") or {}).get("source_filename")
        _require(declared is None or declared == Path(path).name, "Original source filename trace is inconsistent")
    allowed = Path(input_root).resolve()
    _require(allowed.is_dir(), "Explicit input root is unavailable: " + str(allowed))
    candidates = []
    for path in ([Path(dataset_root)] if dataset_root is not None else []) + [
        allowed / "datasets/chrisbiran/tgdi-traffic-videos", allowed / "tgdi-traffic-videos",
    ] + [Path(video["source_path"]).parent for video in videos]:
        resolved = path.resolve()
        if resolved.is_relative_to(allowed) and resolved.is_dir() and resolved not in candidates:
            candidates.append(resolved)
    extensions = {Path(video["source_path"]).suffix.lower() for video in videos}

    def scan(roots):
        found = set()
        for root in roots:
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in extensions:
                    resolved = path.resolve()
                    _require(resolved.is_relative_to(allowed), "Source symlink escapes the explicit input root")
                    found.add(resolved)
        return sorted(found)

    files = scan(candidates)
    strategy = "CONFIGURED_AND_KNOWN_DATASET_ROOTS"
    if not files:
        files = scan([allowed])
        strategy = "BOUNDED_EXPLICIT_INPUT_ROOT_SEARCH"
    matches = {}
    for path in files:
        digest = sha256_file(path)
        _require(digest in expected, "Unexpected video bytes within source discovery scope: " + str(path))
        _require(digest not in matches, "Ambiguous duplicate source SHA at multiple actual paths")
        _require(path.name == expected_names[digest], "Source filename trace differs despite matching SHA; refusing reversed/renamed assignments")
        matches[digest] = path
    _require(set(matches) == set(expected), "Actual mounted inputs are missing one or more of the eight expected SHA identities")
    effective = json.loads(json.dumps(original))
    mapping = []
    for video in effective["videos"]:
        actual = str(matches[video["source_sha256"]])
        mapping.append({"video_id": video["video_id"], "source_sha256": video["source_sha256"],
            "original_source_path": video["source_path"], "effective_source_path": actual,
            "filename_trace_verified": True})
        video["source_path"] = actual
    proof = json.loads(json.dumps(effective))
    for before, after in zip(original["videos"], proof["videos"]):
        after["source_path"] = before["source_path"]
    _require(proof == original and manifest_path.read_bytes() == original_bytes, "Source resolution changed non-path configuration or the original manifest")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    target = Path(output_root) / timestamp
    target.mkdir(parents=True, exist_ok=False)
    effective_path = target / "runtime_effective_manifest.json"
    effective_bytes = original_bytes if effective == original else (json.dumps(effective, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    effective_path.write_bytes(effective_bytes)
    record = {"schema_version": "phase8_source_mount_resolution_v1", "claim_type": "ACTUAL_SOURCE_SHA_MOUNT_RESOLUTION_NOT_MODEL_EXECUTION",
        "original_manifest_path": str(manifest_path), "original_manifest_sha256": sha256_file(manifest_path),
        "effective_manifest_path": str(effective_path.resolve()), "effective_manifest_sha256": sha256_file(effective_path),
        "input_root": str(allowed), "configured_dataset_root": str(dataset_root) if dataset_root is not None else None,
        "examined_dataset_roots": [str(path) for path in candidates], "discovery_strategy": strategy,
        "resolved_source_count": len(mapping), "relocated_source_count": sum(row["original_source_path"] != row["effective_source_path"] for row in mapping),
        "source_mapping": mapping, "manifest_change_scope": "videos[*].source_path_ONLY",
        "scientific_fields_changed": False, "actual_model_inference_executed": False,
        "effective_dataset_root": os.path.commonpath([str(path.parent) for path in matches.values()]),
        "record_path": str((target / "source_mount_resolution.json").resolve())}
    _write_json(record["record_path"], record)
    return record


def _verify_source_resolution(record, manifest_path, manifest):
    _require(isinstance(record, dict) and record.get("schema_version") == "phase8_source_mount_resolution_v1", "Invalid source relocation record")
    _require(record.get("effective_manifest_sha256") == sha256_file(manifest_path), "Effective manifest differs from its relocation record")
    _require(Path(record["effective_manifest_path"]).resolve() == Path(manifest_path).resolve(), "Effective manifest path differs from its relocation record")
    original_path = Path(record["original_manifest_path"])
    _require(sha256_file(original_path) == record.get("original_manifest_sha256"), "Original source manifest changed after relocation")
    original = _read_json(original_path)
    proof = json.loads(json.dumps(manifest))
    mapping = record.get("source_mapping")
    _require(isinstance(mapping, list) and len(mapping) == 8 and len(original.get("videos", [])) == len(proof.get("videos", [])) == 8,
             "Relocation record requires all eight source mappings")
    for before, after, row in zip(original["videos"], proof["videos"], mapping):
        _require(row.get("video_id") == after["video_id"] == before["video_id"]
                 and row.get("source_sha256") == after["source_sha256"] == before["source_sha256"]
                 and row.get("original_source_path") == before["source_path"]
                 and row.get("effective_source_path") == after["source_path"], "Relocation record source mapping mismatch")
        after["source_path"] = before["source_path"]
    _require(proof == original, "Runtime manifest changed scientific/business fields rather than only source paths")


def discover_runtime():
    """Report observed devices; visibility alone never means both were used."""
    observed = {"python": platform.python_version(), "cpu_count": os.cpu_count(),
                "gpu_probe": "nvidia-smi", "available_gpus": [],
                "processing_assignment": "sequential_cuda0_only",
                "parallel_gpu_orchestration_implemented": False}
    command = shutil.which("nvidia-smi")
    if command:
        completed = subprocess.run([command, "--query-gpu=index,name,memory.total", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=30, check=False)
        observed["gpu_probe_exit_code"] = completed.returncode
        if completed.returncode == 0:
            for row in csv.reader(completed.stdout.splitlines()):
                if len(row) == 3:
                    observed["available_gpus"].append({"index": int(row[0].strip()), "name": row[1].strip(),
                                                       "memory_mib": int(row[2].strip())})
        else:
            observed["gpu_probe_status"] = "FAILED_GPU_INFORMATION_UNKNOWN"
    else:
        observed["gpu_probe_status"] = "NVIDIA_SMI_UNAVAILABLE_GPU_INFORMATION_UNKNOWN"
    observed["available_gpu_count"] = len(observed["available_gpus"]) if observed.get("gpu_probe_exit_code") == 0 else None
    observed["gpu_visibility_semantics"] = "NVIDIA_SMI_OBSERVATION_NOT_PYTORCH_CUDA_VISIBILITY_OR_DEVICE_EXECUTION_PROOF"
    observed["installed_packages"] = {}
    for name in ("numpy", "opencv-python", "opencv-python-headless", "Pillow", "torch", "ultralytics", "onnx", "onnxruntime-gpu", "lap"):
        try:
            observed["installed_packages"][name] = package_metadata.version(name)
        except package_metadata.PackageNotFoundError:
            observed["installed_packages"][name] = None
    return observed


def prepare_batch(manifest_path, *, repo_root=".", dataset_root=None):
    """Discover real files and expose unresolved fields, without authorizing a run."""
    manifest_module = _module("phase_8_manifest_helpers", repo_root)
    manifest_path = _resolve(manifest_path, repo_root)
    manifest = _read_json(manifest_path)
    root = dataset_root or manifest.get("dataset_root")
    discovery, discovery_status = [], "DATASET_ROOT_UNDEFINED"
    if root:
        try:
            discovery = manifest_module.discover_videos(root)
            discovery_status = "ACTUAL_FILES_DISCOVERED_METADATA_UNCONFIRMED"
        except FileNotFoundError:
            discovery_status = "DATASET_UNAVAILABLE_IN_CURRENT_ENVIRONMENT"
    readiness = manifest_module.validate_manifest(manifest, repo_root=repo_root, check_files=False)
    return {"mode": "prepare", "execution_kind": "NO_MODEL_EXECUTION", "manifest_path": str(manifest_path),
            "dataset_root": str(root) if root is not None else None,
            "manifest_sha256": sha256_file(manifest_path), "discovered_videos": discovery,
            "dataset_discovery_status": discovery_status,
            "readiness": readiness, "runtime": discover_runtime(),
            "message": "Fill the eight actual input assignments, business metadata and traceable per-video geometry approval; prepare never authorizes inference."}


def write_preparation_outputs(preparation, guards, manifest_path, profile_path, output_root, *, repo_root=".", notebook_path=None):
    """Retain actual preparation evidence without manufacturing traffic results."""
    _require(preparation.get("mode") == "prepare" and preparation.get("execution_kind") == "NO_MODEL_EXECUTION",
             "Preparation retention cannot relabel inference outputs")
    required_guards = {"phase_8_manifest_tests", "phase_8_pipeline_tests", "phase_8_batch_tests", "phase_8_review_tests"}
    _require(isinstance(guards, dict) and set(guards) == required_guards, "All four Phase8 software guard suites are required")
    _require(all(value.get("successful") is True and type(value.get("tests_run")) is int and value["tests_run"] > 0 for value in guards.values()),
             "Failed or empty software guards cannot authorize retained preparation status")
    manifest_path, profile_path = _resolve(manifest_path, repo_root), _resolve(profile_path, repo_root)
    _require(sha256_file(manifest_path) == preparation["manifest_sha256"], "Manifest changed during preparation")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    target = Path(output_root) / "preparation" / timestamp
    target.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(manifest_path, target / "input_manifest.json")
    shutil.copyfile(profile_path, target / "processing_profile.json")
    _write_json(target / "discovered_videos.json", preparation["discovered_videos"])
    _write_json(target / "readiness.json", preparation["readiness"])
    _write_json(target / "effective_video_configuration.json", preparation["readiness"]["effective_videos"])
    _write_json(target / "runtime.json", preparation["runtime"])
    _write_json(target / "software_guards.json", guards)
    methods = ["notebooks/phase_8_manifest_helpers.py", "notebooks/phase_8_pipeline_helpers.py",
               "notebooks/phase_8_batch_helpers.py", "notebooks/phase_8_review_helpers.py"]
    methods += [name.replace("_helpers.py", "_tests.py") for name in methods]
    if notebook_path is not None:
        methods.append(str(notebook_path))
    sources = []
    for name in methods:
        path = _resolve(name, repo_root)
        _require(path.is_file(), "Preparation method source unavailable: " + str(path))
        sources.append({"path": str(path), "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
    _write_json(target / "source_provenance.json", {"claim_type": "CANONICAL_REPOSITORY_SOURCE_IDENTITY_NOT_EXECUTED_KERNEL_WRAPPER_HASH",
        "source_methods": sources, "input_manifest_sha256": sha256_file(manifest_path),
        "processing_profile_sha256": sha256_file(profile_path)})
    observed = preparation["dataset_discovery_status"] == "ACTUAL_FILES_DISCOVERED_METADATA_UNCONFIRMED"
    report = {"phase": 8, "mode": "prepare", "run_id": timestamp,
        "execution_kind": "ACTUAL_INPUT_DISCOVERY_AND_SOFTWARE_GUARDS_NO_MODEL_EXECUTION",
        "status": "prepared_configuration_requires_full_execution_gate",
        "dataset_root": preparation.get("dataset_root"), "dataset_discovery_status": preparation["dataset_discovery_status"],
        "discovered_video_count": len(preparation["discovered_videos"]) if observed else None,
        "source_media_available_for_discovery": observed, "readiness": preparation["readiness"],
        "input_manifest_sha256": sha256_file(manifest_path), "processing_profile_sha256": sha256_file(profile_path),
        "software_guard_summary": {name: {"tests_run": value["tests_run"], "tests_passed": value.get("tests_passed"),
            "tests_skipped": value.get("tests_skipped", 0), "successful": value["successful"]} for name, value in guards.items()},
        "counting_execution_authorized_by_prepare": False, "new_model_inference_executed": False,
        "traffic_result_created": False, "complete_eight_video_processing": False,
        "output_directory": str(target)}
    _write_json(target / "report.json", report)
    artifacts = [{"path": str(path.relative_to(target)), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
                 for path in sorted(target.iterdir()) if path.is_file()]
    _write_json(target / "retention_manifest.json", {"phase": 8, "mode": "prepare", "artifacts": artifacts})
    return report


def _video_identity(video):
    # Manifest schema owns validation; aggregation still checks the selected
    # snapshot against the manifest instead of trusting the filename or IDs.
    return {"video_sha256": video.get("source_sha256"), "geometry_sha256": video.get("geometry_sha256")}


def _verified_artifact(snapshot, name, repo_root):
    path_key, digest_key = name + "_path", name + "_sha256"
    _require(isinstance(snapshot.get(path_key), str) and snapshot[path_key], "Missing snapshot " + path_key)
    path = _resolve(snapshot[path_key], repo_root)
    _require(path.is_file(), "Snapshot artifact unavailable: " + str(path))
    _require(sha256_file(path) == snapshot.get(digest_key), "Snapshot artifact SHA mismatch: " + str(path))
    return _read_json(path)


def _selected_snapshot(video, result):
    requested = video.get("snapshot_selection", {"kind": "machine"})
    kind = requested if isinstance(requested, str) else requested.get("kind")
    _require(kind in ("machine", "reviewed"), "Choose exactly one machine/reviewed snapshot per video")
    snapshots = result.get("snapshots")
    snapshot = snapshots.get(kind) if isinstance(snapshots, dict) else result.get("snapshot")
    _require(isinstance(snapshot, dict), "Selected snapshot not available: " + str(kind))
    _require(snapshot.get("kind") == kind, "Selected snapshot kind mismatch")
    if isinstance(requested, dict) and requested.get("run_id"):
        _require(snapshot.get("run_id") == requested["run_id"], "Requested snapshot run mismatch")
    _require(snapshot.get("run_id") == result.get("run_id"), "Mixed rerun snapshot and result")
    return snapshot


def _logical_id(prefix, value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return prefix + hashlib.sha256(canonical.encode()).hexdigest()


def _machine_policy(configuration):
    fields = ("policy_version", "metric", "neutral_band_px", "confirmation_observations", "association")
    _require(all(key in configuration for key in fields), "Frozen counting policy fields missing")
    semantic = {key: configuration[key] for key in fields}
    semantic["grouping_enabled"] = configuration.get("grouping_enabled")
    semantic["association_frame_windows"] = (configuration.get("scope") or {}).get("association_frame_windows")
    return semantic, _logical_id("cfg6b_", semantic)


def _reconcile_event(event, decisions, configuration, source, snapshot_kind):
    by_candidate = {decision.get("candidate_id"): decision for decision in decisions}
    _require(len(by_candidate) == len(decisions), "Duplicate candidate decisions in selected snapshot")
    candidate = by_candidate.get(event.get("candidate_id"))
    _require(candidate is not None, "Accepted event has no retained candidate decision")
    _require(candidate.get("status") == "accepted" and candidate.get("accepted_count_event") is True
             and candidate.get("event_id") == event.get("event_id"), "CountEvent is not an accepted representative decision")
    for key in ("category", "track_id", "physical_unit_id", "passage_id"):
        _require(candidate.get(key) == event.get(key), "Event/decision mismatch: " + key)
    _require(candidate.get("episode_id") == event.get("vehicle_measurement_episode_id"), "Event has a foreign vehicle measurement episode")
    diagnostic = candidate.get("diagnostic")
    _require(isinstance(diagnostic, dict) and diagnostic.get("type") == "GEOMETRY_TRANSITION"
             and diagnostic.get("accepted_count_event") is False, "Invalid retained crossing diagnostic")
    _require(diagnostic == event.get("geometry_evidence") and candidate.get("measurement_support") == event.get("measurement_support"),
             "Event changed the measured geometry/source BC support")
    _require(diagnostic.get("direction") == event.get("direction"), "Event/decision direction mismatch")
    _require(not candidate.get("reasons") and not candidate.get("hard_block_reasons"), "Accepted candidate retains unresolved conflicts")
    semantic, machine_policy = _machine_policy(configuration)
    manual = event.get("manual_review_applied") is True
    if manual:
        _require(snapshot_kind == "reviewed", "Reviewed event silently placed in machine snapshot")
        fields = ("policy_version", "metric", "neutral_band_px", "confirmation_observations", "grouping_enabled", "scope", "association",
                  "episode_policy", "category_policy", "identity_policy", "identity_support_policy")
        overlay = {key: configuration[key] for key in fields if key in configuration}
        expected_policy = _logical_id("cfg6br_", {"source_identity": source, "source_policy": overlay,
                                                   "review_overlay_policy": "phase6_option_b_review_overlay_v1"})
        expected_event = _logical_id("ce6br_", {"source_identity": source, "policy_identity": expected_policy,
                                               "physical_unit_id": event["physical_unit_id"], "passage_id": event["passage_id"]})
    else:
        expected_policy = machine_policy
        expected_event = _logical_id("ce6b_", {"source_identity": source, "policy": semantic,
                                              "physical_unit_id": event["physical_unit_id"], "passage_id": event["passage_id"]})
    _require(event.get("policy_identity") == expected_policy, "Event policy identity differs from frozen counting/review configuration")
    _require(event.get("event_id") == expected_event, "Event ID differs from its source-bound physical passage")


def _validate_synthetic_snapshot(snapshot, configuration, events, decisions, repo_root):
    """Exercise frozen predicates on explicitly synthetic source graphs only."""
    bridge = _module("phase_8_review_helpers", repo_root)
    pipeline = _module("phase_8_pipeline_helpers", repo_root)
    directory = _resolve(snapshot["configuration_path"], repo_root).parent
    bridge.verify_machine_manifest(directory)
    report = _read_json(directory / "counting_report.json")
    _require(report.get("execution_kind") == "SYNTHETIC_FIXTURE", "Synthetic batch requires explicitly synthetic source outputs")
    source = configuration["input_identity"]
    _require(report.get("source_identity") == source, "Synthetic source identity mismatch")
    pipeline.validate_processing_profile(report["configuration"], repo_root)
    _require({key: configuration.get(key) for key in report["configuration"]["counting"]} == report["configuration"]["counting"],
             "Synthetic counting differs from frozen controls")
    proof = report["cache_provenance"]
    pipeline._validate_full_cache(report["records_path"], source, proof["measurement_provenance"], proof["frame_count"])
    _, geometry = pipeline.validate_geometry(report["geometry_path"], source, repo_root=repo_root, allow_synthetic=True)
    episodes = _read_json(directory / "episodes.json.gz")
    episode_index = {episode["episode_id"]: episode for episode in episodes}
    module, _, _ = bridge.load_review_adapter(repo_root)
    original_events = _read_json(directory / "machine_count_events.json.gz")
    original_decisions = _read_json(directory / "machine_passage_decisions.json.gz")
    if snapshot["kind"] == "machine":
        _require(events == original_events and decisions == original_decisions, "Selected snapshot is not the retained machine result")
    else:
        review_root = _resolve(snapshot["events_path"], repo_root).parent
        reviews = _read_json(review_root / "review_input.json")
        rebuilt = module.build_reviewed_snapshot(original_decisions, episodes, original_events, configuration, reviews,
                                                 repo=Path(report["geometry_path"]).parent, geometry=geometry)
        _require(rebuilt["accepted_events"] == events and rebuilt["resolved_decisions"] == decisions,
                 "Reviewed synthetic snapshot differs from guarded overlay")
    for event in events:
        candidate = next(item for item in decisions if item["candidate_id"] == event["candidate_id"])
        module.validate_candidate(candidate, episode_index, configuration, geometry, repo_root)


def _verify_selected_source(snapshot, configuration, events, decisions, repo_root, evidence_kind):
    if evidence_kind == "SYNTHETIC_TEST_FIXTURE":
        _validate_synthetic_snapshot(snapshot, configuration, events, decisions, repo_root)
    else:
        _require(evidence_kind == "ACTUAL_DATASET", "Batch evidence_kind must be explicit")
        bridge = _module("phase_8_review_helpers", repo_root)
        bridge.validate_selected_snapshot(snapshot, repo_root=repo_root)


def _collect_video(video, result, repo_root, evidence_kind="ACTUAL_DATASET"):
    _require(result.get("scope") == "full_video", "Targeted windows cannot stand in for a full Phase 8 video")
    source = result.get("source_identity")
    _require(isinstance(source, dict), "Missing per-video source identity")
    expected = _video_identity(video)
    for key, digest in expected.items():
        _require(isinstance(digest, str) and len(digest) == 64 and source.get(key) == digest,
                 "Snapshot " + key + " does not match the selected input")
    _require(source.get("variant") == "raw", "Phase 8 frozen baseline requires raw; raw/gamma results cannot be mixed")
    _require(isinstance(source.get("records_sha256"), str) and len(source["records_sha256"]) == 64,
             "Missing source measurement cache identity")
    _require(type(result.get("frames_processed")) is int and result["frames_processed"] > 0,
             "Completed video requires actual processed frames")
    metadata = video.get("observed_metadata") or {}
    if metadata.get("frame_count") is not None:
        _require(result["frames_processed"] == metadata["frame_count"], "Incomplete observed-frame processing")
    for key in ("width", "height"):
        if metadata.get(key) is not None:
            _require(source.get(key) == metadata[key], "Source native dimensions differ from selected input")
    verified = video.get("verified_source") or {}
    if verified.get("decoded_frame_count") is not None:
        _require(result["frames_processed"] == verified["decoded_frame_count"], "Incomplete decoded-frame processing")
    snapshot = _selected_snapshot(video, result)
    events = _verified_artifact(snapshot, "events", repo_root)
    decisions = _verified_artifact(snapshot, "decisions", repo_root)
    configuration = _verified_artifact(snapshot, "configuration", repo_root)
    _require(configuration.get("input_identity") == source, "Counting configuration and source snapshot differ")
    _require(isinstance(events, list) and isinstance(decisions, list), "Events and decisions must be retained JSON lists")
    counts = {category: 0 for category in SUPPORTED_ACCEPTED_CATEGORIES}
    ledger, queue, event_ids, passages = [], [], set(), set()
    for event in events:
        _require(isinstance(event, dict) and event.get("type") == "CountEvent" and event.get("status") == "accepted"
                 and event.get("accepted_count_event") is True, "Only typed accepted CountEvent enters accepted totals")
        _require(event.get("source_identity") == source, "CountEvent belongs to a different source/configuration")
        category = event.get("category")
        _require(category in SUPPORTED_ACCEPTED_CATEGORIES, "Unresolved/unsupported category cannot be accepted by this frozen vehicle profile")
        _require(event.get("direction") in ("A_TO_B", "B_TO_A"), "CountEvent direction is unresolved")
        event_id = event.get("event_id")
        _require(isinstance(event_id, str) and event_id and event_id not in event_ids, "Duplicate or missing accepted event ID")
        event_ids.add(event_id)
        unit, passage = event.get("physical_unit_id"), event.get("passage_id")
        _require(isinstance(unit, str) and unit and isinstance(passage, str) and passage, "CountEvent lacks physical unit/passage identity")
        _require(isinstance(event.get("vehicle_measurement_episode_id"), str) and event["vehicle_measurement_episode_id"],
                 "CountEvent lacks source vehicle measurement episode")
        physical_key = (unit, passage)
        _require(physical_key not in passages, "Duplicate physical passage with different event IDs")
        passages.add(physical_key)
        _reconcile_event(event, decisions, configuration, source, snapshot["kind"])
        counts[category] += 1
        namespace = "/".join((video["video_id"], source["video_sha256"], snapshot["run_id"], snapshot["kind"], event_id))
        ledger.append({"batch_event_id": "be8_" + hashlib.sha256(namespace.encode()).hexdigest(),
                       "video_id": video["video_id"], "day_type": video["day_type"], "recording_period": video["recording_period"],
                       "source_event_id": event_id, "snapshot_kind": snapshot["kind"], "run_id": snapshot["run_id"],
                       "snapshot_events_sha256": snapshot["events_sha256"], "counting_configuration_sha256": snapshot["configuration_sha256"],
                       "source_identity": source, "category": category, "direction": event["direction"],
                       "physical_unit_id": unit, "passage_id": passage, "event": event})
    accepted_decisions = {decision.get("event_id") for decision in decisions if decision.get("accepted_count_event") is True}
    _require(accepted_decisions == event_ids, "Accepted decisions and typed events do not reconcile")
    _verify_selected_source(snapshot, configuration, events, decisions, repo_root, evidence_kind)
    for decision in decisions:
        _require(isinstance(decision, dict), "Decision artifact contains a non-record")
        if str(decision.get("status", "")).startswith("pending"):
            candidate_id = decision.get("candidate_id")
            _require(isinstance(candidate_id, str) and candidate_id, "Pending decision lacks candidate identity")
            namespace = "/".join((video["video_id"], source["video_sha256"], snapshot["run_id"], snapshot["kind"], candidate_id))
            queue.append({"audit_item_id": "aq8_" + hashlib.sha256(namespace.encode()).hexdigest(),
                          "video_id": video["video_id"], "candidate_id": candidate_id, "run_id": snapshot["run_id"],
                          "snapshot_kind": snapshot["kind"], "source_identity": source,
                          "status": decision["status"], "decision": decision})
    return {"video_id": video["video_id"], "status": "completed", "source_identity": source,
            "snapshot_kind": snapshot["kind"], "run_id": snapshot["run_id"], "frames_processed": result["frames_processed"],
            "accepted_event_count": len(ledger), "accepted_by_category": counts, "pending_count": len(queue),
            "snapshot": snapshot}, ledger, queue


def _is_completed(result):
    status = str(result.get("status", ""))
    return status == "completed" or status.startswith("completed_full_video_")


def _business_context(manifest, repo_root, validation=None):
    """Unknown business facts remain null, even in explicitly allowed research."""
    location = manifest.get("location")
    _require(isinstance(location, dict), "Batch location metadata must be explicit")
    unknown = [field for field in ("store_code", "store_name", "latitude", "longitude") if location.get(field) is None]
    authorized = False
    if validation is not None:
        _require(validation.get("business_metadata_complete") == (not unknown)
                 and validation.get("unknown_location_fields") == unknown,
                 "Validated business metadata differs from retained manifest")
        authorized = validation.get("research_unknown_location_authorized") is True
    elif manifest.get("execution_purpose") is not None:
        # Synthetic contract fixtures can verify the same acknowledgement
        # without claiming real dataset execution or weakening actual gates.
        validator = _module("phase_8_manifest_helpers", repo_root)
        if manifest["execution_purpose"] == validator.RESEARCH_UNKNOWN_LOCATION_PURPOSE:
            try:
                authorized = validator._verify_unknown_location_review(manifest, Path(repo_root).resolve(), unknown,
                    manifest.get("evidence_kind") == "SYNTHETIC_TEST_FIXTURE")
            except (ValueError, KeyError, TypeError, OSError) as error:
                raise BatchContractError("Research business metadata acknowledgement invalid: " + str(error)) from error
    return {"location": dict(location), "business_metadata_complete": not unknown, "unknown_location_fields": unknown,
            "location_metadata_status": "COMPLETE" if not unknown else "UNKNOWN_DECLARED_RESEARCH_ONLY" if authorized else "INCOMPLETE_UNACKNOWLEDGED",
            "research_only": authorized, "research_unknown_location_authorized": authorized,
            "location_metadata_review": manifest.get("location_metadata_review") if authorized else None,
            "business_result_complete": False}


def aggregate_batch(manifest, results, *, repo_root="."):
    """Reconcile eight selected source-bound snapshots, never sum reruns."""
    _require(manifest.get("schema_version") == SCHEMA_VERSION, "Unsupported batch manifest schema")
    checked = None
    if manifest.get("evidence_kind") == "ACTUAL_DATASET":
        checked = _module("phase_8_manifest_helpers", repo_root).validate_manifest(manifest, repo_root=repo_root, check_files=False)
        unresolved = [issue for issue in checked["issues"] if issue["code"] != "source_files_not_verified"]
        _require(not unresolved, "Actual result aggregation requires confirmed business metadata and geometry: " + json.dumps(unresolved))
    business_context = _business_context(manifest, repo_root, checked)
    videos = manifest.get("videos")
    _require(isinstance(videos, list) and len(videos) == 8, "Exactly eight configured slots are required")
    _require(isinstance(results, list), "Results must be a list, including explicit failures")
    slot_keys, video_ids, sources = set(), set(), set()
    for video in videos:
        _require(video.get("day_type") in DAY_TYPES and video.get("recording_period") in PERIODS, "Undefined recording slot")
        key = video["day_type"], video["recording_period"]
        _require(key not in slot_keys and video.get("video_id") not in video_ids, "Duplicate slot/video identity")
        slot_keys.add(key)
        _require(isinstance(video.get("video_id"), str) and video["video_id"], "Missing video_id")
        video_ids.add(video["video_id"])
        digest = video.get("source_sha256")
        if digest is not None:
            _require(digest not in sources, "Same source video reused in different business slots")
            sources.add(digest)
    result_index = {}
    for result in results:
        _require(result.get("video_id") in video_ids, "Result references a video outside this manifest")
        _require(result["video_id"] not in result_index, "Duplicate rerun results: select one result per video")
        result_index[result["video_id"]] = result
    per_video, ledger, queue = [], [], []
    cells = {day: {cat: {period: None for period in PERIODS} for cat in CATEGORIES} for day in DAY_TYPES}
    for video in videos:
        result = result_index.get(video["video_id"])
        if result is None or not _is_completed(result):
            status = "not_executed" if result is None else result.get("status", "failed")
            per_video.append({"video_id": video["video_id"], "status": status, "accepted_event_count": None,
                              "pending_count": None, "error": None if result is None else result.get("error"), **business_context})
            continue
        summary, selected_events, selected_queue = _collect_video(video, result, repo_root, manifest.get("evidence_kind"))
        summary.update(business_context)
        per_video.append(summary)
        ledger.extend(selected_events)
        queue.extend(selected_queue)
        for category, total in summary["accepted_by_category"].items():
            cells[video["day_type"]][category][video["recording_period"]] = total
    tables = {}
    for day in DAY_TYPES:
        tables[day] = []
        for category in CATEGORIES:
            row = {"category": category, **cells[day][category]}
            row["total"] = sum(row[period] for period in PERIODS) if all(row[period] is not None for period in PERIODS) else None
            tables[day].append(row)
    _require(len({row["batch_event_id"] for row in ledger}) == len(ledger), "Namespaced event ledger contains duplicates")
    _require(sum(summary["accepted_event_count"] or 0 for summary in per_video) == len(ledger), "Per-video/ledger reconciliation failure")
    observed_cells = sum(value for day in cells.values() for category in day.values() for value in category.values() if value is not None)
    _require(observed_cells == len(ledger), "Tables/ledger reconciliation failure")
    complete = all(row["status"] == "completed" for row in per_video)
    return {"schema_version": SCHEMA_VERSION, "claim_type": "ACCEPTED_PASSAGES_IN_OBSERVED_RECORDINGS_NOT_DAILY_TRAFFIC_OR_ACCURACY",
            "evidence_kind": manifest.get("evidence_kind"), **business_context,
            "status": ("completed_research_snapshots_pending_audit" if business_context["research_only"] else "completed_selected_snapshots_pending_audit") if complete else ("incomplete_research_batch" if business_context["research_only"] else "incomplete_batch"),
            "all_eight_videos_processed": complete, "business_category_coverage_complete": False,
            "accepted_observed_event_count": len(ledger), "complete_batch_accepted_total": len(ledger) if complete else None,
            "pending_observed_count": len(queue), "coverage_by_category": COVERAGE,
            "zero_semantics": "ZERO_ACCEPTED_EVENTS_IN_SUPPORTED_COMPLETED_SLOT_NOT_PROOF_OF_NO_PHYSICAL_PASSAGES",
            "null_semantics": "UNEXECUTED_FAILED_OR_UNSUPPORTED_CATEGORY_NO_FABRICATED_ZERO",
            "total_semantics": "SUM_OF_FOUR_OBSERVED_RECORDINGS_NOT_EXTRAPOLATED_DAILY_COUNT",
            "per_video": per_video, "tables": tables, "accepted_event_ledger": ledger, "audit_queue": queue}


def write_batch_outputs(output_dir, report):
    """Persist exact CSV layout plus evidence/coverage sidecars."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "batch_report.json", report)
    _write_json(output_dir / "accepted_event_ledger.json", report["accepted_event_ledger"])
    _write_json(output_dir / "audit_queue.json", report["audit_queue"])
    _write_json(output_dir / "coverage.json", {key: report[key] for key in ("coverage_by_category", "zero_semantics", "null_semantics", "total_semantics",
        "location", "business_metadata_complete", "unknown_location_fields", "location_metadata_status", "research_only", "location_metadata_review", "business_result_complete")})
    for day, rows in report["tables"].items():
        with (output_dir / (day + ".csv")).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=("category", *PERIODS, "total"))
            writer.writeheader()
            writer.writerows(rows)
    artifacts = [{"path": str(path.relative_to(output_dir)), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
                 for path in sorted(output_dir.rglob("*")) if path.is_file() and path != output_dir / "batch_retention_manifest.json"]
    _write_json(output_dir / "batch_retention_manifest.json", {"schema_version": SCHEMA_VERSION, "artifacts": artifacts})
    return output_dir


def configured_execution_mode(video):
    """An invalid explicit cache is an error, never an inference fallback."""
    mode = video.get("execution_mode", "new_inference")
    _require(mode in ("new_inference", "verified_cache_replay"), "Unknown video execution_mode")
    if mode == "new_inference":
        _require(video.get("retained_cache") is None, "A retained cache requires explicit verified_cache_replay mode")
    else:
        _require(isinstance(video.get("retained_cache"), dict), "Explicit retained_cache descriptor required")
    return mode


def _run_configured_video(video, profile, output_dir, *, repo_root):
    pipeline = _module("phase_8_pipeline_helpers", repo_root)
    mode = configured_execution_mode(video)
    if mode == "new_inference":
        return pipeline.run_full_video(video, profile, output_dir, repo_root=repo_root)
    donor = video["retained_cache"]
    identity = donor.get("cache_identity")
    _require(isinstance(identity, dict), "Cache descriptor requires cache_identity")
    for key, digest in _video_identity(video).items():
        _require(identity.get(key) == digest, "Cache source/geometry differs from selected video")
    for key in ("width", "height"):
        _require(identity.get(key) == video["observed_metadata"][key], "Cache dimensions differ from selected video")
    records = _resolve(donor["records_path"], repo_root)
    result = pipeline.replay_full_video_cache(records, video["geometry_path"], profile, output_dir, repo_root=repo_root,
                                             cache_identity=identity, cache_provenance=donor["cache_provenance"])
    result["video_id"] = video["video_id"]
    result["run_id"] = result["snapshot"]["run_id"]
    annotated = pipeline.render_annotated_video(_resolve(video["source_path"], repo_root), records,
        _resolve(video["geometry_path"], repo_root), result["source_identity"], result["snapshot"]["decisions_path"],
        Path(output_dir) / "annotated.mp4", fps=video["observed_metadata"]["fps"],
        expected_frame_count=result["frames_processed"])
    result["annotated_video"] = annotated
    result["execution_kind"] = "CACHE_REPLAY_NO_NEW_INFERENCE"
    _write_json(Path(output_dir) / "annotation_report.json", annotated)
    result["report"]["annotated_video"] = annotated
    _write_json(Path(output_dir) / "report.json", result["report"])
    pipeline._manifest(Path(output_dir))
    return result


def run_batch(manifest_path, profile_path, output_root, *, repo_root=".", runner=None, source_resolution=None):
    """Run one complete source at a time on explicit CUDA0 after strict preflight."""
    repo_root = Path(repo_root).resolve()
    manifest_path, profile_path = _resolve(manifest_path, repo_root), _resolve(profile_path, repo_root)
    manifest, profile = _read_json(manifest_path), _read_json(profile_path)
    if source_resolution is not None:
        if isinstance(source_resolution, (str, Path)):
            source_resolution = _read_json(source_resolution)
        _verify_source_resolution(source_resolution, manifest_path, manifest)
    _require(manifest.get("evidence_kind") == "ACTUAL_DATASET", "Synthetic fixtures cannot authorize actual model execution")
    validator = _module("phase_8_manifest_helpers", repo_root)
    readiness = validator.validate_manifest(manifest, repo_root=repo_root, check_files=True)
    _require(readiness.get("ready") is True, "Actual batch input readiness failed: " + json.dumps(readiness.get("issues")))
    _require(readiness.get("evidence_kind") == "ACTUAL_DATASET", "Synthetic source validation cannot authorize actual batch execution")
    business_context = _business_context(manifest, repo_root, readiness)
    if manifest.get("processing_profile_sha256") is not None:
        _require(manifest["processing_profile_sha256"] == sha256_file(profile_path), "Frozen profile hash differs from manifest")
    pipeline = _module("phase_8_pipeline_helpers", repo_root)
    pipeline.validate_processing_profile(profile, repo_root)
    if runner is None:
        runner = _run_configured_video
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output_dir = Path(output_root) / timestamp
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "input_manifest.json", manifest)
    _write_json(output_dir / "processing_profile.json", profile)
    _write_json(output_dir / "runtime.json", discover_runtime())
    if source_resolution is not None:
        _write_json(output_dir / "source_mount_resolution.json", source_resolution)
        shutil.copyfile(source_resolution["original_manifest_path"], output_dir / "original_source_manifest.json")
    results = []
    effective_videos = readiness["effective_videos"]
    modes = {video["video_id"]: configured_execution_mode(video) for video in effective_videos}
    _write_json(output_dir / "execution_modes.json", modes)
    for video in effective_videos:
        try:
            result = runner(video, profile, output_dir / video["video_id"], repo_root=repo_root)
            _require(isinstance(result, dict), "Pipeline must return an explicit result record")
            _require(result.get("video_id") == video["video_id"], "Pipeline output video identity mismatch")
            result["business_context"] = business_context
            if _is_completed(result):
                _collect_video(video, result, repo_root)
            results.append(result)
        except Exception as error:
            results.append({"video_id": video["video_id"], "status": "failed", "accepted_event_count": None,
                            "business_context": business_context,
                            "error": {"type": type(error).__name__, "message": str(error)}})
        # A completed prior video is never appended again after a rerun. This
        # immutable run directory gets its own snapshot and progress journal.
        _write_json(output_dir / "per_video_results.json", results)
    report = aggregate_batch(manifest, results, repo_root=repo_root)
    report.update(run_id=timestamp, input_manifest_sha256=sha256_file(manifest_path),
                  processing_profile_sha256=sha256_file(profile_path), output_directory=str(output_dir),
                  processing_assignment="sequential_cpu_cache_only" if all(mode == "verified_cache_replay" for mode in modes.values()) else "sequential_explicit_cuda0_for_new_inference",
                  execution_modes=modes, parallel_gpu_orchestration_implemented=False)
    if source_resolution is not None:
        report.update(original_manifest_sha256=source_resolution["original_manifest_sha256"],
            effective_manifest_sha256=source_resolution["effective_manifest_sha256"],
            source_mount_resolution=source_resolution, source_mount_resolution_sha256=sha256_file(output_dir / "source_mount_resolution.json"))
    write_batch_outputs(output_dir, report)
    return report
