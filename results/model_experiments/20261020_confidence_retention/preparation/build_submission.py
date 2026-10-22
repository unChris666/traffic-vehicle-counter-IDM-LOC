"""Build a private Kaggle submission only after an actual retained P0 gate."""
import base64
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path("/tmp/phase9-confidence-kaggle")
PACKET = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.splitlines(keepends=True)}


def main():
    names = ["notebooks/phase_9_model_experiment.py", "notebooks/phase_7_night_helpers.py",
             "notebooks/phase_7_temporal_helpers.py", "notebooks/09b_model_configuration_experiment.ipynb",
             "docs/evidence/phase_8/config/processing_profile_v1.json",
             "results/b_v5/verification/p0_execution_gate.json"]
    gate = json.loads((ROOT / names[-1]).read_text())
    assert gate["status"] == "PASS", "Actual P0 gate required"
    bundle = {}
    for name in names:
        data = (ROOT / name).read_bytes()
        bundle[name] = {"sha256": sha(data), "bytes": len(data),
                        "gzip_base64": base64.b64encode(gzip.compress(data, mtime=0)).decode()}
    bootstrap = '''from pathlib import Path
import base64, gzip, hashlib, json, sys, subprocess
SOURCE_BUNDLE = json.loads(BUNDLE_JSON)
REPO_ROOT = Path("/kaggle/working/traffic_project")
for relative, receipt in SOURCE_BUNDLE.items():
    data = gzip.decompress(base64.b64decode(receipt["gzip_base64"]))
    assert len(data) == receipt["bytes"] and hashlib.sha256(data).hexdigest() == receipt["sha256"]
    target = REPO_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
print("Source bundle verified:", len(SOURCE_BUNDLE), "files; P0 evidence retained")
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "ultralytics==8.4.175", "onnx==1.20.1", "onnxruntime-gpu==1.24.4", "lap==0.5.13"], check=True)
import torch
assert torch.cuda.is_available(), "CUDA required; no CPU fallback"
import onnxruntime as ort
ort.preload_dlls()
expected = "5ffeec3d74e51eed43f45050c44fc019c989a8f2d5659c0bf6ccf3370284f4d1"
found = sorted(Path("/kaggle/input").rglob("TGDI-WEEKDAY-SIANG.mp4"))
matched = [p for p in found if hashlib.sha256(p.read_bytes()).hexdigest() == expected]
assert len(matched) == 1, "Need one discovered source matching the retained video SHA"
VIDEO_PATH = matched[0]
print("Verified source:", VIDEO_PATH, "CUDA:", torch.cuda.get_device_name(0))
'''.replace("BUNDLE_JSON", repr(json.dumps(bundle, separators=(",", ":"))))
    canonical = json.loads((ROOT / names[3]).read_text())
    notebook = deepcopy(canonical)
    notebook["cells"] = [code(bootstrap)] + notebook["cells"]
    changed = 0
    for cell in notebook["cells"][1:]:
        for i, line in enumerate(cell["source"]):
            if line == "RUN_EXPERIMENT = False\n":
                cell["source"][i] = "RUN_EXPERIMENT = True\n"
                changed += 1
    assert changed == 1
    OUT.mkdir(exist_ok=True)
    name = "phase9_confidence_retention.ipynb"
    (OUT / name).write_text(json.dumps(notebook, indent=1) + "\n")
    metadata = {"id": "chrisbiran/phase-9-tgdi-confidence-retention-after-p0",
                "title": "Phase 9 TGDI confidence retention after P0",
                "code_file": name, "language": "python", "kernel_type": "notebook",
                "is_private": True, "enable_gpu": True, "enable_tpu": False,
                "enable_internet": True, "dataset_sources": ["chrisbiran/tgdi-traffic-videos"],
                "kernel_sources": [], "competition_sources": [], "model_sources": []}
    (OUT / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    manifest = {"status": "PREPARED_NOT_SUBMITTED", "source_files": [
        {"path": name, "sha256": item["sha256"], "bytes": item["bytes"]} for name, item in bundle.items()],
        "bootstrap_adjustment": "Only RUN_EXPERIMENT False→True; canonical notebook and old kernels unchanged",
        "models_or_videos_bundled": False, "private_kernel": metadata["id"],
        "files": [{"path": p.name, "sha256": sha(p.read_bytes()), "bytes": p.stat().st_size}
                  for p in sorted(OUT.iterdir()) if p.is_file()]}
    (PACKET / "source_bundle_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (PACKET / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (PACKET / "submitted_notebook.ipynb.gz").write_bytes(gzip.compress((OUT / name).read_bytes(), mtime=0))
    print(json.dumps({"output": str(OUT), "source_files": len(bundle), "private_kernel": metadata["id"]}))


if __name__ == "__main__":
    main()
