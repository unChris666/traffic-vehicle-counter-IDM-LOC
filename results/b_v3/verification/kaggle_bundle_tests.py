"""Offline packet guards using explicitly synthetic repositories, never video evidence."""
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("b_v3_bundle", HERE / "build_kaggle_bundle.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
VERIFY_SPEC = importlib.util.spec_from_file_location("b_v3_packet_verifier", HERE / "verify_submitted_packet.py")
verifier = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(verifier)


def store(root, name, data):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def js(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def fixture(root):
    for name in builder.PYTHON_SOURCES:
        store(root, name, b"# Synthetic software fixture; not executed video evidence.\n")
    notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": [
        {"cell_type": "code", "id": "fixture", "metadata": {}, "execution_count": None,
         "outputs": [], "source": ["# Synthetic replay placeholder; not actual execution.\n", "fixture_value = 7\n"]}]}
    store(root, builder.NOTEBOOK, js(notebook))
    template_path = "results/b_v2/input/synthetic-geometry-review.json"
    template = b'{"claim_type":"SYNTHETIC_TEST_GEOMETRY"}\n'
    store(root, template_path, template)
    new, old = [], []
    for i, video_id in enumerate(sorted(builder.EXPECTED_VIDEO_IDS)):
        source_sha = hashlib.sha256(video_id.encode()).hexdigest()
        new_path = f"results/b_v2/geometry/{video_id}.json"
        old_path = f"docs/evidence/phase_8/geometry/{video_id}.json"
        new_bytes, old_bytes = js({"synthetic": video_id, "version": 2}), js({"synthetic": video_id, "version": 1})
        store(root, new_path, new_bytes)
        store(root, old_path, old_bytes)
        new.append({"video_id": video_id, "geometry_path": new_path,
                    "geometry_sha256": builder.sha(new_bytes), "video_sha256": source_sha})
        old.append({"video_id": video_id, "geometry_path": old_path,
                    "geometry_sha256": builder.sha(old_bytes), "source_sha256": source_sha})
    store(root, builder.NEW_GEOMETRY_MANIFEST, js({"videos": new, "template_path": template_path,
                                                "template_sha256": builder.sha(template)}))
    store(root, builder.OLD_GEOMETRY_MANIFEST, js({"videos": old}))
    for name in (builder.POLICY, builder.USER_DECISIONS):
        store(root, name, js({"source_template_sha256": builder.sha(template)}))
    for name in (builder.REVISION_POLICY, builder.REVIEW_DECISIONS):
        store(root, name, js({"claim_type": "SYNTHETIC_SOFTWARE_FIXTURE"}))
    baseline_bytes = js({"claim_type": "SYNTHETIC_RETAINED_BASELINE_FIXTURE", "frames_processed": 72590,
        "operational_total": 3717, "per_video": []})
    store(root, builder.BASELINE_SUMMARY, baseline_bytes)
    store(root, builder.REVIEW_DECISIONS, js({"claim_type": "SYNTHETIC_SOFTWARE_FIXTURE",
        "b_v2_baseline_reference": {"path": builder.BASELINE_SUMMARY, "sha256": builder.sha(baseline_bytes)}}))
    return notebook


class PacketGuards(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.notebook = fixture(self.root)
        self.output = self.base / "packet"

    def tearDown(self):
        self.temporary.cleanup()

    def build(self):
        return builder.build(self.root, self.output)

    def mutate_json(self, name, action):
        target = self.root / name
        value = json.loads(target.read_text())
        action(value)
        target.write_bytes(js(value))

    def test_packet_is_private_cpu_offline_with_original_inputs(self):
        report = self.build()
        metadata = json.loads((self.output / "kernel-metadata.json").read_text())
        self.assertTrue(metadata["is_private"])
        self.assertFalse(metadata["enable_gpu"])
        self.assertFalse(metadata["enable_tpu"])
        self.assertFalse(metadata["enable_internet"])
        self.assertEqual(metadata["kernel_sources"], ["chrisbiran/phase-8-tgdi-full-video-research"])
        self.assertEqual(metadata["dataset_sources"], ["chrisbiran/tgdi-traffic-videos"])
        self.assertEqual(metadata["id"], "chrisbiran/phase-8-tgdi-b-v3-review")
        self.assertFalse(report["new_model_execution"])
        self.assertFalse(report["new_counting_execution"])
        self.assertFalse(report["upload_performed"])
        self.assertEqual(report["review_decisions_sha256"], builder.sha((self.root / builder.REVIEW_DECISIONS).read_bytes()))

    def test_canonical_notebook_code_unchanged_and_no_outputs_added(self):
        self.build()
        actual = json.loads((self.output / "phase8_tgdi_b_v3_review.ipynb").read_text())
        self.assertEqual(actual["cells"][2:], self.notebook["cells"])
        self.assertTrue(all(cell.get("execution_count") is None and not cell.get("outputs")
                            for cell in actual["cells"] if cell["cell_type"] == "code"))

    def test_bootstrap_extracts_hash_exact_sources_without_running_them(self):
        store(self.root, builder.PYTHON_SOURCES[0], b"raise RuntimeError('Do not execute bundled source')\n")
        report = self.build()
        notebook = json.loads((self.output / "phase8_tgdi_b_v3_review.ipynb").read_text())
        namespace = {"PHASE8_B_V3_SOURCE_PARENT": str(self.base / "extracted")}
        with patch("sys.path", list(__import__("sys").path)), patch("builtins.print"):
            exec(builder.cell_source(notebook["cells"][1]), namespace)
        for name, record in report["source_files"].items():
            actual = (namespace["REPO_ROOT"] / name).read_bytes()
            self.assertEqual(builder.sha(actual), record["sha256"])
            self.assertEqual(actual, (self.root / name).read_bytes())
        proof = json.loads((namespace["REPO_ROOT"] / "b_v3_source_provenance.json").read_text())
        self.assertFalse(proof["new_b_v3_counting_executed_by_bootstrap"])
        self.assertFalse(proof["new_detector_tracker_reid_inference"])

    def test_actual_canonical_parameters_preserve_injected_verified_snapshot(self):
        canonical = json.loads((HERE.parents[2] / builder.NOTEBOOK).read_text())
        cell = next(cell for cell in canonical["cells"] if cell.get("id") == "bv3-01")
        snapshot = self.base / "verified-snapshot"
        store(snapshot, "results/b_v3/input/review_decisions.json", b"{}\n")
        namespace = {"REPO_ROOT": snapshot}
        with patch("sys.path", list(__import__("sys").path)):
            exec(builder.cell_source(cell), namespace)
        self.assertEqual(namespace["REPO_ROOT"], snapshot)
        self.assertTrue((namespace["REPO_ROOT"] / "results/b_v3/input/review_decisions.json").is_file())

    def test_bootstrap_rejects_changed_payload_before_extraction(self):
        self.build()
        notebook = json.loads((self.output / "phase8_tgdi_b_v3_review.ipynb").read_text())
        source = builder.cell_source(notebook["cells"][1])
        source = source.replace("B_V3_SOURCE_BINDING_SHA256 = '", "B_V3_SOURCE_BINDING_SHA256 = 'f", 1)
        with self.assertRaisesRegex(ValueError, "manifest changed"):
            exec(source, {"PHASE8_B_V3_SOURCE_PARENT": str(self.base / "extract")})
        self.assertFalse((self.base / "extract").exists())

    def test_missing_required_source_rejected(self):
        (self.root / builder.PYTHON_SOURCES[0]).unlink()
        with self.assertRaisesRegex(ValueError, "source missing"):
            self.build()

    def test_source_symlink_rejected(self):
        target = self.root / builder.PYTHON_SOURCES[0]
        target.unlink()
        external = self.base / "external.py"
        external.write_text("# external source\n")
        target.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "source missing or outside"):
            self.build()

    def test_unsafe_path_rejected(self):
        for name in ("../source.py", "/source.py", "a/../source.py", "a\\source.py", "./source.py"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                builder.safe_relative(name)

    def test_model_import_in_source_rejected(self):
        for source in ("import ultralytics", "from torch import cuda", "__import__('onnxruntime')",
                       "importlib.import_module('torch')"):
            with self.subTest(source=source):
                store(self.root, builder.PYTHON_SOURCES[0], source.encode())
                with self.assertRaisesRegex(ValueError, "model/network runtimes"):
                    self.build()

    def test_network_import_in_notebook_rejected(self):
        self.mutate_json(builder.NOTEBOOK, lambda value: value["cells"][0].update(source=["import requests\n"]))
        with self.assertRaisesRegex(ValueError, "model/network runtimes"):
            self.build()

    def test_credential_or_signed_capability_rejected(self):
        for secret in ("github_pat_" + "x" * 30, "KGAT_" + "x" * 30,
                       "https://example.invalid/file?X-Goog-Signature=fixture"):
            with self.subTest(kind=secret[:11]):
                store(self.root, builder.PYTHON_SOURCES[0], ("# " + secret).encode())
                with self.assertRaisesRegex(ValueError, "Credential or signed capability"):
                    self.build()

    def test_geometry_bytes_changed_rejected(self):
        row = json.loads((self.root / builder.NEW_GEOMETRY_MANIFEST).read_text())["videos"][0]
        store(self.root, row["geometry_path"], b"{}")
        with self.assertRaisesRegex(ValueError, "Geometry hash changed"):
            self.build()

    def test_exact_eight_unique_video_sources_required(self):
        self.mutate_json(builder.NEW_GEOMETRY_MANIFEST, lambda value: value["videos"].pop())
        with self.assertRaisesRegex(ValueError, "Exactly eight unique"):
            self.build()

    def test_template_and_policy_bindings_required(self):
        self.mutate_json(builder.POLICY, lambda value: value.update(source_template_sha256="0" * 64))
        with self.assertRaisesRegex(ValueError, "another geometry upload"):
            self.build()

    def test_donor_and_new_geometry_must_bind_same_source_video(self):
        self.mutate_json(builder.NEW_GEOMETRY_MANIFEST,
                         lambda value: value["videos"][0].update(video_sha256="0" * 64))
        with self.assertRaisesRegex(ValueError, "different video bytes"):
            self.build()

    def test_executed_notebook_outputs_not_repackaged(self):
        self.mutate_json(builder.NOTEBOOK, lambda value: value["cells"][0].update(execution_count=1))
        with self.assertRaisesRegex(ValueError, "no execution outputs"):
            self.build()

    def test_revision_policy_and_reviews_must_be_objects(self):
        store(self.root, builder.REVIEW_DECISIONS, b"[]")
        with self.assertRaisesRegex(ValueError, "JSON objects"):
            self.build()

    def test_different_submission_bytes_never_overwritten(self):
        self.build()
        target = self.output / "kernel-metadata.json"
        target.write_bytes(b"different submitted packet")
        with self.assertRaisesRegex(ValueError, "already contains different bytes"):
            self.build()
        self.assertEqual(target.read_bytes(), b"different submitted packet")

    def test_identical_submission_can_be_rebuilt(self):
        first = self.build()
        before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        self.assertEqual(self.build(), first)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.output.iterdir()})

    def test_actual_packet_can_be_independently_verified_without_running_cells(self):
        self.build()
        proof = verifier.verify(self.root, self.output)
        self.assertEqual(proof["status"], "PASS")
        self.assertGreater(proof["check_count"], 50)
        self.assertFalse(proof["execution_cells_run"])
        self.assertFalse(proof["remote_submission_performed"])

    def test_independent_packet_verifier_rejects_modified_notebook(self):
        self.build()
        target = self.output / "phase8_tgdi_b_v3_review.ipynb"
        value = json.loads(target.read_text())
        value["cells"][2]["source"] = ["print('changed canonical code')"]
        target.write_bytes(js(value))
        with self.assertRaisesRegex(ValueError, "submitted notebook SHA"):
            verifier.verify(self.root, self.output)

    def review_proof_fixture(self):
        name = "results/b_v3/review/pedestrian_role/review.json"
        data = js({"claim_type": "SYNTHETIC_SOURCE_BOUND_REVIEW_PROOF", "images": [
            {"path": "results/b_v3/review/pedestrian_role/frame-0.png", "sha256": "1" * 64,
             "raw_bgr_pixel_sha256": "2" * 64, "frame_index": 0}]})
        store(self.root, name, data)
        review = json.loads((self.root / builder.REVIEW_DECISIONS).read_text())
        review["videos"] = [{"reviews": [{"evidence": [{"path": name, "sha256": builder.sha(data)}]}]}]
        store(self.root, builder.REVIEW_DECISIONS, js(review))
        return name, data

    def test_explicit_json_review_proof_bundled_without_png_files(self):
        name, data = self.review_proof_fixture()
        report = self.build()
        self.assertIn(name, report["source_files"])
        self.assertEqual(report["source_files"][name]["sha256"], builder.sha(data))
        self.assertEqual(report["review_evidence_json_count"], 1)
        self.assertFalse(report["review_png_pixels_bundled"])
        self.assertTrue(all(not path.endswith(".png") for path in report["source_files"]))
        self.assertEqual(verifier.verify(self.root, self.output)["status"], "PASS")

    def test_changed_retained_review_proof_sha_rejected(self):
        name, data = self.review_proof_fixture()
        store(self.root, name, data + b" ")
        with self.assertRaisesRegex(ValueError, "review evidence proof SHA changed"):
            self.build()

    def test_non_json_or_unscoped_review_proof_path_rejected(self):
        self.review_proof_fixture()
        for name in ("results/b_v3/review/pedestrian_role/frame-0.png", "../evidence.json", "docs/other.json"):
            with self.subTest(name=name):
                self.mutate_json(builder.REVIEW_DECISIONS,
                    lambda value: value["videos"][0]["reviews"][0]["evidence"][0].update(path=name))
                with self.assertRaises(ValueError):
                    self.build()

    def test_repeated_explicit_review_proof_is_bundled_once(self):
        name, data = self.review_proof_fixture()
        self.mutate_json(builder.REVIEW_DECISIONS,
            lambda value: value["videos"][0]["reviews"].append(deepcopy(value["videos"][0]["reviews"][0])))
        report = self.build()
        self.assertEqual(report["review_evidence_json_paths"], [name])
        self.assertEqual(report["review_evidence_json_count"], 1)

    def test_compact_retained_baseline_is_bundled_and_independently_verified(self):
        report = self.build()
        self.assertIn(builder.BASELINE_SUMMARY, report["source_files"])
        self.assertEqual(report["baseline_reference_path"], builder.BASELINE_SUMMARY)
        self.assertEqual(report["baseline_reference_sha256"],
            builder.sha((self.root / builder.BASELINE_SUMMARY).read_bytes()))
        self.assertEqual(verifier.verify(self.root, self.output)["status"], "PASS")

    def test_changed_compact_baseline_sha_rejected(self):
        store(self.root, builder.BASELINE_SUMMARY, b'{"changed":true}')
        with self.assertRaisesRegex(ValueError, "compact B v2 baseline SHA changed"):
            self.build()

    def test_missing_or_different_baseline_reference_rejected(self):
        for reference in (None, {"path": "../other.json", "sha256": "a" * 64},
                          {"path": builder.BASELINE_SUMMARY, "sha256": "not-a-SHA"}):
            with self.subTest(reference=reference):
                self.mutate_json(builder.REVIEW_DECISIONS,
                    lambda value: value.update(b_v2_baseline_reference=reference))
                with self.assertRaises(ValueError):
                    self.build()

    def test_packet_size_bound(self):
        self.mutate_json(builder.NOTEBOOK, lambda value: value["cells"].append({
            "cell_type": "markdown", "metadata": {}, "source": ["x" * 1_000_000]}))
        with self.assertRaisesRegex(ValueError, "smaller than 1 MB"):
            self.build()


if __name__ == "__main__":
    unittest.main(verbosity=2)
