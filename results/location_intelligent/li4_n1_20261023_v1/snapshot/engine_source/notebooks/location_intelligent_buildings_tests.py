"""LI-1 synthetic offline tests; no empirical/live-building validation claim."""
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

from location_intelligent_buildings import classify_building, main, select_buildings, selection_reason
from location_intelligent_validator import canonical_hash, context_hash

try:
    from osgeo import ogr
    from pyproj import Transformer
    GEOMETRY_AVAILABLE = True
except ImportError:
    GEOMETRY_AVAILABLE = False

FIXTURES = Path(__file__).parent / "fixtures" / "li1"
HELPER = Path(__file__).with_name("location_intelligent_buildings.py")


@unittest.skipUnless(GEOMETRY_AVAILABLE, "Use /usr/bin/python3 with installed GDAL/OGR and PyProj for LI-1 geometry tests")
class BuildingSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for path in FIXTURES.iterdir():
            shutil.copyfile(path, self.root / path.name)
        self.c = json.loads((self.root / "context.json").read_text())
        self.m = json.loads((self.root / "manifest.json").read_text())
        self.data = json.loads((self.root / "buildings.geojson").read_text())

    def rebind(self):
        self.c["context_hash"] = context_hash(self.c)
        self.m.update(analysis_run_id=self.c["analysis_run_id"], context_hash=self.c["context_hash"])
        for run in self.m["modules"]:
            run.update(context_hash=self.c["context_hash"], config_hash=canonical_hash(self.c["config"]))

    def snapshot(self, features=None, *, payload=None, raw=None):
        if payload is None:
            payload = {"type": "FeatureCollection", "features": features if features is not None else self.data["features"]}
        if raw is None:
            raw = (json.dumps(payload, sort_keys=True, allow_nan=False) + "\n").encode()
        p = self.root / "buildings.geojson"
        p.write_bytes(raw)
        s = self.m["sources"][0]
        count = len(payload.get("features", [])) if isinstance(payload, dict) and isinstance(payload.get("features"), list) else 1
        s.update(fingerprint={"algorithm": "sha256", "value": hashlib.sha256(raw).hexdigest()},
                 byte_count=len(raw), row_count=count, availability="AVAILABLE" if count else "AVAILABLE_EMPTY")
        return p

    def run_selection(self, *, source="fixture-buildings", rebind=True):
        if rebind:
            self.rebind()
        return select_buildings(self.c, self.m, root=self.root, source_ref_id=source)

    def rectangle(self, key="test-building", *, width=10, height=10, dx=0, dy=0,
                  cls="residential", sub="residential"):
        crs = self.c["config"]["area_coverage"]["metric_crs"]
        to_metric = Transformer.from_crs(4326, crs, always_xy=True)
        to_geo = Transformer.from_crs(crs, 4326, always_xy=True)
        x, y = to_metric.transform(self.c["target"]["longitude"], self.c["target"]["latitude"])
        coords = [list(to_geo.transform(x+dx+a, y+dy+b)) for a, b in
                  [(-width/2,-height/2),(width/2,-height/2),(width/2,height/2),(-width/2,height/2),(-width/2,-height/2)]]
        return {"type": "Feature", "properties": {"building_id": key, "class": cls, "subclass": sub},
                "geometry": {"type": "Polygon", "coordinates": [coords]}}

    def assert_record_reason(self, feature, code):
        self.snapshot([feature])
        r = self.run_selection()
        self.assertEqual(r["status"], "PARTIAL", r)
        self.assertEqual(r["summary"]["rejected"], 1)
        self.assertEqual(r["reject_ledger"][0]["code"], code, r)
        return r

    def test_retained_fixture_expected_membership(self):
        r = self.run_selection(rebind=False)
        expected = json.loads((FIXTURES / "expected.json").read_text())
        self.assertEqual(r["status"], expected["status"], r)
        self.assertEqual([x["building_id"] for x in r["selected"]], expected["selected_ids"])
        self.assertEqual({x["building_id"]: x["code"] for x in r["reject_ledger"]}, expected["excluded"])
        self.assertEqual(r["summary"]["source_records"], expected["source_records"])
        self.assertEqual(r["summary"]["selected"], 5)
        self.assertEqual(r["summary"]["excluded"], 4)
        self.assertEqual(r["summary"]["rejected"], 0)
        self.assertEqual(r["live_readiness"], "NOT_VERIFIED")

    def test_retained_invalid_fixture_has_reconcilable_ledger(self):
        self.m=json.loads((self.root/"invalid_manifest.json").read_text())
        r=self.run_selection(source="fixture-buildings-invalid",rebind=False)
        self.assertEqual(r["status"],"PARTIAL",r)
        self.assertEqual((r["summary"]["selected"],r["summary"]["excluded"],r["summary"]["rejected"]),(1,2,6))
        self.assertEqual(r["summary"]["accounted_records"],9)
        self.assertEqual(r["summary"]["reason_counts"]["DUPLICATE_BUILDING_ID"],2)

    def test_source_binding_and_external_schema_version(self):
        self.assertEqual(self.run_selection(source="not-selected")["diagnostics"][0]["code"], "SOURCE_BINDING_INVALID")
        self.m["sources"][0]["schema_version"] = "li0_building_fixture_v1"
        r = self.run_selection()
        self.assertEqual(r["status"], "FAILED")
        self.assertIsNone(r["summary"])

    def test_file_format_is_not_inferred_as_parquet_or_csv(self):
        p=self.root/"buildings.csv"
        shutil.copyfile(self.root/"buildings.geojson",p)
        self.m["sources"][0]["locator"]=p.name
        r=self.run_selection()
        self.assertEqual(r["diagnostics"][0]["code"],"SNAPSHOT_FORMAT_UNSUPPORTED")
        self.assertIsNone(r["summary"])

    def test_snapshot_bytes_rechecked_after_gate(self):
        with patch.object(Path,"read_bytes",return_value=b"Changed after LI-0"):
            r=self.run_selection()
        self.assertEqual(r["diagnostics"][0]["code"],"SNAPSHOT_CHANGED")
        self.assertIsNone(r["summary"])

    def test_missing_snapshot_is_not_zero_buildings(self):
        (self.root / "buildings.geojson").unlink()
        r = self.run_selection()
        self.assertEqual(r["status"], "BLOCKED")
        self.assertIsNone(r["summary"])

    def test_unreadable_snapshot_is_not_zero(self):
        with patch.object(Path, "read_bytes", side_effect=PermissionError("private detail")):
            r = self.run_selection()
        self.assertEqual(r["status"], "FAILED")
        self.assertEqual(r["diagnostics"][0]["code"], "SNAPSHOT_UNREADABLE")
        self.assertIsNone(r["summary"])
        self.assertNotIn("private detail", json.dumps(r))

    def test_snapshot_malformed_and_duplicate_json_keys(self):
        for raw in [b"{", b'{"type":"FeatureCollection","features":[],"features":[]}', b'{"x":NaN}', b'\xff']:
            with self.subTest(raw=raw):
                self.snapshot(raw=raw)
                r = self.run_selection()
                self.assertEqual(r["status"], "FAILED", r)
                self.assertIsNone(r["summary"])
                self.assertEqual(r["diagnostics"][0]["code"], "SNAPSHOT_JSON_INVALID")

    def test_snapshot_top_level_schema_and_count(self):
        for payload in [[], {}, {"type": "Point", "coordinates": [0,0]}, {"type": "FeatureCollection", "features": {}}]:
            with self.subTest(payload=payload):
                self.snapshot(payload=payload)
                self.assertEqual(self.run_selection()["diagnostics"][0]["code"], "SNAPSHOT_SCHEMA_INVALID")
        self.snapshot([self.rectangle()])
        self.m["sources"][0]["row_count"] = 2
        self.assertEqual(self.run_selection()["diagnostics"][0]["code"], "SNAPSHOT_ROW_COUNT_MISMATCH")

    def test_source_crs_and_units_must_be_explicit(self):
        self.m["sources"][0]["crs"] = "EPSG:3857"
        self.assertEqual(self.run_selection()["diagnostics"][0]["code"], "SNAPSHOT_CRS_INVALID")
        self.m["sources"][0]["crs"] = "EPSG:4326"
        self.m["sources"][0]["units"] = {"coordinates": "m"}
        self.assertEqual(self.run_selection()["diagnostics"][0]["code"], "SNAPSHOT_CRS_INVALID")

    def test_payload_crs_conflict(self):
        payload = deepcopy(self.data)
        payload["crs"] = {"type": "name", "properties": {"name": "EPSG:3857"}}
        self.snapshot(payload=payload)
        self.assertEqual(self.run_selection()["diagnostics"][0]["code"], "SNAPSHOT_CRS_CONFLICT")

    def test_missing_and_wrong_type_building_ids(self):
        for key in [None, True, 123, "", "   "]:
            with self.subTest(id=key):
                f = self.rectangle()
                f["properties"]["building_id"] = key
                self.assert_record_reason(f, "BUILDING_ID_MISSING")

    def test_conflicting_feature_and_property_identity(self):
        f = self.rectangle()
        f["id"] = "different-building"
        self.assert_record_reason(f, "BUILDING_ID_CONFLICT")

    def test_duplicate_ids_reject_all_occurrences(self):
        a, b = self.rectangle("repeat"), self.rectangle("repeat", dx=30)
        self.snapshot([a, b, self.rectangle("independent", dx=50)])
        r = self.run_selection()
        self.assertEqual(r["status"], "PARTIAL")
        self.assertEqual([x["building_id"] for x in r["selected"]], ["independent"])
        self.assertEqual([x["code"] for x in r["reject_ledger"]], ["DUPLICATE_BUILDING_ID"] * 2)
        self.assertFalse(r["summary"]["complete_for_selection"])

    def test_missing_attributes_not_inferred_as_null(self):
        for key in ["class", "subclass"]:
            f = self.rectangle()
            del f["properties"][key]
            self.assert_record_reason(f, "ATTRIBUTE_REQUIRED")

    def test_wrong_types_and_unusable_numeric_attributes(self):
        for key, val in [("class", []), ("subclass", 2), ("num_floors", "2"), ("height", True), ("height", -1)]:
            with self.subTest(key=key, val=val):
                f = self.rectangle()
                f["properties"][key] = val
                self.assert_record_reason(f, "ATTRIBUTE_TYPE")

    def test_record_and_properties_structures(self):
        for f,code in [(None,"FEATURE_INVALID"),([],"FEATURE_INVALID"),
            ({"type":"Point"},"FEATURE_INVALID"),({"type":"Feature","properties":None},"PROPERTIES_INVALID")]:
            with self.subTest(feature=f):self.assert_record_reason(f,code)

    def test_nonfinite_foreign_metadata_cannot_break_json_output(self):
        f=self.rectangle();f["properties"]["unused_value"]="OVERFLOW_MARKER"
        raw=json.dumps({"type":"FeatureCollection","features":[f]}).replace('"OVERFLOW_MARKER"','1e400').encode()
        self.snapshot([f],raw=raw);r=self.run_selection()
        self.assertEqual(r["reject_ledger"][0]["code"],"RECORD_NONFINITE")
        json.dumps(r,allow_nan=False)

    def test_null_optional_floor_and_household_preserved_without_calculation(self):
        f = self.rectangle()
        f["properties"].update(height=None, num_floors=None, household=None)
        self.snapshot([f])
        r = self.run_selection()
        self.assertEqual(r["status"], "SUCCEEDED")
        self.assertIsNone(r["selected"][0]["raw_properties"]["household"])
        self.assertNotIn("household", r["selected"][0])

    def test_missing_null_empty_unsupported_and_invalid_geometry(self):
        for geom, reason in [(None, "GEOMETRY_MISSING"), ({"type":"Polygon","coordinates":[]}, "GEOMETRY_EMPTY"),
                             ({"type":"Point","coordinates":[106.81,-6.43]}, "GEOMETRY_TYPE")]:
            with self.subTest(reason=reason):
                f = self.rectangle();f["geometry"] = geom
                self.assert_record_reason(f, reason)
        f = self.rectangle()
        ring = f["geometry"]["coordinates"][0]
        f["geometry"]["coordinates"] = [[ring[0],ring[2],ring[1],ring[3],ring[0]]]
        self.assert_record_reason(f, "GEOMETRY_INVALID")

    def test_unclosed_short_and_three_dimensional_rings_rejected(self):
        base = self.rectangle()
        ring = base["geometry"]["coordinates"][0]
        for coords in [ring[:-1], ring[:3], [[*p,0] for p in ring]]:
            f = deepcopy(base);f["geometry"]["coordinates"] = [coords]
            self.assert_record_reason(f, "GEOMETRY_COORDINATES")

    def test_coordinate_ranges_axis_order_and_nonfinite(self):
        for point, reason in [([181,0],"COORDINATE_RANGE"), ([0,91],"COORDINATE_RANGE"),
                              ([-6.43,106.81],"COORDINATE_RANGE"), ([True,-6.43],"GEOMETRY_COORDINATES")]:
            f = self.rectangle();f["geometry"]["coordinates"][0][0] = point
            self.assert_record_reason(f, reason)
        f = self.rectangle();f["properties"]["height"] = "NONFINITE_MARKER"
        raw = json.dumps({"type":"FeatureCollection","features":[f]}).replace('"NONFINITE_MARKER"','1e400').encode()
        self.snapshot([f],raw=raw)
        r = self.run_selection()
        self.assertEqual(r["reject_ledger"][0]["code"], "ATTRIBUTE_TYPE")
        json.dumps(r,allow_nan=False)

    def test_footprint_utm_domain_not_inferred_from_magnitude(self):
        f = self.rectangle()
        for point in f["geometry"]["coordinates"][0]:point[0] = 110.0
        self.assert_record_reason(f, "GEOMETRY_CRS_DOMAIN")

    def test_projected_area_and_representative_distance(self):
        self.snapshot([self.rectangle(width=10,height=12,dx=100)])
        r = self.run_selection()
        row = r["selected"][0]
        self.assertAlmostEqual(row["area_m2"],120,delta=1e-5)
        self.assertAlmostEqual(row["distance_to_store_m"],100,delta=1e-5)
        self.assertEqual(row["metric_crs"],"EPSG:32748")
        self.assertEqual(row["geometry"],self.rectangle(width=10,height=12,dx=100)["geometry"])

    def test_radius_inclusion_exclusion_geometry(self):
        self.snapshot([self.rectangle("inside",dx=399.9),self.rectangle("outside",dx=400.1)])
        r = self.run_selection()
        self.assertEqual([x["building_id"] for x in r["selected"]],["inside"])
        self.assertEqual(r["reject_ledger"][0]["code"],"OUTSIDE_RADIUS")
        self.assertEqual(r["reject_ledger"][0]["disposition"],"EXCLUDED")

    def test_full_footprint_not_clipped_to_radius(self):
        self.snapshot([self.rectangle(width=1000,height=20,dx=390,cls="hotel")])
        row = self.run_selection()["selected"][0]
        self.assertAlmostEqual(row["area_m2"],20000,delta=.001)
        self.assertLess(row["distance_to_store_m"],400)

    def test_multipolygon_area(self):
        a,b = self.rectangle(width=10,height=10),self.rectangle(width=10,height=10,dx=30)
        a["geometry"] = {"type":"MultiPolygon","coordinates":[a["geometry"]["coordinates"],b["geometry"]["coordinates"]]}
        self.snapshot([a])
        self.assertAlmostEqual(self.run_selection()["selected"][0]["area_m2"],200,delta=1e-5)

    def test_polygon_hole_area(self):
        outer,inner = self.rectangle(width=20,height=20),self.rectangle(width=10,height=10)
        outer["geometry"]["coordinates"].append(inner["geometry"]["coordinates"][0])
        self.snapshot([outer])
        self.assertAlmostEqual(self.run_selection()["selected"][0]["area_m2"],300,delta=1e-5)

    def test_concave_point_on_surface_is_not_centroid(self):
        f = self.rectangle()
        to_metric=Transformer.from_crs(4326,32748,always_xy=True);to_geo=Transformer.from_crs(32748,4326,always_xy=True)
        x,y=to_metric.transform(106.81,-6.43)
        coords=[list(to_geo.transform(x+a,y+b)) for a,b in [(0,0),(30,0),(30,4),(4,4),(4,26),(30,26),(30,30),(0,30),(0,0)]]
        f["geometry"]["coordinates"]=[coords]
        self.snapshot([f]);row=self.run_selection()["selected"][0]
        geom=ogr.CreateGeometryFromJson(json.dumps(f["geometry"]))
        point=ogr.CreateGeometryFromJson(json.dumps(row["representative_point"]))
        self.assertTrue(geom.Contains(point))
        self.assertFalse(geom.Contains(geom.Centroid()))

    def test_crs_zone_and_hemisphere_are_configurable(self):
        self.c["target"].update(latitude=13.0,longitude=100.0)
        self.c["config"]["area_coverage"]["metric_crs"]="EPSG:32647"
        self.snapshot([self.rectangle(width=10,height=10)])
        row=self.run_selection()["selected"][0]
        self.assertAlmostEqual(row["area_m2"],100,delta=1e-5)
        self.assertEqual(row["metric_crs"],"EPSG:32647")

    def test_empty_and_zero_qualifying_snapshots_are_successful(self):
        for features in [[],[self.rectangle(dx=500)]]:
            with self.subTest(count=len(features)):
                self.snapshot(features)
                r=self.run_selection()
                self.assertEqual(r["status"],"SUCCEEDED",r)
                self.assertEqual(r["summary"]["selected"],0)
                self.assertTrue(r["summary"]["complete_for_selection"])

    def test_reconciliation_of_all_three_dispositions(self):
        invalid=self.rectangle("bad");invalid["geometry"]=None
        self.snapshot([self.rectangle("ok"),self.rectangle("outside",dx=500),invalid])
        r=self.run_selection();s=r["summary"]
        self.assertEqual((s["selected"],s["excluded"],s["rejected"]),(1,1,1))
        indices=[x["source_row_index"] for x in r["selected"]+r["reject_ledger"]]
        self.assertEqual(sorted(indices),[0,1,2]);self.assertEqual(s["accounted_records"],s["source_records"])
        for row in r["reject_ledger"]:
            self.assertEqual(row["analysis_run_id"],self.c["analysis_run_id"])
            self.assertEqual(row["config_hash"],canonical_hash(self.c["config"]))

    def test_repeatability_and_no_mutation(self):
        old=deepcopy((self.c,self.m));before={p.name:p.read_bytes() for p in self.root.iterdir()}
        a=self.run_selection(rebind=False);b=self.run_selection(rebind=False)
        self.assertEqual(a,b);self.assertEqual(old,(self.c,self.m))
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})

    def test_no_network_no_dataset_driver_and_no_writes(self):
        with patch.object(socket,"socket",side_effect=AssertionError("Network forbidden")),patch.object(ogr,"Open",side_effect=AssertionError("Dataset driver forbidden")),patch.object(Path,"write_bytes",side_effect=AssertionError("Write forbidden")),patch.object(Path,"write_text",side_effect=AssertionError("Write forbidden")):
            self.assertEqual(self.run_selection()["status"],"SUCCEEDED")

    def test_missing_backend_is_explicit_blocker(self):
        with patch("location_intelligent_buildings._backend",side_effect=ImportError()):
            r=self.run_selection()
        self.assertEqual(r["status"],"BLOCKED");self.assertIsNone(r["summary"])
        self.assertEqual(r["diagnostics"][0]["code"],"GEOMETRY_BACKEND_UNAVAILABLE")

    def test_cli_smoke_without_credentials(self):
        cmd=[sys.executable,"-B",str(HELPER),"--context",str(self.root/"context.json"),"--manifest",str(self.root/"manifest.json"),"--root",str(self.root),"--source-ref","fixture-buildings"]
        r=subprocess.run(cmd,capture_output=True,text=True,env={"PROJ_NETWORK":"OFF","PYTHONDONTWRITEBYTECODE":"1"})
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)["summary"]["selected"],5)

    def test_cli_missing_or_malformed_inputs_block(self):
        (self.root/"context.json").write_text("{")
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            code=main(["--context",str(self.root/"context.json"),"--manifest",str(self.root/"manifest.json"),"--root",str(self.root),"--source-ref","fixture-buildings"])
        self.assertEqual(code,2);self.assertIsNone(json.loads(output.getvalue())["summary"])

    def test_cli_partial_and_failed_exit_codes(self):
        for expected,raw in [(3,None),(1,b"{")]:
            with self.subTest(expected=expected):
                f=self.rectangle();f["geometry"]=None
                self.snapshot([f],raw=raw)
                (self.root/"manifest.json").write_text(json.dumps(self.m))
                output=io.StringIO()
                with contextlib.redirect_stdout(output):
                    code=main(["--context",str(self.root/"context.json"),"--manifest",str(self.root/"manifest.json"),"--root",str(self.root),"--source-ref","fixture-buildings"])
                self.assertEqual(code,expected,output.getvalue())


class PureReferenceRulesTests(unittest.TestCase):
    def test_exact_numeric_radius_and_area_boundaries(self):
        for distance,area,kind,expected in [(400,100,"standard_residential",None),
            (400.0001,100,"standard_residential","OUTSIDE_RADIUS"),
            (0,44.999,"standard_residential","AREA_NOT_ABOVE_MIN"),
            (0,45,"standard_residential","AREA_NOT_ABOVE_MIN"),(0,45.001,"standard_residential",None),
            (0,549.999,"standard_residential",None),(0,550,"standard_residential","AREA_NOT_BELOW_MAX"),
            (0,550.001,"standard_residential","AREA_NOT_BELOW_MAX"),(0,550,"apartment",None),
            (0,1000,"hotel",None),(0,45,"dormitory","AREA_NOT_ABOVE_MIN")]:
            with self.subTest(distance=distance,area=area,kind=kind):
                self.assertEqual(selection_reason(distance,area,kind,radius=400,minimum=45,maximum=550),expected)

    def test_classification_precedence_and_null_subtype_fallback(self):
        for cls,sub,expected in [(" APARTMENTS ","commercial","apartment"),("dormitory","residential","dormitory"),
            ("HOTEL",None,"hotel"),(None,None,"standard_residential"),("office",None,"standard_residential"),
            ("office"," RESIDENTIAL ","standard_residential"),("office","commercial",None)]:
            with self.subTest(cls=cls,sub=sub):self.assertEqual(classify_building(cls,sub),expected)


if __name__ == "__main__":
    unittest.main()
