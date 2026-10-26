<!-- current-status:2026-10-27 -->
> Sinkronisasi 27 Oktober 2026: [status sistem saat ini](CURRENT_STATUS.md) adalah rujukan runtime dan integrasi. Versi/hasil/fase bertanggal di dokumen ini berlaku pada cakupannya saat ditulis; tidak membuktikan status rilis atau akurasi terbaru. Runtime Traffic kini memakai kandidat FP32 dan antrean satu video per GPU.

# Area Coverage — OSM source profile

24 Oktober2026. Owner authorizes OSM buildings→selection→OSM directed motor
graph→routing→calculation→OSM basemap. Traffic and historical Overture outputs
remain unchanged. This is a new source experiment, not an accuracy claim.

## Active notebook

`notebooks/area_coverage_cpu_800m_poi_2km.ipynb` contains all executable source
visibly, including the new OSM adapter. CPU only. The attached private dataset
`chrisbiran/area-coverage-osm-network-seed` contains only frozen OSM road/barrier
inputs and OSM POI data. It contains no Overture building footprints or private
BigQuery data/credentials. Dataset seed files have checksum verification.

The OSM building query requests tagged building ways and multipolygon relations
in the bounded pilot bbox. Successful raw Overpass responses are retained under
OUTPUT/osm_buildings_raw.json.gz before processing. HTTP failures/remarks/row
cap violations fail closed; no Overture fallback and no false empty inventory.

BUILDING_SOURCE_MODE=ACQUIRE_ONCE is the explicit initial acquisition operation.
For subsequent identical-source runs, attach the retained raw output and use
FROZEN with OSM_FROZEN_RAW_PATH pointing to that actual file. Same coordinates
with a new live source is a new input, not a deterministic replay. Existing
completed PILOT results are verified and reopened. Live basemap tiles may
change independently of frozen domain results.

## Mapping and preserved rules

- Stable source IDs: way/<id> and relation/<id>; tags/version/timestamp retained.
- Closed ways and stitched multipolygon rings supported, including inner holes.
  Tagged ways used as relation components are suppressed to avoid counting both
  component and relation. Invalid/ambiguous topology is not repaired silently;
  normalization exclusions remain in raw/building_cache/report.json.
- Explicit residential building tags map to canonical residential subtype;
  apartments/dormitory/hotel use existing special-class rules. Other explicit
  building uses remain their tagged class/subtype. building=yes retains null
  class/subtype: legacy N1 null fallback still applies and does NOT prove actual
  residential use. Tags and subtype mapping are experimental business semantics
  needing review, not a newly validated taxonomy.
- Missing or non-numeric height/floors stay null. No guessed floor counts.
- Radius800m, strict area>45m²/<550m² standard selection,125m candidate limit,
  motor permissions/direction/barrier rules,7km/h and round(minutes)≤10 unchanged.
  Changing source can change counts; fewer/more footprints is not proof of better
  accuracy. Existing routing connectivity limitations remain.
- Network uses the verified OSM drive_service+motor supplements snapshot. It is
  not every globally mapped road and does not make unknown alleys motor-usable.
  Buildings and network can have different timestamps; report warning preserves
  that fact, with no atomic-snapshot claim.
- Eight facility types and basemap are OSM. Competitor/Indomaret layers remain
  BigQuery as previously requested; neither is silently replaced by OSM shops.
  BQ failures retain unknown counts and do not discard an independent OSM domain
  result. No credentials are printed or written into source/result artifacts.

## Validation and limits

Five system-Python/GDAL topology/mapping tests pass;23existing notebook boundary
tests pass in the source venv (the five GDAL tests are skipped there and run
separately). A synthetic fixture also verifies provider OPENSTREETMAP through
raw normalization→canonical manifest→existing selection/capacity. Synthetic
fixtures are not results for the actual pilot. The Overture dispatcher retains
its original path for baseline compatibility; active OSM mode does not invoke it.

Workspace historical building acquisition returned HTTP502 and timeout; an
explicit current-snapshot retry returned HTTP406/429. These failures are retained
outside the dataset and not presented as empty buildings. Actual Kaggle execution
is inspected separately before claiming an end-to-end OSM result. No current
OSM building count or accuracy is invented to fill this source dependency.

Kaggle versi10 sudah dikirim dan terakhir teramati RUNNING. Jumlah footprint,
accepted/routing dan peta end-to-end OSM belum diverifikasi; null pada source
plan bukan0. Perubahan label audit/guard seed terbaru disimpan sebagai source
revision berikutnya tanpa menjadwalkan perhitungan penuh kedua.
