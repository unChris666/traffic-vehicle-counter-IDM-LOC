"""Local engine CLI. The caller explicitly selects runtime, input and operation."""
import argparse,json,sys
from pathlib import Path
from .artifacts import read
from .persistence import publish,reopen_traffic,verify_manifest

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('operation',choices=['traffic','location-selection','location-recount','reopen','fresh-inference'])
 parser.add_argument('--request');parser.add_argument('--root',default='.')
 parser.add_argument('--output',required=True)
 parser.add_argument('--python',dest='python_executable',default=sys.executable,help='Explicit isolated inference worker runtime')
 args=parser.parse_args(argv)
 try:
  if args.operation=='reopen':
   manifest=verify_manifest(args.output)
   if manifest.get('metadata',{}).get('engine')=='traffic':value=reopen_traffic(args.output)
   else:value=read(Path(args.output)/'result.json')
   print(json.dumps(value,ensure_ascii=False));return 0
  if not args.request:raise ValueError('--request required')
  request=read(args.request)
  if args.operation=='traffic':
   from .traffic.pipeline import run
   value=run(request,root=args.root)
   files={'result.json':value['result'],'native.json.gz':value['native'],'adapter_audit.json':value['adapter_audit'],'request.json':request}
   engine='traffic'
  elif args.operation=='fresh-inference':
   from .traffic.orchestration import fresh_inference
   value=fresh_inference(args.request,args.output,python_executable=args.python_executable)
   print(json.dumps({'execution_status':value['status'],'frames':value['frames'],'output':str(args.output)}));return 0
  else:
   from .location.engine import run_selection,run_recount
   value=(run_selection if args.operation=='location-selection' else run_recount)(request,root=args.root)
   files={'result.json':value,'request.json':request};engine='location'
  manifest=publish(args.output,files,metadata={'engine':engine,'operation':args.operation})
  print(json.dumps({'execution_status':'SUCCEEDED','output':str(Path(args.output).resolve()),'artifacts':len(manifest['files'])}))
  return 0
 except (ValueError,OSError,KeyError,ImportError) as exc:
  print(json.dumps({'execution_status':'FAILED','error':str(exc)}),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
