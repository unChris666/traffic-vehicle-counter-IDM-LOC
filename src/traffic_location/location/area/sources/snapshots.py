"""Read retained V5 ZIPs without invoking a notebook, CUDA or any provider."""
import csv
import io
import json
import stat
import math
import zipfile
from pathlib import PurePosixPath
from collections import Counter
from ....artifacts import semantic_hash, sha

REQUIRED = {'job_config.json','runtime_environment.json','gpu_execution.json','gpu_equivalence.json',
            'pilot/manifest.json','pilot/report.json','pilot/building_results/capacity.json',
            'pilot/building_results/decisions.json.gz','pilot/normalized/buildings.geojson',
            'sources/source_manifest.json'}

class MarketSnapshot:
    def __init__(self,path):
        self.path=path
        with zipfile.ZipFile(path) as archive:
            entries=archive.infolist();names=[i.filename for i in entries]
            if len(names)!=len(set(names)):
                raise ValueError('AREA_ZIP_DUPLICATE_PATH')
            for info in entries:
                p=PurePosixPath(info.filename)
                if (p.is_absolute() or '..' in p.parts or '\\' in info.filename or
                        stat.S_ISLNK(info.external_attr>>16) or info.flag_bits & 1):
                    raise ValueError('AREA_ZIP_UNSAFE_PATH')
            files={i.filename for i in entries if not i.is_dir()}
            if not REQUIRED<=files:
                raise ValueError('AREA_BASELINE_INPUTS_INCOMPLETE')
            total=sum(i.file_size for i in entries)
            if total>50*1024**3:
                raise ValueError('AREA_ZIP_EXPANSION_LIMIT')
            # Read only requested documents; no extraction or all-archive RAM copy.
            def document(name):return json.loads(archive.read(name))
            config=document('job_config.json');market_config=config['MARKET_CONFIG']
            p=market_config['allocation_requirements']
            if (p.get('attractor_gate')!='RADIAL_ATTRACTOR_400M_NO_POI_ROUTING' or
                    p.get('attractor_radius_m')!=400 or
                    market_config['sources'].get('indomaret_calculation_radius_m')!=800 or
                    market_config['sources'].get('competitor_calculation_radius_m')!=800):
                raise ValueError('AREA_BASELINE_POLICY_NOT_V5')
            results=[n for n in files if n.startswith('market/') and n.endswith('/result.json')]
            # An export may retain previous versions: select exactly the configured policy.
            matches=[]
            for name in sorted(results):
                value=document(name)
                if value.get('identity',{}).get('market_config')==market_config:matches.append((name,value))
            if len(matches)!=1:raise ValueError('AREA_BASELINE_MARKET_RESULT_AMBIGUOUS')
            result_path,native=matches[0]
            if native.get('schema_version')!='area_market_result_v1' or native.get('status') not in {'SUCCEEDED','PARTIAL'}:
                raise ValueError('AREA_BASELINE_RESULT_NOT_FINALIZED')
            self._verify_manifest(archive,'pilot/manifest.json','pilot/')
            self._verify_manifest(archive,'sources/source_manifest.json','sources/')
            market_parent=result_path.rsplit('/',1)[0]+'/'
            self._verify_manifest(archive,market_parent+'manifest.json',market_parent)
            self._verify_manifest(archive,'sources/network_roads_only/network_manifest.json','sources/network_roads_only/')
            # Source bytes plus code included by the original exported packet.
            source_files=sorted(n for n in files if n.startswith('source/') and n.endswith('.py'))
            if not source_files:raise ValueError('AREA_BASELINE_CODE_MISSING')
            report=document('pilot/report.json');rows=native['rows'];summary=native['summary']
            if (len(rows)!=report['source_records'] or report['all_source_rows_accounted']!=report['source_records'] or
                    summary['rows']!=len(rows) or summary['assigned']+summary['unassigned']!=len(rows)):
                raise ValueError('AREA_BASELINE_ROWS_DO_NOT_RECONCILE')
            ids=[r['building_id'] for r in rows]
            if len(ids)!=len(set(ids)):raise ValueError('AREA_BASELINE_DUPLICATE_BUILDING')
            if native['identity']['config']!=config['CONFIG']:
                raise ValueError('AREA_BASELINE_CONFIG_MISMATCH')
            from hashlib import sha256
            if native['identity']['pilot']!=sha256(archive.read('pilot/manifest.json')).hexdigest():
                raise ValueError('AREA_BASELINE_PILOT_BINDING_MISMATCH')
            if semantic_hash(native['identity'])!=native['fingerprint']:
                raise ValueError('AREA_BASELINE_IDENTITY_MISMATCH')
            counts=dict(Counter(r['market_status'] for r in rows))
            if summary['market_status_counts']!=counts:
                raise ValueError('AREA_BASELINE_STATUS_COUNTS_MISMATCH')
            assigned=[r for r in rows if r['winner_store_key'] is not None]
            owners=dict(Counter(r['winner_store_key'] for r in assigned))
            reasons=dict(Counter(r['reason'] for r in rows))
            if (summary['assigned']!=len(assigned) or summary['whole_buildings_by_store']!=owners or
                    summary['reason_counts']!=reasons or
                    summary['candidate_whole_buildings']!=owners.get('candidate',0) or
                    sum(r['count_candidate'] for r in rows)!=owners.get('candidate',0)):
                raise ValueError('AREA_BASELINE_AGGREGATE_MISMATCH')
            for row in assigned:
                scores=[s['huff_score'] for s in row['scores']]
                if not scores or not all(math.isfinite(s) and 0<=s<=1 for s in scores) or not math.isclose(math.fsum(scores),1.0,abs_tol=1e-12):
                    raise ValueError('AREA_BASELINE_HUFF_SCORES_INVALID')
            csv_rows=list(csv.DictReader(io.StringIO(archive.read(market_parent+'market_buildings.csv').decode())))
            if [r['building_id'] for r in csv_rows]!=ids:
                raise ValueError('AREA_BASELINE_CSV_ROWS_MISMATCH')
            self.native=native;self.config=config;self.capacity=document('pilot/building_results/capacity.json')
            self.gpu_execution=document('gpu_execution.json');self.equivalence=document('gpu_equivalence.json')
            self.environment=document('runtime_environment.json')
            self.source_zip_sha256=sha(path)
            self.file_count=len(files)
            self.code_hashes={name:sha256(archive.read(name)).hexdigest() for name in source_files}

    @staticmethod
    def _verify_manifest(archive,name,prefix):
        from hashlib import sha256
        value=json.loads(archive.read(name));files=value['files']
        records=({'path':k,'sha256':v} for k,v in files.items()) if isinstance(files,dict) else files
        seen=set()
        for record in records:
            path=PurePosixPath(record['path'])
            if path.is_absolute() or '..' in path.parts or record['path'] in seen:
                raise ValueError('AREA_BASELINE_MANIFEST_PATH_INVALID')
            seen.add(record['path']);raw=archive.read(prefix+record['path'])
            if sha256(raw).hexdigest()!=record['sha256'] or ('bytes' in record and len(raw)!=record['bytes']):
                raise ValueError('AREA_BASELINE_MANIFEST_HASH_MISMATCH')
