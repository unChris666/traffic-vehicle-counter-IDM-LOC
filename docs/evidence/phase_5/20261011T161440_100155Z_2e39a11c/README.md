# Phase 5 — actual CPU geometry replay

Run `20261011T161440_100155Z_2e39a11c` executed [source notebook](../../../../notebooks/05_geometry_replay.ipynb) in Codex CPU. [synthetic_test_results.json](synthetic_test_results.json) records40/40PASS before six controls/sensitivitycells. Everycell processed10282frames/48228raw-linkedemittedmeasurements/997softwareIDs; no model inference.

Per-cell `*_report.json` and `*_diagnostics.jsonl.gz` retain source/code/config hashes and actual geometry diagnostics. [execution_manifest.json](execution_manifest.json) is original runmanifest; [retention_manifest.json](retention_manifest.json) covers later retention/audit/analysis additions. [replay_audit.json](replay_audit.json) records25independentPASS checks from artifacts, not pipeline rerun. [temporal_replay_review.json](temporal_replay_review.json) compares exact crossing-frame keys and prioritycases.

[executed_notebook.ipynb.gz](executed_notebook.ipynb.gz) preserves actual executed notebook bytes including outputs; [notebook_retention.json](notebook_retention.json) records decompressed SHA/size. Original video is excluded.

```bash
gzip -dc docs/evidence/phase_5/20261011T161440_100155Z_2e39a11c/executed_notebook.ipynb.gz > /tmp/phase5_executed.ipynb
```

Default suitability remainsOPEN; diagnostic totals are not vehicle counts. See [full review](../../../PHASE_5_REVIEW.md) and [later targeted original-pixel review](../20261012_temporal_review/README.md).
