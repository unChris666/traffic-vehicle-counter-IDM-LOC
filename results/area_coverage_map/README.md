# Area Coverage CPU — verification and handoff

Target `-6.409737552410453, 106.82835008971841`; buildings800m, POI2000m.
This is a scoped visible-code notebook, not the full Area package migration.

- [Notebook source](../../notebooks/area_coverage_cpu_800m_poi_2km.ipynb)
- [Kaggle execution and map](https://www.kaggle.com/code/chrisbiran/area-coverage-800m-poi-2km-cpu)
- [Setup, limits and source details](../../docs/AREA_COVERAGE_KAGGLE_CPU_MAP.md)
- [Frozen data binding](source_binding.json); private Kaggle dataset
  `chrisbiran/area-coverage-800m-source-snapshot`, version3 adds frozen OSM
  facilities; the64MB building/network data archive is unchanged from version2.
  The64MB data archive
  is intentionally kept outside Git. It contains no BigQuery credentials/data.

## Retained actual evidence

`verification/source_snapshot/` contains original acquisition/configuration,
manifest and source report, not the entire snapshot. Source9151rows; selected
3597; scenario accepted1048; unverified1083; no route88; no connector740;
over time638. Every source row reconciles; analysis remains PARTIAL.

`verification/reproducibility.json`: three host calculations, with two replay
comparisons of21calculation artifacts each, no differences, network forbidden
during replay. This is not a claim of cross-runtime byte identity.

`verification/tests.log`:13offline tests pass. Live BigQuery schema/query and
real POI markers remain unverified, because owner credentials are unavailable.

`verification/kaggle_v2/`: retained actual completed CPU execution, runtime,
output manifest and summaries. Both BigQuery sources BLOCKED; counts null,
not zero. Kaggle decisions reconcile to the host counts above.

`verification/kaggle_v3/`: historical source completed CPU execution. Its
visible-code fingerprint identifies that baseline; the full calculation
manifest matches V2. Both BigQuery sources remain BLOCKED, not zero. Result
view29fd5925e13c40a852416f937eeeff4fb6d07d1805c1929da2f00b208e282d42
was retained in that Kaggle output. This does not validate private BQ data.

`verification/poi_v1/` and [POI binding](poi_binding.json): actual frozen OSM
facility source71features within2km, raw response, rules and source timestamp.
Eight separate categories; OSM feature identity does not prove unique physical
sites or exhaustive facilities. New notebook uses user-confirmed secret label
`PROJECT_PPAC`;400m store circles are display-only layers.

`verification/kaggle_v4/`: latest actual CPU run COMPLETE.9151source rows and
3597selected; calculation manifest unchanged from V3.71OSM facilities displayed
and exported,15layer toggles validated in Chromium. Both private BQ sources
remain BLOCKED/null: reading `PROJECT_PPAC` raises ConnectionError before a query.
This does not prove incorrect IAM or an invalid key.400m positive rendering is
validated by a separate synthetic regression fixture, not by invented stores.
Only BQ readiness metadata is retained here; raw private data/maps stay in the
private Kaggle output. Source code fingerprint:
`2a455703bb19fa5d6cd027d78cd4d8434bc0b3b16b178f13531aa971eabfbc21`.

`verification/browser/`: actual Kaggle V2 HTML opened in Chromium; layer toggle
works, center and both radii verified, no JS/resource errors. Screenshot is from
the real generated map with public building/network sources and unavailable
BigQuery layers. Original HTML checksum is recorded in the receipt.

Kaggle V1 failed on dataset auto-decompression changing nested source bytes.
The manifest check was preserved. Dataset V2 uses a `.snapshot` data container
and `.data` inventory to retain the immutable byte representation.

Do not treat `MAP_READY` as production access/ETA validation. Private query data
must stay in the private Kaggle output/cache, not be committed here.
