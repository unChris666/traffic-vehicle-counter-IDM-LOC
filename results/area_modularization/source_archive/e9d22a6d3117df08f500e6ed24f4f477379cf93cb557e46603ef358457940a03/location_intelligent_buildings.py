"""LI-1: local canonical GeoJSON validation/selection, no capacity or routing.

Uses installed GDAL/OGR (GEOS PointOnSurface) and OSR/PROJ with explicit XY.
Imports geometry dependencies only after the LI-0 input gate passes.
No dataset driver, URL opener, geometry repair, implicit CRS or source fetch.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from location_intelligent_validator import (
    _reject_constant, _strict_pairs, canonical_hash, validate, validate_files,
)


SCHEMA = "li_building_snapshot_v1"
RESULT_SCHEMA = "location_intelligent_building_selection_v1"
RULE_VERSION = "N1_BUILDING_SELECTION_V1"
SPECIAL = {"apartments": "apartment", "dormitory": "dormitory", "hotel": "hotel"}
MESSAGES = {
    "FEATURE_INVALID": "Each row must be a GeoJSON Feature object.",
    "PROPERTIES_INVALID": "Supply a properties object with canonical building attributes.",
    "BUILDING_ID_MISSING": "Supply a nonempty stable string building_id; no ID is generated.",
    "BUILDING_ID_CONFLICT": "Feature ID and canonical building_id must identify the same source record.",
    "DUPLICATE_BUILDING_ID": "All occurrences of this source ID are rejected; no arbitrary winner is selected.",
    "ATTRIBUTE_REQUIRED": "Supply class and subclass explicitly; null is allowed, omission is not a value.",
    "ATTRIBUTE_TYPE": "Class/subclass must be string or null; optional floors/height must be finite positive numbers or null.",
    "RECORD_NONFINITE": "Record metadata/geometry contains a nonfinite or unusable number; no output value is fabricated.",
    "GEOMETRY_MISSING": "Supply a non-null footprint geometry.",
    "GEOMETRY_TYPE": "Only 2D Polygon and MultiPolygon footprints are supported.",
    "GEOMETRY_EMPTY": "Empty footprints or rings do not provide a usable building geometry.",
    "GEOMETRY_COORDINATES": "Supply closed rings with at least four explicit finite [longitude,latitude] positions.",
    "COORDINATE_RANGE": "Coordinates must lie within EPSG:4326 longitude/latitude ranges.",
    "GEOMETRY_INVALID": "Invalid polygon topology is rejected; no automatic repair is performed.",
    "GEOMETRY_CRS_DOMAIN": "Footprint lies outside the declared supported UTM zone/hemisphere domain.",
    "GEOMETRY_TRANSFORM": "Metric transformation or representative-point/area calculation failed.",
    "OUTSIDE_RADIUS": "A valid representative point lies outside the configured building radius.",
    "CLASS_UNSUPPORTED": "Neither a supported special class nor null/empty/residential subtype applies.",
    "AREA_NOT_ABOVE_MIN": "Full projected footprint area must be strictly greater than min_area_m2.",
    "AREA_BELOW_MIN": "Full projected footprint area must be at least min_area_m2 in the market profile.",
    "AREA_NOT_BELOW_MAX": "Standard residential footprint area must be strictly smaller than max_area_m2.",
}


def classify_building(building_class: str | None, subclass: str | None) -> str | None:
    """N1 cell6/cell10 precedence; null subtype fallback is intentionally retained."""
    cls = (building_class or "").strip().lower()
    subtype = (subclass or "").strip().lower()
    if cls in SPECIAL:
        return SPECIAL[cls]
    return "standard_residential" if subtype in ("", "residential") else None


def selection_reason(distance: float, area: float, building_type: str | None,
                     *, radius: float, minimum: float, maximum: float,
                     minimum_inclusive: bool = False) -> str | None:
    """Full precision, order and strictness match N1; no jitter tolerance/rounding."""
    if distance > radius:
        return "OUTSIDE_RADIUS"
    if building_type is None:
        return "CLASS_UNSUPPORTED"
    if (area < minimum if minimum_inclusive else area <= minimum):
        return "AREA_BELOW_MIN" if minimum_inclusive else "AREA_NOT_ABOVE_MIN"
    if building_type == "standard_residential" and area >= maximum:
        return "AREA_NOT_BELOW_MAX"
    return None


def _finite(value: Any) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _unicode(value: Any) -> None:
    if isinstance(value, str):
        value.encode("utf-8")
    elif isinstance(value, dict):
        for key, item in value.items():
            key.encode("utf-8")
            _unicode(item)
    elif isinstance(value, list):
        for item in value:
            _unicode(item)


def _finite_json(value: Any) -> bool:
    if isinstance(value, dict):
        return all(_finite_json(item) for item in value.values())
    if isinstance(value, list):
        return all(_finite_json(item) for item in value)
    return _finite(value) if type(value) in (int, float) else True


def _rings(geometry: Any) -> tuple[list, str | None]:
    if geometry is None:
        return [], "GEOMETRY_MISSING"
    if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon"):
        return [], "GEOMETRY_TYPE"
    coords = geometry.get("coordinates")
    if not isinstance(coords, list):
        return [], "GEOMETRY_COORDINATES"
    if not coords:
        return [], "GEOMETRY_EMPTY"
    polygons = [coords] if geometry["type"] == "Polygon" else coords
    rings = []
    for polygon in polygons:
        if not isinstance(polygon, list):
            return [], "GEOMETRY_COORDINATES"
        if not polygon:
            return [], "GEOMETRY_EMPTY"
        for ring in polygon:
            if not isinstance(ring, list):
                return [], "GEOMETRY_COORDINATES"
            if not ring:
                return [], "GEOMETRY_EMPTY"
            if len(ring) < 4:
                return [], "GEOMETRY_COORDINATES"
            for xy in ring:
                if not isinstance(xy, list) or len(xy) != 2 or not all(_finite(v) for v in xy):
                    return [], "GEOMETRY_COORDINATES"
                if not (-180 <= xy[0] <= 180 and -90 <= xy[1] <= 90):
                    return [], "COORDINATE_RANGE"
            if ring[0] != ring[-1]:
                return [], "GEOMETRY_COORDINATES"
            rings.append(ring)
    return rings, None


def _backend():
    # No global dependency/environment modification; OGR parses an in-memory
    # geometry only. It never opens a dataset driver or a remote data source.
    from osgeo import gdal, ogr, osr
    return gdal, ogr, osr


def _spatial(crs: str, target: dict, ogr, osr):
    wgs, local = osr.SpatialReference(), osr.SpatialReference()
    if wgs.ImportFromEPSG(4326) != 0 or local.ImportFromEPSG(int(crs.split(":")[1])) != 0:
        raise ValueError("Unsupported spatial reference")
    for ref in (wgs, local):
        ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(wgs, local)
    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint_2D(target["longitude"], target["latitude"])
    if point.Transform(transform) != 0:
        raise ValueError("Target projection failed")
    return transform, point


def _measure(geometry: dict, crs: str, transform, target, ogr, gdal):
    rings, reason = _rings(geometry)
    if reason:
        return None, reason
    # Conservative ordinary UTM domain, same explicit gate as LI-0. No zone
    # auto-selection, geodesic fallback or projection of out-of-domain vertices.
    zone, south = int(crs[-2:]), crs.startswith("EPSG:327")
    for ring in rings:
        for lon, lat in ring:
            if not (-80 <= lat <= 84 and (lat <= 0 if south else lat >= 0)
                    and -180 + 6 * (zone - 1) <= lon <= -180 + 6 * zone):
                return None, "GEOMETRY_CRS_DOMAIN"
    try:
        # Keep native GEOS diagnostics out of the deterministic ledger/stderr.
        with gdal.quiet_errors():
            geom = ogr.CreateGeometryFromJson(json.dumps(geometry, allow_nan=False))
            if geom is None or geom.IsEmpty():
                return None, "GEOMETRY_EMPTY"
            if not geom.IsValid():
                return None, "GEOMETRY_INVALID"
            representative = geom.PointOnSurface()
            if representative is None or representative.IsEmpty():
                return None, "GEOMETRY_TRANSFORM"
            # N1 obtains PointOnSurface BEFORE projection; projected centroid
            # or PointOnSurface on the projected polygon is a different rule.
            lon, lat = representative.GetX(), representative.GetY()
            metric_rep, metric_geom = representative.Clone(), geom.Clone()
            if metric_rep.Transform(transform) != 0 or metric_geom.Transform(transform) != 0:
                return None, "GEOMETRY_TRANSFORM"
            if not metric_geom.IsValid():
                return None, "GEOMETRY_TRANSFORM"
            area, distance = metric_geom.GetArea(), metric_rep.Distance(target)
        if not _finite(area) or not _finite(distance) or area <= 0 or distance < 0:
            return None, "GEOMETRY_TRANSFORM"
        return {"area_m2": area, "distance_to_store_m": distance,
                "representative_point": {"type": "Point", "coordinates": [lon, lat]},
                "lat": lat, "lon": lon}, None
    except (RuntimeError, ValueError, TypeError, OverflowError):
        return None, "GEOMETRY_TRANSFORM"


def select_buildings(context: Any, manifest: Any, *, root: Path | str,
                     source_ref_id: str) -> dict:
    """Return a deterministic local selection and one disposition per source row.

    Every invocation verifies LI-0 and the exact bytes consumed. A successful
    empty snapshot has count0; source failures have summary=null, never count0.
    """
    gate = validate(context, manifest, root=root)
    result = {"schema_version": RESULT_SCHEMA, "status": "BLOCKED", "live_readiness": "NOT_VERIFIED",
              "analysis_run_id": context.get("analysis_run_id") if isinstance(context, dict) else None,
              "rule_version": RULE_VERSION, "li0": gate, "snapshot": None,
              "summary": None, "selected": [], "reject_ledger": [], "diagnostics": [],
              "limitations": ["Reference building selection only; not routing/accessibility or capacity.",
                              "Declared coverage is not verified geographic completeness.",
                              "Synthetic fixtures do not validate live Overture integration."]}

    def fail(code, message, status="FAILED"):
        result["status"] = status
        result["diagnostics"].append({"code": code, "message": message})
        return result

    if gate["offline_readiness"] != "READY":
        return fail("LI0_GATE_BLOCKED", "Correct invalid or unavailable required LI-0 inputs first.", "BLOCKED")
    area_run = next(r for r in manifest["modules"] if r["module"] == "area_coverage")
    source = next((s for s in manifest["sources"] if s["source_ref_id"] == source_ref_id), None)
    if source is None or source_ref_id not in area_run["required_inputs"] or source["inventory_id"] != "SRC04":
        return fail("SOURCE_BINDING_INVALID", "Select an SRC04 source explicitly required by this area module.")
    result["snapshot"] = {"source_ref_id": source_ref_id, "fingerprint": deepcopy(source["fingerprint"]),
                          "schema_version": source["schema_version"], "provider": source["provider"],
                          "source_version": source["source_version"], "source_as_of": source["source_as_of"],
                          "acquisition_mode": source["acquisition_mode"], "provenance": deepcopy(source["provenance"]),
                          "coverage": deepcopy(source["coverage"]), "crs": source["crs"],
                          "context_hash": context["context_hash"], "config_hash": canonical_hash(context["config"])}
    if source["schema_version"] != SCHEMA:
        return fail("SNAPSHOT_SCHEMA_UNSUPPORTED", f"Supply the canonical local {SCHEMA} payload; no provider schema is inferred.")
    if source["crs"] != "EPSG:4326" or source["units"].get("coordinates") != "degree":
        return fail("SNAPSHOT_CRS_INVALID", "Canonical GeoJSON requires explicit EPSG:4326 [lon,lat] and degree units in SourceRef.")
    locator = source.get("local_path") or source["locator"]
    path = Path(locator) if Path(locator).is_absolute() else Path(root) / locator
    if path.suffix.lower() not in (".json", ".geojson"):
        return fail("SNAPSHOT_FORMAT_UNSUPPORTED", "Only canonical local JSON/GeoJSON FeatureCollection is supported.")
    try:
        if not path.is_file():
            return fail("SNAPSHOT_UNAVAILABLE", "Snapshot must remain an available regular local file.")
        raw = path.read_bytes()
        if len(raw) != source["byte_count"] or hashlib.sha256(raw).hexdigest() != source["fingerprint"]["value"]:
            return fail("SNAPSHOT_CHANGED", "The bytes consumed no longer match the immutable manifest reference.")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_pairs, parse_constant=_reject_constant)
        _unicode(data)
    except OSError:
        return fail("SNAPSHOT_UNREADABLE", "Local snapshot cannot be read; no live fallback is attempted.")
    except (ValueError, UnicodeError, RecursionError):
        return fail("SNAPSHOT_JSON_INVALID", "Supply strict UTF-8 JSON with unique keys and valid Unicode.")
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        return fail("SNAPSHOT_SCHEMA_INVALID", "Snapshot must contain type=FeatureCollection and an array of features.")
    if "crs" in data and data["crs"] != {"type": "name", "properties": {"name": "EPSG:4326"}}:
        return fail("SNAPSHOT_CRS_CONFLICT", "Payload CRS declaration conflicts with the supported canonical CRS.")
    features = data["features"]
    if len(features) != source["row_count"]:
        return fail("SNAPSHOT_ROW_COUNT_MISMATCH", "Feature count must match the manifest's observed row_count.")
    try:
        gdal, ogr, osr = _backend()
        if ogr.GetGEOSVersionMajor() < 1:
            raise ImportError("GEOS support required")
        crs = context["config"]["area_coverage"]["metric_crs"]
        with osr.ExceptionMgr(useExceptions=True):
            transform, target = _spatial(crs, context["target"], ogr, osr)
    except (ImportError, OSError):
        return fail("GEOMETRY_BACKEND_UNAVAILABLE", "Use an offline environment with GDAL/OGR, GEOS and PROJ installed.", "BLOCKED")
    except (RuntimeError, ValueError):
        return fail("GEOMETRY_BACKEND_FAILED", "Check local CRS support and transform initialization.")
    result["backend"] = {"gdal": gdal.VersionInfo("RELEASE_NAME"),
                         "geos": f"{ogr.GetGEOSVersionMajor()}.{ogr.GetGEOSVersionMinor()}.{ogr.GetGEOSVersionMicro()}",
                         "proj": f"{osr.GetPROJVersionMajor()}.{osr.GetPROJVersionMinor()}.{osr.GetPROJVersionMicro()}",
                         "metric_crs": crs, "axis_order": "XY", "representative_point": "GEOS PointOnSurface in EPSG:4326 before projection"}
    ids = []
    for f in features:
        props = f.get("properties") if isinstance(f, dict) else None
        key = props.get("building_id") if isinstance(props, dict) else None
        ids.append(key if isinstance(key, str) and key.strip() else None)
    duplicates = {key for key, count in Counter(x for x in ids if x is not None).items() if count > 1}
    params = context["config"]["area_coverage"]["parameters"]
    controls = {"radius": params["building_radius_m"]["value"], "minimum": params["min_area_m2"]["value"],
                "maximum": params["max_area_m2"]["value"]}
    if context['config']['version'] == 'area-market-ge36-v1':
        controls['minimum_inclusive'] = True
        result['rule_version'] = 'MARKET_BUILDING_SELECTION_GE_MIN_V1'
    fingerprint = source["fingerprint"]["value"]

    def reject(index, key, stage, code, field, metrics=None):
        result["reject_ledger"].append({"analysis_run_id": context["analysis_run_id"],
            "source_ref_id": source_ref_id, "snapshot_sha256": fingerprint,
            "source_row_index": index, "building_id": key, "stage": stage,
            "disposition": "EXCLUDED" if stage == "SELECTION" else "REJECTED",
            "code": code, "message": MESSAGES[code], "field": field,
            "context_hash": context["context_hash"], "config_hash": result["snapshot"]["config_hash"],
            "rule_version": result['rule_version'], "metrics": metrics})

    for index, feature in enumerate(features):
        key = ids[index]
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            reject(index, key, "PAYLOAD", "FEATURE_INVALID", "type")
            continue
        props = feature.get("properties")
        if not isinstance(props, dict):
            reject(index, key, "PAYLOAD", "PROPERTIES_INVALID", "properties")
            continue
        if key is None:
            reject(index, None, "IDENTITY", "BUILDING_ID_MISSING", "properties.building_id")
            continue
        if key in duplicates:
            reject(index, key, "IDENTITY", "DUPLICATE_BUILDING_ID", "properties.building_id")
            continue
        if "id" in feature and feature["id"] != key:
            reject(index, key, "IDENTITY", "BUILDING_ID_CONFLICT", "id")
            continue
        if "class" not in props or "subclass" not in props:
            reject(index, key, "PAYLOAD", "ATTRIBUTE_REQUIRED", "properties.class/subclass")
            continue
        if any(props[k] is not None and not isinstance(props[k], str) for k in ("class", "subclass")) or any(
                props.get(k) is not None and (not _finite(props[k]) or props[k] <= 0) for k in ("num_floors", "height")):
            reject(index, key, "PAYLOAD", "ATTRIBUTE_TYPE", "properties")
            continue
        if not _finite_json(feature):
            reject(index, key, "PAYLOAD", "RECORD_NONFINITE", "feature")
            continue
        metrics, reason = _measure(feature.get("geometry"), crs, transform, target, ogr, gdal)
        if reason:
            reject(index, key, "GEOMETRY", reason, "geometry")
            continue
        kind = classify_building(props["class"], props["subclass"])
        reason = selection_reason(metrics["distance_to_store_m"], metrics["area_m2"], kind, **controls)
        if reason:
            reject(index, key, "SELECTION", reason, "geometry/class/subclass", metrics)
            continue
        result["selected"].append({"analysis_run_id": context["analysis_run_id"], "source_ref_id": source_ref_id,
            "source_row_index": index, "building_id": key, "snapshot_sha256": fingerprint,
            "building_key": {"provider": source["provider"], "source_version": source["source_version"],
                             "snapshot_sha256": fingerprint, "building_id": key},
            "class": props["class"], "subclass": (props["subclass"] or "").strip().lower() or None,
            "building_type": kind, "geometry": deepcopy(feature["geometry"]), "metric_crs": crs,
            "raw_properties": deepcopy(props), **metrics})
    rejected = sum(r["disposition"] == "REJECTED" for r in result["reject_ledger"])
    excluded = len(result["reject_ledger"]) - rejected
    result["summary"] = {"source_records": len(features), "selected": len(result["selected"]),
                         "excluded": excluded, "rejected": rejected,
                         "accounted_records": len(result["selected"]) + len(result["reject_ledger"]),
                         "complete_for_selection": rejected == 0,
                         "reason_counts": dict(sorted(Counter(r["code"] for r in result["reject_ledger"]).items()))}
    assert result["summary"]["accounted_records"] == len(features)
    result["status"] = "PARTIAL" if rejected else "SUCCEEDED"
    if duplicates:
        result["diagnostics"].append({"code": "SNAPSHOT_IDENTITY_CONFLICT", "message": "Repeated source IDs affect snapshot integrity; all occurrences are held outside selected records."})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("context", "manifest", "root"):
        parser.add_argument(f"--{key}", required=True, type=Path)
    parser.add_argument("--source-ref", required=True)
    args = parser.parse_args(argv)
    gate = validate_files(args.context, args.manifest, root=args.root)
    if gate["offline_readiness"] != "READY":
        result = {"schema_version": RESULT_SCHEMA, "status": "BLOCKED", "li0": gate,
                  "summary": None, "live_readiness": "NOT_VERIFIED"}
    else:
        # Already strictly validated; no fallback input or remote source.
        try:
            with args.context.open(encoding="utf-8") as stream:
                context = json.load(stream, object_pairs_hook=_strict_pairs, parse_constant=_reject_constant)
            with args.manifest.open(encoding="utf-8") as stream:
                manifest = json.load(stream, object_pairs_hook=_strict_pairs, parse_constant=_reject_constant)
            result = select_buildings(context, manifest, root=args.root, source_ref_id=args.source_ref)
        except (OSError, ValueError, RecursionError):
            result = {"schema_version": RESULT_SCHEMA, "status": "FAILED", "summary": None,
                      "live_readiness": "NOT_VERIFIED", "diagnostics": [{"code": "INPUT_CHANGED",
                      "message": "Context/manifest changed after validation; supply stable local inputs."}]}
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False))
    return {"SUCCEEDED": 0, "PARTIAL": 3, "BLOCKED": 2, "FAILED": 1}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
