"""Gradio input/output adapter. Algorithms and credentials stay in the runtime."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import json
import math
from pathlib import Path
import re
import time
from uuid import uuid4
from zoneinfo import ZoneInfo
from ..artifacts import read, write, semantic_hash
from .contracts import GateError
from .kaggle_runtime import KaggleRuntime

MODES={'Area Coverage':'area','Traffic Counter':'traffic','Gabungan + PPAC':'workflow'}
VIDEO_SOURCES=('Upload video','Dataset T7SL (contoh)')
ROADS=['highway','mainstreet','street','substreet']
INPUT_NAMES=('mode','target_id','latitude','longitude','period','video_ids','road','days','hours',
             'drive_thru','swot','cut','parking','confirmed')


def validate(values,video_choices):
    x=dict(zip(INPUT_NAMES,values[:len(INPUT_NAMES)]))
    x['video_source']=values[14] if len(values)>14 else VIDEO_SOURCES[1]
    x['uploads']=values[15] if len(values)>15 else []
    if x['video_source'] not in VIDEO_SOURCES:raise ValueError('Pilih sumber video yang tersedia.')
    if x['mode'] not in MODES:raise ValueError('Pilih mode yang tersedia.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',str(x['target_id'])):
        raise ValueError('Kode toko: 1–32 huruf, angka, garis bawah, atau tanda minus.')
    for field,low,high in (('latitude',-80,84),('longitude',-180,180)):
        if not isinstance(x[field],(int,float)) or not math.isfinite(x[field]) or not low<=x[field]<=high:
            raise ValueError('Koordinat lokasi tidak valid.')
    try:date.fromisoformat(x['period'])
    except (ValueError,TypeError):raise ValueError('Tanggal analisis harus YYYY-MM-DD.') from None
    mode=MODES[x['mode']]
    selected=[] if mode=='area' else (x['video_ids'] or [])
    if mode!='area' and x['video_source']==VIDEO_SOURCES[0]:
        if not x['uploads'] or not all(r.get('reviewed') is True for r in x['uploads']):
            raise ValueError('Upload video, lalu tinjau dan simpan geometri setiap video.')
        selected=[r['id'] for r in x['uploads']]
    if mode!='area' and x['video_source']==VIDEO_SOURCES[1] and (not selected or len(selected)!=len(set(selected)) or not set(selected)<=set(video_choices)):
        raise ValueError('Pilih minimal satu video T7SL yang tersedia.')
    if mode=='workflow':
        if not x['confirmed']:raise ValueError('Konfirmasi kesesuaian video dengan target lokasi untuk PPAC.')
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
    return {**x,'mode':mode,'parameters':parameters,'video_ids':selected}


def engine_rows(result):
    rows=[]
    for item in result.get('engines',[]):
        brief=item.get('summary') or {}
        rows.append([item['id'],item.get('execution_status'),item.get('quality',''),
                     json.dumps(brief,ensure_ascii=False) if brief else item.get('message',item.get('code',''))])
    return rows


class Controller:
    def __init__(self,base,config_root,*,input_root='/kaggle/input',runtime_factory=KaggleRuntime):
        self.base=Path(base).resolve();self.config_root=Path(config_root).resolve()
        self.input_root=input_root;self.runtime_factory=runtime_factory
        self.video_choices=[Path(v['filename']).stem for v in read(self.config_root/'experiment.json')['videos']]
        from .cloud_schema import CloudDestination
        self.destination=CloudDestination.configured()
        self.upload_root=self.base/'uploads';self.upload_root.mkdir(parents=True,exist_ok=True)
        self.exports=self.base/'exports';self.exports.mkdir(parents=True,exist_ok=True)

    def runtime(self,x):
        # Stable target-specific workspace enables validated reuse across business changes.
        key=semantic_hash({k:x[k] for k in ('target_id','latitude','longitude','period')})
        return self.runtime_factory(self.base/'targets'/key,self.config_root,x['latitude'],x['longitude'],
                                    target_id=x['target_id'],period_id=x['period'],performance={'reuse':True},
                                    publication=self.destination,upload_root=self.upload_root)

    def check(self,*values):
        try:
            x=validate(values,self.video_choices);runtime=self.runtime(x)
            state=runtime.probe()
            if x['mode']=='area':inventory=[]
            elif x['video_source']==VIDEO_SOURCES[0]:
                from .uploads import inventory as upload_inventory
                inventory=upload_inventory(x['uploads'],self.upload_root)
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
        if not pointer:return 'Belum ada job yang dapat disimpan ulang.',None
        folder=Path(pointer['output']).resolve()
        if not folder.is_relative_to(self.base):return 'Lokasi job tidak valid.',None
        runtime=self.runtime(pointer['context'])
        status=runtime.retry_publication(folder)
        export={'schema_version':'publication_retry_v1','publication':status,'target':{k:pointer['context'][k] for k in ('target_id','latitude','longitude','period')}}
        path=self.exports/(uuid4().hex+'.json');write(path,export)
        return 'Penyimpanan: '+status['status']+' '+str(status.get('code','')),str(path)

    def progress_text(self,runtime,started):
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

    def process(self,*values):
        try:x=validate(values,self.video_choices)
        except ValueError as exc:
            yield str(exc),[],{},'',None,None;return
        started=time.time()
        try:runtime=self.runtime(x)
        except Exception as exc:
            yield 'Workspace gagal disiapkan ('+type(exc).__name__+').',[],{},'',None,None;return
        yield 'Proses dimulai. Biarkan notebook tetap berjalan.',[],{},'Memeriksa sumber dan menyiapkan runtime.',None,None
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                options={'uploaded_videos':x['uploads']} if x['video_source']==VIDEO_SOURCES[0] and x['mode']!='area' else {}
                future=pool.submit(runtime.execute,x['mode'],x['parameters'],input_root=self.input_root,
                                   target_confirmed=x['confirmed'],video_ids=x['video_ids'],**options)
                while not future.done():
                    yield 'Engine berjalan…',[],{},self.progress_text(runtime,started),None,None
                    time.sleep(1)
                result=future.result()
            ppac=result['ppac']
            export={'schema_version':'gradio_summary_v1','target':{k:x[k] for k in ('target_id','latitude','longitude','period')},
                    'mode':x['mode'],'video_ids':x['video_ids'],'parameters':x['parameters'],
                    'engines':[{k:v for k,v in row.items() if k!='result_ref'} for row in result['engines']],
                    'ppac':ppac,'publication':result.get('publication',{'status':'NOT_REQUESTED'})}
            path=self.exports/(uuid4().hex+'.json');write(path,export)
            failed=sum(row.get('execution_status')!='SUCCEEDED' for row in result['engines'])
            publication=result.get('publication',{'status':'NOT_REQUESTED'})
            status=f"Selesai. Engine/video gagal: {failed}. PPAC: {ppac['execution_status']}. Penyimpanan: {publication['status']} {publication.get('code','')}."
            yield status,engine_rows(result),ppac,self.progress_text(runtime,started),str(path),{'output':result.get('output',''),'context':x}
        except GateError as exc:yield str(exc),[],{},self.progress_text(runtime,started),None,None
        except Exception as exc:
            yield 'Proses gagal ('+type(exc).__name__+'). Periksa log notebook; hasil engine tersimpan tetap dipertahankan.',[],{},self.progress_text(runtime,started),None,None


def build_app(base,config_root,*,input_root='/kaggle/input',runtime_factory=KaggleRuntime):
    import gradio as gr
    controller=Controller(base,config_root,input_root=input_root,runtime_factory=runtime_factory)
    with gr.Blocks(title='Area · Traffic · PPAC') as app:
        gr.Markdown('# Area Coverage · Traffic Counter · PPAC\nMasukkan input, periksa kesiapan, lalu mulai proses. Upload video Anda, tinjau geometri setiap video, lalu jalankan engine. Dataset T7SL tetap tersedia sebagai contoh.')
        with gr.Row():
            mode=gr.Dropdown(list(MODES),value='Gabungan + PPAC',label='Proses')
            target=gr.Textbox(value='T7SL',label='Kode toko')
            period=gr.Textbox(value=datetime.now(ZoneInfo('Asia/Jakarta')).date().isoformat(),label='Tanggal analisis (YYYY-MM-DD)')
        with gr.Row():
            latitude=gr.Number(value=-0.8994976613947719,label='Latitude')
            longitude=gr.Number(value=131.3221639428227,label='Longitude')
        source=gr.Radio(VIDEO_SOURCES,value=VIDEO_SOURCES[0],label='Sumber video')
        upload_state=gr.State([]);job_pointer=gr.State(None)
        with gr.Group() as upload_group:
            files=gr.File(file_count='multiple',file_types=['video'],type='filepath',label='Upload video asli (maks. 1 GiB/file, 2 GiB/batch)')
            prepare=gr.Button('Siapkan video dan geometri')
            upload_status=gr.Textbox(label='Kesiapan video',interactive=False)
            selected=gr.Dropdown(choices=[],label='Video yang ditinjau')
            preview=gr.Image(type='filepath',interactive=False,label='Frame pertama: garis merah, polygon A biru, polygon B kuning')
            with gr.Row():
                day=gr.Dropdown(['weekday','weekend'],label='Kelompok hari')
                session=gr.Dropdown(['pagi','siang','sore','malam','tengah_malam','dini_hari','subuh'],label='Sesi perekaman')
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
        gr.Markdown('Hasil job disimpan ke **gs://aretfak-location-intelligence** dan **locdeproject.location_intelligence**. Tabel perlu disiapkan sekali; kegagalan penyimpanan tidak menghapus hasil lokal.')
        with gr.Accordion('Input bisnis PPAC',open=True):
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
        confirmed=gr.Checkbox(value=False,label='Saya memastikan video yang dipilih digunakan untuk analisis target lokasi ini.')
        with gr.Row():
            check=gr.Button('Periksa kesiapan')
            start=gr.Button('Mulai proses',variant='primary')
        status=gr.Textbox(label='Status',interactive=False)
        readiness=gr.Dataframe(headers=['Sumber','Status'],datatype=['str','str'],interactive=False,label='Kesiapan sumber')
        progress=gr.Textbox(label='Tahap aktif dan progres',lines=8,interactive=False)
        engines=gr.Dataframe(headers=['Engine/video','Status','Kualitas','Ringkasan'],datatype=['str']*4,interactive=False,label='Hasil masing-masing engine')
        ppac=gr.JSON(label='Hasil PPAC / alasan menunggu input')
        download=gr.File(label='Unduh ringkasan JSON',interactive=False)
        retry=gr.Button('Ulangi penyimpanan hasil (tanpa inferensi)')
        def toggle_source(value):return gr.update(visible=value==VIDEO_SOURCES[0]),gr.update(visible=value==VIDEO_SOURCES[1])
        source.change(toggle_source,source,[upload_group,dataset_group],api_name=False)
        files.change(lambda:([],gr.update(choices=[],value=None),None,'Daftar upload berubah. Tekan Siapkan video dan geometri.'),None,[upload_state,selected,preview,upload_status],api_name=False,concurrency_id='engines',concurrency_limit=1)
        prepared=prepare.click(controller.prepare_files,files,[upload_state,selected,upload_status],api_name=False,concurrency_id='engines',concurrency_limit=1)
        prepared.then(controller.preview_upload,[upload_state,selected],[preview,day,session,direction,reviewed,review_status],api_name=False)
        selected.change(controller.preview_upload,[upload_state,selected],[preview,day,session,direction,reviewed,review_status],api_name=False)
        def clicked(rows,video_id,part,evt:gr.SelectData):return controller.edit_geometry(rows,video_id,part,point=evt.index)
        preview.select(clicked,[upload_state,selected,component],[upload_state,preview,reviewed,review_status],api_name=False,concurrency_id='engines',concurrency_limit=1)
        clear.click(lambda rows,v,c:controller.edit_geometry(rows,v,c,clear=True),[upload_state,selected,component],[upload_state,preview,reviewed,review_status],api_name=False,concurrency_id='engines',concurrency_limit=1)
        save.click(controller.save_review,[upload_state,selected,day,session,direction,reviewed],[upload_state,review_status],api_name=False,concurrency_id='engines',concurrency_limit=1)
        for field in (day,session,direction):field.input(controller.invalidate_review,[upload_state,selected],[upload_state,reviewed,review_status],api_name=False)
        retry.click(controller.retry_storage,job_pointer,[status,download],api_name=False,concurrency_id='engines',concurrency_limit=1)
        inputs=[mode,target,latitude,longitude,period,videos,road,days,hours,drive,swot,cut,parking,confirmed,source,upload_state]
        check.click(controller.check,inputs,[status,readiness],api_name=False,concurrency_id='engines',concurrency_limit=1)
        start.click(controller.process,inputs,[status,engines,ppac,progress,download,job_pointer],api_name=False,concurrency_id='engines',concurrency_limit=1)
    app.queue(max_size=4,default_concurrency_limit=1)
    return app,controller


def launch(base,config_root,*,input_root='/kaggle/input',share=True,**kwargs):
    app,controller=build_app(base,config_root,input_root=input_root)
    _,local_url,share_url=app.launch(share=share,server_name='0.0.0.0',inline=False,show_error=False,
                                   allowed_paths=[str(controller.exports)],max_file_size='1024mb',prevent_thread_lock=True,**kwargs)
    if share and not share_url:
        app.close();raise RuntimeError('URL publik Gradio gagal dibuat. Periksa Internet/tunnel pada sesi Kaggle; engine belum dijalankan.')
    return app,share_url or local_url
