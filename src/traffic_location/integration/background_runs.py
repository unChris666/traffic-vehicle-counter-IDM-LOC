"""Single prototype job runner, independent of browser/SSE request lifetime.

Memory holds only bounded UI snapshots. Disk/GCS receipts remain authoritative;
this is not a persistent queue or restart recovery service.
"""
import threading
from uuid import uuid4

class BackgroundRuns:
    def __init__(self):
        self.lock=threading.Lock();self.records={};self.active=None;self.latest=None

    def submit(self,factory):
        with self.lock:
            if self.active:
                r=self.records[self.active]
                return self.active,r['value'],True
            token=uuid4().hex
            # First event validates inputs and prepares local identity only.
            generator=iter(factory())
            try:first=next(generator)
            except StopIteration:raise ValueError('JOB_SUBMISSION_EMPTY') from None
            self.records[token]={'value':first,'revision':1,'done':False,'error':None}
            self.active=self.latest=token
            old=[k for k in self.records if k!=token and self.records[k]['done']]
            for key in old[:-19]:del self.records[key]
            thread=threading.Thread(target=self._run,args=(token,generator),name='prototype-job-'+token[:8],daemon=True)
            thread.start()
            return token,first,False

    def _run(self,token,generator):
        error=None
        try:
            for value in generator:
                with self.lock:
                    r=self.records[token];r.update(value=value,revision=r['revision']+1)
        except Exception as exc:
            from .failure_details import safe
            error=safe(exc)
        finally:
            try:
                close=getattr(generator,'close',None)
                if close:close()
            finally:
                with self.lock:
                    r=self.records[token];r.update(done=True,error=error,revision=r['revision']+1)
                    if self.active==token:self.active=None

    def snapshot(self,token):
        with self.lock:
            r=self.records.get(token)
            return dict(r) if r else None

    def current(self,*,completed=False):
        with self.lock:return self.active or (self.latest if completed else None)
