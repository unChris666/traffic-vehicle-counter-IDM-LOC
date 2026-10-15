#!/usr/bin/env python3
"""Build a private Kaggle PREPARE submission; never upload or run models.

The canonical notebook cells are preserved verbatim. A preceding hash-checked
bootstrap extracts the exact minimal source files and explicitly selects
MODE='prepare'. No videos, model weights or historical model outputs are bundled.
"""
from __future__ import annotations

import argparse
import ast
import base64
import gzip
import hashlib
import json
from pathlib import Path


NOTEBOOK = "notebooks/08_end_to_end_batch.ipynb"
MANIFEST = "docs/evidence/phase_8/config/batch_manifest_v1.json"
PROFILE = "docs/evidence/phase_8/config/processing_profile_v1.json"
DATASET = "chrisbiran/tgdi-traffic-videos"
KERNEL_ID = "chrisbiran/phase-8-tgdi-batch-preparation"
SOURCE_PATHS = (
    "notebooks/phase_8_manifest_helpers.py", "notebooks/phase_8_manifest_tests.py",
    "notebooks/phase_8_pipeline_helpers.py", "notebooks/phase_8_pipeline_tests.py",
    "notebooks/phase_8_batch_helpers.py", "notebooks/phase_8_batch_tests.py",
    "notebooks/phase_8_review_helpers.py", "notebooks/phase_8_review_tests.py",
    "notebooks/phase_5_geometry_helpers.py", "notebooks/phase_6_counting_helpers.py",
    "notebooks/phase_6_identity_resolution_helpers.py", "notebooks/phase_7_night_helpers.py",
    "notebooks/phase_7_temporal_helpers.py",
    "docs/evidence/phase_6/option_b_verification/build_reviewed_comparison.py",
    "docs/evidence/phase_6/option_b_calibration/frozen_thresholds.json",
    NOTEBOOK, MANIFEST, PROFILE,
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _safe_relative(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Unsafe packaged source path: " + str(value))
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or path.as_posix() != value:
        raise ValueError("Unsafe packaged source path: " + str(value))
    return path


def _notebook_source(cell):
    value = cell.get("source", [])
    return "".join(value) if isinstance(value, list) else value


def make_bootstrap(source_files, binding):
    """Portable extraction cell, with a parent override only for local validation."""
    bootstrap = '''# Exact, source-bound repository snapshot. This cell does not run models.
from pathlib import Path
import base64, gzip, hashlib, json

SOURCE_BUNDLE = json.loads(__SOURCE_BUNDLE__)
SOURCE_BUNDLE_BINDING_SHA256 = __SOURCE_BINDING__
_source_manifest = {relative: {key: entry[key] for key in ('sha256', 'bytes')}
                    for relative, entry in SOURCE_BUNDLE.items()}
_canonical = json.dumps(_source_manifest, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
if hashlib.sha256(_canonical.encode()).hexdigest() != SOURCE_BUNDLE_BINDING_SHA256:
    raise ValueError('Source bundle manifest binding changed.')
_parent = Path(globals().get('PHASE8_SOURCE_PARENT', '/kaggle/working')).resolve()
REPO_ROOT = (_parent / ('phase8_source_snapshot_' + SOURCE_BUNDLE_BINDING_SHA256[:16])).resolve()
if not REPO_ROOT.is_relative_to(_parent):
    raise ValueError('Unsafe source snapshot root.')
for relative, entry in SOURCE_BUNDLE.items():
    _relative = Path(relative)
    if (not relative or _relative.is_absolute() or '..' in _relative.parts
            or chr(92) in relative or _relative.as_posix() != relative):
        raise ValueError('Unsafe bundle source path: ' + relative)
    _bytes = gzip.decompress(base64.b64decode(entry['gzip_base64'], validate=True))
    if len(_bytes) != entry['bytes'] or hashlib.sha256(_bytes).hexdigest() != entry['sha256']:
        raise ValueError('Packaged source checksum mismatch: ' + relative)
    _target = REPO_ROOT / _relative
    if _target.is_symlink() or not _target.resolve().is_relative_to(REPO_ROOT):
        raise ValueError('Source snapshot symlink/path escape: ' + relative)
    _target.parent.mkdir(parents=True, exist_ok=True)
    if _target.exists():
        if not _target.is_file() or _target.read_bytes() != _bytes:
            raise ValueError('Existing snapshot differs; use a fresh source parent.')
    else:
        _target.write_bytes(_bytes)
_provenance = {'claim_type':'HASH_BOUND_SOURCE_EXTRACTION_NOT_MODEL_EXECUTION',
               'source_bundle_binding_sha256':SOURCE_BUNDLE_BINDING_SHA256,
               'source_files':_source_manifest, 'mode':'prepare'}
(REPO_ROOT / 'source_bundle_provenance.json').write_text(json.dumps(_provenance, indent=2, sort_keys=True) + '\\n')
MODE = 'prepare'
print('Verified source snapshot:', REPO_ROOT)
print('Bundle binding:', SOURCE_BUNDLE_BINDING_SHA256)
print('Mode:', MODE, '(input preparation and software guards; no model execution)')
'''
    return bootstrap.replace("__SOURCE_BUNDLE__", repr(canonical(source_files))).replace("__SOURCE_BINDING__", repr(binding))


def build(repo, output_dir):
    repo, output_dir = Path(repo).resolve(), Path(output_dir).resolve()
    files, payload = {}, {}
    paths = list(SOURCE_PATHS)
    manifest = json.loads((repo / MANIFEST).read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "phase8_batch_v1" or len(manifest.get("videos", [])) != 8:
        raise ValueError("Phase8 preparation requires the explicit eight-slot batch manifest")
    # Preserve the small explicit user authorization referenced by the manifest.
    # Sampling PNGs/proposals and source MP4s are intentionally external inputs.
    authorization = manifest.get("input_authorization_path")
    if authorization is not None:
        if Path(authorization).suffix != ".json":
            raise ValueError("Only a small JSON authorization record may supplement the minimal sources")
        paths.append(authorization)
    for relative in paths:
        path = _safe_relative(relative)
        source = (repo / path).resolve()
        if not source.is_relative_to(repo) or not source.is_file():
            raise ValueError("Required repository source unavailable: " + relative)
        data = source.read_bytes()
        if source.suffix == ".py":
            ast.parse(data.decode("utf-8"), filename=relative)
        files[relative] = {"sha256": sha256(data), "bytes": len(data)}
        payload[relative] = {**files[relative], "gzip_base64": base64.b64encode(gzip.compress(data, mtime=0)).decode("ascii")}
    if authorization is not None and files[authorization]["sha256"] != manifest.get("input_authorization_sha256"):
        raise ValueError("Manifest user authorization SHA mismatch")
    profile = json.loads((repo / PROFILE).read_text(encoding="utf-8"))
    for relative, expected in profile.get("source_bindings", {}).items():
        if relative not in files or files[relative]["sha256"] != expected:
            raise ValueError("Frozen processing-profile source missing or changed: " + relative)
    binding = sha256(canonical(files).encode())
    source_notebook = json.loads((repo / NOTEBOOK).read_text(encoding="utf-8"))
    if source_notebook.get("nbformat") != 4:
        raise ValueError("Only a canonical nbformat4 notebook can be packaged")
    notebook = json.loads(json.dumps(source_notebook))
    code_cells = 0
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            ast.parse(_notebook_source(cell))
            code_cells += 1
            cell["execution_count"], cell["outputs"] = None, []
    if code_cells < 1:
        raise ValueError("Canonical notebook contains no code cells")
    bootstrap = make_bootstrap(payload, binding)
    ast.parse(bootstrap)
    notebook["cells"] = [{"cell_type": "markdown", "id": "phase8-bundle-note", "metadata": {}, "source": [
        "# Phase 8 TGDI — source-bound preparation bundle\n",
        "The following bootstrap preserves the canonical repository notebook and selects `prepare`.\n",
        "It discovers the actual TGDI inputs, runs synthetic software guards, and retains readiness evidence.\n",
        "It does not run detector/tracker/encoder inference or counting on the actual videos.\n",
    ]}, {"cell_type": "code", "id": "phase8-bundle-bootstrap", "metadata": {}, "execution_count": None,
         "outputs": [], "source": bootstrap.splitlines(keepends=True)}] + notebook["cells"]
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "phase8_tgdi_prepare.ipynb"
    metadata_path = output_dir / "kernel-metadata.json"
    notebook_bytes = (json.dumps(notebook, indent=1, ensure_ascii=False) + "\n").encode()
    metadata = {"id": KERNEL_ID, "title": "Phase 8 TGDI batch preparation", "code_file": destination.name,
        "language": "python", "kernel_type": "notebook", "is_private": True,
        "enable_gpu": True, "enable_tpu": False, "enable_internet": True,
        "dataset_sources": [DATASET], "kernel_sources": [], "competition_sources": [], "model_sources": [], "keywords": []}
    destination.write_bytes(notebook_bytes)
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    report = {"claim_type": "SOURCE_PACKAGING_NOT_EXECUTION", "mode": "prepare",
        "source_bundle_binding_sha256": binding, "source_file_count": len(files), "source_files": files,
        "canonical_notebook_path": NOTEBOOK, "canonical_notebook_sha256": files[NOTEBOOK]["sha256"],
        "canonical_notebook_code_cells": code_cells, "canonical_code_cells_modified": False,
        "submitted_notebook": {"path": str(destination), "sha256": sha256(notebook_bytes), "bytes": len(notebook_bytes)},
        "kernel_metadata": {"path": str(metadata_path), "sha256": sha256(metadata_path.read_bytes())},
        "builder": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).read_bytes())},
        "videos_bundled": False, "model_weights_bundled": False, "actual_model_inference_executed": False,
        "upload_performed": False, "submission_folder": str(output_dir)}
    (output_dir / "source_bundle_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output-dir", required=True)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.repo, arguments.output_dir), indent=2, sort_keys=True))
