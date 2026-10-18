#!/usr/bin/env python3
"""Build a private CPU Kaggle B v2 replay packet without uploading or running it.

Only explicit Python/notebook/configuration evidence is packaged. Original
model measurements and raw videos remain read-only Kaggle inputs. B v2 writes
a separate counting experiment; it never rewrites the immutable B v1 donor.
"""
from __future__ import annotations

import argparse
import ast
import base64
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import re


NOTEBOOK = "notebooks/08b_counting_b_v2_replay.ipynb"
NEW_GEOMETRY_MANIFEST = "results/b_v2/config/geometry_manifest.json"
OLD_GEOMETRY_MANIFEST = "docs/evidence/phase_8/config/batch_manifest_TGDI_G3_T1_v2.json"
POLICY = "results/b_v2/config/policy.json"
USER_DECISIONS = "results/b_v2/input/user_decisions.json"
PARENT_KERNEL = "chrisbiran/phase-8-tgdi-full-video-research"
RAW_DATASET = "chrisbiran/tgdi-traffic-videos"
KERNEL_ID = "chrisbiran/phase-8-tgdi-b-v2-review"
DONOR_MANIFEST_SHA256 = "79e8cf19747c63b34f8389d8f525925fd0c69e966f3d12ffb89716a5c89bd0dc"
MAX_PACKET_BYTES = 1_000_000
PYTHON_SOURCES = (
    "notebooks/phase_8_b_v2_counting.py",
    "notebooks/phase_8_b_v2_counting_tests.py",
    "notebooks/phase_8_b_v2_annotation.py",
    "notebooks/phase_8_b_v2_annotation_tests.py",
    "notebooks/phase_8_b_v2_batch.py",
    "notebooks/phase_8_b_v2_batch_tests.py",
    "notebooks/phase_5_geometry_helpers.py",
    "notebooks/phase_8_annotation_helpers.py",
    "notebooks/phase_8_annotation_batch.py",
)
FORBIDDEN_IMPORTS = frozenset(("ultralytics", "torch", "onnxruntime", "kaggle", "requests", "httpx"))
EXPECTED_VIDEO_IDS = frozenset(f"{day}_{period}" for day in ("weekday", "weekend")
                               for period in ("pagi", "siang", "sore", "malam"))
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bKGAT_[A-Za-z0-9_-]{20,}"),
    re.compile(r"https?://[^\s\"'<>]*(?:[?&](?:X-Goog-Signature|X-Amz-Signature|token|access_token)=)", re.I),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def safe_relative(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Explicit packaged relative path required")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or path.as_posix() != value:
        raise ValueError("Unsafe package path")
    return path


def read_source(repo, name):
    path = repo / safe_relative(name)
    if path.is_symlink() or not path.resolve().is_relative_to(repo) or not path.is_file():
        raise ValueError("Packaged source missing or outside repository: " + name)
    if path.suffix not in (".py", ".json", ".ipynb"):
        raise ValueError("Only explicit source/configuration may be bundled")
    data = path.read_bytes()
    text = data.decode("utf-8")
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        raise ValueError("Credential or signed capability detected in packaged source: " + name)
    return data


def cell_source(cell):
    source = cell.get("source", [])
    return "".join(source) if isinstance(source, list) else source


def check_python(source, filename):
    tree = ast.parse(source, filename=filename)
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.Import):
            modules = [item.name for item in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
            function = node.func
            dynamic = ((isinstance(function, ast.Name) and function.id == "__import__")
                       or (isinstance(function, ast.Attribute) and function.attr == "import_module"))
            if dynamic and isinstance(node.args[0].value, str):
                modules = [node.args[0].value]
        if any(module.split(".")[0] in FORBIDDEN_IMPORTS for module in modules):
            raise ValueError("B v2 packet must not import model/network runtimes: " + filename)
    return tree


def bootstrap_cell(payload, binding):
    source = r'''# Exact hash-bound B v2 source extraction; no model or counting execution here.
from pathlib import Path
import base64, gzip, hashlib, json, sys

B_V2_SOURCE_BUNDLE = json.loads(__PAYLOAD__)
B_V2_SOURCE_BINDING_SHA256 = __BINDING__
_manifest = {name: {key: entry[key] for key in ('sha256', 'bytes')}
             for name, entry in B_V2_SOURCE_BUNDLE.items()}
_canonical = json.dumps(_manifest, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
if hashlib.sha256(_canonical.encode()).hexdigest() != B_V2_SOURCE_BINDING_SHA256:
    raise ValueError('B v2 source bundle manifest changed')
_parent = Path(globals().get('PHASE8_B_V2_SOURCE_PARENT', '/kaggle/working')).resolve()
REPO_ROOT = (_parent / ('b_v2_source_snapshot_' + B_V2_SOURCE_BINDING_SHA256[:16])).resolve()
if not REPO_ROOT.is_relative_to(_parent):
    raise ValueError('Unsafe B v2 source root')
for name, entry in B_V2_SOURCE_BUNDLE.items():
    relative = Path(name)
    if not name or relative.is_absolute() or '..' in relative.parts or chr(92) in name or relative.as_posix() != name:
        raise ValueError('Unsafe B v2 source path')
    data = gzip.decompress(base64.b64decode(entry['gzip_base64'], validate=True))
    if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise ValueError('B v2 packaged source hash mismatch: ' + name)
    target = REPO_ROOT / relative
    if target.is_symlink() or not target.resolve().is_relative_to(REPO_ROOT):
        raise ValueError('B v2 source path escapes snapshot')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not target.is_file() or target.read_bytes() != data:
            raise ValueError('Existing B v2 source snapshot differs')
    else:
        target.write_bytes(data)
sys.path.insert(0, str(REPO_ROOT / 'notebooks'))
_proof = {'claim_type': 'HASH_BOUND_B_V2_SOURCE_EXTRACTION_NOT_REPLAY_OR_MODEL_EXECUTION',
          'source_bundle_binding_sha256': B_V2_SOURCE_BINDING_SHA256,
          'source_files': _manifest,
          'original_donor_manifest_sha256': __DONOR_MANIFEST__,
          'new_detector_tracker_reid_inference': False,
          'original_machine_events_or_decisions_modified': False,
          'new_b_v2_counting_executed_by_bootstrap': False}
(REPO_ROOT / 'b_v2_source_provenance.json').write_text(json.dumps(_proof, indent=2, sort_keys=True) + '\n')
print('Verified B v2 source snapshot:', REPO_ROOT)
print('B v2 bundle binding:', B_V2_SOURCE_BINDING_SHA256)
print('CPU replay uses retained measurements; new policy results are separate from B v1')
'''
    return source.replace("__PAYLOAD__", repr(canonical(payload))).replace("__BINDING__", repr(binding)).replace(
        "__DONOR_MANIFEST__", repr(DONOR_MANIFEST_SHA256))


def _video_map(manifest):
    videos = manifest.get("videos", [])
    result = {video["video_id"]: video for video in videos}
    if len(videos) != 8 or len(result) != 8 or set(result) != EXPECTED_VIDEO_IDS:
        raise ValueError("Exactly eight unique TGDI geometry inputs required")
    return result


def build(repo_root, output_dir):
    repo = Path(repo_root).resolve()
    destination = Path(output_dir).resolve()
    # Resolve only the explicit geometry/configuration paths. Never recursively
    # collect repository files, credentials, videos, caches or model weights.
    new_geometry = json.loads(read_source(repo, NEW_GEOMETRY_MANIFEST))
    old_geometry = json.loads(read_source(repo, OLD_GEOMETRY_MANIFEST))
    new_videos, old_videos = _video_map(new_geometry), _video_map(old_geometry)
    template_path = new_geometry["template_path"]
    template_data = read_source(repo, template_path)
    if sha(template_data) != new_geometry["template_sha256"]:
        raise ValueError("User-uploaded geometry template SHA changed")
    policy = json.loads(read_source(repo, POLICY))
    decisions = json.loads(read_source(repo, USER_DECISIONS))
    if (policy["source_template_sha256"] != sha(template_data)
            or decisions["source_template_sha256"] != sha(template_data)):
        raise ValueError("Policy/user decisions belong to another geometry upload")
    paths = list(PYTHON_SOURCES) + [NOTEBOOK, NEW_GEOMETRY_MANIFEST, POLICY, USER_DECISIONS, template_path]
    for video_id in sorted(EXPECTED_VIDEO_IDS):
        for video in (new_videos[video_id], old_videos[video_id]):
            name = safe_relative(video["geometry_path"]).as_posix()
            if sha(read_source(repo, name)) != video["geometry_sha256"]:
                raise ValueError("Geometry hash changed: " + video_id)
            paths.append(name)
        if new_videos[video_id]["video_sha256"] != old_videos[video_id]["source_sha256"]:
            raise ValueError("New geometry and frozen donor refer to different video bytes")
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate bundled source path")
    manifest, payload = {}, {}
    for name in paths:
        data = read_source(repo, name)
        if Path(name).suffix == ".py":
            check_python(data.decode("utf-8"), name)
        elif Path(name).suffix == ".json":
            json.loads(data)
        manifest[name] = {"sha256": sha(data), "bytes": len(data)}
        payload[name] = dict(manifest[name], gzip_base64=base64.b64encode(gzip.compress(data, mtime=0)).decode())
    binding = sha(canonical(manifest).encode())
    canonical_notebook = json.loads(read_source(repo, NOTEBOOK))
    notebook = deepcopy(canonical_notebook)
    original_code = []
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            check_python(cell_source(cell), NOTEBOOK)
            original_code.append(cell_source(cell))
            if cell.get("execution_count") is not None or cell.get("outputs", []):
                raise ValueError("Canonical notebook must retain no execution outputs")
    if not original_code:
        raise ValueError("Canonical B v2 notebook has no executable cells")
    bootstrap = bootstrap_cell(payload, binding)
    check_python(bootstrap, "b_v2_source_bootstrap")
    notebook["cells"] = [
        {"cell_type": "markdown", "id": "bv2-bundle-note", "metadata": {}, "source": [
            "# TGDI — B v2 retained-cache counting and annotation experiment\n",
            "Private CPU replay, with original model caches and source videos mounted read-only.\n",
            "This notebook creates a separate B v2 counting result; B v1 remains unchanged.\n"]},
        {"cell_type": "code", "id": "bv2-bundle-bootstrap", "metadata": {}, "execution_count": None,
         "outputs": [], "source": bootstrap.splitlines(keepends=True)},
    ] + notebook["cells"]
    if [cell_source(cell) for cell in notebook["cells"][2:] if cell["cell_type"] == "code"] != original_code:
        raise ValueError("Canonical code cells were modified during packaging")
    notebook_data = (json.dumps(notebook, indent=1, ensure_ascii=False, allow_nan=False) + "\n").encode()
    if len(notebook_data) >= MAX_PACKET_BYTES:
        raise ValueError("B v2 notebook packet must be smaller than 1 MB")
    notebook_name = "phase8_tgdi_b_v2_review.ipynb"
    metadata = {"id": KERNEL_ID, "title": "Phase 8 TGDI B v2 review", "code_file": notebook_name,
        "language": "python", "kernel_type": "notebook", "is_private": True,
        "enable_gpu": False, "enable_tpu": False, "enable_internet": False,
        "dataset_sources": [RAW_DATASET], "kernel_sources": [PARENT_KERNEL],
        "competition_sources": [], "model_sources": [], "keywords": []}
    metadata_data = (json.dumps(metadata, indent=2) + "\n").encode()
    report = {"claim_type": "B_V2_SOURCE_PACKAGING_NOT_EXECUTION", "source_files": manifest,
        "source_file_count": len(manifest), "source_bundle_binding_sha256": binding,
        "canonical_notebook_path": NOTEBOOK, "canonical_notebook_sha256": manifest[NOTEBOOK]["sha256"],
        "canonical_notebook_code_cells": len(original_code), "canonical_code_cells_modified": False,
        "submitted_notebook": {"path": str(destination / notebook_name), "sha256": sha(notebook_data),
                               "bytes": len(notebook_data)},
        "kernel_metadata": {"path": str(destination / "kernel-metadata.json"), "sha256": sha(metadata_data)},
        "dedicated_kernel": KERNEL_ID, "original_parent_kernel": PARENT_KERNEL, "original_parent_kernel_version": 2,
        "original_batch_manifest_sha256": DONOR_MANIFEST_SHA256, "source_videos_dataset": RAW_DATASET,
        "original_input_mounts_read_only": True, "videos_bundled": False, "model_weights_bundled": False,
        "retained_model_caches_bundled": False, "credentials_bundled": False, "new_model_execution": False,
        "new_counting_execution": False, "original_machine_events_or_decisions_modified": False,
        "upload_performed": False, "submission_folder": str(destination), "accelerator": "CPU_ONLY",
        "builder": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).read_bytes())}}
    report_data = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    if len(notebook_data) + len(metadata_data) + len(report_data) >= MAX_PACKET_BYTES:
        raise ValueError("Entire B v2 submission packet must be smaller than 1 MB")
    outputs = {notebook_name: notebook_data, "kernel-metadata.json": metadata_data,
               "source_bundle_manifest.json": report_data}
    # Rebuilding identical bytes is safe; never replace a different review packet.
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in outputs.items():
        target = destination / name
        if target.is_symlink() or not target.resolve().is_relative_to(destination):
            raise ValueError("Unsafe submission output path")
        if target.exists() and (not target.is_file() or target.read_bytes() != data):
            raise ValueError("Submission output already contains different bytes: " + name)
    for name, data in outputs.items():
        (destination / name).write_bytes(data)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.repo_root, args.output_dir), indent=2, sort_keys=True))
