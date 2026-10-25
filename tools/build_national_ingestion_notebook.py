"""Build visible CPU-only ingestion notebook; never run an engine or access BQ."""
import json,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def build():
    cells=[]
    def md(text):cells.append({'cell_type':'markdown','metadata':{},'source':text.splitlines(True)})
    def code(text):
        ast.parse(text);cells.append({'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':text.splitlines(True)})
    md('''# Indonesia source ingestion → GCS (CPU)
Aktifkan Internet dan Secret `LocatioIntelligent`. Accelerator None.
Mengunggah PBF OSM Indonesia dan dua model Traffic terikat hash. Ini ingestion
terpisah, tanpa counting/routing/GPU/BQ. PBF belum merupakan paket input engine:
parsing, indeks geospasial dan adapter ekuivalensi diperlukan sesudah upload.
Overture, vector basemap, video dan container image belum dibuat notebook ini.
Lisensi OSM/Geofabrik dan model tetap berlaku; bucket privat.
''')
    code('''import sys,subprocess
subprocess.run([sys.executable,'-m','pip','install','--quiet','google-cloud-storage','google-crc32c'],check=True)
import json,hashlib,base64,uuid,shutil
from pathlib import Path
from datetime import datetime,timezone
import requests
from kaggle_secrets import UserSecretsClient
from google.oauth2 import service_account
from google.cloud import storage
BUCKET='feeder-location-intelligent'
PROJECT='locdeproject'
WORK=Path('/kaggle/working/national_ingestion');WORK.mkdir(exist_ok=True)
credentials=service_account.Credentials.from_service_account_info(json.loads(UserSecretsClient().get_secret('LocatioIntelligent')))
client=storage.Client(project=PROJECT,credentials=credentials)
bucket=client.bucket(BUCKET)
RUN_ID=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
RECEIPTS=[]
''')
    code('''def digests(path):
    sha=hashlib.sha256();md5=hashlib.md5()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):sha.update(block);md5.update(block)
    return sha.hexdigest(),md5.hexdigest(),base64.b64encode(md5.digest()).decode()

def download(url,path,expected_md5=None,expected_sha=None):
    if path.exists():
        sha,md5,_=digests(path)
        if (expected_md5 and md5==expected_md5) or (expected_sha and sha==expected_sha):return path
        raise RuntimeError('Existing local input checksum differs; inspect '+str(path))
    temporary=path.with_suffix(path.suffix+'.partial')
    with requests.get(url,stream=True,timeout=(20,90)) as response:
        response.raise_for_status();size=int(response.headers.get('Content-Length',0))
        if size and shutil.disk_usage(WORK).free<size+512*1024*1024:raise RuntimeError('Insufficient disk')
        done=0;next_log=0
        with temporary.open('wb') as f:
            for chunk in response.iter_content(8*1024*1024):
                f.write(chunk);done+=len(chunk)
                if done>=next_log:print(path.name,done,'bytes',flush=True);next_log=done+128*1024*1024
        if size and done!=size:raise RuntimeError('Incomplete download')
    sha,md5,_=digests(temporary)
    if expected_md5 and md5!=expected_md5:raise RuntimeError('Provider MD5 mismatch: latest may have rotated; nothing finalized')
    if expected_sha and sha!=expected_sha:raise RuntimeError('Model SHA256 mismatch')
    temporary.replace(path);return path

def upload_verified(path,prefix,provenance):
    sha,md5,md5_b64=digests(path);key=prefix+'/'+sha+'/'+path.name
    blob=bucket.blob(key)
    if blob.exists():
        blob.reload()
    else:
        blob.metadata={'sha256':sha,'ingestion_run':RUN_ID}
        blob.upload_from_filename(str(path),if_generation_match=0,checksum='crc32c',timeout=600)
        blob.reload()
    if blob.size!=path.stat().st_size or (blob.metadata or {}).get('sha256')!=sha or blob.md5_hash!=md5_b64:
        raise RuntimeError('GCS object verification failed')
    receipt={'uri':'gs://'+BUCKET+'/'+key,'generation':int(blob.generation),'bytes':blob.size,
        'sha256':sha,'md5':md5,'gcs_crc32c':blob.crc32c,'provenance':provenance}
    RECEIPTS.append(receipt);print('VERIFIED',receipt['uri'],flush=True);return receipt
''')
    code('''PBF_URL='https://download.geofabrik.de/asia/indonesia-latest.osm.pbf'
checksum=requests.get(PBF_URL+'.md5',timeout=30);checksum.raise_for_status()
provider_md5=checksum.text.split()[0].lower()
if len(provider_md5)!=32 or any(c not in '0123456789abcdef' for c in provider_md5):raise RuntimeError('Invalid provider checksum')
pbf=download(PBF_URL,WORK/'indonesia.osm.pbf',expected_md5=provider_md5)
upload_verified(pbf,'sources/osm/indonesia',{'provider':'Geofabrik/OpenStreetMap','url':PBF_URL,'role':'osm_indonesia_pbf',
    'provider_md5':provider_md5,'coverage':'GEOFABRIK_INDONESIA_EXTRACT_NOT_COMPLETENESS_CLAIM',
    'license':'ODbL; preserve attribution and applicable obligations',
    'engine_ready':False,'next':'Parse PBF header/replication timestamp, build spatial index, validate adapter'})
''')
    refs=json.loads((ROOT/'results/t7sl_modular/config/fresh_request.json').read_text())['artifacts']
    assets={k:{'filename':Path(refs[k]['path']).name,'sha256':refs[k]['sha256']} for k in ['detector','reid']}
    code('ASSETS='+repr(assets)+'''
for role,asset in ASSETS.items():
    url='https://github.com/ultralytics/assets/releases/download/v8.4.0/'+asset['filename']
    path=download(url,WORK/asset['filename'],expected_sha=asset['sha256'])
    upload_verified(path,'models/traffic/'+role,{'provider':'Ultralytics','url':url,'role':role,
        'scope':'CURRENT_EXPERIMENT_ASSET_NOT_FINAL_VEHICLE_REID_VALIDATION'})
''')
    code('''unique={row['uri']:row for row in RECEIPTS}
roles={row['provenance'].get('role') for row in unique.values()}
if roles!={'osm_indonesia_pbf','detector','reid'} or len(unique)!=3:
    raise RuntimeError('Required PBF/models missing or ambiguous; no successful ingestion manifest published')
manifest={'schema':'national_ingestion_receipt_v1','run_id':RUN_ID,'status':'RAW_ASSETS_UPLOADED',
    'engine_snapshot_ready':False,'objects':list(unique.values()),
    'pending':['PBF timestamp and completeness audit','PBF spatial index and canonical adapter',
               'national Overture extraction','licensed national vector basemap and local frontend assets',
               'Traffic video/config bundles','container builds and no-provider-egress tests']}
body=json.dumps(manifest,sort_keys=True,indent=2).encode()
key='ingestion/manifests/'+RUN_ID+'.json'
blob=bucket.blob(key);blob.metadata={'sha256':hashlib.sha256(body).hexdigest()}
blob.upload_from_string(body,content_type='application/json',if_generation_match=0,checksum='crc32c')
(WORK/'ingestion_receipt.json').write_bytes(body)
print(json.dumps(manifest,indent=2));print('Manifest: gs://'+BUCKET+'/'+key)
''')
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},'cells':cells}
    name='indonesia_gcs_source_ingestion.ipynb';p=ROOT/'notebooks'/name;p.write_text(json.dumps(notebook,indent=1)+'\n')
    packet=ROOT/'results/gcs/national_ingestion_packet';packet.mkdir(parents=True,exist_ok=True)
    (packet/name).write_bytes(p.read_bytes())
    metadata={'id':'chrisbiran/indonesia-gcs-source-ingestion-cpu','title':'Indonesia GCS Source Ingestion CPU','code_file':name,
        'language':'python','kernel_type':'notebook','is_private':True,'enable_gpu':False,'enable_internet':True,
        'dataset_sources':[],'kernel_sources':[],'competition_sources':[]}
    (packet/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n');return packet


if __name__=='__main__':print(build())
