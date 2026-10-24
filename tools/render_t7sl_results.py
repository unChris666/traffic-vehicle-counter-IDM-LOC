"""Render completed producer outputs. No detector/tracker/ReID/counting execution."""
from pathlib import Path
import json,gzip,shutil,concurrent.futures
from traffic_location.artifacts import read,write,sha,semantic_hash,require
from traffic_location.traffic.annotation import render

def main(producer,video_root,output):
 producer,video_root,output=map(Path,[producer,video_root,output]);require(not output.exists(),'Annotation revision output exists');output.mkdir(parents=True)
 combined=read(producer/'combined.json');jobs=read(producer/'jobs.json');require(combined['videos_completed']==8 and len(jobs)==8 and all(j['status']=='SUCCEEDED' for j in jobs),'Eight full-video results required')
 original_hash=semantic_hash(combined);shutil.copyfile(producer/'combined.json',output/'combined.json');shutil.copyfile(producer/'combined.csv',output/'combined.csv');shutil.copyfile(producer/'jobs.json',output/'jobs.json')
 def artifact(path):
  if path.exists():return path
  if path.suffix=='.gz' and path.with_suffix('').exists():return path.with_suffix('')
  raise ValueError('Missing producer artifact: '+str(path))
 def run(j):
  vid=j['video_id'];job=producer/'videos'/vid;native_path=artifact(job/'counting/native.json.gz');native=read(native_path);wrapper=read(job/'counting/result.json')
  require(semantic_hash(native)==wrapper['native_semantic_sha256'],'Native result semantic hash differs')
  measurement=artifact(job/'measurement/result.json.gz')
  if sha(measurement)!=native['source_identity']['records_sha256']:
   # Kaggle can expand gzip attachments. Reconstruct exact gzip from the original
   # JSON bytes in the pinned Python/zlib runtime, then require the original SHA.
   recovered=output/'recovered'/vid/'result.json.gz';recovered.parent.mkdir(parents=True,exist_ok=True);recovered.write_bytes(gzip.compress(measurement.read_bytes(),mtime=0))
   require(sha(recovered)==native['source_identity']['records_sha256'],'Original measurement bytes cannot be restored; do not weaken identity checks');measurement=recovered
  report=render(video_root/(vid+'.mp4'),measurement,native_path,job/'geometry.json',output/'annotated'/(vid+'.mp4'))
  require(report['frames_encoded']==j['frames'] and report['scope']=='FULL_VIDEO','Annotation incomplete')
  return report
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:reports=list(pool.map(run,jobs))
 require(semantic_hash(read(producer/'combined.json'))==original_hash,'Producer result changed')
 write(output/'annotation_manifest.json',{'status':'SUCCEEDED','videos':reports,'frames':sum(r['frames_encoded'] for r in reports),'inference_rerun':False,'counting_rerun':False,'source_combined_semantic_sha256':original_hash})
 import html
 cards=''.join('<h2>'+html.escape(r['video_id'])+'</h2><p>'+str(r['frames_encoded'])+' frames</p><video controls preload="none" width="960" src="annotated/'+html.escape(r['video_id'])+'.mp4"></video>' for r in reports)
 (output/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>T7SL annotated review</title><h1>Full-frame offline review</h1><p>Geometry provisional; measured and estimated separate. Source counts unchanged.</p>'+cards)
 return reports
