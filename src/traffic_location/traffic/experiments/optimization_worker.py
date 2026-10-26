"""Benchmark entry point for the shared model worker."""
import sys,json
from ...artifacts import read
from ..model_worker import execute

if __name__=="__main__":
 try:execute(read(sys.argv[1]),sys.argv[2])
 except Exception as error:
  print(json.dumps({"status":"FAILED","reason":str(error)}),file=sys.stderr);sys.exit(1)
