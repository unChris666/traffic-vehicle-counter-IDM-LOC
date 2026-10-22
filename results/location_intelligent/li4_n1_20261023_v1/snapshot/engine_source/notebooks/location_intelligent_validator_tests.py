"""Focused LI-0 contract tests. Synthetic fixtures; no model/provider execution."""
from copy import deepcopy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from location_intelligent_validator import canonical_hash, context_hash, main, validate, validate_files


FIXTURES = Path(__file__).parent / "fixtures" / "li0"
HELPER = Path(__file__).with_name("location_intelligent_validator.py")


def bind(c, m):
    c["context_hash"] = context_hash(c)
    m["context_hash"] = c["context_hash"]
    for run in m.get("modules", []):
        if isinstance(run, dict):
            run["context_hash"] = c["context_hash"]
            run["config_hash"] = canonical_hash(c["config"])


def change(doc, path, *, delete=False, value=None):
    parts = path.split(".")
    parent = doc
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    key = int(parts[-1]) if isinstance(parent, list) else parts[-1]
    if delete:
        del parent[key]
    else:
        parent[key] = value


class OfflineValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for p in FIXTURES.iterdir():
            shutil.copyfile(p, self.root / p.name)
        self.c = json.loads((self.root / "context.json").read_text())
        self.m = json.loads((self.root / "manifest.json").read_text())

    def run_validation(self, *, rebind=True):
        if rebind:
            bind(self.c, self.m)
        return validate(self.c, self.m, root=self.root)

    def codes(self, result):
        return {d["code"] for d in result["diagnostics"]}

    def assert_invalid(self, result, code):
        self.assertEqual(result["validation_status"], "INVALID", result)
        self.assertEqual(result["offline_readiness"], "BLOCKED")
        self.assertIn(code, self.codes(result))

    def assert_blocked(self, result, code):
        self.assertEqual(result["validation_status"], "VALID", result)
        self.assertEqual(result["offline_readiness"], "BLOCKED")
        self.assertIn(code, self.codes(result))

    def unknown_source(self, status):
        s = self.m["sources"][0]
        s.update(availability=status, row_count=None, fingerprint=None, byte_count=None)
        if status is None:
            s["unknown_reasons"]["availability"] = "Availability has not been established"

    def test_valid_fixture_without_rebinding(self):
        r = self.run_validation(rebind=False)
        self.assertEqual(r["validation_status"], "VALID", r)
        self.assertEqual(r["offline_readiness"], "READY", r)
        self.assertEqual(r["live_readiness"], "NOT_VERIFIED")
        self.assertEqual(r["verified_local_source_count"], 1)
        self.assertTrue(any(d["severity"] == "UNKNOWN" and not d["blocking"] for d in r["diagnostics"]))

    def test_checked_in_invalid_cases(self):
        for case in json.loads((FIXTURES / "invalid_cases.json").read_text()):
            with self.subTest(case=case["name"]):
                c, m = deepcopy(self.c), deepcopy(self.m)
                doc = {"context": c, "manifest": m}
                change(doc, case.get("delete", case.get("set")), delete="delete" in case, value=case.get("value"))
                # Refresh only hashes; deliberate run/schema inconsistencies remain.
                bind(c, m)
                r = validate(c, m, root=self.root)
                self.assertEqual(r["validation_status"], case["validity"], r)
                self.assertEqual(r["offline_readiness"], "BLOCKED")
                self.assertIn(case["code"], self.codes(r))

    def test_deterministic_and_nonmutating(self):
        before = deepcopy((self.c, self.m))
        a = self.run_validation(rebind=False)
        b = validate(deepcopy(self.c), deepcopy(self.m), root=self.root)
        self.assertEqual(a, b)
        self.assertEqual((self.c, self.m), before)

    def test_known_context_hash_and_unicode(self):
        self.assertEqual(context_hash(self.c), "c9d04b4cf0c42bf72e9e37f9c5eab822b1cb6d01948cdcfa4f04c8e4ce716940")
        self.assertEqual(canonical_hash({"é": 1}), hashlib.sha256('{"é":1}'.encode()).hexdigest())

    def test_context_hash_mismatch(self):
        self.c["target"]["store_name"] = "Changed"
        self.assert_invalid(self.run_validation(rebind=False), "CONTEXT_HASH_MISMATCH")

    def test_module_config_hash_mismatch(self):
        self.m["modules"][0]["config_hash"] = "a" * 64
        self.assert_invalid(self.run_validation(rebind=False), "CONFIG_HASH_MISMATCH")

    def test_ids_and_duplicate_refs(self):
        for value in ["../escape", "a/b", "a\\b", "", None, True, "a..b"]:
            with self.subTest(value=value):
                self.c["analysis_run_id"] = value
                self.assert_invalid(self.run_validation(), "ID_INVALID")
        self.c["analysis_run_id"] = "valid"
        self.m["sources"].append(deepcopy(self.m["sources"][0]))
        self.assert_invalid(self.run_validation(), "ID_DUPLICATE")

    def test_unknown_coordinates_block_without_zero(self):
        t = self.c["target"]
        t.update(latitude=None, longitude=None)
        t["unknown_reasons"] = {"latitude": "Unknown location", "longitude": "Unknown location"}
        self.assert_blocked(self.run_validation(), "VALUE_UNKNOWN")
        self.assertIsNone(t["latitude"])

    def test_half_coordinate_pair_invalid(self):
        self.c["target"]["latitude"] = None
        self.c["target"]["unknown_reasons"]["latitude"] = "Not known"
        self.assert_invalid(self.run_validation(), "COORDINATE_PAIR")

    def test_unknown_store_metadata_nonblocking(self):
        t = self.c["target"]
        t.update(store_code=None, store_name=None)
        t["unknown_reasons"] = {"store_code": "Not supplied", "store_name": "Not supplied"}
        self.assertEqual(self.run_validation()["offline_readiness"], "READY")

    def test_missing_unknown_reason_invalid(self):
        self.c["target"]["store_name"] = None
        self.assert_invalid(self.run_validation(), "UNKNOWN_REASON_REQUIRED")

    def test_nonfinite_python_numbers_invalid(self):
        for value in [float("nan"), float("inf"), -float("inf")]:
            with self.subTest(value=value):
                self.c["target"]["latitude"] = value
                self.assert_invalid(validate(self.c, self.m, root=self.root), "NUMBER_NONFINITE")

    def test_crs_axes_utm_and_boundaries(self):
        self.c["target"]["crs"] = "EPSG:3857"
        self.assert_invalid(self.run_validation(), "CRS_INVALID")
        self.c["target"]["crs"] = "EPSG:4326"
        for crs in ["EPSG:32648", "EPSG:32747"]:
            self.c["config"]["area_coverage"]["metric_crs"] = crs
            self.assert_invalid(self.run_validation(), "METRIC_CRS_DOMAIN")
        self.c["config"]["area_coverage"]["metric_crs"] = "EPSG:3857"
        self.assert_invalid(self.run_validation(), "METRIC_CRS_UNSUPPORTED")
        self.c["config"]["area_coverage"]["metric_crs"] = None
        self.c["target"].update(latitude=-90, longitude=180)
        r = self.run_validation()
        self.assertNotIn("COORDINATE_RANGE", self.codes(r))
        self.assert_blocked(r, "METRIC_CRS_REQUIRED")

    def test_quantities_order_ratios_bool_and_unknown(self):
        params = self.c["config"]["area_coverage"]["parameters"]
        params["max_area_m2"]["value"] = 45
        self.assert_invalid(self.run_validation(), "CONFIG_ORDER")
        params["max_area_m2"]["value"] = 550
        params["apartment_occupancy"] = {"value": 1.1, "unit": "ratio"}
        self.assert_invalid(self.run_validation(), "CONFIG_RANGE")
        params["apartment_occupancy"]["value"] = 0
        self.assertEqual(self.run_validation()["offline_readiness"], "READY")
        params["apartment_occupancy"]["value"] = True
        self.assert_invalid(self.run_validation(), "TYPE_NUMBER")
        params["apartment_occupancy"].update(value=None, unknown_reason="Unknown occupancy")
        self.assert_blocked(self.run_validation(), "CONFIG_UNKNOWN")

    def test_unavailable_failed_unattempted_and_unknown_are_not_empty(self):
        for status in ["UNAVAILABLE", "REQUEST_FAILED", "NOT_ATTEMPTED", None]:
            with self.subTest(status=status):
                self.unknown_source(status)
                self.assert_blocked(self.run_validation(), "REQUIRED_SOURCE_UNAVAILABLE")
                self.assertIsNone(self.m["sources"][0]["row_count"])
                self.m["sources"][0]["row_count"] = 0
                self.assert_invalid(self.run_validation(), "ROW_COUNT_UNOBSERVED")

    def test_verified_empty_source_is_ready_without_world_claim(self):
        s = self.m["sources"][0]
        p = self.root / "empty_buildings.geojson"
        s.update(availability="AVAILABLE_EMPTY", locator=p.name, row_count=0,
                 byte_count=p.stat().st_size, fingerprint={"algorithm": "sha256", "value": hashlib.sha256(p.read_bytes()).hexdigest()})
        self.assertEqual(self.run_validation()["offline_readiness"], "READY")
        s["row_count"] = 1
        self.assert_invalid(self.run_validation(), "EMPTY_STATUS_MISMATCH")

    def test_available_zero_must_declare_empty(self):
        self.m["sources"][0]["row_count"] = 0
        self.assert_invalid(self.run_validation(), "EMPTY_STATUS_MISMATCH")

    def test_partial_source_and_coverage_block(self):
        self.m["sources"][0]["availability"] = "PARTIAL"
        self.assert_blocked(self.run_validation(), "REQUIRED_SOURCE_UNAVAILABLE")
        self.m["sources"][0]["availability"] = "AVAILABLE"
        self.m["sources"][0]["coverage"]["completeness"] = "PARTIAL"
        self.assert_blocked(self.run_validation(), "SOURCE_COVERAGE_INCOMPLETE")

    def test_optional_unknown_rwi_does_not_block_core_area(self):
        s = deepcopy(self.m["sources"][0])
        s.update(source_ref_id="unknown-rwi", inventory_id="SRC07", availability=None,
                 row_count=None, fingerprint=None, byte_count=None)
        s["unknown_reasons"]["availability"] = "No mapping exists"
        self.m["sources"].append(s)
        self.assertEqual(self.run_validation()["offline_readiness"], "READY")

    def test_missing_required_source_or_module_blocks(self):
        self.m["sources"] = []
        self.assert_blocked(self.run_validation(), "SOURCE_REF_MISSING")
        self.m["modules"] = []
        self.assert_blocked(self.run_validation(), "AREA_MODULE_REQUIRED")

    def test_unknown_source_metadata_does_not_become_zero(self):
        s = self.m["sources"][0]
        s["units"] = None
        s["unknown_reasons"]["units"] = "Unknown measurement units"
        self.assert_blocked(self.run_validation(), "VALUE_UNKNOWN")

    def test_freshness_unknown_offline_not_automatically_stale(self):
        self.assertEqual(self.run_validation()["offline_readiness"], "READY")
        self.m["sources"][0].update(freshness="STALE_FOR_POLICY", freshness_policy_ref="fixture-policy-1")
        self.assert_blocked(self.run_validation(), "SOURCE_STALE")

    def test_remote_locator_never_fetched(self):
        s = self.m["sources"][0]
        s.update(kind="OBJECT_STORAGE", locator="s3://example.invalid/buildings")
        with patch.object(socket, "socket", side_effect=AssertionError("Network forbidden")):
            self.assert_blocked(self.run_validation(), "SOURCE_NOT_LOCAL")
            s["local_path"] = "buildings.geojson"
            self.assertEqual(self.run_validation()["offline_readiness"], "READY")

    def test_source_checksum_algorithm_size_and_provenance(self):
        s = self.m["sources"][0]
        s["fingerprint"]["algorithm"] = "md5"
        self.assert_invalid(self.run_validation(), "CHECKSUM_ALGORITHM")
        s["fingerprint"]["algorithm"] = "sha256"
        s["byte_count"] += 1
        self.assert_invalid(self.run_validation(), "FILE_FINGERPRINT_MISMATCH")
        s["provenance"]["origin"] = "LIVE_ACQUIRED"
        self.assert_invalid(self.run_validation(), "PROVENANCE_MODE_MISMATCH")

    def test_unknown_schema_version_and_extra_typo_rejected(self):
        self.c["schema_version"] = "unsupported"
        self.assert_invalid(self.run_validation(), "SCHEMA_UNSUPPORTED")
        self.c["schema_version"] = "location_intelligent_v1"
        self.c["target"]["latitdue"] = -6.43
        self.assert_invalid(self.run_validation(), "FIELD_UNKNOWN")

    def artifact(self):
        s = self.m["sources"][0]
        a = {"artifact_id": "fixture-output", "layer": "NORMALIZED", "schema_version": "fixture-v1",
             "module_run_id": "other-run", "path": "buildings.geojson", "fingerprint": deepcopy(s["fingerprint"]),
             "byte_count": s["byte_count"], "dependencies": ["fixture-buildings"], "status": "SUCCEEDED", "completeness": "COMPLETE"}
        other = deepcopy(self.m["modules"][0])
        other.update(module_run_id="other-run", module="traffic_counter", status="SUCCEEDED", artifact_refs=[a["artifact_id"]],
                     started_at="2026-10-21T00:00:00Z", finished_at="2026-10-21T00:00:01Z",
                     engine={"name": "synthetic-test-only", "version": "fixture-1", "source_hashes": {"fixture-code": "a" * 64}})
        self.m["modules"].append(other)
        self.m["artifacts"].append(a)
        return a, other

    def test_artifact_path_traversal_and_symlink_escape(self):
        a, _ = self.artifact()
        for path in ["../outside.json", "/etc/hosts", "https://example.invalid/file", "a\\b"]:
            with self.subTest(path=path):
                a["path"] = path
                self.assert_invalid(self.run_validation(), "PATH_UNSAFE")
        with tempfile.TemporaryDirectory() as outside:
            (self.root / "escape").symlink_to(Path(outside), target_is_directory=True)
            a["path"] = "escape/output.json"
            self.assert_invalid(self.run_validation(), "PATH_ESCAPE")

    def test_artifact_producer_reference_and_checksum(self):
        a, _ = self.artifact()
        a["module_run_id"] = "absent-run"
        self.assert_invalid(self.run_validation(), "PRODUCER_REF_INVALID")
        a["module_run_id"] = "other-run"
        a["fingerprint"]["value"] = "0" * 64
        self.assert_invalid(self.run_validation(), "FILE_FINGERPRINT_MISMATCH")

    def test_artifact_and_producer_status_are_consistent(self):
        a, other = self.artifact()
        self.assertEqual(self.run_validation()["offline_readiness"], "READY")
        other.update(status="NOT_RUN", started_at=None, finished_at=None)
        self.assert_invalid(self.run_validation(), "ARTIFACT_BEFORE_EXECUTION")
        other.update(status="SUCCEEDED", started_at="2026-10-21T00:00:00Z", finished_at="2026-10-21T00:00:01Z")
        a["completeness"] = "PARTIAL"
        self.assert_invalid(self.run_validation(), "ARTIFACT_STATUS_MISMATCH")

    def test_other_module_readiness_does_not_block_area_inputs(self):
        other = deepcopy(self.m["modules"][0])
        other.update(module="ppac", module_run_id="blocked-ppac", status="BLOCKED",
                     error="Formula and feature refs unavailable", required_inputs=["unknown-feature"])
        self.m["modules"].append(other)
        r = self.run_validation()
        self.assertEqual(r["offline_readiness"], "READY", r)
        self.assertIn("SOURCE_REF_MISSING", self.codes(r))

    def test_artifact_wrong_types_do_not_crash(self):
        a, _ = self.artifact()
        before = deepcopy(a)
        for key in before:
            for wrong in [[], {}, True, None]:
                with self.subTest(field=key, value=wrong):
                    a.clear()
                    a.update(deepcopy(before))
                    a[key] = wrong
                    r = self.run_validation()
                    self.assertEqual(r["validation_status"], "INVALID", r)

    def test_remote_fingerprint_metadata_is_checked_without_fetch(self):
        s = self.m["sources"][0]
        s.update(kind="OBJECT_STORAGE", locator="s3://example.invalid/file", byte_count=True)
        self.assert_invalid(self.run_validation(), "BYTE_COUNT_INVALID")

    def test_source_bytes_changed_without_manifest_update(self):
        (self.root / "buildings.geojson").write_text("Changed snapshot")
        self.assert_invalid(self.run_validation(), "FILE_FINGERPRINT_MISMATCH")

    def test_local_file_permission_error_is_structured(self):
        with patch.object(Path, "open", side_effect=PermissionError("Do not echo sensitive details")):
            r = self.run_validation()
        self.assert_invalid(r, "LOCAL_READ_FAILED")
        self.assertNotIn("sensitive details", json.dumps(r))

    def test_invalid_checksum_even_when_file_is_missing(self):
        self.m["sources"][0].update(locator="absent", fingerprint=None)
        self.assert_invalid(self.run_validation(), "CHECKSUM_INVALID")

    def test_dependency_cycles_invalid(self):
        a, _ = self.artifact()
        a["dependencies"] = [a["artifact_id"]]
        self.assert_invalid(self.run_validation(), "DEPENDENCY_CYCLE")

    def test_success_claim_requires_execution_proof(self):
        self.m["modules"][0]["status"] = "SUCCEEDED"
        self.assert_invalid(self.run_validation(), "SUCCESS_EVIDENCE_REQUIRED")

    def test_module_timestamp_and_parent_rules(self):
        self.c["parent_analysis_run_id"] = self.c["analysis_run_id"]
        self.assert_invalid(self.run_validation(), "PARENT_SELF")
        self.c["parent_analysis_run_id"] = None
        self.c["created_at"] = "2026-10-21T00:00:00"
        self.assert_invalid(self.run_validation(), "TIMESTAMP_INVALID")
        self.c["created_at"] = "2026-10-21T00:00:00Z"
        self.m["modules"][0]["started_at"] = "2026-10-21T00:00:00Z"
        self.assert_invalid(self.run_validation(), "NOT_RUN_TIMESTAMPS")

    def test_strict_json_loader(self):
        for text in ["{", '{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '[1,2,]']:
            with self.subTest(text=text):
                path = self.root / "bad.json"
                path.write_text(text)
                self.assert_invalid(validate_files(path, self.root / "manifest.json", root=self.root), "JSON_INVALID")
        (self.root / "bad.json").write_bytes(b"\xff")
        self.assert_invalid(validate_files(self.root / "bad.json", self.root / "manifest.json", root=self.root), "JSON_INVALID")

    def test_missing_input_file_reported(self):
        self.assert_invalid(validate_files(self.root / "absent.json", self.root / "manifest.json", root=self.root), "JSON_FILE_UNAVAILABLE")

    def test_cli_exit_codes(self):
        args = ["--context", str(self.root / "context.json"), "--manifest", str(self.root / "manifest.json"), "--root", str(self.root)]
        for expected, mode in [(0, "ready"), (2, "blocked"), (1, "invalid")]:
            with self.subTest(mode=mode):
                if mode == "blocked":
                    (self.root / "buildings.geojson").unlink()
                elif mode == "invalid":
                    (self.root / "context.json").write_text("{")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main(args), expected)
                self.assertEqual(json.loads(output.getvalue())["live_readiness"], "NOT_VERIFIED")

    def test_import_has_no_filesystem_or_network_side_effects(self):
        code = """import builtins, socket, importlib.util, sys
spec=importlib.util.spec_from_file_location('li0_check',sys.argv[1])
module=importlib.util.module_from_spec(spec)
def forbidden(*a,**k): raise AssertionError('Unexpected I/O during module execution')
builtins.open=forbidden
socket.socket=forbidden
spec.loader.exec_module(module)
assert 'cv2' not in sys.modules and 'google.cloud.bigquery' not in sys.modules
"""
        r = subprocess.run([sys.executable, "-B", "-c", code, str(HELPER)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_local_inputs_not_written_or_fetched(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        with patch.object(socket, "socket", side_effect=AssertionError("Network forbidden")), patch.object(Path, "write_bytes", side_effect=AssertionError("Write forbidden")), patch.object(Path, "write_text", side_effect=AssertionError("Write forbidden")):
            self.assertEqual(self.run_validation(rebind=False)["offline_readiness"], "READY")
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_wrong_types_fail_closed_without_crashing(self):
        # Mutate every existing JSON field; catches nested malformed/unhashable
        # values rather than testing only the documented happy path.
        cases = []
        def walk(value, parts):
            if isinstance(value, dict):
                for key, child in value.items():
                    cases.append(parts + [key])
                    walk(child, parts + [key])
            elif isinstance(value, list):
                for i, child in enumerate(value):
                    cases.append(parts + [str(i)])
                    walk(child, parts + [str(i)])
        walk({"context": self.c, "manifest": self.m}, [])
        for parts in cases:
            for wrong in [None, [], {}, True, 1, "unexpected"]:
                with self.subTest(path=".".join(parts), value=wrong):
                    doc = deepcopy({"context": self.c, "manifest": self.m})
                    change(doc, ".".join(parts), value=wrong)
                    r = validate(doc["context"], doc["manifest"], root=self.root)
                    self.assertIn(r["validation_status"], {"VALID", "INVALID"})
                    json.dumps(r, allow_nan=False)


class LI0GapRegressionTests(unittest.TestCase):
    setUp = OfflineValidatorTests.setUp
    run_validation = OfflineValidatorTests.run_validation
    codes = OfflineValidatorTests.codes
    assert_invalid = OfflineValidatorTests.assert_invalid

    def test_unpaired_unicode_value_cannot_skip_context_hash_check(self):
        self.c["target"]["store_name"] = "\ud800"
        self.assert_invalid(self.run_validation(rebind=False), "JSON_STRING_INVALID")

    def test_unpaired_unicode_key_has_serializable_diagnostic(self):
        self.c["target"]["\ud800"] = "value"
        r = self.run_validation(rebind=False)
        self.assert_invalid(r, "JSON_STRING_INVALID")
        json.dumps(r, ensure_ascii=False).encode("utf-8")

    def test_partial_source_fingerprint_metadata_is_validated(self):
        self.m["sources"][0].update(availability="PARTIAL", fingerprint={"algorithm": "md5", "value": "bad"})
        self.assert_invalid(self.run_validation(), "CHECKSUM_ALGORITHM")

    def test_unused_second_building_source_does_not_block_selected_source(self):
        other = deepcopy(self.m["sources"][0])
        other.update(source_ref_id="unused-snapshot", availability="UNAVAILABLE",
                     row_count=None, byte_count=None, fingerprint=None)
        self.m["sources"].append(other)
        r = self.run_validation()
        self.assertEqual(r["validation_status"], "VALID", r)
        self.assertEqual(r["offline_readiness"], "READY", r)

    def test_present_quantity_reason_requires_string_even_for_known_value(self):
        self.c["config"]["area_coverage"]["parameters"]["building_radius_m"]["unknown_reason"] = True
        self.assert_invalid(self.run_validation(), "TYPE_STRING")

    def test_fifo_json_input_is_rejected_before_open(self):
        import os
        p = self.root / "input.fifo"
        os.mkfifo(p)
        original = Path.open
        def guarded(path, *args, **kwargs):
            if path == p:
                raise ValueError("FIFO must never be opened")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", guarded):
            r = validate_files(p, self.root / "manifest.json", root=self.root)
        self.assert_invalid(r, "JSON_FILE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
