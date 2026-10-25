"""Submit bounded private GPU parity from verified frozen inputs, never live APIs."""
import json
from pathlib import Path
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest,KernelExecutionType
ROOT=Path(__file__).resolve().parents[1]
api=KaggleApi();api.authenticate()
n=json.loads((ROOT/'notebooks/area_modular_v5_frozen_parity.ipynb').read_text())
for cell in n['cells']:cell['source']=''.join(cell['source'])
r=ApiSaveKernelRequest();r.slug='chrisbiran/area-modular-v5-frozen-parity';r.new_title='Area Modular V5 Frozen Parity'
r.text=json.dumps(n);r.language='python';r.kernel_type='notebook';r.is_private=True;r.enable_gpu=True;r.enable_internet=True
r.machine_shape='NvidiaTeslaT4';r.docker_image_pinning_type='latest'
# A CPU-image digest from notebook metadata did not expose driver libraries.
# Let Kaggle select its GPU image; scientific/core version checks remain strict.
r.dataset_data_sources=['chrisbiran/area-modular-v5-frozen-baseline'];r.kernel_data_sources=[];r.competition_data_sources=[]
r.kernel_execution_type=KernelExecutionType.SAVE_AND_RUN_ALL
with api.build_kaggle_client() as client:print(client.kernels.kernels_api_client.save_kernel(r))
