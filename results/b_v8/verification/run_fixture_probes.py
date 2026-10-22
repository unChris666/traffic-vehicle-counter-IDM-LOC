"""Replay bounded actual-source P1 fixtures, without new model inference."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks"))
import phase_8_b_v7_batch as baseline
import phase_8_b_v3_batch as adapter
import phase_8_b_v6_identity as identity
import phase_8_b_v7_counting as counting
from phase_8_b_v8_review import prepare_reviewed_frames
from phase_5_geometry_helpers import Geometry


def run(output_relative="results/b_v8/verification/actual_fixture_probes_v2",
        overlay_relative="results/b_v8/config/review_overlay.json", include_competing=False,
        include_handoff_recovery=False):
    prepared = baseline.prepare_b_v7_batch(repo_root=ROOT,
        source_run_root="/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z",
        source_video_root="/tmp/qc-source")
    job = prepared["jobs"][0]
    source = job["b_v2_source_identity"]
    links = adapter.relationship_evidence(job["paths"]["relations"])
    frames = list(adapter.adapted_frames(job["paths"]["records"], source, 9128,
        relationships=links, reviews=prepared["base_reviews"]["weekday_siang"].get("reviews", []),
        reviews_sha256=prepared["reviews_sha256"], application_proof={}))
    geometry = Geometry.from_draft(job["b_v2_geometry_path"], 640, 480)
    overlay = json.loads((ROOT / overlay_relative).read_text())
    directory = (ROOT / output_relative).resolve()
    if not directory.is_relative_to(ROOT / "results/b_v8/verification"):
        raise ValueError("Probe output must stay in new P1 verification directory")
    if directory.exists():
        raise ValueError("Preserve existing probe; use an explicit new probe version")
    directory.mkdir()
    summaries = []
    cases = [
        ("blocker4843", 7800, 8010, {4808, 4843, 4913}, {"SAME_VEHICLE", "SPLIT_IDENTITY"}),
        ("pedestrian54", 0, 220, {54}, {"PEDESTRIAN_ROLE"}),
    ]
    if include_handoff_recovery:
        cases.append(("handoff_recovery",0,1450,{1049,1123,1101,1070},{"SAME_VEHICLE"}))
    for name, low, high, tracks, kinds in cases:
        if name == "blocker4843" and include_competing:
            tracks = tracks | {4798}
            low = 7796
        selected = [{"frame_index": row["frame_index"], "observations": [deepcopy(item)
            for item in row["observations"] if item["track_id"] in tracks]}
            for row in frames if row["frame_index"] <= high]
        scoped = deepcopy(overlay)
        scoped["videos"][0]["reviews"] = [r for r in scoped["videos"][0]["reviews"]
            if r["type"] in kinds and all(s["track_id"] in tracks for s in r["scopes"])]
        digest = hashlib.sha256(json.dumps(scoped, sort_keys=True).encode()).hexdigest()
        reviewed = prepare_reviewed_frames(selected, scoped, source_identity=source,
            repo_root=ROOT, source_records_path=job["paths"]["records"], frame_count=9128,
            overlay_sha256=digest)
        output = directory / name
        for branch, data in (("baseline", selected), ("reviewed", reviewed["frames"])):
            policy = deepcopy(prepared["policy"])
            if branch == "reviewed":
                policy.update(execution_branch="review_assisted", review_overlay_sha256=digest)
            resolved = identity.prepare_identity_frames(data, geometry, policy, relationships=links)
            policy["episode_relations"] = resolved.get("unit_relations", [])
            result = counting.replay_frames(resolved["frames"], geometry,
                source_identity=source, policy=policy)
            baseline._write(output / (branch + "_result.json.gz"), result)
            baseline._write(output / (branch + "_resolved_frames.json.gz"), resolved["frames"])
            baseline._write(output / (branch + "_identity_audit.json.gz"),
                {k: value for k, value in resolved.items() if k != "frames"})
            summaries.append({"fixture": name, "branch": branch,
                "source_frame_window": [low, high], "aggregate": result["aggregate"],
                "actual_replayed_frame_history": [0, high],
                "source_scene_filtered_to_raw_tracks": sorted(tracks),
                "events": [{k: event.get(k) for k in ("track_id", "physical_unit_id", "category",
                    "direction", "route", "decision_frame")} | {
                    "measured_crossing": event["evidence"]["measured_crossing"],
                    "source_tracks": sorted({r["track_id"] for r in event["evidence"]["source_refs"]})}
                    for event in result["events"]]})
        baseline._write(output / "review_application.json", reviewed["application_audit"])
    baseline._write(directory / "summary.json", summaries)
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-relative", default="results/b_v8/verification/actual_fixture_probes_v2")
    parser.add_argument("--overlay-relative", default="results/b_v8/config/review_overlay.json")
    parser.add_argument("--include-competing", action="store_true")
    parser.add_argument("--include-handoff-recovery", action="store_true")
    run(**vars(parser.parse_args()))
