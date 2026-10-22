"""Documentary/source QC of retained P1 results; no counting or model replay."""
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"notebooks"))
from phase_9_v7_compare import _event_map, _normalize
from phase_9_v8_compare import compare_results, read


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def strip_display(value):
    if isinstance(value,dict):return {k:strip_display(v) for k,v in value.items() if k not in ("display_id","namespace")}
    if isinstance(value,list):return [strip_display(x) for x in value]
    return value


def source_relation_ids(result):
    """Versioned relation hashes are joined only by exact endpoint witnesses."""
    mapping={}
    for relation in result.get("v7_handoff_relations",[]):
        material={key:relation.get(key) for key in ("candidate_kind","verified",
            "first_track_id","second_track_id","first_physical_episode_id",
            "second_physical_episode_id","first_support_frames","second_support_frames",
            "gap_source_frames","motion_provenance","identity_merged")}
        for prefix in ("first","second"):
            material[prefix+"_measured_witnesses"]=[{key:ref.get(key) for key in
                ("frame_index","track_id","original_detection_index","raw_bbox")}
                for ref in relation[prefix+"_source_refs"]]
        digest=hashlib.sha256(json.dumps(material,sort_keys=True).encode()).hexdigest()
        mapping[relation["relation_id"]]="handoff-source:"+digest
    return mapping


def main(candidate_relative, output_relative):
    candidate_path=(ROOT/candidate_relative).resolve();output=(ROOT/output_relative).resolve()
    assert output.is_relative_to(ROOT/"results/b_v8/review") and not output.exists()
    baseline_path=ROOT/"results/b_v7/execution/pilot_v7_machine_final/weekday_siang/counting_result.json.gz"
    before,after=read(baseline_path),read(candidate_path)
    inventory=read(ROOT/"results/b_v8/pending_review/pending_inventory.json")
    comparison=compare_results(before,after,inventory)
    maps=[{**_event_map(r),**source_relation_ids(r)} for r in (before,after)];controls=[]
    for track in (1049,1123,4251,4281,4149,4367,4934,4946,4953,2445,4552,4480,3563):
        values=[]
        for result,mapping in zip((before,after),maps):
            values.append(strip_display(_normalize({"events":[e for e in result["events"] if e["track_id"]==track],
                "decisions":[d for d in result["decisions"] if d.get("track_id")==track]},mapping)))
        controls.append({"raw_track_id":track,"unchanged_source_counting_decisions":values[0]==values[1],
            "baseline_accepted":len(values[0]["events"]),"candidate_accepted":len(values[1]["events"])})
    # Verify every active event witness plus every old pending witness against
    # exact emitted records. This cannot establish physical counting accuracy.
    refs=[r for e in after["events"] for r in e["evidence"]["source_refs"]]
    refs += [d["source_ref"] for d in before["decisions"] if d["status"]=="pending"]
    wanted=defaultdict(list)
    for ref in refs:wanted[ref["frame_index"]].append(ref)
    cache=Path("/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz")
    assert sha(cache)==after["source_identity"]["records_sha256"]
    checked=0;checked_frames=set()
    with gzip.open(cache,"rt") as handle:
        for line in handle:
            row=json.loads(line);frame=row["frame_index"]
            if frame not in wanted:continue
            measured={i["track_id"]:i for i in row["emitted_tracks"]}
            for ref in wanted[frame]:
                item=measured[ref["track_id"]]
                assert all(item[k]==ref[k] for k in ("original_detection_index","raw_bbox","class_name"))
                assert ref["observed"] and ref["emitted"]
                x1,_,x2,y2=ref["raw_bbox"];assert ref["point"]==[(x1+x2)/2,y2]
                checked+=1
            checked_frames.add(frame)
    assert checked_frames==set(wanted)
    red=[e for e in after["events"] if e["physical_unit_id"]=="review:TGDI_SIANG:red_motorcycle_passage"]
    foreground=[e for e in after["events"] if e["physical_unit_id"]=="review:TGDI_SIANG:distinct_foreground_motorcycle"]
    blue=[e for e in after["events"] if any(
        (r["track_id"]==4843 and 7874<=r["frame_index"]<=7905)
        or (r["track_id"]==4913 and 7950<=r["frame_index"]<=7964)
        for r in e["evidence"]["source_refs"])]
    recovered=[e for e in after["events"] if e["physical_unit_id"]=="review:TGDI_SIANG:recovered_handoff_passage"]
    handoff_ok=(len(recovered)==1 and not recovered[0]["evidence"]["measured_crossing"]
        and {r["track_id"] for r in recovered[0]["evidence"]["source_refs"]}=={1049,1123}
        and all(r["frame_index"]<=1336 if r["track_id"]==1049 else 1349<=r["frame_index"]<=1396
            for r in recovered[0]["evidence"]["source_refs"]))
    for control in controls:
        approved=bool(recovered) and control["raw_track_id"] in (1049,1123)
        control["expected_source_review_change"]=approved
        control["control_pass"]=(handoff_ok if approved else control["unchanged_source_counting_decisions"])
    red_ok=(len(red)==1 and not red[0]["evidence"]["measured_crossing"]
        and {r["track_id"] for r in red[0]["evidence"]["source_refs"]}=={4808,4843}
        and all(r["frame_index"]<=7907 if r["track_id"]==4808 else r["frame_index"]>=7928
            for r in red[0]["evidence"]["source_refs"]))
    source_preserved=after["source_identity"]==before["source_identity"]
    pending=comparison["pending_reconciliation"]
    output.parent.mkdir(parents=True,exist_ok=True)
    data={"schema_version":"phase9_b_v8_p1_source_qc_v1",
        "baseline_sha256":sha(baseline_path),"candidate_sha256":sha(candidate_path),
        "candidate_path":candidate_path.relative_to(ROOT).as_posix(),
        "baseline_branch":"machine","candidate_branch":"review_assisted",
        "baseline_aggregate":before["aggregate"],"candidate_aggregate":after["aggregate"],
        "source_identity_unchanged":source_preserved,
        "event_count_changes":comparison["event_counts"],
        "display_id_renumberings":len(comparison["display_id_changes"]),
        "category_changed_events":comparison["category_changed_events"],
        "direction_changed_events":comparison["direction_changed_events"],
        "existing_event_evidence_level_transitions":comparison["evidence_transition_counts"],
        "pending_dispositions":pending["by_final_status"],
        "unresolved_pending_reconciliation":[r["case_id"] for r in pending["rows"] if r["final_status"]=="unresolved_reconciliation"],
        "unmatched_new_pending":pending["unmatched_new_pending"],
        "reviewed_component_closures":len(after.get("v8_pending_finalization_audit",[])),
        "all_component_closures_have_plus_zero":all(a["count_delta"]==0 for a in after.get("v8_pending_finalization_audit",[])),
        "measured_source_refs_verified_against_frozen_cache":checked,
        "source_frames_verified":len(checked_frames),
        "regression_controls":controls,
        "relation_identifiers_joined_by":"EXACT_ENDPOINT_RAW_MEASUREMENTS_PHYSICAL_CONTEXTS_SUPPORT_AND_PROVENANCE",
        "baseline_handoff_relation_source_ids":source_relation_ids(before),
        "candidate_handoff_relation_source_ids":source_relation_ids(after),
        "red_exactly_one_clean_inferred_passage":red_ok,
        "distinct_foreground_passage_kept":len(foreground)==1 and foreground[0]["evidence"]["measured_crossing"],
        "unsupported_blue_destination_presence_events":len(blue),
        "additional_handoff_recovery_accepted":len(recovered),
        "additional_handoff_has_one_clean_inferred_event":handoff_ok if recovered else None,
        "published_log_total":sum(l.get("count_delta",0) for l in after["passage_log"]),
        "source_review_independent_from_implementation_reference":"independent_source_verification.json",
        "additional_foreground_pixels_reviewed_by":"PRIMARY_ENGINEER_AI_REVIEW_NOT_NEW_HUMAN_CONFIRMATION",
        "full_replay_comparison_performed_by":"PRIMARY_ENGINEER_READ_ONLY_QC",
        "new_model_execution":False,"new_counting_execution_by_qc":False,
        "formal_ground_truth_or_accuracy_established":False,
        "reviewed_red_reconstruction_is_net_new_aggregate_passage":False,
        "known_intentional_exclusion_1049_1123_still_not_recovered":not handoff_ok,
        "automatic_machine_baseline_p0_blocker_fixed":False}
    data["scoped_checks_pass"]=(red_ok and len(blue)==0 and data["distinct_foreground_passage_kept"]
        and all(c["control_pass"] for c in controls)
        and not data["unresolved_pending_reconciliation"] and not pending["unmatched_new_pending"]
        and data["published_log_total"]==after["aggregate"]["total"])
    output.write_text(json.dumps(data,indent=2)+"\n")
    print(json.dumps({k:data[k] for k in ("scoped_checks_pass","red_exactly_one_clean_inferred_passage",
        "distinct_foreground_passage_kept","unsupported_blue_destination_presence_events","pending_dispositions")}))


if __name__=="__main__":main(*sys.argv[1:])
