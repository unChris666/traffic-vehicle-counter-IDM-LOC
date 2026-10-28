"""Bounded per-job Area evidence, separate from immutable numerical artifacts."""
from datetime import datetime,timezone
from pathlib import Path
import json
import time
import os
import zipfile
from .. import __version__
from ..artifacts import read,write
from .failure_details import details,safe


def stamp():
    return datetime.now(timezone.utc).isoformat()


class AreaTrace:
    def __init__(self,base,root,context):
        self.base=Path(base);self.root=Path(root);self.started=time.time()
        self.path=self.root/'area-trace.json'
        self.value={'schema_version':'area_trace_v1','package_version':__version__,
                    'context':context,'started_at':stamp(),'started_epoch':self.started,
                    'execution_status':'RUNNING','stage':'source_access','events':[]}
        self.mark('source_access')

    def save(self):
        self.value.update(updated_epoch=time.time(),pid=os.getpid())
        temporary=self.path.with_suffix('.partial')
        write(temporary,self.value);temporary.replace(self.path)

    def mark(self,stage):
        if self.value.get('stage')!=stage or 'stage_started_epoch' not in self.value:self.value['stage_started_epoch']=time.time()
        self.value['stage']=stage;self.value['events'].append({'stage':stage,'at':stamp()});self.save()

    def finish(self,result=None,error=None):
        self.value['finished_at']=stamp()
        if error is not None:
            self.value['execution_status']='FAILED' if isinstance(error,Exception) else 'INTERRUPTED'
            self.value['failure']=details(self.base,error,self.started)
        else:
            self.value['execution_status']='SUCCEEDED'
            job=result['jobs'][0];ref=job['result_ref']
            envelope=read(Path(ref['path'])/'result.json')
            self.value['result']={'result_ref':ref,'result_version':envelope['result_version'],
                'quality':job.get('quality'),'presentation_status':envelope.get('presentation_status'),
                'presentation_ref':envelope.get('presentation_ref')}
            self.mark('finished')
        self.save()


def latest_report(base):
    base=Path(base)
    traces=sorted((p for p in base.glob('runs/*/area/area-trace.json') if p.is_file() and not p.is_symlink()),key=lambda p:p.stat().st_mtime)
    trace=None;publication=None
    if traces:
        p=traces[-1]
        if p.stat().st_size<=1024**2:
            trace=read(p)
            if trace.get('schema_version')!='area_trace_v1':trace=None
            status=p.parent.parent/'publication-status.json'
            if status.is_file() and not status.is_symlink() and status.stat().st_size<=65536:
                saved=read(status)
                publication={k:saved[k] for k in ('status','code','message','job_id','manifest_uri','manifest_sha256','diagnostics') if k in saved}
    current_job=None;current_status=None;latest_root=None
    inputs=sorted(base.glob('runs/*/job-input.json'),key=lambda p:p.stat().st_mtime)
    if inputs and inputs[-1].is_file() and not inputs[-1].is_symlink() and inputs[-1].stat().st_size<=2*1024**2:
        try:
            current_job=read(inputs[-1]);latest_root=inputs[-1].parent
            if not isinstance(current_job,dict) or current_job.get('schema_version')!='job_input_v1':current_job=None
            status_path=latest_root/'job-status.json'
            if status_path.is_file() and status_path.stat().st_size<=65536:
                current_status=read(status_path)
                if current_status.get('status')=='RUNNING' and current_status.get('pid'):
                    from .job_status import observation
                    seen=observation(current_status['pid']);current_status['process_observation']=seen
                    if seen['process_alive'] is False:current_status['observed_status']='INTERRUPTED_PROCESS_EXITED'
        except (OSError,ValueError):pass
    started=inputs[-1].stat().st_mtime if current_job else trace.get('started_epoch',0) if trace else 0
    source_status=None
    if latest_root:
        source_path=latest_root/'area/source-preparation-status.json'
        if source_path.is_file() and source_path.stat().st_size<=65536:
            try:source_status=read(source_path)
            except (OSError,ValueError):pass
    evidence=details(base,RuntimeError('Diagnosis workspace; tidak menjalankan engine.'),started)
    return {'schema_version':'area_diagnostic_report_v1','package_version':__version__,
            'generated_at':stamp(),'source_preparation_status':source_status,'current_job':current_job,'current_job_status':current_status,
            'area_trace_is_latest_job':not current_job or bool(traces and traces[-1].parent.parent==latest_root),'trace':trace,'publication':publication,'diagnostics':evidence,
            'scope':'Latest job input/status and latest Area trace in this target workspace; no credentials, source rows, video or inference included.'}


def export_report(base,output):
    """Export only a bounded diagnostic document, never arbitrary workspace files."""
    report=latest_report(base)
    def cleaned(v):
        if isinstance(v,str):return safe(v)
        if isinstance(v,list):return [cleaned(x) for x in v]
        if isinstance(v,dict):return {k:('[REDACTED]' if k.lower() in ('private_key','access_token','refresh_token','authorization') else cleaned(x)) for k,x in v.items()}
        return v
    payload=json.dumps(cleaned(report),ensure_ascii=False,indent=2).encode()
    if len(payload)>2*1024**2:raise ValueError('DIAGNOSTIC_REPORT_TOO_LARGE')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('area-diagnostic-report.json',payload)
    return output
