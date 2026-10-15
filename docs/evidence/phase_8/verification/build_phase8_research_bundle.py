#!/usr/bin/env python3
"""Package the approved eight-video research run; never upload or run models.

The immutable PREPARE-v1 builder supplies extraction safety. This new wrapper
explicitly selects run_batch/v2 and carries the native geometry review evidence.
Unknown business facts remain null; this is not a final product result.
"""
from __future__ import annotations

import argparse
import ast
import base64
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

BASE_BUILDER = "docs/evidence/phase_8/verification/build_phase8_kaggle_bundle.py"
BASE_SHA256 = "157a03bbbab8f5aa1adddc654db6c08d604100db275186caaf0f60db897aac31"
MANIFEST = "docs/evidence/phase_8/config/batch_manifest_TGDI_G3_T1_v2.json"
KERNEL_ID = "chrisbiran/phase-8-tgdi-full-video-research"
OUTPUT_ROOT = "/kaggle/working/phase_8_tgdi_research"


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _base(repo):
    path = repo / BASE_BUILDER
    if _sha(path.read_bytes()) != BASE_SHA256:
        raise ValueError("Immutable PREPARE-v1 builder differs from retained source")
    spec = importlib.util.spec_from_file_location("phase8_immutable_v1_bundle_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(repo, output_dir, *, external_frame_dataset=None, external_frame_manifest=None, external_frame_root=None):
    repo, output_dir = Path(repo).resolve(), Path(output_dir).resolve()
    base = _base(repo)
    manifest = json.loads((repo / MANIFEST).read_text())
    if (manifest.get("schema_version") != "phase8_batch_v1" or len(manifest.get("videos", [])) != 8
            or manifest.get("execution_purpose") != "RESEARCH_WITH_DECLARED_UNKNOWN_LOCATION"):
        raise ValueError("Expected the explicitly approved TGDI research manifest")
    files, payload, excluded, native_frames = {}, {}, [], {}

    def add(relative, expected=None):
        path = base._safe_relative(relative)
        if path.suffix not in {".py", ".json", ".ipynb", ".png"}:
            raise ValueError("Source/media type is not an allowed minimal research dependency")
        absolute = (repo / path).resolve()
        if not absolute.is_relative_to(repo) or not absolute.is_file():
            raise ValueError("Research dependency unavailable: " + relative)
        data = absolute.read_bytes()
        if expected is not None and _sha(data) != expected:
            raise ValueError("Research dependency SHA mismatch: " + relative)
        if path.suffix == ".py":
            ast.parse(data.decode(), filename=relative)
        files[relative] = {"sha256": _sha(data), "bytes": len(data)}
        payload[relative] = {**files[relative], "gzip_base64": base64.b64encode(gzip.compress(data, mtime=0)).decode("ascii")}
        return json.loads(data) if path.suffix == ".json" else None

    def reference(ref):
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not isinstance(ref.get("sha256"), str):
            raise ValueError("Explicit path/SHA research evidence reference required")
        return add(ref["path"], ref["sha256"])

    for path in base.SOURCE_PATHS:
        add(MANIFEST if path == base.MANIFEST else path)
    add(manifest["input_authorization_path"], manifest["input_authorization_sha256"])
    for key in ("location_metadata_review", "source_user_confirmation", "supersedes_input_configuration"):
        data = reference(manifest[key])
        if isinstance(data, dict) and "source_user_confirmation" in data:
            reference(data["source_user_confirmation"])
    for video in manifest["videos"]:
        geometry = add(video["geometry_path"], video["geometry_sha256"])
        if geometry.get("geometry_contract_accepted") is not True or geometry.get("counting_execution_allowed") is not True:
            raise ValueError("Per-video geometry is not accepted for this research run")
        reference(geometry["source_frame"])
        native_frames[geometry["source_frame"]["path"]] = geometry["source_video"]["sha256"]
        feedback = reference(geometry["approval_feedback"])
        for ref in feedback["evidence_frames"]:
            reference(ref)
        for document in (geometry, feedback):
            for key in ("source_proposal", "source_user_confirmation", "template_source"):
                if key in document:
                    reference(document[key])
        reference(video["source_inspection"])
        reference(video["geometry_proposal"])
        if "preview" in geometry:
            excluded.append({**geometry["preview"], "reason": "Optional overlay audit preview; native review PNG is bundled"})
    profile = json.loads((repo / base.PROFILE).read_text())
    for relative, expected in profile["source_bindings"].items():
        if files.get(relative, {}).get("sha256") != expected:
            raise ValueError("Frozen scientific control source changed: " + relative)
    binding = _sha(base.canonical(files).encode())
    if external_frame_dataset is None or external_frame_manifest is None:
        raise ValueError("Native PNG evidence must use the explicit private dataset transport to fit Kaggle's kernel-size limit")
    asset_manifest_path = Path(external_frame_manifest).resolve()
    asset_manifest_bytes = asset_manifest_path.read_bytes()
    assets = json.loads(asset_manifest_bytes)
    if (assets.get("schema_version") != "phase8_native_geometry_frames_v1"
            or assets.get("dataset_ref") != external_frame_dataset
            or assets.get("source_manifest_sha256") != files[MANIFEST]["sha256"]):
        raise ValueError("External native-frame dataset manifest has a different source scope")
    rows = assets.get("files", [])
    if len(rows) != 8 or {row.get("repository_path") for row in rows} != set(native_frames):
        raise ValueError("External native-frame dataset must bind exactly the eight accepted native PNGs")
    for row in rows:
        relative = row["repository_path"]
        asset_path = base._safe_relative(row["relative_asset_path"])
        actual = (asset_manifest_path.parent / asset_path).resolve()
        if (not actual.is_relative_to(asset_manifest_path.parent) or row.get("source_video_sha256") != native_frames[relative]
                or row.get("sha256") != files[relative]["sha256"] or row.get("size_bytes") != files[relative]["bytes"]
                or _sha(actual.read_bytes()) != row["sha256"]):
            raise ValueError("External native PNG bytes/source identity differ: " + relative)
        payload[relative].pop("gzip_base64")
        payload[relative]["external_native_png"] = row
    owner, slug = external_frame_dataset.split("/", 1)
    candidates = [external_frame_root] if external_frame_root else ["/kaggle/input/datasets/" + owner + "/" + slug, "/kaggle/input/" + slug]
    transport = {"kind": "BYTE_IDENTICAL_NATIVE_PNG_PRIVATE_DATASET", "dataset_ref": external_frame_dataset,
        "manifest_filename": asset_manifest_path.name, "manifest_sha256": _sha(asset_manifest_bytes),
        "source_manifest_sha256": files[MANIFEST]["sha256"], "dataset_root_candidates": candidates,
        "external_frame_count": 8, "native_png_bytes_changed": False}
    bootstrap = base.make_bootstrap(payload, binding)
    external_bootstrap = '''
_FRAME_TRANSPORT = json.loads(__FRAME_TRANSPORT__)
_expected_external = {relative: entry['external_native_png'] for relative, entry in SOURCE_BUNDLE.items()
                      if 'external_native_png' in entry}
_roots = [Path(globals()['PHASE8_FRAME_DATASET_ROOT'])] if 'PHASE8_FRAME_DATASET_ROOT' in globals() else [Path(p) for p in _FRAME_TRANSPORT['dataset_root_candidates']]
_verified_roots = set()
for _root in _roots:
    _manifest = _root / _FRAME_TRANSPORT['manifest_filename']
    if _manifest.is_file() and hashlib.sha256(_manifest.read_bytes()).hexdigest() == _FRAME_TRANSPORT['manifest_sha256']:
        _verified_roots.add(_root.resolve())
if len(_verified_roots) != 1:
    raise ValueError('Expected one mounted native-frame evidence dataset with the exact bound manifest SHA.')
FRAME_EVIDENCE_ROOT = _verified_roots.pop()
_assets = json.loads((FRAME_EVIDENCE_ROOT / _FRAME_TRANSPORT['manifest_filename']).read_text())
if (_assets.get('schema_version') != 'phase8_native_geometry_frames_v1'
        or _assets.get('dataset_ref') != _FRAME_TRANSPORT['dataset_ref']
        or _assets.get('source_manifest_sha256') != _FRAME_TRANSPORT['source_manifest_sha256']):
    raise ValueError('Native-frame evidence dataset has a different research source scope.')
_rows = _assets.get('files', [])
if len(_rows) != 8 or {row.get('repository_path') for row in _rows} != set(_expected_external):
    raise ValueError('Native-frame evidence dataset does not bind exactly the accepted eight PNGs.')
for _row in _rows:
    _relative = _row['repository_path']
    if _row != _expected_external[_relative]:
        raise ValueError('Native frame source identity/SHA mapping differs from the approved bundle.')
    _asset = Path(_row['relative_asset_path'])
    if _asset.is_absolute() or '..' in _asset.parts or chr(92) in _row['relative_asset_path']:
        raise ValueError('Unsafe native-frame evidence asset path.')
    _path = (FRAME_EVIDENCE_ROOT / _asset).resolve()
    if not _path.is_relative_to(FRAME_EVIDENCE_ROOT):
        raise ValueError('Native-frame evidence asset escaped its dataset.')
    _raw = _path.read_bytes()
    if len(_raw) != _row['size_bytes'] or hashlib.sha256(_raw).hexdigest() != _row['sha256']:
        raise ValueError('Native-frame evidence PNG differs from the accepted original bytes.')
    SOURCE_BUNDLE[_relative]['gzip_base64'] = base64.b64encode(gzip.compress(_raw, mtime=0)).decode('ascii')
print('Verified byte-identical native PNG dataset:', FRAME_EVIDENCE_ROOT)
'''.replace("__FRAME_TRANSPORT__", repr(base.canonical(transport)))
    bootstrap = bootstrap.replace("SOURCE_BUNDLE_BINDING_SHA256 =", external_bootstrap + "\nSOURCE_BUNDLE_BINDING_SHA256 =", 1)
    substitutions = {
        "'source_files':_source_manifest, 'mode':'prepare'": "'source_files':_source_manifest, 'mode':'run_batch'",
        "MODE = 'prepare'": "MODE = 'run_batch'",
        "print('Mode:', MODE, '(input preparation and software guards; no model execution)')":
            "print('Mode:', MODE, '(approved full-video TGDI research; sequential CUDA0; business metadata incomplete)')",
    }
    for old, new in substitutions.items():
        if bootstrap.count(old) != 1:
            raise ValueError("PREPARE bootstrap wrapper shape changed")
        bootstrap = bootstrap.replace(old, new, 1)
    bootstrap += ("\n_provenance['external_native_frame_transport'] = _FRAME_TRANSPORT"
                  + "\n_provenance['external_frame_dataset_root'] = str(FRAME_EVIDENCE_ROOT)"
                  + "\n(REPO_ROOT / 'source_bundle_provenance.json').write_text(json.dumps(_provenance, indent=2, sort_keys=True) + '\\n')"
                  + "\nMANIFEST_PATH = REPO_ROOT / " + repr(MANIFEST)
                  + "\nPROFILE_PATH = REPO_ROOT / " + repr(base.PROFILE)
                  + "\nOUTPUT_ROOT = Path(" + repr(OUTPUT_ROOT) + ")"
                  + "\nprint('Research manifest:', MANIFEST_PATH)"
                  + "\nprint('Output:', OUTPUT_ROOT)\n")
    ast.parse(bootstrap)
    notebook = json.loads((repo / base.NOTEBOOK).read_text())
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            ast.parse(base._notebook_source(cell))
            cell["execution_count"], cell["outputs"] = None, []
    notebook["cells"] = [{"cell_type": "markdown", "id": "phase8-research-bundle-note", "metadata": {}, "source": [
        "# Phase 8 TGDI — approved full-video research run\n",
        "This source-bound wrapper selects `run_batch` with all eight user-approved geometries/directions.\n",
        "Raw detector/tracker/ReID/counting controls are unchanged; videos run sequentially on CUDA0.\n",
        "Store name, latitude and longitude remain explicitly unknown/null under the retained research acknowledgement.\n",
        "Outputs are accepted passage subtotals with pending/coverage limits, not complete production results or accuracy.\n",
    ]}, {"cell_type": "code", "id": "phase8-research-source-bootstrap", "metadata": {}, "execution_count": None,
         "outputs": [], "source": bootstrap.splitlines(keepends=True)}] + notebook["cells"]
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "phase8_tgdi_research.ipynb"
    path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n")
    metadata = {"id": KERNEL_ID, "title": "Phase 8 TGDI full-video research", "code_file": path.name,
        "language": "python", "kernel_type": "notebook", "is_private": True, "enable_gpu": True,
        "enable_tpu": False, "enable_internet": True, "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": [base.DATASET, external_frame_dataset], "kernel_sources": [], "competition_sources": [], "model_sources": [], "keywords": []}
    metadata_path = output_dir / "kernel-metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    if path.stat().st_size >= 1_000_000:
        raise ValueError("Submitted kernel source must be less than 1,000,000 bytes")
    report = {"claim_type": "SOURCE_PACKAGING_NOT_MODEL_EXECUTION", "mode": "run_batch", "research_only": True,
        "business_metadata_complete": False, "source_bundle_binding_sha256": binding, "source_file_count": len(files), "source_files": files,
        "canonical_notebook_path": base.NOTEBOOK, "canonical_notebook_sha256": files[base.NOTEBOOK]["sha256"],
        "canonical_code_cells_modified": False, "bootstrap_parameter_overrides": {"MODE": "run_batch", "MANIFEST_PATH": MANIFEST, "OUTPUT_ROOT": OUTPUT_ROOT},
        "base_builder_sha256": BASE_SHA256, "builder_sha256": _sha(Path(__file__).read_bytes()),
        "external_native_frame_transport": transport, "embedded_source_file_count": len(files) - 8,
        "source_bundle_transport_binding_sha256": _sha(base.canonical({"logical_source_files": files, "transport": transport}).encode()),
        "submitted_notebook": {"path": str(path), "sha256": _sha(path.read_bytes()), "bytes": path.stat().st_size},
        "kernel_metadata": {"path": str(metadata_path), "sha256": _sha(metadata_path.read_bytes())},
        "external_optional_audit_previews": excluded, "videos_bundled": False, "model_weights_bundled": False,
        "actual_model_inference_executed": False, "upload_performed": False, "submission_folder": str(output_dir)}
    (output_dir / "source_bundle_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--external-frame-dataset", required=True)
    parser.add_argument("--external-frame-manifest", required=True)
    parser.add_argument("--external-frame-root")
    args = parser.parse_args()
    print(json.dumps(build(args.repo, args.output_dir, external_frame_dataset=args.external_frame_dataset,
        external_frame_manifest=args.external_frame_manifest, external_frame_root=args.external_frame_root), indent=2, sort_keys=True))
