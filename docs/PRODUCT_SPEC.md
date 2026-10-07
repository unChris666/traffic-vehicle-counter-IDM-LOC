# Product Specification

## 1. Product Goal

Provide a simple application that accepts store/location information and eight traffic videos, processes them, and returns traffic counts by category and recording period.

## 2. Final Product Pages

### Page 1 — Home

Inputs:

- Kode Toko
- Nama Toko
- Latitude
- Longitude
- 4 weekday videos: pagi, siang, sore, malam
- 4 weekend videos: pagi, siang, sore, malam

Action:

- Process

The final UI must eventually support per-video geometry configuration because camera position/orientation may vary between videos. Within a video, the camera remains at its recording position, with possible small handheld shake.

### Page 2 — Result

Show two read-only tables.

Weekdays:

| category | pagi | siang | sore | malam | total |
|---|---:|---:|---:|---:|---:|

Weekends:

| category | pagi | siang | sore | malam | total |
|---|---:|---:|---:|---:|---:|

Actions:

- Download result
- Audit result
- Edit value

Download result must export both tables as CSV.

### Page 3 — Edit Value

Two editable result tables:

- Weekdays
- Weekends

Action:

- Save

Edits are manual overrides and must not silently overwrite the original machine-generated result. The exact audit/versioning behavior is an implementation decision to be documented before production.

### Page 4 — Audit

Show a list grouped per processed video.

Each item should contain:

A. minimized video thumbnail / preview
B. KODE TOKO - NAMA TOKO
C. video type, for example `WEEKDAYS-PAGI`
D. download button for the annotated video

Annotated video should visualize detections/tracks/counting information sufficiently for human audit.

## 3. Prototype Scope

The Kaggle prototype does NOT need to implement the final web UI.

The prototype should first prove:

single video
→ detection
→ tracking
→ ReID
→ geometry
→ crossing
→ count

Then prove eight-video processing.

## 4. Non-Goals During Prototype

Do not implement initially:

- production authentication
- database
- cloud orchestration
- web deployment
- production frontend styling
- advanced user management

## 5. Geometry Configuration

A final application should provide a way for the user to define per-video:

- Side A ROI/polygon
- counting line
- Side B ROI/polygon

This is important because the videos are handheld and geometry may vary.

For the Kaggle prototype, geometry can be configured interactively in the notebook and saved as JSON.

Initial geometry is in pixel coordinates and supports configurable diagonal counting lines and Side A/B polygons. The reference example's side placement is documented in `PROJECT_CONTEXT.md`; it must not become a fixed orientation rule for other videos. The geometry anchor remains OPEN.
