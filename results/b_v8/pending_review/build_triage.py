"""Read-only evidence triage of all B v7 pending scopes; no pipeline replay."""
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results/b_v8/pending_review"
BASELINE = ROOT / "results/b_v7/execution/pilot_v7_machine_final/weekday_siang/counting_result.json.gz"
ROLE_DECISIONS = ROOT / "results/phase_9/20261020_QC_BV4_SIANG/roles/per_case_decisions.jsonl"
CACHE = Path("/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def artifact(path):
    p = ROOT / path
    assert p.is_file(), p
    return {"path": path, "sha256": sha(p)}


def scope(row):
    return {key: row[key] for key in ("track_id", "physical_unit_id", "episode_id", "passage_id")}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = read(BASELINE)
    source = baseline["source_identity"]
    assert sha(CACHE) == source["records_sha256"]
    pending = [d for d in baseline["decisions"] if d["status"] == "pending"]
    assert len(pending) == 24
    reviews = {r["raw_track_id"]: r for r in map(json.loads, ROLE_DECISIONS.read_text().splitlines())}
    assignments = defaultdict(list)
    for row in baseline["frame_assignments"]:
        assignments[(row["track_id"], row["physical_episode_id"])].append(row)
    diagnostics = {(d["physical_unit_id"], d.get("episode_id"), d["passage_id"]): d
                   for d in baseline["open_passage_diagnostics"]}
    desired = {d["source_ref"]["frame_index"] for d in pending}
    for d in pending:
        if d["track_id"] in reviews:
            desired.update(reviews[d["track_id"]]["role_scope"]["positive_raw_person_sample_frames"])
    rows_by_frame = {}
    with gzip.open(CACHE, "rt") as handle:
        for line in handle:
            row = json.loads(line)
            if row["frame_index"] in desired:
                rows_by_frame[row["frame_index"]] = row
    cases, closures = [], []
    for decision in pending:
        tid, ref = decision["track_id"], decision["source_ref"]
        cache_row = rows_by_frame[ref["frame_index"]]
        matches = [o for o in cache_row["emitted_tracks"] if o["track_id"] == tid
                   and o["original_detection_index"] == ref["original_detection_index"]
                   and o["raw_bbox"] == ref["raw_bbox"]]
        assert len(matches) == 1, (tid, ref["frame_index"])
        physical = ref["physical_episode_id"]
        assigned = assignments[(tid, physical)]
        context_frames = [a["frame_index"] for a in assigned]
        key = scope(decision)
        material = [source, key, ref["frame_index"], ref["original_detection_index"], ref["raw_bbox"]]
        case_id = "p1-pending:" + hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:20]
        diag = diagnostics.get((decision["physical_unit_id"], decision["episode_id"], decision["passage_id"]), {})
        case = {"case_id": case_id, "baseline_candidate_scope": key,
            "baseline_source_ref": ref, "previous_status": "pending",
            "previous_reasons": decision["reasons"],
            "baseline_candidate_decision_frame": decision["frame_index"],
            "baseline_latest_retry_frame_not_observation": decision.get("latest_frame_index"),
            "physical_context_observed_range": [min(context_frames), max(context_frames)],
            "physical_context_observed_frames": len(context_frames),
            "baseline_final_display_id": decision.get("display_id"),
            "raw_track_ids": [tid], "source_witness_verified_against_cache": True,
            "origin_destination_and_eligibility_diagnostic": diag,
            "new_status_executed_by_this_triage": False,
            "decision_origin_proposal": "AI_PIXELS_REVIEW",
            "role_global_for_raw_id": False}
        if tid in reviews:
            q = reviews[tid]
            proofs = [artifact(str(ROLE_DECISIONS.relative_to(ROOT)))]
            for item in q["evidence"]:
                proof = artifact(item["path"])
                assert proof["sha256"] == item["sha256"]
                proofs.append(proof)
            case.update(earlier_qc_case_id=q["qc_case_id"], reviewed_role=q["role_recommendation"],
                role_scope=q["role_scope"], reviewer_observation=q["observation"],
                related_vehicle_raw_ids=q["related_vehicle_raw_ids"],
                parent_attribution_status=q["parent_attribution_status"], proof_artifacts=proofs,
                exact_source_images_reopened_for_p1=True,
                review_extent="Retained temporal sample sheets reopened; not every frame or global raw ID")
            if q["role_recommendation"] in ("RIDER_PASSENGER", "VEHICLE_OCCUPANT"):
                positives = q["role_scope"]["positive_raw_person_sample_frames"]
                assert ref["frame_index"] in positives
                case.update(action_group="VERIFIED_NON_INDEPENDENT_COMPONENT",
                    proposed_final_status="resolved_not_eligible", proposed_delta=0,
                    proposed_reason="REVIEWED_NON_INDEPENDENT_COMPONENT",
                    missing_evidence_and_next_action="No independent-person count. Parent raw ID can remain uncertain during overlap; do not create aliases or add another motorcycle.")
                closures.append({"adjudication_id": case_id,
                    "baseline_candidate_scope": key, "baseline_source_ref": ref,
                    "reviewed_role": q["role_recommendation"], "reviewer_origin": "AI_PIXELS_REVIEW",
                    "role_scope": q["role_scope"], "positive_source_frames": positives,
                    "proof_artifacts": proofs, "related_vehicle_raw_ids": q["related_vehicle_raw_ids"],
                    "parent_attribution_status": q["parent_attribution_status"],
                    "source_identity": source, "scope": "EXACT_PENDING_CANDIDATE_ONLY_NO_RAW_ID_GLOBAL_ROLE",
                    "reason": "REVIEWED_NON_INDEPENDENT_COMPONENT"})
            elif q["role_recommendation"] == "PEDESTRIAN":
                case.update(action_group="POSITIVE_PEDESTRIAN_ROLE_REQUIRES_PASSAGE_REPLAY",
                    proposed_final_status="REPLAY_ELIGIBILITY_NOT_AUTOMATIC_ACCEPTANCE", proposed_delta=None,
                    proposed_reason="POSITIVE_ROLE_DOES_NOT_ESTABLISH_PASSAGE",
                    missing_evidence_and_next_action="Replay bounded positive pedestrian role through unchanged Bv7 geometry/motion gates; retain measured/inferred provenance and do not copy historical +1 blindly.")
            else:
                case.update(action_group="INSUFFICIENT_ROLE_AND_IDENTITY_EVIDENCE",
                    proposed_final_status="pending", proposed_delta=0,
                    proposed_reason="RETAIN_UNKNOWN_ROLE_AFTER_TINY_CLASS_FRAGMENT",
                    missing_evidence_and_next_action="Raw3185 initial rider/motor history cannot positively label tiny person box at5579. Needs source-bound identity/role evidence at the actual candidate; do not propagate initial role globally.")
        else:
            assert tid == 3555
            cargo = read(OUT / "cargo3555_review.json")
            native = artifact("results/b_v8/pending_review/evidence/source-frame-006269.png")
            proofs = [artifact("results/b_v8/pending_review/cargo3555_review.json"), native,
                artifact("results/b_v8/pending_review/evidence/cargo6269_decode_receipt.json")]
            for item in cargo["evidence"]:
                proof = artifact(item["path"])
                assert proof["sha256"] == item["sha256"]
                proofs.append(proof)
            assert cargo["baseline_pending_candidate"]["source_ref"] == ref
            case.update(action_group="VERIFIED_CARGO_COMPONENT", reviewed_role="CARGO",
                proposed_final_status="resolved_not_eligible", proposed_delta=0,
                proposed_reason="REVIEWED_NON_INDEPENDENT_COMPONENT", related_vehicle_raw_ids=[3563],
                reviewer_observation="Tied cardboard load travels on motorcycle3563; source6269 shows rear motorcycle wheel below load, not an independent truck.",
                proof_artifacts=proofs, role_scope={"start_frame":6269,"end_frame":6269},
                parent_attribution_status="SOURCE_SHEET_AND_EXISTING_MEASURED_PARENT_PASSAGE",
                missing_evidence_and_next_action="Keep existing measuredmotor3563 event6267; cargoBC is not a second crossing source. No automatic whole-track taxonomy remap.")
            closures.append({"adjudication_id":case_id,"baseline_candidate_scope":key,
                "baseline_source_ref":ref,"reviewed_role":"CARGO","reviewer_origin":"AI_PIXELS_REVIEW",
                "role_scope":{"start_frame":6269,"end_frame":6269},"positive_source_frames":[6269],
                "proof_artifacts":proofs,"related_vehicle_raw_ids":[3563],
                "parent_attribution_status":"SOURCE_SHEET_AND_EXISTING_MEASURED_PARENT_PASSAGE",
                "source_identity":source,"scope":"EXACT_PENDING_CANDIDATE_ONLY_NO_RAW_ID_GLOBAL_ROLE",
                "reason":"REVIEWED_NON_INDEPENDENT_COMPONENT"})
        cases.append(case)
    assert len(closures) == 22 and len(cases) == 24
    for row in closures:
        row.update(source_video_sha256=source["video_sha256"],
                   records_sha256=source["records_sha256"])
    proposal = {"schema_version":"phase9_b_v8_pending_adjudications_v1",
        "baseline_result_sha256":sha(BASELINE),"source_identity":source,
        "decision_origin":"AI_PIXELS_REVIEW_NOT_AUTOMATIC_MODEL_PREDICTION",
        "adjudications":closures}
    write("proposed_closures.json", proposal)
    inventory = {"schema_version":"phase9_b_v8_pending_triage_v1",
        "baseline_result":str(BASELINE.relative_to(ROOT)),"baseline_result_sha256":sha(BASELINE),
        "source_identity":source,"baseline_pending":24,
        "groups":dict(Counter(c["action_group"] for c in cases)),
        "proposed_component_plus_zero_closures":22,
        "positive_role_cases_requiring_unchanged_geometry_replay":1,
        "necessary_pending_retained":1,"actual_pipeline_decisions_executed":False,
        "new_model_tracker_reid_counting_or_enhancement_execution":False,"cases":cases}
    write("pending_inventory.json",inventory)
    fields=["case_id","raw_track_id","source_ref_frame","physical_context_start","physical_context_end",
        "baseline_reason","reviewed_role","action_group","proposed_final_status","proposed_delta","next_action"]
    with (OUT/"pending_inventory.csv").open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for c in cases:
            writer.writerow({"case_id":c["case_id"],"raw_track_id":c["baseline_candidate_scope"]["track_id"],
                "source_ref_frame":c["baseline_source_ref"]["frame_index"],
                "physical_context_start":c["physical_context_observed_range"][0],"physical_context_end":c["physical_context_observed_range"][1],
                "baseline_reason":";".join(c["previous_reasons"]),"reviewed_role":c["reviewed_role"],
                "action_group":c["action_group"],"proposed_final_status":c["proposed_final_status"],
                "proposed_delta":c["proposed_delta"],"next_action":c["missing_evidence_and_next_action"]})
    write("triage_verification.json",{"baseline_sha256":sha(BASELINE),"source_cache_sha256":sha(CACHE),
        "pending_source_witnesses_verified":len(cases),"component_closure_witnesses_with_positive_pixels":22,
        "all_23_person_source_sheets_reopened":True,"cargo6269_native_frame_reopened":True,
        "scope_is_not_every_frame_or_formal_ground_truth":True,"old_files_modified":False,
        "status":"COMPLETE_24_CASE_EVIDENCE_TRIAGE_NOT_PIPELINE_FINALIZATION"})
    print(json.dumps({"pending":24,"proposed_component_plus_zero":22,"pedestrian_role_replay":1,
        "necessary_pending_retained":1,"groups":inventory["groups"]}))


if __name__ == "__main__":
    main()
