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
ROADS=['highway','mainstreet','street','substreet']
INPUT_NAMES=('mode','target_id','latitude','longitude','period','video_ids','road','days','hours',
             'drive_thru','swot','cut','parking','confirmed')


def validate(values,video_choices):
    x=dict(zip(INPUT_NAMES,values))
    if x['mode'] not in MODES:raise ValueError('Pilih mode yang tersedia.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',str(x['target_id'])):
        raise ValueError('Kode toko: 1–32 huruf, angka, garis bawah, atau tanda minus.')
    for field,low,high in (('latitude',-80,84),('longitude',-180,180)):
        if not isinstance(x[field],(int,float)) or not math.isfinite(x[field]) or not low<=x[field]<=high:
            raise ValueError('Koordinat lokasi tidak valid.')
    try:date.fromisoformat(x['period'])
    except (ValueError,TypeError):raise ValueError('Tanggal analisis harus YYYY-MM-DD.') from None
    mode=MODES[x['mode']]
    selected=x['video_ids'] or []
    if mode!='area' and (not selected or len(selected)!=len(set(selected)) or not set(selected)<=set(video_choices)):
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
        self.exports=self.base/'exports';self.exports.mkdir(parents=True,exist_ok=True)

    def runtime(self,x):
        # Stable target-specific workspace enables validated reuse across business changes.
        key=semantic_hash({k:x[k] for k in ('target_id','latitude','longitude','period')})
        return self.runtime_factory(self.base/'targets'/key,self.config_root,x['latitude'],x['longitude'],
                                    target_id=x['target_id'],period_id=x['period'],performance={'reuse':True})

    def check(self,*values):
        try:
            x=validate(values,self.video_choices);runtime=self.runtime(x)
            state=runtime.probe();inventory=runtime.video_inventory(self.input_root)
            objects=state['gcs'].get('objects',{})
            rows=[[name,item['status']] for name,item in objects.items()]
            rows += [[v['id'],v['status']] for v in inventory if v['id'] in x['video_ids']]
            return 'Kesiapan diperiksa. Engine belum berjalan.',rows
        except (ValueError,GateError) as exc:return str(exc),[]
        except Exception as exc:return 'Pemeriksaan gagal ('+type(exc).__name__+'). Periksa Internet, Secret LocatioIntelligent, dan izin GCS.',[]

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
                if obj.get('completed') is not None:text+=f" | {obj['completed']}/{obj.get('total','?')} frame"
                if obj.get('fps_actual') is not None:text+=f" | {obj['fps_actual']:.1f} FPS"
                if obj.get('eta_seconds') is not None:text+=f" | ETA tahap {obj['eta_seconds']:.0f} detik"
                lines.append(text)
            except (OSError,ValueError,KeyError,TypeError):continue
        return '\n'.join(lines[-24:]) or 'Menyiapkan sumber/runtime; rincian setup tersedia di log notebook.'

    def process(self,*values):
        try:x=validate(values,self.video_choices)
        except ValueError as exc:
            yield str(exc),[],{},'',None;return
        runtime=self.runtime(x);started=time.time()
        yield 'Proses dimulai. Biarkan notebook tetap berjalan.',[],{},'Memeriksa sumber dan menyiapkan runtime.',None
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(runtime.execute,x['mode'],x['parameters'],input_root=self.input_root,
                                   target_confirmed=x['confirmed'],video_ids=x['video_ids'])
                while not future.done():
                    yield 'Engine berjalan…',[],{},self.progress_text(runtime,started),None
                    time.sleep(1)
                result=future.result()
            ppac=result['ppac']
            export={'schema_version':'gradio_summary_v1','target':{k:x[k] for k in ('target_id','latitude','longitude','period')},
                    'mode':x['mode'],'video_ids':x['video_ids'],'parameters':x['parameters'],
                    'engines':[{k:v for k,v in row.items() if k!='result_ref'} for row in result['engines']],
                    'ppac':ppac}
            path=self.exports/(uuid4().hex+'.json');write(path,export)
            failed=sum(row.get('execution_status')!='SUCCEEDED' for row in result['engines'])
            status=f"Selesai. Engine/video gagal: {failed}. PPAC: {ppac['execution_status']}."
            yield status,engine_rows(result),ppac,self.progress_text(runtime,started),str(path)
        except GateError as exc:yield str(exc),[],{},self.progress_text(runtime,started),None
        except Exception as exc:
            yield 'Proses gagal ('+type(exc).__name__+'). Periksa log notebook; hasil engine tersimpan tetap dipertahankan.',[],{},self.progress_text(runtime,started),None


def build_app(base,config_root,*,input_root='/kaggle/input',runtime_factory=KaggleRuntime):
    import gradio as gr
    controller=Controller(base,config_root,input_root=input_root,runtime_factory=runtime_factory)
    with gr.Blocks(title='Area · Traffic · PPAC') as app:
        gr.Markdown('# Area Coverage · Traffic Counter · PPAC\nMasukkan input, periksa kesiapan, lalu mulai proses. Video berasal dari dataset T7SL yang terpasang di notebook.')
        with gr.Row():
            mode=gr.Dropdown(list(MODES),value='Gabungan + PPAC',label='Proses')
            target=gr.Textbox(value='T7SL',label='Kode toko')
            period=gr.Textbox(value=datetime.now(ZoneInfo('Asia/Jakarta')).date().isoformat(),label='Tanggal analisis (YYYY-MM-DD)')
        with gr.Row():
            latitude=gr.Number(value=-0.8994976613947719,label='Latitude')
            longitude=gr.Number(value=131.3221639428227,label='Longitude')
        videos=gr.CheckboxGroup(controller.video_choices,value=controller.video_choices,label='Video T7SL yang diproses',
                               info='Traffic dapat memakai satu video. PPAC memerlukan slot observasi yang lengkap.')
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
        inputs=[mode,target,latitude,longitude,period,videos,road,days,hours,drive,swot,cut,parking,confirmed]
        check.click(controller.check,inputs,[status,readiness],api_name=False,concurrency_id='engines',concurrency_limit=1)
        start.click(controller.process,inputs,[status,engines,ppac,progress,download],api_name=False,concurrency_id='engines',concurrency_limit=1)
    app.queue(max_size=4,default_concurrency_limit=1)
    return app,controller


def launch(base,config_root,*,input_root='/kaggle/input',share=True,**kwargs):
    app,controller=build_app(base,config_root,input_root=input_root)
    _,local_url,share_url=app.launch(share=share,server_name='0.0.0.0',inline=False,show_error=False,
                                   allowed_paths=[str(controller.exports)],prevent_thread_lock=True,**kwargs)
    if share and not share_url:
        app.close();raise RuntimeError('URL publik Gradio gagal dibuat. Periksa Internet/tunnel pada sesi Kaggle; engine belum dijalankan.')
    return app,share_url or local_url
