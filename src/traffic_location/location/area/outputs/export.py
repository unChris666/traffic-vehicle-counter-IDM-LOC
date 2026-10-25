"""Local immutable publication; renderer/transfer failures cannot mark success."""
from pathlib import Path
from ....persistence import verify_manifest
from ....artifacts import sha,write

def finalize(stage,output,metadata):
    files=[{'path':str(p.relative_to(stage)),'bytes':p.stat().st_size,'sha256':sha(p)}
           for p in sorted(stage.rglob('*')) if p.is_file() and p.name!='manifest.json']
    # Nested native manifests are artifacts too, not the publication manifest.
    for p in sorted(stage.rglob('manifest.json')):
        if p!=stage/'manifest.json':files.append({'path':str(p.relative_to(stage)),'bytes':p.stat().st_size,'sha256':sha(p)})
    write(stage/'manifest.json',{'schema_version':'engine_artifacts_v1','files':files,'metadata':metadata})
    verify_manifest(stage)
    if Path(output).exists():raise ValueError('AREA_OUTPUT_ALREADY_EXISTS')
    stage.rename(output)


def archive_result(root,archive):
    """Stream a verified result into deterministic ZIP; archive lives outside root."""
    import os,shutil,tempfile,zipfile,json,hashlib
    root=Path(root).resolve();archive=Path(archive).resolve()
    if archive.is_relative_to(root):raise ValueError('AREA_ARCHIVE_MUST_BE_OUTSIDE_RESULT')
    manifest=verify_manifest(root);expected={r['path']:r['sha256'] for r in manifest['files']}
    expected['manifest.json']=sha(root/'manifest.json')
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            if len(z.namelist())!=len(expected) or set(z.namelist())!=set(expected):raise ValueError('AREA_ARCHIVE_CONFLICT')
            for name,digest in expected.items():
                h=hashlib.sha256()
                with z.open(name) as source:
                    for block in iter(lambda:source.read(1024*1024),b''):h.update(block)
                if h.hexdigest()!=digest:raise ValueError('AREA_ARCHIVE_CHANGED')
        return archive
    archive.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.area-archive-',dir=archive.parent);os.close(fd)
    try:
        with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name in sorted(expected):
                info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                info.create_system=3;info.external_attr=0o600<<16
                with (root/name).open('rb') as source,z.open(info,'w',force_zip64=True) as target:
                    shutil.copyfileobj(source,target,1024*1024)
        if archive.exists():raise ValueError('AREA_ARCHIVE_APPEARED_DURING_BUILD')
        os.replace(temp,archive)
        return archive
    finally:
        Path(temp).unlink(missing_ok=True)
