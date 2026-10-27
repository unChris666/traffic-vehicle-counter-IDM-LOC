"""Bounded diagnostics from known worker logs; never copy credential payloads."""
import re
from pathlib import Path

def safe(text):
    text=re.sub(r'-----BEGIN[^\n]*PRIVATE KEY-----.*?-----END[^\n]*PRIVATE KEY-----','[REDACTED_KEY]',str(text),flags=re.S)
    text=re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~+/-]+',r'\1[REDACTED]',text)
    text=re.sub(r'(?i)(private_key|access_token|refresh_token|authorization)["\s:=]+[^\n]+',r'\1=[REDACTED]',text)
    return text[:1500]

def details(base,error,started=0):
    code=getattr(error,'code',None)
    if not isinstance(code,str):code=type(error).__name__
    result={'code':code,'message':safe(error),'evidence':[]}
    candidates=[]
    for pattern in ('area-setup.log','area-preparation.log','worker.log','failure.json'):
        candidates.extend(p for p in Path(base).rglob(pattern) if p.is_file() and p.stat().st_mtime>=started)
    for path in sorted(candidates,key=lambda p:p.stat().st_mtime)[-4:]:
        with path.open('rb') as stream:
            stream.seek(max(0,path.stat().st_size-65536));lines=stream.read().decode('utf-8',errors='replace').splitlines()
        matches=[line.strip() for line in lines if re.match(r'^(?:[\w.]+(?:Error|Exception)|RuntimeError|ValueError|Forbidden|NotFound|PermissionDenied|Unauthenticated|BadRequest|ServiceUnavailable|ERROR:|[A-Z][A-Z0-9_]{5,})',line.strip())]
        if matches:result['evidence'].append({'log':str(path.relative_to(base)),'errors':[safe(v) for v in matches[-4:]]})
    return result
