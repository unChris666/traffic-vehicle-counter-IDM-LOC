# G3 — new relative template after scaled-image feedback

**USER DECISION:** [G2 feedback 001](../../feedback/G2_review_001.json) confirms the supplied coordinates came from a scaled image, revises A using four exact points, and selects a relative template with per-video review. [Feedback 002](../../feedback/G2_review_002.json) says the original dimensions are unknown and delegates preparation of a default, with a future line/polygon setup page.

**PROPOSAL — new reference canvas:** 960×540 accommodates all supplied coordinates and matches this video's 16:9 aspect ratio. This is a new engineering convention under that delegation. It is not a discovered size of the original screenshot or a recovered resize/crop transform. G3 interprets the supplied values in this new template solely to produce a concrete reviewable default. Original display dimensions, margins and crop remain UNKNOWN.

G1/G2, their original manifests and feedback remain unchanged. G2's native1280×720 interpretation is refuted. Its placement arithmetic is reproducible for that old interpretation but cannot support conclusions about the user's intended gate. In particular, the small boxes observed near the old G2 line are not findings about this G3 placement.

## Review artifacts

Open [review.html](review.html) to compare overlays with the unchanged native frame. [SVG](TOR3-PAGI-G3.svg) embeds the byte-identical retained raw PNG; [PNG](TOR3-PAGI-G3.png) is its browser rendering. [candidate_geometry.json](candidate_geometry.json) retains reference, normalized and native-preview coordinates separately. [manifest.json](manifest.json) records artifact hashes.

Source: retained TOR3-PAGI frame5140, 1280×720. The same actual Phase 4 ReID-on track973/detection1 supplies the raw bbox and BC example. BC remains user-selected; an operational raw-versus-filtered box source has not been agreed. No detector, tracker or encoder is rerun to make this figure.

## Exact input and proposed polygon perimeter

The original reply labels all four points `P1`. They are retained in the JSON with their supplied order. Connecting that list as a polygon creates a crossing near `(289.9513,335.2152)` in the supplied coordinate units. The [independent static review](supplied_coordinate_review.json) retains that arithmetic and its [method](../../verification/check_supplied_polygon_coordinates.py). The proposed simple perimeter swaps the last two points without moving any point:

`(4.5,516.5) → (4.5,348.2) → (557.5,165.3) → (936.6,305.8)`.

The line remains `P1=(4.5,516.5)` to `P2=(936.4,305.4)` in template units. P2 is distinct from the polygon's right vertex `(936.6,305.8)`; the difference is preserved, with no snapping or selected tolerance.

**PROPOSAL — B:** share A's lower polygon edge, clip it at X875, and use a lower drawing margin of532.5/540 (the earlier710/720 margin). Its vertices are `(4.5,516.5)`, `(875,319.72460036476775)`, `(875,532.5)`, `(4.5,532.5)`. This is an engineer-adjusted outline, not a polygon approved by the user. A/B interiors are separated by their shared edge; the counting line is slightly offset from that edge. Whether the final line should coincide with the region edge remains a review decision; no numerical neutral band is inferred from that offset.

The complete line extends beyond B's cap. Detection/tracking remain full-frame, and these coverage envelopes include background. They are spatial eligibility proposals, not asphalt segmentation or one polygon per traffic lane. Side presence alone does not establish movement direction.

## Relative coordinates and per-video configuration

**USER-CONFIRMED POLICY:** a relative template, with review per video.

For this proposed reference, store `u=x/960`, `v=y/540`. For a full native frame of dimensions `W×H`, the review mapping is `x=u×W`, `y=v×H`. These are continuous image-edge coordinates; pixel-array indexing is a separate matter. This diagram uses the complete source frame without crop, rotation or letterbox. Other transforms require explicit configuration, not blind reuse of these equations.

For the current1280×720 preview:

| Element | Native-preview pixels |
|---|---|
| Line P1 | `(6.0,688.6666666666666)` |
| Line P2 | `(1248.5333333333333,407.2)` |
| B maximum X | `1166.6666666666667` |

These mapped values are consequences of the new proposed canvas, not reconstructed original positions. Different aspect ratios scale the template in each image axis; viewpoint/road geometry and spatial preprocessing still require review and may need overrides. Each accepted configuration should retain video/frame dimensions, template version, effective vertices/endpoints and any explicit spatial mapping.

The user reiterates a future per-video setup page. It belongs to Phase11 UI and will edit/save each video's effective geometry before processing. This offline viewer is a review aid; its pointer or toggles do not edit or save a pipeline configuration. No product UI is implemented here.

## Remaining contract decisions

User feedback revises polygons and selects the template policy; it does not explicitly accept the earlier crossing-rule proposal. Still proposed: observed raw-bbox BC, finite line segment, neutral boundaries, touch-only exclusion, ambiguous endpoint/gap passage, and no acceptance using Kalman predictions. Origin → line passage → observed arrival at the opposite side remains required by the existing specification.

Polygon perimeter/B outline, endpoint alignment, operational box source and qualitative gap/boundary rules need review before the agreed synthetic-trajectory stage. Neutral-band width and destination confirmation remain unset and are investigated later. Changed-ID duplication, category/rider association and genuine return-count business rules stay OPEN for Phase6. No accepted crossing state-machine replay, synthetic crossing tests, traffic totals or all-video reliability are established by this figure.

## Reproduce the figure

From the repository root:

```bash
python docs/evidence/phase_5/verification/build_g3_review.py
python docs/evidence/phase_5/verification/check_g3_review.py
```

[figure_validation.json](figure_validation.json) reports actual source, coordinate, static draft-topology and browser-control checks. Static topology verifies this proposed drawing, not a synthetic trajectory or accepted crossing contract. Numerical roundoff handling in verification does not select any noise, hysteresis or gap threshold. No Phase1–4 model processing is repeated.
