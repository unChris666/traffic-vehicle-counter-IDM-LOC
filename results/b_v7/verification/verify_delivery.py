"""Verify retained bytes, frozen controls and notebook structure; no inference."""
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "results/b_v7"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def verify_rows(rows, base):
    wrong = [row["path"] for row in rows
             if not (base / row["path"]).is_file()
             or digest(base / row["path"]) != row["sha256"]]
    if wrong:
        raise AssertionError("Retained bytes changed: " + repr(wrong))
    return len(rows)


def main():
    frozen = read(PACKAGE / "verification/frozen_inputs_before.json")
    historical = verify_rows(frozen["files"], ROOT)
    baseline_manifest = read(ROOT / "results/b_v6/retention_manifest.json")
    baseline = verify_rows(baseline_manifest["files"], ROOT / "results/b_v6")
    bindings = verify_rows(baseline_manifest["code_and_document_bindings"], ROOT)
    freeze = read(PACKAGE / "verification/configuration_freeze.json")
    correction = read(PACKAGE / "verification/notebook_metadata_correction.json")
    notebook_path = correction["path"]
    assert freeze["source_sha256"][notebook_path] == correction["before_sha256"]
    assert digest(ROOT / notebook_path) == correction["after_sha256"]
    verify_rows([{"path": p, "sha256": value}
                 for p, value in freeze["source_sha256"].items()
                 if p != notebook_path], ROOT)
    assert digest(ROOT / freeze["policy_path"]) == freeze["policy_sha256"]
    assert digest(ROOT / "docs/B_V7_HANDOFF_CONTRACT.md") == freeze["contract_sha256"]
    run = PACKAGE / "execution/pilot_v7_machine_final"
    counts = {}
    for name, path in {
        "full_run": run,
        "actual_fixture": PACKAGE / "fixtures/1049_1123_v1",
        "event_comparison": PACKAGE / "comparison/full_pilot_v1",
    }.items():
        counts[name] = verify_rows(read(path / "retention_manifest.json")["files"], path)
    for filename, metadata in read(run / "source_snapshot.json").items():
        data = gzip.decompress((run / metadata["retained_path"]).read_bytes())
        assert hashlib.sha256(data).hexdigest() == metadata["sha256"]
        if Path(filename) == ROOT / notebook_path:
            assert metadata["sha256"] == correction["before_sha256"]
            original, current = json.loads(data), read(Path(filename))
            for cell in current["cells"]:
                assert isinstance(cell.pop("id"), str)
            assert original == current, "Notebook change exceeds cell ID metadata"
        else:
            assert digest(Path(filename)) == metadata["sha256"]
    guarded = verify_rows(read(run / "guarded_inputs.json"), ROOT)
    report = read(run / "batch_report.json")
    assert report["frames_processed"] == 9128 and report["inputs_and_sources_unchanged"]
    assert report["new_detector_tracker_reid_execution"] is False
    assert report["new_enhancement_execution"] is False
    comparison = read(PACKAGE / "comparison/full_pilot_v1/comparison.json")
    assert comparison["event_counts"] == {"unchanged": 72, "changed": 0, "removed": 2, "added": 0}
    assert comparison["pending_semantically_unchanged"]
    assert comparison["frame_assignments_unchanged"] and comparison["component_links_unchanged"]
    assert len(comparison["display_id_changes"]) == 17
    assert not comparison["evidence_level_transitions"]
    qc = read(PACKAGE / "review/independent_replay_qc.json")
    assert qc["overall_p0_gate"] == "BLOCKED"
    assert qc["target_scope_gate"] == "PASS_SCOPED_DUPLICATE_PREVENTION_WITH_INTENTIONAL_COVERAGE_LOSS"
    assert all(not row["changed_source_dispositions"]
               for row in qc["legacy_qc_inventory_reconciliation"].values())
    tests = read(PACKAGE / "verification/tests.json")
    assert all(row["returncode"] == 0 for row in tests)
    assert sum(row["tests"] for row in tests) == 211
    import nbformat
    notebook = nbformat.read(ROOT / "notebooks/09d_motion_handoff_replay.ipynb", as_version=4)
    nbformat.validate(notebook)
    for i, cell in enumerate(notebook.cells):
        if cell.cell_type == "code":
            compile(cell.source, f"09d:cell{i}", "exec")
            assert not cell.outputs and cell.execution_count is None
    result = {"status": "PASS_RETENTION_AND_SCOPED_SOFTWARE_CHECKS_NOT_P0_APPROVAL",
        "historical_files_unchanged": historical, "baseline_retained_files_verified": baseline,
        "baseline_code_document_bindings_verified": bindings,
        "guarded_execution_inputs_verified": guarded, "retention_files_verified": counts,
        "software_tests_passed": 211, "notebook_structure_and_code_cells": "PASS",
        "post_execution_notebook_metadata_only_correction_verified": True,
        "notebook_outputs_fabricated": False, "full_p0_gate": "BLOCKED",
        "new_model_execution": False}
    (PACKAGE / "verification/final_checks.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
