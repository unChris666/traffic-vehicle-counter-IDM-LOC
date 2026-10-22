import gzip,json
from collections import defaultdict
from pathlib import Path
r=Path('/workspace/traffic-vehicle-counter-IDM-LOC');p=r/'results/phase_9/20261020_QC_BV4_SIANG/unmatched'
cache=next(Path('/tmp/qc-donor').rglob('track_records.jsonl.gz'));windows={'begin':(0,360),'middle':(4380,4780),'late':(8620,9020)};tracks={k:defaultdict(list) for k in windows};records={}
with gzip.open(cache,'rt') as f:
 for line in f:
  j=json.loads(line);i=j['frame_index']
  for name,(s,e) in windows.items():
   if s<=i<=e:
    records[i]=j
    for o in j['emitted_tracks']:tracks[name][o['track_id']].append(o)
summary={}
for name,ts in tracks.items():
 summary[name]=[]
 for track,obs in ts.items():
  classes=sorted(set(o['class_name'] for o in obs))
  if set(classes)&{'car','truck','motorcycle','bus'}:
   first,last=obs[0],obs[-1];a,b=first['raw_bbox'],last['raw_bbox'];summary[name].append({'track':track,'first':first['frame_index'],'last':last['frame_index'],'n':len(obs),'classes':classes,'first_bc':[(a[0]+a[2])/2,a[3]],'last_bc':[(b[0]+b[2])/2,b[3]]})
(p/'evidence'/'mapping_candidates.json').write_text(json.dumps(summary,indent=2)+'\n');
for name,rows in summary.items():
 print(name)
 for x in rows:
  if x['last']-x['first']>=12 and x['n']>=6:print(x)
