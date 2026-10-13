#!/usr/bin/env python3
"""Read retained snapshots; compare bounded physical-passage review references.

This postprocessor never imports or executes the detector, tracker, encoder,
geometry state machine, or identity resolver. The default case roster selects
the user-requested audit cases; it is not a rule in the counting algorithm.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path


DEFAULT_CASE_ROSTER = [
    {"case_id": "car1", "vehicle_track_ids": [1], "component_track_ids": [],
     "pixel_case_id": None, "reference_category": "car"},
    {"case_id": "motorcycle923_rider912", "vehicle_track_ids": [923],
     "component_track_ids": [912], "pixel_case_id": "motorcycle923_rider912",
     "reference_category": "motorcycle"},
    {"case_id": "red_scooter964_973_rider967", "vehicle_track_ids": [964, 973],
     "component_track_ids": [967], "pixel_case_id": "duplicate964_973",
     "reference_category": "motorcycle"},
    {"case_id": "car1323", "vehicle_track_ids": [1323], "component_track_ids": [],
     "pixel_case_id": "car1323", "reference_category": "car"},
    {"case_id": "motorcycle1772_rider1774", "vehicle_track_ids": [1772],
     "component_track_ids": [1774], "pixel_case_id": "motorcycle1772_rider1774",
     "reference_category": "motorcycle"},
]
SNAPSHOT_NAMES = ["A_original", "A_updated", "episode_only", "B_machine", "B_reviewed"]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def diagnostic_in_scope(row, track_ids, windows):
    """Require source track AND complete crossing/confirmation in one window.

    An AMBIGUOUS_GAP has no accepted crossing; use its own audit frame only.
    Origin may precede a review window and is never changed by this selector.
    """
    if row.get("track_id") not in track_ids:
        return False
    diagnostic = row.get("diagnostic", row.get("geometry_evidence", {}))
    if diagnostic.get("type") == "AMBIGUOUS_GAP":
        frame = diagnostic["frame_index"]
        return any(first <= frame <= last for first, last in windows)
    frames = [diagnostic.get(key) for key in (
        "crossing_frame_start", "crossing_frame_end", "confirmation_frame")]
    if any(frame is None for frame in frames):
        return False
    return any(all(first <= frame <= last for frame in frames) for first, last in windows)


def compact_geometry(diagnostic):
    if diagnostic.get("type") != "GEOMETRY_TRANSITION":
        return {"type": diagnostic.get("type"), "audit_frame": diagnostic.get("frame_index")}
    evidence = diagnostic["crossing_evidence"]
    observations = {
        "origin": diagnostic["origin_observation"],
        "crossing_start": evidence["start_observation"],
        "crossing_end": evidence["end_observation"],
        "confirmation": diagnostic["confirmation_observations"][-1],
    }
    sources = {}
    for name, observation in observations.items():
        metadata = observation["metadata"]
        bbox = metadata["raw_bbox"]
        expected = [(bbox[0] + bbox[2]) / 2, bbox[3]]
        if observation["point"] != expected:
            raise ValueError("Crossing anchor differs from measured raw bbox BC")
        if metadata["track_id"] != diagnostic["track_id"]:
            raise ValueError("Crossing source track differs from diagnostic")
        sources[name] = {
            "frame_index": observation["frame_index"], "track_id": metadata["track_id"],
            "class_name": metadata["class_name"],
            "original_detection_index": metadata["original_detection_index"],
            "raw_bbox": bbox, "raw_bc": expected,
            "measurement_provenance": metadata["measurement_provenance"],
            "video_sha256": metadata["video_sha256"], "variant": metadata["variant"],
            "parent_run_id": metadata["parent_run_id"],
        }
    return {"type": diagnostic["type"], "track_id": diagnostic["track_id"],
            "origin_frame": diagnostic["origin_frame"],
            "crossing_frames": [diagnostic["crossing_frame_start"], diagnostic["crossing_frame_end"]],
            "confirmation_frame": diagnostic["confirmation_frame"],
            "direction": diagnostic["direction"], "source_anchor": "MEASURED_RAW_BBOX_BOTTOM_CENTER",
            "intersection_kind": evidence["intersection"]["kind"],
            "sources": sources}


def compact_decision(row):
    review = row.get("review_decision") or row.get("review") or {}
    return {"candidate_id": row["candidate_id"], "track_id": row["track_id"],
            "status": row["status"], "accepted_count_event": row.get("accepted_count_event", False),
            "event_id": row.get("event_id"), "serialized_category": row.get("category"),
            "review_recorded_category": review.get("category"),
            "reasons": row.get("reasons", []),
            "manual_review_applied": bool(review),
            "physical_unit_id": row.get("physical_unit_id"), "passage_id": row.get("passage_id"),
            "geometry": compact_geometry(row["diagnostic"])}


def event_candidate_ids(event):
    return set(event.get("source_candidate_ids") or event.get("same_passage_candidate_ids")
               or [event.get("candidate_id") or event.get("representative_candidate_id")])


def compact_event(event, episodes):
    geometry = event["geometry_evidence"]
    components = [episodes[episode]["track_id"] for episode in event.get("component_episode_ids", [])]
    manual_component_ids = sorted({track for ref in event.get("review_references", [])
                                   for track in ref["review"].get("manual_component_track_ids", [])})
    return {"event_id": event["event_id"], "category": event["category"],
            "representative_track_id": event.get("track_id", event.get("representative_track_id")),
            "source_candidate_ids": sorted(event_candidate_ids(event)),
            "automatic_acceptance": event.get("automatic_acceptance", not bool(event.get("review_ids"))),
            "manual_review_applied": bool(event.get("manual_review_applied") or event.get("review_ids")),
            "automatic_component_track_ids": sorted(set(components)),
            "manual_component_reference_track_ids": manual_component_ids,
            "geometry": compact_geometry(geometry),
            "category_latest_evidence_frame": event.get("category_decision_latest_evidence_frame"),
            "is_causal_online_decision": event.get("is_causal_online_decision", False),
            "claim_type": event.get("claim_type", "AUDIT_GATED_OPTION_A_REVIEWED_PASSAGE")}


def build_comparison(snapshots, cases, config, episodes, pixel_reviews, association_relations):
    """Generic data-only comparison; audit roster is supplied explicitly."""
    track_ids = set(config["scope"]["track_ids"])
    windows = config["scope"]["association_frame_windows"]
    scoped = {}
    summary = {}
    for name in SNAPSHOT_NAMES:
        decisions, events = snapshots[name]
        subset = [row for row in decisions if diagnostic_in_scope(row, track_ids, windows)]
        candidate_ids = {row["candidate_id"] for row in subset}
        accepted = [event for event in events if event_candidate_ids(event) & candidate_ids]
        if len({event["event_id"] for event in accepted}) != len(accepted):
            raise ValueError("Duplicate accepted event ID in snapshot")
        scoped[name] = (subset, accepted)
        summary[name] = {"audit_items": len(subset),
                         "decision_status_counts": dict(sorted(Counter(r["status"] for r in subset).items())),
                         "accepted_unique_passages": len(accepted),
                         "accepted_by_category": dict(sorted(Counter(e["category"] for e in accepted).items())),
                         "manual_accepted_passages": sum(bool(e.get("manual_review_applied") or e.get("review_ids")) for e in accepted),
                         "automatic_accepted_passages": sum(not bool(e.get("manual_review_applied") or e.get("review_ids")) for e in accepted)}
    passages = []
    for case in cases:
        vehicles = set(case["vehicle_track_ids"])
        case_ids = vehicles | set(case["component_track_ids"])
        row = {**case, "claim_type": "BOUNDED_PHYSICAL_PASSAGE_REVIEW_REFERENCE_NOT_GROUND_TRUTH", "snapshots": {}}
        for name, (decisions, events) in scoped.items():
            vehicle_decisions = [r for r in decisions if r["track_id"] in vehicles]
            component_decisions = [r for r in decisions if r["track_id"] in case_ids - vehicles]
            source_ids = {r["candidate_id"] for r in vehicle_decisions}
            case_events = [e for e in events if event_candidate_ids(e) & source_ids]
            row["snapshots"][name] = {
                "accepted_unique_passages": len(case_events),
                "vehicle_decisions": [compact_decision(r) for r in vehicle_decisions],
                "component_audit_items": [compact_decision(r) for r in component_decisions],
                "accepted_events": [compact_event(e, episodes) for e in case_events],
            }
        row["retained_pixel_review"] = next((review for review in pixel_reviews
                                                if review["case_id"] == case.get("pixel_case_id")), None)
        row["comparison_dimensions"] = {
            "duplicate_review_required": len(vehicles) > 1,
            "no_snapshot_accepts_two_events_for_this_review_reference": all(
                snapshot["accepted_unique_passages"] <= 1 for snapshot in row["snapshots"].values()),
            "category_reference": case["reference_category"],
            "every_accepted_category_matches_case_reference": all(
                event["category"] == case["reference_category"] for snapshot in row["snapshots"].values()
                for event in snapshot["accepted_events"]),
            "accepted_crossing_always_uses_vehicle_source_bc": all(
                event["geometry"]["track_id"] in vehicles
                and all(s["class_name"] in {"motorcycle", "car", "truck", "bus"}
                        for s in event["geometry"]["sources"].values())
                for snapshot in row["snapshots"].values() for event in snapshot["accepted_events"]),
            "source_coordinate_identity_checked": True,
            "false_merge_rate_established": False,
        }
        passages.append(row)
    controls = []
    for review in pixel_reviews:
        if review["case_id"] in {case.get("pixel_case_id") for case in cases}:
            continue
        ids = set(review.get("track_ids", []))
        controls.append({"case_id": review["case_id"], "track_ids": sorted(ids),
                         "scope": "ASSOCIATION_ONLY_NOT_AN_ADDITIONAL_COMPARED_ACCEPTED_PASSAGE",
                         "pixel_review": review,
                         "machine_relations": [r for r in association_relations
                                               if {r["first_track_id"], r["second_track_id"]} <= ids],
                         "count_events_in_comparison_added": False})
    return {"claim_type": "EXECUTED_RETAINED_PER_PASSAGE_COMPARISON_NOT_A_TRAFFIC_BENCHMARK",
            "scope": {"track_ids": sorted(track_ids), "inclusive_frame_windows": windows,
                      "selection": "SOURCE_TRACK_AND_COMPLETE_CROSSING_CONFIRMATION_IN_SAME_WINDOW; gap audit items use their audit frame",
                      "physical_passage_reference_count": len(cases),
                      "A_full_snapshot_18_is_context_only": True,
                      "pending_item_denominators_not_interchangeable": True},
            "formal_ground_truth": False, "whole_video_traffic_count_established": False,
            "models_geometry_or_resolver_rerun": False, "summary": summary,
            "passages": passages, "association_controls": controls,
            "limits": ["Five passage references and bounded pixel reviews do not establish general performance.",
                       "A is reviewed; B_machine is automatic; B_reviewed retains explicit manual decisions.",
                       "The B grouping/category/episode policy differs from A; episode-only isolates removal of grouping, not every changed factor.",
                       "Raw label unanimity on a full vehicle episode is an offline category control, not business taxonomy or online stability.",
                       "Source IDs from separate configuration namespaces must not be appended or summed together.",
                       "A track-only inventory in the executed notebook includes out-of-window880; this postprocessor applies both scope constraints."]}


def markdown(comparison):
    lines = ["# Perbandingan per passage TOR3-PAGI — Opsi A/B", "",
             "**EXPERIMENT RESULT:** pembacaan snapshot retained, tanpa menjalankan model, state machine atau resolver kembali. Scope memakai track **dan** frame crossing/confirmation dalam satu window inklusif. Lima passage adalah reference review terbatas, bukan ground truth atau total lalu lintas.", "",
             "| Snapshot | Accepted passage | Manual | Otomatis | Item keputusan dalam scope |", "|---|---:|---:|---:|---:|"]
    for name, row in comparison["summary"].items():
        lines.append(f"| {name} | {row['accepted_unique_passages']} | {row['manual_accepted_passages']} | {row['automatic_accepted_passages']} | {row['audit_items']} |")
    lines.extend(["", "| Passage / sumber unit | A original | A updated | Episode-only | B machine | B reviewed |", "|---|---|---|---|---|---|"])
    for row in comparison["passages"]:
        statuses = []
        for name in SNAPSHOT_NAMES:
            snapshot = row["snapshots"][name]
            if snapshot["accepted_unique_passages"]:
                event = snapshot["accepted_events"][0]
                statuses.append(f"1 {event['category']}; ID{event['representative_track_id']} "
                                f"({'manual' if event['manual_review_applied'] else 'otomatis'})")
            else:
                statuses.append("pending; " + ", ".join(f"ID{r['track_id']}" for r in snapshot["vehicle_decisions"]))
        lines.append("| " + row["case_id"] + " | " + " | ".join(statuses) + " |")
    lines.extend(["", "## Audit salah gabung, duplikasi, kategori dan sumber crossing", "",
        "- **ID1772/1774:** B mengeluarkan satu motorcycle dari episode kendaraan ID1772, origin7716, crossing7721→7722. Origin person7712 pada A tidak diwarisi; rider1774 crossing7717→7718 tidak menjadi sumber passage kendaraan. Event mesin dipertahankan verbatim pada B reviewed.",
        "- **ID964/973:** A memakai ID973 untuk satu skuter yang sama; ID964 lama mixed person→motorcycle tetap pending. B membuat episode kendaraan baru origin5122 tetapi kedua kandidat otomatis pending. Pair motion residual maksimum0,057293 melampaui kontrol0,01, sehingga deduplikasi otomatis tidak terbukti berhasil. B reviewed secara eksplisit menyatukan satu passage, memilih kendaraan ID964 crossing5128→5129; ID973 menjadi duplicate support tanpa count tambahan.",
        "- **ID923/912:** bukti hubungan yang lolos pada frame5116–5122/5128–5131 tidak membuktikan identitas crossing5028→5029. Gate passage-local v1 menahan kandidat; manual review frame origin5017 dan crossing5028/5029 mengesahkan satu motorcycle pada snapshot reviewed. Hubungan aktual in-window gagal kontrol relative motion; later pixel identity terhadap passage awal tetap UNKNOWN.",
        "- **ID1323:** keputusan pengguna car tersimpan pada A updated review meskipun top-level kategori legacy HOLD tetap null. B raw temporal category car tidak menyelesaikan rawcar kecil/d3 di tepi kendaraan yang physical identity-nya UNKNOWN; seluruh snapshot tetap pending.",
        "- **ID1:** A review mengonfirmasi satu car; overlap motorID3 merupakan kendaraan berbeda. B mempertahankan pending tanpa bukti identitas otomatis positif; B reviewed memakai bukti pixel retained yang sama.",
        "- **Kontrol ID880/892:** review menunjukkan dua kendaraan berbeda; mesin menolak SAME_VEHICLE. Ini satu negative nyata lintas gerakan, bukan bukti generalisasi. COMPONENT_OF893/880 didukung, tetapi crossing kendaraan880 frame4987→4988 di luar window4975–4980; kontrol ini tidak menambah accepted passage pembanding.",
        "", "Semua event accepted menggunakan raw vehicle BC dari source detection yang terhubung ke track. Tidak menggabungkan bbox, mengganti anchor dengan rider atau menyambung trajectory lintas ID. JSON menyimpan bbox/source-index/frame untuk origin, crossing dan confirmation serta keputusan tiap namespace.",
        "", "## Batas", ""])
    lines.extend("- " + limit for limit in comparison["limits"])
    lines.extend(["", "Data lengkap: [JSON](passage_comparison.json), [CSV](passage_comparison.csv).", ""])
    return "\n".join(lines)


def execute(repo, run, original, updated, reviewed, output, case_roster=None):
    repo, run, original, updated, reviewed, output = [Path(p).resolve() for p in (
        repo, run, original, updated, reviewed, output)]
    if output != run:
        output.mkdir(parents=True, exist_ok=True)
    report = read_json(run / "report.json")
    config = read_json(run / "configuration_input.json")
    episodes = {r["episode_id"]: r for r in read_jsonl(run / "episodes.jsonl.gz")}
    cases = read_json(case_roster) if case_roster else DEFAULT_CASE_ROSTER
    snapshots = {}
    inputs = {}
    checks = []

    def check(name, value):
        checks.append({"name": name, "passed": bool(value)})
        if not value:
            raise AssertionError(name)

    for name, directory in [("A_original", original), ("A_updated", updated),
                            ("episode_only", run / "ablation"), ("B_machine", run),
                            ("B_reviewed", reviewed)]:
        decision_file = "resolved_decisions.jsonl.gz" if name in {"A_original", "A_updated", "B_reviewed"} else "machine_decisions.jsonl.gz"
        paths = [directory / decision_file, directory / "accepted_events.jsonl.gz", directory / "aggregate.json"]
        for path in paths:
            inputs[str(path.relative_to(repo))] = sha256(path)
        decisions, events = read_jsonl(paths[0]), read_jsonl(paths[1])
        check(name + " unique candidate IDs", len({r["candidate_id"] for r in decisions}) == len(decisions))
        check(name + " unique accepted event IDs", len({e["event_id"] for e in events}) == len(events))
        check(name + " aggregate reconciles", read_json(paths[2])["total"] == len(events))
        for event in events:
            check(name + " typed accepted " + event["event_id"], event["type"] == "CountEvent" and event["accepted_count_event"] is True)
        if name.startswith("A_"):
            for path in paths[:2]:
                check(name + " retained byte hash " + path.name,
                      report["input_sha256"][name + "/" + path.name] == sha256(path))
        snapshots[name] = (decisions, events)

    for path in [run / "configuration_input.json", run / "report.json", run / "episodes.jsonl.gz",
                 run / "relations.jsonl.gz", reviewed / "report.json", reviewed / "review_input.json",
                 run / "execution_manifest.json", reviewed / "execution_manifest.json"]:
        inputs[str(path.relative_to(repo))] = sha256(path)
    for label, directory in [("B machine", run), ("B reviewed", reviewed)]:
        for artifact in read_json(directory / "execution_manifest.json")["artifacts"]:
            path = directory / artifact["path"]
            check(label + " manifest " + artifact["path"],
                  path.exists() and sha256(path) == artifact["sha256"]
                  and path.stat().st_size == artifact["size_bytes"])

    reviewed_report = read_json(reviewed / "report.json")
    check("reviewed binds final source run", reviewed_report["source_run_id"] == run.name == report["run_id"])
    for filename, digest in reviewed_report["source_artifact_sha256"].items():
        check("reviewed retained original " + filename, sha256(run / filename) == digest)
    pixel_path = repo / "docs/evidence/phase_6/option_b_temporal_review/pixel_review.json"
    pixels = read_json(pixel_path)
    inputs[str(pixel_path.relative_to(repo))] = sha256(pixel_path)
    check("pixel source video matches", pixels["source_video_sha256"] == config["input_identity"]["video_sha256"])
    check("pixel source cache matches", pixels["records_sha256"] == config["input_identity"]["records_sha256"])
    check("pixel source geometry matches", pixels["geometry_sha256"] == config["input_identity"]["geometry_sha256"])
    for review in pixels["reviews"]:
        for evidence in review["evidence"]:
            check("pixel evidence " + evidence["path"], sha256(repo / evidence["path"]) == evidence["sha256"])
    relations = read_jsonl(run / "relations.jsonl.gz")
    result = build_comparison(snapshots, cases, config, episodes, pixels["reviews"], relations)
    check("A strict scope three accepted", result["summary"]["A_original"]["accepted_unique_passages"] == 3)
    check("A strict scope fourteen audit items", result["summary"]["A_original"]["audit_items"] == 14)
    check("A updated strict scope unchanged accepted", result["summary"]["A_updated"]["accepted_unique_passages"] == 3)
    check("B one machine accepted", result["summary"]["B_machine"]["accepted_unique_passages"] == 1)
    check("ablation zero accepted", result["summary"]["episode_only"]["accepted_unique_passages"] == 0)
    check("reviewed four accepted", result["summary"]["B_reviewed"]["accepted_unique_passages"] == 4)
    for row in result["passages"]:
        for dimension in ("no_snapshot_accepts_two_events_for_this_review_reference",
                          "every_accepted_category_matches_case_reference", "accepted_crossing_always_uses_vehicle_source_bc"):
            check(row["case_id"] + " " + dimension, row["comparison_dimensions"][dimension])
        for name, snapshot in row["snapshots"].items():
            for decision in snapshot["vehicle_decisions"] + snapshot["component_audit_items"]:
                for role, source in decision["geometry"].get("sources", {}).items():
                    check(name + " " + decision["candidate_id"] + " " + role + " source namespace",
                          all(source[key] == config["input_identity"][key]
                              for key in ("video_sha256", "variant", "parent_run_id")))
        if row.get("pixel_case_id") is not None:
            check(row["case_id"] + " retains exact pixel case reference", row["retained_pixel_review"] is not None)
    machine_events = snapshots["B_machine"][1]
    reviewed_events = snapshots["B_reviewed"][1]
    check("automatic event preserved verbatim in reviewed", all(event in reviewed_events for event in machine_events))
    result.update({"source_run_id": run.name, "input_identity": config["input_identity"],
                   "input_file_sha256": inputs, "method_sha256": sha256(__file__),
                   "validation": {"checks_run": len(checks), "checks_passed": len(checks), "checks": checks}})
    (output / "passage_comparison.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    (output / "passage_comparison.md").write_text(markdown(result), encoding="utf-8")
    with (output / "passage_comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["case_id", "vehicle_track_ids", "component_track_ids"]
        for name in SNAPSHOT_NAMES:
            fields.extend([name + "_accepted_passages", name + "_representative_track_ids", name + "_vehicle_statuses", name + "_reasons"])
        writer = csv.DictWriter(stream, fields, lineterminator="\n")
        writer.writeheader()
        for case in result["passages"]:
            row = {"case_id": case["case_id"], "vehicle_track_ids": ";".join(map(str, case["vehicle_track_ids"])),
                   "component_track_ids": ";".join(map(str, case["component_track_ids"]))}
            for name, snapshot in case["snapshots"].items():
                row[name + "_accepted_passages"] = snapshot["accepted_unique_passages"]
                row[name + "_representative_track_ids"] = ";".join(str(e["representative_track_id"]) for e in snapshot["accepted_events"])
                row[name + "_vehicle_statuses"] = ";".join(str(r["track_id"]) + ":" + r["status"] for r in snapshot["vehicle_decisions"])
                row[name + "_reasons"] = ";".join(str(r["track_id"]) + ":" + ",".join(r["reasons"]) for r in snapshot["vehicle_decisions"])
            writer.writerow(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--run", required=True)
    parser.add_argument("--original", default="docs/evidence/phase_6/20261012T144625_030645Z")
    parser.add_argument("--updated", default="docs/evidence/phase_6/option_b_a_updated_20261013")
    parser.add_argument("--reviewed")
    parser.add_argument("--output")
    parser.add_argument("--case-roster", help="Optional explicit JSON list of bounded passage review references")
    args = parser.parse_args()
    run = Path(args.run)
    result = execute(args.repo, run, args.original, args.updated, args.reviewed or run / "reviewed",
                     args.output or run, args.case_roster)
    print(json.dumps({"summary": result["summary"], "validation": {key: result["validation"][key]
                     for key in ("checks_run", "checks_passed")}}, indent=2))


if __name__ == "__main__":
    main()
