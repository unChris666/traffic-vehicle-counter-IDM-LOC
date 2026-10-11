# Phase 3 execution report

Status: `completed_cached_sequence_manual_review_pending`
Run: `20261011T060227_579936Z_05ebe213`
Parent: `20261011T052950_360560Z_ed399fb8`

Cached BoT-SORT association only; no Phase 2 rerun, geometry, counting or ReID experiment.
Frames processed: 10282
Unique tracker IDs are lifecycle diagnostics, not physical vehicle or traffic totals.
Visual review: pending_actual_temporal_evidence_review

## Observed software/lifecycle diagnostics

```json
{
  "serialized_rows_verified": 10282,
  "captured_tracker_ids_including_unconfirmed": 4922,
  "unique_emitted_tracker_ids": 780,
  "emitted_track_observations": 45756,
  "frames_with_zero_cached_detections": 7,
  "frames_with_no_emitted_tracks": 14,
  "ids_never_emitted": 4142,
  "within_id_gap_events": 1633,
  "within_id_raw_class_changes": 497,
  "lifecycle_transition_events": 14570,
  "id_switch_count": null,
  "id_switch_count_status": "Unknown; requires physical-object temporal review, not inferred from diagnostics.",
  "traffic_count": null,
  "traffic_count_status": "Not implemented; ID totals are not vehicle counts."
}
```
