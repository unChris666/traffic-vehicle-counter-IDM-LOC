#!/usr/bin/env python3
"""Read-only verification of the actual B v3 Kaggle packet; never executes cells."""
from __future__ import annotations

import argparse
import ast
import base64
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("b_v3_builder_verification", HERE / "build_kaggle_bundle.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def verify(repo_root, packet_dir):
    repo, packet = Path(repo_root).resolve(), Path(packet_dir).resolve()
    checks = []

    def require(condition, name):
        if not condition:
            raise ValueError("Submitted packet verification failed: " + name)
        checks.append(name)

    names = {"kernel-metadata.json", "source_bundle_manifest.json", "phase8_tgdi_b_v3_review.ipynb"}
    require(packet.is_dir() and {path.name for path in packet.iterdir()} == names,
            "submission directory contains exactly three expected files")
    require(all(path.is_file() and not path.is_symlink() for path in packet.iterdir()), "submission files are regular")
    report = json.loads((packet / "source_bundle_manifest.json").read_text())
    meta_bytes = (packet / "kernel-metadata.json").read_bytes()
    metadata = json.loads(meta_bytes)
    notebook_path = packet / "phase8_tgdi_b_v3_review.ipynb"
    notebook_bytes = notebook_path.read_bytes()
    notebook = json.loads(notebook_bytes)
    require(builder.sha(notebook_bytes) == report["submitted_notebook"]["sha256"], "submitted notebook SHA")
    require(len(notebook_bytes) == report["submitted_notebook"]["bytes"], "submitted notebook byte length")
    require(builder.sha(meta_bytes) == report["kernel_metadata"]["sha256"], "kernel metadata SHA")
    require(metadata["id"] == builder.KERNEL_ID and metadata["code_file"] == notebook_path.name, "dedicated kernel identity")
    require(metadata["is_private"] is True and metadata["enable_gpu"] is False
            and metadata["enable_tpu"] is False and metadata["enable_internet"] is False, "private CPU offline execution")
    require(metadata["dataset_sources"] == [builder.RAW_DATASET]
            and metadata["kernel_sources"] == [builder.PARENT_KERNEL]
            and not metadata["competition_sources"] and not metadata["model_sources"], "original read-only input mounts")
    require(report["original_parent_kernel_version"] == 2
            and report["original_batch_manifest_sha256"] == builder.DONOR_MANIFEST_SHA256, "original donor identity")
    require(builder.sha(Path(builder.__file__).read_bytes()) == report["builder"]["sha256"], "builder source SHA")
    require(len(notebook["cells"]) >= 3 and notebook["cells"][0]["cell_type"] == "markdown"
            and notebook["cells"][1]["cell_type"] == "code", "bootstrap cell position")
    bootstrap = builder.cell_source(notebook["cells"][1])
    tree = ast.parse(bootstrap)
    assignments = {node.targets[0].id: node.value for node in tree.body
                   if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}
    payload_node = assignments["B_V3_SOURCE_BUNDLE"]
    require(isinstance(payload_node, ast.Call) and isinstance(payload_node.func, ast.Attribute)
            and isinstance(payload_node.func.value, ast.Name) and payload_node.func.value.id == "json"
            and payload_node.func.attr == "loads" and len(payload_node.args) == 1, "literal JSON source payload")
    payload = json.loads(ast.literal_eval(payload_node.args[0]))
    binding = ast.literal_eval(assignments["B_V3_SOURCE_BINDING_SHA256"])
    manifest = {name: {key: item[key] for key in ("sha256", "bytes")} for name, item in payload.items()}
    require(manifest == report["source_files"], "embedded source manifest equals retained packet report")
    require(builder.sha(builder.canonical(manifest).encode()) == binding
            == report["source_bundle_binding_sha256"], "source bundle binding")
    require(bootstrap == builder.bootstrap_cell(payload, binding), "bootstrap exact allowlisted extraction code")
    required = set(builder.PYTHON_SOURCES) | {builder.NOTEBOOK, builder.NEW_GEOMETRY_MANIFEST,
        builder.POLICY, builder.USER_DECISIONS, builder.REVISION_POLICY, builder.REVIEW_DECISIONS}
    geometry = json.loads(builder.read_source(repo, builder.NEW_GEOMETRY_MANIFEST))
    old_geometry = json.loads(builder.read_source(repo, builder.OLD_GEOMETRY_MANIFEST))
    required.add(geometry["template_path"])
    review_decisions = json.loads(builder.read_source(repo, builder.REVIEW_DECISIONS))
    evidence_paths = builder.review_evidence_paths(repo, review_decisions)
    required.update(evidence_paths)
    baseline_path = builder.baseline_reference_path(repo, review_decisions)
    required.add(baseline_path)
    require(report["baseline_reference_path"] == baseline_path
            and report["baseline_reference_sha256"] == report["source_files"][baseline_path]["sha256"],
            "compact B v2 baseline reference binding")
    require(report["review_evidence_json_paths"] == evidence_paths
            and report["review_evidence_json_count"] == len(evidence_paths)
            and report["review_png_pixels_bundled"] is False, "explicit review JSON proof bindings without PNG packaging")
    for config in (geometry, old_geometry):
        for item in builder._video_map(config).values():
            required.add(item["geometry_path"])
    require(set(payload) == required, "exact allowlisted source/configuration set")
    for name, item in sorted(payload.items()):
        data = gzip.decompress(base64.b64decode(item["gzip_base64"], validate=True))
        require(len(data) == item["bytes"] and builder.sha(data) == item["sha256"]
                and data == builder.read_source(repo, name), "exact embedded bytes: " + name)
        if Path(name).suffix == ".py":
            builder.check_python(data.decode(), name)
    canonical = json.loads(builder.read_source(repo, builder.NOTEBOOK))
    require(notebook["cells"][2:] == canonical["cells"], "canonical notebook cells unchanged")
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            require(cell.get("execution_count") is None and not cell.get("outputs"), "no fabricated cell execution/output")
            builder.check_python(builder.cell_source(cell), builder.NOTEBOOK)
    require(sum(path.stat().st_size for path in packet.iterdir()) < builder.MAX_PACKET_BYTES, "entire packet below size bound")
    require(report["review_decisions_sha256"] == manifest[builder.REVIEW_DECISIONS]["sha256"]
            and report["revision_policy_sha256"] == manifest[builder.REVISION_POLICY]["sha256"], "review and revision-policy bindings")
    return {"claim_type": "ACTUAL_SUBMITTED_SOURCE_PACKET_VERIFICATION_NOT_VIDEO_EXECUTION",
            "status": "PASS", "check_count": len(checks), "checks": checks,
            "source_bundle_binding_sha256": binding, "source_file_count": len(manifest),
            "submitted_notebook_sha256": builder.sha(notebook_bytes), "submitted_notebook_bytes": len(notebook_bytes),
            "kernel_metadata_sha256": builder.sha(meta_bytes), "execution_cells_run": False,
            "new_detector_tracker_reid_or_counting_execution": False, "remote_submission_performed": False,
            "verifier_sha256": builder.sha(Path(__file__).read_bytes())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--packet-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.repo_root, args.packet_dir), indent=2, sort_keys=True))
