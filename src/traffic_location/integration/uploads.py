"""User uploads: immutable source staging, full decoder count and reviewed geometry.

No detector/tracker inference and no provider writes happen in this module.
"""
from copy import deepcopy
from pathlib import Path
import json
import math
import shutil
import subprocess
import tempfile
import struct
from ..artifacts import read,write,sha,semantic_hash
from .contracts import need

DAYS=('weekday','weekend')
SESSIONS=('pagi','siang','sore','malam','tengah_malam','dini_hari','subuh')
DIRECTIONS=('A_TO_B mendekat; B_TO_A menjauh','A_TO_B menjauh; B_TO_A mendekat')
MAX_FILE_BYTES=1024**3
MAX_BATCH_BYTES=2*1024**3
MAX_FILES=14


def inspect_video(path,preview,*,runner=subprocess.run):
    command=['ffprobe','-v','error','-protocol_whitelist','file,pipe','-select_streams','v:0',
             '-show_entries','stream=width,height,avg_frame_rate,duration:format=duration','-of','json',str(path)]
    result=runner(command,capture_output=True,text=True,check=True,timeout=30)
    value=json.loads(result.stdout);need(len(value.get('streams',[]))==1,'VIDEO_STREAM_INVALID','Video tidak memiliki stream gambar yang dapat dibaca.')
    stream=value['streams'][0];width,height=int(stream['width']),int(stream['height'])
    numerator,denominator=map(int,stream['avg_frame_rate'].split('/'))
    need(numerator>0 and denominator>0,'VIDEO_FPS_INVALID','FPS video tidak diketahui atau tidak valid.')
    fps=numerator/denominator
    duration=float(stream.get('duration',value.get('format',{}).get('duration','nan')))
    need(width>0 and height>0 and width*height<=33554432 and math.isfinite(fps) and fps>0 and math.isfinite(duration) and duration>0,
         'VIDEO_METADATA_INVALID','Resolusi, FPS, atau durasi video tidak valid.')
    counted=runner(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-threads','1','-select_streams','v:0',
                    '-count_frames','-show_entries','stream=nb_read_frames','-of','json',str(path)],
                   capture_output=True,text=True,check=True,timeout=300)
    frames=int(json.loads(counted.stdout)['streams'][0]['nb_read_frames'])
    need(frames>0,'VIDEO_FRAMES_INVALID','Tidak ada frame video yang berhasil dibaca.')
    runner(['ffmpeg','-v','error','-protocol_whitelist','file,pipe','-threads','1','-i',str(path),'-frames:v','1','-y',str(preview)],
           capture_output=True,check=True,timeout=60)
    need(Path(preview).is_file(),'VIDEO_PREVIEW_MISSING','Pratinjau video gagal dibuat.')
    with Path(preview).open('rb') as image:header=image.read(24)
    need(len(header)==24 and header.startswith(b'\x89PNG\r\n\x1a\n'),'VIDEO_PREVIEW_INVALID','Pratinjau PNG tidak valid.')
    actual_width,actual_height=struct.unpack('>II',header[16:24])
    need((actual_width,actual_height) in ((width,height),(height,width)),'VIDEO_ORIENTATION_UNSUPPORTED','Orientasi tampilan video belum didukung.')
    return {'width':actual_width,'height':actual_height,'coded_width':width,'coded_height':height,'decoded_frames':frames,'fps':fps,
            'duration_seconds':duration,'inspection':'FFPROBE_FULL_DECODE_COUNT_NO_RESAMPLING'}


def prepare(files,root,template,*,inspector=inspect_video):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    paths=[Path(p) if isinstance(p,(str,Path)) else Path(p.name) for p in (files or [])]
    need(0<len(paths)<=MAX_FILES,'UPLOAD_COUNT_INVALID',f'Upload 1–{MAX_FILES} video.')
    need(all(p.is_file() and not p.is_symlink() and 0<p.stat().st_size<=MAX_FILE_BYTES for p in paths),
         'UPLOAD_SIZE_INVALID','Video harus berupa file biasa, maksimal 1 GiB per file.')
    need(sum(p.stat().st_size for p in paths)<=MAX_BATCH_BYTES,'UPLOAD_BATCH_TOO_LARGE','Total upload maksimal 2 GiB per batch.')
    need(shutil.disk_usage(root).free>sum(p.stat().st_size for p in paths)+64*1024**2,
         'UPLOAD_DISK_FULL','Ruang kerja tidak cukup untuk menyalin video; hasil lama tetap disimpan.')
    rows=[];seen=set()
    for path in paths:
        digest=sha(path)
        need(digest not in seen,'UPLOAD_DUPLICATE','Video yang sama diunggah lebih dari sekali.');seen.add(digest)
        folder=root/digest;folder.mkdir(exist_ok=True)
        suffix=path.suffix.lower();need(suffix in ('.mp4','.mov','.mkv','.avi','.webm','.m4v'),
                                      'UPLOAD_FORMAT_INVALID','Gunakan MP4, MOV, MKV, AVI, WEBM, atau M4V.')
        target=folder/('source'+suffix);preview=folder/'first-frame.png';probe=folder/'inspection.json'
        if not target.exists():
            with tempfile.NamedTemporaryFile(dir=folder,prefix='.source-',delete=False) as temporary:
                temp=Path(temporary.name)
            try:
                shutil.copyfile(path,temp);need(sha(temp)==digest,'UPLOAD_CHANGED','Isi upload berubah saat disalin.');temp.replace(target)
            finally:temp.unlink(missing_ok=True)
        need(sha(target)==digest,'UPLOAD_CHANGED','Checksum video tersimpan berubah.')
        if probe.exists() and preview.exists():metadata=read(probe)
        else:
            metadata=inspector(target,preview);write(probe,metadata)
        draft={'draft_id':'upload-'+digest[:32],'status':'DRAFT_REQUIRES_PER_VIDEO_REVIEW',
               'source_video':{'sha256':digest,'filename':path.name},
               'normalized':deepcopy(template['normalized'])}
        rows.append({'id':'upload_'+digest[:32],'filename':path.name,'path':str(target),'preview':str(preview),
                     'sha256':digest,**metadata,'inspection_ref':{'path':str(probe),'sha256':sha(probe)},'geometry':draft,'day':None,'session':None,
                     'direction':DIRECTIONS[0],'reviewed':False})
    need(len({r['id'] for r in rows})==len(rows),'UPLOAD_ID_CONFLICT','Identitas upload tidak unik.')
    return rows


def find(rows,video_id):
    matches=[r for r in rows if r['id']==video_id]
    need(len(matches)==1,'UPLOAD_NOT_SELECTED','Pilih satu video untuk ditinjau.');return matches[0]


def render(row,root):
    from PIL import Image,ImageDraw
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    # The displayed image retains native dimensions; Gradio select indexes use these pixels.
    with Image.open(row['preview']) as source:image=source.convert('RGB')
    need(image.size==(row['width'],row['height']),'PREVIEW_DIMENSIONS_CHANGED','Ukuran pratinjau tidak sesuai video.')
    draw=ImageDraw.Draw(image);w,h=image.size;n=row['geometry']['normalized']
    for key,color,label in [('side_a_polygon','#00d9ff','A'),('side_b_polygon','#ffba00','B')]:
        points=[(p[0]*w,p[1]*h) for p in n[key]]
        if len(points)>1:draw.line(points+([points[0]] if len(points)>2 else []),fill=color,width=3)
        for i,p in enumerate(points):draw.ellipse((p[0]-4,p[1]-4,p[0]+4,p[1]+4),fill=color);draw.text(p,f'{label}{i+1}',fill=color)
    points=[(p[0]*w,p[1]*h) for p in n['line'].values() if p is not None]
    if len(points)==2:draw.line(points,fill='#ff4050',width=4)
    for i,p in enumerate(points):draw.text(p,f'L{i+1}',fill='#ff4050')
    output=root/(semantic_hash({'id':row['id'],'geometry':n})+'.png');image.save(output)
    return str(output)


def edit(rows,video_id,component,*,point=None,clear=False):
    rows=deepcopy(rows);row=find(rows,video_id);n=row['geometry']['normalized']
    need(component in ('Garis','Polygon A','Polygon B'),'GEOMETRY_COMPONENT_INVALID','Pilih bagian geometri.')
    if clear:
        if component=='Garis':n['line']={'P1':None,'P2':None}
        else:n['side_a_polygon' if component=='Polygon A' else 'side_b_polygon']=[]
    else:
        need(isinstance(point,(tuple,list)) and len(point)==2,'GEOMETRY_POINT_INVALID','Klik titik pada pratinjau.')
        x,y=point;need(type(x) in (int,float) and type(y) in (int,float) and
                      math.isfinite(x) and math.isfinite(y) and 0<=x<row['width'] and 0<=y<row['height'],
                      'GEOMETRY_POINT_INVALID','Titik berada di luar gambar.')
        p=[x/row['width'],y/row['height']]
        if component=='Garis':
            key=next((k for k in ('P1','P2') if n['line'][k] is None),None)
            need(key is not None,'GEOMETRY_LINE_FULL','Garis sudah memiliki dua titik. Tekan Ulangi bagian untuk mengganti.');n['line'][key]=p
        else:
            points=n['side_a_polygon' if component=='Polygon A' else 'side_b_polygon']
            need(len(points)<64,'GEOMETRY_TOO_MANY_POINTS','Maksimal 64 titik per polygon.');points.append(p)
    row['reviewed']=False;row.pop('geometry_ref',None);return rows


def review(rows,video_id,day,session,direction,confirmed,root):
    from ..traffic.adapters.video_input import load_geometry
    from ..traffic._kernel.passage import _side_signs
    rows=deepcopy(rows);row=find(rows,video_id)
    need(confirmed is True,'GEOMETRY_REVIEW_REQUIRED','Konfirmasi geometri dan arah untuk video ini.')
    need(day in DAYS and session in SESSIONS and direction in DIRECTIONS,'VIDEO_SLOT_REQUIRED','Pilih hari, sesi, dan arah video.')
    need(sha(row['path'])==row['sha256'],'UPLOAD_CHANGED','Checksum video berubah sejak inspeksi.')
    draft=deepcopy(row['geometry']);draft.update(status='USER_REVIEWED',direction_semantics=direction)
    folder=Path(root);folder.mkdir(parents=True,exist_ok=True);path=folder/(semantic_hash(draft)+'.json')
    write(path,draft)
    try:
        geometry=load_geometry(path,{'video_sha256':row['sha256'],'width':row['width'],'height':row['height']});_side_signs(geometry)
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError('Geometri belum valid: '+str(exc)) from None
    row.update(geometry=draft,geometry_ref={'path':str(path),'sha256':sha(path)},day=day,session=session,
               direction=direction,reviewed=True)
    return rows


def inventory(rows,root):
    """Revalidate the server-side upload state at the execution boundary."""
    root=Path(root).resolve();result=[]
    need(isinstance(rows,list) and 0<len(rows)<=MAX_FILES,'UPLOAD_REQUIRED','Upload dan siapkan 1–14 video terlebih dahulu.')
    need(len({r['id'] for r in rows})==len(rows),'UPLOAD_ID_CONFLICT','Identitas upload tidak unik.')
    need(len({r['sha256'] for r in rows})==len(rows),'UPLOAD_DUPLICATE','Video sumber tidak boleh berulang.')
    for r in rows:
        need(r.get('reviewed') is True and r.get('day') in DAYS and r.get('session') in SESSIONS,
             'GEOMETRY_REVIEW_REQUIRED','Tinjau dan simpan geometri setiap video sebelum memproses.')
        for p in (Path(r['path']),Path(r['geometry_ref']['path']),Path(r['inspection_ref']['path'])):
            need(p.resolve().is_relative_to(root) and not p.is_symlink(),'UPLOAD_PATH_INVALID','Sumber upload di luar workspace.')
        need(sha(r['path'])==r['sha256'] and sha(r['geometry_ref']['path'])==r['geometry_ref']['sha256'],
             'UPLOAD_CHANGED','Video/geometri berubah sejak ditinjau.')
        need(sha(r['inspection_ref']['path'])==r['inspection_ref']['sha256'],'UPLOAD_INSPECTION_CHANGED','Inspeksi sumber berubah.')
        metadata=read(r['inspection_ref']['path'])
        need(all(metadata[k]==r[k] for k in ('width','height','decoded_frames','fps','duration_seconds')),'UPLOAD_METADATA_CHANGED','Metadata video berubah sejak inspeksi.')
        draft=read(r['geometry_ref']['path'])
        need(draft['source_video']['sha256']==r['sha256'] and draft['status']=='USER_REVIEWED',
             'UPLOAD_GEOMETRY_SOURCE_INVALID','Geometri tidak terikat ke video yang ditinjau.')
        slot={k:r[k] for k in ('sha256','width','height','decoded_frames','fps','duration_seconds','day','session','direction')}
        result.append({'id':r['id'],'status':'READY','path':r['path'],'filename':r['filename'],
                       'duration_seconds':r['duration_seconds'],'slot':slot,'geometry_ref':r['geometry_ref'],
                       'inspection_ref':r['inspection_ref'],'origin':'USER_UPLOAD_REVIEWED'})
    return result


def valid_inventory(rows,root):
    """Notebook16: isolate invalid/review-pending inputs, preserving each reason."""
    need(isinstance(rows,list) and len(rows)<=MAX_FILES,'UPLOAD_REQUIRED','Upload maksimal14 video.')
    valid=[];skipped=[];ids=set();hashes=set();slots=set()
    for row in rows:
        try:
            if isinstance(row,dict) and row.get('skip_reason'):
                raise ValueError(row['skip_reason'])
            item=inventory([row],root)[0]
            slot=(item['slot']['day'],item['slot']['session'])
            need(item['id'] not in ids and item['slot']['sha256'] not in hashes,'UPLOAD_DUPLICATE','Video sumber berulang.')
            need(slot not in slots,'DUPLICATE_SLOT','Satu video valid per hari/sesi; slot ini sudah terisi.')
            valid.append(item);ids.add(item['id']);hashes.add(item['slot']['sha256']);slots.add(slot)
        except (ValueError,KeyError,TypeError,OSError) as error:
            skipped.append({'video_id':row.get('id') if isinstance(row,dict) else None,
                            'status':'SKIPPED','code':row.get('skip_code',getattr(error,'code',type(error).__name__)) if isinstance(row,dict) else type(error).__name__,
                            'reason':str(error)[:500]})
    return valid,skipped
