CREATE TABLE IF NOT EXISTS `locdeproject.location_intelligence.job_runs` (
  job_id STRING,
  target_id STRING,
  created_at TIMESTAMP,
  period_id STRING,
  latitude FLOAT64,
  longitude FLOAT64,
  execution_status STRING,
  ppac_status STRING,
  publication_status STRING,
  manifest_uri STRING,
  manifest_sha256 STRING,
  package_version STRING
)
PARTITION BY DATE(created_at)
CLUSTER BY target_id, job_id;

CREATE TABLE IF NOT EXISTS `locdeproject.location_intelligence.traffic_videos` (
  job_id STRING,
  target_id STRING,
  created_at TIMESTAMP,
  video_id STRING,
  filename STRING,
  day_group STRING,
  session STRING,
  source_sha256 STRING,
  result_version STRING,
  execution_status STRING,
  result_quality STRING,
  source_frames INT64,
  processed_frames INT64,
  observed_seconds FLOAT64,
  accepted_measured INT64,
  accepted_estimated INT64,
  pending INT64,
  invalid INT64,
  direction_semantics STRING,
  manifest_uri STRING
)
PARTITION BY DATE(created_at)
CLUSTER BY target_id, job_id;

CREATE TABLE IF NOT EXISTS `locdeproject.location_intelligence.traffic_counts` (
  job_id STRING,
  target_id STRING,
  created_at TIMESTAMP,
  video_id STRING,
  category STRING,
  direction STRING,
  evidence_level STRING,
  accepted_count INT64
)
PARTITION BY DATE(created_at)
CLUSTER BY target_id, job_id;

CREATE TABLE IF NOT EXISTS `locdeproject.location_intelligence.area_results` (
  job_id STRING,
  target_id STRING,
  created_at TIMESTAMP,
  result_version STRING,
  execution_status STRING,
  result_quality STRING,
  allocated_buildings INT64,
  unverified_buildings INT64,
  outer_zone_open BOOL,
  fasum_le400 INT64,
  fasum_gt400_le800 INT64,
  manifest_uri STRING
)
PARTITION BY DATE(created_at)
CLUSTER BY target_id, job_id;

CREATE TABLE IF NOT EXISTS `locdeproject.location_intelligence.ppac_results` (
  job_id STRING,
  target_id STRING,
  created_at TIMESTAMP,
  execution_status STRING,
  result_quality STRING,
  std_total FLOAT64,
  std_residential FLOAT64,
  std_traffic FLOAT64,
  std_fasum FLOAT64,
  policy_version STRING,
  parameters_json JSON,
  diagnostics_json JSON
)
PARTITION BY DATE(created_at)
CLUSTER BY target_id, job_id;

CREATE VIEW IF NOT EXISTS `locdeproject.location_intelligence.traffic_ppac_samples` AS
SELECT v.job_id, v.target_id, v.video_id, v.day_group, v.session,
       v.source_sha256, v.result_version, v.result_quality, v.observed_seconds,
       v.pending, v.invalid, v.direction_semantics,
       (v.observed_seconds BETWEEN 300 AND 306) AS sample_duration_compatible,
       SUM(IF(c.category='motorcycle', c.accepted_count, NULL)) AS motor_count,
       SUM(IF(c.category='car', c.accepted_count, NULL)) AS mobil_count,
       SUM(IF(c.category='bus', c.accepted_count, NULL)) AS angkutan_umum_count,
       SUM(IF(c.category='pedestrian', c.accepted_count, NULL)) AS pejalan_kaki_count,
       SUM(IF(c.evidence_level='measured', c.accepted_count, NULL)) AS accepted_measured,
       SUM(IF(c.evidence_level='estimated', c.accepted_count, NULL)) AS accepted_estimated
FROM `locdeproject.location_intelligence.traffic_videos` v
JOIN `locdeproject.location_intelligence.job_runs` j USING(job_id, target_id)
LEFT JOIN `locdeproject.location_intelligence.traffic_counts` c USING(job_id, target_id, video_id)
WHERE j.publication_status='READY' AND v.execution_status='SUCCEEDED'
  AND v.source_frames=v.processed_frames AND v.source_frames>0
GROUP BY v.job_id,v.target_id,v.video_id,v.day_group,v.session,v.source_sha256,
         v.result_version,v.result_quality,v.observed_seconds,v.pending,v.invalid,v.direction_semantics;

CREATE VIEW IF NOT EXISTS `locdeproject.location_intelligence.ppac_feeder` AS
SELECT t.*, j.period_id, j.latitude, j.longitude, j.ppac_status, (j.ppac_status='SUCCEEDED') AS gate2_admission_verified_for_saved_parameters,
       a.allocated_buildings, a.outer_zone_open, a.fasum_le400, a.fasum_gt400_le800,
       a.result_quality AS area_quality, a.unverified_buildings,
       'ACCEPTED_MEASURED_AND_ESTIMATED_BOTH_DIRECTIONS' AS traffic_policy,
       'USER_DECLARED_TARGET_PERIOD_AND_GEOMETRY_NOT_INDEPENDENT_GPS_VALIDATION' AS binding_trust
FROM `locdeproject.location_intelligence.traffic_ppac_samples` t
JOIN `locdeproject.location_intelligence.job_runs` j USING(job_id,target_id)
LEFT JOIN `locdeproject.location_intelligence.area_results` a USING(job_id,target_id);
