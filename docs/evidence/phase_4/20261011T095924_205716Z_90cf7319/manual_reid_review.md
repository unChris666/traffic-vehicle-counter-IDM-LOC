# Subsequent Phase 4 review — TOR3-PAGI

**EXPERIMENT RESULT:** both variants completed 10,282 cached frames. This is a later **AI-assisted** review of actual retained pixels and source-linked records, not human ground truth. The original execution exports remain unchanged, including their then-pending review fields. Exact scope, hashes and limitations are in [manual_reid_review.json](manual_reid_review.json); [artifact_audit.json](artifact_audit.json) passed 19/19 checks.

| Reviewed case | ReID off | ReID on | Supported conclusion |
|---|---|---|---|
| Same red scooter | Concurrent 1934/1951 | Concurrent 964/973 | Observed duplicate remains. |
| Entering rider/scooter | 3681/3683 class/component handoff | 1772/1774, same source/class sequences | Handoff remains. |
| Roadside gap | 3622 returns after 7713–7717 | 1731 returns after same gap | Existing local recovery preserved; extra benefit not demonstrated. |
| Small beginning car candidate | 6/8/9/10/11 remain unconfirmed | 6 confirmed/reacquired at 11/16/19/29 | Real appearance-cost/association difference; physical benefit unestablished because target is small and label-covered. |
| Receding/end controls | Local component/car continuity | Local component/car continuity | No apparent new regression at the displayed positions; no whole-video correctness claim. |

ReID produced 50,713 finite nonzero 512D features. First actual encoder-update profile records 137 CUDA and 20 CPU node events. Association runs on CPU; GPU 1 was unused. Loop time was 41.1397 seconds off and 422.9125 seconds on, including instrumentation, decode and serialization. This is not an optimized production benchmark; encoder time is already inside tracker-update time.

**EXPERIMENTAL DECISION:** reject this tested untuned configuration as the current vehicle-ReID default. The reviewed priority problems persist, physical benefit is not established here, and measured processing cost is higher. This does not establish universal ReID failure or remove ReID from the architecture; final vehicle configuration remains OPEN.

Phase 4's scoped contribution experiment is complete. Phase 5 may follow with synthetic deterministic geometry after its contract is explicit; this does not establish counting readiness. See [PHASE_5_READINESS.md](../../../PHASE_5_READINESS.md).

Review covered 6 paired red-scooter positions, 8 paired entry positions, selected native 7712/7713/7718 images, 18 displayed control positions, and 15 beginning clip-derived crop positions. Full sequences were audited as software records, but were not fully annotated visually. OpenCV final `read_false` after all expected rows leaves EOF versus terminal decode condition unresolved; all 10 exported 30-frame clips decoded. Source timestamps are not verified. No formal ground truth, identity/counting metrics or physical vehicle totals exist.
