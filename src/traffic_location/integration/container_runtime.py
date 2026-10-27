"""Prebuilt container entrypoint and fail-fast verification. Never installs software."""
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .contracts import need
from .kaggle_runtime import SCIENTIFIC

TRAFFIC={'ultralytics':'8.4.175','lap':'0.5.13','onnx':'1.20.1','onnxruntime-gpu':'1.24.4',
         'torch':'2.7.1','torchvision':'0.22.1'}

def verify_runtime(engine,*,require_gpu):
    need(engine in ('area','traffic'),'ENGINE_INVALID','Engine tidak dikenal.')
    versions=SCIENTIFIC if engine=='area' else TRAFFIC
    for name,version in versions.items():
        try:found=importlib.metadata.version(name).split('+')[0]
        except importlib.metadata.PackageNotFoundError:found=None
        need(found==version,'BUNDLED_DEPENDENCY_MISMATCH','Image perlu dibangun ulang: '+name+' harus '+version+'.')
    need(all(shutil.which(b) for b in ('ffmpeg','ffprobe','osmium')),'BUNDLED_BINARY_MISSING','Binary sistem belum tersedia pada image.')
    if engine=='area':
        core=os.environ.get('LI_CORE_PYTHON','/usr/bin/python3')
        subprocess.run([core,'-c','from osgeo import gdal;import pyproj;assert int(gdal.VersionInfo("VERSION_NUM"))>=3070000'],check=True,timeout=60)
        command='import numpy,pandas,shapely,pyproj,osmnx,geopandas,folium,osmium,cupy;from google.cloud import bigquery,storage'
        if require_gpu:command+=';assert cupy.cuda.runtime.getDeviceCount()>0;assert int(cupy.sum(cupy.arange(4)).get())==6'
        result={'status':'READY','core_python':core,'osmium':shutil.which('osmium')}
    else:
        command='import torch,ultralytics,onnxruntime as o;o.preload_dlls()'
        if require_gpu:command+=';assert torch.cuda.is_available();assert "CUDAExecutionProvider" in o.get_available_providers();assert torch.ones(1,device="cuda").sum().item()==1'
        result={'status':'READY','python':sys.executable,'device':'cuda:0'}
    subprocess.run([sys.executable,'-c',command],check=True,timeout=120)
    return result


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');parser.add_argument('--gpu',action='store_true')
    args=parser.parse_args()
    if args.verify:
        for engine in ('area','traffic'):verify_runtime(engine,require_gpu=args.gpu)
        print('BUNDLED_RUNTIME_OK'+(' GPU' if args.gpu else ' CPU_IMPORTS_ONLY'));return
    need(os.environ.get('LI_RUNTIME_MODE')=='bundled','RUNTIME_MODE_INVALID','Container memerlukan bundled runtime.')
    # Hypercorn accepts h2c for Cloud Run end-to-end HTTP/2 (large uploads).
    import asyncio
    import gradio as gr
    from fastapi import FastAPI
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    from .gradio_app import build_app
    base=Path(os.environ.get('LI_WORKSPACE','/data'))
    blocks,controller=build_app(base/'system',os.environ.get('LI_CONFIG_ROOT','/app/config'),input_root=base/'input')
    server=FastAPI()
    @server.get('/healthz')
    def health():return {'status':'UI_READY','runtime':'bundled','engine_started':False}
    server=gr.mount_gradio_app(server,blocks,path='/',allowed_paths=[str(controller.exports)],max_file_size='1024mb',show_error=False)
    config=Config();config.bind=['0.0.0.0:'+os.environ.get('PORT','8080')]
    config.accesslog='-';config.errorlog='-';config.graceful_timeout=8
    asyncio.run(serve(server,config))

if __name__=='__main__':main()
