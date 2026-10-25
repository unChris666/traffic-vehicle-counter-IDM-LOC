"""Area retained-artifact CLI; fresh domain replay is not released yet."""
import argparse
import json
from .facade import freeze,reopen
from ...artifacts import read

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['freeze','reopen']);p.add_argument('--request',required=True)
    p.add_argument('--output');args=p.parse_args(argv)
    if args.operation=='freeze' and not args.output:p.error('--output required for freeze')
    q=read(args.request)
    if q.get('operation')!=args.operation:raise ValueError('AREA_OPERATION_MISMATCH')
    value=freeze(q,args.output) if args.operation=='freeze' else reopen(q)
    print(json.dumps({k:v for k,v in value.items() if k not in {'rows','capacity'}},ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
