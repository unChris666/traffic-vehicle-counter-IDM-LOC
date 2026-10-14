"""Retain actual Codex-assisted pixel review and physical-passage comparisons.

This file documents images actually opened in the review session. It reads
existing outputs and emits review proposals only; no models, trackers, geometry
state machine, or counting/identity resolver execute here.
"""
from __future__ import annotations
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[6]
RUN = Path(__file__).resolve().parents[1]
OUTPUT = Path(__file__).resolve().parent


def read(path):
    with (gzip.open(path, "rt") if str(path).endswith(".gz") else open(path)) as stream:
        return json.load(stream)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


OBSERVATIONS = {
    "dev_beginning_motorcycle_27": {
        "physical_category": "motorcycle", "disposition": "CONFIRM_PASSAGE",
        "physical_observation": "One motorcycle with pink-shirt rider recedes from right foreground toward left background in raw and gamma. Raw IDs4/7/9 and gamma IDs4/6/7 overlap the same motorcycle at sampled times, not separate motorcycles. Vehicle BC crosses26→27 in both branches.",
        "comparison": "Automatic duplicate/component ambiguity remains in both. Gamma loses the emitted motorcycle at14 despite raw4 being emitted; later gamma7 still supplies the same measured crossing. No new physical passage is established by extra IDs.",
        "manual_components": {"raw": [2], "gamma_070": [2]},
        "manual_duplicate_tracks": {"raw": [4,7,9], "gamma_070": [4,6,7]},
        "failure_dimensions": ["duplicate_boxes", "component_ambiguity", "short_observation_loss"],
    },
    "dev_beginning_motorcycle_113": {
        "physical_category": "motorcycle", "disposition": "CONFIRM_PASSAGE",
        "physical_observation": "One motorcycle carrying rider(s) recedes through frames104–119 in both conditions. Person18 is part of that vehicle, not an independent counted vehicle. Gamma's accepted event uses motorcycle15 raw measured BC112→113. No distinct foreground motorcycle is merged in the inspected sequence.",
        "comparison": "Gamma alone is machine accepted. This is sensitive to full-episode/global relation admission: raw local105–113 residual0.120785 passes0.15, but later115→116 raises full-episode residual to0.157327 and rejects the relation. Gamma15 becomes bicycle115/117, ending the relevant vehicle episode114; its admitted relation avoids that later interval. Gamma brightness does not remove motion blur. Not a demonstrated visibility/ReID performance gain.",
        "manual_components": {"raw": [14,18], "gamma_070": [18]},
        "manual_duplicate_tracks": {"raw": [15], "gamma_070": [15]},
        "failure_dimensions": ["offline_episode_boundary_sensitivity", "person_duplicate_or_multiple_rider_boxes", "later_vehicle_class_flip"],
    },
    "dev_quarter_motorcycle_2297": {
        "physical_category": "motorcycle", "disposition": "CONFIRM_PASSAGE",
        "physical_observation": "One motorcycle with rider(s) and bright purple rear lamp recedes through both conditions. Raw409 and gamma432 refer to this same physical passage; vehicle BC crosses2296→2297. No separate car is visible at gamma's extra car detection on the motorcycle front at2277.",
        "comparison": "Both machine candidates pending because admitted rider relation support begins later than passage2285–2297. Gamma's extra unconfirmed car label at2277 is a category regression on motorcycle pixels; glare/blur remain.",
        "manual_components": {"raw": [408], "gamma_070": [430]},
        "manual_duplicate_tracks": {"raw": [409], "gamma_070": [432]},
        "failure_dimensions": ["future_only_component_support", "gamma_false_car_component", "glare"],
    },
    "holdout_middle_motorcycle_4869": {
        "physical_category": "motorcycle", "disposition": "CONFIRM_PASSAGE",
        "physical_observation": "One motorcycle with red-shirt rider recedes through4855–4887. Raw564 and gamma587 correspond to the same bike, with proper measured vehicle BC4868→4869. The rider is not counted separately.",
        "comparison": "Both remain machine pending for absent positive identity evidence. Gamma motorcycle emitted one frame later at4856 versus raw4855; the crossing endpoints remain identical. Gamma appears brighter, but the lamp/body blur remains and no accepted machine hold-out gain is established.",
        "manual_components": {"raw": [563], "gamma_070": [585]},
        "manual_duplicate_tracks": {"raw": [564], "gamma_070": [587]},
        "failure_dimensions": ["component_geometry_control_failure", "initial_emitted_observation_delay", "motion_blur"],
    },
    "dev_three_quarters_truck_7114": {
        "physical_category": "truck", "disposition": "CONFIRM_PASSAGE",
        "physical_observation": "One loaded flatbed truck recedes through7071–7147. Duplicate cabin/front versus full-body boxes raw807/810 and gamma826/829 describe parts/extents of the same truck. The representative raw810/gamma829 measured vehicle BC crosses7113→7114; the later foreground motorcycle is a separate vehicle.",
        "comparison": "Both pending due duplicate/identity competitor evidence. Gamma's crossing episode ends7126 versus raw7147, while later same physical truck observations occur in other episodes. Duplicate boxes are not resolved automatically. No extra truck is counted from cab/full-body detections.",
        "manual_components": {"raw": [], "gamma_070": []},
        "manual_duplicate_tracks": {"raw": [807,810], "gamma_070": [826,829]},
        "failure_dimensions": ["truck_component_duplicate", "gamma_episode_fragmentation", "bbox_extent_jitter"],
    },
    "dev_three_quarters_motorcycle_7170": {
        "physical_category": "motorcycle", "disposition": "CONFIRM_PASSAGE",
        "physical_observation": "One motorcycle with rider(s), including an orange head covering, recedes through7150–7172. Raw819/gamma841 supply vehicle BC7169→7170. The truck farther left/background is physically separate and must not be merged with this motorcycle.",
        "comparison": "Raw current eligible episode starts7166 after earlier gaps; gamma's eligible episode starts7154 and has longer measured support. Both remain pending. Gamma admits a global component before its origin and flags truck/bus raw competitor boxes. Photo review resolves identity only for this measured passage, without bridging raw gaps or using rider BC.",
        "manual_components": {"raw": [815,816], "gamma_070": [835,838]},
        "manual_duplicate_tracks": {"raw": [819], "gamma_070": [841]},
        "failure_dimensions": ["temporal_fragmentation", "component_support_outside_passage", "separate_vehicle_overlap_screening"],
    },
    "dev_three_quarters_car_conflict_7244": {
        "physical_category": "passenger_vehicle_car_like_business_subtype_unknown", "disposition": "HOLD",
        "physical_observation": "One white enclosed passenger vehicle recedes through7210–7360. It is visually distinct from the earlier flatbed truck and motorcycle. Exact MPV/SUV business taxonomy is not asserted. Both vehicle BCs cross7243→7244.",
        "comparison": "Frozen full-vehicle-episode unanimity fails: raw835 has truck7360; gamma856 crossing episode has truck7337. These are observed class flips on the distant passenger vehicle, not demonstrated physical category changes. Review must not erase CATEGORY_CONFLICT, even though near-frame appearance supports a passenger vehicle.",
        "manual_components": {"raw": [], "gamma_070": []},
        "manual_duplicate_tracks": {"raw": [835], "gamma_070": [856]},
        "failure_dimensions": ["offline_category_conflict", "distant_class_instability", "business_taxonomy_open"],
    },
    "holdout_end_motorcycle_9356": {
        "physical_category": "motorcycle", "disposition": "CONFIRM_PASSAGE",
        "physical_observation": "A motorcycle with bright headlamp moves from left/background toward right foreground, separately from the red motorcycle farther right. Raw1198/gamma1223 follow that same physical passage. Vehicle BC9355→9356 is A_TO_B; no rider BC or nearby red-bike BC substitutes for it.",
        "comparison": "Both machine pending without positive identity evidence. Gamma9345 labels this track person before its clean vehicle episode9346; raw vehicle episode begins9345. Both preserve the same crossing. Bright glare and surrounding motorcycles remain difficult; no machine hold-out acceptance benefit is shown.",
        "manual_components": {"raw": [], "gamma_070": []},
        "manual_duplicate_tracks": {"raw": [1198], "gamma_070": [1223]},
        "failure_dimensions": ["person_vehicle_family_handoff", "glare", "nearby_distinct_vehicle"],
    },
    "dev_quarter_car_detection_control": {
        "physical_category": "motorcycle", "disposition": "NO_NEW_COUNT_CANDIDATE",
        "physical_observation": "The foreground moving object at2277 is a blurred motorcycle with rider(s); no independent car occupies gamma's small car box on its front/left body. Sequence2280 onward clarifies the same motorcycle. This control overlaps the2297 passage and is not an additional vehicle.",
        "comparison": "Gamma produces an extra unconfirmed car detection on motorcycle pixels. This is an observed category regression, not evidence of an extra car detected correctly. Purple rear-lamp glare becomes brighter.",
        "failure_dimensions": ["false_category_component", "overlap_control_not_extra_passage"],
    },
    "holdout_middle_headlight_control": {
        "physical_category": "UNKNOWN_FOR_GLARE_OBSCURED_OBJECTS", "disposition": "NO_NEW_COUNT_CANDIDATE",
        "physical_observation": "Distant and approaching headlight sources at4674/4734/4794 are difficult to assign a vehicle body/category from these pixels. Frame4854 is the red-shirt motorcycle represented separately by the4869 case. At4913 its body is distant and person-associated; no new passage is certified here.",
        "comparison": "Gamma brightens road, background and glare. Both variants have no detections at4674 and4794. No supported new body/identity/crossing is established for glare-only objects. Sparse control tiles cannot quantify missed vehicles.",
        "failure_dimensions": ["glare_obscured_unknown_category", "no_supported_new_crossing"],
    },
    "holdout_end_censored_control": {
        "physical_category": "UNKNOWN_FOR_END_HEADLIGHT_SOURCE", "disposition": "NO_NEW_COUNT_CANDIDATE",
        "physical_observation": "End samples show multiple lamp sources and a motorcycle near the right edge. At9589 the left headlight body is obscured and the file ends, so later evidence is unavailable. No new complete measured passage is established by these sparse images.",
        "comparison": "Both have no detections at9589 despite brighter gamma input. Gamma also has no emitted observations at9410 while raw emits persons1227/1177. The sampled person change is a local observation difference, not an extra or missed complete traffic passage.",
        "failure_dimensions": ["right_censored", "headlight_body_unknown", "local_emitted_observation_loss"],
    },
}


def main():
    index = read(OUTPUT / "contact_index.json")
    assert len(index["cases"]) == 11 and index["contact_artifacts_generated"] == 22
    pixel_rows, comparisons = [], []
    decisions = {v: read(RUN / v / "machine_passage_decisions.json.gz") for v in ("raw", "gamma_070")}
    review_inputs = {}
    for variant in decisions:
        review_inputs[variant] = {
            "schema_version": "phase7_explicit_physical_review_input_v1",
            "source_run_id": RUN.name,
            "source_machine_decisions_sha256": sha(RUN / variant / "machine_passage_decisions.json.gz"),
            "source_identity": read(RUN / variant / "counting_configuration.json")["input_identity"],
            "reviewer": "CODEX_ASSISTED_ACTUAL_PIXEL_REVIEW_NOT_GROUND_TRUTH",
            "scope": "eight same-physical-passage comparisons; no full-video count finalization",
            "decisions": [],
            "automatic_events_preserved_without_reclassification": [],
        }
    for case in index["cases"]:
        observation = OBSERVATIONS[case["case_id"]]
        evidence = []
        for mode, artifact in case["artifacts"].items():
            assert sha(REPO / artifact["path"]) == artifact["sha256"]
            evidence.append({"path": artifact["path"], "sha256": artifact["sha256"], "frame_indices": case["frames"], "observation": observation["physical_observation"] + " " + observation["comparison"]})
        pixel_rows.append({"case_id": case["case_id"], "split": case["split"], "segment_id": case["segment_id"], "frame_indices_actually_viewed_raw_and_gamma": case["frames"], "photos_actually_opened": [a["path"] for a in case["artifacts"].values()], "evidence": evidence, **observation})
        if case["crossing_end"] is None:
            continue
        row = {"physical_passage_review_id": "night_" + case["case_id"], "case_id": case["case_id"], "split": case["split"], "segment_id": case["segment_id"], "same_physical_vehicle_across_variants": True, "pairing_basis": "actual same-original-frame pixels and vehicle trajectory/context; track IDs are branch-local only", "physical_category_observation": observation["physical_category"], "visual_observation": observation["physical_observation"], "comparison": observation["comparison"], "failure_dimensions": observation["failure_dimensions"], "evidence": evidence, "branches": {}}
        for variant in decisions:
            candidate = next(d for d in decisions[variant] if d["diagnostic"].get("crossing_frame_end") == case["crossing_end"])
            diagnostic = candidate["diagnostic"]
            source_support = candidate["measurement_support"]
            assert all(item["point"] == [(item["raw_bbox"][0]+item["raw_bbox"][2])/2, item["raw_bbox"][3]] for item in source_support)
            row["branches"][variant] = {"candidate_id": candidate["candidate_id"], "track_id": candidate["track_id"], "machine_status": candidate["status"], "machine_category": candidate["category"], "machine_reasons": candidate["reasons"], "review_disposition": "KEEP_AUTOMATIC_ACCEPTED" if candidate["accepted_count_event"] else observation["disposition"], "geometry_type": diagnostic["type"], "direction": diagnostic["direction"], "origin_frame": diagnostic["origin_frame"], "crossing_frame_start": diagnostic["crossing_frame_start"], "crossing_frame_end": diagnostic["crossing_frame_end"], "confirmation_frame": diagnostic["confirmation_frame"], "source_anchor": "raw_detector_linked_emitted_vehicle_BC", "source_support_contiguous": [s["frame_index"] for s in source_support] == list(range(diagnostic["origin_frame"], diagnostic["confirmation_frame"]+1)), "rider_or_prediction_source_used": False, "reviewed_overlay_result": "NOT_EXECUTED_BY_THIS_METHOD"}
            if candidate["accepted_count_event"]:
                review_inputs[variant]["automatic_events_preserved_without_reclassification"].append({"candidate_id": candidate["candidate_id"], "event_id": candidate["event_id"], "pixel_review_support": evidence})
                continue
            confirm = observation["disposition"] == "CONFIRM_PASSAGE"
            review_inputs[variant]["decisions"].append({"candidate_id": candidate["candidate_id"], "disposition": observation["disposition"], "physical_unit_id": "manual_night_unit_" + case["case_id"], "passage_id": "manual_night_passage_" + case["case_id"], "category": observation["physical_category"] if confirm else None, "unit_confirmed": True, "category_confirmed": confirm, "identity_confirmed": True, "reviewer": "CODEX_ASSISTED_ACTUAL_PIXEL_REVIEW_NOT_GROUND_TRUTH", "reason": observation["physical_observation"] + " " + observation["comparison"], "evidence": evidence, "manual_component_track_ids": observation["manual_components"][variant], "manual_same_unit_vehicle_track_ids_observed": observation["manual_duplicate_tracks"][variant], "manual_links_semantics": "bounded photo annotations only; no replacement source trajectory, rider BC, merged bbox, or future-event identity claim"})
        comparisons.append(row)
    write(OUTPUT / "pixel_review.json", {"schema_version": "phase7_actual_temporal_pixel_review_v1", "run_id": RUN.name, "reviewed_at_utc": datetime.now(timezone.utc).isoformat(), "reviewer": "CODEX_ASSISTED_ACTUAL_PIXEL_REVIEW_NOT_GROUND_TRUTH", "execution_kind": "ACTUAL_RETAINED_VIDEO_PIXEL_AND_SOURCE_REVIEW", "contact_index_sha256": sha(OUTPUT / "contact_index.json"), "unique_native_source_frames": index["actual_unique_native_frames_decoded"], "images_actually_opened": 22, "physical_candidate_passages_reviewed": 8, "supplementary_controls_reviewed": 3, "cases": pixel_rows, "limitations": ["Not blind: historical Phase1 pixels and DEV screening were already reviewed", "Only declared windows/candidate passages and bounded controls; not whole-video traffic completeness", "No ground truth or performance rates", "Hold-out observations did not change gamma0.7/model/tracker/ReID/counting controls", "Full-episode offline relation/category policies can be affected by observations after crossing", "Manual proposals do not change machine artifacts or establish automatic improvement"]})
    for variant, value in review_inputs.items():
        write(OUTPUT / (variant + "_review_input.json"), value)
    write(OUTPUT / "physical_passage_comparison.json", {"schema_version": "phase7_actual_physical_passage_comparison_v1", "run_id": RUN.name, "source_pixel_review_sha256": sha(OUTPUT / "pixel_review.json"), "scope": "eight matched physical candidate passages from five predeclared development/holdout windows", "claim_type": "EXPERIMENT_RESULT_BOUNDED_REVIEW_NOT_GROUND_TRUTH", "machine_accepted": {v: sum(d["accepted_count_event"] for d in ds) for v,ds in decisions.items()}, "review_overlay_execution_status": "PROPOSED_INPUTS_ONLY_SEPARATE_GUARDED_OVERLAY_REQUIRED", "passages": comparisons, "hypothesis_disposition": "No general gamma improvement established by one additional automatic accepted event; raw retained as baseline/default pending broader evidence"})
    with (OUTPUT / "physical_passage_comparison.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["physical_passage", "split", "raw_track", "gamma_track", "raw_machine", "gamma_machine", "crossing_start", "crossing_end", "direction", "review_proposal", "main_findings"])
        for row in comparisons:
            a,b = row["branches"]["raw"],row["branches"]["gamma_070"]
            writer.writerow([row["case_id"],row["split"],a["track_id"],b["track_id"],a["machine_status"],b["machine_status"],a["crossing_frame_start"],a["crossing_frame_end"],a["direction"],a["review_disposition"],row["comparison"]])
    lines = ["# Actual TOR3-MALAM temporal passage review", "", "Raw and frozen gamma0.7 were executed in Kaggle over all9,590 source frames. This review compares eight candidate physical passages within the five predeclared windows, plus three controls. Track IDs are local to each variant. No model, tracker, encoder, geometry replay or counting resolver was rerun here.", "", "All22 new contact PNGs were actually opened. Their73 unique native-frame donor pixels and measured raw-bbox links passed601/601 checks. This is bounded review evidence, not ground truth or exhaustive vehicle counts.", "", "| Physical passage/crossing | Split | Raw / gamma tracks | Machine raw → gamma | Review proposal |", "|---|---|---|---|---|"]
    for row in comparisons:
        a,b = row["branches"]["raw"],row["branches"]["gamma_070"]
        lines.append(f"| {row['case_id']} / {a['crossing_frame_start']}→{a['crossing_frame_end']} | {row['split']} | {a['track_id']} / {b['track_id']} | {a['machine_status']} → {b['machine_status']} | {a['review_disposition']} |")
    lines.extend(["", "Gamma's one accepted motorcycle15 is visually one unit with its rider(s), and crossing uses vehicle BC112→113. Raw's same local identity observations would pass the numeric motion control, but global relation admission also includes later115→116; gamma's intervening bicycle labels end its vehicle episode114. The acceptance difference therefore exposes offline episode/policy sensitivity as well as pixel/bbox changes. It is not proof of a generally better night pipeline or of ReID improvement.", "", "Seven physically reviewed passages have reviewable identity-only holds or an already accepted event. The white passenger vehicle remains pending because CATEGORY_CONFLICT is a hard blocker in both complete vehicle-episode histories. The review inputs propose resolution only; accepted overlay numbers belong to the separately executed guarded overlay.", "", "Hold-out middle/end motorcycles remain machine pending in both conditions. Gamma brightens visible pixels but does not establish a new hold-out accepted passage or recover the glare-only unknown bodies at4674/9589. Additional gamma false car labeling on motorcycle pixels2277 and observation/category changes are retained as regressions. No hold-out result was used to retune the frozen candidate.", "", "See [pixel review](pixel_review.json), [physical-passage JSON](physical_passage_comparison.json), [raw review input](raw_review_input.json), and [gamma review input](gamma_070_review_input.json)."])
    (OUTPUT / "README.md").write_text("\n".join(lines)+"\n")
    print(json.dumps({"images_opened":22,"physical_passages":8,"controls":3,"raw_review_rows":len(review_inputs['raw']['decisions']),"gamma_review_rows":len(review_inputs['gamma_070']['decisions']),"automatic_gamma_events_preserved":len(review_inputs['gamma_070']['automatic_events_preserved_without_reclassification'])}))


if __name__ == "__main__":
    main()
