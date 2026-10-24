"""Readable annotation notebook, CPU only, consuming completed GPU results."""
from pathlib import Path
import json,uuid
ROOT=Path(__file__).resolve().parents[1]
def main():
 cells=[]
 def add(kind,s):cells.append({'cell_type':kind,'id':uuid.uuid4().hex[:8],'metadata':{},'source':s.splitlines(True),**({'execution_count':None,'outputs':[]} if kind=='code' else {})})
 add('markdown','# T7SL — full-frame annotated MP4 review\nThis run reads completed8-video measurements and counting results. It performs no new detector, tracker, ReID or counting. CPU rendering only. Each source frame is verified and written to H264; encoded output is fully decoded for verification.')
 add('code',"from pathlib import Path\nimport os,sys,json,subprocess\nROOT=Path('/kaggle/working/t7sl_annotation_source');ROOT.mkdir(exist_ok=False);os.chdir(ROOT)\n")
 files=[ROOT/'src/traffic_location/__init__.py',ROOT/'src/traffic_location/artifacts.py',ROOT/'src/traffic_location/traffic/__init__.py',ROOT/'src/traffic_location/traffic/results.py',ROOT/'src/traffic_location/traffic/annotation.py',ROOT/'src/traffic_location/traffic/_kernel/__init__.py',ROOT/'src/traffic_location/traffic/_kernel/geometry.py',ROOT/'tools/render_t7sl_results.py']
 add('code','for name in '+repr([str(p.relative_to(ROOT).parent) for p in files])+':\n (ROOT/name).mkdir(parents=True,exist_ok=True)\n')
 for p in files:add('markdown','## '+str(p.relative_to(ROOT)));add('code','%%writefile '+str(Path('/kaggle/working/t7sl_annotation_source')/p.relative_to(ROOT))+'\n'+p.read_text().rstrip()+'\n')
 add('markdown','## Validate completed input results and full-source videos')
 add('code',"sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT))\nfrom traffic_location.artifacts import read,sha\nroots=[p.parent for p in Path('/kaggle/input').rglob('combined.json') if (p.parent/'jobs.json').exists()]\nassert len(roots)==1,roots\nPRODUCER=roots[0];summary=read(PRODUCER/'combined.json');assert summary['videos_completed']==8\nhits=list(Path('/kaggle/input').rglob('T7SL-WEEKDAY-PAGI.mp4'));assert len(hits)==1;VIDEO_ROOT=hits[0].parent\nprint('Producer:',PRODUCER,'Videos:',summary['videos_completed'])\nprint('Video source:',VIDEO_ROOT)\nsubprocess.run(['ffmpeg','-version'],check=True)\n")
 add('markdown','## Render all source frames and verify output\nMP4 includes raw IDs, category colors and label backgrounds, exact-frame rider union with parent raw BC, geometry+margin, category/direction pivot, accepted passage logs, measured/estimated and final pending/invalid. Panel is explicitly offline finalized. No accuracy claim.')
 add('code',"import cv2\ncv2.setNumThreads(1)\nfrom tools.render_t7sl_results import main\nOUTPUT=Path('/kaggle/working/results/t7sl_annotated_full_v1')\nreports=main(PRODUCER,VIDEO_ROOT,OUTPUT)\nprint('ALL ANNOTATED:',len(reports),'frames:',sum(r['frames_encoded'] for r in reports))\n")
 add('markdown','## Open output directly from Kaggle\nOpen Output → results/t7sl_annotated_full_v1/annotated/. Each MP4 has its own JSON audit. combined.csv/json preserve the producer counts. review.html is a standalone video index.')
 add('code',"import pandas as pd\nfrom IPython.display import display,FileLink\ndisplay(pd.read_csv(OUTPUT/'combined.csv'))\nfor report in reports:\n print(report['video_id'],report['frames_encoded'],'frames verified')\n display(FileLink(str(OUTPUT/'annotated'/(report['video_id']+'.mp4'))))\n")
 nb={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},'cells':cells}
 packet=ROOT/'results/t7sl_modular/annotation_submission';packet.mkdir(parents=True,exist_ok=True);name='10b_t7sl_full_annotation.ipynb'
 (packet/name).write_text(json.dumps(nb));(ROOT/'notebooks'/name).write_text(json.dumps(nb))
 metadata={'id':'chrisbiran/t7sl-annotated-full-review','title':'T7SL annotated full review','code_file':name,'language':'python','kernel_type':'notebook','is_private':True,'enable_gpu':False,'enable_tpu':False,'enable_internet':False,'dataset_sources':['chrisbiran/t7sl-traffic-videos'],'kernel_sources':['chrisbiran/t7sl-traffic-counter-readable'],'competition_sources':[],'docker_image':'gcr.io/kaggle-private-byod/python@sha256:9a6bcfda6d03b2cd9aa347ee8c1bae62043328ed0f4afe9bda014e4f8bbf9435'}
 (packet/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2));print('Readable annotation notebook',len(cells),'cells')
if __name__=='__main__':main()
