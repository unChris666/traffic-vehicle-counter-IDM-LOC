# Phase 7 retained evidence — TOR3-MALAM

Actual Kaggle screening and temporal runs completed on 14 October 2026. Read the [engineering review](../../PHASE_7_REVIEW.md) and [final experiment decision](selection/TOR3-MALAM_final_decision_v1.json) first. Raw remains the next research baseline; no production enhancement is selected.

Evidence is separated by purpose:

- `authorization/`, `feedback/`, `accepted_geometry/`: user decisions and source-bound N1 approval. Historical geometry proposals remain separate.
- `sampling/`, `config/`, `selection/`: declared DEV/hold-out windows, fixed controls, immutable DEV shortlist and final decision after actual review.
- `screening/20261014T060849_366767Z/`: original15-frame/five-variant GPU outputs, source snapshots, independent audit and DEV visual review.
- `temporal/20261014T062858_002323Z/raw/` and `gamma_070/`: original9,590-frame caches, CUDA/appearance observer evidence, geometry/episode/relation diagnostics and machine counting outputs. The original85-artifact run manifest stays unchanged.
- `temporal/.../temporal_review/`: actual22-contact/73-frame pixel review, eight matched physical passages and three controls, review inputs and the guarded application method. Original proposal JSON remains a pre-overlay review record.
- `temporal/.../raw_reviewed/` and `gamma_070_reviewed/`: separately executed manual snapshots. Each contains seven accepted passages and one category-conflicting pending item; raw7manual, gamma6manual plus its original automatic event. These are scoped passage subtotals, not complete traffic or new automatic success.
- `temporal/.../final_physical_passage_comparison.json/.csv`: joins actual machine and reviewed statuses by physical passage, without model/geometry/resolver replay.
- `kaggle_submission/`: exact submitted source notebooks/metadata, actual logs and execution provenance. Submitted notebooks are not represented as executed-output notebooks.
- `baseline_retention/`: original Phase6B context bytes before status documentation changed. Original A/B source, controls, outputs and manifests remain immutable.
- `verification/`: synthetic test results, independent checkers, packaging reproduction and tested cloud audit setup. Final validation binds the final retention manifest; those two files are excluded from recursive hashing.

No original video, detector weights or encoder weights are included. Source/model SHA and official asset URLs are retained. Source timing uses decoder indices; no verified PTS/VFR decision or formal ground truth exists. Embedding vectors and cost matrices are not retained for independent numeric association recomputation.

Kaggle runs are private in the owner's account:

- [Screening](https://www.kaggle.com/code/chrisbiran/phase-7-tor3-malam-enhancement-screening)
- [Temporal comparison](https://www.kaggle.com/code/chrisbiran/phase-7-tor3-malam-temporal-comparison)

The packaging builders reproduce the exact submitted bytes without executing models. GPU execution is not required to read or audit the existing artifacts. All source-pixel decode checks need the byte-identical external video; the final retention/event checks use retained artifacts only:

```bash
cd /workspace/traffic-vehicle-counter-IDM-LOC
/workspace/.venvs/phase7-audit/bin/python \
  docs/evidence/phase_7/verification/check_final_phase7_retention.py --repo .
```

This verifies the frozen manifest; omit `--capture` during routine review. The cloud setup draft saves install/start instructions only. Review/save it in environment settings and publish the environment to persist the configuration/snapshot; publication and fresh-task restoration were not executed or claimed by this task.
