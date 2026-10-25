"""Build a new readable GPU-hybrid notebook; never overwrite CPU baseline."""
from pathlib import Path
import ast,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'notebooks/area_coverage_market_cpu_2km.ipynb'
DEST=ROOT/'notebooks/area_coverage_market_gpu_2km.ipynb'
GPU_FILES=['location_intelligent_gpu.py','location_intelligent_gpu_worker.py','location_intelligent_gpu_runtime.py',
 'location_intelligent_gpu_geometry.py','location_intelligent_gpu_weighted.py','location_intelligent_gpu_connectors.py','location_intelligent_gpu_validation.py','location_intelligent_gpu_diagnostics.py']


def build():
    baseline_file=ROOT/'docs/AREA_COVERAGE_GPU_BASELINE.json'
    if baseline_file.exists() and json.loads(baseline_file.read_text())['cpu_notebook_sha256']!=hashlib.sha256(SOURCE.read_bytes()).hexdigest():
        raise ValueError('GPU_BASELINE_CHANGED_NEEDS_EXPLICIT_REBASE')
    notebook=json.loads(SOURCE.read_text());baseline={}
    for cell in notebook['cells']:
        text=''.join(cell['source'])
        if text.startswith('%%writefile '):
            header,body=text.split('\n',1);baseline[header.rsplit('/',1)[1]]=hashlib.sha256(body.encode()).hexdigest()
        text=text.replace('/kaggle/working/area_coverage_market_source','/kaggle/working/area_coverage_gpu_source')
        text=text.replace("os.environ['CUDA_VISIBLE_DEVICES']='-1'", "GPU_DEVICE=0 # local CUDA device; Area Coverage and Traffic Counter execute sequentially")
        text=text.replace('/kaggle/working/results/area_coverage_market/notebook_readiness.json','/kaggle/working/results/area_coverage_gpu/notebook_readiness.json')
        text=text.replace("Path('/kaggle/working/results/area_coverage_market')", "Path('/kaggle/working/results/area_coverage_gpu')")
        cell['source']=text.splitlines(True)
    notebook['cells'][0]['source']=('''# Area Coverage — GPU hybrid, business baseline unchanged

Notebook baru; notebook CPU tetap utuh. GPU menghitung kandidat jarak FP64, intersection batch dan shortest-path
berbobot FP64. CPU mempertahankan preprocessing, konstruksi endpoint skalar,
Huff dan fallback kasus ambigu yang diaudit.
Percepatan belum diukur. Mode VALIDATE juga menjalankan CPU reference, sehingga
run validasi pertama memang menambah biaya. Output/handoff diblok jika tidak setara.
Tidak ada klaim accuracy/akses legal.

Sebelum Run All: pilih accelerator GPU, aktifkan Internet, lalu aktifkan Kaggle
Secret `LocatioIntelligent` pada notebook ini. Secret tidak disalin dari notebook
lain secara otomatis. Jangan menaruh nilai key di cell.

Jangan menjalankan Traffic Counter bersamaan. Area Coverage menghasilkan peta,
tabel, CSV/JSON/ZIP dahulu. Cell terakhir hanya menerbitkan handoff setelah output
berhasil diverifikasi dan pool GPU dibebaskan; tidak menjalankan Traffic Counter.
''').splitlines(True)
    dependencies=''.join(notebook['cells'][3]['source'])
    marker="  finish_notebook_stage('dependencies','SUCCEEDED')"
    install='''  # GPU is mandatory. No CPU-only fallback or NumPy replacement.
  try:
   import cupy
  except ImportError:
   subprocess.run([sys.executable,'-m','pip','install','--quiet','--no-deps',
                   'cupy-cuda12x==13.6.0','fastrlock==0.8.3'],check=True)
  sys.path.insert(0,str(SOURCE_ROOT/'notebooks'))
  from location_intelligent_gpu import gpu_preflight
  GPU_PREFLIGHT=gpu_preflight(GPU_DEVICE)
  (NOTEBOOK_REPORT_PATH.parent).mkdir(parents=True,exist_ok=True)
  (NOTEBOOK_REPORT_PATH.parent/'gpu_preflight.json').write_text(json.dumps(GPU_PREFLIGHT,indent=2))
  print('GPU PREFLIGHT:',GPU_PREFLIGHT)
'''
    assert marker in dependencies
    dependencies=dependencies.replace(marker,install+marker)
    dependencies=dependencies.replace(' except Exception as error:\n  fail_notebook_stage'," except Exception as error:\n  GPU_PREFLIGHT={'status':'FAILED','error_type':type(error).__name__}\n  NOTEBOOK_REPORT_PATH.parent.mkdir(parents=True,exist_ok=True)\n  (NOTEBOOK_REPORT_PATH.parent/'gpu_preflight.json').write_text(json.dumps(GPU_PREFLIGHT,indent=2))\n  fail_notebook_stage")
    notebook['cells'][3]['source']=dependencies.splitlines(True)
    config=''.join(notebook['cells'][50]['source'])
    # Expected source hashes include GPU adapter files too, while policy remains exact.
    expected=dict(baseline)
    for name in GPU_FILES:expected[name]=hashlib.sha256((ROOT/'notebooks'/name).read_bytes()).hexdigest()
    config=re.sub(r"activate_notebook_sources\(SOURCE_ROOT/'notebooks',\{[^\n]+\}\)",
                  lambda m:"activate_notebook_sources(SOURCE_ROOT/'notebooks',"+repr(expected)+')',config)
    config=config.replace("  print('CPU; SOURCE:'", "  print('GPU HYBRID; SOURCE:'")
    config=config.replace("  PILOT=OUTPUT/'pilot'","  PILOT=OUTPUT/'pilot'\n  GPU_REPORT=OUTPUT/'gpu_runtime.json'\n  GPU_EQUIVALENCE=OUTPUT/'gpu_equivalence.json'")
    notebook['cells'][50]['source']=config.splitlines(True)
    calculation=''.join(notebook['cells'][56]['source'])
    calculation=calculation.replace("  from location_intelligent_osm_buildings import prepare_osm_from_network", "  from location_intelligent_gpu_runtime import build_gpu\n  from location_intelligent_osm_buildings import prepare_osm_from_network")
    calculation=calculation.replace("timed_call('build',build,PILOT)","timed_call('build_gpu_hybrid',build_gpu,PILOT,GPU_REPORT,device=GPU_DEVICE)")
    calculation=calculation.replace("  print('Access status", "  from location_intelligent_gpu_validation import validate_calculation\n  CPU_REFERENCE_PILOT=validate_calculation(PILOT,OUTPUT/'cpu_reference',GPU_EQUIVALENCE)\n  print('Access status")
    notebook['cells'][56]['source']=calculation.splitlines(True)
    allocation=''.join(notebook['cells'][60]['source'])
    allocation=allocation.replace('  from location_intelligent_market_runtime import build_market', '  from location_intelligent_gpu_runtime import build_market_gpu')
    allocation=allocation.replace("MARKET=build_market(CONFIG,MARKET_CONFIG,PILOT,layers,facilities,OUTPUT/'market')",
        "MARKET=build_market_gpu(CONFIG,MARKET_CONFIG,PILOT,layers,facilities,OUTPUT/'market',report_path=GPU_REPORT,device=GPU_DEVICE)")
    allocation=allocation.replace("  print('MARKET STATUS:", "  from location_intelligent_gpu_validation import validate_market\n  validate_market(CONFIG,MARKET_CONFIG,CPU_REFERENCE_PILOT,layers,facilities,MARKET,OUTPUT/'cpu_reference_market',GPU_EQUIVALENCE)\n  print('MARKET STATUS:")
    notebook['cells'][60]['source']=allocation.splitlines(True)
    export=''.join(notebook['cells'][62]['source'])
    export=export.replace("    z.writestr('job_config.json'", "    z.writestr('gpu_execution.json',json.dumps({'preflight':GPU_PREFLIGHT,'runtime':read_json(GPU_REPORT) if GPU_REPORT.exists() else [],'profile':'GPU_WEIGHTED_GEOMETRY_V2'},sort_keys=True,indent=2))\n    for f in sorted(OUTPUT.glob('*-gpu-*.json.gz')):z.write(f,'gpu_runtime/'+f.name)\n    z.writestr('job_config.json'")
    export=export.replace("(PILOT,'pilot'),", "(PILOT,'pilot'),(CPU_REFERENCE_PILOT,'cpu_reference'),(OUTPUT/'cpu_reference_market','cpu_reference_market'),")
    export=export.replace("    z.writestr('gpu_execution.json'", "    z.writestr('gpu_equivalence.json',json.dumps(read_json(GPU_EQUIVALENCE),sort_keys=True,indent=2))\n    z.writestr('gpu_execution.json'")
    notebook['cells'][62]['source']=export.splitlines(True)
    # Remove CPU-specific instruction about patching only part8; backend changes need new job.
    notebook['cells'][59]['source']=['## 8. Market allocation — GPU weighted routing + audited geometry fallback\n',
        'Mode VALIDATE: GPU dan CPU reference harus setara sebelum output dipakai.\n']
    helper_cells=[]
    for name in GPU_FILES:
        helper_cells.append({'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],
            'source':('%%writefile /kaggle/working/area_coverage_gpu_source/notebooks/'+name+'\n'+(ROOT/'notebooks'/name).read_text()).splitlines(True)})
    # Written before dependency preflight; only stdlib is imported at GPU-module import.
    # All CPU helper writefiles must exist before V2 self-test imports routing.
    preflight={'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],
        'source':("if STAGES['dependencies']['status']=='SUCCEEDED':\n try:\n  activate_notebook_sources(SOURCE_ROOT/'notebooks',"+repr(expected)+")\n  from location_intelligent_gpu_diagnostics import compile_cuda_kernels,diagnostic\n  GPU_PREFLIGHT['kernel_compilation']=compile_cuda_kernels(NOTEBOOK_REPORT_PATH.parent,GPU_DEVICE)\n  from location_intelligent_gpu_validation import gpu_compute_preflight\n  GPU_PREFLIGHT['v2']=gpu_compute_preflight(GPU_DEVICE)\n  GPU_PREFLIGHT['profile']='GPU_WEIGHTED_GEOMETRY_V2'\n  GPU_PREFLIGHT['status']='SUCCEEDED'\n  (NOTEBOOK_REPORT_PATH.parent/'gpu_preflight.json').write_text(json.dumps(GPU_PREFLIGHT,indent=2))\n  print('GPU V2 preflight passed')\n except Exception as error:\n  from location_intelligent_gpu_diagnostics import diagnostic\n  GPU_PREFLIGHT['v2']=diagnostic(error,'gpu_v2_preflight')\n  GPU_PREFLIGHT['status']='FAILED'\n  (NOTEBOOK_REPORT_PATH.parent/'gpu_preflight.json').write_text(json.dumps(GPU_PREFLIGHT,indent=2))\n  print(GPU_PREFLIGHT['v2'])\n  print('GPU compile details:',NOTEBOOK_REPORT_PATH.parent/'kernel_compilation.json')\n  fail_notebook_stage('dependencies',error)\n").splitlines(True)}
    notebook['cells'].insert(50,preflight)
    notebook['cells'][2:2]=helper_cells
    notebook['cells'].append({'cell_type':'markdown','metadata':{},'source':[
        '## Handoff berurutan: Area Coverage → Traffic Counter\n',
        'Tidak menjalankan Traffic Counter. READY berarti output teknis tersedia, bukan semua unknown terselesaikan.\n']})
    notebook['cells'].append({'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':'''# Failures can never publish a successful handoff from an older run.
HANDOFF_PATH=globals().get('OUTPUT',NOTEBOOK_REPORT_PATH.parent)/'engine_handoff.json'
handoff={'status':'NOT_READY','traffic_started':False,'area_business_status':None}
try:
 if STAGES['output']['status'] in {'SUCCEEDED','PARTIAL'} and MARKET is not None:
  from location_intelligent_li3 import verify_manifest
  verify_manifest(PILOT)
  market_manifest=read_json(Path(MARKET['output_path'])/'manifest.json')
  for name,digest in market_manifest['files'].items():
   if sha(Path(MARKET['output_path'])/name)!=digest:raise RuntimeError('MARKET_MANIFEST_CHANGED')
  if sha(archive)!=read_json(archive_manifest)['sha256']:raise RuntimeError('ARCHIVE_CHANGED')
  equivalence=read_json(GPU_EQUIVALENCE)
  if any(equivalence.get(stage,{}).get('status')!='PASS' for stage in ['calculation','market']):raise RuntimeError('GPU_EQUIVALENCE_REQUIRED')
  if not GPU_PREFLIGHT.get('v2',{}).get('actual_cuda_executed'):raise RuntimeError('GPU_V2_PREFLIGHT_REQUIRED')
  from location_intelligent_gpu import release_gpu
  released=release_gpu(GPU_DEVICE)
  handoff.update(status='READY_FOR_TRAFFIC_COUNTER',area_business_status=MARKET['status'],
                 area_market_manifest=str(Path(MARKET['output_path'])/'manifest.json'),gpu_release=released)
except Exception as error:
 handoff.update(status='NOT_READY',error_type=type(error).__name__)
finally:
 # Also attempt cleanup on failure; never convert failure into READY.
 try:
  from location_intelligent_gpu import release_gpu
  handoff['gpu_cleanup']=release_gpu(GPU_DEVICE)
 except Exception as cleanup_error:handoff.update(status='NOT_READY',cleanup_error_type=type(cleanup_error).__name__)
 HANDOFF_PATH.parent.mkdir(parents=True,exist_ok=True)
 HANDOFF_PATH.write_text(json.dumps(handoff,indent=2))
print(handoff)
'''.splitlines(True)})
    for cell in notebook['cells']:
        if cell['cell_type']=='code':
            text=''.join(cell['source']);ast.parse(text.split('\n',1)[1] if text.startswith('%%writefile ') else text)
            cell['execution_count']=None;cell['outputs']=[]
    DEST.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+'\n')
    report={'baseline_commit':'b84c850','cpu_notebook_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'cpu_helpers_sha256':baseline,'gpu_profile':'GPU_WEIGHTED_GEOMETRY_V2',
        'cuda_execution_status':'NOT_EXECUTED_IN_CODEX','business_configuration':'UNCHANGED'}
    packet=ROOT/'results/area_coverage_map/gpu_kaggle_packet';packet.mkdir(parents=True,exist_ok=True)
    (packet/DEST.name).write_bytes(DEST.read_bytes())
    metadata={'id':'chrisbiran/area-coverage-market-gpu-hybrid','title':'Area Coverage Market GPU Hybrid',
        'code_file':DEST.name,'language':'python','kernel_type':'notebook','is_private':True,
        'enable_gpu':True,'enable_internet':True,'dataset_sources':[],'kernel_sources':[],'competition_sources':[]}
    (packet/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (ROOT/'docs/AREA_COVERAGE_GPU_BASELINE.json').write_text(json.dumps(report,indent=2)+'\n')
    print(str(DEST))

if __name__=='__main__':build()
