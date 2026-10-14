# Actual TOR3-MALAM temporal passage review

Raw and frozen gamma0.7 were executed in Kaggle over all9,590 source frames. This review compares eight candidate physical passages within the five predeclared windows, plus three controls. Track IDs are local to each variant. No model, tracker, encoder, geometry replay or counting resolver was rerun here.

All22 new contact PNGs were actually opened. Their73 unique native-frame donor pixels and measured raw-bbox links passed601/601 checks. This is bounded review evidence, not ground truth or exhaustive vehicle counts.

| Physical passage/crossing | Split | Raw / gamma tracks | Machine raw → gamma | Review proposal |
|---|---|---|---|---|
| dev_beginning_motorcycle_27 / 26→27 | development | 4 / 7 | pending_review → pending_review | CONFIRM_PASSAGE |
| dev_beginning_motorcycle_113 / 112→113 | development | 15 / 15 | pending_review → accepted | CONFIRM_PASSAGE |
| dev_quarter_motorcycle_2297 / 2296→2297 | development | 409 / 432 | pending_review → pending_review | CONFIRM_PASSAGE |
| holdout_middle_motorcycle_4869 / 4868→4869 | holdout | 564 / 587 | pending_review → pending_review | CONFIRM_PASSAGE |
| dev_three_quarters_truck_7114 / 7113→7114 | development | 810 / 829 | pending_review → pending_review | CONFIRM_PASSAGE |
| dev_three_quarters_motorcycle_7170 / 7169→7170 | development | 819 / 841 | pending_review → pending_review | CONFIRM_PASSAGE |
| dev_three_quarters_car_conflict_7244 / 7243→7244 | development | 835 / 856 | pending_review → pending_review | HOLD |
| holdout_end_motorcycle_9356 / 9355→9356 | holdout | 1198 / 1223 | pending_review → pending_review | CONFIRM_PASSAGE |

Gamma's one accepted motorcycle15 is visually one unit with its rider(s), and crossing uses vehicle BC112→113. Raw's same local identity observations would pass the numeric motion control, but global relation admission also includes later115→116; gamma's intervening bicycle labels end its vehicle episode114. The acceptance difference therefore exposes offline episode/policy sensitivity as well as pixel/bbox changes. It is not proof of a generally better night pipeline or of ReID improvement.

Seven physically reviewed passages have reviewable identity-only holds or an already accepted event. The white passenger vehicle remains pending because CATEGORY_CONFLICT is a hard blocker in both complete vehicle-episode histories. The review inputs propose resolution only; accepted overlay numbers belong to the separately executed guarded overlay.

Hold-out middle/end motorcycles remain machine pending in both conditions. Gamma brightens visible pixels but does not establish a new hold-out accepted passage or recover the glare-only unknown bodies at4674/9589. Additional gamma false car labeling on motorcycle pixels2277 and observation/category changes are retained as regressions. No hold-out result was used to retune the frozen candidate.

The separately guarded review overlay subsequently executed after32/32 software tests. [Raw reviewed output](../raw_reviewed/report.json) contains7accepted/1pending, all seven accepted through explicit review. [Gamma reviewed output](../gamma_070_reviewed/report.json) also contains7accepted/1pending: six through explicit review and the unchanged automatic motorcycle15 event. Both reviewed snapshots contain6motorcycles+1truck, direction1A_TO_B/6B_TO_A, while the same passenger-vehicle category conflict remains pending. These totals cover the eight reviewed candidate passages only. Seven versus seven after review does not prove automatic gamma improvement or whole-video completeness.

The [physical-passage JSON](physical_passage_comparison.json) and review-input files remain the immutable pre-overlay proposals; actual merged comparison results are retained separately. See [pixel review](pixel_review.json), [raw review input](raw_review_input.json), and [gamma review input](gamma_070_review_input.json).
