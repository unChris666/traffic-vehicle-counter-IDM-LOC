# P1 source fixture — blocker4843

**FACT — source evidence:** native TGDI-WEEKDAY-SIANG source video and cached
measurements match the retained B v7 SHA256 identities. This fixture retains211
raw source-frame records7800–8010 and168 emitted target measurements for4808,
4843 and4913. Seventeen selected frames were decoded sequentially from frame0;
all17 BGR pixel hashes match the frozen detector-input hashes. No model,
tracker, ReID, enhancement or counting replay was executed to build this package.

**REQUIREMENT — supplied user review:** the red motorcycle passage must produce
exactly one accepted event; a blue motorcycle merely appearing on the destination
side while moving away from the line must not receive an unsupported count.
The actual uploaded brief is retained byte-for-byte as `user_task.txt`.

**AI PIXEL ADJUDICATION — raw IDs and scope:** mapping the reviewed physical
vehicles to raw IDs and frame intervals is this source review, not a new human
raw-ID annotation or a model prediction. It is explicitly a development/reviewed
input. No machine claim of automatic identity recovery is made.

## Source interpretation and geometry

| Source scope | Physical interpretation | Evidence |
|---|---|---|
|4808, reviewed7860–7907|Red motorcycle with dark-shirt rider/tan trousers approaches the line|Visible before the SUV; co-present with blue4843 at7874,7888,7899 and7905 |
|4843,7874–7905|Blue motorcycle distinct from red4808|Both vehicles visible concurrently before SUV occlusion |
|4843,7928–7955|Red motorcycle after SUV occlusion|The detector box now encloses the red bike; at7950 red4843 and blue4913 are simultaneously separate |
|4913,7950–7964|Blue motorcycle observed in B, moving farther from the finite line|BC signed distance increases from+153,03 to+260,12px; no origin/band measurement exists in this raw track |

The last row does not prove a U-turn or prove the bike never crossed. This
fixture does not positively link the blue pre-occlusion context to4913 across
the gap. Its destination presence alone supplies no independently eligible
crossing. An identity/passage connection remains unestablished under this review.

The line and polygon bytes are the existing native640×480 TGDI geometry;
half-margin remains25px. Numeric geometry observations are calculated directly
from each unchanged raw vehicle bbox bottom-center, not from a rider or a
predicted point:

- Red4808 is in A at7899/7904; at7904 BC signed distance is−30,96px.
- Red4808 touches the **finite margin band** at7907, distance−24,78px.
- After occlusion, red4843 is in B at7928, distance+70,44px, and7935,+106,95px.
- There are20 missing source frames between red measurements7907 and7928.
  A recovered crossing from this sequence must remain **LINE_MARGIN inferred**.
  It cannot become a measured crossing or acquire synthetic BC observations.

## Reviewed reconstruction proposal

`review_overlay.json` uses the existing `phase8_b_v4_review_overlay_v1` schema
and the same frozen donor-manifest hash. It passed the unchanged B v4 overlay
validator; see `overlay_validation.json`. All pixel anchors bind
`pixel_evidence.json`, which includes exact source detection indices/bboxes.

1. A single `SAME_VEHICLE` review connects red4808 only during7860–7907 and
   red4843 only during7928–7955, sharing one reviewed unit and episode.
2. A `SPLIT_IDENTITY` review gives blue4843 only during7874–7905 a distinct
   source context. Its origin/timer cannot be inherited by the red post-gap
   context. This is a frame-bounded change, not a raw-ID-wide blacklist.
3. Blue4913 is left without a positive cross-gap identity link. Its B-side,
   away-from-line observations alone do not create an accepted passage.

The reviews have `claim_type=ADJUDICATED_AI_PIXELS_REVIEW` and
`human_confirmation_status=NOT_NEWLY_ADJUDICATED_BY_USER`. Explicit user physical
case authority is bound separately by the uploaded-brief path/hash. A reviewed
result must remain separately identified from the unchanged B v7 machine result.

**EXPECTED TEST OUTCOME, not an executed result in this package:** reviewed
replay reconstructs exactly one eligible red passage, retains inferred
provenance, prevents a duplicate timeout/inferred event from the same passage,
and produces no unsupported blue or genuine-return count. Parent P1 execution
must verify this expectation through the generic review adapter and frozen
counting engine. This evidence task did not execute counting.

## Files

- `source_records_7800_8010.json.gz`: full context records, not target-only data.
- `selected_measurements.json.gz`:168 source-linked measurements, their raw BC,
  ROI and finite-band diagnostics.
- `geometry_measurements.csv`: inspectable numeric geometry per observation.
- `source_contact_1.jpg`–`source_contact_3.jpg`: bounded temporal source images
  annotated with raw IDs and the existing finite line.
- `source_decode_receipt.json`:17 exact pixel hashes and source identities.
- `pixel_evidence.json`: existing-overlay-compatible proofs including source
  detection indices, classes and bboxes.
- `review_overlay.json`: proposed reviewed reconstruction data; no hardcoded
  case/rawID/color rule belongs in runtime code.
- `build_source_fixture.py`: source-only extraction procedure; deliberately
  refuses to overwrite an existing completed decode receipt.

This source case is development, not hold-out, not full-video ground truth, and
not evidence that all neighboring vehicles or return passages are resolved.
