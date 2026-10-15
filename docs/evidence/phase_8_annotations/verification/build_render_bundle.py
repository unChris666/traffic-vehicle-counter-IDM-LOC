#!/usr/bin/env python3
"""Package a private CPU-only annotation notebook; never upload or run it.

The parent Kaggle notebook outputs and the eight original TGDI source videos
are attached read-only inputs. Only new presentation code/tests, the frozen
geometry helper and accepted geometry JSONs are embedded. No model weights,
videos, detection caches or modified counting decisions enter this packet.
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


NOTEBOOK = "notebooks/08a_annotation_review.ipynb"
GEOMETRY_MANIFEST = "docs/evidence/phase_8/config/batch_manifest_TGDI_G3_T1_v2.json"
PARENT_KERNEL = "chrisbiran/phase-8-tgdi-full-video-research"
RAW_DATASET = "chrisbiran/tgdi-traffic-videos"
KERNEL_ID = "chrisbiran/phase-8-tgdi-annotation-review"
ORIGINAL_BATCH_MANIFEST_SHA256 = "79e8cf19747c63b34f8389d8f525925fd0c69e966f3d12ffb89716a5c89bd0dc"
DEFAULT_SOURCES = (
    "notebooks/phase_8_annotation_helpers.py",
    "notebooks/phase_8_annotation_tests.py",
    "notebooks/phase_8_annotation_batch.py",
    "notebooks/phase_8_annotation_batch_tests.py",
    "notebooks/phase_5_geometry_helpers.py",
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


def cell_source(cell):
    source = cell.get("source", [])
    return "".join(source) if isinstance(source, list) else source


def bootstrap_cell(payload, binding):
    source = '''# Exact presentation source extraction; no detector/tracker/ReID execution.
from pathlib import Path
import base64, gzip, hashlib, json, sys

ANNOTATION_SOURCE_BUNDLE = json.loads(__PAYLOAD__)
ANNOTATION_SOURCE_BINDING_SHA256 = __BINDING__
_manifest = {name: {key: entry[key] for key in ('sha256', 'bytes')}
             for name, entry in ANNOTATION_SOURCE_BUNDLE.items()}
_canonical = json.dumps(_manifest, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
if hashlib.sha256(_canonical.encode()).hexdigest() != ANNOTATION_SOURCE_BINDING_SHA256:
    raise ValueError('Annotation source bundle manifest changed')
_parent = Path(globals().get('PHASE8_ANNOTATION_SOURCE_PARENT', '/kaggle/working')).resolve()
REPO_ROOT = (_parent / ('annotation_source_snapshot_' + ANNOTATION_SOURCE_BINDING_SHA256[:16])).resolve()
if not REPO_ROOT.is_relative_to(_parent):
    raise ValueError('Unsafe annotation source root')
for name, entry in ANNOTATION_SOURCE_BUNDLE.items():
    relative = Path(name)
    if not name or relative.is_absolute() or '..' in relative.parts or chr(92) in name or relative.as_posix() != name:
        raise ValueError('Unsafe annotation source path')
    data = gzip.decompress(base64.b64decode(entry['gzip_base64'], validate=True))
    if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise ValueError('Annotation packaged source hash mismatch: ' + name)
    target = REPO_ROOT / relative
    if target.is_symlink() or not target.resolve().is_relative_to(REPO_ROOT):
        raise ValueError('Annotation source path escapes snapshot')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not target.is_file() or target.read_bytes() != data:
            raise ValueError('Existing annotation snapshot differs')
    else:
        target.write_bytes(data)
sys.path.insert(0, str(REPO_ROOT / 'notebooks'))
INPUT_ROOT = globals().get('INPUT_ROOT', '/kaggle/input')
SOURCE_RUN_ROOT = globals().get('SOURCE_RUN_ROOT', None)
SOURCE_VIDEO_ROOT = globals().get('SOURCE_VIDEO_ROOT', None)
OUTPUT_ROOT = globals().get('OUTPUT_ROOT', '/kaggle/working/phase_8_annotated_review_v1')
VIDEO_IDS = globals().get('VIDEO_IDS', None)
_proof = {'claim_type': 'HASH_BOUND_PRESENTATION_SOURCE_EXTRACTION_NOT_MODEL_EXECUTION',
          'source_bundle_binding_sha256': ANNOTATION_SOURCE_BINDING_SHA256,
          'source_files': _manifest,
          'original_batch_manifest_sha256': __PARENT_MANIFEST__,
          'new_detector_tracker_reid_inference': False,
          'original_machine_events_or_decisions_modified': False}
(REPO_ROOT / 'annotation_source_provenance.json').write_text(json.dumps(_proof, indent=2, sort_keys=True) + '\\n')
print('Verified annotation source snapshot:', REPO_ROOT)
print('Annotation bundle binding:', ANNOTATION_SOURCE_BINDING_SHA256)
print('CPU-only render from retained original events and source videos; no new model execution')
'''
    return source.replace("__PAYLOAD__", repr(canonical(payload))).replace("__BINDING__", repr(binding)).replace(
        "__PARENT_MANIFEST__", repr(ORIGINAL_BATCH_MANIFEST_SHA256))


def build(repo_root, output_dir, *, notebook_path=NOTEBOOK, source_paths=DEFAULT_SOURCES):
    repo = Path(repo_root).resolve()
    destination = Path(output_dir).resolve()
    geometry_manifest = json.loads((repo / GEOMETRY_MANIFEST).read_text(encoding="utf-8"))
    videos = geometry_manifest["videos"]
    if len(videos) != 8 or len({v["video_id"] for v in videos}) != 8:
        raise ValueError("Eight approved TGDI geometry inputs required")
    paths = list(source_paths) + [notebook_path]
    for video in videos:
        path = safe_relative(video["geometry_path"])
        if sha((repo / path).read_bytes()) != video["geometry_sha256"]:
            raise ValueError("Approved geometry hash changed")
        paths.append(path.as_posix())
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate bundled source path")
    manifest, payload = {}, {}
    for name in paths:
        relative = safe_relative(name)
        path = repo / relative
        if path.is_symlink() or not path.resolve().is_relative_to(repo) or not path.is_file():
            raise ValueError("Packaged file is missing or outside the source repository: " + name)
        if path.suffix not in (".py", ".json", ".ipynb"):
            raise ValueError("Only explicit presentation source/geometry files may be bundled")
        data = path.read_bytes()
        if path.suffix == ".py":
            tree = ast.parse(data.decode(), filename=name)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    modules = [node.module or ""] if isinstance(node, ast.ImportFrom) else [x.name for x in node.names]
                    if any(m.split(".")[0] in ("ultralytics", "torch", "onnxruntime") for m in modules):
                        raise ValueError("Annotation packet must not load a detector/tracker/encoder runtime")
        manifest[name] = {"sha256": sha(data), "bytes": len(data)}
        payload[name] = dict(manifest[name], gzip_base64=base64.b64encode(gzip.compress(data, mtime=0)).decode())
    binding = sha(canonical(manifest).encode())
    canonical_notebook = json.loads((repo / notebook_path).read_text(encoding="utf-8"))
    notebook = deepcopy(canonical_notebook)
    code_cells = 0
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            ast.parse(cell_source(cell)); cell["execution_count"] = None; cell["outputs"] = []; code_cells += 1
    if code_cells == 0:
        raise ValueError("Canonical annotation notebook has no executable cells")
    bootstrap = bootstrap_cell(payload, binding); ast.parse(bootstrap)
    notebook["cells"] = [{"cell_type": "markdown", "id": "annotation-bundle-note", "metadata": {}, "source": [
        "# TGDI — retained-cache annotation review\n",
        "This CPU-only notebook preserves the original Phase8 machine events and renders a separate review output.\n",
        "The parent output and source videos are mounted read-only; no detector/tracker/ReID is rerun.\n",
    ]}, {"cell_type": "code", "id": "annotation-bundle-bootstrap", "metadata": {}, "execution_count": None,
         "outputs": [], "source": bootstrap.splitlines(keepends=True)}] + notebook["cells"]
    destination.mkdir(parents=True, exist_ok=True)
    notebook_output = destination / "phase8_tgdi_annotation_review.ipynb"
    metadata_output = destination / "kernel-metadata.json"
    notebook_bytes = (json.dumps(notebook, indent=1, ensure_ascii=False) + "\n").encode()
    metadata = {"id": KERNEL_ID, "title": "Phase 8 TGDI annotation review", "code_file": notebook_output.name,
        "language": "python", "kernel_type": "notebook", "is_private": True,
        "enable_gpu": False, "enable_tpu": False, "enable_internet": False,
        "dataset_sources": [RAW_DATASET], "kernel_sources": [PARENT_KERNEL],
        "competition_sources": [], "model_sources": [], "keywords": []}
    notebook_output.write_bytes(notebook_bytes)
    metadata_output.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    report = {"claim_type": "ANNOTATION_SOURCE_PACKAGING_NOT_EXECUTION", "source_files": manifest,
        "source_file_count": len(manifest), "source_bundle_binding_sha256": binding,
        "canonical_notebook_path": notebook_path, "canonical_notebook_sha256": manifest[notebook_path]["sha256"],
        "canonical_notebook_code_cells": code_cells, "canonical_code_cells_modified": False,
        "submitted_notebook": {"path": str(notebook_output), "sha256": sha(notebook_bytes), "bytes": len(notebook_bytes)},
        "kernel_metadata": {"path": str(metadata_output), "sha256": sha(metadata_output.read_bytes())},
        "original_parent_kernel": PARENT_KERNEL, "original_parent_kernel_version": 2,
        "original_batch_manifest_sha256": ORIGINAL_BATCH_MANIFEST_SHA256,
        "source_videos_dataset": RAW_DATASET, "original_input_mounts_read_only": True,
        "builder": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).read_bytes())},
        "videos_bundled": False, "model_weights_bundled": False, "retained_model_caches_bundled": False,
        "new_model_execution": False, "counting_decisions_modified": False, "upload_performed": False,
        "submission_folder": str(destination), "accelerator": "CPU_ONLY"}
    (destination / "source_bundle_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--notebook", default=NOTEBOOK)
    parser.add_argument("--source", action="append", help="Explicit complete source list; replaces the default list")
    args = parser.parse_args()
    print(json.dumps(build(args.repo_root, args.output_dir, notebook_path=args.notebook,
        source_paths=args.source if args.source else DEFAULT_SOURCES), indent=2, sort_keys=True))
