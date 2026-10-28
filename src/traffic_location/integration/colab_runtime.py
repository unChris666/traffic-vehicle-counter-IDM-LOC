"""Colab adapter: prebuilt isolated runtime, ADC, and target-bound Area reopen gate.

No installation, authentication prompt or GPU work occurs on import.
"""
from pathlib import Path
import json
import math
import os
import re
from .. import __version__
from ..artifacts import read,write,semantic_hash
from .contracts import need,GateError
from .kaggle_runtime import KaggleRuntime,SCIENTIFIC


def require_l4(rows):
    need(bool(rows),'COLAB_GPU_MISSING','Pilih Runtime → Change runtime type → L4 GPU, lalu reconnect.')
    need(all(re.search(r'\bL4\b',r.get('name','')) for r in rows),'COLAB_GPU_NOT_L4',
         'GPU yang dialokasikan bukan L4. Pilih L4 pada pengaturan Colab; kode tidak dapat mengubah alokasi GPU.')
    return rows


def observe_gpu():
    import csv,io,subprocess
    try:
        output=subprocess.check_output(['nvidia-smi','--query-gpu=name,uuid,memory.total,driver_version','--format=csv,noheader,nounits'],text=True,timeout=30)
    except (OSError,subprocess.SubprocessError):raise GateError('COLAB_GPU_MISSING','GPU NVIDIA belum tersedia pada runtime Colab.') from None
    rows=[dict(zip(('name','uuid','memory_mib','driver'),(v.strip() for v in r))) for r in csv.reader(io.StringIO(output)) if len(r)==4]
    return require_l4(rows)


def gate_identity(context):
    keys=('target_id','period_id','latitude','longitude')
    need(all(context.get(k) is not None for k in keys),'AREA_CONTEXT_MISSING','Identitas/koordinat Area belum lengkap.')
    try:latitude,longitude=float(context['latitude']),float(context['longitude'])
    except (TypeError,ValueError):raise GateError('AREA_CONTEXT_INVALID','Koordinat Area bukan angka valid.') from None
    need(math.isfinite(latitude) and math.isfinite(longitude) and -80<=latitude<=84 and -180<=longitude<=180,
         'AREA_CONTEXT_INVALID','Koordinat Area tidak valid.')
    return {'target_id':context['target_id'],'period_id':context['period_id'],'latitude':latitude,'longitude':longitude,'package_version':__version__}


class ColabRuntime(KaggleRuntime):
    def gate_path(self,context):
        folder=Path(os.environ.get('LI_COLAB_GATE_ROOT','/content/location-intelligence/area-verifications'))
        return folder/(semantic_hash(gate_identity(context))+'.json')

    def run_area(self,root):
        gpu=observe_gpu()
        try:return super().run_area(root)
        finally:
            path=Path(root)/'area-trace.json'
            try:
                if path.is_file():
                    trace=read(path);trace.update(runtime_platform='colab',gpu=gpu);write(path,trace)
            except (OSError,ValueError):pass  # Missing proof keeps the next stage blocked; preserve engine outcome.

    def note_reopened_area(self,result):
        if os.environ.get('LI_COMPONENT_FLOW')=='1':
            return 'Mode independen aktif: Traffic tidak memerlukan job Area sebelumnya. STD total hanya untuk PPAC gabungan dengan input lengkap.'
        job=result.get('job_context',{});areas=result.get('area_results',[])
        display=result.get('display',{});trace=result.get('area_trace',{})
        verified=(trace.get('runtime_platform')=='colab' and trace.get('execution_status')=='SUCCEEDED'
                  and trace.get('package_version')==__version__
                  and bool(trace.get('gpu')) and all(re.search(r'\bL4\b',r.get('name','')) for r in trace.get('gpu',[]))
                  and job.get('package_version')==__version__ and result.get('manifest_job_id')==result.get('job_id')
                  and bool(result.get('map_html')) and len(areas)==1
                  and areas[0].get('execution_status')=='SUCCEEDED'
                  and areas[0].get('job_id')==result.get('job_id')
                  and areas[0].get('target_id')==job.get('target_id')
                  and trace.get('result',{}).get('result_version')==areas[0].get('result_version')
                  and display.get('schema_version')=='area_display_v1'
                  and all(isinstance(display.get(k),list) for k in ('area','competitors','indomaret')))
        if not verified:return 'Traffic/PPAC masih menunggu Area sukses serta tabel/peta job yang sama dibuka kembali dari GCS/BQ.'
        try:
            identity=gate_identity(job)
            need(gate_identity(trace.get('context',{}))==identity,'AREA_CONTEXT_MISMATCH','Konteks trace Area berbeda.')
        except GateError:return 'Konteks Area belum lengkap; Traffic/PPAC belum dibuka.'
        write(self.gate_path(job),{'schema_version':'colab_area_reopened_v1','identity':identity,
                                 'job_id':result['job_id'],'result_version':areas[0].get('result_version')})
        return 'Area tersimpan sudah dibaca kembali dan diverifikasi; Traffic/PPAC tersedia untuk target, periode, koordinat dan versi ini. Tinjau peta di browser.'

    def execute(self,mode,parameters,**kwargs):
        need(os.environ.get('LI_RUNTIME_MODE')=='bundled' and os.environ.get('LI_AUTH_MODE')=='adc',
             'COLAB_STARTUP_REQUIRED','Jalankan cell setup dan autentikasi Colab dahulu; runtime tidak memasang dependency saat job berjalan.')
        if mode!='area' and os.environ.get('LI_COMPONENT_FLOW')!='1':
            context={'target_id':self.target_id,'period_id':self.period_id,'latitude':self.latitude,'longitude':self.longitude}
            proof=self.gate_path(context)
            need(proof.is_file() and not proof.is_symlink(),'AREA_REOPEN_REQUIRED',
                 'Jalankan Area Coverage dahulu, lalu buka hasil BQ dan peta GCS untuk target/periode/koordinat ini.')
            saved=read(proof)
            need(saved.get('schema_version')=='colab_area_reopened_v1' and saved.get('identity')==gate_identity(context),
                 'AREA_REOPEN_REQUIRED','Bukti Area tidak cocok dengan konteks aplikasi saat ini.')
        return super().execute(mode,parameters,**kwargs)


def preflight(base,config_root):
    """Owner-run read checks. Does not create tables, upload files, or run engines."""
    from google.cloud import bigquery
    from .cloud_schema import CloudDestination
    from ..location.area._kernel.location_intelligent_map_pilot import resolve_bq_fields
    gpu=observe_gpu()
    runtime=ColabRuntime(Path(base)/'preflight',config_root,0.,0.,publication=CloudDestination.configured())
    runtime.connect();publisher=runtime.cloud_publisher()
    destination=publisher.check()
    required=['storage.objects.get','storage.objects.create']
    granted=publisher.storage.bucket(runtime.publication.bucket).test_iam_permissions(required,timeout=30)
    need(set(required)<=set(granted),'OUTPUT_GCS_PERMISSION_MISSING','Bucket hasil memerlukan izin baca dan create object.')
    for name in ('job_runs','traffic_videos','traffic_counts','area_results','ppac_results'):
        table=runtime.publication.dataset+'.'+name
        granted_bq=publisher.bq.test_iam_permissions(table,['bigquery.tables.getData','bigquery.tables.updateData'],timeout=30)
        need({'bigquery.tables.getData','bigquery.tables.updateData'}<=set(granted_bq.get('permissions',[])),
             'OUTPUT_BQ_PERMISSION_MISSING','Izin baca/tulis belum tersedia pada '+table)
    # The query exercises jobs.create in the output dataset's actual location.
    publisher.bq.query('SELECT 1 AS access_probe',location=publisher.location,
        job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1024)).result(timeout=60)
    from .kaggle_runtime import area_config
    tables=area_config(0.,0.)['CONFIG']['bq_tables'];inputs={}
    for kind,name in tables.items():
        table=publisher.bq.get_table(name,timeout=30)
        inputs[kind]={'table':name,'schema':resolve_bq_fields(table,kind),'status':'METADATA_READABLE'}
    source=runtime.probe()
    pbf=source['gcs']['objects']['national_pbf']
    need(pbf['status']=='READY','AREA_SOURCE_NOT_READY','PBF nasional tidak siap: '+str(pbf))
    report={'schema_version':'colab_preflight_v1','gpu':gpu,'destination':destination,
            'source_tables':inputs,'objects':source['gcs']['objects'],
            'scope':'Read/metadata/query checks only. Actual output writes and reopen are verified by the Area user test.'}
    write(Path(base)/'colab-preflight.json',report)
    return report


def verify():
    """Actual import/CUDA smoke in the isolated interpreter; no inference."""
    import importlib.metadata,subprocess,sys
    from .container_runtime import verify_runtime
    gpu=observe_gpu()
    subprocess.run([sys.executable,'-m','pip','check'],check=True,timeout=120)
    area=verify_runtime('area',require_gpu=True);traffic=verify_runtime('traffic',require_gpu=True)
    core_probe="""import json,math
from osgeo import gdal,osr
import pyproj,platform
source,target=osr.SpatialReference(),osr.SpatialReference()
assert source.ImportFromEPSG(4326)==target.ImportFromEPSG(32752)==0
source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
x,y,z=osr.CoordinateTransformation(source,target).TransformPoint(131.3221639428227,-.8994976613947719)
assert math.isfinite(x) and math.isfinite(y) and 100000<x<900000 and 9000000<y<10000000
print(json.dumps({'python':platform.python_version(),'gdal':gdal.VersionInfo('RELEASE_NAME'),'pyproj':pyproj.__version__,'utm_sorong':[x,y]}))
"""
    core=json.loads(subprocess.check_output([area['core_python'],'-c',core_probe],text=True,timeout=60))
    import cupy as cp
    kernel=cp.RawKernel('extern "C" __global__ void probe(float* x){x[0]=7.0f;}','probe')
    x=cp.zeros(1,dtype=cp.float32);kernel((1,),(1,),(x,));need(float(x.get()[0])==7.,'CUDA_KERNEL_FAILED','CuPy kernel gagal pada driver Colab.')
    cp.get_default_memory_pool().free_all_blocks()
    import onnx,onnxruntime as ort,numpy as np,torch
    from onnx import helper,TensorProto
    model=helper.make_model(helper.make_graph([helper.make_node('MatMul',['a','b'],['c'])],'cuda-smoke',
        [helper.make_tensor_value_info(n,TensorProto.FLOAT,[2,2]) for n in ('a','b')],
        [helper.make_tensor_value_info('c',TensorProto.FLOAT,[2,2])]),opset_imports=[helper.make_opsetid('',13)])
    model.ir_version=9
    options=ort.SessionOptions();options.add_session_config_entry('session.disable_cpu_ep_fallback','1')
    session=ort.InferenceSession(model.SerializeToString(),sess_options=options,providers=['CUDAExecutionProvider'])
    need(session.get_providers()[0]=='CUDAExecutionProvider','ORT_CUDA_REQUIRED','ONNX Runtime gagal menggunakan CUDA.')
    value=session.run(None,{'a':np.eye(2,dtype=np.float32),'b':np.ones((2,2),dtype=np.float32)})[0]
    need(np.array_equal(value,np.ones((2,2),dtype=np.float32)),'ORT_CUDA_FAILED','Hasil CUDA smoke tidak cocok.')
    return {'schema_version':'colab_runtime_verified_v1','gpu':gpu,'area':area,'traffic':traffic,
            'python':sys.version,'torch_cuda':torch.version.cuda,'onnx_providers':session.get_providers(),
            'packages':{k:importlib.metadata.version(k) for k in SCIENTIFIC},'core':core,'scope':'Import and synthetic CUDA smoke; not engine inference or accuracy.'}


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['verify','preflight','serve']);p.add_argument('--base',required=True);p.add_argument('--config-root',required=True)
    args=p.parse_args();base=Path(args.base)
    try:_main(args,base)
    except Exception as exc:
        from .failure_details import safe
        code=getattr(exc,'code',None)
        if not isinstance(code,(str,int)):code=type(exc).__name__
        write(base/'colab-startup-failure.json',{'stage':args.operation,'code':code,'message':safe(exc)})
        raise RuntimeError(safe(exc)) from None


def _main(args,base):
    if args.operation=='verify':
        report=verify();write(base/'colab-runtime-verified.json',report);print(json.dumps(report));return
    if args.operation=='preflight':print(json.dumps(preflight(base,args.config_root)));return
    need((base/'colab-runtime-verified.json').is_file() and (base/'colab-preflight.json').is_file(),
         'COLAB_PREFLIGHT_REQUIRED','Jalankan cell pemeriksaan runtime dan akses cloud terlebih dahulu.')
    # Recheck imports/GPU and permissions so stale marker files cannot bypass readiness.
    verify();preflight(base,args.config_root)
    from .gradio_app import launch
    app,url=launch(base/'system',args.config_root,input_root='/content/videos',share=True,
                   default_mode='Area Coverage',runtime_factory=ColabRuntime)
    print('GRADIO_PUBLIC_URL='+url,flush=True)
    try:app.block_thread()
    finally:
        app.close()
        import psutil
        children=psutil.Process().children(recursive=True)
        for child in children:
            try:child.terminate()
            except psutil.NoSuchProcess:pass
        _,alive=psutil.wait_procs(children,timeout=5)
        for child in alive:
            try:child.kill()
            except psutil.NoSuchProcess:pass

if __name__=='__main__':main()
