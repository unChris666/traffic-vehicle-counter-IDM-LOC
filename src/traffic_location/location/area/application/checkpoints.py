"""Per-job diagnostic checkpoints; never interpreted as finalized results."""
import os
from ....artifacts import write

def record(root,stage,status,**detail):
    path=root/'checkpoint.json';temp=path.with_suffix('.partial')
    write(temp,{'schema':'area_checkpoint_v1','stage':stage,'status':status,**detail})
    os.replace(temp,path)
