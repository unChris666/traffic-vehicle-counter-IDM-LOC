"""Read committed BQ summaries and their checksum-bound private GCS presentation."""
import hashlib
from html import escape
import json
import re
from .cloud_schema import SCHEMAS

MAX_HTML_BYTES=64*1024**2

class ResultsReader:
    def __init__(self,destination,storage_client,bq_client):
        self.destination=destination;self.storage=storage_client;self.bq=bq_client
        self.location=None

    def query(self,sql,**params):
        from google.cloud import bigquery
        config=bigquery.QueryJobConfig(maximum_bytes_billed=268435456,
            query_parameters=[bigquery.ScalarQueryParameter(k,'STRING',v) for k,v in params.items()])
        return [dict(r) for r in self.bq.query(sql,job_config=config,location=self.location).result(timeout=60)]

    def load(self,target_id,job_id=None):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',target_id or ''):raise ValueError('Kode toko tidak valid.')
        if job_id and not re.fullmatch(r'job_[a-f0-9]{32}',job_id):raise ValueError('Job ID tidak valid.')
        d=self.destination.dataset;self.location=self.bq.get_dataset(d,timeout=30).location
        job_filter=' AND job_id=@job_id' if job_id else ''
        jobs=self.query(f"SELECT * FROM `{d}.job_runs` WHERE target_id=@target_id AND publication_status='READY'{job_filter} ORDER BY created_at DESC LIMIT 1",
                        **{'target_id':target_id,**({'job_id':job_id} if job_id else {})})
        if not jobs:raise ValueError('Belum ada hasil READY untuk kode toko/job ini. Jalankan engine dan pastikan publikasi selesai.')
        job=jobs[0];result={'job_id':job['job_id'],'map_html':'','map_status':'Peta belum tersedia pada job ini.'}
        for table in ('traffic_counts','area_results','ppac_results'):
            # Select explicit schema: additive metadata is visible, unrelated columns are excluded.
            order='video_id, category, direction, evidence_level' if table=='traffic_counts' else 'created_at'
            selection=', '.join(SCHEMAS[table]);source=f'`{d}.{table}`'
            if table=='traffic_counts':
                selection=', '.join('c.'+k for k in SCHEMAS[table])+', v.day_group, v.session'
                source=f'`{d}.traffic_counts` c LEFT JOIN `{d}.traffic_videos` v USING(job_id,target_id,video_id)'
            rows=self.query(f"SELECT {selection} FROM {source} WHERE target_id=@target_id AND job_id=@job_id ORDER BY {order} LIMIT 1001",
                            target_id=target_id,job_id=job['job_id'])
            if len(rows)>1000:result['truncated']=True
            result[table]=[{k:(json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(dict,list)) else v) for k,v in row.items()} for row in rows[:1000]]
        areas=result['area_results']
        if areas and areas[0].get('map_html_uri'):
            try:
                result['map_html']=self.map_html(job,areas[0])
                result['map_status']='Peta Folium/Esri dari artefak hasil terverifikasi.'
            except Exception as exc:
                result['map_status']='Peta gagal dibuka ('+type(exc).__name__+'); tabel BQ tetap tersedia.'
        result['display']={}
        if job.get('manifest_uri'):
            try:
                manifest=json.loads(self.verified_bytes(job,job['manifest_uri'],job['manifest_sha256'],8*1024**2))
                matches=[e for e in manifest['files'] if e['object'].endswith('/presentation/display-tables.json')]
                if len(matches)==1:
                    e=matches[0];result['display']=json.loads(self.verified_bytes(job,'gs://'+self.destination.bucket+'/'+e['object'],e['sha256'],8*1024**2))
            except Exception:result['map_status']+=' Tabel detail Area belum tersedia/terverifikasi.'
        return result

    def verified_bytes(self,job,uri,digest,limit):
        prefix=f"gs://{self.destination.bucket}/jobs/{job['target_id']}/{job['period_id']}/{job['job_id']}/"
        if not uri.startswith(prefix) or '..' in uri.split('/') or not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Referensi artefak tidak valid.')
        blob=self.storage.bucket(self.destination.bucket).blob(uri[len('gs://'+self.destination.bucket+'/'):]);blob.reload(timeout=30)
        if not blob.size or blob.size>limit:raise ValueError('Artefak terlalu besar.')
        raw=blob.download_as_bytes(if_generation_match=int(blob.generation),timeout=60,checksum='crc32c')
        if len(raw)>limit or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Checksum artefak berubah.')
        return raw

    def map_html(self,job,area):
        prefix=f"gs://{self.destination.bucket}/jobs/{job['target_id']}/{job['period_id']}/{job['job_id']}/engines/area/"
        uri=area['map_html_uri'];digest=area.get('map_html_sha256','')
        if not uri.startswith(prefix) or '..' in uri.split('/') or not re.fullmatch('[a-f0-9]{64}',digest):
            raise ValueError('Referensi peta bukan artefak job ini.')
        name=uri[len('gs://'+self.destination.bucket+'/'):]
        blob=self.storage.bucket(self.destination.bucket).blob(name);blob.reload(timeout=30)
        if not blob.size or blob.size>MAX_HTML_BYTES:raise ValueError('Ukuran peta melampaui batas viewer.')
        raw=blob.download_as_bytes(if_generation_match=int(blob.generation),timeout=60,checksum='crc32c')
        if len(raw)>MAX_HTML_BYTES or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Checksum peta berbeda.')
        # Scripts execute in an opaque-origin iframe, never in the Gradio parent origin.
        return '<iframe title="Area Coverage Folium Esri" sandbox="allow-scripts" referrerpolicy="no-referrer" style="width:100%;height:680px;border:0" srcdoc="'+escape(raw.decode('utf-8'),quote=True)+'"></iframe>'
