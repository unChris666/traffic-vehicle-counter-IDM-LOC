"""Fresh, source-bound manual overlays of full-video Phase 8 machine snapshots.

No model, video decoder, identity resolver or geometry state machine is run.
The frozen reviewed-snapshot implementation keeps its geometry/category/unit/
return guards. One audited production provenance guard accepts the explicitly
verified Phase 2/7/8 measurement namespaces; source artifacts stay immutable.
An empty template is an unreviewed queue, never invented manual confirmation.
"""
from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import types


SCHEMA_VERSION = "phase8_full_video_review_input_v1"
POLICY = "phase8_guarded_full_video_review_overlay_v1"
BASE_PATH = "docs/evidence/phase_6/option_b_verification/build_reviewed_comparison.py"
BASE_SHA256 = "663a52190f8c495533d50b36509232dad0d3fb64e0d31c0c3d669415fb38e81b"
FROZEN_SOURCES = {
    "notebooks/phase_5_geometry_helpers.py": "c344aa5b73b8b75fcdd567355b867e977a3d8e170feb512cdf0d15ac61b123c9",
    "notebooks/phase_6_counting_helpers.py": "99a98807d315b42bd3995b8e68afc749e47c76b03b39329dbb5f4b867661f4c5",
}
MEASUREMENT_NAMESPACES = (
    "retained_phase_2_detection", "retained_phase_7_detection", "retained_phase_8_detection",
)
OLD_GUARD = 'observation.get("measurement_provenance") != "retained_phase_2_detection"'
NEW_GUARD = 'observation.get("measurement_provenance") not in ' + repr(MEASUREMENT_NAMESPACES)
SOURCE_FILES = (
    "counting_configuration.json", "counting_report.json", "episodes.json.gz",
    "machine_passage_decisions.json.gz", "machine_count_events.json.gz", "machine_aggregate.json",
)
OBSERVATION_FIELDS = (
    "frame_index", "track_id", "raw_bbox", "original_detection_index", "class_id",
    "class_name", "confidence", "emitted", "measurement_provenance",
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _array(path):
    result = json.loads(gzip.decompress(Path(path).read_bytes()).decode("utf-8"))
    _require(isinstance(result, list), "Expected retained JSON array: " + str(path))
    return result


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                                   allow_nan=False) + "\n", encoding="utf-8")


def _write_gzip(path, value):
    Path(path).write_bytes(gzip.compress((canonical(value) + "\n").encode(), mtime=0))


def _path(root, value):
    _require(isinstance(value, str) and bool(value.strip()), "Explicit source path required")
    path = Path(value)
    return (path if path.is_absolute() else Path(root) / path).resolve()


def load_review_adapter(repo_root):
    """Change one source-provenance guard, preserving all old production rules."""
    root = Path(repo_root).resolve()
    original = root / BASE_PATH
    _require(sha256_file(original) == BASE_SHA256, "Frozen reviewed-snapshot source changed")
    for path, expected in FROZEN_SOURCES.items():
        _require(sha256_file(root / path) == expected, "Frozen review predicate source changed: " + path)
    source = original.read_text(encoding="utf-8")
    _require(source.count(OLD_GUARD) == 1, "Expected exactly one production provenance guard")
    adapted = source.replace(OLD_GUARD, NEW_GUARD, 1)
    _require(adapted.replace(NEW_GUARD, OLD_GUARD, 1) == source, "Additional review semantics changed")
    module = types.ModuleType("phase8_frozen_review_overlay_adapter")
    module.__file__ = str(original)
    exec(compile(adapted, str(original) + "::phase8_provenance_adapter", "exec"), module.__dict__)
    proof = {"base_path": BASE_PATH, "base_source_sha256": BASE_SHA256,
        "adapted_source_sha256": hashlib.sha256(adapted.encode()).hexdigest(),
        "production_substitution_count": 1, "old_guard": OLD_GUARD, "new_guard": NEW_GUARD,
        "allowed_measurement_namespaces": list(MEASUREMENT_NAMESPACES),
        "algorithm_category_geometry_identity_controls_changed": False,
        "historical_source_modified": False, "frozen_predicate_sources": deepcopy(FROZEN_SOURCES)}
    return module, adapted, proof


def verify_machine_manifest(machine_run_dir):
    root = Path(machine_run_dir).resolve()
    path = root / "retention_manifest.json"
    manifest = _json(path)
    _require(manifest.get("phase") == 8, "Only a new Phase 8 machine manifest is reviewable")
    entries = manifest.get("artifacts")
    _require(isinstance(entries, list) and bool(entries), "Machine manifest has no retained artifacts")
    bindings = {"retention_manifest.json": sha256_file(path)}
    for entry in entries:
        relative = entry.get("path")
        _require(isinstance(relative, str) and not Path(relative).is_absolute(), "Unsafe manifest path")
        item = (root / relative).resolve()
        _require(item.is_relative_to(root) and relative not in bindings, "Unsafe/duplicate manifest entry")
        expected_size = entry.get("bytes", entry.get("size_bytes"))
        _require(item.is_file() and item.stat().st_size == expected_size
                 and sha256_file(item) == entry.get("sha256"), "Machine artifact changed: " + relative)
        bindings[relative] = entry["sha256"]
    _require(all(name in bindings for name in SOURCE_FILES), "Machine manifest lacks review source artifacts")
    return bindings


def _load_machine(machine_run_dir, repo_root):
    run, repo = Path(machine_run_dir).resolve(), Path(repo_root).resolve()
    bindings = verify_machine_manifest(run)
    config, report = _json(run / "counting_configuration.json"), _json(run / "counting_report.json")
    _require(report.get("phase") == 8 and report.get("status") == "completed_full_video_machine_snapshot_review_pending",
             "Review requires a completed full-video Phase 8 machine snapshot")
    _require(report.get("execution_kind") == "ACTUAL_RETAINED_SOURCE_COUNTING_REPLAY",
             "Synthetic or partial execution is not actual video evidence")
    _require(report.get("counting_scope") == "ALL_MEASURED_TRACK_EPISODES_FULL_VIDEO"
             and config.get("scope") == {"track_ids": None, "association_frame_windows": None},
             "Historical sampling windows cannot authorize full-video review")
    identity = config.get("input_identity")
    _require(isinstance(identity, dict) and identity == report.get("source_identity"), "Machine source identity mismatch")
    _require(identity.get("variant") == "raw", "Current Phase 8 review profile requires raw frames")
    _require(isinstance(report.get("run_id"), str) and report["run_id"].startswith("p8_"), "Fresh Phase 8 run identity required")
    profile = report.get("configuration")
    _require(isinstance(profile, dict) and profile.get("phase") == 8, "Phase 8 processing profile absent")
    from phase_8_pipeline_helpers import validate_processing_profile, validate_cache_provenance, validate_appearance_execution
    validate_processing_profile(profile, repo)
    _require({k: config.get(k) for k in profile["counting"]} == profile["counting"], "Counting differs from frozen profile")
    provenance = report.get("cache_provenance", {}).get("measurement_provenance")
    _require(provenance in MEASUREMENT_NAMESPACES, "Unsupported source measurement provenance")
    records_path = _path(repo, report.get("records_path"))
    _require(sha256_file(records_path) == identity.get("records_sha256"), "Source cache hash mismatch")
    proof = report["cache_provenance"]
    if proof.get("source_report_sha256"):
        validated = validate_cache_provenance(proof, identity, profile, repo_root=repo)
        _require(validated["frame_count"] == proof.get("frame_count")
                 and validated["measurement_provenance"] == provenance,
                 "Retained GPU report differs from cache provenance")
    else:
        # Fresh GPU outputs bind their finalized parent report through its
        # parent retention manifest, avoiding a circular report/counting hash.
        _require(proof.get("source_phase") == 8 and proof.get("new_detector_tracker_encoder_inference") is True,
                 "Actual donor execution proof absent")
        donor_path = _path(repo, proof.get("source_report_path"))
        donor = _json(donor_path)
        parent_manifest = _json(donor_path.parent / "retention_manifest.json")
        entries = {entry["path"]: entry for entry in parent_manifest.get("artifacts", [])}
        for item in (donor_path, records_path):
            _require(item.is_relative_to(donor_path.parent), "Fresh cache belongs to another GPU run")
            entry = entries.get(str(item.relative_to(donor_path.parent)))
            _require(entry and entry.get("sha256") == sha256_file(item)
                     and entry.get("bytes", entry.get("size_bytes")) == item.stat().st_size,
                     "Fresh GPU report/cache differs from parent retention manifest")
        _require(donor.get("execution_kind") == "ACTUAL_MODEL_EXECUTION"
                 and donor.get("inference_status") == "completed"
                 and donor.get("run_id") == identity["parent_run_id"]
                 and donor.get("source_identity") == identity
                 and donor.get("track_records_sha256") == identity["records_sha256"]
                 and donor.get("frames_processed") == proof["frame_count"],
                 "Fresh Phase 8 actual inference/frame proof incomplete")
        validate_appearance_execution(donor)
        _require(donor.get("source_helper_sha256") == sha256_file(repo / "notebooks/phase_8_pipeline_helpers.py"),
                 "Fresh GPU execution helper differs from the source reviewed for this profile")
        finalized_proof = dict(proof, source_report_sha256=sha256_file(donor_path),
            appearance_records_path=str(donor_path.parent / "appearance_records.jsonl.gz"),
            appearance_records_sha256=donor.get("appearance_records_sha256"))
        validated = validate_cache_provenance(finalized_proof, identity, profile, repo_root=repo)
        _require(validated["frame_count"] == proof["frame_count"]
                 and validated["measurement_provenance"] == provenance,
                 "Fresh finalized donor model/appearance controls differ from source proof")
    geometry_path = _path(repo, report.get("geometry_path"))
    _require(geometry_path.is_relative_to(repo) and sha256_file(geometry_path) == identity.get("geometry_sha256"),
             "Accepted geometry hash/path mismatch")
    from phase_8_manifest_helpers import _reviewed_geometry
    _, geometry, _ = _reviewed_geometry(repo, geometry_path, identity["geometry_sha256"],
        identity["video_sha256"], identity["width"], identity["height"], False)
    episodes = _array(run / "episodes.json.gz")
    decisions = _array(run / "machine_passage_decisions.json.gz")
    events = _array(run / "machine_count_events.json.gz")
    expected_count = report.get("cache_provenance", {}).get("frame_count")
    _require(type(expected_count) is int and expected_count > 0, "Complete source frame count absent")
    donors, observations, count = {}, {}, 0
    with gzip.open(records_path, "rt", encoding="utf-8") as source:
        for line in source:
            frame = json.loads(line)
            _require(frame.get("frame_index") == count and type(frame.get("frame_index")) is int,
                     "Source cache must contain every frame from zero in order")
            _require(all(frame.get(k) == identity[k] for k in ("video_sha256", "variant", "parent_run_id", "width", "height")),
                     "Source cache identity/native dimensions mismatch")
            donors[count] = frame.get("detector_input_frame_pixel_sha256")
            for observed in frame.get("emitted_tracks", []):
                key = (count, observed.get("track_id"), observed.get("original_detection_index"))
                _require(key not in observations and observed.get("measurement_provenance") == provenance,
                         "Duplicate/mixed-provenance emitted source observation")
                observations[key] = observed
            count += 1
    _require(count == expected_count == report.get("source_frame_count"), "Source full decode/cache count mismatch")
    for episode in episodes:
        _require(episode.get("source_identity") == identity, "Episode belongs to another source")
        for observed in episode.get("observations", []):
            key = (observed.get("frame_index"), observed.get("track_id"), observed.get("original_detection_index"))
            original = observations.get(key)
            _require(original is not None and all(observed.get(k) == original.get(k) for k in OBSERVATION_FIELDS),
                     "Episode does not preserve source raw measured observation")
    binding = {"schema_version": SCHEMA_VERSION, "source_run_id": report["run_id"],
        "source_identity": deepcopy(identity), "source_snapshot_kind": "machine",
        "source_machine_decisions_sha256": bindings["machine_passage_decisions.json.gz"],
        "source_machine_events_sha256": bindings["machine_count_events.json.gz"],
        "source_configuration_sha256": bindings["counting_configuration.json"],
        "source_episodes_sha256": bindings["episodes.json.gz"],
        "source_machine_manifest_sha256": bindings["retention_manifest.json"],
        "source_processing_profile_sha256": _digest(profile), "scope": "full_video"}
    return {"run": run, "config": config, "report": report, "identity": identity,
        "bindings": bindings, "binding": binding, "episodes": episodes, "decisions": decisions,
        "events": events, "geometry": geometry, "geometry_path": geometry_path,
        "donors": donors, "records_path": records_path}


def make_review_template(machine_run_dir, *, repo_root):
    """Return an executable empty overlay and a separate unreviewed work queue.

    Move a queue entry to ``decisions`` only after actual image review. HOLD also
    needs retained photographic evidence; null fields are not review decisions.
    """
    source = _load_machine(machine_run_dir, repo_root)
    template = deepcopy(source["binding"])
    template.update(claim_type="UNREVIEWED_TEMPLATE_NOT_PIXEL_REVIEW_OR_GROUND_TRUTH",
        decisions=[], review_queue=[{"candidate_id": candidate["candidate_id"],
            "machine_status": candidate["status"], "machine_reasons": candidate.get("reasons", []),
            "disposition": None, "reviewer": None, "reason": None, "evidence": [],
            "physical_unit_id": None, "passage_id": None, "category": None,
            "unit_confirmed": False, "category_confirmed": False, "identity_confirmed": False}
            for candidate in source["decisions"] if candidate.get("accepted_count_event") is not True],
        instructions="Empty decisions preserves machine events and pending candidates. Review cannot repair invalid geometry or category history.")
    return template


def _validate_review_bindings(review, source):
    _require(isinstance(review, dict), "Review input must be an object")
    for key, expected in source["binding"].items():
        _require(review.get(key) == expected, "Stale/mixed-scope review binding: " + key)
    _require(isinstance(review.get("decisions"), list), "Explicit review decisions list required")


def _verify_raw_photos(review, source, repo_root):
    """Check native unannotated lossless raw photos against cache donor pixels.

    Annotated/cropped contact sheets may be extra evidence, but only exact raw
    native PNG donors establish the required origin/crossing/confirmation frames.
    No source-video decode occurs, so this binds retained images to retained raw
    cache evidence; it does not independently establish physical identity.
    """
    by_id = {candidate["candidate_id"]: candidate for candidate in source["decisions"]}
    root = Path(repo_root).resolve()
    for row in review["decisions"]:
        if row.get("disposition") != "CONFIRM_PASSAGE":
            continue
        candidate = by_id.get(row.get("candidate_id"))
        _require(candidate is not None, "Unknown review candidate")
        diagnostic = candidate.get("diagnostic", {})
        required = {diagnostic.get(k) for k in ("origin_frame", "crossing_frame_start", "crossing_frame_end", "confirmation_frame")}
        if diagnostic.get("crossing_evidence", {}).get("method") == "measured_touch_then_opposite_sign":
            required.update(range(diagnostic["crossing_frame_start"] + 1, diagnostic["crossing_frame_end"]))
        covered = set()
        for ref in row.get("evidence", []):
            if ref.get("kind") != "native_raw_source_frame":
                continue
            frame = ref.get("frame_index")
            _require(type(frame) is int and frame in source["donors"], "Raw photo frame is outside retained source")
            identity = source["identity"]
            _require(ref.get("source_video_sha256") == identity["video_sha256"]
                     and ref.get("width") == identity["width"] and ref.get("height") == identity["height"]
                     and ref.get("frame_indices") == [frame], "Raw photo source/frame/native identity mismatch")
            path = _path(root, ref.get("path"))
            _require(path.is_relative_to(root) and path.suffix.lower() == ".png"
                     and sha256_file(path) == ref.get("sha256"), "Raw photo path/hash mismatch")
            from PIL import Image
            with Image.open(path) as image:
                _require(image.format == "PNG" and image.mode == "RGB"
                         and image.size == (identity["width"], identity["height"]), "Raw source PNG must be RGB at native size")
                bgr = image.convert("RGB").tobytes()
            # Pillow RGB bytes are reordered exactly to the native OpenCV BGR donor.
            raw = bytearray(bgr)
            raw[0::3], raw[2::3] = raw[2::3], raw[0::3]
            actual = hashlib.sha256(raw).hexdigest()
            expected = source["donors"][frame]
            _require(isinstance(expected, str) and len(expected) == 64
                     and actual == expected == ref.get("frame_bgr_sha256"), "Raw image differs from measured detector donor pixels")
            covered.add(frame)
        _require(required <= covered, "Positive review needs exact native raw source photos for origin/crossing/confirmation")


def apply_review(machine_run_dir, review_input_path, output_dir, *, repo_root):
    """Write one independent reviewed snapshot and return a batch descriptor."""
    source = _load_machine(machine_run_dir, repo_root)
    repo = Path(repo_root).resolve()
    review_path, output = Path(review_input_path).resolve(), Path(output_dir).resolve()
    _require(review_path.is_relative_to(repo), "Review input must be retained under repo_root")
    _require(output != source["run"] and not source["run"].is_relative_to(output)
             and output != review_path.parent and not review_path.is_relative_to(output), "Output would overwrite source/review")
    _require(not output.exists() or not any(output.iterdir()), "Refusing to overwrite a reviewed snapshot")
    review_bytes = review_path.read_bytes()
    review = json.loads(review_bytes)
    _validate_review_bindings(review, source)
    _verify_raw_photos(review, source, repo)
    module, adapted, adaptation = load_review_adapter(repo)
    result = module.build_reviewed_snapshot(source["decisions"], source["episodes"], source["events"],
        source["config"], review, repo=repo, geometry=source["geometry"])
    untouched = [event for event in source["events"]
        if event["candidate_id"] not in {row["candidate_id"] for row in review["decisions"]}]
    by_event = {event["event_id"]: event for event in result["accepted_events"]}
    _require(all(by_event.get(event["event_id"]) == event for event in untouched), "Untouched accepted event payload changed")
    _require(verify_machine_manifest(source["run"]) == source["bindings"]
             and sha256_file(source["records_path"]) == source["identity"]["records_sha256"]
             and review_path.read_bytes() == review_bytes, "Source inputs changed during manual overlay")
    result["report"].update(phase=8, overlay_policy=POLICY, source_run_id=source["report"]["run_id"],
        source_machine_binding=source["binding"], manual_review_is_formal_ground_truth=False,
        complete_eight_video_batch=False, full_video_source_scope=True,
        whole_video_traffic_result=False, aggregate_semantics="ACCEPTED_REVIEWED_PASSAGE_SUBTOTAL_PENDING_UNRESOLVED",
        review_input_sha256=hashlib.sha256(review_bytes).hexdigest(),
        method_sha256=sha256_file(__file__), provenance_adapter=adaptation,
        preserved_machine_event_ids=[event["event_id"] for event in untouched],
        raw_photo_verification="native PNG BGR equals retained raw detector donor; no independent source-video decode",
        geometry_resolver_detector_tracker_encoder_rerun=False)
    output.mkdir(parents=True, exist_ok=True)
    _write_gzip(output / "resolved_decisions.json.gz", result["resolved_decisions"])
    _write_gzip(output / "accepted_events.json.gz", result["accepted_events"])
    _write_json(output / "aggregate.json", result["aggregate"])
    _write_json(output / "report.json", result["report"])
    (output / "review_input.json").write_bytes(review_bytes)
    (output / "review_adapter.executed_source.py").write_text(adapted, encoding="utf-8")
    _write_json(output / "review_adapter_provenance.json", adaptation)
    configuration = source["run"] / "counting_configuration.json"
    snapshot = {"kind": "reviewed", "run_id": source["report"]["run_id"],
        "review_id": "p8rv_" + _digest({"binding": source["binding"], "review_sha256": sha256_file(review_path)}),
        "scope": "full_video", "source_identity": deepcopy(source["identity"]),
        "configuration_path": str(configuration), "configuration_sha256": sha256_file(configuration)}
    for prefix, name in (("events", "accepted_events.json.gz"), ("decisions", "resolved_decisions.json.gz")):
        snapshot[prefix + "_path"] = str(output / name)
        snapshot[prefix + "_sha256"] = sha256_file(output / name)
    _write_json(output / "phase_8_snapshot.json", snapshot)
    _write_json(output / "execution_manifest.json", {"phase": 8, "source_machine_binding": source["binding"],
        "model_geometry_resolver_rerun": False, "formal_ground_truth": False,
        "artifacts": [{"path": str(path.relative_to(output)), "sha256": sha256_file(path), "bytes": path.stat().st_size}
                      for path in sorted(output.iterdir()) if path.is_file()]})
    return {"run_id": snapshot["run_id"], "source_identity": deepcopy(source["identity"]),
        "snapshot": snapshot, "aggregate": result["aggregate"], "report": result["report"],
        "frames_processed": source["report"]["source_frame_count"], "scope": "full_video",
        "status": "completed_full_video_reviewed_snapshot_pending_cases_retained", "output_dir": str(output)}


def _validate_typed_events(events, decisions, source, module, repo_root, snapshot_kind):
    """Recheck event IDs and measured candidates without resolving identities."""
    by_candidate = {row.get("candidate_id"): row for row in decisions}
    episodes = {row.get("episode_id"): row for row in source["episodes"]}
    _require(len(by_candidate) == len(decisions) and len(episodes) == len(source["episodes"]),
             "Duplicate source candidate/episode identity")
    config, identity = source["config"], source["identity"]
    semantic = {key: config[key] for key in ("policy_version", "metric", "neutral_band_px", "confirmation_observations", "association")}
    semantic.update(grouping_enabled=config.get("grouping_enabled"),
                    association_frame_windows=config["scope"]["association_frame_windows"])
    machine_policy = "cfg6b_" + _digest(semantic)
    overlay_semantic = {key: config[key] for key in module.SEMANTIC_POLICY_FIELDS if key in config}
    overlay_policy = "cfg6br_" + _digest({"source_identity": identity, "source_policy": overlay_semantic,
                                        "review_overlay_policy": module.POLICY})
    seen_events, seen_candidates = set(), set()
    for event in events:
        candidate = by_candidate.get(event.get("candidate_id"))
        _require(candidate is not None and candidate.get("accepted_count_event") is True
                 and candidate.get("status") == "accepted" and not candidate.get("reasons")
                 and not candidate.get("hard_block_reasons"), "Event lacks an accepted, conflict-free candidate")
        _require(event.get("type") == "CountEvent" and event.get("status") == "accepted"
                 and event.get("accepted_count_event") is True and event.get("source_identity") == identity,
                 "Typed event/source identity mismatch")
        _require(event.get("event_id") not in seen_events and event.get("candidate_id") not in seen_candidates,
                 "Duplicate event/candidate in selected snapshot")
        seen_events.add(event.get("event_id")); seen_candidates.add(event.get("candidate_id"))
        for field in ("event_id", "category", "track_id", "physical_unit_id", "passage_id"):
            _require(candidate.get(field) == event.get(field), "Event/decision source mismatch: " + field)
        _require(candidate.get("episode_id") == event.get("vehicle_measurement_episode_id")
                 and candidate.get("measurement_support") == event.get("measurement_support")
                 and candidate.get("diagnostic") == event.get("geometry_evidence")
                 and candidate.get("diagnostic", {}).get("direction") == event.get("direction"),
                 "Event changed source BC/geometry/episode evidence")
        module.validate_candidate(candidate, episodes, config, source["geometry"], repo_root)
        if event.get("manual_review_applied") is True:
            _require(snapshot_kind == "reviewed" and event.get("automatic_acceptance") is False,
                     "Manual event cannot be an automatic machine success")
            expected_policy = overlay_policy
            expected_event = "ce6br_" + _digest({"source_identity": identity, "policy_identity": expected_policy,
                "physical_unit_id": event["physical_unit_id"], "passage_id": event["passage_id"]})
        else:
            expected_policy = machine_policy
            expected_event = "ce6b_" + _digest({"source_identity": identity, "policy": semantic,
                "physical_unit_id": event["physical_unit_id"], "passage_id": event["passage_id"]})
        _require(event.get("policy_identity") == expected_policy and event.get("event_id") == expected_event,
                 "Event policy/ID differs from source-bound counting or manual overlay policy")
    _require({row["candidate_id"] for row in decisions if row.get("accepted_count_event") is True} == seen_candidates,
             "Accepted candidate is missing a typed event")
    _, _, _, aggregate_events = module.geometry_imports(repo_root)
    return aggregate_events(events)


def _same_subtotals(first, second):
    """Machine/reviewed aggregate scopes have distinct, preserved labels."""
    return all(first.get(key) == second.get(key)
               for key in ("total", "by_category", "by_direction", "event_ids"))


def _verify_review_execution_manifest(directory, source):
    manifest = _json(directory / "execution_manifest.json")
    _require(manifest.get("phase") == 8 and manifest.get("source_machine_binding") == source["binding"]
             and manifest.get("model_geometry_resolver_rerun") is False,
             "Reviewed snapshot does not bind the current full-video machine source")
    entries = manifest.get("artifacts")
    _require(isinstance(entries, list) and bool(entries), "Reviewed snapshot manifest is empty")
    seen = set()
    for entry in entries:
        relative = entry.get("path")
        _require(isinstance(relative, str) and not Path(relative).is_absolute() and relative not in seen,
                 "Unsafe/duplicate reviewed artifact path")
        path = (directory / relative).resolve()
        _require(path.is_relative_to(directory) and path.is_file()
                 and path.stat().st_size == entry.get("bytes", entry.get("size_bytes"))
                 and sha256_file(path) == entry.get("sha256"), "Reviewed artifact differs from its execution manifest")
        seen.add(relative)
    _require({"review_input.json", "resolved_decisions.json.gz", "accepted_events.json.gz", "aggregate.json",
              "report.json", "review_adapter.executed_source.py", "review_adapter_provenance.json"} <= seen,
             "Reviewed manifest lacks evidence/method/output artifacts")
    return sha256_file(directory / "execution_manifest.json")


def validate_selected_snapshot(snapshot, *, repo_root):
    """Validate one actual machine/reviewed snapshot before batch aggregation.

    Positive review is reconstructed with the frozen guarded postprocessor, not
    with models or the resolver. A reviewed snapshot can contain both untouched
    automatic cfg6b events and explicit manual cfg6br events; they remain distinct.
    """
    _require(isinstance(snapshot, dict) and snapshot.get("kind") in {"machine", "reviewed"},
             "Select exactly one machine/reviewed snapshot")
    repo = Path(repo_root).resolve()
    paths = {}
    for name in ("configuration", "events", "decisions"):
        path = _path(repo, snapshot.get(name + "_path"))
        _require(path.is_file() and sha256_file(path) == snapshot.get(name + "_sha256"),
                 "Selected snapshot artifact hash mismatch: " + name)
        paths[name] = path
    source = _load_machine(paths["configuration"].parent, repo)
    _require(paths["configuration"] == source["run"] / "counting_configuration.json"
             and snapshot.get("run_id") == source["report"]["run_id"], "Selected snapshot binds another run/configuration")
    if "source_identity" in snapshot:
        _require(snapshot["source_identity"] == source["identity"], "Selected snapshot source identity mismatch")
    events, decisions = _array(paths["events"]), _array(paths["decisions"])
    module, adapted, adaptation = load_review_adapter(repo)
    empty = {"source_identity": source["identity"], "decisions": []}
    # Validate untouched machine events even when a review later holds one.
    machine = module.build_reviewed_snapshot(source["decisions"], source["episodes"], source["events"],
        source["config"], empty, repo=repo, geometry=source["geometry"])
    _validate_typed_events(source["events"], source["decisions"], source, module, repo, "machine")
    machine_aggregate = _json(source["run"] / "machine_aggregate.json")
    _require(_same_subtotals(machine["aggregate"], machine_aggregate), "Machine aggregate does not reconcile")
    execution_manifest_sha256 = None
    if snapshot["kind"] == "machine":
        _require(events == source["events"] and decisions == source["decisions"],
                 "Selected machine outputs differ from the retained machine snapshot")
        canonical_result = machine
        canonical_result["aggregate"] = machine_aggregate
    else:
        directory = paths["events"].parent
        _require(paths["events"].name == "accepted_events.json.gz"
                 and paths["decisions"] == directory / "resolved_decisions.json.gz",
                 "Reviewed decisions/events must belong to one reviewed snapshot")
        execution_manifest_sha256 = _verify_review_execution_manifest(directory, source)
        reviews = _json(directory / "review_input.json")
        _validate_review_bindings(reviews, source)
        _verify_raw_photos(reviews, source, repo)
        _require((directory / "review_adapter.executed_source.py").read_text(encoding="utf-8") == adapted
                 and _json(directory / "review_adapter_provenance.json") == adaptation,
                 "Reviewed method is not the frozen provenance-only guard adapter")
        canonical_result = module.build_reviewed_snapshot(source["decisions"], source["episodes"], source["events"],
            source["config"], reviews, repo=repo, geometry=source["geometry"])
        _require(events == canonical_result["accepted_events"] and decisions == canonical_result["resolved_decisions"]
                 and _json(directory / "aggregate.json") == canonical_result["aggregate"],
                 "Reviewed outputs differ from the guarded review reconstruction")
        retained_report = _json(directory / "report.json")
        _require(all(retained_report.get(key) == value for key, value in canonical_result["report"].items())
                 and retained_report.get("source_machine_binding") == source["binding"]
                 and retained_report.get("overlay_policy") == POLICY, "Reviewed report differs from guarded reconstruction")
        expected_review_id = "p8rv_" + _digest({"binding": source["binding"],
            "review_sha256": sha256_file(directory / "review_input.json")})
        if "review_id" in snapshot:
            _require(snapshot["review_id"] == expected_review_id, "Selected review identity mismatch")
    aggregate = _validate_typed_events(events, decisions, source, module, repo, snapshot["kind"])
    _require(_same_subtotals(aggregate, canonical_result["aggregate"]), "Selected accepted aggregate does not reconcile")
    aggregate = canonical_result["aggregate"]
    return {"status": "validated_selected_full_video_snapshot", "source_run_id": source["report"]["run_id"],
        "source_identity": deepcopy(source["identity"]), "snapshot_kind": snapshot["kind"],
        "events": events, "decisions": decisions, "aggregate": aggregate,
        "source_machine_binding": source["binding"], "review_execution_manifest_sha256": execution_manifest_sha256,
        "model_geometry_resolver_rerun": False, "formal_ground_truth": False}
