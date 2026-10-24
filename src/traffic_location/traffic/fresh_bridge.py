"""Source-linked fresh observations, without pretending they are notebook caches."""
from copy import deepcopy
import math
from ..artifacts import read,require,semantic_hash

def frames(path,source_identity,frame_count,*,audit=None):
 value=read(path)
 require(value['schema_version']=='fresh_inference_result_v1' and value['status']=='SUCCEEDED','Successful fresh measurement required')
 require(value['source_sha256']==source_identity['video_sha256'],'Fresh source video differs')
 require(value['records_semantic_sha256']==semantic_hash(value['records']),'Fresh measurement integrity differs')
 require(value['frames']==frame_count==len(value['records']),'Fresh source scope differs')
 meta=value['metadata'];require(all(meta[k]==source_identity[k] for k in ['width','height']),'Fresh dimensions differ')
 names={int(k):v for k,v in value['class_names'].items()}
 for index,row in enumerate(value['records']):
  require(row['frame_index']==index,'Fresh frames must be continuous from zero')
  seen=set();linked=set();observations=[]
  for obs in row['emitted_measurements']:
   track=obs['track_id'];di=obs['original_detection_index']
   require(type(track) is int and track>0 and track not in seen and type(di) is int and 0<=di<len(row['detections']) and di not in linked,'Repeated/invalid fresh source link')
   seen.add(track);linked.add(di)
   raw=row['detections'][di];require(obs['raw_detection']==raw and obs['observed'] is True and obs['emitted'] is True,'Fresh prediction or altered raw link')
   box=raw['bbox'];require(len(box)==4 and all(type(x) in (int,float) and math.isfinite(x) for x in box) and 0<=box[0]<box[2]<=meta['width'] and 0<=box[1]<box[3]<=meta['height'],'Invalid fresh bbox')
   require(type(raw['confidence']) in (int,float) and math.isfinite(raw['confidence']) and 0<=raw['confidence']<=1,'Invalid fresh confidence')
   category=names[raw['class_id']]
   if category not in {'person','motorcycle','car','truck','bus'}:continue
   observations.append({'frame_index':index,'track_id':track,'original_detection_index':di,
    'raw_bbox':deepcopy(box),'class_name':category,'class_id':raw['class_id'],'confidence':raw['confidence'],
    'observed':True,'emitted':True,'role':'unknown_person' if category=='person' else 'vehicle',
    'unit_id':f'track:{track}','episode_id':'unreviewed-fresh','association_verified':False,
    'measurement_provenance':'fresh_modular_detection_v1','source_ref':{'measurement_sha256':source_identity['records_sha256'],
     'source_pixel_sha256':row['source_pixel_sha256'],'frame_index':index,'original_detection_index':di}})
  yield {'frame_index':index,'observations':observations}
 if audit is not None:audit.update(format='fresh_v1',frames=frame_count,legacy_provenance_relabelled=False)
