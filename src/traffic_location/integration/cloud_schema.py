"""Output schema only. Existing Area reference tables remain independent."""
import re
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class CloudDestination:
    bucket:str='aretfak-location-intelligence'
    dataset:str='locdeproject.location_intelligence'

    def __post_init__(self):
        if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]',self.bucket):raise ValueError('Invalid artifact bucket name')
        if not re.fullmatch(r'[a-z][a-z0-9-]{4,62}\.[A-Za-z_][A-Za-z0-9_]{0,1023}',self.dataset):raise ValueError('Invalid BigQuery dataset identifier')

    @classmethod
    def configured(cls):
        return cls(os.environ.get('LI_ARTIFACT_BUCKET',cls.bucket),os.environ.get('LI_OUTPUT_DATASET',cls.dataset))

COMMON={'job_id':'STRING','target_id':'STRING','created_at':'TIMESTAMP'}
SCHEMAS={
 'job_runs':{**COMMON,'period_id':'STRING','latitude':'FLOAT64','longitude':'FLOAT64',
             'execution_status':'STRING','ppac_status':'STRING','publication_status':'STRING',
             'manifest_uri':'STRING','manifest_sha256':'STRING','package_version':'STRING'},
 'traffic_videos':{**COMMON,'video_id':'STRING','filename':'STRING','day_group':'STRING','session':'STRING',
                   'source_sha256':'STRING','result_version':'STRING','execution_status':'STRING','result_quality':'STRING',
                   'source_frames':'INT64','processed_frames':'INT64','observed_seconds':'FLOAT64',
                   'accepted_measured':'INT64','accepted_estimated':'INT64','pending':'INT64','invalid':'INT64',
                   'direction_semantics':'STRING','manifest_uri':'STRING'},
 'traffic_counts':{**COMMON,'video_id':'STRING','category':'STRING','direction':'STRING',
                  'evidence_level':'STRING','accepted_count':'INT64'},
 'area_results':{**COMMON,'result_version':'STRING','execution_status':'STRING','result_quality':'STRING',
                 'allocated_buildings':'INT64','unverified_buildings':'INT64','outer_zone_open':'BOOL',
                 'fasum_le400':'INT64','fasum_gt400_le800':'INT64','manifest_uri':'STRING',
                 'map_html_uri':'STRING','map_html_sha256':'STRING'},
 'ppac_results':{**COMMON,'execution_status':'STRING','result_quality':'STRING','std_total':'FLOAT64',
                 'std_residential':'FLOAT64','std_traffic':'FLOAT64','std_fasum':'FLOAT64',
                 'policy_version':'STRING','parameters_json':'JSON','diagnostics_json':'JSON'}
}


def setup_sql(destination=None):
    d=(destination or CloudDestination()).dataset
    statements=[]
    for table,fields in SCHEMAS.items():
        columns=',\n  '.join(name+' '+kind for name,kind in fields.items())
        statements.append(f'CREATE TABLE IF NOT EXISTS `{d}.{table}` (\n  {columns}\n)\nPARTITION BY DATE(created_at)\nCLUSTER BY target_id, job_id;')
    for name in ('map_html_uri','map_html_sha256'):
        statements.append(f'ALTER TABLE `{d}.area_results` ADD COLUMN IF NOT EXISTS {name} STRING;')
    statements.append(f'''CREATE VIEW IF NOT EXISTS `{d}.traffic_ppac_samples` AS
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
FROM `{d}.traffic_videos` v
JOIN `{d}.job_runs` j USING(job_id, target_id)
LEFT JOIN `{d}.traffic_counts` c USING(job_id, target_id, video_id)
WHERE j.publication_status='READY' AND v.execution_status='SUCCEEDED'
  AND v.source_frames=v.processed_frames AND v.source_frames>0
GROUP BY v.job_id,v.target_id,v.video_id,v.day_group,v.session,v.source_sha256,
         v.result_version,v.result_quality,v.observed_seconds,v.pending,v.invalid,v.direction_semantics;''')
    statements.append(f'''CREATE VIEW IF NOT EXISTS `{d}.ppac_feeder` AS
SELECT t.*, j.period_id, j.latitude, j.longitude, j.ppac_status, (j.ppac_status='SUCCEEDED') AS gate2_admission_verified_for_saved_parameters,
       a.allocated_buildings, a.outer_zone_open, a.fasum_le400, a.fasum_gt400_le800,
       a.result_quality AS area_quality, a.unverified_buildings,
       'ACCEPTED_MEASURED_AND_ESTIMATED_BOTH_DIRECTIONS' AS traffic_policy,
       'USER_DECLARED_TARGET_PERIOD_AND_GEOMETRY_NOT_INDEPENDENT_GPS_VALIDATION' AS binding_trust
FROM `{d}.traffic_ppac_samples` t
JOIN `{d}.job_runs` j USING(job_id,target_id)
LEFT JOIN `{d}.area_results` a USING(job_id,target_id);''')
    return '\n\n'.join(statements)+'\n'


def publication_sql(destination):
    """One transaction replaces this immutable job only; query parameters carry data."""
    d=destination.dataset
    statements=['BEGIN TRANSACTION;',f"ASSERT NOT EXISTS(SELECT 1 FROM `{d}.job_runs` WHERE job_id=@job_id AND manifest_sha256!=@manifest_sha256) AS 'JOB_REVISION_CONFLICT';"]
    for table,fields in SCHEMAS.items():
        statements.append(f'DELETE FROM `{d}.{table}` WHERE job_id=@job_id;')
        expressions=[]
        for name,kind in fields.items():
            expressions.append(f"JSON_QUERY(r,'$.{name}')" if kind=='JSON' else f"CAST(JSON_VALUE(r,'$.{name}') AS {kind})")
        statements.append(f"INSERT INTO `{d}.{table}` ({', '.join(fields)})\nSELECT {', '.join(expressions)}\nFROM UNNEST(JSON_QUERY_ARRAY(PARSE_JSON(@rows_{table}))) r;")
    statements.append('COMMIT TRANSACTION;');return '\n'.join(statements)
