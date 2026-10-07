# Evaluation

## 1. Current Evaluation Constraint

No formal ground-truth dataset exists yet.

The reference screenshot supplied by the user illustrates scene and diagonal geometry only. Its existing boxes, IDs, labels, and displayed counts are not experiment results of this repository and do not establish detector, ReID, tracking, or counting performance. Full video properties have not been measured from that screenshot.

Therefore the project must NOT report formal:

- accuracy
- precision
- recall
- F1
- MAPE
- counting accuracy

as established model performance.

## 2. What Can Be Evaluated Now

### Software Correctness

- deterministic geometry tests
- counting state-machine tests
- duplicate-count prevention
- schema validity
- pipeline integrity

### Tracking Behavior

- visual track continuity
- obvious ID switches
- track fragmentation
- detection gaps
- trajectory stability

These are observations unless a formal annotation protocol is introduced.

### Counting Behavior

- duplicate events
- obvious missed crossings
- wrong direction assignment
- wrong class at event time
- consistency between event-level output and aggregate tables

### Performance

Measure actual:

- video FPS
- processing time
- inference latency where available
- GPU memory usage where available
- CPU/RAM usage where available
- throughput per video

Do not compare systems using metrics that were not actually measured under equivalent conditions.

## 3. Recommended Future Ground Truth

Before claiming quantitative accuracy, create a manually annotated benchmark subset representing:

- morning
- noon
- afternoon
- night
- weekday
- weekend
- different road geometries
- different traffic densities
- difficult overlaps/occlusions

At minimum, annotate enough video segments to compare:

- total count
- per-class count
- directional count

A future ground-truth protocol should be documented before annotation begins.

## 4. Evaluation Protocol

When comparing model/configuration variants:

1. Use the same video subset.
2. Use the same geometry configuration.
3. Change one major variable at a time where practical.
4. Record exact configuration.
5. Keep raw evidence.
6. Report both improvements and regressions.
7. Do not cherry-pick only successful videos.

## 5. Experiment Record

Every meaningful experiment should record:

- experiment ID
- date
- video set
- model identifier
- detector settings
- tracker settings
- ReID settings
- preprocessing settings
- geometry settings
- measured observations
- conclusions
- limitations

## 6. No Ground Truth ≠ No Evaluation

Until formal labels exist, the project can still establish whether the software is internally correct and whether the system produces auditable, reproducible outputs.

However, internal correctness and visual plausibility must never be presented as measured real-world accuracy.
