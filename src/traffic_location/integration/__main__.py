"""Run Area, Traffic and modular PPAC without UI."""
import argparse,json,sys
from ..artifacts import read
from .workflow import run,reopen,diagnostic

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['area','traffic','ppac','run','reopen'])
    p.add_argument('--request');p.add_argument('--root',default='.');p.add_argument('--output',required=True)
    a=p.parse_args(argv)
    try:
        if a.operation=='reopen':value=reopen(a.output)
        else:
            if not a.request:p.error('--request required')
            value=run(read(a.request),a.output,root=a.root,operation=a.operation)
        print(json.dumps({'execution_status':value['execution_status'],'result_version':value['result_version'],
                         'jobs':[{k:v for k,v in j.items() if k in ('id','execution_status','diagnostics')} for j in value['jobs']],
                         'ppac':{k:value['ppac'][k] for k in ('execution_status','std_total','diagnostics')}},ensure_ascii=False))
        return {'SUCCEEDED':0,'FAILED':1,'BLOCKED':2}[value['execution_status']]
    except Exception as exc:
        print(json.dumps({'execution_status':'FAILED','diagnostics':[diagnostic(exc,'WORKFLOW_INVALID')]},ensure_ascii=False),file=sys.stderr)
        return 1
if __name__=='__main__':raise SystemExit(main())
