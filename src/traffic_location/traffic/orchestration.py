"""Inference runs in one fresh process per job; no tracker globals are shared."""
import os,subprocess,sys,tempfile,shutil
from pathlib import Path
from ..artifacts import read,require,semantic_hash

def fresh_inference(request_path,output,*,python_executable):
 output=Path(output).resolve();require(not output.exists(),'Immutable inference output required')
 output.parent.mkdir(parents=True,exist_ok=True)
 stage=Path(tempfile.mkdtemp(prefix='.inference-',dir=output.parent))
 try:
  # Keep the worker output nonexistent until its processing has succeeded.
  with (stage/'worker.log').open('w') as log:
   completed=subprocess.run([str(python_executable),'-B','-m','traffic_location.traffic.inference_worker',str(Path(request_path).resolve()),str(stage/'worker')],
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[2])},stdout=log,stderr=subprocess.STDOUT)
  require(completed.returncode==0,'Inference worker failed; no finalized result was published')
  value=read(stage/'worker/result.json.gz')
  require(value['status']=='SUCCEEDED' and value['request_fingerprint']==semantic_hash(read(request_path)),'Worker request/result mismatch')
  require(value['records_semantic_sha256']==semantic_hash(value['records']),'Worker records integrity mismatch')
  shutil.move(stage/'worker/result.json.gz',stage/'result.json.gz');(stage/'worker').rmdir()
  require(not output.exists(),'Output appeared while inference ran');stage.rename(output)
  return value
 finally:
  if stage.exists():shutil.rmtree(stage)
