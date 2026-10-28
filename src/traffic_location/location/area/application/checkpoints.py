"""Per-job diagnostic checkpoints; never interpreted as finalized results."""
import os,time
from ....artifacts import write

def record(root,stage,status,**detail):
    path=root/'checkpoint.json';temp=path.with_suffix('.partial')
    from ....artifacts import read
    now=time.time();old={}
    try:old=read(path)
    except (OSError,ValueError):pass
    started=old.get('stage_started_epoch',now) if old.get('stage')==stage else now
    events=(old.get('events',[])+[{'stage':stage,'status':status,'at':now,'duration_seconds':max(0,now-started)}])[-100:]
    write(temp,{'events':events,'schema':'area_checkpoint_v1','stage':stage,'status':status,'pid':os.getpid(),'updated_epoch':now,'stage_started_epoch':started,**detail})
    os.replace(temp,path)
