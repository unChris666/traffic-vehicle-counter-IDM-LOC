"""Publish verified job artifacts to GCS, then atomically commit small BQ summaries.

Publication failure is separate from engine failure. Retry uses a saved immutable
request and never triggers inference/counting or creates tables implicitly.
"""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import base64
import json
import re
import os
import fcntl
from uuid import uuid4
from .. import __version__
from ..artifacts import read,write,sha,canonical,artifact,semantic_hash
from ..persistence import verify_manifest
from .adapters import inspect
from .contracts import need
from .cloud_schema import CloudDestination,SCHEMAS,publication_sql


def _crc32c(path):
    import google_crc32c
    checksum=google_crc32c.Checksum()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):checksum.update(chunk)
    return base64.b64encode(checksum.digest()).decode()


def prepare(root,result,inventory,context,parameters,destination):
    root=Path(root).resolve();saved=root/'publication-request.json'
    if saved.exists():return read(saved)
    for key in ('target_id','period_id'):
        need(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',context[key]) is not None,'PUBLICATION_CONTEXT_INVALID','Target/periode tidak aman.')
    job_id='job_'+uuid4().hex;prefix=f"jobs/{context['target_id']}/{context['period_id']}/{job_id}"
    created=datetime.now(timezone.utc).isoformat();common={'job_id':job_id,'target_id':context['target_id'],'created_at':created}
    rows={t:[] for t in SCHEMAS};entries=[];names=set()
    def add(path,name,expected=None):
        p=Path(path).resolve();need(p.is_file() and not Path(path).is_symlink(),'PUBLICATION_ARTIFACT_MISSING','Artefak hasil tidak tersedia.')
        digest=sha(p);need(expected is None or digest==expected,'PUBLICATION_ARTIFACT_CHANGED','Checksum artefak berubah.')
        need(name not in names and not Path(name).is_absolute() and '..' not in Path(name).parts,
             'PUBLICATION_PATH_INVALID','Nama artefak cloud tidak unik/aman.');names.add(name)
        entry={'path':str(p),'object':prefix+'/'+name,'sha256':digest,'bytes':p.stat().st_size};entries.append(entry)
        return 'gs://'+destination.bucket+'/'+entry['object']
    by_id={v['id']:v for v in inventory};safe_engines=[]
    for e in result['engines']:
        map_uri=map_sha=None
        base={'id':e['id'],'engine':e['engine'],'execution_status':e['execution_status'],'quality':e.get('quality')}
        if e['execution_status']=='SUCCEEDED':
            h=inspect(e['engine'],e['result_ref'],root);folder=Path(e['result_ref']['path']);manifest=verify_manifest(folder)
            engine_prefix='engines/'+e['engine']+'/'+e['id']
            for file in manifest['files']:
                uri=add(folder/file['path'],engine_prefix+'/'+file['path'],file['sha256'])
                if e['engine']=='area' and file['path']==h['result'].get('presentation_ref'):
                    map_uri,map_sha=uri,file['sha256']
            manifest_uri=add(folder/'manifest.json',engine_prefix+'/manifest.json',e['result_ref']['sha256'])
            r,n=h['result'],h['native']
            need(e.get('quality')==h['quality'],'PUBLICATION_QUALITY_MISMATCH','Kualitas receipt berbeda dari hasil engine.')
            need(e.get('summary')==r['summary'],'PUBLICATION_SUMMARY_MISMATCH','Rekap receipt berbeda dari ledger engine.')
            base.update(result_version=r['result_version'],manifest_uri=manifest_uri,summary=r['summary'])
            request_path=folder/'request.json'
            if e['engine']=='traffic':
                request=read(request_path)
                for key,ref in request.get('artifacts',{}).items():
                    p=artifact(ref,folder)
                    add(p,'inputs/config/'+e['id']+'/'+key+(''.join(p.suffixes) or '.json'),ref['sha256'])
            elif request_path.exists():
                request=read(request_path);ref=request.get('baseline',request.get('input'))
                if ref:add(artifact(ref,folder),'inputs/area/source-bundle.zip',ref['sha256'])
        else:r=n=None;manifest_uri=None
        if e['execution_status']!='SUCCEEDED':base.update(code=e.get('code'),message=e.get('message'),diagnostics=e.get('diagnostics',[]))
        safe_engines.append(base)
        if e['engine']=='traffic':
            item=by_id[e['id']];slot=item['slot']
            if r is not None:
                need(r['source_identity']['video_sha256']==slot['sha256'] and r['scope']['source_frames']==slot['decoded_frames'],
                     'PUBLICATION_SOURCE_MISMATCH','Hasil Traffic tidak sesuai sumber/ruang lingkup video.')
            if item.get('path') and Path(item['path']).is_file():
                add(item['path'],'inputs/videos/'+e['id']+'/source'+Path(item['path']).suffix.lower(),slot['sha256'])
            else:need(e['execution_status']!='SUCCEEDED','PUBLICATION_INPUT_MISSING','Video sumber untuk hasil sukses tidak tersedia.')
            if item.get('inspection_ref'):
                ref=item['inspection_ref'];add(ref['path'],'inputs/videos/'+e['id']+'/inspection.json',ref['sha256'])
            summary=r['summary'] if r is not None else {}
            rows['traffic_videos'].append({**common,'video_id':e['id'],'filename':item.get('filename') or Path(item.get('path') or e['id']).name,
                'day_group':slot.get('day'),'session':slot.get('session'),'source_sha256':slot['sha256'],
                'result_version':r['result_version'] if r else None,'execution_status':e['execution_status'],
                'result_quality':e.get('quality'),'source_frames':slot.get('decoded_frames'),
                'processed_frames':r['scope']['processed_frames'] if r else None,'observed_seconds':item['duration_seconds'],
                'accepted_measured':summary.get('accepted_measured'),'accepted_estimated':summary.get('accepted_estimated'),
                'pending':summary.get('pending'),'invalid':summary.get('invalid'),
                'direction_semantics':slot.get('direction'),'manifest_uri':manifest_uri})
            if n is not None:
                counts=Counter((v['category'],v['direction'],'measured' if v['evidence']['measured_crossing'] is True else 'estimated') for v in n['events'])
                for c in n['report']['supported_categories']:
                    for d in ('A_TO_B','B_TO_A'):
                        for level in ('measured','estimated'):
                            rows['traffic_counts'].append({**common,'video_id':e['id'],'category':c,'direction':d,
                                                          'evidence_level':level,'accepted_count':counts[c,d,level]})
        elif e['engine']=='area':
            if n is not None:
                target=n['identity']['market_config']['target']
                need(all(target[k]==context[k] for k in ('latitude','longitude')),'PUBLICATION_TARGET_MISMATCH','Target Area berbeda dari job.')
            s=n['summary'] if n else {};gate=n['attractor_gate'] if n else {}
            distances=[v['distance_to_candidate_m'] for v in gate.get('evidence',[])]
            rows['area_results'].append({**common,'result_version':r['result_version'] if r else None,
                'execution_status':e['execution_status'],'result_quality':e.get('quality'),
                'allocated_buildings':s.get('candidate_whole_buildings'),
                'unverified_buildings':s.get('market_status_counts',{}).get('UNVERIFIED',0) if n else None,
                'outer_zone_open':gate['state']=='OPEN' if gate.get('state') in ('OPEN','CLOSED') else None,
                'fasum_le400':sum(d<=400 for d in distances) if n else None,
                'fasum_gt400_le800':sum(400<d<=800 for d in distances) if n else None,'manifest_uri':manifest_uri,
                'map_html_uri':map_uri,'map_html_sha256':map_sha})
    ppac=result['ppac']
    if ppac['execution_status']=='SUCCEEDED':
        need(ppac.get('parameters')==parameters,'PUBLICATION_PARAMETERS_MISMATCH','Parameter PPAC berbeda dari job tersimpan.')
        bound=ppac.get('features',{}).get('context',{})
        need(all(bound.get(k)==context[k] for k in ('target_id','period_id','latitude','longitude')),'PUBLICATION_CONTEXT_MISMATCH','Context PPAC berbeda dari job.')
    rows['ppac_results'].append({**common,'execution_status':ppac['execution_status'],
        'result_quality':ppac.get('result_quality'),'std_total':ppac.get('std_total'),
        'std_residential':ppac.get('residential',{}).get('std_residential'),
        'std_traffic':ppac.get('traffic',{}).get('std_traffic_raw'),'std_fasum':ppac.get('fasum',{}).get('std_fasum'),
        'policy_version':ppac.get('policy_version'),'parameters_json':parameters,'diagnostics_json':ppac.get('diagnostics',[])})
    snapshot=root/'cloud-payload';snapshot.mkdir(exist_ok=True)
    write(snapshot/'context.json',context);add(snapshot/'context.json','inputs/context.json')
    write(snapshot/'video-inventory.json',[{k:v for k,v in i.items() if k not in ('path','geometry_ref','inspection_ref')} for i in inventory]);add(snapshot/'video-inventory.json','inputs/video-inventory.json')
    write(snapshot/'parameters.json',parameters);add(snapshot/'parameters.json','inputs/parameters.json')
    write(snapshot/'ppac.json',ppac);add(snapshot/'ppac.json','ppac/result.json')
    summary={'schema_version':'cloud_job_summary_v1','job_id':job_id,'context':context,'engines':safe_engines,'ppac':ppac}
    write(snapshot/'summary.json',summary);add(snapshot/'summary.json','summary.json')
    manifest={'schema_version':'cloud_job_manifest_v1','job_id':job_id,'created_at':created,
              'files':[{k:v for k,v in e.items() if k!='path'} for e in entries]}
    write(snapshot/'manifest.json',manifest);manifest_uri=add(snapshot/'manifest.json','manifest.json')
    statuses=[e['execution_status'] for e in result['engines']]
    execution='SUCCEEDED' if statuses and all(s=='SUCCEEDED' for s in statuses) else 'PARTIAL' if 'SUCCEEDED' in statuses else 'FAILED'
    rows['job_runs'].append({**common,'period_id':context['period_id'],'latitude':context['latitude'],'longitude':context['longitude'],
        'execution_status':execution,'ppac_status':ppac['execution_status'],'publication_status':'READY',
        'manifest_uri':manifest_uri,'manifest_sha256':sha(snapshot/'manifest.json'),'package_version':__version__})
    request={'schema_version':'cloud_publication_v1','job_id':job_id,'bucket':destination.bucket,'dataset':destination.dataset,
             'manifest_uri':manifest_uri,'manifest_sha256':sha(snapshot/'manifest.json'),'entries':entries,'rows':rows,
             'rows_sha256':semantic_hash(rows)}
    temporary=saved.with_name('.publication-request.tmp');write(temporary,request);temporary.replace(saved)
    return request


def progress(root,stage,completed=None,total=None):
    try:write(Path(root)/'publication-progress.json',{'stage':stage,'completed':completed,'total':total,'unit':'artefak'})
    except (OSError,ValueError):pass


class CloudPublisher:
    def __init__(self,destination,storage_client,bq_client):
        self.destination=destination;self.storage=storage_client;self.bq=bq_client;self.location=None

    def check(self):
        bucket=self.storage.bucket(self.destination.bucket)
        try:bucket.reload(timeout=30)
        except Exception as exc:
            if type(exc).__name__=='NotFound':need(False,'ARTIFACT_BUCKET_NOT_FOUND','Bucket hasil belum tersedia.')
            raise
        try:dataset=self.bq.get_dataset(self.destination.dataset,timeout=30)
        except Exception as exc:
            if type(exc).__name__=='NotFound':need(False,'BQ_DATASET_NOT_FOUND','Dataset hasil belum tersedia.')
            raise
        self.location=dataset.location
        aliases={'INTEGER':'INT64','BOOLEAN':'BOOL','FLOAT':'FLOAT64'}
        for name,expected in SCHEMAS.items():
            try:t=self.bq.get_table(self.destination.dataset+'.'+name,timeout=30)
            except Exception as exc:
                if type(exc).__name__=='NotFound':need(False,'BQ_TABLE_MISSING','Tabel '+name+' belum ada. Jalankan SQL setup sekali.')
                raise
            found={f.name:aliases.get(f.field_type,f.field_type) for f in t.schema}
            need(all(found.get(k)==v for k,v in expected.items()),'BQ_SCHEMA_MISMATCH','Schema tabel '+name+' berbeda; jalankan SQL setup atau migrasi yang sesuai.')
        return {'status':'READY','bucket':self.destination.bucket,'dataset':self.destination.dataset,'location':self.location}

    def upload(self,entry):
        p=Path(entry['path']);need(p.stat().st_size==entry['bytes'] and sha(p)==entry['sha256'],
                                  'PUBLICATION_ARTIFACT_CHANGED','Artefak berubah setelah disiapkan.')
        checksum=_crc32c(p);blob=self.storage.bucket(self.destination.bucket).blob(entry['object'])
        try:blob.reload(timeout=30)
        except Exception as exc:
            if type(exc).__name__!='NotFound':raise
            blob.metadata={'sha256':entry['sha256']}
            try:blob.upload_from_filename(str(p),if_generation_match=0,checksum='crc32c',timeout=600,content_type='text/html; charset=utf-8' if p.suffix.lower()=='.html' else None)
            except Exception as error:
                if type(error).__name__ not in ('PreconditionFailed','Conflict'):raise
            blob.reload(timeout=30)
        need(blob.size==entry['bytes'] and blob.crc32c==checksum and (blob.metadata or {}).get('sha256')==entry['sha256'],
             'GCS_ARTIFACT_CONFLICT','Object GCS berbeda; sumber tidak ditimpa.')
        return {'object':entry['object'],'generation':int(blob.generation),'crc32c':blob.crc32c}

    def commit(self,request):
        from google.cloud import bigquery
        params=[bigquery.ScalarQueryParameter('job_id','STRING',request['job_id']),
                bigquery.ScalarQueryParameter('manifest_sha256','STRING',request['manifest_sha256'])]
        for table in SCHEMAS:
            params.append(bigquery.ScalarQueryParameter('rows_'+table,'STRING',canonical(request['rows'][table]).decode()))
        need(sum(len(canonical(v)) for v in request['rows'].values())<5*1024**2,'BQ_SUMMARY_TOO_LARGE','Rekap terlalu besar untuk publikasi atomik.')
        self.bq.query(publication_sql(self.destination),job_config=bigquery.QueryJobConfig(query_parameters=params,maximum_bytes_billed=268435456),
                      location=self.location).result(timeout=300)

    def publish(self,root):
        root=Path(root)
        fd=os.open(root/'.publication.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:need(False,'PUBLICATION_RUNNING','Job ini sedang disimpan oleh proses lain.')
            return self._publish_locked(root)
        finally:os.close(fd)

    def _publish_locked(self,root):
        root=Path(root);request=read(root/'publication-request.json')
        need(request['schema_version']=='cloud_publication_v1' and request['bucket']==self.destination.bucket and
             request['dataset']==self.destination.dataset,'PUBLICATION_DESTINATION_CHANGED','Tujuan publication request berbeda.')
        need(request.get('rows_sha256')==semantic_hash(request['rows']),'PUBLICATION_SUMMARY_CHANGED','Rekap berubah sejak publication request dibuat.')
        progress(root,'Memeriksa tujuan GCS/BQ')
        self.check()  # Fail early on empty/missing BQ tables, before large uploads.
        receipts=[]
        for i,entry in enumerate(request['entries']):
            progress(root,'Menyimpan GCS: '+Path(entry['object']).name,i,len(request['entries']))
            receipts.append(self.upload(entry))  # Manifest is deliberately last.
        progress(root,'Menyimpan rekap BigQuery',len(receipts),len(receipts))
        self.commit(request)
        result={'status':'READY','job_id':request['job_id'],'manifest_uri':request['manifest_uri'],
                'dataset':request['dataset'],'uploaded_artifacts':len(receipts)}
        write(root/'publication-status.json',result)
        progress(root,'Penyimpanan selesai',len(receipts),len(receipts))
        return result
