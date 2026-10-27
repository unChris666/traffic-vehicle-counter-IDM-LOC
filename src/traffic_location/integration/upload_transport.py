"""Interrupted browser uploads are request failures, not engine failures."""
from pathlib import Path
from urllib.parse import urlsplit
import hashlib,os,shutil,tempfile
from .uploads import MAX_FILE_BYTES

async def disconnected_upload(request,error):
    from starlette.responses import JSONResponse
    return JSONResponse({'detail':'Upload terputus sebelum selesai. Ulangi satu video, atau gunakan referensi GCS/Kaggle Input pada slot yang sama. Engine belum dijalankan.'},status_code=400)

def resolve_reference(value,root,client_factory):
    value=value.strip();root=Path(root);root.mkdir(parents=True,exist_ok=True)
    if not value.startswith('gs://'):
        path=Path(value).resolve()
        allowed=('/content/videos',) if os.environ.get('LI_RUNTIME_PLATFORM')=='colab' else ('/kaggle/input','/kaggle/working/videos')
        if not any(path.is_relative_to(Path(p)) for p in allowed):
            raise ValueError('Path video harus di '+ ' atau '.join(allowed)+'.')
        if not path.is_file() or path.stat().st_size>MAX_FILE_BYTES:raise ValueError('File tidak tersedia atau melebihi 1 GiB.')
        return str(path)
    uri=urlsplit(value)
    if uri.netloc not in (os.environ.get('LI_ARTIFACT_BUCKET','aretfak-location-intelligence'),'feeder-location-intelligent') or not uri.path.strip('/') or uri.query or uri.fragment:
        raise ValueError('Gunakan object video pada bucket aplikasi, tanpa query/fragment.')
    blob=client_factory().bucket(uri.netloc).blob(uri.path.lstrip('/'));blob.reload(timeout=60)
    if not blob.size or blob.size>MAX_FILE_BYTES:raise ValueError('Ukuran video GCS harus 1 byte–1 GiB.')
    if shutil.disk_usage(root).free<blob.size+64*1024**2:raise ValueError('Ruang staging video tidak cukup.')
    folder=root/hashlib.sha256((value+str(blob.generation)).encode()).hexdigest();folder.mkdir(exist_ok=True)
    target=folder/Path(uri.path).name
    if not target.exists():
        fd,temp=tempfile.mkstemp(dir=folder,prefix='.download-');os.close(fd)
        try:
            blob.download_to_filename(temp,if_generation_match=int(blob.generation),checksum='crc32c',timeout=900)
            Path(temp).replace(target)
        finally:Path(temp).unlink(missing_ok=True)
    return str(target)
