"""Explicit eight-video input contract with opt-in confirmed filename mapping.

OpenCV discovery reports container properties, not a successful full decode.
Execution readiness separately checks all source bytes, native frames and
source-bound geometry review. This module does not run detection or counting.
Generic discovery never interprets names. The separate manifest builder uses
the user's confirmed KODETOKO-KATEGORI-KEADAAN convention, not a guessed rule.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from numbers import Real
from pathlib import Path
from typing import Any

from phase_5_geometry_helpers import Geometry


SCHEMA_VERSION = "phase8_batch_v1"
DAY_TYPES = ("weekday", "weekend")
RECORDING_PERIODS = ("pagi", "siang", "sore", "malam")
SLOT_IDS = tuple(f"{day}_{period}" for day in DAY_TYPES for period in RECORDING_PERIODS)
VIDEO_EXTENSIONS = frozenset({".mp4", ".avi", ".mov", ".mkv", ".m4v", ".webm", ".mpeg", ".mpg"})
_SYNTHETIC_LABEL = "SYNTHETIC_TEST_FIXTURE_NOT_REAL_DATASET"
_G3_SHA = "8d9ab10d63b7e50205d6e778061c8f22f98daba619eb1176b59003fd33391c15"
_N1_SHA = "89ff1d6201fba37d6edb9501f1524a5c96781ff1b9f442f25b728cb4d543c7a4"
_G3_FEEDBACK_SHA = "23ac7b06db0221f2ab30ef441a0d4075a742f67e424e76a0aa922bb283f842be"
_G1_DIRECTION_SHA = "3a1594a1e9e00079c8a16a8394d85934c869d516c22a2ef0e59a9eaed76c8034"
_N1_FEEDBACK_SHA = "a4c6fcf6f0332ae582e53a2b6df2cbf7ecdf1edb038df58fa8553f775707cc03"
RESEARCH_UNKNOWN_LOCATION_PURPOSE = "RESEARCH_WITH_DECLARED_UNKNOWN_LOCATION"
_UNKNOWN_LOCATION_AUTHORIZATION = "CONTINUE_RESEARCH_WITH_UNKNOWN_LOCATION_METADATA"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_batch_manifest() -> dict[str, Any]:
    """Unknown facts stay null; this scaffold cannot authorize a batch run."""
    return {
        "schema_version": SCHEMA_VERSION,
        "claim_type": "UNFILLED_BATCH_CONFIGURATION_NOT_EXECUTION_RESULT",
        "evidence_kind": "ACTUAL_DATASET",
        "location": {"store_code": None, "store_name": None, "latitude": None, "longitude": None},
        "videos": [
            {
                "slot_id": f"{day}_{period}", "video_id": f"{day}_{period}",
                "day_type": day, "recording_period": period,
                "source_path": None, "source_sha256": None,
                "observed_metadata": {"width": None, "height": None, "fps": None, "frame_count": None},
                "metadata_confirmed": False,
                "geometry_path": None, "geometry_sha256": None,
                "geometry_review_confirmed": False,
            }
            for day in DAY_TYPES for period in RECORDING_PERIODS
        ],
    }


def _positive_property(value: Any, *, integer: bool = False):
    if not isinstance(value, Real) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        return None
    if integer:
        return int(value) if float(value).is_integer() else None
    return float(value)


def parse_confirmed_video_filename(filename: str) -> dict[str, str]:
    """Parse only the user-confirmed KODETOKO-KATEGORI-KEADAAN convention.

    KATEGORI is WEEKDAY or WEEKEND; KEADAAN is PAGI, SIANG, SORE or MALAM.
    Day/period tokens are case-insensitive labels. The store code is preserved
    verbatim. The convention supplies neither a store name nor coordinates,
    date, lighting measurements, geometry approval or source integrity proof.
    """
    if not isinstance(filename, str) or not filename or Path(filename).name != filename:
        raise ValueError("Confirmed filename mapping requires a basename, without directories")
    if Path(filename).suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(f"Unsupported video filename extension: {filename}")
    match = re.fullmatch(r"([A-Za-z0-9_]+)-(WEEKDAY|WEEKEND)-(PAGI|SIANG|SORE|MALAM)",
                         Path(filename).stem, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Filename does not match confirmed KODETOKO-KATEGORI-KEADAAN: {filename}")
    code, day, period = match.groups()
    day, period = day.lower(), period.lower()
    return {"store_code": code, "day_type": day, "recording_period": period,
            "slot_id": f"{day}_{period}", "video_id": f"{day}_{period}"}


def make_manifest_from_discovery(discovered, *, dataset_root=None, location=None):
    """Construct an incomplete batch from measured inventory and confirmed names.

    Exactly eight distinct source identities for one code and every product
    slot are required. This pure builder writes no files. ``dataset_root`` can
    explicitly rebase inventory paths to the Kaggle mount, retaining measured
    relative paths. It does not make unavailable video files available.

    Metadata confirmation applies to the user-confirmed code/day/period naming
    rule. Observed dimensions/FPS/count are copied as measured (including nulls)
    and still require full source verification before processing. Geometry and
    unknown location facts remain unapproved/null, blocking full execution.
    """
    if not isinstance(discovered, list) or len(discovered) != 8:
        raise ValueError("Confirmed batch discovery must contain exactly eight video files")
    if dataset_root is not None and (not isinstance(dataset_root, (str, Path)) or not str(dataset_root)):
        raise ValueError("dataset_root must be an explicit nonempty path or null")
    parsed, slots, codes, identities = [], set(), set(), set()
    for entry in discovered:
        _object(entry, "discovery entry")
        mapping = parse_confirmed_video_filename(entry.get("filename"))
        if mapping["slot_id"] in slots:
            raise ValueError(f"Two discovered files map to the same slot: {mapping['slot_id']}")
        slots.add(mapping["slot_id"])
        codes.add(mapping["store_code"])
        digest = entry.get("source_sha256")
        _nullable_sha(digest, "discovery source_sha256")
        if digest is None or digest in identities:
            raise ValueError("Discovery needs eight distinct measured source SHA-256 identities")
        identities.add(digest)
        path = entry.get("source_path")
        _nullable_text(path, "discovery source_path")
        if path is None or Path(path).name != entry["filename"]:
            raise ValueError("Discovered source path must identify its exact discovered filename")
        if dataset_root is not None:
            relative = Path(entry.get("relative_path", entry["filename"]))
            if relative.is_absolute() or ".." in relative.parts or relative.name != entry["filename"]:
                raise ValueError("Discovery relative_path must stay inside the dataset and match filename")
            path = str(Path(dataset_root) / relative)
        observed = _object(entry.get("observed_metadata"), "discovered observed_metadata")
        copied = {field: observed.get(field) for field in ("width", "height", "fps", "frame_count")}
        for field, value in copied.items():
            if value is not None and (isinstance(value, bool) or not isinstance(value, Real)
                    or not math.isfinite(value) or value <= 0 or (field != "fps" and not isinstance(value, int))):
                raise ValueError(f"Discovered observed_metadata.{field} must be measured positive numeric data or null")
        parsed.append((entry, mapping, path, copied))
    if slots != set(SLOT_IDS):
        raise ValueError(f"Confirmed batch is missing slots: {sorted(set(SLOT_IDS) - slots)}")
    if len(codes) != 1:
        raise ValueError("Confirmed eight-video batch must belong to exactly one store code")
    manifest = make_batch_manifest()
    code = next(iter(codes))
    manifest["location"]["store_code"] = code
    if location is not None:
        _object(location, "explicit location")
        if any(key not in manifest["location"] for key in location):
            raise ValueError("Explicit location contains unsupported fields")
        if location.get("store_code") not in (None, code):
            raise ValueError("Explicit store_code conflicts with the confirmed filenames")
        manifest["location"].update({key: value for key, value in location.items() if key != "store_code"})
    manifest["claim_type"] = "DISCOVERED_INPUT_CONFIGURATION_NOT_EXECUTION_RESULT"
    manifest["filename_mapping_contract"] = {
        "claim_type": "USER_CONFIRMED_FILENAME_CONVENTION",
        "pattern": "KODETOKO-KATEGORI-KEADAAN.<video extension>",
        "day_types": ["WEEKDAY", "WEEKEND"], "periods": ["PAGI", "SIANG", "SORE", "MALAM"],
        "case_policy": "Day/period tokens ignore case; preserve exact store code",
        "unknown_facts": ["store_name", "latitude", "longitude", "recording_date", "per_video_geometry"],
    }
    by_slot = {video["slot_id"]: video for video in manifest["videos"]}
    for entry, mapping, path, observed in parsed:
        by_slot[mapping["slot_id"]].update(
            source_path=path, source_sha256=entry["source_sha256"], observed_metadata=observed,
            metadata_confirmed=True,
            metadata_confirmation={"claim_type": "USER_CONFIRMED_FILENAME_CONVENTION",
                "confirmed_fields": ["store_code", "day_type", "recording_period"],
                "source_filename": entry["filename"],
                "observed_metadata_provenance": entry.get("metadata_provenance"),
                "full_decode_required_before_execution": True},
        )
    return manifest


def discover_videos(dataset_root: str | Path) -> list[dict[str, Any]]:
    """Inventory actual files and reported OpenCV properties without name rules.

    ``frame_count`` is the container-reported property. It is not a full decode
    result; ``validate_manifest(check_files=True)`` verifies every selected frame.
    Missing OpenCV or unavailable metadata remains null, with a recorded issue.
    """
    root = Path(dataset_root)
    if not root.is_dir():
        raise FileNotFoundError(f"Dataset directory is unavailable: {root}")
    try:
        import cv2
    except ImportError:
        cv2 = None
    result = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS):
        entry = {
            "source_path": str(path.resolve()), "filename": path.name,
            "relative_path": str(path.relative_to(root)),
            "extension": path.suffix, "size_bytes": path.stat().st_size,
            "source_sha256": sha256_file(path),
            "observed_metadata": {"width": None, "height": None, "fps": None, "frame_count": None},
            "metadata_provenance": "OpenCV container properties; full decode not performed",
            "fully_decoded": False, "codec_fourcc": None, "metadata_issues": [],
            "store_code": None, "day_type": None, "recording_period": None,
        }
        if cv2 is None:
            entry["metadata_issues"].append("opencv_unavailable")
        else:
            capture = cv2.VideoCapture(str(path))
            try:
                if not capture.isOpened():
                    entry["metadata_issues"].append("opencv_cannot_open_video")
                else:
                    props = (("width", cv2.CAP_PROP_FRAME_WIDTH, True),
                             ("height", cv2.CAP_PROP_FRAME_HEIGHT, True),
                             ("fps", cv2.CAP_PROP_FPS, False),
                             ("frame_count", cv2.CAP_PROP_FRAME_COUNT, True))
                    for name, prop, integer in props:
                        entry["observed_metadata"][name] = _positive_property(capture.get(prop), integer=integer)
                    fourcc = int(capture.get(cv2.CAP_PROP_FOURCC))
                    if fourcc:
                        entry["codec_fourcc"] = "".join(chr((fourcc >> (8 * i)) & 0xff) for i in range(4))
                    if any(v is None for v in entry["observed_metadata"].values()):
                        entry["metadata_issues"].append("one_or_more_properties_unavailable")
            finally:
                capture.release()
        result.append(entry)
    return result


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _nullable_text(value, label):
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{label} must be nonempty text or null")


def _nullable_sha(value, label):
    _nullable_text(value, label)
    if value is not None and (len(value) != 64 or any(c not in "0123456789abcdef" for c in value)):
        raise ValueError(f"{label} must be a lowercase SHA-256 or null")


def _repo_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("Evidence/geometry paths must be relative to repo_root")
    return path


def _load_json(path: Path):
    return _object(json.loads(path.read_text(encoding="utf-8")), str(path))


def _bound_json(root: Path, reference: dict[str, Any]) -> dict[str, Any]:
    _object(reference, "artifact reference")
    path = _repo_file(root, reference["path"])
    if sha256_file(path) != reference["sha256"]:
        raise ValueError(f"Artifact hash mismatch: {reference['path']}")
    return _load_json(path)


def geometry_coordinates_sha256(document: dict[str, Any]) -> str:
    """Bind review to these source/native coordinates and direction labels.

    Excludes status, timestamps and approval_feedback to avoid a circular hash.
    Used by the NEW phase8_geometry_review_v1 contract only. Historical G3/N1
    approvals retain their original evidence contracts unchanged.
    """
    payload = {key: document.get(key) for key in (
        "draft_id", "source_video", "source_frame", "normalized", "rendered_native_pixels",
        "selected_anchor", "confirmed_direction_metadata",
    )}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _native_geometry(document, source_sha, width, height):
    source = _object(document.get("source_video"), "geometry source_video")
    if source.get("sha256") != source_sha:
        raise ValueError("Geometry belongs to a different source video")
    for field, expected in (("native_width", width), ("native_height", height)):
        if field in source and source[field] != expected:
            raise ValueError("Geometry source_video dimensions differ from selected source")
    if document.get("geometry_contract_accepted") is not True:
        raise ValueError("Geometry contract is not accepted")
    if not isinstance(document.get("status"), str) or not document["status"].startswith("ACCEPTED_"):
        raise ValueError("Geometry has no accepted status")
    if document.get("selected_anchor") != "bottom_center":
        raise ValueError("Current frozen experiment requires measured vehicle bottom-center")
    native = _object(document.get("rendered_native_pixels"), "rendered_native_pixels")
    if native.get("width") != width or native.get("height") != height:
        raise ValueError("Geometry native dimensions differ from the selected source")
    normalized = _object(document.get("normalized"), "normalized geometry")
    def resolve(point):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("Malformed normalized point")
        if any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) or not 0 <= v <= 1 for v in point):
            raise ValueError("Normalized coordinates must be finite within [0,1]")
        return (float(point[0]) * width, float(point[1]) * height)
    geometry = Geometry(resolve(normalized["line"]["P1"]), resolve(normalized["line"]["P2"]),
                        tuple(resolve(p) for p in normalized["side_a_polygon"]),
                        tuple(resolve(p) for p in normalized["side_b_polygon"]), width, height,
                        document["draft_id"], source_sha, document["status"])
    expected = {"line": {"P1": geometry.p1, "P2": geometry.p2},
                "side_a_polygon": geometry.side_a, "side_b_polygon": geometry.side_b}
    for key in ("side_a_polygon", "side_b_polygon"):
        if len(native[key]) != len(expected[key]):
            raise ValueError("Rendered polygon differs from normalized coordinates")
    pairs = [(native["line"][key], expected["line"][key]) for key in ("P1", "P2")]
    pairs += [(a, b) for key in ("side_a_polygon", "side_b_polygon") for a, b in zip(native[key], expected[key])]
    if any(len(a) != 2 or any(not isinstance(v, Real) or isinstance(v, bool) or not math.isfinite(v) for v in a)
           or any(not math.isclose(a[i], b[i], rel_tol=1e-12, abs_tol=1e-9) for i in (0, 1)) for a, b in pairs):
        raise ValueError("Rendered native coordinates differ from normalized template")
    directions = _object(document.get("confirmed_direction_metadata"), "confirmed_direction_metadata")
    if {directions.get("A_TO_B"), directions.get("B_TO_A")} != {"approaching camera", "moving away from camera"}:
        raise ValueError("Direction metadata must explicitly map both opposite directions")
    return geometry, directions


def _reviewed_geometry(root, path, digest, source_sha, width, height, synthetic):
    document = _load_json(path)
    geometry, directions = _native_geometry(document, source_sha, width, height)
    frame = _object(document.get("source_frame"), "geometry source_frame")
    if frame.get("width") != width or frame.get("height") != height:
        raise ValueError("Geometry review frame native dimensions differ")
    if not isinstance(frame.get("frame_index"), int) or isinstance(frame["frame_index"], bool) or frame["frame_index"] < 0:
        raise ValueError("Geometry review source frame index is invalid")
    frame_path = frame.get("path", frame.get("retained_path"))
    if not isinstance(frame_path, str) or sha256_file(_repo_file(root, frame_path)) != frame.get("sha256"):
        raise ValueError("Geometry review source frame is absent or has changed")
    evidence_frames = [{"path": frame_path, "sha256": frame["sha256"], "frame_index": frame["frame_index"]}]
    if digest == _G3_SHA:
        feedback = _bound_json(root, {"path": document["approval_feedback"], "sha256": _G3_FEEDBACK_SHA})
        direction = _bound_json(root, {"path": "docs/evidence/phase_5/feedback/G1_review_001.json",
                                      "sha256": _G1_DIRECTION_SHA})
        if feedback.get("reference_g3_and_polygon_b_approved") is not True or feedback.get("a_coordinates_identical_to_g3") is not True:
            raise ValueError("G3 original contextual approval is unsupported")
        source = _bound_json(root, {"path": document["geometry_source"], "sha256": document["geometry_source_sha256"]})
        if source.get("normalized") != document["normalized"]:
            raise ValueError("G3 proposal coordinates differ")
        recorded = direction["confirmed_direction_mapping"]
    elif digest == _N1_SHA:
        feedback = _bound_json(root, document["approval_feedback"])
        if document["approval_feedback"]["sha256"] != _N1_FEEDBACK_SHA:
            raise ValueError("N1 original feedback identity differs")
        source = _bound_json(root, document["source_proposal"])
        if source.get("normalized") != document["normalized"]:
            raise ValueError("N1 proposal coordinates differ")
        answers = [q.get("answer") for q in feedback.get("questions_and_answers", [])]
        if answers != ["Setuju untuk uji awal", "Ya, pemetaan arah benar"]:
            raise ValueError("N1 geometry/direction approval is unsupported")
        recorded = feedback["confirmed_decisions"]["direction_metadata"]
    else:
        feedback = _bound_json(root, document.get("approval_feedback"))
        if feedback.get("schema_version") != "phase8_geometry_review_v1" or feedback.get("approved") is not True:
            raise ValueError("New geometry needs explicit phase8_geometry_review_v1 approval")
        if feedback.get("source_video_sha256") != source_sha:
            raise ValueError("New geometry approval belongs to a different source")
        if feedback.get("geometry_coordinates_sha256") != geometry_coordinates_sha256(document):
            raise ValueError("Geometry coordinates/direction changed after review")
        for field in ("reviewer", "reviewed_at", "observation"):
            if not isinstance(feedback.get(field), str) or not feedback[field].strip():
                raise ValueError(f"New geometry review lacks {field}")
        fixture = feedback.get("claim_type") == _SYNTHETIC_LABEL
        if fixture != synthetic:
            raise ValueError("Synthetic review and actual dataset cannot be mixed")
        if frame.get("coordinate_space") != "native_full_frame_pixels":
            raise ValueError("New geometry review must explicitly use native_full_frame_pixels")
        if not synthetic:
            try:
                reviewed_at = datetime.fromisoformat(feedback["reviewed_at"].replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("Actual geometry review time must be ISO8601 with timezone") from exc
            if reviewed_at.utcoffset() is None:
                raise ValueError("Actual geometry review time requires an explicit timezone")
        evidence = feedback.get("evidence_frames")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("New geometry approval has no source frame evidence")
        if not any(item.get("path") == frame_path and item.get("sha256") == frame["sha256"]
                   and item.get("frame_index") == frame["frame_index"] for item in evidence if isinstance(item, dict)):
            raise ValueError("Geometry source frame is not included in review evidence")
        for item in evidence:
            if not isinstance(item, dict) or sha256_file(_repo_file(root, item["path"])) != item["sha256"]:
                raise ValueError("New geometry review evidence is missing or changed")
            if isinstance(item.get("frame_index"), bool) or not isinstance(item.get("frame_index"), int) or item["frame_index"] < 0:
                raise ValueError("New geometry review evidence needs a measured nonnegative frame index")
        evidence_frames = evidence
        recorded = feedback.get("confirmed_direction_metadata", {})
    if any(recorded.get(key) != directions[key] for key in ("A_TO_B", "B_TO_A")):
        raise ValueError("Geometry direction labels differ from original review")
    return document, geometry, evidence_frames


def _decode_source(path, frame_indices, observed):
    """Decode all frames and capture native BGR identity for review verification."""
    import cv2
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise ValueError("Source video cannot be opened by OpenCV")
    declared_count = _positive_property(capture.get(cv2.CAP_PROP_FRAME_COUNT), integer=True)
    fps = _positive_property(capture.get(cv2.CAP_PROP_FPS))
    count, frame_digests = 0, {}
    frame_indices = set(frame_indices)
    try:
        while True:
            okay, image = capture.read()
            if not okay:
                break
            if image is None or image.shape != (observed["height"], observed["width"], 3):
                raise ValueError("Native video frame dimensions/channels changed or differ from metadata")
            if count in frame_indices:
                frame_digests[count] = hashlib.sha256(image.tobytes()).hexdigest()
            count += 1
    finally:
        capture.release()
    if count != observed["frame_count"]:
        raise ValueError(f"Full decode count {count} differs from metadata {observed['frame_count']}")
    if declared_count is not None and declared_count != count:
        raise ValueError(f"Container reports {declared_count} frames but full decode reads {count}")
    if fps is None or not math.isclose(fps, observed["fps"], rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError("Observed FPS differs from OpenCV source metadata")
    if set(frame_digests) != frame_indices:
        raise ValueError("Geometry review frame is outside the full decoded video")
    return {"decoded_frame_count": count, "fps": fps, "review_frame_bgr_sha256_by_index": frame_digests,
            "timestamp_status": "index/FPS only; authoritative PTS/VFR unverified"}


def _verify_unknown_location_review(manifest, root, unknown_fields, synthetic):
    """A research-only acknowledgement never supplies unknown business facts."""
    if manifest.get("execution_purpose") != RESEARCH_UNKNOWN_LOCATION_PURPOSE:
        raise ValueError("Unknown location metadata requires an explicit research execution purpose")
    location = manifest["location"]
    if not location.get("store_code"):
        raise ValueError("Research acknowledgement cannot waive a missing store code")
    if not unknown_fields or "store_code" in unknown_fields:
        raise ValueError("Research acknowledgement applies only to unknown name/latitude/longitude")
    review = _bound_json(root, manifest.get("location_metadata_review"))
    if review.get("schema_version") != "phase8_location_metadata_review_v1":
        raise ValueError("Expected phase8_location_metadata_review_v1")
    expected_claim = _SYNTHETIC_LABEL if synthetic else "USER_CONFIRMED_UNKNOWN_LOCATION_METADATA_FOR_RESEARCH"
    if review.get("claim_type") != expected_claim:
        raise ValueError("Location acknowledgement claim type must truthfully match actual/synthetic input")
    if review.get("store_code") != location["store_code"]:
        raise ValueError("Location acknowledgement belongs to another store code")
    recorded_unknown = review.get("unknown_fields")
    if (not isinstance(recorded_unknown, list) or any(not isinstance(field, str) for field in recorded_unknown)
            or len(recorded_unknown) != len(set(recorded_unknown)) or set(recorded_unknown) != set(unknown_fields)):
        raise ValueError("Acknowledged unknown_fields must exactly match current null business metadata")
    if review.get("user_reply") != "belum diketahui":
        raise ValueError("Location acknowledgement must retain the explicit unknown-location reply")
    if review.get("authorization") != _UNKNOWN_LOCATION_AUTHORIZATION:
        raise ValueError("Research continuation with unknown location metadata was not authorized")
    if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
        raise ValueError("Location acknowledgement lacks its reviewer")
    reviewed_at = review.get("reviewed_at")
    if not isinstance(reviewed_at, str):
        raise ValueError("Location acknowledgement requires ISO8601 review time with timezone")
    try:
        parsed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Location acknowledgement review time is not ISO8601") from exc
    if parsed.utcoffset() is None:
        raise ValueError("Location acknowledgement review time requires timezone")
    source_binding = review.get("source_video_sha256_by_slot")
    expected_binding = {video["slot_id"]: video.get("source_sha256") for video in manifest["videos"]}
    for digest in expected_binding.values():
        _nullable_sha(digest, "research acknowledgement source binding")
        if digest is None:
            raise ValueError("Research acknowledgement requires all eight measured source SHA-256 identities")
    if len(set(expected_binding.values())) != 8 or source_binding != expected_binding:
        raise ValueError("Location acknowledgement does not bind the current eight unique input sources/slots")
    if "source_user_confirmation" in review:
        confirmation = _bound_json(root, review["source_user_confirmation"])
        if (confirmation.get("store_metadata_reply") != review["user_reply"]
                or confirmation.get("source_video_sha256_by_slot") != expected_binding):
            raise ValueError("Referenced user confirmation does not support this reply and eight-source scope")
    return True


def validate_manifest(manifest, repo_root, *, check_files=True, require_ready=True):
    """Return readiness and stable issue records; malformed schema raises ValueError.

    Unknown required facts block readiness rather than receiving defaults.
    The explicit, source-bound research acknowledgement can retain unknown
    name/latitude/longitude as null while allowing research processing. Such a
    run remains business-metadata-incomplete and cannot be called a final result.
    ``require_ready`` records whether execution is intended; neither mode raises
    for incomplete factual inputs, and neither can authorize an unchecked source.
    Synthetic fixtures are explicitly distinguished in ``evidence_kind``.
    """
    _object(manifest, "manifest")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Expected schema_version={SCHEMA_VERSION}")
    if not isinstance(check_files, bool) or not isinstance(require_ready, bool):
        raise ValueError("check_files and require_ready must be booleans")
    root = Path(repo_root).resolve()
    location = _object(manifest.get("location"), "location")
    videos = manifest.get("videos")
    if not isinstance(videos, list) or len(videos) != 8:
        raise ValueError("Manifest must contain exactly eight input slots")
    if any(not isinstance(v, dict) for v in videos):
        raise ValueError("Each video slot must be an object")
    ids = [video.get("slot_id") for video in videos]
    if any(not isinstance(slot, str) for slot in ids):
        raise ValueError("Each slot_id must be text")
    if len(set(ids)) != 8 or set(ids) != set(SLOT_IDS):
        raise ValueError("Manifest needs each weekday/weekend × pagi/siang/sore/malam slot exactly once")
    issues, effective = [], []
    def issue(code, slot_id=None, detail=None):
        row = {"code": code, "slot_id": slot_id}
        if detail is not None:
            row["detail"] = detail
        issues.append(row)
    unknown_location_fields = []
    for field in ("store_code", "store_name"):
        _nullable_text(location.get(field), f"location.{field}")
        if location.get(field) is None:
            unknown_location_fields.append(field)
    for field, minimum, maximum in (("latitude", -90, 90), ("longitude", -180, 180)):
        value = location.get(field)
        if value is None:
            unknown_location_fields.append(field)
        elif isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f"location.{field} must be a finite geographic coordinate in [{minimum},{maximum}]")
    synthetic = manifest.get("claim_type") == _SYNTHETIC_LABEL
    evidence_kind = "SYNTHETIC_TEST_FIXTURE" if synthetic else "ACTUAL_DATASET"
    if "evidence_kind" in manifest and manifest["evidence_kind"] != evidence_kind:
        raise ValueError("Manifest evidence_kind conflicts with its actual/synthetic claim_type")
    business_metadata_complete = not unknown_location_fields
    research_authorized = False
    if manifest.get("execution_purpose") == RESEARCH_UNKNOWN_LOCATION_PURPOSE:
        try:
            research_authorized = _verify_unknown_location_review(manifest, root, unknown_location_fields, synthetic)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            issue("invalid_location_metadata_review", detail=str(exc))
    elif manifest.get("location_metadata_review") is not None:
        issue("research_location_waiver_not_authorized", detail="Explicit research execution purpose is required")
    if not research_authorized:
        for field in unknown_location_fields:
            issue(f"missing_location_{field}")
    location_metadata_status = ("COMPLETE" if business_metadata_complete else
        "UNKNOWN_DECLARED_RESEARCH_ONLY" if research_authorized else "INCOMPLETE_UNACKNOWLEDGED")
    known_sha = {}
    for video in videos:
        slot = video["slot_id"]
        day, period = slot.split("_", 1)
        if video.get("video_id") != slot or video.get("day_type") != day or video.get("recording_period") != period:
            raise ValueError(f"{slot}: video_id/day_type/recording_period must agree with its explicit slot")
        if "store_code" in video and video["store_code"] != location.get("store_code"):
            raise ValueError(f"{slot}: videos must belong to the single manifest location")
        for field in ("metadata_confirmed", "geometry_review_confirmed"):
            if not isinstance(video.get(field), bool):
                raise ValueError(f"{slot}.{field} must be an explicit boolean")
            if video[field] is not True:
                issue(f"{field}_required", slot)
        for field in ("source_path", "geometry_path"):
            _nullable_text(video.get(field), f"{slot}.{field}")
            if video.get(field) is None:
                issue(f"missing_{field}", slot)
        for field in ("source_sha256", "geometry_sha256"):
            _nullable_sha(video.get(field), f"{slot}.{field}")
            if video.get(field) is None:
                issue(f"missing_{field}", slot)
        digest = video.get("source_sha256")
        if digest is not None:
            if digest in known_sha:
                issue("duplicate_source_sha256", slot, f"Same source as {known_sha[digest]}; eight distinct inputs required")
            else:
                known_sha[digest] = slot
        observed = _object(video.get("observed_metadata"), f"{slot}.observed_metadata")
        for field in ("width", "height", "frame_count", "fps"):
            value = observed.get(field)
            if value is None:
                issue(f"missing_observed_{field}", slot)
            elif (isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0
                  or (field != "fps" and not isinstance(value, int))):
                raise ValueError(f"{slot}.observed_metadata.{field} must be a positive {'number' if field == 'fps' else 'integer'} or null")
        row = dict(video)
        row["location"] = dict(location)
        row["business_metadata_complete"] = business_metadata_complete
        row["unknown_location_fields"] = list(unknown_location_fields)
        row["location_metadata_status"] = location_metadata_status
        row["research_unknown_location_authorized"] = research_authorized
        row["research_only"] = research_authorized
        row["execution_purpose"] = manifest.get("execution_purpose", "COMPLETE_BUSINESS_BATCH")
        if research_authorized:
            row["location_metadata_review"] = dict(manifest["location_metadata_review"])
        effective.append(row)
        geometry = document = evidence_frames = None
        metadata_ready = all(observed.get(field) is not None for field in ("width", "height", "fps", "frame_count"))
        if metadata_ready and digest and video.get("geometry_path") and video.get("geometry_sha256"):
            try:
                path = _repo_file(root, video["geometry_path"])
                if sha256_file(path) != video["geometry_sha256"]:
                    raise ValueError("Selected geometry file hash differs")
                document, geometry, evidence_frames = _reviewed_geometry(root, path, video["geometry_sha256"],
                                                                        digest, observed["width"], observed["height"], synthetic)
                row["effective_geometry"] = {"geometry_id": geometry.geometry_id, "p1": list(geometry.p1),
                    "p2": list(geometry.p2), "side_a": [list(p) for p in geometry.side_a],
                    "side_b": [list(p) for p in geometry.side_b], "width": geometry.width, "height": geometry.height,
                    "confirmed_direction_metadata": document["confirmed_direction_metadata"]}
            except (ValueError, KeyError, TypeError, OSError) as exc:
                issue("invalid_or_unreviewed_geometry", slot, str(exc))
        if not check_files:
            issue("source_files_not_verified", slot)
        elif video.get("source_path") and digest:
            try:
                path = Path(video["source_path"])
                if not path.is_absolute():
                    path = root / path
                if sha256_file(path) != digest:
                    raise ValueError("Actual video bytes do not match source_sha256")
                if metadata_ready:
                    # A missing geometry blocks the run, but must not invent a review frame.
                    indices = [item["frame_index"] for item in evidence_frames] if geometry is not None else [0]
                    decoded = _decode_source(path, indices, observed)
                    row["verified_source"] = decoded
                    if geometry is not None:
                        import cv2
                        for item in evidence_frames:
                            image = cv2.imread(str(_repo_file(root, item["path"])), cv2.IMREAD_COLOR)
                            if (image is None or image.shape != (observed["height"], observed["width"], 3)
                                    or hashlib.sha256(image.tobytes()).hexdigest()
                                    != decoded["review_frame_bgr_sha256_by_index"][item["frame_index"]]):
                                raise ValueError("Geometry evidence PNG is not the selected video's measured native source frame")
            except (ValueError, OSError, ImportError) as exc:
                issue("source_verification_failed", slot, str(exc))
    return {"ready": not issues, "issues": issues, "effective_videos": effective,
            "execution_requested": require_ready,
            "evidence_kind": evidence_kind,
            "business_metadata_complete": business_metadata_complete,
            "unknown_location_fields": list(unknown_location_fields),
            "location_metadata_status": location_metadata_status,
            "research_unknown_location_authorized": research_authorized,
            "research_only": research_authorized}


def describe_issues(validation):
    """Stable human-readable lines suitable for notebook preflight output."""
    _object(validation, "validation result")
    return [f"{item['slot_id'] or 'location'}: {item['code']}" + (f" — {item['detail']}" if item.get("detail") else "")
            for item in validation.get("issues", [])]
