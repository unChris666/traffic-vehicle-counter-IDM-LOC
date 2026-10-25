"""Data-only frozen input: config + OSM source packet + BQ snapshots + runtime.

A new calculation does not require a previous calculation or market result.
"""
from pathlib import Path,PurePosixPath
import json,zipfile,hashlib,stat
from ....artifacts import sha,canonical
from .snapshots import MarketSnapshot

class SourceBundle:
    def __init__(self,path):
        with zipfile.ZipFile(path) as z:
            names=z.namelist()
            if sum(i.file_size for i in z.infolist())>50*1024**3:raise ValueError('AREA_SOURCE_EXPANSION_LIMIT')
            required={'source_bundle_manifest.json','job_config.json','runtime_profile.json',
                'sources/source_manifest.json','sources/pbf_source.json','sources/osm_buildings_raw.json.gz',
                'sources/optional_poi_result.json','sources/network_roads_only/config/pilot.json',
                'sources/network_roads_only/raw/osm_roads.json.gz','sources/network_roads_only/raw/osm_features_roads_only.json.gz',
                'sources/network_roads_only/network_manifest.json','bq_snapshot/competitor.json','bq_snapshot/indomaret.json'}
            if not required<=set(names):raise ValueError('AREA_SOURCE_REQUIRED_ROLES_MISSING')
            if len(names)!=len(set(names)):raise ValueError('AREA_SOURCE_DUPLICATE_PATH')
            for i in z.infolist():
                p=PurePosixPath(i.filename)
                if p.is_absolute() or '..' in p.parts or '\\' in i.filename or stat.S_ISLNK(i.external_attr>>16) or i.flag_bits & 1:
                    raise ValueError('AREA_SOURCE_UNSAFE_PATH')
            if any(n.startswith(('pilot/','market/')) for n in names):raise ValueError('AREA_SOURCE_INPUT_CONTAINS_RESULTS')
            meta=json.loads(z.read('source_bundle_manifest.json'))
            if meta['schema_version']!='area_source_bundle_v1':raise ValueError('AREA_SOURCE_VERSION_UNKNOWN')
            if set(meta['files'])!=set(names)-{'source_bundle_manifest.json'}:raise ValueError('AREA_SOURCE_INVENTORY_MISMATCH')
            for n,digest in meta['files'].items():
                if hashlib.sha256(z.read(n)).hexdigest()!=digest:raise ValueError('AREA_SOURCE_HASH_MISMATCH')
            self.config=json.loads(z.read('job_config.json'))
            self.runtime_profile=json.loads(z.read('runtime_profile.json'))
            MarketSnapshot._verify_manifest(z,'sources/source_manifest.json','sources/')
            MarketSnapshot._verify_manifest(z,'sources/network_roads_only/network_manifest.json','sources/network_roads_only/')
            source=json.loads(z.read('sources/source_manifest.json'))['config']
            ignored={'building_entrance_profile','road_rule_profile'}
            if {k:v for k,v in source.items() if k not in ignored}!={k:v for k,v in self.config['CONFIG'].items() if k not in ignored}:
                raise ValueError('AREA_SOURCE_REQUEST_BINDING_MISMATCH')
            for kind in ['competitor','indomaret']:
                layer=json.loads(z.read('bq_snapshot/'+kind+'.json'))
                binding=layer.get('request_binding',{})
                if any(binding.get(k)!=self.config['CONFIG'][k] for k in ['latitude','longitude']):
                    raise ValueError('AREA_SOURCE_BQ_LOCATION_MISMATCH')
            policy=self.config['MARKET_CONFIG']
            if any(policy['target'][k]!=self.config['CONFIG'][k] for k in ['latitude','longitude']):raise ValueError('AREA_SOURCE_TARGET_MISMATCH')
            if not {'scientific','core'}<=set(self.runtime_profile):raise ValueError('AREA_SOURCE_RUNTIME_PROFILE_MISSING')
            if (policy['allocation_requirements'].get('attractor_gate')!='RADIAL_ATTRACTOR_400M_NO_POI_ROUTING' or
                policy['allocation_requirements'].get('attractor_radius_m')!=400 or
                policy['sources'].get('competitor_calculation_radius_m')!=800 or
                policy['sources'].get('indomaret_calculation_radius_m')!=800):raise ValueError('AREA_SOURCE_POLICY_NOT_V5')
        self.source_zip_sha256=sha(path);self.native=None;self.capacity=None


def create_source_bundle(config,sources,bq_snapshot,runtime_profile,output):
    """Package prepared sources without running selection, routing or allocation."""
    from .._kernel.location_intelligent_market_runtime import verify_market_source_packet
    sources=Path(sources);bq_snapshot=Path(bq_snapshot);output=Path(output)
    source_manifest=verify_market_source_packet(sources,config['CONFIG'])
    if output.exists():raise ValueError('AREA_SOURCE_BUNDLE_IMMUTABLE')
    output.parent.mkdir(parents=True,exist_ok=True)
    import tempfile,os,shutil
    fd,temp=tempfile.mkstemp(prefix='.area-sources-',dir=output.parent);os.close(fd)
    try:
        files={}
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            def info(name):
                value=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));value.compress_type=zipfile.ZIP_DEFLATED
                value.create_system=3;value.external_attr=0o600<<16
                return value
            for base,prefix in [(sources,'sources'),(bq_snapshot,'bq_snapshot')]:
                members=[base/name for name in source_manifest['files']]+[base/'source_manifest.json'] if prefix=='sources' else [base/'competitor.json',base/'indomaret.json']
                for p in sorted(members):
                    if p.is_symlink():raise ValueError('AREA_SOURCE_SYMLINK')
                    if p.is_file():
                        name=prefix+'/'+str(p.relative_to(base));files[name]=sha(p)
                        with p.open('rb') as source,z.open(info(name),'w',force_zip64=True) as target:shutil.copyfileobj(source,target,1024*1024)
            for name,value in [('job_config.json',config),('runtime_profile.json',runtime_profile)]:
                data=canonical(value);z.writestr(info(name),data);files[name]=hashlib.sha256(data).hexdigest()
            z.writestr(info('source_bundle_manifest.json'),canonical({'schema_version':'area_source_bundle_v1','files':files}))
        SourceBundle(temp)
        if output.exists():raise ValueError('AREA_SOURCE_BUNDLE_CONFLICT')
        os.replace(temp,output)
    finally:Path(temp).unlink(missing_ok=True)
    return output
