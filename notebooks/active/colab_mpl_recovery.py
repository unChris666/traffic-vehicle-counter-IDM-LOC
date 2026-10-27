# Salin seluruh isi file ini ke CELL BARU pada notebook Colab yang gagal di scientific_imports.
# Memakai runtime/dependency yang sudah terpasang. Tidak mengubah backend kernel notebook.
# Setelah SETUP_READY, lanjutkan ke cell "Periksa import dan CUDA"; jangan ulang cell setup lama.
import json, os, sys
from pathlib import Path
if not all(k in globals() for k in ('BASE','WHEEL','run_logged')):
    raise RuntimeError('Cell pemulihan memerlukan BASE, WHEEL dan run_logged dari cell setup r2 yang sudah dijalankan.')
run_logged([sys.executable,'-u',str(BASE/'bootstrap.py'),str(BASE),'--wheel',WHEEL.name],
           'setup',env={**os.environ,'MPLBACKEND':'Agg'})
SETUP=json.loads((BASE/'setup-ready.json').read_text())
SCIENCE=SETUP['science_python'];CORE=SETUP['core_python']
def child_env():
    env={**os.environ,'LI_RUNTIME_MODE':'bundled','LI_AUTH_MODE':'adc','LI_RUNTIME_PLATFORM':'colab',
         'LI_CORE_PYTHON':CORE,'LI_COLAB_GATE_ROOT':str(BASE/'area-verifications'),
         'GRADIO_ANALYTICS_ENABLED':'False','MPLBACKEND':'Agg','PROJ_NETWORK':'OFF','GOOGLE_CLOUD_PROJECT':'locdeproject'}
    for key in ('PROJ_LIB','PROJ_DATA','GDAL_DATA'):env.pop(key,None)
    return env
def command(operation):
    return [SCIENCE,'-u','-m','traffic_location.integration.colab_runtime',operation,
            '--base',str(BASE),'--config-root',str(BASE/'config')]
print('Setup pulih. Lanjutkan ke cell Periksa import dan CUDA, lalu autentikasi Google dan UI.')
