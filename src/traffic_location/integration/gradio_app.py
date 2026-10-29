"""Gradio input/output adapter. Algorithms and credentials stay in the runtime."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import json
import math
import os
from pathlib import Path
import re
import time
from uuid import uuid4
from copy import deepcopy
from zoneinfo import ZoneInfo
from ..artifacts import read, write, semantic_hash
from .contracts import GateError
from .kaggle_runtime import KaggleRuntime

MODES={'Area Coverage':'area','Traffic Counter':'traffic','Gabungan + PPAC':'workflow','PPAC':'workflow'}
VIDEO_SOURCES=('Upload video','Dataset T7SL (contoh)')
UPLOAD_SLOTS=tuple((d,t) for d in ('weekday','weekend') for t in ('pagi','siang','sore','malam'))
EXTRA_SLOTS=tuple((d,t) for d in ('weekday','weekend') for t in ('tengah_malam','dini_hari','subuh'))
ROADS=['highway','mainstreet','street','substreet']
DISPLAY_TABLES={'Traffic Counter':['sesi','waktu','tipe kendaraan','jumlah kendaraan lewat'],
 'Area Coverage':['radius','Tipe Bangunan','Jumlah bangunan','jumlah kepala'], 'POI':['tipe_POI','nama_POI'],
 'Kompetitor (5 terdekat)':['Kdtk','nama_toko'],'Indomaret (5 terdekat)':['KDTK','NAMA_TOKO','TGL_GO','TIPE_TOKO','DOMAIN','SOCIO_CLASS','Investasi','RAB','STD','Jarak (m)','Tipe Jalan'],'Kontribusi':['Source','Kontribusi']}

def frame(data,columns):
    import pandas as pd
    from .ppac_view import scalar
    f=pd.DataFrame(data,columns=columns).astype(object)
    f=f.where(pd.notna(f),None)
    f=f.map(scalar) if hasattr(f,'map') else f.applymap(scalar)
    return f.astype(object).where(pd.notna(f),None)

def annotation_buttons(result=None):
    import gradio as gr
    by_slot={(v['day'],v['session']):v for v in (result or {}).get('annotated_videos',[])}
    names={(v.get('day_group'),v.get('session')):v.get('filename',v.get('video_id')) for v in (result or {}).get('traffic_counts',[])}
    return [gr.update(value='Buka annotated video' if slot in by_slot else 'Annotated belum tersedia',link=by_slot.get(slot,{}).get('url'),interactive=slot in by_slot) for slot in UPLOAD_SLOTS]+[gr.update(value=by_slot.get(slot,{}).get('filename') or names.get(slot) or (' / '.join(slot))) for slot in UPLOAD_SLOTS]

def display_frames(result=None):
    from .ppac_view import rows as ppac_rows,grid_from_rows
    has_result=bool(result);result=result or {};detail=result.get('display',{});traffic={}
    if not detail.get('area') and result.get('area_results'):
        a=result['area_results'][0];count=a.get('allocated_buildings') if a.get('execution_status')=='SUCCEEDED' else None
        detail={**detail,'area':[{'radius':'Total alokasi (rincian radius belum tersedia)' if count is not None else 'Area gagal/belum selesai; periksa diagnosis Area','jumlah_bangunan':count,'jumlah_KK':count}]}
    document=result.get('ppac_document')
    if has_result and document is None:document={'execution_status':'UNAVAILABLE','std_total':None,'reason':'ppac.json belum tersedia atau belum lolos verifikasi GCS. Muat ulang hasil dan periksa status penyimpanan.'}
    for r in result.get('traffic_counts',[]):
        key=(r.get('day_group'),r.get('session'),r.get('category'))
        if r.get('accepted_count') is not None:traffic[key]=traffic.get(key,0)+r['accepted_count']
    data=[[dict(zip(DISPLAY_TABLES['Traffic Counter'],(*k,v))) for k,v in traffic.items()],detail.get('area',[]),detail.get('poi',[]),detail.get('competitors',[]),detail.get('indomaret',[]),grid_from_rows(ppac_rows(document))]
    return [frame(rows,columns) for rows,columns in zip(data,DISPLAY_TABLES.values())]

INPUT_NAMES=('mode','target_id','latitude','longitude','period','video_ids','road','days','hours',
             'drive_thru','swot','cut','parking','confirmed')


def validate(values,video_choices):
    x=dict(zip(INPUT_NAMES,values[:len(INPUT_NAMES)]))
    x['video_source']=values[14] if len(values)>14 else VIDEO_SOURCES[1]
    x['uploads']=values[15] if len(values)>15 else []
    x['store_name']=values[16] if len(values)>16 else None
    x['annotate']=bool(values[17]) if len(values)>17 else False
    if x['store_name'] is not None:
        if not re.fullmatch('[A-Za-z0-9]{4}',str(x['target_id'])):raise ValueError('KDTK harus tepat 4 karakter huruf/angka.')
        if not str(x['store_name']).strip() or len(str(x['store_name']))>160:raise ValueError('Isi nama toko (maksimal 160 karakter).')
    if x['video_source'] not in VIDEO_SOURCES:raise ValueError('Pilih sumber video yang tersedia.')
    if x['mode'] not in MODES:raise ValueError('Pilih mode yang tersedia.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',str(x['target_id'])):
        raise ValueError('Kode toko: 1–32 huruf, angka, garis bawah, atau tanda minus.')
    for field,low,high in (('latitude',-80,84),('longitude',-180,180)):
        if not isinstance(x[field],(int,float)) or not math.isfinite(x[field]) or not low<=x[field]<=high:
            raise ValueError('Koordinat lokasi tidak valid.')
    try:date.fromisoformat(x['period'])
    except (ValueError,TypeError):raise ValueError('Tanggal analisis harus YYYY-MM-DD.') from None
    component_flow=os.environ.get('LI_COMPONENT_FLOW')=='1'
    mode=MODES[x['mode']]
    selected=[] if mode=='area' else (x['video_ids'] or [])
    if mode!='area' and x['video_source']==VIDEO_SOURCES[0]:
        reviewed=[r for r in x['uploads'] if isinstance(r,dict) and r.get('reviewed') is True]
        if not reviewed or (not component_flow and len(reviewed)!=len(x['uploads'])):
            raise ValueError('Upload video, lalu tinjau dan simpan geometri setiap video.')
        selected=[r['id'] for r in (reviewed if component_flow else x['uploads'])]
    if mode!='area' and x['video_source']==VIDEO_SOURCES[1] and (not selected or len(selected)!=len(set(selected)) or not set(selected)<=set(video_choices)):
        raise ValueError('Pilih minimal satu video T7SL yang tersedia.')
    if mode=='workflow' or component_flow:
        if mode=='workflow' and not x['confirmed']:raise ValueError('Konfirmasi kesesuaian video dengan target lokasi untuk PPAC.')
        if x['road'] not in ROADS:raise ValueError('Pilih profil jalan PPAC.')
        for field,low,high in (('days',1,7),('hours',1,24),('swot',0,None),('cut',0,None),('parking',0,None)):
            v=x[field]
            if not isinstance(v,(int,float)) or not math.isfinite(v) or v<low or (high is not None and v>high):
                raise ValueError('Nilai '+field+' tidak valid.')
    parameters={'schema_version':'ppac_parameters_mvp_v2',
                'residential':{'operating_days_per_week':x['days'],'swot_factor':x['swot']},
                'traffic':{'road_type':x['road'],'operating_hours':x['hours'],'drive_thru':bool(x['drive_thru'])},
                'aggregation':{'traffic_cut_factor':x['cut'],'parking_factor':x['parking']},
                'provenance':'Input bisnis pengguna melalui Gradio; lookup Residential/balance dinonaktifkan sesuai MVP v2.'}
    if len(values)>20:
        from .population import RWI
        if values[20] not in RWI:raise ValueError('Pilih RWI sebelum proses/pratinjau.')
        parameters['residential']['rwi']=values[20]
    return {**x,'mode':mode,'parameters':parameters,'video_ids':selected}


def engine_rows(result):
    rows=[]
    for item in result.get('engines',[]):
        brief=item.get('summary') or {}
        rows.append([item['id'],item.get('execution_status'),item.get('quality',''),
                     json.dumps(brief,ensure_ascii=False) if brief else (str(item.get('message') or item.get('code') or 'Tahap gagal')+' '+json.dumps(item.get('diagnostics',[]),ensure_ascii=False))])
    rows.extend([v.get('video_id'),'SKIPPED','',v.get('code','')+': '+v.get('reason','')] for v in result.get('skipped_videos',[]))
    return rows


class Controller:
    def __init__(self,base,config_root,*,input_root='/kaggle/input',runtime_factory=KaggleRuntime):
        self.base=Path(base).resolve();self.config_root=Path(config_root).resolve()
        self.input_root=input_root;self.runtime_factory=runtime_factory
        self.video_choices=[Path(v['filename']).stem for v in read(self.config_root/'experiment.json')['videos']]
        from .cloud_schema import CloudDestination
        self.destination=CloudDestination.configured()
        self.upload_root=self.base/'uploads';self.upload_root.mkdir(parents=True,exist_ok=True)
        self.maps=self.base/'saved-maps';self.maps.mkdir(parents=True,exist_ok=True)
        self.exports=self.base/'exports';self.exports.mkdir(parents=True,exist_ok=True)

    def runtime(self,x):
        # Stable target-specific workspace enables validated reuse across business changes.
        key=semantic_hash({k:x[k] for k in ('target_id','latitude','longitude','period')})
        return self.runtime_factory(self.base/'targets'/key,self.config_root,x['latitude'],x['longitude'],
                                    target_id=x['target_id'],period_id=x['period'],performance={'reuse':True},
                                    publication=self.destination,upload_root=self.upload_root,store_name=x.get('store_name'),annotate=x.get('annotate',False))

    def check(self,*values):
        if getattr(self,'background_runs',None) and self.background_runs.current():return 'Job masih aktif; pantau progres atau diagnosis tanpa pemeriksaan runtime baru.',[]
        try:
            x=validate(values,self.video_choices);runtime=self.runtime(x)
            state=runtime.probe()
            if x['mode']=='area':inventory=[]
            elif x['video_source']==VIDEO_SOURCES[0]:
                from .uploads import inventory as upload_inventory
                if os.environ.get('LI_COMPONENT_FLOW')=='1':
                    from .uploads import valid_inventory
                    inventory,skipped=valid_inventory(x['uploads'],self.upload_root)
                else:inventory=upload_inventory(x['uploads'],self.upload_root)
            else:inventory=runtime.video_inventory(self.input_root)
            objects=state['gcs'].get('objects',{})
            rows=[[name,item['status']] for name,item in objects.items()]
            publication=state.get('publication',{})
            rows.append(['Penyimpanan hasil GCS/BQ',publication.get('status','NOT_CHECKED')+' '+str(publication.get('code',''))])
            rows += [[v['id'],v['status']] for v in inventory if v['id'] in x['video_ids']]
            return 'Kesiapan diperiksa. Engine belum berjalan.',rows
        except (ValueError,GateError) as exc:return str(exc),[]
        except Exception as exc:return 'Pemeriksaan gagal ('+type(exc).__name__+'). Periksa Internet, Secret LocatioIntelligent, dan izin GCS.',[]

    def prepare_files(self,files):
        import gradio as gr
        from .uploads import prepare
        try:
            template=read(self.config_root/'geometry/T7SL-WEEKDAY-PAGI.json')
            rows=prepare(files,self.upload_root,template)
            choices=[(r['filename']+' ['+r['id'][-6:]+']',r['id']) for r in rows]
            return rows,gr.update(choices=choices,value=rows[0]['id']),f'{len(rows)} video disiapkan. Tinjau dan simpan geometri setiap video.'
        except Exception as exc:
            message=str(exc) if isinstance(exc,ValueError) else 'Video gagal dibaca ('+type(exc).__name__+'). Periksa format video dan FFmpeg.'
            return [],gr.update(choices=[],value=None),message

    def save_project(self,*values):
        try:
            original=list(values);original[0]='Area Coverage';x=validate(original,self.video_choices)
            payload={'schema_version':'li_project_v1','period':x['period'],'kdtk':x['target_id'],'store_name':x['store_name'],
                     'latitude':x['latitude'],'longitude':x['longitude'],'parameters':x['parameters'],
                     'videos':[{'id':r['id'],'filename':r['filename'],'sha256':r['sha256'],'day':r['day'],'session':r['session'],'reviewed':r['reviewed'],'geometry':r['geometry']} for r in x['uploads']]}
            path=self.base/'projects'/(uuid4().hex+'.json');write(path,payload)
            runtime=self.runtime(x);name='projects/'+x['target_id']+'/'+x['period']+'/'+path.name
            runtime.connect().bucket(self.destination.bucket).blob(name).upload_from_filename(str(path),if_generation_match=0,content_type='application/json',checksum='crc32c')
            return 'Project tersimpan: gs://'+self.destination.bucket+'/'+name+'. Metadata/geometri tersimpan; video upload lokal belum otomatis menjadi input GCS.'
        except Exception as exc:return 'Save project belum berhasil: '+(str(exc) if isinstance(exc,ValueError) else type(exc).__name__)+'. Draft lokal tetap tersedia pada sesi Kaggle.'

    def diagnostic_runtime(self,values):
        # Log reading must not require store name, videos, geometry or PPAC inputs.
        if len(values)<5:raise ValueError('Isi KDTK, koordinat dan periode untuk memilih workspace.')
        target,latitude,longitude,period=values[1:5]
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',target or ''):raise ValueError('KDTK tidak valid.')
        from .kaggle_runtime import area_config
        area_config(latitude,longitude,target_id=target)
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',period or ''):raise ValueError('Periode tidak valid.')
        return self.runtime({'target_id':target,'latitude':latitude,'longitude':longitude,'period':period})

    def area_diagnostic(self,*values):
        from .area_trace import latest_report
        from .failure_details import safe
        try:
            runtime=self.diagnostic_runtime(values);report=latest_report(runtime.base)
            lines=[];trace=report['trace']
            if report.get('current_job'):
                job=report['current_job'];lines.append('Job '+job['job_id']+' — mode '+job['mode']+' — input '+job['input_sha256'])
                if report.get('current_job_status'):lines.append('Tahap job: '+str(report['current_job_status'].get('stage'))+' '+str(report['current_job_status'].get('observed_status',report['current_job_status'].get('status'))))
                if trace and not report.get('area_trace_is_latest_job'):lines.append('Jejak Area di bawah adalah milik job sebelumnya; bukan status Area pada job saat ini.')
            if trace:
                lines.append('Area '+trace['execution_status']+' — tahap '+trace['stage']+' — package '+trace['package_version'])
                if trace.get('result'):lines.append('Hasil: '+str(trace['result']))
                if trace.get('failure'):
                    lines.append('Kategori: '+trace['failure'].get('category','UNKNOWN'))
                    lines.append('Penyebab: '+str(trace['failure']))
            if report.get('publication'):lines.append('Penyimpanan: '+str(report['publication']))
            if report.get('traffic_preparation_status'):
                stage=report['traffic_preparation_status'];lines.append('Traffic: '+str(stage.get('stage'))+' '+str(stage.get('status'))+' '+str(stage.get('message','')))
            for receipt in report.get('current_engine_receipts',[]):
                lines.append(str(receipt.get('id'))+': '+str(receipt.get('execution_status'))+' '+str(receipt.get('code',''))+' '+str(receipt.get('message','')))
                if receipt.get('execution_status')=='FAILED':lines.append(str(receipt.get('diagnostics',[])))
            lines.extend(e['log']+'\n'+'\n'.join(e['errors']) for e in report['diagnostics']['evidence'])
            return '\n'.join(lines) if lines else 'Belum ada jejak/log error Area pada workspace ini. Pilih Area Coverage dan proses Area saja; Traffic tidak dijalankan.'
        except Exception as exc:return 'Diagnosis Area gagal: '+safe(exc)

    def export_area_diagnostics(self,*values):
        from .area_trace import export_report
        from .failure_details import safe
        try:
            from uuid import uuid4
            runtime=self.diagnostic_runtime(values)
            path=export_report(runtime.base,self.exports/('area-diagnostics-'+uuid4().hex+'.zip'))
            if os.environ.get('LI_AUTH_MODE')=='adc':
                from .server_watchdog import append_diagnostics
                append_diagnostics(self.base.parent,path)
            return str(path),'Paket diagnosis siap. Tidak memuat secret, video, source rows atau perhitungan baru.'
        except Exception as exc:return None,'Paket diagnosis gagal: '+safe(exc)

    def prepare_slot_sources(self,*values):
        if os.environ.get('LI_COMPONENT_FLOW')=='1':return self.prepare_independent_sources(*values)
        from .upload_transport import resolve_reference
        import gradio as gr
        count=len(UPLOAD_SLOTS+EXTRA_SLOTS);files=list(values[:count]);refs=values[count:]
        try:
            for i,reference in enumerate(refs):
                if reference and reference.strip():
                    if files[i]:raise ValueError('Pilih file ATAU referensi pada slot yang sama, bukan keduanya.')
                    def connect():
                        runtime=self.runtime({'target_id':'video-staging','period':'sources','latitude':0.,'longitude':0.})
                        return runtime.connect()
                    files[i]=resolve_reference(reference,self.upload_root/'references',connect)
                    from .uploads import MAX_BATCH_BYTES
                    if sum(Path(p).stat().st_size for p in files if p)>MAX_BATCH_BYTES:raise ValueError('Total video maksimal 2 GiB per batch.')
            return self.prepare_slots(*files)
        except Exception as exc:
            return [],gr.update(choices=[],value=None),str(exc) if isinstance(exc,ValueError) else 'Sumber video gagal diambil ('+type(exc).__name__+'). Periksa path/izin GCS.'

    def prepare_independent_sources(self,*values):
        from .upload_transport import resolve_reference
        from .uploads import prepare,MAX_BATCH_BYTES
        from .failure_details import safe
        import gradio as gr
        slots=UPLOAD_SLOTS+EXTRA_SLOTS;count=len(slots)
        files=list(values[:count]);refs=list(values[count:]);errors=[];rows=[];seen=set();total=0
        template=read(self.config_root/'geometry/T7SL-WEEKDAY-PAGI.json')
        for i,(day,session) in enumerate(slots):
            path=files[i] if i<len(files) else None;reference=refs[i] if i<len(refs) else None
            if not path and not reference:continue
            try:
                if path and reference:raise ValueError('Pilih file ATAU referensi pada slot yang sama.')
                if reference:
                    def connect():
                        runtime=self.runtime({'target_id':'video-staging','period':'sources','latitude':0.,'longitude':0.})
                        return runtime.connect()
                    path=resolve_reference(reference,self.upload_root/'references',connect)
                size=Path(path).stat().st_size
                if total+size>MAX_BATCH_BYTES:raise ValueError('Total video valid maksimal2GiB per batch.')
                row=prepare([path],self.upload_root,template)[0]
                if row['sha256'] in seen:raise ValueError('Video sumber duplikat pada slot lain.')
                total+=size;seen.add(row['sha256'])
                row.update(day=day,session=session,upload_slot=[day,session]);rows.append(row)
            except Exception as error:
                errors.append({'id':'skipped_'+day+'_'+session,'reviewed':False,'skip_reason':safe(error),
                               'skip_code':getattr(error,'code',type(error).__name__)})
        choices=[(r['day']+' / '+r['session']+' — '+r['filename'],r['id']) for r in rows]
        message=str(len(rows))+' video valid disiapkan; tinjau dan simpan geometri. '+str(len(errors))+' slot dilewati.'
        if errors:message+=' '+ '; '.join(r['id']+': '+r['skip_reason'] for r in errors)
        return rows+errors,gr.update(choices=choices,value=rows[0]['id'] if rows else None),message

    def prepare_slots(self,*files):
        from .uploads import prepare
        import gradio as gr
        slots=UPLOAD_SLOTS+EXTRA_SLOTS
        try:
            present=[(slot,path) for slot,path in zip(slots,files) if path]
            if not present:raise ValueError('Pilih video pada minimal satu slot.')
            rows=prepare([path for _,path in present],self.upload_root,read(self.config_root/'geometry/T7SL-WEEKDAY-PAGI.json'))
            for row,((day,session),_) in zip(rows,present):
                row.update(day=day,session=session,upload_slot=[day,session])
            choices=[(r['day']+' / '+r['session']+' — '+r['filename'],r['id']) for r in rows]
            missing=[d+'/'+t for (d,t),path in zip(UPLOAD_SLOTS,files[:8]) if not path]
            message=f'{len(rows)} video disiapkan. Tinjau geometri setiap video.'
            if missing:message+=' Slot utama belum diisi: '+', '.join(missing)+'. PPAC menunggu seluruh slot.'
            return rows,gr.update(choices=choices,value=rows[0]['id']),message
        except Exception as exc:
            message=str(exc) if isinstance(exc,ValueError) else 'Video gagal dibaca ('+type(exc).__name__+').'
            return [],gr.update(choices=[],value=None),message

    def cloud_results(self,target_id,job_id):
        from .cloud_results import ResultsReader
        from .cloud_schema import SCHEMAS
        import pandas as pd
        empty=[pd.DataFrame(columns=list(SCHEMAS[t])) for t in ('traffic_counts','area_results','ppac_results')]
        try:
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',target_id or ''):raise ValueError('Kode toko tidak valid.')
            runtime=self.runtime({'target_id':target_id,'period':'saved-results','latitude':0.,'longitude':0.})
            publisher=runtime.cloud_publisher()
            reader=ResultsReader(self.destination,publisher.storage,publisher.bq,map_cache=self.maps)
            result=reader.load(target_id,job_id.strip() if job_id else None)
            frames=[frame(result[t],list(SCHEMAS[t])) for t in ('traffic_counts','area_results','ppac_results')]
            status='Hasil tersimpan dari BigQuery: '+result['job_id']+'. '+result['map_status']
            status+=' '+' '.join(result.get('read_errors',[])+result.get('artifact_status',[]))
            document=result.get('ppac_document') or {}
            from .failure_details import safe
            status+=' PPAC: '+str(document.get('execution_status','UNAVAILABLE'))+'. '+safe(document.get('diagnostics') or document.get('reason') or '')
            note=getattr(type(runtime),'note_reopened_area',None)
            if callable(note):status+=' '+str(note(runtime,result))
            if result.get('truncated'):status+=' Tampilan traffic dibatasi; gunakan query BQ untuk seluruh baris.'
            return status,result['job_id'],result['map_html'],*frames,*display_frames(result),*annotation_buttons(result),result.get('identity_text','')
        except Exception as exc:
            message=str(exc) if isinstance(exc,ValueError) else 'Pembacaan BQ/GCS gagal ('+type(exc).__name__+'). Periksa izin dan schema.'
            return message,job_id or '','',*empty,*display_frames(),*annotation_buttons(),''

    def current_cloud_results(self,pointer,target_id,job_id,live_ppac=None):
        if pointer:
            try:
                saved=read(Path(pointer['output'])/'publication-status.json')
                if saved.get('status')=='READY':return self.cloud_results(pointer['context']['target_id'],saved['job_id'])
            except (OSError,KeyError,ValueError):pass
            from .cloud_schema import SCHEMAS
            import pandas as pd
            from html import escape
            c=pointer.get('context',{})
            identity_text='**Job:** '+escape(str(pointer.get('job_id','')))+' · **KDTK:** '+escape(str(c.get('target_id','')))+' · **Latitude:** '+str(c.get('latitude'))+' · **Longitude:** '+str(c.get('longitude'))
            live_frames=display_frames()
            if live_ppac:
                from .ppac_view import grid_from_rows
                live_frames[-1]=frame(grid_from_rows(live_ppac),DISPLAY_TABLES['Kontribusi'])
            return ('Hasil job ini belum dipublikasikan. Tabel Kontribusi berisi hasil komputasi lokal bila tersedia; belum terbukti tersimpan. Periksa status penyimpanan.', '', '',
                    *[pd.DataFrame(columns=list(SCHEMAS[t])) for t in ('traffic_counts','area_results','ppac_results')],*live_frames,*annotation_buttons(),identity_text)
        from .cloud_schema import SCHEMAS
        import pandas as pd
        return ('Belum ada hasil job ini yang dapat dibuka. Gunakan tombol Buka hasil BQ untuk hasil sebelumnya.','','',
                *[pd.DataFrame(columns=list(SCHEMAS[t])) for t in ('traffic_counts','area_results','ppac_results')],*display_frames(),*annotation_buttons(),'')

    def preview_upload(self,rows,video_id):
        from .uploads import find,render
        if not rows or not video_id:return None,None,None,None,False,'Belum ada video disiapkan.'
        try:r=find(rows,video_id)
        except ValueError as exc:return None,None,None,None,False,str(exc)
        text=f"{r['filename']} | {r['width']}x{r['height']} | {r['decoded_frames']} frame | {r['duration_seconds']:.2f} detik | "+('TERSIMPAN' if r['reviewed'] else 'BELUM DITINJAU')
        return render(r,self.upload_root/'previews'),r['day'],r['session'],r['direction'],bool(r['reviewed']),text

    def edit_geometry(self,rows,video_id,component,point=None,clear=False):
        from .uploads import edit,find,render
        try:
            updated=edit(rows,video_id,component,point=point,clear=clear)
            return updated,render(find(updated,video_id),self.upload_root/'previews'),False,'Geometri berubah. Lengkapi titik lalu simpan tinjauan.'
        except ValueError as exc:return rows,None,False,str(exc)

    def save_review(self,rows,video_id,day,session,direction,confirmed):
        from .uploads import review
        try:
            from .uploads import find
            slot=find(rows,video_id).get('upload_slot')
            if slot and slot!=[day,session]:raise ValueError('Hari/sesi harus sesuai slot upload. Pindahkan file ke slot yang benar.')
            updated=review(rows,video_id,day,session,direction,confirmed,self.upload_root/'geometries')
            done=sum(r['reviewed'] for r in updated)
            return updated,f'Tinjauan tersimpan: {done}/{len(updated)} video siap.'
        except ValueError as exc:return rows,str(exc)

    def invalidate_review(self,rows,video_id):
        from copy import deepcopy
        from .uploads import find
        rows=deepcopy(rows)
        if rows and video_id:
            row=find(rows,video_id);row['reviewed']=False;row.pop('geometry_ref',None)
        return rows,False,'Metadata berubah. Simpan kembali tinjauan video ini.'

    def retry_storage(self,pointer):
        if getattr(self,'background_runs',None) and self.background_runs.current():return 'Job masih aktif; tunggu publikasi selesai sebelum retry.',None
        if not pointer:return 'Belum ada job yang dapat disimpan ulang.',None
        folder=Path(pointer['output']).resolve()
        if not folder.is_relative_to(self.base):return 'Lokasi job tidak valid.',None
        runtime=self.runtime(pointer['context'])
        status=runtime.retry_publication(folder)
        return 'Penyimpanan: '+status['status']+' '+str(status.get('code','')),None

    def location_preview(self,latitude,longitude):
        from html import escape
        for value,low,high in ((latitude,-80,84),(longitude,-180,180)):
            if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError('Koordinat lokasi tidak valid.')
        import folium
        m=folium.Map(location=[latitude,longitude],zoom_start=15,tiles=None)
        folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',attr='Esri',name='Esri Imagery').add_to(m)
        folium.Marker([latitude,longitude],tooltip='Calon toko').add_to(m)
        for radius in (400,2000):folium.Circle([latitude,longitude],radius=radius,fill=False).add_to(m)
        return '<iframe title="Peta lokasi calon toko" sandbox="allow-scripts" referrerpolicy="no-referrer" style="width:100%;height:460px;border:0" srcdoc="'+escape(m.get_root().render(),quote=True)+'"></iframe>'

    def save_location(self,latitude,longitude):
        from .failure_details import safe
        try:
            html=self.location_preview(latitude,longitude)
            write(self.base/'locations'/(uuid4().hex+'.json'),{'schema_version':'location_draft_v1','latitude':latitude,'longitude':longitude,'created_at':datetime.now(ZoneInfo('Asia/Jakarta')).isoformat()})
            return html,'Lokasi tersimpan sementara: '+str(latitude)+', '+str(longitude)+'. Snapshot GCS dibuat saat Running; tinjau dan konfirmasi seluruh input sebelum memproses.'
        except Exception as error:return '', 'SAVE lokasi gagal: '+safe(error)

    def preview_job(self,*values):
        from .job_input import review
        try:
            x=validate(values,self.video_choices)
            html=self.location_preview(x['latitude'],x['longitude'])
            token=review(x)
            summary={'KDTK':x['target_id'],'Nama Toko':x.get('store_name'),'Periode':x['period'],
                     'Latitude':x['latitude'],'Longitude':x['longitude'],'Mode':x['mode'],
                     'Video dipilih':x['video_ids'],'Parameter':x['parameters'],'Review SHA256':token['fingerprint']}
            return token,html,json.dumps(summary,ensure_ascii=False,indent=2),False
        except Exception as error:
            from .failure_details import safe
            return None,'','Pratinjau gagal: '+safe(error),False

    def progress_text(self,runtime,started):
        if os.environ.get('LI_PHASE123')=='1':
            from .job_status import lines as observed
            cached=getattr(runtime,'_phase_progress_cache',None)
            if cached and time.time()-cached[0]<2:return cached[1]
            text='\n'.join(observed(runtime.base,started)) or 'Menyiapkan job; belum ada checkpoint. Server hidup bukan bukti engine maju.'
            runtime._phase_progress_cache=(time.time(),text)
            return text
        lines=[]
        for path in sorted(runtime.base.rglob('*progress.json')):
            try:
                if path.stat().st_mtime<started or path.stat().st_size>131072:continue
                obj=read(path)
                if not isinstance(obj,dict):continue
                label='Area' if 'area' in path.name else 'Proses'
                for parent in list(path.parents)[:4]:
                    producer=parent/'producer.json'
                    if producer.exists():
                        data=read(producer);label=Path(data['artifacts']['video']['path']).stem;break
                text=label+' — '+str(obj.get('stage','berjalan'))
                if obj.get('completed') is not None:text+=f" | {obj['completed']}/{obj.get('total','?')} {obj.get('unit','frame')}"
                if obj.get('fps_actual') is not None:text+=f" | {obj['fps_actual']:.1f} FPS"
                if obj.get('eta_seconds') is not None:text+=f" | ETA tahap {obj['eta_seconds']:.0f} detik"
                lines.append(text)
            except (OSError,ValueError,KeyError,TypeError):continue
        return '\n'.join(lines[-24:]) or 'Menyiapkan sumber/runtime; rincian setup tersedia di log notebook.'

    def live_engine_rows(self,runtime,identity):
        if not identity:return []
        try:
            root=getattr(runtime,'_active_run_root',None)
            if root is None:return []
            path=Path(root)/'progress.json';snapshot=Path(root)/'job-input.json'
            if not snapshot.is_file() or snapshot.stat().st_size>2*1024**2:return []
            if read(snapshot).get('job_id')!=identity['job_id']:return []
            if not path.is_file() or path.stat().st_size>1024**2:return []
            return engine_rows({'engines':read(path)})
        except (OSError,ValueError,KeyError,TypeError):return []

    def process(self,*values):
        try:
            x=deepcopy(validate(values,self.video_choices))
            if os.environ.get('LI_PHASE123')=='1':
                from .job_input import checked_review
                x=checked_review(x,values[18] if len(values)>18 else None,values[19] if len(values)>19 else False)
        except ValueError as exc:
            yield ('INPUT_ERROR: '+str(exc) if os.environ.get('LI_PHASE123')=='1' else str(exc)),[],{},'',None,None;return
        started=time.time()
        try:runtime=self.runtime(x)
        except Exception as exc:
            yield 'Workspace gagal disiapkan ('+type(exc).__name__+').',[],{},'',None,None;return
        identity={'job_id':'job_'+uuid4().hex,'review_sha256':values[18]['fingerprint']} if os.environ.get('LI_PHASE123')=='1' else None
        yield ('Job '+identity['job_id']+' — Latitude '+str(x['latitude'])+', Longitude '+str(x['longitude'])+'. Input dibekukan; snapshot GCS dipersiapkan. Biarkan notebook berjalan.' if identity else 'Proses dimulai. Biarkan notebook tetap berjalan.'),[],{},'Memeriksa sumber dan menyiapkan runtime.',None,None
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                options={'uploaded_videos':x['uploads']} if x['video_source']==VIDEO_SOURCES[0] and x['mode']!='area' else {}
                if os.environ.get('LI_PHASE123')=='1':
                    options['request_identity']=identity
                future=pool.submit(runtime.execute,x['mode'],x['parameters'],input_root=self.input_root,
                                   target_confirmed=x['confirmed'],video_ids=x['video_ids'],**options)
                while not future.done():
                    yield 'Engine berjalan…',self.live_engine_rows(runtime,identity),{},self.progress_text(runtime,started),None,None
                    time.sleep(2)
                result=future.result()
            ppac=result['ppac']
            failed=sum(row.get('execution_status')!='SUCCEEDED' for row in result['engines'])
            publication=result.get('publication',{'status':'NOT_REQUESTED'})
            status=f"Selesai. Engine/video gagal: {failed}. Video dilewati: {len(result.get('skipped_videos',[]))}. PPAC: {ppac['execution_status']}. Penyimpanan: {publication['status']} {publication.get('code','')}."
            from .failure_details import safe
            explanation=ppac.get('diagnostics') or ppac.get('reason')
            if explanation:status+=' Alasan: '+safe(explanation)
            if ppac.get('scope') in ('area','traffic'):status+=' Komponen '+ppac['scope']+' saja; STD total belum lengkap.'
            yield status,engine_rows(result),ppac,self.progress_text(runtime,started),None,{'output':result.get('output',''),'context':x,'job_id':identity['job_id'] if identity else publication.get('job_id')}
        except GateError as exc:
            from .failure_details import category
            yield category(exc.code,str(exc))+': '+str(exc),[],{},self.progress_text(runtime,started),None,None
        except Exception as exc:
            if os.environ.get('LI_PHASE123')=='1':
                from .failure_details import category,safe
                yield category(type(exc).__name__,str(exc))+': '+safe(exc),[],{},self.progress_text(runtime,started),None,None
                return
            yield 'Proses gagal ('+type(exc).__name__+'). Periksa log notebook; hasil engine tersimpan tetap dipertahankan.',[],{},self.progress_text(runtime,started),None,None


def build_app(base,config_root,*,input_root='/kaggle/input',runtime_factory=KaggleRuntime,default_mode='Gabungan + PPAC'):
    import gradio as gr
    if default_mode not in MODES:raise ValueError('Mode awal tidak valid.')
    controller=Controller(base,config_root,input_root=input_root,runtime_factory=runtime_factory)
    import os
    local_video='/content/videos/...' if os.environ.get('LI_RUNTIME_PLATFORM')=='colab' else '/kaggle/input/...'
    with gr.Blocks(title='Area · Traffic · PPAC') as app:
        with gr.Tabs():
            with gr.Tab('HOME'):
                phase123=os.environ.get('LI_PHASE123')=='1'
                gr.Markdown('## 1. Pilih Mode')
                choices=['Area Coverage','Traffic Counter','PPAC'] if os.environ.get('LI_COMPONENT_FLOW')=='1' else ['Area Coverage','Traffic Counter','Gabungan + PPAC']
                if default_mode not in choices:default_mode=choices[-1]
                mode=gr.Dropdown(choices,value=default_mode,label='Proses')
                if os.environ.get('LI_COMPONENT_FLOW')=='1':
                    gr.Markdown('**Area Coverage:** Area → PPAC Residential/Fasum. **Traffic Counter:** video valid → PPAC Traffic. **PPAC:** Area → Traffic → PPAC gabungan. STD total menunggu semua input wajib lengkap; komponen tersedia tetap ditampilkan.')
                gr.Markdown('## 2. PPAC')
                gr.Markdown('## Identity')
                with gr.Row():
                    target=gr.Textbox(value='T7SL',label='KDTK (4 karakter)',max_length=4)
                    store_name=gr.Textbox(label='Nama Toko',max_length=160)
                    period=gr.DateTime(value=datetime.now(ZoneInfo('Asia/Jakarta')).date().isoformat(),include_time=False,type='string',interactive=False,label='Periode (tanggal pembuatan)')
                with gr.Group():
                    with gr.Row():
                        road=gr.Dropdown(ROADS,value='mainstreet',label='Profil jalan PPAC')
                        days=gr.Dropdown(list(range(1,8)),value=7,label='Hari operasional per minggu')
                        hours=gr.Dropdown(list(range(1,25)),value=15,label='Jam operasional per hari')
                        drive=gr.Checkbox(value=False,label='Drive thru')
                    with gr.Row():
                        swot=gr.Number(value=1,minimum=0,label='Faktor SWOT (1 = tanpa penyesuaian)')
                        cut=gr.Number(value=1,minimum=0,label='Faktor potongan Traffic (1 = tanpa penyesuaian)')
                        parking=gr.Number(value=1,minimum=0,label='Faktor parkir (1 = tanpa penyesuaian)')
                gr.Markdown('Operasional **lebih dari 15 jam** memerlukan sesi tambahan. Memilih sebagian video dapat membuat PPAC menunggu input. Hasil parsial tetap ditandai; akurasi identitas kendaraan belum tervalidasi.')
                rwi=gr.Dropdown(choices=['MENENGAH ATAS','MENENGAH BAWAH'],value=None,label='RWI — asumsi estimasi penduduk') if phase123 else None
                gr.Markdown('## 3. Area Coverage')
                with gr.Row(equal_height=True):
                    with gr.Column(scale=1,min_width=220):
                        latitude=gr.Number(value=-0.8994976613947719,label='Latitude')
                        longitude=gr.Number(value=131.3221639428227,label='Longitude')
                        save_location=gr.Button('SAVE')
                        location_status=gr.Textbox(label='Status lokasi',interactive=False)
                    with gr.Column(scale=3,min_width=320):
                        input_map=gr.HTML(label='Peta lokasi calon toko')
                gr.Markdown('SAVE menyimpan koordinat dan menampilkan pin. Peta membutuhkan Leaflet/Esri dari jaringan browser. SAVE tidak menjalankan engine atau mengonfirmasi seluruh input job.')
                gr.Markdown('## 4. Traffic Counter')
                source=gr.Radio(VIDEO_SOURCES,value=VIDEO_SOURCES[0],label='Sumber video')
                upload_state=gr.State([]);job_pointer=gr.State(None)
                with gr.Group() as upload_group:
                    with gr.Accordion('Menu upload',open=False):
                        gr.Markdown('Delapan slot utama: satu video per kondisi dan waktu. Maksimal 1 GiB/file dan 2 GiB total. Slot kosong tidak dianggap nol.')
                        slot_files=[];slot_refs=[]
                        gr.Markdown("Jika upload terputus: unggah video ke GCS melalui Cloud Console, lalu isi gs://bucket/object di slot yang sesuai. Referensi file lokal: "+local_video+". Jangan ubah file menjadi publik.")
                        for d in ('weekday','weekend'):
                            gr.Markdown('### '+('Weekday' if d=='weekday' else 'Weekend'))
                            with gr.Row():
                                for t in ('pagi','siang','sore','malam'):
                                    with gr.Column():
                                        slot_files.append(gr.File(file_count='single',file_types=['video'],type='filepath',label=d+' / '+t))
                                        slot_refs.append(gr.Textbox(label='Referensi '+d+' / '+t,placeholder='gs://aretfak-location-intelligence/incoming/video.mp4 atau '+local_video))
                        with gr.Accordion('Sesi tambahan untuk operasional >15 jam',open=False):
                            for d in ('weekday','weekend'):
                                with gr.Row():
                                    for t in ('tengah_malam','dini_hari','subuh'):
                                        with gr.Column():
                                            slot_files.append(gr.File(file_count='single',file_types=['video'],type='filepath',label=d+' / '+t))
                                            slot_refs.append(gr.Textbox(label='Referensi '+d+' / '+t,placeholder='gs://aretfak-location-intelligence/incoming/video.mp4 atau '+local_video))
                        prepare=gr.Button('Siapkan video dan geometri')
                        upload_status=gr.Textbox(label='Kesiapan video',interactive=False)
                    with gr.Accordion('Menu edit geometri',open=False):
                        selected=gr.Dropdown(choices=[],label='Video yang ditinjau')
                        preview=gr.Image(type='filepath',interactive=False,label='Frame pertama: garis merah, polygon A biru, polygon B kuning')
                        with gr.Row():
                            day=gr.Dropdown(['weekday','weekend'],label='Kelompok hari (dari slot)',interactive=False)
                            session=gr.Dropdown(['pagi','siang','sore','malam','tengah_malam','dini_hari','subuh'],label='Sesi perekaman (dari slot)',interactive=False)
                        from .uploads import DIRECTIONS
                        direction=gr.Dropdown(DIRECTIONS,value=DIRECTIONS[0],label='Arti arah pada video')
                        gr.Markdown('Template awal harus ditinjau per video. Untuk menggambar ulang: pilih bagian, tekan **Ulangi bagian**, lalu klik titik berurutan pada gambar. Garis: 2 titik; polygon: minimal 3 titik perimeter. Video asli tidak diubah.')
                        with gr.Row():
                            component=gr.Dropdown(['Garis','Polygon A','Polygon B'],value='Garis',label='Bagian yang diedit')
                            clear=gr.Button('Ulangi bagian')
                        reviewed=gr.Checkbox(value=False,label='Saya telah meninjau geometri, arah, hari dan sesi video ini.')
                        save=gr.Button('Simpan tinjauan video')
                        review_status=gr.Textbox(label='Tinjauan per video',interactive=False)
                with gr.Group(visible=False) as dataset_group:
                    videos=gr.CheckboxGroup(controller.video_choices,value=controller.video_choices,label='Video contoh T7SL',
                                           info='Data contoh tetap tersedia untuk regression/pilot.')
                confirmed=gr.Checkbox(value=False,label='Saya memastikan video yang dipilih digunakan untuk analisis target lokasi ini.')
                annotate=gr.Checkbox(value=True,label='Buat annotated video (tahap CPU tambahan setelah counting)')
                gr.Markdown('## 5. Running')
                if phase123:
                    input_review=gr.State(None)
                    preview_job_button=gr.Button('Pratinjau lokasi dan seluruh input sebelum Process')
                    input_summary=gr.Textbox(label='Ringkasan input yang akan dibekukan',lines=6,interactive=False)
                    input_confirmed=gr.Checkbox(value=False,label='Saya memastikan titik calon toko dan seluruh input pada ringkasan sudah benar.')
                    gr.Markdown('Tinjau dan konfirmasi input sebelum Running. Perubahan HOME saat job berjalan tidak mengubah input job tersebut.')
                save_project=gr.Button('Save Project')
                project_status=gr.Textbox(label='Status penyimpanan project',interactive=False)
                with gr.Row():
                    check=gr.Button('Periksa kesiapan')
                    start=gr.Button('Running',variant='primary')
                status=gr.Textbox(label='Status',interactive=False)
                readiness=gr.Dataframe(headers=['Sumber','Status'],datatype=['str','str'],interactive=False,label='Kesiapan sumber')
                progress=gr.Textbox(label='Tahap aktif dan progres',lines=8,interactive=False)
            with gr.Tab('RESULT'):
                gr.Markdown('## Identity')
                result_identity=gr.Markdown()
                gr.Markdown('Jumlah kepala = estimasi penduduk (orang), bukan KK. Radius berupa zona terpisah. Tipe Jalan memakai segmen graf terdekat, bukan bukti akses toko. Kontribusi dalam STD/hari: Area = Residential + Fasum; Traffic memakai hasil setelah penyesuaian bisnis jika tersedia. Total berasal dari hasil tersimpan; kosong berarti belum lengkap.')
                gr.Markdown('## Status dan log proses')
                engines=gr.Dataframe(headers=['Engine/video','Status','Kualitas','Ringkasan'],datatype=['str']*4,interactive=False,label='Hasil masing-masing engine')
                from .ppac_view import HEADERS
                ppac=gr.State([])
                download=gr.State(None)
                retry=gr.Button('Ulangi penyimpanan hasil (tanpa inferensi)')
                gr.Markdown('## Hasil tersimpan di BigQuery\nKosongkan Job ID untuk membuka job terbaru pada kode toko ini. Peta menggunakan referensi artefak GCS pada baris Area di BQ. Membuka hasil tidak menjalankan engine.')
                saved_job=gr.Textbox(label='Job ID tersimpan (opsional)')
                refresh=gr.Button('Buka / muat ulang hasil BQ')
                saved_status=gr.Textbox(label='Status hasil BQ',interactive=False)
                gr.Markdown('## Area Coverage Result')
                map_view=gr.HTML(label='Area Coverage — Folium / Esri')
                with gr.Accordion('Rincian rekap BQ',open=False):
                    table_views=[gr.Dataframe(label=t,interactive=False,type='pandas',wrap=True,visible=t!='ppac_results') for t in ('traffic_counts','area_results','ppac_results')]
                gr.Markdown('Jumlah kepala adalah estimasi orang menurut tipe bangunan, lantai, RWI dan okupansi. Status UNVERIFIED tetap dipertahankan. Radius memakai centroid bangunan, berbeda dari proporsi zona bisnis PPAC.')
                display_views=[None]*len(DISPLAY_TABLES)
                items=list(DISPLAY_TABLES.items())
                for index in (1,3,4,2,0):
                    name,columns=items[index]
                    if index==0:gr.Markdown('## Traffic Counter Result')
                    display_views[index]=gr.Dataframe(label=name,headers=columns,interactive=False,type='pandas',wrap=True)
                gr.Markdown('## Annotated Video')
                annotated_buttons=[];annotated_names=[]
                for day_key,time_key in UPLOAD_SLOTS:
                    with gr.Row():
                        annotated_names.append(gr.Textbox(value=day_key+' / '+time_key,label='Nama video',interactive=False,scale=2))
                        annotated_buttons.append(gr.Button('Annotated belum tersedia',interactive=False,scale=1))
                gr.Markdown('## Kontribusi')
                name,columns=list(DISPLAY_TABLES.items())[5]
                display_views[5]=gr.Dataframe(label=name,headers=columns,interactive=False,type='pandas',wrap=True)
        app.load(controller.location_preview,[latitude,longitude],input_map,api_name=False,queue=False)
        save_location.click(controller.save_location,[latitude,longitude],[input_map,location_status],api_name=False,queue=False)
        def toggle_source(value):return gr.update(visible=value==VIDEO_SOURCES[0]),gr.update(visible=value==VIDEO_SOURCES[1])
        source.change(toggle_source,source,[upload_group,dataset_group],api_name=False)
        for file in slot_files+slot_refs:
            file.change(lambda:([],gr.update(choices=[],value=None),None,'Daftar upload berubah. Tekan Siapkan video dan geometri.'),None,[upload_state,selected,preview,upload_status],api_name=False,concurrency_id='engines',concurrency_limit=1)
        prepared=prepare.click(controller.prepare_slot_sources,slot_files+slot_refs,[upload_state,selected,upload_status],api_name=False,concurrency_id='engines',concurrency_limit=1)
        prepared.then(controller.preview_upload,[upload_state,selected],[preview,day,session,direction,reviewed,review_status],api_name=False)
        selected.change(controller.preview_upload,[upload_state,selected],[preview,day,session,direction,reviewed,review_status],api_name=False)
        def clicked(rows,video_id,part,evt:gr.SelectData):return controller.edit_geometry(rows,video_id,part,point=evt.index)
        preview.select(clicked,[upload_state,selected,component],[upload_state,preview,reviewed,review_status],api_name=False,concurrency_id='engines',concurrency_limit=1)
        clear.click(lambda rows,v,c:controller.edit_geometry(rows,v,c,clear=True),[upload_state,selected,component],[upload_state,preview,reviewed,review_status],api_name=False,concurrency_id='engines',concurrency_limit=1)
        save.click(controller.save_review,[upload_state,selected,day,session,direction,reviewed],[upload_state,review_status],api_name=False,concurrency_id='engines',concurrency_limit=1)
        for field in (day,session,direction):field.input(controller.invalidate_review,[upload_state,selected],[upload_state,reviewed,review_status],api_name=False)
        retried=retry.click(controller.retry_storage,job_pointer,[status,download],api_name=False,concurrency_id='engines',concurrency_limit=1)
        inputs=[mode,target,latitude,longitude,period,videos,road,days,hours,drive,swot,cut,parking,confirmed,source,upload_state,store_name,annotate]
        if phase123:
            preview_inputs=inputs+[input_review,input_confirmed,rwi]
            preview_job_button.click(controller.preview_job,preview_inputs,[input_review,input_map,input_summary,input_confirmed],api_name=False,concurrency_id='diagnostics',concurrency_limit=1)
            def invalidate_input_review():return None,False,'Input berubah. Pratinjau dan konfirmasi ulang sebelum Process.'
            for field in (mode,target,latitude,longitude,videos,road,days,hours,drive,swot,cut,parking,confirmed,source,store_name,annotate,rwi):
                field.input(invalidate_input_review,None,[input_review,input_confirmed,input_summary],api_name=False,queue=False)
            upload_state.change(invalidate_input_review,None,[input_review,input_confirmed,input_summary],api_name=False,queue=False)
            inputs=inputs+[input_review,input_confirmed,rwi]
        for coordinate in (latitude,longitude):
            coordinate.input(lambda:('','Koordinat berubah; tekan SAVE untuk memperbarui peta.'),None,[input_map,location_status],api_name=False,queue=False)
        diagnostic=gr.Button('Periksa penyebab kegagalan Area (tanpa proses ulang)')
        diagnostic_text=gr.Textbox(label='Diagnosis Area — penyebab dari log worker',lines=8,interactive=False)
        gr.Button('Lihat log proses (Area/Traffic)').click(controller.area_diagnostic,inputs,diagnostic_text,api_name=False,concurrency_id='diagnostics',concurrency_limit=1)
        diagnostic.click(controller.area_diagnostic,inputs,diagnostic_text,api_name=False,concurrency_id='diagnostics',concurrency_limit=1)
        diagnostic_file=gr.File(label='Paket diagnosis Area (ZIP)',interactive=False)
        gr.Button('Siapkan paket diagnosis Area').click(controller.export_area_diagnostics,inputs,[diagnostic_file,diagnostic_text],api_name=False,concurrency_id='diagnostics',concurrency_limit=1)
        check.click(controller.check,inputs,[status,readiness],api_name=False,concurrency_id='engines',concurrency_limit=1)
        result_outputs=[saved_status,saved_job,map_view,*table_views,*display_views,*annotated_buttons,*annotated_names,result_identity]
        def readable_process(*values):
            from .ppac_view import rows
            first=True;accepted=''
            for output in controller.process(*values):
                result=list(output);result[2]=rows(result[2]);result[4]=None
                if phase123:
                    terminal=output[5] is not None or (not first and output[0]!='Engine berjalan…')
                    if first:accepted=output[0]
                    if first or terminal:
                        live=list(controller.current_cloud_results(None,None,None))
                        live[0]='Hasil eksekusi saat ini; pembacaan GCS/BQ menyusul. '+output[0]
                        from .ppac_view import grid_from_rows
                        live[3+len(table_views)+5]=frame(grid_from_rows(result[2]),DISPLAY_TABLES['Kontribusi'])
                        live[-1]=accepted
                        result.extend(live)
                    else:result.extend(gr.skip() for _ in result_outputs)
                    first=False
                yield tuple(result)
        outputs=[status,engines,ppac,progress,download,job_pointer]+(result_outputs if phase123 else [])
        if phase123:
            from .background_runs import BackgroundRuns
            background=BackgroundRuns();controller.background_runs=background
            monitor_token=gr.State(None);monitor_revision=gr.State(0)
            monitor_timer=gr.Timer(2,active=True)
            reconnect=gr.Button('Hubungkan kembali pantauan job (tanpa proses ulang)')
            def background_events(values):
                last=None
                for event in readable_process(*values):
                    last=list(event);yield tuple(last)
                # Cloud lookup runs in this worker, not in an HTTP polling call.
                if last is not None and last[5]:
                    pointer=last[5]
                    saved=controller.current_cloud_results(pointer,pointer['context'].get('target_id'),None,last[2])
                    last[6:]=saved
                    yield tuple(last)
            def submit_job(*values):
                active=background.current()
                if active:return active,0,*[gr.skip() for _ in outputs],gr.update(interactive=True)
                from .job_input import checked_review
                try:
                    checked_review(validate(values,controller.video_choices),values[18],values[19])
                    token,event,reused=background.submit(lambda:background_events(deepcopy(values)))
                    print('JOB_SUBMIT_REATTACHED' if reused else 'JOB_SUBMIT_ACCEPTED',flush=True)
                    if reused:
                        return token,0,*[gr.skip() for _ in outputs],gr.update(interactive=True)
                    return token,1,*event,gr.update(interactive=True)
                except Exception as error:
                    from .failure_details import safe
                    return gr.skip(),gr.skip(),'INPUT_ERROR: '+safe(error),*[gr.skip() for _ in outputs[1:]],gr.update(interactive=True)
            def poll_job(token,revision):
                state=background.snapshot(token) if token==background.current(completed=True) else None
                if state and time.time()-getattr(controller,'_last_ui_poll_record',0)>=5:
                    try:
                        write(controller.base/'ui-poll-status.json',{'observed_at':datetime.now(ZoneInfo('Asia/Jakarta')).isoformat(),'monitor_hash':semantic_hash(token),'revision':state['revision'],'done':state['done'],'scope':'Last status HTTP poll received by server; not proof of browser rendering or engine progress.'})
                        controller._last_ui_poll_record=time.time()
                    except (OSError,ValueError):pass
                if not state or state['revision']==revision:
                    return revision,*[gr.skip() for _ in outputs]
                event=list(state['value'])
                if state['error']:event[0]='Pemantauan job gagal: '+state['error']+'. Periksa diagnosis; jangan langsung mengulang job.'
                return state['revision'],*event
            def reconnect_job():return background.current(completed=True),0
            def attach_active():return background.current(),0
            start.click(submit_job,inputs,[monitor_token,monitor_revision,*outputs,start],api_name=False,queue=False)
            monitor_timer.tick(poll_job,[monitor_token,monitor_revision],[monitor_revision,*outputs],api_name=False,queue=False,show_progress='hidden',trigger_mode='once')
            gr.Button('Perbarui status sekarang').click(poll_job,[monitor_token,monitor_revision],[monitor_revision,*outputs],api_name=False,queue=False,show_progress='hidden')
            reconnect.click(reconnect_job,None,[monitor_token,monitor_revision],api_name=False,queue=False)
            app.load(attach_active,None,[monitor_token,monitor_revision],api_name=False,queue=False)
            processed=None
        else:
            processed=start.click(readable_process,inputs,outputs,api_name=False,concurrency_id='engines',concurrency_limit=1)
        save_project.click(controller.save_project,inputs,project_status,api_name=False,concurrency_id='engines',concurrency_limit=1)
        refresh.click(controller.cloud_results,[target,saved_job],result_outputs,api_name=False,concurrency_id='engines',concurrency_limit=1)
        for event in (processed,retried):
            if event is None:continue
            event.then(controller.current_cloud_results,[job_pointer,target,saved_job,ppac],result_outputs,api_name=False,concurrency_id='engines',concurrency_limit=1)
    app.queue(max_size=4,default_concurrency_limit=1)
    return app,controller


def launch(base,config_root,*,input_root='/kaggle/input',share=True,default_mode='Gabungan + PPAC',runtime_factory=KaggleRuntime,**kwargs):
    app,controller=build_app(base,config_root,input_root=input_root,default_mode=default_mode,runtime_factory=runtime_factory)
    from starlette.requests import ClientDisconnect
    from .upload_transport import disconnected_upload
    app_kwargs=kwargs.pop('app_kwargs',{})
    app_kwargs['exception_handlers']={**app_kwargs.get('exception_handlers',{}),ClientDisconnect:disconnected_upload}
    _,local_url,share_url=app.launch(app_kwargs=app_kwargs,share=share,server_name='0.0.0.0',inline=False,show_error=False,
                                   allowed_paths=[str(controller.exports)],max_file_size='1024mb',prevent_thread_lock=True,**kwargs)
    from .map_view import install_map_route
    install_map_route(app.app,controller.maps)
    from fastapi import Body,HTTPException
    @app.app.post('/remote-check')
    def remote_check(payload:dict=Body(...)):
        nonce=payload.get('nonce')
        if not isinstance(nonce,str) or not re.fullmatch('[a-f0-9]{32}',nonce):raise HTTPException(status_code=400,detail='Invalid probe')
        return {'nonce':nonce,'engine_started':False}
    if share and not share_url:
        app.close();raise RuntimeError('URL publik Gradio gagal dibuat. Periksa Internet/tunnel pada sesi Kaggle; engine belum dijalankan.')
    return app,share_url or local_url
