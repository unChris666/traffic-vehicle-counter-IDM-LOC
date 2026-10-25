"""Read-only baseline export from the successful Kaggle session; no analysis.

Run this cell after the successful notebook. All files remain private outputs;
no credentials are serialized, and no detector/routing/allocation is executed.
"""
from pathlib import Path
import hashlib
import json
import shutil


def collect(namespace):
    if namespace.get('STAGES',{}).get('output',{}).get('status')!='SUCCEEDED':
        print('BASELINE EXPORT BLOCKED: output not successful; no recompute attempted')
        return None
    output=Path('/kaggle/working/area_modular_baseline_export');output.mkdir(exist_ok=True)
    archive=namespace.get('archive');receipt=namespace.get('GCS_RECEIPT')
    if archive is None or receipt is None:
        raise RuntimeError('BASELINE_EXPORT_REQUIRES_COMPLETED_OUTPUT_SESSION: no recompute attempted')
    archive=Path(archive)
    def digest(p):
        h=hashlib.sha256()
        with Path(p).open('rb') as f:
            for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
        return h.hexdigest()
    if not archive.is_file() or digest(archive)!=receipt['sha256']:
        raise RuntimeError('BASELINE_EXPORT_ARCHIVE_MISMATCH')
    import zipfile
    with zipfile.ZipFile(archive) as z:
        config=json.loads(z.read('job_config.json'))
        if config['MARKET_CONFIG']['allocation_requirements'].get('attractor_gate')!='RADIAL_ATTRACTOR_400M_NO_POI_ROUTING':
            raise RuntimeError('BASELINE_EXPORT_NOT_V5')
        if z.testzip() is not None:raise RuntimeError('BASELINE_EXPORT_CORRUPT_ZIP')
    target=output/'baseline.zip'
    if target.exists():
        if digest(target)!=receipt['sha256']:raise RuntimeError('BASELINE_EXPORT_TARGET_CONFLICT')
    else:shutil.copyfile(archive,target)
    if digest(target)!=receipt['sha256']:raise RuntimeError('BASELINE_EXPORT_COPY_CHANGED')
    # Explicit allowlist: credentials and session globals cannot enter receipt.
    record={k:receipt[k] for k in ['manifest_uri','object','generation','bytes','sha256','crc32c']}
    record['schema_version']='area_baseline_export_v1'
    (output/'receipt.json').write_text(json.dumps(record,indent=2))
    print('BASELINE EXPORT READY:',output)
    print('No source download, routing, allocation or GPU processing performed.')
    from IPython.display import display,FileLink
    display(FileLink(str(target)));display(FileLink(str(output/'receipt.json')))
    return record


if __name__=='__main__':collect(globals())
