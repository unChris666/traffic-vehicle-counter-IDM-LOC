#!/usr/bin/env bash
set -euo pipefail
# Cloud artifact audit and Kaggle CLI only; model execution belongs to Kaggle.
cd /workspace
mkdir -p /workspace/.venvs
if [ ! -x /workspace/.venvs/phase7-audit/bin/python ]; then
  python3 -m venv /workspace/.venvs/phase7-audit
fi
/workspace/.venvs/phase7-audit/bin/python -m pip install --disable-pip-version-check --no-input --no-cache-dir numpy==2.0.2 opencv-python-headless==4.13.0.92 nbformat==5.10.4 nbclient==0.10.2 pillow==12.2.0
if [ ! -x /workspace/.venvs/kaggle-cli/bin/python ]; then
  python3 -m venv /workspace/.venvs/kaggle-cli
fi
if ! /workspace/.venvs/kaggle-cli/bin/python -m pip --version >/dev/null 2>&1; then
  /workspace/.venvs/kaggle-cli/bin/python -m ensurepip
fi
/workspace/.venvs/kaggle-cli/bin/python -m pip install --disable-pip-version-check --no-input --no-cache-dir kaggle==2.2.4
/workspace/.venvs/phase7-audit/bin/python -c 'import cv2, numpy, nbformat, nbclient, PIL; assert cv2.__version__ == "4.13.0"; assert numpy.__version__ == "2.0.2"; print("Cloud audit dependencies verified")'
/workspace/.venvs/kaggle-cli/bin/kaggle --version
