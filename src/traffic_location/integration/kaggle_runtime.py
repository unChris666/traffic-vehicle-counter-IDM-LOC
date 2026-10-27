"""Kaggle deployment adapter: explicit source staging, setup and independent jobs.

No cloud/model/apt work happens on import. Analytic algorithms remain in engine
facades. Kaggle Secret is read only in connect(); never serialized or printed.
"""
from pathlib import Path
from copy import deepcopy
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
from ..artifacts import read,write,sha,semantic_hash
from .contracts import need,GateError
from .workflow import run
from ..traffic.adapters.model_sources import gcs_model_ref

BUCKET='feeder-location-intelligent'
SECRET='LocatioIntelligent'
SCIENTIFIC={'numpy':'2.1.3','pandas':'2.3.3','shapely':'2.1.2','pyproj':'3.7.2',
            'networkx':'3.6.1','folium':'0.20.0','osmnx':'2.1.1'}


def area_config(latitude,longitude,core_python='/usr/bin/python3',target_id='T7SL'):
    """Same accepted Area policy, new explicit target and correct UTM zone."""
    need(type(latitude) in (int,float) and type(longitude) in (int,float) and
         math.isfinite(latitude) and math.isfinite(longitude) and -80<=latitude<=84
         and -180<=longitude<=180,'TARGET_INVALID','Koordinat tidak valid untuk profil UTM.')
    from ..location.area._kernel.location_intelligent_market_config import get_market_config,require_market_decisions
    from ..location.area._kernel.location_intelligent_market_scope import configure_scope
    policy=get_market_config()
    policy['target'].update(latitude=latitude,longitude=longitude,store_id=target_id,store_name=None)
    policy=configure_scope(require_market_decisions(policy));p=policy['allocation_requirements']
    zone=min(60,int((longitude+180)//6)+1)
    config={'latitude':latitude,'longitude':longitude,'building_radius_m':p['zones_m'][-1],
      'poi_radius_m':2000.,'building_query_padding_m':50.,'min_area_m2':p['residential_min_area_m2'],
      'max_area_m2':p['residential_max_area_m2_exclusive'],'selection_profile':'area-market-ge36-v1',
      'metric_crs':f'EPSG:{(32700 if latitude<0 else 32600)+zone}',
      'network_radius_m':policy['sources']['network_radius_m'],'osm_use_policy_version':'osm_poi_use_v2',
      'poi_profile':'market_attractors_v2','network_feature_mode':policy['sources']['network_feature_mode'],
      'building_entrance_profile':policy['access']['building_entrance_profile'],
      'road_rule_profile':policy['access']['road_rule_profile'],'building_provider':'OPENSTREETMAP',
      'max_building_rows':50000,'core_python':core_python,'poi_overpass_endpoints':[],
      'bq_billing_project':'locdeproject','bq_maximum_bytes_billed':268435456,
      'bq_tables':{'competitor':policy['sources']['competitor_table'],'indomaret':policy['sources']['indomaret_table']}}
    return {'CONFIG':config,'MARKET_CONFIG':policy}


def error_status(error):
    name=type(error).__name__
    if name in ('NotFound',):return 'NOT_FOUND'
    if name in ('Forbidden','Unauthorized','PermissionDenied','Unauthenticated'):return 'ACCESS_DENIED'
    return 'ERROR'


def continue_jobs(jobs,callback):
    """Persist each failure instead of aborting another engine/video."""
    rows=[]
    for item in jobs:
        try:row={'id':item['id'],'status':'SUCCEEDED','result':callback(item)}
        except Exception as exc:
            row={'id':item['id'],'status':'FAILED','code':(exc.code if isinstance(exc,GateError) else type(exc).__name__)}
        rows.append(row)
    return rows


class KaggleRuntime:
    def __init__(self,base,config_root,latitude,longitude,*,target_id='T7SL',period_id='analysis',client=None,credentials=None,performance=None,publication=None,upload_root=None):
        self.publication=publication;self.upload_root=Path(upload_root) if upload_root is not None else Path(base)/'uploads'
        self.performance=deepcopy(performance) if performance is not None else None
        if self.performance is not None:
            from ..traffic.experiments.performance import batch_size
            batch_size({'performance':self.performance})
        self.base=Path(base);self.config_root=Path(config_root);self.latitude=latitude;self.longitude=longitude
        self.target_id=target_id;self.period_id=period_id;self.client=client;self.credentials=credentials
        self.state={'gcs':{'status':'NOT_CHECKED'},'runtime':{},'models':{},'area':{'status':'NOT_CHECKED'}}
        self.base.mkdir(parents=True,exist_ok=True)

    def record(self):
        write(self.base/'system-status.json',self.state)
        return deepcopy(self.state)

    def connect(self):
        if self.client is None and os.environ.get('LI_AUTH_MODE')=='adc':
            import google.auth
            from google.cloud import storage
            self.credentials,project=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            self.client=storage.Client(project=project or 'locdeproject',credentials=self.credentials)
        if self.client is None:
            from kaggle_secrets import UserSecretsClient
            from google.oauth2 import service_account
            from google.cloud import storage
            try:info=json.loads(UserSecretsClient().get_secret(SECRET))
            except Exception:raise GateError('KAGGLE_SECRET_UNAVAILABLE','Aktifkan Kaggle Secret LocatioIntelligent.') from None
            self.credentials=service_account.Credentials.from_service_account_info(info,scopes=['https://www.googleapis.com/auth/cloud-platform'])
            self.client=storage.Client(project=info.get('project_id'),credentials=self.credentials)
        return self.client

    def object_status(self,ref):
        """Metadata observation is not confused with full checksum verification."""
        try:
            client=self.connect()
            blob=client.bucket(ref.get('bucket',BUCKET)).blob(ref['object'],generation=int(ref['generation']) if ref.get('generation') else None)
            blob.reload(timeout=60)
            if ref.get('generation'):need(int(blob.generation)==int(ref['generation']),'GENERATION_CHANGED','GCS generation berbeda.')
            if ref.get('bytes') is not None:need(blob.size==ref['bytes'],'SIZE_CHANGED','Ukuran object berbeda.')
            return {'status':'READY','validation':'METADATA_ONLY','generation':int(blob.generation),'bytes':blob.size}
        except Exception as exc:
            return {'status':error_status(exc),'code':(exc.code if isinstance(exc,GateError) else type(exc).__name__)}

    def probe(self):
        from ..location.area._kernel.location_intelligent_google_only import PBF
        items={'national_pbf':self.object_status(PBF)}
        profile=read(self.config_root/'fresh_request.json')
        for key in ('detector','reid'):
            r=profile['artifacts'][key];name=Path(r['path']).name
            pointer=gcs_model_ref(key,r)
            observed=self.object_status(pointer);observed['object']=pointer['object']
            observed['recovery']='Jika belum ada, bootstrap bobot resmi dengan SHA yang sama; cache GCS jika izin tulis tersedia.'
            items[key]=observed
        root_status='READY' if all(x['status']=='READY' for x in items.values()) else 'NOT_FOUND' if any(x['status']=='NOT_FOUND' for x in items.values()) else 'ACCESS_DENIED' if any(x['status']=='ACCESS_DENIED' for x in items.values()) else 'ERROR'
        self.state['gcs']={'status':root_status,'objects':items,'area_source':'BUILDABLE_FROM_PINNED_PBF' if items['national_pbf']['status']=='READY' else 'UNAVAILABLE',
                           'note':'Tidak membutuhkan registry integration/gate2/runtime-manifest.json.'}
        if self.publication is not None:
            try:self.state['publication']=self.cloud_publisher().check()
            except Exception as exc:self.state['publication']={'status':'NOT_READY','code':(exc.code if isinstance(exc,GateError) else type(exc).__name__),'bucket':self.publication.bucket,'dataset':self.publication.dataset}
        return self.record()

    def cloud_publisher(self):
        from google.cloud import bigquery
        from .cloud_publish import CloudPublisher
        self.connect()
        return CloudPublisher(self.publication,self.client,bigquery.Client(project=self.publication.dataset.split('.')[0],credentials=self.credentials))

    def publish_output(self,root,result,inventory,parameters):
        from .cloud_publish import prepare,progress
        context={'target_id':self.target_id,'period_id':self.period_id,'latitude':self.latitude,'longitude':self.longitude}
        try:
            progress(root,'Menyiapkan artefak hasil')
            prepare(root,result,inventory,context,parameters,self.publication)
            return self.cloud_publisher().publish(root)
        except Exception as exc:
            status={'status':'FAILED','code':(exc.code if isinstance(exc,GateError) else type(exc).__name__),'message':'Hasil lokal tetap tersimpan. Periksa tabel BQ dan izin GCS/BQ, lalu ulangi penyimpanan.'}
            write(Path(root)/'publication-status.json',status);return status

    def retry_publication(self,root):
        need(self.publication is not None,'PUBLICATION_NOT_CONFIGURED','Tujuan cloud belum disetel.')
        try:
            status=self.cloud_publisher().publish(root)
            saved=read(Path(root)/'summary.json');saved['publication']=status;write(Path(root)/'summary.json',saved)
            return status
        except Exception as exc:
            status={'status':'FAILED','code':(exc.code if isinstance(exc,GateError) else type(exc).__name__),'message':'Publikasi belum berhasil; hasil lokal tidak dihapus.'}
            write(Path(root)/'publication-status.json',status);return status

    def stage(self,ref,destination):
        client=self.connect();path=Path(destination);path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists() and sha(path)==ref['sha256']:return path
        temp=path.with_name(path.name+'.partial')
        try:
            blob=client.bucket(ref.get('bucket',BUCKET)).blob(ref['object'],generation=int(ref['generation']))
            blob.download_to_filename(str(temp),if_generation_match=int(ref['generation']))
            need(sha(temp)==ref['sha256'],'GCS_CHECKSUM_CHANGED','Checksum sumber GCS berbeda.')
            temp.replace(path)
        finally:temp.unlink(missing_ok=True)
        return path

    def cache_upload(self,path,name):
        """Write new content-addressed object only; never overwrite sources."""
        path=Path(path);blob=self.connect().bucket(BUCKET).blob(name)
        try:
            blob.upload_from_filename(str(path),if_generation_match=0)
            blob.reload(timeout=60)
            return {'status':'STORED','bucket':BUCKET,'object':name,'generation':int(blob.generation),'sha256':sha(path),'bytes':path.stat().st_size}
        except Exception as exc:
            # Read-only identities may still calculate with hash-verified local inputs.
            return {'status':error_status(exc),'code':type(exc).__name__,'local_retained':True}

    def prepare_models(self):
        """Same pinned assets: GCS first, explicit official bootstrap only if absent."""
        profile=read(self.config_root/'fresh_request.json');folder=self.base/'models';folder.mkdir(exist_ok=True)
        for key in ('detector','reid'):
            r=profile['artifacts'][key];name=Path(r['path']).name;destination=folder/name
            pointer=gcs_model_ref(key,r)
            if destination.exists():
                need(sha(destination)==r['sha256'],'MODEL_CHANGED','Model lokal tidak cocok dengan SHA terkunci.')
                self.state['models'][key]={'status':'READY','path':str(destination),'sha256':r['sha256'],'source':'VERIFIED_LOCAL_CACHE'};continue
            observed=self.object_status(pointer)
            if observed['status']=='READY':
                pointer['generation']=observed['generation'];self.stage(pointer,destination);source='GCS'
                cache={'status':'ALREADY_STORED'}
            elif observed['status']=='NOT_FOUND':
                import requests
                url='https://github.com/ultralytics/assets/releases/download/v8.4.0/'+name
                print('Bootstrap model resmi:',name,'(GCS belum berisi object)',flush=True)
                temporary=destination.with_name(name+'.partial')
                try:
                    with requests.get(url,stream=True,timeout=(30,180)) as response:
                        response.raise_for_status()
                        with temporary.open('wb') as f:
                            for chunk in response.iter_content(8*1024*1024):f.write(chunk)
                    need(sha(temporary)==r['sha256'],'MODEL_CHECKSUM_CHANGED','Bobot resmi tidak cocok dengan SHA terkunci.')
                    temporary.replace(destination)
                finally:temporary.unlink(missing_ok=True)
                source='OFFICIAL_PINNED_BOOTSTRAP';cache=self.cache_upload(destination,pointer['object'])
            else:
                raise GateError('MODEL_GCS_'+observed['status'],'Akses model GCS gagal; bukan dianggap object kosong.')
            self.state['models'][key]={'status':'READY','path':str(destination),'sha256':r['sha256'],'source':source,'gcs_cache':cache}
            self.record()
        return {k:v['path'] for k,v in self.state['models'].items()}

    def setup_runtime(self,engine):
        from ..traffic.experiments.performance import Progress
        timing=Progress(self.base/(engine+'-setup-progress.json'))
        timing.snapshot('setup_'+engine)
        with timing.stage('setup_'+engine):
            result=self._setup_runtime(engine)
        timing.snapshot('setup_finished')
        return result

    def _setup_runtime(self,engine):
        need(engine in ('area','traffic'),'ENGINE_INVALID','Unknown runtime')
        if self.state['runtime'].get(engine,{}).get('status')=='READY':return self.state['runtime'][engine]
        need(self.state['runtime'].get(engine,{}).get('status')!='FAILED','RUNTIME_SETUP_FAILED','Runtime '+engine+' gagal disiapkan; periksa log setup. Engine lain tetap berjalan.')
        self.state['runtime'][engine]={'status':'PREPARING'};self.record()
        if os.environ.get('LI_RUNTIME_MODE')=='bundled':
            from .container_runtime import verify_runtime
            self.state['runtime'][engine]=verify_runtime(engine,require_gpu=True)
            self.record();return self.state['runtime'][engine]
        need(os.environ.get('LI_RUNTIME_MODE','kaggle')=='kaggle','RUNTIME_MODE_INVALID','Mode runtime tidak dikenal.')
        import shutil
        need(shutil.which('nvidia-smi') is not None,'GPU_REQUIRED','Pilih GPU pada Notebook Settings Kaggle sebelum Mulai uji.')
        gpu=subprocess.run(['nvidia-smi','-L'],capture_output=True,text=True,timeout=30)
        need(gpu.returncode==0 and 'GPU' in gpu.stdout,'GPU_REQUIRED','GPU Kaggle belum aktif; aktifkan accelerator, kemudian ulangi uji.')
        if engine=='area':
            from ..location.area._kernel.location_intelligent_kaggle_esri import setup_dependencies
            subprocess.run([sys.executable,'-m','pip','install','--only-binary=:all:',*[k+'=='+v for k,v in SCIENTIFIC.items()]],check=True,timeout=900)
            core,osmium=setup_dependencies()
            for key in ('PROJ_LIB','PROJ_DATA','GDAL_DATA'):os.environ.pop(key,None)
            self.state['runtime'][engine]={'status':'READY','core_python':core,'osmium':osmium}
        else:
            subprocess.run([sys.executable,'-m','pip','install','ultralytics==8.4.175','lap==0.5.13','onnx==1.20.1','onnxruntime-gpu==1.24.4'],check=True,timeout=900)
            # New subprocess sees newly installed packages even in an old notebook kernel.
            command='import torch,onnxruntime as o; o.preload_dlls() if hasattr(o,"preload_dlls") else None; assert torch.cuda.is_available(),"CUDA required; select GPU in Kaggle";assert "CUDAExecutionProvider" in o.get_available_providers(),"CUDA ReID provider missing"'
            subprocess.run([sys.executable,'-c',command],check=True,timeout=120)
            self.state['runtime'][engine]={'status':'READY','python':sys.executable,'device':'cuda:0'}
        self.record();return self.state['runtime'][engine]

    def _prepare_area(self):
        """Build fresh Sorong source input from national PBF + target-bound BQ.

        This is ingestion. No routing/counting/market calculation happens here.
        The engine receives a data-only SourceBundle after freeze.
        """
        runtime=self.setup_runtime('area');self.connect()
        configuration=area_config(self.latitude,self.longitude,runtime['core_python'],self.target_id)
        from ..location.area._kernel.location_intelligent_google_only import PBF
        sourcekey=semantic_hash({'configuration':configuration,'pbf':PBF,'analysis_period':self.period_id})
        root=self.base/'area-source'/sourcekey;root.mkdir(parents=True,exist_ok=True)
        from ..location.area.sources.bundle import SourceBundle,create_source_bundle
        bundle_path=root/'source-bundle.zip'
        if not bundle_path.exists():
            from ..location.area._kernel.location_intelligent_pbf_sources import materialize
            from ..location.area._kernel import location_intelligent_map_pilot as bq_runtime
            prior=getattr(bq_runtime,'_NOTEBOOK_BQ_CREDENTIALS',None)
            try:
                bq_runtime._NOTEBOOK_BQ_CREDENTIALS=self.credentials
                layers=bq_runtime.load_bq_layers(configuration['CONFIG'],root/'bq_snapshot')
            finally:bq_runtime._NOTEBOOK_BQ_CREDENTIALS=prior
            write(root/'bq-readiness.json',layers)
            need(all(x['status']=='SUCCEEDED' for x in layers.values()),'BQ_SOURCE_UNAVAILABLE','Snapshot toko/kompetitor gagal; bukan nol kompetitor. Traffic tetap dapat berjalan.')
            pbf=self.stage(PBF,self.base/'national'/f"{PBF['sha256']}.osm.pbf")
            source=materialize(configuration['CONFIG'],root/'sources',pbf,runtime['osmium'],PBF)
            command='import platform,json,pyproj;from osgeo import gdal;print(json.dumps({"python":platform.python_version(),"gdal":gdal.VersionInfo("RELEASE_NAME"),"pyproj":pyproj.__version__}))'
            core=json.loads(subprocess.check_output([runtime['core_python'],'-c',command],text=True))
            profile={'scientific':{'python':platform.python_version(),'packages':{k:importlib.metadata.version(k) for k in SCIENTIFIC}},'core':core}
            create_source_bundle(configuration,source,root/'bq_snapshot',profile,bundle_path)
        bundle=SourceBundle(bundle_path)
        need(bundle.config['CONFIG']['latitude']==self.latitude and bundle.config['CONFIG']['longitude']==self.longitude,'AREA_TARGET_CHANGED','Bundle bukan target Sorong.')
        cache=self.cache_upload(bundle_path,f'sources/area-coverage/{sourcekey}/source-bundle.zip')
        self.state['area']={'status':'READY','source_bundle':str(bundle_path),'sha256':sha(bundle_path),'metric_crs':configuration['CONFIG']['metric_crs'],'gcs_cache':cache}
        self.record()
        return {'schema_version':'area_execution_request_v2','operation':'compute_gpu_sources',
                'input':{'path':str(bundle_path),'sha256':sha(bundle_path)},'core_python':runtime['core_python'],'render':True,'timeout_seconds':3600}

    def prepare_area(self):
        # Native ingestion runs in a fresh interpreter after pip/apt, avoiding
        # stale NumPy/GEOS/GDAL already imported by the Kaggle notebook kernel.
        runtime=self.setup_runtime('area')
        path=self.base/'area-preparation.json'
        write(path,{'base':str(self.base),'config_root':str(self.config_root),
                    'latitude':self.latitude,'longitude':self.longitude,'target_id':self.target_id,
                    'period_id':self.period_id,'runtime':runtime})
        self.state['area']={'status':'PREPARING'};self.record()
        log=self.base/'area-preparation.log'
        with log.open('w') as stream:
            subprocess.run([sys.executable,'-u','-m','traffic_location.integration.kaggle_runtime',
                            'prepare-area',str(path)],stdout=stream,stderr=subprocess.STDOUT,
                           check=True,timeout=7200)
        child=read(self.base/'area-preparation-result.json')
        self.state['area']=child['area'];self.record()
        return child['request']

    def run_area(self,root):
        root=Path(root);root.mkdir(parents=True,exist_ok=True)
        from ..location.area._kernel.location_intelligent_google_only import PBF
        status=self.object_status(PBF)
        need(status['status']=='READY','AREA_GCS_'+status['status'],'PBF nasional GCS tidak siap: '+status['status']+'. Traffic tetap dapat diuji.')
        from ..traffic.experiments.performance import Progress
        timing=Progress(root/'area-progress.json');timing.snapshot('area_source')
        with timing.stage('area_source'):
            request=self.prepare_area()
        timing.snapshot('area_compute')
        def compute(folder):
            write(folder/'request.json',request)
            q={'schema_version':'gate2_workflow_v1','jobs':[{'id':'area','engine':'area','action':'run','request_ref':{'path':str(folder/'request.json'),'sha256':sha(folder/'request.json')},'root':str(folder)}],'ppac':None}
            result=run(q,folder/'workflow',root=folder,operation='area')
            need(result['execution_status']=='SUCCEEDED','ENGINE_JOB_FAILED','Area gagal; hasil tidak disimpan sebagai cache sukses')
            return result
        identity={**request,'input':{'sha256':request['input']['sha256']},'target':{'latitude':self.latitude,'longitude':self.longitude,'id':self.target_id,'period':self.period_id}}
        with timing.stage('area_compute'):
            result=self._experiment_stage('area',identity,compute,root)
        timing.snapshot('area_finished')
        return result

    def video_inventory(self,input_root='/kaggle/input'):
        rows=[]
        for slot in read(self.config_root/'experiment.json')['videos']:
            matches=[p for p in Path(input_root).rglob(slot['filename']) if p.is_file()]
            video_id=Path(slot['filename']).stem
            _,day,session=video_id.split('-');slot={**slot,'day':day.lower(),'session':session.lower()}
            rows.append({'id':video_id,'status':'READY' if len(matches)==1 else 'NOT_FOUND' if not matches else 'AMBIGUOUS',
                         'path':str(matches[0]) if len(matches)==1 else None,'filename':slot['filename'],
                         'duration_seconds':slot['duration_seconds'],'slot':slot})
        return rows

    def _experiment_stage(self,stage,identity,build,root):
        """Completed-stage reuse is opt-in; no partial tracker checkpoint recovery."""
        from ..traffic.experiments.performance import Progress
        timing=Progress(Path(root)/'stage-progress.json')
        timing.snapshot(stage)
        with timing.stage(stage):
            if self.performance is not None and self.performance.get('reuse',True):
                from ..traffic.experiments.cache import StageCache,source_identity,runtime_identity
                identity={'inputs':identity,'code':source_identity(),'runtime':runtime_identity()}
                value,reused=StageCache(self.base/'completed-cache').get_or_create(stage,identity,build)
            else:
                value=build(Path(root));reused=False
        status={**timing.snapshot(stage+'_finished'),'reused':reused}
        print(status,flush=True)
        return value

    def run_video(self,item,root,*,gpu_id=None,models=None):
        root=Path(root);root.mkdir(parents=True,exist_ok=True)
        need(item['status']=='READY','VIDEO_UNAVAILABLE','Video tidak ditemukan/ambigu: '+item['id'])
        from ..traffic.experiments.performance import Progress
        setup=Progress(root/'setup-progress.json')
        with setup.stage('setup'):
            if models is None:
                self.connect();self.setup_runtime('traffic');models=self.prepare_models()
        setup.snapshot('setup_finished')
        slot=item['slot'];video=Path(item['path']);need(sha(video)==slot['sha256'],'VIDEO_CHANGED','Video SHA berbeda')
        geometry=self.config_root/'geometry'/(item['id']+'.json')
        if item.get('geometry_ref'):
            from ..artifacts import artifact
            geometry=artifact(item['geometry_ref'],self.base)
        config=read(self.config_root/'experiment.json');profile=read(self.config_root/'fresh_request.json')
        profile.update(device='cuda:0',input_root=str(self.base),frame_limit=slot['decoded_frames'])
        profile['execution_profile']='candidate_fp32'
        if gpu_id is not None:profile['gpu_allocation']=str(gpu_id)
        profile['artifacts']['video']={'path':str(video),'sha256':slot['sha256']}
        for key in ('detector','reid'):
            profile['artifacts'][key]['path']=models[key]
            need(sha(models[key])==profile['artifacts'][key]['sha256'],'MODEL_CHANGED','Model checksum berbeda')
        # Paths and PPAC inputs do not define inference; content and execution profile do.
        inference_identity={k:v for k,v in profile.items() if k not in ('artifacts','input_root')}
        inference_identity['assets']={k:v['sha256'] for k,v in profile['artifacts'].items()}
        def infer(folder):
            write(folder/'producer.json',profile)
            from ..traffic.orchestration import fresh_inference
            options={'gpu_id':gpu_id} if gpu_id is not None else {}
            fresh_inference(folder/'producer.json',folder/'measurement',python_executable=sys.executable,timeout_seconds=3600,**options)
            measurement=folder/'measurement/result.json.gz'
            return {'path':str(measurement),'sha256':sha(measurement)}
        measurement_ref=self._experiment_stage('inference',inference_identity,infer,root)
        measurement=Path(measurement_ref['path'])
        need(sha(measurement)==measurement_ref['sha256'],'MEASUREMENT_CHANGED','Measurement checksum berbeda')
        policy=self.config_root/'policy.json'
        source_manifest=self.config_root/'experiment.json';parent_run=config['experiment_id']
        if item.get('origin')=='USER_UPLOAD_REVIEWED':
            source_manifest=root/'source-manifest.json'
            manifest={'schema_version':'user_upload_source_v1','video_sha256':slot['sha256'],
                      'inspection':read(item['inspection_ref']['path']),'geometry_sha256':sha(geometry),
                      'day':slot['day'],'session':slot['session'],'direction':slot['direction']}
            write(source_manifest,manifest);parent_run='upload-'+semantic_hash(manifest)[:32]
        source={'video_sha256':slot['sha256'],'records_sha256':sha(measurement),'geometry_sha256':sha(geometry),
                'width':slot['width'],'height':slot['height'],'variant':'raw','parent_run_id':parent_run}
        request={'schema_version':'traffic_request_v1','profile':'machine','measurement_format':'fresh_v1','video_id':item['id'],
          'frame_count':slot['decoded_frames'],'source_identity':source,'source_manifest_sha256':sha(source_manifest),
          'artifacts':{k:{'path':str(p),'sha256':sha(p)} for k,p in [('measurements',measurement),('geometry',geometry),('policy',policy)]}}
        identity={**request,'artifacts':{k:v['sha256'] for k,v in request['artifacts'].items()}}
        def count(folder):
            from ..traffic.experiments.performance import profile_to
            write(folder/'request.json',request)
            q={'schema_version':'gate2_workflow_v1','jobs':[{'id':item['id'],'engine':'traffic','action':'run','request_ref':{'path':str(folder/'request.json'),'sha256':sha(folder/'request.json')},'root':str(folder)}],'ppac':None}
            with profile_to(folder/'counting-progress.json'):
                result=run(q,folder/'workflow',root=folder,operation='traffic')
            need(result['execution_status']=='SUCCEEDED','ENGINE_JOB_FAILED','Counting gagal; hasil tidak disimpan sebagai cache sukses')
            return result
        return self._experiment_stage('counting',identity,count,root)

    def _scheduled_tasks(self,tasks,root):
        """Prepare shared assets once; isolate inference and reserve a GPU per video."""
        for item in tasks:
            if item['kind']=='area':
                try:yield item,self.run_area(root/'area'),None
                except Exception as exc:yield item,None,exc
        videos=[v for v in tasks if v['kind']=='traffic']
        if not videos:return
        try:
            self.connect();self.setup_runtime('traffic');models=self.prepare_models()
            from ..traffic.gpu_scheduler import run_video_jobs
            def worker(item,gpu):
                print('START',item['id'],'GPU',gpu,flush=True)
                try:return self.run_video(item,root/item['id'],gpu_id=gpu,models=models)
                finally:print('WORKER FINISHED',item['id'],'GPU',gpu,flush=True)
            outcomes=run_video_jobs(videos,worker)
        except Exception as exc:
            for item in videos:yield item,None,exc
            return
        for item,outcome in zip(videos,outcomes):
            write(root/item['id']/'gpu-assignment.json',{'gpu_id':outcome['gpu_id'],'execution_status':outcome['execution_status']})
            if outcome['execution_status']=='SUCCEEDED':yield item,outcome['result'],None
            else:
                exc=RuntimeError(outcome['message']);exc.code=outcome['error_type']
                yield item,None,exc

    def execute(self,mode,parameters,*,input_root='/kaggle/input',target_confirmed=False,video_ids=None,uploaded_videos=None):
        """One invocation per engine/video; failures and successes always visible."""
        from datetime import datetime
        need(mode in ('area','traffic','workflow'),'MODE_INVALID','Pilih Area, Traffic, atau gabungan.')
        if mode=='workflow':need(target_confirmed,'TARGET_BINDING_REQUIRED','Konfirmasi bahwa video dan Area dipakai untuk target yang sama.')
        root=self.base/'runs'/datetime.now().strftime('%Y%m%dT%H%M%S_%f');root.mkdir(parents=True)
        from ..runtime_resources import record as resource_record
        resource_record(root,'start')
        if mode=='area':inventory=[]
        elif uploaded_videos is not None:
            from .uploads import inventory as upload_inventory
            inventory=upload_inventory(uploaded_videos,self.upload_root)
        else:inventory=self.video_inventory(input_root)
        if video_ids is not None and mode!='area':
            need(isinstance(video_ids,list) and bool(video_ids) and len(video_ids)==len(set(video_ids)),
                 'VIDEO_SELECTION_INVALID','Pilih minimal satu video unik.')
            need(set(video_ids)<=set(v['id'] for v in inventory),'VIDEO_SELECTION_INVALID','Video di luar dataset terikat.')
            inventory=[v for v in inventory if v['id'] in video_ids]
        tasks=([{'id':'area','kind':'area'}] if mode in ('area','workflow') else [])+([{**v,'kind':'traffic'} for v in inventory] if mode in ('traffic','workflow') else [])
        receipts=[];jobs=[];bindings=[]
        for item,result,error in self._scheduled_tasks(tasks,root):
            print('START',item['id'],flush=True)
            try:
                if error is not None:raise error
                need(result['execution_status']=='SUCCEEDED','ENGINE_JOB_FAILED','Hasil workflow engine gagal; periksa receipt engine.')
                job=result['jobs'][0];jobs.append({'id':job['id'],'engine':job['engine'],'action':'reuse','result_ref':job['result_ref']})
                receipts.append({'id':item['id'],'engine':item['kind'],'execution_status':'SUCCEEDED','quality':job['quality'],'summary':job['summary'],'result_ref':job['result_ref']})
                if item['kind']=='traffic':
                    if 'day' in item['slot'] and 'session' in item['slot']:
                        day,session=item['slot']['day'],item['slot']['session']
                    else:_,day,session=item['id'].split('-')
                    bindings.append({'job_id':item['id'],'result_version':job['result_version'],'video_sha256':item['slot']['sha256'],
                      'target_id':self.target_id,'period_id':self.period_id,'day':day.lower(),'session':session.lower(),
                      'observed_seconds':item['duration_seconds'],'observed_categories':['motorcycle','car','bus','truck','pedestrian'],
                      'evidence':('User-uploaded source; SHA-bound inspection; per-video geometry/day/session review; user target/period declaration; no rescaling' if item.get('origin')=='USER_UPLOAD_REVIEWED' else 'User target declaration; pinned T7SL source inspection durations, no count rescaling')})
            except Exception as exc:
                if self.state['runtime'].get(item['kind'],{}).get('status')=='PREPARING':
                    self.state['runtime'][item['kind']]={'status':'FAILED','code':type(exc).__name__}
                self.record()
                receipts.append({'id':item['id'],'engine':item['kind'],'execution_status':'FAILED','code':(exc.code if isinstance(exc,GateError) else type(exc).__name__),
                                 'message':str(exc) if isinstance(exc,GateError) else 'Tahap gagal ('+type(exc).__name__+'); periksa log setup/worker. Engine/video berikut tetap diproses.'})
            write(root/'progress.json',receipts);print('FINISH',item['id'],receipts[-1]['execution_status'],flush=True)
        ppac={'execution_status':'NOT_RUN','std_total':None}
        if mode=='workflow':
            if any(r['execution_status']!='SUCCEEDED' for r in receipts):
                ppac={'execution_status':'BLOCKED','std_total':None,'diagnostics':[{'code':'REQUIRED_ENGINE_UNAVAILABLE','message':'Hasil wajib engine/video gagal. Hasil sukses tetap tersedia.'}]}
            else:
                area=next(j for j in jobs if j['engine']=='area')
                binding={'schema_version':'gate2_binding_v1','context':{'target_id':self.target_id,'period_id':self.period_id,
                  'latitude':self.latitude,'longitude':self.longitude,'evidence':'User target declaration, date is analysis date'},
                  'area':{'job_id':'area','result_version':read(Path(area['result_ref']['path'])/'result.json')['result_version']},
                  'traffic':bindings,'category_mapping':{'motorcycle':'motor','car':'mobil','bus':'angkutan_umum','truck':None,'pedestrian':'pejalan_kaki'},'supplemental':[]}
                write(root/'binding.json',binding);write(root/'parameters.json',parameters)
                q={'schema_version':'gate2_workflow_v1','jobs':jobs,'ppac':{k+'_ref':{'path':str(root/(k+'.json')),'sha256':sha(root/(k+'.json'))} for k in ('binding','parameters')}}
                write(root/'joined-request.json',q)
                joined=self._experiment_stage('ppac',{'binding':binding,'parameters':parameters,'jobs':jobs},
                    lambda folder:run(q,folder/'joined',root=root,operation='ppac'),root)
                ppac=joined['ppac']
        result={'schema_version':'kaggle_real_route_v1','engines':receipts,'ppac':ppac,'output':str(root),'system':self.record()}
        write(root/'summary.json',result)
        if self.publication is not None:
            result['publication']=self.publish_output(root,result,inventory,parameters)
            write(root/'summary.json',result)
        resource_record(root,'finished')
        return result


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['prepare-area']);parser.add_argument('request')
    args=parser.parse_args();q=read(args.request)
    runtime=KaggleRuntime(q['base'],q['config_root'],q['latitude'],q['longitude'],target_id=q['target_id'],period_id=q['period_id'])
    runtime.state['runtime']['area']=q['runtime']
    request=runtime._prepare_area()
    write(Path(q['base'])/'area-preparation-result.json',{'request':request,'area':runtime.state['area']})

if __name__=='__main__':main()
