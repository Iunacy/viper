#!/usr/bin/env bash
# Linux CPU development setup. Optional GPU runtimes remain separately consented.
set -euo pipefail
cd "$(dirname "$0")/.."
for tool in uv cmake c++ ffmpeg; do
    command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
if [[ ! -x .venv/bin/python ]]; then
    uv venv --python 3.12 .venv
fi
uv pip install --python .venv/bin/python -r requirements-dev.txt
mujoco_sdk="$(.venv/bin/python -c 'import pathlib,mujoco; print(pathlib.Path(mujoco.__file__).parent)')"
mujoco_library="$(.venv/bin/python -c 'import pathlib,mujoco; print(next(pathlib.Path(mujoco.__file__).parent.glob("libmujoco.so.*")))')"
cmake -S . -B build-dev -DCMAKE_BUILD_TYPE=Release \
    -DMUJOCO_INCLUDE_DIR="$mujoco_sdk/include" -DMUJOCO_LIBRARY="$mujoco_library" \
    -DPython3_EXECUTABLE="$PWD/.venv/bin/python" \
    -DRELIC_ADAPTIVE=ON -DRELIC_INTERACTIVE=ON \
    -DRELIC_RUCKIG_EXPERIMENT=ON -DRELIC_DOUBLE_S_EXPERIMENT=ON
cmake --build build-dev --parallel 2
cmake -S embodiment/native -B build-dev/contract -DCMAKE_BUILD_TYPE=Release
cmake --build build-dev/contract --parallel 2
printf '\nCPU development setup complete. No model weights or GPU runtimes installed.\n'
printf 'Test: ctest --test-dir build-dev --output-on-failure\n'
printf 'Offline checks: .venv/bin/python -m unittest discover -s embodiment/tests -v\n'
printf 'Viewer (requires cached robot assets): VIPER_VIEWER_PYTHON=.venv/bin/python bash interactive/run.sh\n'
