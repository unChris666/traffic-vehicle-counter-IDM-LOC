"""Reproduce updated human-review A without changing the original snapshot."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "notebooks"))
import phase_6_counting_helpers as helper
import phase_6_synthetic_tests as tests


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_rows(path, values):
    with path.open("wb") as stream:
        with gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as archive:
            for row in values:
                archive.write((json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    test_report = tests.run_tests()
    write_json(out / "synthetic_test_results.json", test_report)
    if not test_report["successful"]:
        raise AssertionError("A test guard failed; no actual records consumed")
    config_path = ROOT / "docs/evidence/phase_6/config/TOR3-PAGI_option_a_v0.json"
    review_path = ROOT / "docs/evidence/phase_6/reviews/TOR3-PAGI_option_a_updated_20261013.json"
    records = ROOT / "docs/evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_on/track_records.jsonl.gz"
    diagnostics = ROOT / "docs/evidence/phase_5/20261011T161440_100155Z_2e39a11c/b0_c1_diagnostics.jsonl.gz"
    geometry = ROOT / "docs/evidence/phase_5/accepted_geometry/TOR3-PAGI-G3.json"
    config = json.loads(config_path.read_text())
    reviews = json.loads(review_path.read_text())
    started = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    result = helper.run_counting(diagnostics, records, geometry, config=config,
                                 reviews=reviews, evidence_root=ROOT)
    elapsed = time.perf_counter() - clock
    for name in ("machine_decisions", "resolved_decisions", "machine_events", "accepted_events"):
        write_rows(out / (name + ".jsonl.gz"), result[name])
    for name in ("machine_aggregate", "aggregate"):
        write_json(out / (name + ".json"), result[name])
    write_rows(out / "audit_queue.jsonl.gz", [d for d in result["resolved_decisions"] if d["status"] == "pending_review"])
    write_rows(out / "rejected_decisions.jsonl.gz", [d for d in result["resolved_decisions"] if d["status"] == "rejected"])
    (out / "configuration_input.json").write_bytes(config_path.read_bytes())
    (out / "review_input.json").write_bytes(review_path.read_bytes())
    original = ROOT / "docs/evidence/phase_6/20261012T144625_030645Z"
    old = json.loads((original / "aggregate.json").read_text())
    original_event_ids_unchanged = old["event_ids"] == result["aggregate"]["event_ids"]
    report = {"claim_type": "EXECUTED_A_UPDATED_HUMAN_CASE_REVIEW_NOT_NEW_GEOMETRY_POLICY",
              "run_id": "option_b_a_updated_20261013", "started_at_utc": started,
              "completed_at_utc": datetime.now(timezone.utc).isoformat(),
              "measured_counting_elapsed_seconds": elapsed,
              "effective_configuration": config, "software_report": result["report"],
              "input_sha256": {"configuration": sha(config_path), "reviews": sha(review_path),
                               "records": sha(records), "diagnostics": sha(diagnostics), "geometry": sha(geometry)},
              "source_code_sha256": {"method": sha(__file__), "counting_helper": sha(helper.__file__),
                                     "synthetic_tests": sha(tests.__file__)},
              "runtime": {"python": sys.version, "platform": platform.platform(), "gpu_required": False},
              "original_event_ids_unchanged": original_event_ids_unchanged,
              "unit_episode_recovery_executed": False, "models_tracker_encoder_geometry_rerun": False,
              "formal_ground_truth_available": False, "complete_video_traffic_count_established": False}
    write_json(out / "report.json", report)
    entries = [{"path": p.name, "sha256": sha(p), "size_bytes": p.stat().st_size}
               for p in sorted(out.iterdir()) if p.is_file()]
    write_json(out / "execution_manifest.json", {"run_id": report["run_id"], "artifacts": entries})
    print(json.dumps({"output": str(out), "tests_passed": test_report["tests_passed"],
                      "aggregate": result["aggregate"], "statuses": result["report"]["resolved_decision_statuses"],
                      "original_event_ids_unchanged": original_event_ids_unchanged}, indent=2))


if __name__ == "__main__":
    main()
