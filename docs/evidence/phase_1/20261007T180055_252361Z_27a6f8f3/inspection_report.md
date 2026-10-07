# Phase 1 — one-video inspection report

Run: `20261007T180055_252361Z_27a6f8f3`
Input: `/kaggle/input/datasets/chrisbiran/traffic-tracker-videos/TDLE-PAGI.mp4`
Status: **evidence_saved_manual_review_pending**; review: **incomplete_unknown_items**
SHA-256: `7a5e1a3dd55c83549326515398d1eeadc07d223eea171626058fd1bfae61a46c`

## Metadata (executed probe/decode evidence)

| Field | Value | Provenance |
|---|---|---|
| Filename | TDLE-PAGI.mp4 | selected discovered file |
| File size bytes | 12506413 | filesystem stat |
| width | 640 | ffprobe.width |
| height | 480 | ffprobe.height |
| frame_count | 8960 | ffprobe.frame_count |
| fps | 29.761652209830647 | ffprobe average frame rate; constant-FPS status unknown |
| duration_seconds | 301.058555 | ffprobe.stream_duration_seconds |
| codec | h264 | ffprobe codec_name |
| Decoded frame count | 8960 | sequential OpenCV first pass; completeness unverified |

## Manual visual observations

| Item | Observation | Evidence |
|---|---|---|
| camera_position (UNKNOWN) | UNKNOWN | UNKNOWN |
| camera_orientation (UNKNOWN) | UNKNOWN | UNKNOWN |
| road_orientation (UNKNOWN) | UNKNOWN | UNKNOWN |
| approximate_viewing_angle (UNKNOWN) | UNKNOWN | UNKNOWN |
| handheld_shake (UNKNOWN) | UNKNOWN | UNKNOWN |
| camera_stability (UNKNOWN) | UNKNOWN | UNKNOWN |
| lighting_condition (UNKNOWN) | UNKNOWN | UNKNOWN |
| vehicle_visibility (UNKNOWN) | UNKNOWN | UNKNOWN |
| occlusion (UNKNOWN) | UNKNOWN | UNKNOWN |
| blur (UNKNOWN) | UNKNOWN | UNKNOWN |
| reflections (UNKNOWN) | UNKNOWN | UNKNOWN |
| shadows (UNKNOWN) | UNKNOWN | UNKNOWN |
| vehicles_entering_exiting (UNKNOWN) | UNKNOWN | UNKNOWN |
| diagonal_vehicle_movement (UNKNOWN) | UNKNOWN | UNKNOWN |
| geometry_feasibility (UNKNOWN) | UNKNOWN | UNKNOWN |
| geometry_alignment_over_time (UNKNOWN) | UNKNOWN | UNKNOWN |
| low_light_detection_risk (HYPOTHESIS_UNTESTED) | UNKNOWN | UNKNOWN |
| low_light_tracking_risk (HYPOTHESIS_UNTESTED) | UNKNOWN | UNKNOWN |
| low_light_reid_risk (HYPOTHESIS_UNTESTED) | UNKNOWN | UNKNOWN |
| potential_failure_cases (HYPOTHESIS_UNTESTED) | UNKNOWN | UNKNOWN |
| technical_questions (OPEN) | UNKNOWN | UNKNOWN |

## Decode warnings and limitations

- Average and nominal frame rates differ. This alone does not prove variable frame rate; inspect timestamps if needed.
- No detector/tracker/ReID/counting execution or ground-truth evaluation.
- Human observations depend on inspected evidence; unknown items are not fabricated.
- Representative fractions use decoded frame indices; VFR elapsed-time quartiles may differ.
- OpenCV read failure does not distinguish EOF from damaged/unsupported frames.
- Backend timestamps and FPS-derived timing are recorded with uncertainty.
- Short bursts can miss rare shake/events; inspect more evidence if needed.
- Display copies are resized; geometry/visibility assessment should also use native PNGs.

## Evidence

- Native frames and burst manifests: see `run_manifest.json`.
- The contact sheet and temporal previews are display aids; native PNGs retain decoded dimensions.
- No Phase 2 work is started or validated by this report.
