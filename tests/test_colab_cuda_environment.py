"""CUDA wheel loader wiring without CUDA/GPU or installation in CI."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('colab_cuda_env', ROOT/'tools/colab_cuda_environment.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CudaEnvironmentTests(unittest.TestCase):
    def fixture(self, site):
        for name in ('cuda_nvrtc/lib/libnvrtc.so.12', 'cuda_runtime/lib/libcudart.so.12',
                     'cudnn/lib/libcudnn.so.9'):
            p = site/'nvidia'/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        (site/'torch/lib').mkdir(parents=True)

    def test_uses_application_site_not_host_preserves_driver_paths_without_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)/'application-site'
            self.fixture(site)
            original = {'LD_LIBRARY_PATH': '/usr/local/nvidia/lib64::/driver/lib',
                        'MPLBACKEND': 'Agg', 'SENTINEL': 'keep'}
            with patch('subprocess.check_output', return_value=json.dumps({'purelib': str(site)})) as probe:
                env = module.cuda_child_environment('/isolated/python', original)
            self.assertEqual(probe.call_args.args[0][:2], ['/isolated/python', '-I'])
            paths = env['LD_LIBRARY_PATH'].split(':')
            self.assertIn(str(site/'nvidia/cuda_nvrtc/lib'), paths)
            self.assertIn(str(site/'nvidia/cudnn/lib'), paths)
            self.assertIn(str(site/'torch/lib'), paths)
            self.assertEqual(paths[-2:], ['/usr/local/nvidia/lib64', '/driver/lib'])
            self.assertNotIn('', paths)
            self.assertEqual(original['LD_LIBRARY_PATH'], '/usr/local/nvidia/lib64::/driver/lib')
            self.assertEqual(env['SENTINEL'], 'keep')
            with patch('subprocess.check_output', return_value=json.dumps({'purelib': str(site)})):
                self.assertEqual(module.cuda_child_environment('/isolated/python', env), env)

    def test_missing_wheel_stops_before_gpu_work_with_setup_instruction(self):
        with tempfile.TemporaryDirectory() as d, patch('subprocess.check_output', return_value=json.dumps({'purelib': d})):
            with self.assertRaisesRegex(RuntimeError, 'libnvrtc.so.12.*setup terkunci'):
                module.cuda_child_environment('/isolated/python', {})

    def test_generated_notebook_and_existing_session_recovery_embed_same_helper(self):
        helper = (ROOT/'tools/colab_cuda_environment.py').read_text()
        notebook = json.loads((ROOT/'notebooks/active/15_colab_l4_area_first.ipynb').read_text())
        cell = next(c['source'] for c in notebook['cells'] if c['cell_type'] == 'code' and 'def child_env(' in c['source'])
        recovery = (ROOT/'notebooks/active/colab_cuda_recovery.py').read_text()
        self.assertIn(helper, cell)
        self.assertIn(helper, recovery)
        # Both launch paths must supply LD_LIBRARY_PATH BEFORE child exec.
        for text in (cell, recovery):
            fn = next(x for x in ast.parse(text).body if isinstance(x, ast.FunctionDef) and x.name == 'child_env')
            self.assertIn('cuda_child_environment', ast.unparse(fn))
        self.assertIn("run_logged(command('verify'),'runtime-check',env=child_env())", recovery)

    def test_recovery_rechecks_cuda_and_remains_safe_to_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)/'application-site'
            self.fixture(site)
            original = {'MPLBACKEND': 'Agg', 'LD_LIBRARY_PATH': '/driver/lib',
                        'LI_RUNTIME_MODE': 'bundled', 'LI_AUTH_MODE': 'adc'}
            run = Mock()
            namespace = {'SCIENCE': '/isolated/python', 'CORE': '/core/python',
                         'BASE': Path(d), 'child_env': lambda: dict(original),
                         'command': lambda op: ['verify-command', op], 'run_logged': run}
            recovery = (ROOT/'notebooks/active/colab_cuda_recovery.py').read_text()
            with patch('subprocess.check_output', return_value=json.dumps({'purelib': str(site)})):
                exec(compile(recovery, 'recovery-cell', 'exec'), namespace)
                exec(compile(recovery, 'recovery-cell', 'exec'), namespace)
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.args, (['verify-command', 'verify'], 'runtime-check'))
            env = run.call_args.kwargs['env']
            self.assertIn(str(site/'nvidia/cuda_nvrtc/lib'), env['LD_LIBRARY_PATH'])
            self.assertTrue(env['LD_LIBRARY_PATH'].endswith('/driver/lib'))
            self.assertEqual(original['LD_LIBRARY_PATH'], '/driver/lib')
            self.assertEqual(env['LI_AUTH_MODE'], 'adc')


if __name__ == '__main__':
    unittest.main()
