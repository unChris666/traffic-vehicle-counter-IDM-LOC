# Option B: bounded temporal pixel review

Actual source decoding and image inspection, **not resolver execution or formal ground truth**. Six cases,31 unique exact frames and16 actually opened raw/overlay artifacts. The original video and standalone decoded full-frame files remain outside GitHub. The car1323 overview contacts deliberately retain full native-frame tiles; other contacts retain bounded crops. All source tiles are lossless, without resize. Every tile carries a native BGR SHA-256, raw detector-linked emitted measurement and crop/sheet coordinate mapping.

- `sample_index.json`: extraction provenance and exact source links.
- `pixel_review.json`: observations from actual opened pixels, explicit unknowns and bounded association references.
- `artifact_validation.json`: source-link, retained-frame alignment and pixel round-trip checks.
- `manifest.json`: retained file hashes.

Development references:964/973 duplicate vehicle,923/912 component and880/893 component. Actual negative reference880/892 shows two simultaneous distinct motorcycles whose motion separates. Target1772/1774 remains excluded from numeric calibration; it was already known from user feedback, so this is not blind held-out performance evaluation. The1323=`car` reference is a user category decision; its small auxiliary d3 car box remains physically ambiguous.

Geometry overlays only draw unchanged accepted G3 and raw measured BCs. They never imply an accepted crossing/event. Source1323 is not emitted on6256 although a raw car bbox is present; no new track measurement is manufactured. Source1772 on7712 is person, and cannot be inherited as the motorcycle episode origin. Motor880 passage4987–4988 is outside this bounded component review.

Reproduce extraction (before reading the independent review):

```bash
/workspace/.venvs/traffic-inspection/bin/python docs/evidence/phase_6/verification/build_option_b_temporal_review.py \
  --root /workspace/traffic-vehicle-counter-IDM-LOC \
  --video /tmp/traffic-phase5-source/TOR3-PAGI.mp4 \
  --decoded-dir /tmp/option_b_native_review_frames
```

The command requires the actual byte-identical video and OpenCV/numpy/Pillow. It decodes10282 native frames sequentially and validates alignment with retained Phase2 frame5140. The review file is a separate actual inspection record; a reproducible extractor does not automatically recreate visual interpretations. No accuracy, precision, recall, F1, MAPE, or whole-video counting performance is claimed.
