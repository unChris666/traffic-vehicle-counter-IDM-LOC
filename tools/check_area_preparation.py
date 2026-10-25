"""Local preparation gate; does not download/build Indonesia or contact GCS.

Run with the development environment containing ruff and the Area test deps.
"""
import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    notebook = json.loads((ROOT / 'notebooks/area_gcs_runtime_preparation.ipynb').read_text())
    code = [''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code']
    helper = (ROOT / 'tools/national_basemap.py').read_text()
    driver = (ROOT / 'tools/prepare_area_gcs_runtime.py').read_text()
    if code[-1] != driver or code[-2].split('\n', 1)[1] != helper:
        raise RuntimeError('Published notebook and preparation scripts differ')
    files = ['tools/prepare_area_gcs_runtime.py', 'tools/national_basemap.py',
             'notebooks/location_intelligent_google_only.py',
             'notebooks/location_intelligent_pbf_sources.py',
             'notebooks/location_intelligent_gcs_basemap.py']
    subprocess.run([sys.executable, '-m', 'ruff', 'check', '--no-cache',
                    '--select', 'F821,F822,F823', *files], cwd=ROOT, check=True)
    for index, source in enumerate(code):
        if source.startswith('%%writefile '):
            source = source.split('\n', 1)[1]
        filename = f'preparation_cell_{index}.py'
        ast.parse(source, filename=filename)
        subprocess.run([sys.executable, '-m', 'ruff', 'check', '--no-cache',
                        '--select', 'F821,F822,F823', '--stdin-filename', filename, '-'],
                       input=source, text=True, cwd=ROOT, check=True)
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'notebooks',
                    '-p', 'area_coverage_preparation_tests.py'], cwd=ROOT, check=True)
    print('PASS: notebook sync, undefined-name checks and isolated execution paths.', flush=True)
    print('NOT TESTED HERE: live Kaggle secrets/GCS or full Indonesia build.', flush=True)


if __name__ == '__main__':
    main()
