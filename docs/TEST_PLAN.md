# Test Plan

## 1. Ground Truth Status

No formal ground-truth dataset currently exists.

Therefore, model accuracy and counting accuracy are NOT current acceptance criteria.

This document specifies future checks, not executed results. Phase 0 validation is specification consistency; Phase 1 video inspection is prepared in `PHASE_1_TASK.md` and has not started.

## 2. Test Levels

### Unit Tests

Test deterministic logic independently from the model:

- point-in-polygon
- line intersection
- side classification
- trajectory transition
- duplicate-count prevention
- state-machine transitions
- aggregation

### Integration Tests

Test the pipeline boundaries:

- detector output → tracker input
- tracker output → geometry
- geometry → counting event
- events → aggregation

### End-to-End Tests

Run representative videos through the complete pipeline and verify that:

- output video is produced
- track IDs exist
- events are produced in the expected schema
- result aggregation is internally consistent

## 3. Detection Invariants

- bounding boxes have valid coordinates
- confidence values are valid
- class IDs are from the configured class set
- detections are serializable/loggable

## 4. Tracking Invariants

- active track IDs are unique within a video
- track state is updated consistently
- temporary detection gaps do not automatically imply a new physical object
- track history is monotonic in frame order

Do not assume a tracker can guarantee identity under every occlusion. Such behavior must be evaluated empirically.

## 5. Geometry Tests

Use synthetic points/trajectories to test:

- points inside Side A
- points inside Side B
- points outside both regions
- line intersection
- diagonal trajectories
- movement parallel to the line
- movement that touches but does not cross
- crossing with jitter near the line
- arbitrary per-video diagonal line/polygon placement in pixel coordinates
- explicitly configured anchor candidates, without treating a candidate as an accepted default

These tests do not require a trained model or ground truth.

## 6. Counting Tests

Required invariants:

- one valid A → B crossing produces one event
- one valid B → A crossing produces one event
- repeated frames after crossing do not produce duplicate events
- jitter around the line does not create repeated events
- an ineligible track does not create a count
- changing class confidence alone must not create a new vehicle
- an object visible in an eligible region in the first processed frame is not counted on presence alone
- an eligible initial-frame object can produce an event after a subsequent valid crossing and opposite-side arrival
- bounding-box contact with the counting line alone does not produce an event
- a crossing without confirmed arrival in the opposite configured side does not produce an accepted directional event

Temporary gaps, ID switches, re-entry, and genuine repeated crossings require documented identity/deduplication policies before their final acceptance tests are specified. Noise-induced re-crossing must not create duplicates; the business rule for a genuine return crossing remains OPEN. Do not mask an unresolved policy with a passing test.

## 7. Night Preprocessing Tests

Treat each preprocessing variant as an experiment.

For identical sampled frames, compare configured variants such as:

- raw
- gamma
- brightness/exposure
- contrast
- sharpening
- combinations only when justified

Record actual observations.

Do not claim improvement without evidence.

## 8. Regression Tests

Once a behavior is accepted, preserve a minimal fixture or deterministic test so future refactors do not silently change it.

## 9. Manual Validation

Because ground truth is unavailable, maintain a small manually inspected audit set.

For each inspected video, record:

- video identifier
- geometry configuration
- model configuration
- preprocessing configuration
- observed count behavior
- obvious false detections
- obvious ID switches
- duplicate counts
- missed crossings

Manual inspection is evidence, but it is not a statistically rigorous accuracy benchmark.

## 10. Test Reporting

Every implementation task should report:

- tests executed
- tests passed
- tests failed
- tests not run
- relevant assumptions
- unresolved issues
