"""Compiler diagnostics tests using a stub, not GPU execution claims."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from location_intelligent_gpu_diagnostics import compile_cuda_kernels,diagnostic

class Device:
 def __init__(self,*args):pass
 def __enter__(self):return self
 def __exit__(self,*args):pass

class CompileTests(unittest.TestCase):
 def compiler(self,fail=False):
  class Kernel:
   def __init__(self,source,name,options):self.name=name
   def compile(self,log_stream=None):
    if self.name=='relax' and fail:
     error=type('CompileException',(Exception,),{})("relax.cu(18): overloaded fmax argument types (int, int)")
     raise error
    log_stream.write('test compiler stub: '+self.name)
  return SimpleNamespace(RawKernel=Kernel,cuda=SimpleNamespace(Device=Device))
 def test_failure_names_kernel_persists_compiler_log_and_does_not_succeed(self):
  with tempfile.TemporaryDirectory() as d,patch.dict('sys.modules',{'cupy':self.compiler(True)}):
   path=Path(d)
   with self.assertRaisesRegex(RuntimeError,'GPU_KERNEL_COMPILE_FAILED') as raised:compile_cuda_kernels(path)
   data=diagnostic(raised.exception,'preflight');self.assertEqual(data['kernel'],'relax')
   self.assertIn('overloaded fmax',data['compiler_log']);self.assertTrue((path/'relax_compile.log').is_file())
   self.assertEqual(json.loads((path/'kernel_compilation.json').read_text())['status'],'FAIL')
 def test_compile_all_reports_compilation_not_execution(self):
  with tempfile.TemporaryDirectory() as d,patch.dict('sys.modules',{'cupy':self.compiler()}):
   result=compile_cuda_kernels(Path(d));self.assertEqual(result['status'],'PASS')
   self.assertEqual(len(result['kernels']),5);self.assertFalse(result['actual_cuda_executed'])
   self.assertTrue(all(r['status']=='PASS' for r in result['kernels']))
 def test_generic_auth_error_message_is_never_exported(self):
  result=diagnostic(ValueError('PRIVATE_CREDENTIAL_VALUE'),'other')
  self.assertNotIn('PRIVATE_CREDENTIAL_VALUE',json.dumps(result))

if __name__=='__main__':unittest.main()
