"""Build a fully readable Kaggle CPU notebook. No encoded implementation payload."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
FILES=['location_intelligent_config.py','location_intelligent_validator.py','location_intelligent_buildings.py',
 'location_intelligent_capacity.py','location_intelligent_routing.py','location_intelligent_motor_routing.py',
 'location_intelligent_overture_probe.py','location_intelligent_li3_sources.py','location_intelligent_li3_graph.py',
 'location_intelligent_li3_connectors.py','location_intelligent_li3_core.py','location_intelligent_li3.py',
 'location_intelligent_map_pilot.py','location_intelligent_map_poi.py']

def main():
 cells=[]
 def add(kind,text):
  cells.append({'cell_type':kind,'id':hashlib.sha256((kind+text).encode()).hexdigest()[:8],
    'metadata':{},'source':text.splitlines(True),**({'execution_count':None,'outputs':[]} if kind=='code' else {})})
 def md(text):add('markdown',text+'\n')
 def code(text):add('code',text+'\n')
 md('''# Area Coverage — CPU, bangunan800m, toko/kompetitor2km
Target pengguna: **latitude -6.409737552410453; longitude 106.82835008971841**.

Semua implementasi Python ditampilkan sebagai source cell, lalu dipanggil oleh cell eksekusi.
Tidak ada base64, arsip implementasi tersembunyi, `git clone`, atau kode remote yang dieksekusi.
Dataset terlampir merupakan snapshot DATA sumber nyata; file `engine_source` di dalamnya hanya arsip provenance dan tidak diimpor.

Alur: verifikasi sumber → selection/capacity → graph/access → connectors → routing → BigQuery → Folium.
CPU saja. Accepted adalah keputusan skenario7km/jam/round(menit)≤10; bukan validasi akses fisik atau populasi.
Tidak menjalankan Traffic, PPAC, model atau GPU.''')
 md('''## 1. Konfigurasi yang bisa diedit
Radius bangunan800m berbeda dari radius marker toko/kompetitor2000m.
Network extraction5500m mempertahankan kontrol eksperimen untuk routing; tampilan network dipotong2km tanpa memotong graph perhitungan.
`FROZEN` memakai data terlampir. Koordinat/radius sumber berbeda ditolak; pilih `REFRESH` dan revision baru untuk akuisisi baru.
`BQ_MODE=ACQUIRE_ONCE` membuat snapshot private pertama setelah secret tersedia, lalu memakai cache sukses dalam session.
Untuk hasil lintas session identik, lampirkan output/cache BigQuery versi sebelumnya dan gunakan `FROZEN`; tabel live dapat berubah.''')
 code('''from pathlib import Path
import os,sys,json,hashlib,subprocess,shutil
os.environ['CUDA_VISIBLE_DEVICES']='-1'
os.environ['OMP_NUM_THREADS']='2'
os.environ['OPENBLAS_NUM_THREADS']='2'
os.environ['PROJ_NETWORK']='OFF'
SOURCE_ROOT=Path('/kaggle/working/area_coverage_cpu_source')
(SOURCE_ROOT/'notebooks').mkdir(parents=True,exist_ok=True)
SOURCE_MODE='FROZEN'       # FROZEN or REFRESH; never silently fetch on a cache mismatch
SOURCE_REVISION='user-target-800m-v1'
BQ_MODE='ACQUIRE_ONCE'     # ACQUIRE_ONCE or FROZEN
BQ_SECRET_NAME='PROJECT_PPAC'  # User-confirmed Kaggle Secret; full service-account JSON
BQ_FROZEN_CACHE_INPUT=None  # Optional path to a previously saved bq_snapshot directory in /kaggle/input
BQ_SCHEMA_OVERRIDES={}    # e.g. {'indomaret': {'point':'KOORDINAT'}}; verified against actual table.schema
POI_MODE='FROZEN'         # Explicit ACQUIRE_ONCE only for a new source revision
CONFIG={
 'latitude':-6.409737552410453,'longitude':106.82835008971841,
 'building_radius_m':800.0,'poi_radius_m':2000.0,'store_buffer_radius_m':400.0,'building_query_padding_m':50.0,
 'poi_overpass_endpoints':['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter'],
 'min_area_m2':45.0,'max_area_m2':550.0,'metric_crs':'EPSG:32748','network_radius_m':5500.0,
 'overture_release':'2026-10-21.0','overture_schema':'2.0.0','max_building_rows':50000,
 'bq_billing_project':'locdeproject','bq_maximum_bytes_billed':268435456,
 'bq_tables':{'competitor':'locdeproject.DWH_NS_LOC.COMPETITOR','indomaret':'locdeproject.DWH_NS_LOC.AREA_COVERAGE'}
}
print(json.dumps(CONFIG,indent=2));print('Execution: CPU only; no GPU requested')''')
 md('## 2. Dependencies dan runtime CPU eksplisit\nCell ini hanya memasang dependency. Source algoritme berada lengkap di bawah. GDAL worker memakai system Python, terpisah dari runtime notebook.')
 code('''packages=['duckdb==2.0.0','osmnx==2.1.1','shapely==2.2.0','pyproj==3.8.0','numpy==2.5.4','pandas==3.1.0','geopandas==1.2.0','google-cloud-bigquery==3.46.2','folium==0.20.0']
subprocess.run([sys.executable,'-m','pip','install','--quiet',*packages],check=True)
# Avoid passing a different Conda PROJ database to the system GDAL worker.
for name in ['PROJ_LIB','PROJ_DATA','GDAL_DATA']:
 os.environ.pop(name,None)
CORE_PYTHON='/usr/bin/python3'
probe=subprocess.run([CORE_PYTHON,'-c','from osgeo import gdal;import pyproj;assert int(gdal.VersionInfo("VERSION_NUM"))>=3070000'],capture_output=True,text=True)
if probe.returncode:
 subprocess.run(['apt-get','update','-qq'],check=True)
 subprocess.run(['apt-get','install','-y','-qq','python3-gdal','python3-pyproj'],check=True)
subprocess.run([CORE_PYTHON,'-c','import platform,pyproj;from osgeo import gdal;print("CORE",platform.python_version(),gdal.VersionInfo("RELEASE_NAME"),pyproj.__version__);assert int(gdal.VersionInfo("VERSION_NUM"))>=3070000'],check=True)
print('Notebook Python',sys.version)
''')
 md('## 3. Implementasi yang benar-benar diimpor\nSetiap cell berikut menulis file Python yang isinya terlihat penuh. Buka cell nama modul untuk memeriksa algoritme. Folder ini menjadi satu-satunya source helper yang digunakan.')
 for name in FILES:
  md('### '+name)
  code('%%writefile /kaggle/working/area_coverage_cpu_source/notebooks/'+name+'\n'+(ROOT/'notebooks'/name).read_text().rstrip())
 code('''sys.path.insert(0,str(SOURCE_ROOT/'notebooks'))
os.environ['PYTHONPATH']=str(SOURCE_ROOT/'notebooks')
from location_intelligent_li3_sources import read_json,write_json
from location_intelligent_map_pilot import sha,prepare_pilot,load_bq_layers,interactive_map
from location_intelligent_map_poi import load_osm_pois,POI_CATEGORIES
from location_intelligent_li3 import build,make_manifest,verify_manifest
from IPython.display import display,FileLink,HTML
import importlib,platform,importlib.metadata
for name in ['location_intelligent_li3','location_intelligent_motor_routing','location_intelligent_map_pilot']:
 module=importlib.import_module(name)
 assert Path(module.__file__).resolve().is_relative_to(SOURCE_ROOT)
 print('ACTIVE SOURCE:',module.__file__)
CODE_SHA=hashlib.sha256(json.dumps({p.name:sha(p) for p in sorted((SOURCE_ROOT/'notebooks').glob('*.py'))},sort_keys=True).encode()).hexdigest()
key=hashlib.sha256(json.dumps({'config':CONFIG,'code':CODE_SHA,'revision':SOURCE_REVISION},sort_keys=True).encode()).hexdigest()[:16]
OUTPUT=Path('/kaggle/working/results/area_coverage_cpu')/key
OUTPUT.mkdir(parents=True,exist_ok=True)
PILOT=OUTPUT/'pilot';print('OUTPUT:',OUTPUT)''')
 md('''## 4. Snapshot actual dan pilihan acquisition
Data sumber dipilih melalui inventory ber-checksum, bukan nama folder asumsi.
Sumber N1 lama tidak direlabel. Snapshot default ini memang berasal dari target/radius baru.
Perhitungan di bawah tetap menjalankan source cell pada CPU; tidak sekadar membuka HTML hasil lama.''')
 code('''EXPECTED_MANIFEST='__SOURCE_MANIFEST__'
SOURCE_PACKET=None
for p in Path('/kaggle/input').rglob('manifest.json'):
 if p.is_file() and sha(p)==EXPECTED_MANIFEST:
  SOURCE_PACKET=p.parent;break
if SOURCE_MODE=='FROZEN':
 if SOURCE_PACKET is None:
  # Only data may be unpacked here; runtime helper imports remain under SOURCE_ROOT.
  archives=[p for p in Path('/kaggle/input').rglob('area_source_snapshot.snapshot') if sha(p)=='__SOURCE_ARCHIVE__']
  assert len(archives)==1,'Attach chrisbiran/area-coverage-800m-source-snapshot; no implicit live fallback'
  import zipfile
  unpack=OUTPUT/'input_snapshot';unpack.mkdir(exist_ok=True)
  with zipfile.ZipFile(archives[0]) as z:
   for item in z.infolist():
    assert (unpack/item.filename).resolve().is_relative_to(unpack.resolve())
    assert ((item.external_attr>>16)&0o170000)!=0o120000
   z.extractall(unpack)
  found=[p for p in unpack.rglob('manifest.json') if sha(p)==EXPECTED_MANIFEST]
  assert len(found)==1;SOURCE_PACKET=found[0].parent
 verify_manifest(SOURCE_PACKET)
 requested=read_json(SOURCE_PACKET/'requested_config.json')
 for field in ['latitude','longitude','building_radius_m','min_area_m2','max_area_m2','metric_crs','network_radius_m','overture_release','overture_schema']:
  assert requested[field]==CONFIG[field],f'Frozen source differs: {field}; REFRESH/new revision required'
 print('VERIFIED FROZEN SOURCE:',SOURCE_PACKET)
elif SOURCE_MODE!='REFRESH':
 raise ValueError('Explicit SOURCE_MODE FROZEN or REFRESH required')
''')
 md('## 5. Full CPU calculation — seluruh source rows\nSemua bangunan sumber diproses; tidak sampling footprint. Rule selection/routing/capacity asli dipertahankan. Runtime aktual direkam. Source OSM yang non-atomic/unknown tetap PARTIAL, tidak diubah menjadi izin.')
 code('''if (PILOT/'manifest.json').exists():
 verify_manifest(PILOT)
 print('REOPEN existing calculation — no new routing')
else:
 if SOURCE_MODE=='FROZEN':
  PILOT.mkdir(parents=True,exist_ok=False)
  shutil.copytree(SOURCE_PACKET/'raw',PILOT/'raw')
  shutil.copytree(SOURCE_PACKET/'config',PILOT/'config')
  shutil.copyfile(SOURCE_PACKET/'requested_config.json',PILOT/'requested_config.json')
 else:
  index_hits=list(Path('/kaggle/input').rglob('overture_partition_index.data'))
  assert len(index_hits)==1,'Pinned partition inventory required for explicit refresh'
  CONFIG['partition_index_sha256']=sha(index_hits[0]);CONFIG['partition_catalog_sha256']='42e6cc7b99176797e08ecebc85bc21dc7428008e56b47151463d3f10edfa5986'
  prepare_pilot(CONFIG,PILOT,core_python=CORE_PYTHON,partition_index=index_hits[0])
 packages=['duckdb','geopandas','networkx','numpy','osmnx','pandas','pyproj','requests','shapely']
 actual_source={'python':platform.python_version(),'packages':{p:importlib.metadata.version(p) for p in packages}}
 write_json(PILOT/'config/source_software.json',actual_source)
 command='import platform,json,pyproj;from osgeo import gdal;print(json.dumps({"python":platform.python_version(),"gdal":gdal.VersionInfo("RELEASE_NAME"),"pyproj":pyproj.__version__}))'
 actual_core=json.loads(subprocess.check_output([CORE_PYTHON,'-c',command]))
 write_json(PILOT/'config/core_software.json',actual_core)
 print('ACTUAL CPU CORE:',actual_core)
 report=build(PILOT)
 make_manifest(PILOT)
 print('CPU calculation complete:',report['source_records'],'source rows')
report=read_json(PILOT/'report.json')
selection=read_json(PILOT/'building_results/selection.json')
assert report['all_source_rows_accounted']==report['source_records']
assert sum(report['decision_counts_selected'].values())==report['selected_buildings']
import pandas as pd
print('ANALYSIS STATUS:',report['status'])
display(pd.DataFrame([selection['summary']]))
display(pd.DataFrame([{'decision':k,'buildings':v} for k,v in report['decision_counts_selected'].items()]))
print('CAPACITY — reference split units, not population:',report['capacity_by_unit'])
print('SOURCE WARNINGS:',report['source_warnings'])
''')
 md('''## 6. Akses BigQuery dan radius2000m
1. Buat service account pembaca di project `locdeproject`.
2. Grant BigQuery Job User pada billing project dan Data Viewer pada kedua tabel.
3. User sudah menyimpan Kaggle Secret `PROJECT_PPAC`; aktifkan akses notebook ini. Isinya harus seluruh JSON service account.
4. Jangan masukkan key ke source/outputs/GitHub/chat.

Metadata schema dibaca lebih dahulu. Nama kolom belum diklaim terverifikasi sebelum metadata berhasil.
Query memakai parameter, jarak WGS84 spheroid≤2000m, dry run dan byte budget256MiB per query.
Data historis yang sama ID/lokasinya digabung untuk marker; konflik satu ID pada lokasi berbeda tetap terlihat.
Kegagalan auth/query ditampilkan sebagai BLOCKED/FAILED dan jumlah null, bukan toko0.''')
 code('''BQ_CACHE=OUTPUT/'bq_snapshot'
if BQ_FROZEN_CACHE_INPUT is not None and not BQ_CACHE.exists():
 shutil.copytree(Path(BQ_FROZEN_CACHE_INPUT),BQ_CACHE)
if BQ_MODE=='FROZEN':
 assert BQ_CACHE.exists() and all((BQ_CACHE/(k+'.json')).exists() for k in ['indomaret','competitor']),'Provide a successful BQ snapshot from the same request; missing is not zero'
elif BQ_MODE!='ACQUIRE_ONCE':
 raise ValueError('BQ_MODE must be FROZEN or ACQUIRE_ONCE')
layers=load_bq_layers(CONFIG,BQ_CACHE,secret_name=BQ_SECRET_NAME,overrides=BQ_SCHEMA_OVERRIDES)
write_json(OUTPUT/'bq_readiness.json',layers)
from location_intelligent_map_pilot import poi_locations
rows=[]
for kind,layer in layers.items():
 locations=poi_locations(layer) if layer['status']=='SUCCEEDED' else None
 rows.append({'layer':kind,'table':layer['table'],'status':layer['status'],'marker_locations':None if locations is None else len(locations),'error_type':layer.get('error_type')})
 if layer['status']=='SUCCEEDED':
  print('VERIFIED SCHEMA BINDING',kind,layer['fields']);display(pd.DataFrame(locations))
display(pd.DataFrame(rows))
''')
 md('''## 6B. POI fasilitas OpenStreetMap dalam2km
Delapan layer terpisah: rumah sakit, klinik, pasar, kantor polisi, sekolah, kantor pemerintahan, kantor dan universitas.
Sumber/tag/query serta data raw disimpan; nama fasilitas tidak dikarang.
Snapshot default dibekukan agar rerun tidak mengambil keadaan OSM live yang berubah.
Titik way/relation menggunakan center OSM, bukan pintu masuk. Counts adalah fitur OSM, bukan jaminan seluruh fasilitas fisik atau unique site.''')
 code('''POI_EXPECTED_SHA='__POI_SNAPSHOT_SHA__'
POI_INPUTS=[p for p in Path('/kaggle/input').rglob('osm_poi_snapshot.data') if sha(p)==POI_EXPECTED_SHA]
assert len(POI_INPUTS)<=1,'Ambiguous duplicate POI snapshot inputs'
facilities=load_osm_pois(CONFIG,OUTPUT/'osm_poi_snapshot.data',mode=POI_MODE,
 frozen_input=POI_INPUTS[0] if POI_INPUTS else None,
 expected_sha256=POI_EXPECTED_SHA if POI_MODE=='FROZEN' else None)
write_json(OUTPUT/'facilities_readiness.json',{'status':facilities['status'],'count':facilities.get('count'),
 'counts_by_category':facilities.get('counts_by_category'),'source_as_of':facilities.get('source_as_of'),
 'error_type':facilities.get('error_type')})
print('OSM FACILITIES:',facilities['status'])
if facilities['status']=='SUCCEEDED':
 display(pd.DataFrame([{'category':POI_CATEGORIES[k][0],'osm_features':v} for k,v in facilities['counts_by_category'].items()]))
view_identity={'pilot_manifest_sha256':sha(PILOT/'manifest.json'),'code_sha256':CODE_SHA,
 'poi_snapshots':{k:hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest() for k,v in layers.items()},
 'facilities_snapshot_sha256':hashlib.sha256(json.dumps(facilities,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
VIEW_VERSION=hashlib.sha256(json.dumps(view_identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
VIEW=OUTPUT/'views'/VIEW_VERSION
VIEW.mkdir(parents=True,exist_ok=True)
REOPEN_VIEW=(VIEW/'view_manifest.json').exists()
if REOPEN_VIEW:
 for row in read_json(VIEW/'view_manifest.json')['files']:
  assert sha(VIEW/row['path'])==row['sha256'],'Saved view changed'
print('VIEW VERSION:',VIEW_VERSION)
''')
 md('''## 7. Peta interaktif di output Kaggle
Layer: building counter800m, target, lingkaran800m/2000m, footprint dengan keputusan skenario, network OSM, delapan kategori POI, marker Indomaret dan kompetitor.
Radius400m untuk SETIAP marker toko ada dalam layer terpisah Indomaret/Kompetitor yang bisa diaktifkan. Bukan rute atau coverage bisnis tervalidasi.
Layer Control, zoom/pan, tooltip/popup, marker cluster, fullscreen dan alat ukur tersedia.
Marker hanya berasal dari hasil sumber aktual. Jika BQ belum tersedia, banner menyatakan keterbatasannya.
Basemap OSM adalah konteks tampilan online; angka berasal dari snapshot, bukan perubahan tile basemap.''')
 code('''if not REOPEN_VIEW:
 m=interactive_map(CONFIG,PILOT,layers,VIEW/'area_coverage_map.html',facilities=facilities)
 display(m)
else:
 from html import escape
 saved=(VIEW/'area_coverage_map.html').read_text()
 display(HTML('<iframe srcdoc="'+escape(saved,quote=True)+'" style="width:100%;height:800px;border:0"></iframe>'))
display(FileLink(str(VIEW/'area_coverage_map.html')))
''')
 md('## 8. Export dan kesiapan hasil\nPeta HTML/CSV/GeoJSON serta source manifest disimpan. Tidak memasukkan query gagal sebagai data kosong. Hasil lama immutable; perubahan sumber/policy/runtime membuat revision baru. Untuk reopen di session berikutnya, lampirkan saved output/source snapshot; koordinat saja bukan identitas data.')
 code('''from location_intelligent_map_pilot import poi_locations
public_metadata=[]
for kind,layer in layers.items():
 if layer['status']=='SUCCEEDED' and not REOPEN_VIEW:
  frame=pd.DataFrame(poi_locations(layer));frame.to_csv(VIEW/(kind+'_within_2km.csv'),index=False)
  features=[{'type':'Feature','geometry':{'type':'Point','coordinates':[r['longitude'],r['latitude']]},'properties':{k:v for k,v in r.items() if k not in ['latitude','longitude']}} for r in poi_locations(layer)]
  write_json(VIEW/(kind+'_within_2km.geojson'),{'type':'FeatureCollection','features':features})
 public_metadata.append({'layer':kind,'status':layer['status'],'table':layer['table'],'count':None if layer['status']!='SUCCEEDED' else len(poi_locations(layer))})
if facilities['status']=='SUCCEEDED' and not REOPEN_VIEW:
 pd.DataFrame(facilities['rows']).to_csv(VIEW/'osm_facilities_within_2km.csv',index=False)
 features=[{'type':'Feature','geometry':{'type':'Point','coordinates':[r['longitude'],r['latitude']]},'properties':{k:v for k,v in r.items() if k not in ['latitude','longitude']}} for r in facilities['rows']]
 write_json(VIEW/'osm_facilities_within_2km.geojson',{'type':'FeatureCollection','features':features})
summary={'result_version':VIEW_VERSION,'status':'MAP_READY' if facilities['status']=='SUCCEEDED' and all(x['status']=='SUCCEEDED' for x in layers.values()) else 'PARTIAL_MAP_INPUTS_UNAVAILABLE',
 'target':{'latitude':CONFIG['latitude'],'longitude':CONFIG['longitude']},'building_radius_m':CONFIG['building_radius_m'],'poi_radius_m':CONFIG['poi_radius_m'],
 'store_buffer_radius_m':CONFIG['store_buffer_radius_m'],'facility_status':facilities['status'],
 'facility_count':facilities.get('count'),'facility_counts_by_category':facilities.get('counts_by_category'),
 'facility_source_as_of':facilities.get('source_as_of'),
 'analysis_status':report['status'],'source_records':report['source_records'],'selected_buildings':report['selected_buildings'],
 'decisions':report['decision_counts_selected'],'poi_layers':public_metadata,'source_manifest_sha256':sha(PILOT/'manifest.json'),
 'code_sha256':CODE_SHA,'gpu_used':False,'execution':'FROZEN_SOURCE_CPU_CALCULATION_OR_VERIFIED_REOPEN',
 'claim':'EXPERIMENTAL_SCENARIO_NOT_PHYSICAL_ACCESS_OR_POPULATION_VALIDATION'}
if not REOPEN_VIEW:
 write_json(VIEW/'run_summary.json',summary)
 write_json(VIEW/'view_manifest.json',{'schema_version':'area_cpu_map_outputs_v1','result_version':VIEW_VERSION,'files':[{'path':str(p.relative_to(VIEW)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(VIEW.rglob('*')) if p.is_file() and p.name!='view_manifest.json']})
write_json(OUTPUT/'latest_view.json',{'result_version':VIEW_VERSION,'path':str(VIEW.relative_to(OUTPUT))})
print(json.dumps(summary,indent=2));print('IMMUTABLE VIEW DIRECTORY:',VIEW)
''')
 source_manifest=(ROOT/'results/area_coverage_map/source_binding.json')
 if source_manifest.exists():
  binding=json.loads(source_manifest.read_text())
  for cell in cells:
   cell['source']=[line.replace('__SOURCE_MANIFEST__',binding['manifest_sha256']).replace('__SOURCE_ARCHIVE__',binding['archive_sha256']) for line in cell['source']]
 poi_binding=ROOT/'results/area_coverage_map/poi_binding.json'
 if poi_binding.exists():
  poi=json.loads(poi_binding.read_text())
  for cell in cells:
   cell['source']=[line.replace('__POI_SNAPSHOT_SHA__',poi['sha256']) for line in cell['source']]
 notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},'cells':cells}
 path=ROOT/'notebooks/area_coverage_cpu_800m_poi_2km.ipynb';path.write_text(json.dumps(notebook,indent=1)+'\n')
 packet=ROOT/'results/area_coverage_map/kaggle_packet';packet.mkdir(parents=True,exist_ok=True)
 (packet/path.name).write_bytes(path.read_bytes())
 (packet/'kernel-metadata.json').write_text(json.dumps({'id':'chrisbiran/area-coverage-800m-poi-2km-cpu',
 'title':'Area Coverage 800m POI 2km CPU','code_file':path.name,'language':'python','kernel_type':'notebook',
 'is_private':True,'enable_gpu':False,'enable_tpu':False,'enable_internet':True,
 'dataset_sources':['chrisbiran/area-coverage-800m-source-snapshot'],'kernel_sources':[],'competition_sources':[]},indent=2)+'\n')
 print('Notebook cells',len(cells),'bytes',path.stat().st_size)

if __name__=='__main__':main()
