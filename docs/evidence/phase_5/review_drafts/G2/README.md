# TOR3-PAGI G2 — revised geometry for review

**USER DECISION:** [feedback 002](../../feedback/G1_review_002.json) selects P1 `(4.5,516.5)`, P2 `(936.4,305.4)`, bottom-center (BC), B maximum X `875`, and A→B approaching / B→A away. It authorizes adapting polygons to the new line and requests a reliable shared default. [Feedback 001](../../feedback/G1_review_001.json) and [G1](../G1/README.md) remain historical evidence.

**ASSUMPTION requiring confirmation:** these coordinates refer to the native 1280×720 G1 viewer, origin upper-left, X rightward, Y downward. They must not be silently applied to a smaller display, crop, or another resolution. If the user's source was a scaled image, resolve its dimensions before adopting effective pixel geometry.

Open [review.html](review.html) to toggle annotations, compare the unchanged original, and inspect coordinates. [SVG](TOR3-PAGI-G2.svg) uses an embedded byte-identical retained raw frame; [PNG](TOR3-PAGI-G2.png) is its browser rendering. [candidate_geometry.json](candidate_geometry.json) records source/track links, decision status and coordinates; [manifest.json](manifest.json) records retained artifact hashes. No model or tracker was rerun.

## Proposed polygon adjustment

The line remains the complete user-specified segment, including P2 at X=936.4. B's outline stops at X=875; its shared-line vertex has interpolated Y≈319.308724. This is drawing geometry, not a selected noise threshold. The proposed outlines are:

- A: `(50,425)`, `(330,425)`, `(936.4,305.4)`, `(4.5,516.5)`, `(45,470)`.
- B: `(4.5,516.5)`, `(875,319.30872411202915)`, `(875,710)`, `(180,710)`, `(120,545)`.

**PROPOSAL:** these coverage envelopes adapt G1 under the user's delegation. Their exact vertices were not supplied or approved by the user. They include background and are not asphalt segmentation or one polygon per traffic lane. Detection/tracking remain full-frame; geometry later constrains eligibility.

**OBSERVATION — source frame 5140:** much of the line runs across background above the road; P2 is above the house/sky. It crosses the distant left road view. BC for actual ReID-on track 973 is `(248.87887573242188,545.7120971679688)`, from linked raw motorcycle bbox/detection 1. The cyan center is retained as a visual comparator; BC is selected by the user, not proved superior or guaranteed to be a tire-contact point.

**READ-ONLY PLACEMENT SCREENING:** [placement_screening.json](placement_screening.json) retains source-linked arithmetic brackets for three actual tracks. Around the new line, example raw boxes are about 56×42–43 pixels for track 1/car, and 21×31–32 pixels for tracks 485/973/motorcycle. They illustrate the small scale of vehicles at this gate. They are not eligible crossings, unique physical identities, traffic totals, a state-machine replay or an accuracy benchmark. Effects on robustness remain hypotheses. Alignment across the entire video is not established by one frame or Phase 1's short bursts.

## Concrete contract proposal for the next stage

These choices are **PROPOSAL**, not silently accepted defaults:

1. Effective line and polygons use native decoded-frame pixels and the declared reference dimensions. A mismatched coordinate reference requires an explicit mapping/review.
2. Test the finite P1–P2 segment; crossing its infinite extension is insufficient. Touch-only/along-line motion is insufficient. A crossing exactly at an endpoint is ambiguous and retained for review initially.
3. A/B interiors must not overlap. Shared polygon edges and points on boundaries are neutral; outside both polygons does not establish an origin/destination. A neutral band and destination confirmation are configurable; their numerical values remain unset.
4. BC is `((raw_bbox.x1+raw_bbox.x2)/2, raw_bbox.y2)` from detector-linked emitted track observations. Kalman predictions and `bbox` filtering do not supply independent observed crossings. This measurement-source choice still needs agreement; the selected anchor alone does not settle it.
5. Establish origin-side evidence, then line-passage evidence, then observed arrival in the opposite region. Merely appearing in the initial frame supplies no accepted crossing. Direction comes from this temporal order and the video's confirmed metadata.
6. If observations disappear across a possible crossing, retain an ambiguous candidate; do not invent observations, interpolate an accepted event, or use predicted positions to accept it. A bounded gap-recovery policy needs a separate decision and evidence.
7. Jitter near the line must not repeatedly accept the same transition. Investigate neutral-band width and confirmation using retained observations after synthetic logical tests; there is no guessed production threshold here.
8. Changed-ID deduplication, rider/vehicle/category association and genuine return-crossing business rules stay OPEN for Phase 6. Phase 5 tests/replay must mark these limitations rather than emit vehicle totals.

Required agreement is about the coordinate reference, polygon coverage and qualitative contract. Numerical parameters are chosen after evidence, as requested by the staged workflow. No synthetic crossing tests, accepted crossing state-machine replay or parameter decision has been executed for G2.

## Shared default across videos

**REQUIREMENT:** the user requests a shared default line and reliable behavior across videos.

**PROPOSAL:** retain the 1280×720 reference template; represent its positions as `u=x/1280`, `v=y/720`, then explicitly map to target pixel dimensions. The B cap is likewise relative. This is an image-coordinate scaling convention, not world projection or homography. Crop/rotation/letterboxing need a declared transform rather than blind scaling.

The transfer policy remains unselected. Scaling addresses dimensions only. Different camera viewpoints, road positions, lighting, vehicle sizes and camera motion still need per-video review and may require overrides. A saved default does not establish reliability; no all-video performance or suitable final threshold is claimed.

## Reproduction and boundaries

From the repository root:

```bash
python docs/evidence/phase_5/verification/build_g2_review.py
python docs/evidence/phase_5/verification/check_g2_review.py
```

The first command rebuilds the figure/configuration draft from repository-retained G1 source provenance. The second checks source/feedback consistency and actual browser controls, and renders the PNG with Playwright/Chromium. [figure_validation.json](figure_validation.json) records actual results; these are figure/source checks, not synthetic crossing acceptance tests. Phase 1–4 source evidence is preserved. No Phase 6 aggregation, detector/tracker/ReID inference, enhancement, stabilization, UI product, Docker or multi-GPU orchestration is implemented.
