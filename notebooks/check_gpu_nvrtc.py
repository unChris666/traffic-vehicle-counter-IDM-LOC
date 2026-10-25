"""Compile all embedded CUDA kernels to PTX without GPU or CuPy.

Requires standalone NVRTC library; this is compile validation, not device execution.
"""
import argparse,ast,ctypes,hashlib,json
from pathlib import Path

KERNELS=[('location_intelligent_gpu.py','CupyReachability','KERNEL','propagate'),
 ('location_intelligent_gpu_geometry.py','GpuGeometry','DISTANCE','distances'),
 ('location_intelligent_gpu_geometry.py','GpuGeometry','CLIP','polygon_lengths'),
 ('location_intelligent_gpu_geometry.py','GpuGeometry','PRIMITIVES','primitive_hits'),
 ('location_intelligent_gpu_weighted.py','CupyWeightedRouter','KERNEL','relax')]

def sources(root):
 for filename,classname,attribute,name in KERNELS:
  tree=ast.parse((root/filename).read_text())
  cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name==classname)
  node=next(node for node in cls.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==attribute for t in node.targets))
  yield filename,name,ast.literal_eval(node.value)

def compile_kernels(library,root,architectures=('compute_75',)):
 lib=ctypes.CDLL(str(library));program=ctypes.c_void_p
 lib.nvrtcCreateProgram.argtypes=[ctypes.POINTER(program),ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p]
 lib.nvrtcCompileProgram.argtypes=[program,ctypes.c_int,ctypes.POINTER(ctypes.c_char_p)]
 lib.nvrtcGetProgramLogSize.argtypes=[program,ctypes.POINTER(ctypes.c_size_t)];lib.nvrtcGetProgramLog.argtypes=[program,ctypes.c_char_p]
 lib.nvrtcGetPTXSize.argtypes=[program,ctypes.POINTER(ctypes.c_size_t)];lib.nvrtcDestroyProgram.argtypes=[ctypes.POINTER(program)]
 major=ctypes.c_int();minor=ctypes.c_int();lib.nvrtcVersion(ctypes.byref(major),ctypes.byref(minor))
 rows=[]
 for architecture in architectures:
  for filename,name,source in sources(root):
   handle=program();rc=lib.nvrtcCreateProgram(ctypes.byref(handle),source.encode(),(name+'.cu').encode(),0,None,None)
   if rc:raise RuntimeError('NVRTC_CREATE_PROGRAM_FAILED:'+str(rc))
   try:
    options=[b'--std=c++11',b'--fmad=false',('--gpu-architecture='+architecture).encode()]
    compiled=lib.nvrtcCompileProgram(handle,len(options),(ctypes.c_char_p*len(options))(*options))
    size=ctypes.c_size_t();lib.nvrtcGetProgramLogSize(handle,ctypes.byref(size));log=ctypes.create_string_buffer(max(size.value,1));lib.nvrtcGetProgramLog(handle,log)
    ptx=ctypes.c_size_t()
    if not compiled:lib.nvrtcGetPTXSize(handle,ctypes.byref(ptx))
    rows.append({'file':filename,'kernel':name,'architecture':architecture,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
       'compile_status':'PASS' if not compiled else 'FAIL','nvrtc_result':compiled,'ptx_bytes':ptx.value,'compiler_log':log.value.decode(errors='replace')})
   finally:lib.nvrtcDestroyProgram(ctypes.byref(handle))
 return {'scope':'NVRTC_COMPILE_ONLY_NO_GPU_EXECUTION','actual_cuda_executed':False,'nvrtc_version':f'{major.value}.{minor.value}',
         'status':'PASS' if all(r['compile_status']=='PASS' for r in rows) else 'FAIL','kernels':rows}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--library',required=True,type=Path)
 parser.add_argument('--root',type=Path,default=Path(__file__).parent);parser.add_argument('--output',required=True,type=Path)
 parser.add_argument('--architecture',action='append');args=parser.parse_args()
 result=compile_kernels(args.library,args.root,args.architecture or ['compute_75'])
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2));raise SystemExit(0 if result['status']=='PASS' else 1)
