#!/usr/bin/env bash
# Activate the civic-evals project venv and isolate it from the
# pytorch-devcontainers workspace (which exports PYTHONPATH into the
# editable pytorch / vllm / DeepSpeed trees).
#
# Usage (from anywhere):
#   source /workspaces/pytorch-devcontainers/civic-evals/scripts/activate_civic_env.sh
#
# Optional: override the MIG UUID if yours differs.
#   CIVIC_MIG_UUID=MIG-... source .../activate_civic_env.sh

_CIVIC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"

# Drop the pytorch workspace PYTHONPATH so `import torch` resolves to
# the wheel installed in civic-evals/.venv, not the editable source tree.
unset PYTHONPATH
unset VIRTUAL_ENV
# The parent CUDA image exposes cuDNN 9.25 through /usr/local/cuda/lib64,
# while the project torch wheel ships cuDNN 9.26. Mixing their component
# libraries fails at first generation with CUDNN_STATUS_SUBLIBRARY_VERSION_MISMATCH.
unset LD_LIBRARY_PATH

if [[ ! -x "${_CIVIC_ROOT}/.venv/bin/python" ]]; then
  echo "civic-evals .venv missing. From ${_CIVIC_ROOT} run:"
  echo "  uv sync --extra dev --extra gpu"
  return 1 2>/dev/null || exit 1
fi

# Prefer the project venv on PATH.
# shellcheck disable=SC1091
source "${_CIVIC_ROOT}/.venv/bin/activate"

# Respect an explicit MIG UUID; otherwise use the first device exposed by the
# container. MIG UUIDs are allocation-specific and must not be hard-coded.
export CUDA_VISIBLE_DEVICES="${CIVIC_MIG_UUID:-${CUDA_VISIBLE_DEVICES:-0}}"

# Quiet HF progress bars in long batch runs unless the user wants them.
export HF_HUB_DISABLE_PROGRESS_BARS="${HF_HUB_DISABLE_PROGRESS_BARS:-0}"

echo "civic-evals env active"
echo "  python:  $(command -v python)"
echo "  CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES}"
python -c "import sys; assert 'civic-evals' in sys.executable, sys.executable" 2>/dev/null \
  || echo "  WARNING: python executable is not civic-evals/.venv"
