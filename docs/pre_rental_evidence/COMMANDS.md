# Executed verification commands

Each entry is a command actually executed in `/home/iris/VIPER-pre-rental`, with its process exit code and captured output. Zero exit for a dry-run, help command, interface check or negative-test harness does not establish GPU qualification. Repeated runs are retained. Reviewer red/green runs identify their phase; their full output is preserved. Scripts originally invoked from `/tmp` are copied here as `environment_snapshot.py` and `nondivisible_checkpoint.py`. Caches and upstream source directories are environment inputs, not bundled dependencies.

## 1. cpp-config

Exit code: **0**. Passed the stated preparation/check command.

```bash
cmake -S . -B /tmp/viper-final-audit-build -G Ninja -DMUJOCO_ROOT=/home/iris/.local/opt/mujoco-3.16.0 -DRELIC_RUCKIG_EXPERIMENT=ON -DRELIC_DOUBLE_S_EXPERIMENT=ON -DRELIC_ADAPTIVE=ON -DRELIC_INTERACTIVE=ON -DPython3_EXECUTABLE=/home/iris/.local/share/relic-groot-preflight/bin/python -DCMAKE_BUILD_TYPE=Release
```

Output: [cpp-config.log](cpp-config.log).

## 2. baseline-offline

Exit code: **0**. 240 run, 227 passed, 13 optional skips.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python -m unittest discover -s embodiment/tests -v
```

Output: [baseline-offline.log](baseline-offline.log).

## 3. native-config

Exit code: **0**. Passed the stated preparation/check command.

```bash
cmake -S embodiment/native -B /tmp/viper-final-audit-native -G Ninja -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON
```

Output: [native-config.log](native-config.log).

## 4. static-compile

Exit code: **0**. Passed the stated preparation/check command.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python -m compileall -q embodiment interactive adaptive
```

Output: [static-compile.log](static-compile.log).

## 5. isaac-interfaces

Exit code: **0**. Passed the stated preparation/check command.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python -m embodiment.isaac_interfaces --source /home/iris/.local/share/viper-cloud-ubuntu/sources/IsaacLab
```

Output: [isaac-interfaces.log](isaac-interfaces.log).

## 6. upstream-offline

Exit code: **0**. 240 run, 234 passed, six optional skips.

```bash
env RELIC_GROOT_SOURCE=/home/iris/.local/share/viper-cloud-ubuntu/sources/GR00T LD_LIBRARY_PATH=/home/iris/.local/share/relic-groot-preflight/ffmpeg7 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 WANDB_MODE=disabled CUDA_VISIBLE_DEVICES= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/iris/.local/share/relic-groot-preflight/bin/python -m unittest discover -s embodiment/tests -v
```

Output: [upstream-offline.log](upstream-offline.log).

## 7. cpp-build

Exit code: **0**. Passed the stated preparation/check command.

```bash
cmake --build /tmp/viper-final-audit-build -j 6
```

Output: [cpp-build.log](cpp-build.log).

## 8. cpp-ctest

Exit code: **8**. Environment failure: selected Python lacked MuJoCo; 42/42 passed after reconfiguration.

```bash
env MUJOCO_GL=egl ctest --test-dir /tmp/viper-final-audit-build --output-on-failure -j 2
```

Output: [cpp-ctest.log](cpp-ctest.log).

## 9. native-build

Exit code: **0**. Passed the stated preparation/check command.

```bash
cmake --build /tmp/viper-final-audit-native -j 2
```

Output: [native-build.log](native-build.log).

## 10. native-ctest

Exit code: **0**. Passed the stated preparation/check command.

```bash
ctest --test-dir /tmp/viper-final-audit-native --output-on-failure
```

Output: [native-ctest.log](native-ctest.log).

## 11. optional-cpu-upstream

Exit code: **1**. Environment failure: Python lacked MuJoCo; seven passed with viewer interpreter.

```bash
env RELIC_GROOT_SOURCE=/home/iris/.local/share/viper-cloud-ubuntu/sources/GR00T LD_LIBRARY_PATH=/home/iris/.local/share/relic-groot-preflight/ffmpeg7 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 WANDB_MODE=disabled CUDA_VISIBLE_DEVICES= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VIPER_ACTION_CONTRACT_LIBRARY=/tmp/viper-final-audit-native/libviper_action_contract.so VIPER_SIMULATOR_AUDIT=1 VIPER_ASSET_CACHE=/home/iris/.local/share/viper-cloud-ubuntu/robot_cache RELIC_PHYSICAL_REPLAY_TESTS=1 /home/iris/.local/share/relic-groot-preflight/bin/python -m unittest embodiment.tests.test_kinematics embodiment.tests.test_native_contract embodiment.tests.test_dual_media -v
```

Output: [optional-cpu-upstream.log](optional-cpu-upstream.log).

## 12. runtime-import-probe

Exit code: **127**. BLOCKED — EXTERNAL: cached container symlink is unusable on host.

```bash
env LD_LIBRARY_PATH=/home/iris/.local/share/viper-cloud-cache/codec HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CUDA_VISIBLE_DEVICES= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/iris/.local/share/viper-cloud-ubuntu/sources/GR00T/.venv/bin/python -m embodiment.runtime_probe --source /home/iris/.local/share/viper-cloud-ubuntu/sources/GR00T
```

Output: [runtime-import-probe.log](runtime-import-probe.log).

## 13. rental-dry

Exit code: **0**. Passed the stated preparation/check command.

```bash
python -m embodiment.rental full --prefix /workspace/viper --root /workspace/runs/viper
```

Output: [rental-dry.log](rental-dry.log).

## 14. pilot-dry

Exit code: **0**. Passed the stated preparation/check command.

```bash
python -m embodiment.pilot --root /tmp/viper-final-audit-pilot --episodes 12
```

Output: [pilot-dry.log](pilot-dry.log).

## 15. qualification-dry

Exit code: **0**. Passed the stated preparation/check command.

```bash
python -m embodiment.qualification_pair --root /tmp/viper-final-audit-qualification
```

Output: [qualification-dry.log](qualification-dry.log).

## 16. runtime-import-probe-cpu

Exit code: **2**. BLOCKED — EXTERNAL: DeepSpeed and FlashAttention missing.

```bash
env LD_LIBRARY_PATH=/home/iris/.local/share/relic-groot-preflight/ffmpeg7 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CUDA_VISIBLE_DEVICES= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/iris/.local/share/relic-groot-preflight/bin/python -m embodiment.runtime_probe --source /home/iris/.local/share/viper-cloud-ubuntu/sources/GR00T
```

Output: [runtime-import-probe-cpu.log](runtime-import-probe-cpu.log).

## 17. cloud-missing-weights

Exit code: **2**. Expected negative result: missing weights and inadequate host, no model/training executed.

```bash
env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CUDA_VISIBLE_DEVICES= /home/iris/.local/share/relic-groot-preflight/bin/python -m embodiment.cloud --source /home/iris/.local/share/viper-cloud-ubuntu/sources/GR00T --pretrained /tmp/viper-final-audit-absent-weights --volume /tmp
```

Output: [cloud-missing-weights.log](cloud-missing-weights.log).

## 18. doctor

Exit code: **2**. BLOCKED — EXTERNAL: this host is not the required Ubuntu/runtime/GPU/RAM/storage profile.

```bash
python -m embodiment.rental doctor --prefix /workspace/viper --root /workspace/runs/viper
```

Output: [doctor.log](doctor.log).

## 19. cpp-config-viewer

Exit code: **0**. Passed the stated preparation/check command.

```bash
cmake -S . -B /tmp/viper-final-audit-build -DPython3_EXECUTABLE=/home/iris/.local/share/relic-viewer-venv/bin/python
```

Output: [cpp-config-viewer.log](cpp-config-viewer.log).

## 20. optional-cpu-viewer

Exit code: **0**. Passed the stated preparation/check command.

```bash
env VIPER_ACTION_CONTRACT_LIBRARY=/tmp/viper-final-audit-native/libviper_action_contract.so VIPER_SIMULATOR_AUDIT=1 VIPER_ASSET_CACHE=/home/iris/.local/share/viper-cloud-ubuntu/robot_cache VIPER_OFFLINE=1 RELIC_PHYSICAL_REPLAY_TESTS=1 MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 /home/iris/.local/share/relic-viewer-venv/bin/python -m unittest embodiment.tests.test_kinematics embodiment.tests.test_native_contract embodiment.tests.test_dual_media -v
```

Output: [optional-cpu-viewer.log](optional-cpu-viewer.log).

## 21. cpp-ctest-viewer

Exit code: **0**. 42/42 passed, including interactive and adaptive integration.

```bash
env MUJOCO_GL=egl ctest --test-dir /tmp/viper-final-audit-build --output-on-failure -j 2
```

Output: [cpp-ctest-viewer.log](cpp-ctest-viewer.log).

## 22. science-regression

Exit code: **0**. Passed the stated preparation/check command.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python -m unittest embodiment.tests.test_paired embodiment.tests.test_benchmark_report embodiment.tests.test_m0 embodiment.tests.test_research_workflows embodiment.tests.test_training_campaign -v
```

Output: [science-regression.log](science-regression.log).

## 23. shell-syntax

Exit code: **0**. Passed the stated preparation/check command.

```bash
bash -c 'for script in embodiment/*.sh interactive/*.sh experiments/ruckig/*.sh; do bash -n "$script" || exit; done'
```

Output: [shell-syntax.log](shell-syntax.log).

## 24. provenance

Exit code: **0**. Passed the stated preparation/check command.

```bash
python -m embodiment.provenance --output /tmp/viper-final-audit-provenance.json
```

Output: [provenance.log](provenance.log).

## 25. reader-dependencies

Exit code: **0**. Passed the stated preparation/check command.

```bash
uv pip check --python /home/iris/.local/share/relic-groot-preflight/bin/python
```

Output: [reader-dependencies.log](reader-dependencies.log).

## 26. viewer-dependencies

Exit code: **0**. Passed the stated preparation/check command.

```bash
uv pip check --python /home/iris/.local/share/relic-viewer-venv/bin/python
```

Output: [viewer-dependencies.log](viewer-dependencies.log).

## 27. native-sanitize-config

Exit code: **0**. Passed the stated preparation/check command.

```bash
cmake -S embodiment/native -B /tmp/viper-final-audit-sanitize -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -DCMAKE_SHARED_LINKER_FLAGS=-fsanitize=address,undefined -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined
```

Output: [native-sanitize-config.log](native-sanitize-config.log).

## 28. native-sanitize-build

Exit code: **0**. Passed the stated preparation/check command.

```bash
cmake --build /tmp/viper-final-audit-sanitize -j 2
```

Output: [native-sanitize-build.log](native-sanitize-build.log).

## 29. native-sanitize-ctest

Exit code: **0**. Passed the stated preparation/check command.

```bash
ctest --test-dir /tmp/viper-final-audit-sanitize --output-on-failure
```

Output: [native-sanitize-ctest.log](native-sanitize-ctest.log).

## 30. path-sanitize-config

Exit code: **0**. Passed the stated preparation/check command.

```bash
cmake -S tests/standalone -B /tmp/viper-final-audit-path -G Ninja -DMUJOCO_ROOT=/home/iris/.local/opt/mujoco-3.16.0 -DRELIC_SANITIZER=undefined
```

Output: [path-sanitize-config.log](path-sanitize-config.log).

## 31. path-sanitize-build

Exit code: **0**. Passed the stated preparation/check command.

```bash
cmake --build /tmp/viper-final-audit-path -j 2
```

Output: [path-sanitize-build.log](path-sanitize-build.log).

## 32. path-sanitize-targeted

Exit code: **0**. Passed the stated preparation/check command.

```bash
/tmp/viper-final-audit-path/relic_path_standalone targeted
```

Output: [path-sanitize-targeted.log](path-sanitize-targeted.log).

## 33. path-sanitize-fuzz

Exit code: **0**. Passed the stated preparation/check command.

```bash
/tmp/viper-final-audit-path/relic_path_standalone fuzz 0x52454c494332 100000
```

Output: [path-sanitize-fuzz.log](path-sanitize-fuzz.log).

## 34. first-session-dry

Exit code: **0**. Passed the stated preparation/check command.

```bash
python -m embodiment.first_session --root /tmp/viper-final-audit-session --simulation-python /home/iris/.local/share/viper-cloud-ubuntu/simulation/bin/python --reader-python /home/iris/.local/share/relic-groot-preflight/bin/python --isaac-source /home/iris/.local/share/viper-cloud-ubuntu/sources/IsaacLab --groot-source /home/iris/.local/share/viper-cloud-ubuntu/sources/GR00T --robot-cache /home/iris/.local/share/viper-cloud-ubuntu/robot_cache --panda-assets /home/iris/.local/share/viper-cloud-ubuntu/assets --reader-library-path /home/iris/.local/share/relic-groot-preflight/ffmpeg7 --episodes 12
```

Output: [first-session-dry.log](first-session-dry.log).

## 35. first-session-preflight

Exit code: **2**. BLOCKED — EXTERNAL: simulation interpreter absent; reader/assets/source checks returned evidence.

```bash
python -m embodiment.first_session --root /tmp/viper-final-audit-session --simulation-python /home/iris/.local/share/viper-cloud-ubuntu/simulation/bin/python --reader-python /home/iris/.local/share/relic-groot-preflight/bin/python --isaac-source /home/iris/.local/share/viper-cloud-ubuntu/sources/IsaacLab --groot-source /home/iris/.local/share/viper-cloud-ubuntu/sources/GR00T --robot-cache /home/iris/.local/share/viper-cloud-ubuntu/robot_cache --panda-assets /home/iris/.local/share/viper-cloud-ubuntu/assets --reader-library-path /home/iris/.local/share/relic-groot-preflight/ffmpeg7 --episodes 12 --preflight
```

Output: [first-session-preflight.log](first-session-preflight.log).

## 36. final-all-python

Exit code: **1**. Mixed run failed: incompatible global offline flag for file fixture and genuine GIF library defect; corrected run final-combined-python passed.

```bash
env RELIC_GROOT_SOURCE=/home/iris/.local/share/viper-cloud-ubuntu/sources/GR00T LD_LIBRARY_PATH=/home/iris/.local/share/relic-groot-preflight/ffmpeg7 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 WANDB_MODE=disabled NO_ALBUMENTATIONS_UPDATE=1 CUDA_VISIBLE_DEVICES= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VIPER_ACTION_CONTRACT_LIBRARY=/tmp/viper-final-audit-native/libviper_action_contract.so VIPER_SIMULATOR_AUDIT=1 VIPER_ASSET_CACHE=/home/iris/.local/share/viper-cloud-ubuntu/robot_cache VIPER_OFFLINE=1 RELIC_PHYSICAL_REPLAY_TESTS=1 MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 /home/iris/.local/share/relic-groot-preflight/bin/python -c 'import sys,unittest; sys.path.append("/home/iris/.local/share/relic-viewer-venv/lib/python3.12/site-packages"); result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover("embodiment/tests")); sys.exit(not result.wasSuccessful())'
```

Output: [final-all-python.log](final-all-python.log).

## 37. regression-baseline-rejection

Exit code: **1**. Expected RED: current regressions executed against baseline functions, proving defects without modifying checkout.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python -c 'import importlib,subprocess,unittest,sys; names=("benchmark_report","paired","first_session","simulation_smoke"); [(lambda m: exec(compile(subprocess.check_output(["git","show","5c66c95:"+m.__name__.replace(".","/")+".py"]),m.__file__,"exec"),m.__dict__))(importlib.import_module("embodiment."+n)) for n in names]; suite=unittest.defaultTestLoader.loadTestsFromNames(["embodiment.tests.test_paired.PhysicalEvidenceGate.test_raw_episode_identity_must_match_report","embodiment.tests.test_benchmark_report.BenchmarkReport.test_policy_condition_trial_and_training_embodiments_must_agree","embodiment.tests.test_first_session.FirstSession.test_execute_command_preserves_qualification_only_endpoint","embodiment.tests.test_first_session.FirstSession.test_short_session_smoke_configuration_survives_preflight_timing_changes"]); r=unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(not r.wasSuccessful())'
```

Output: [regression-baseline-rejection.log](regression-baseline-rejection.log).

## 38. orchestration-regression

Exit code: **0**. Passed the stated preparation/check command.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python -m unittest embodiment.tests.test_first_session embodiment.tests.test_simulation_smoke embodiment.tests.test_rental embodiment.tests.test_qualification_session -v
```

Output: [orchestration-regression.log](orchestration-regression.log).

## 39. diff-whitespace

Exit code: **0**. Passed the stated preparation/check command.

```bash
git diff --check
```

Output: [diff-whitespace.log](diff-whitespace.log).

## 40. environment-and-preservation

Exit code: **0**. Passed the stated preparation/check command.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python /tmp/viper-audit-snapshot.py
```

Output: [environment-and-preservation.log](environment-and-preservation.log).

## 41. codec-bridge

Exit code: **0**. Passed the stated preparation/check command.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python -m embodiment.codec_runtime --root /tmp/viper-final-audit-codec
```

Output: [codec-bridge.log](codec-bridge.log).

## 42. final-reader-upstream

Exit code: **0**. 245 run, 241 passed, four optional skips; separate final combined run enabled all.

```bash
env RELIC_GROOT_SOURCE=/home/iris/.local/share/viper-cloud-ubuntu/sources/GR00T LD_LIBRARY_PATH=/tmp/viper-final-audit-codec HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 WANDB_MODE=disabled NO_ALBUMENTATIONS_UPDATE=1 CUDA_VISIBLE_DEVICES= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VIPER_ACTION_CONTRACT_LIBRARY=/tmp/viper-final-audit-native/libviper_action_contract.so /home/iris/.local/share/relic-groot-preflight/bin/python -m unittest discover -s embodiment/tests -v
```

Output: [final-reader-upstream.log](final-reader-upstream.log).

## 43. integration-audit

Exit code: **1**. FAIL: historical byte-preservation contract predates intentional branding change; see report and legacy-branding-diff.

```bash
python integration/audit.py --output /tmp/viper-final-audit-integration.json
```

Output: [integration-audit.log](integration-audit.log).

## 44. ruckig-upstream

Exit code: **0**. Passed the stated preparation/check command.

```bash
bash experiments/ruckig/verify_upstream.sh
```

Output: [ruckig-upstream.log](ruckig-upstream.log).

## 45. final-combined-python

Exit code: **0**. 245 passed, zero failures or skips; CPU fixtures/upstream reader, no real GR00T model.

```bash
env RELIC_GROOT_SOURCE=/home/iris/.local/share/viper-cloud-ubuntu/sources/GR00T LD_LIBRARY_PATH=/tmp/viper-final-audit-codec HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 WANDB_MODE=disabled NO_ALBUMENTATIONS_UPDATE=1 CUDA_VISIBLE_DEVICES= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VIPER_ACTION_CONTRACT_LIBRARY=/tmp/viper-final-audit-native/libviper_action_contract.so VIPER_SIMULATOR_AUDIT=1 VIPER_ASSET_CACHE=/home/iris/.local/share/viper-cloud-ubuntu/robot_cache RELIC_PHYSICAL_REPLAY_TESTS=1 MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 /home/iris/.local/share/relic-groot-preflight/bin/python -c 'import sys,unittest; sys.path.append("/home/iris/.local/share/relic-viewer-venv/lib/python3.12/site-packages"); result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover("embodiment/tests")); sys.exit(not result.wasSuccessful())'
```

Output: [final-combined-python.log](final-combined-python.log).

## 46. final-static-compile

Exit code: **0**. Passed the stated preparation/check command.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python -m compileall -q embodiment interactive adaptive
```

Output: [final-static-compile.log](final-static-compile.log).

## 47. media-baseline-rejection

Exit code: **1**. Expected RED: actual GIF export failed against baseline under supported codec bridge.

```bash
env LD_LIBRARY_PATH=/tmp/viper-final-audit-codec VIPER_ASSET_CACHE=/home/iris/.local/share/viper-cloud-ubuntu/robot_cache RELIC_PHYSICAL_REPLAY_TESTS=1 MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 /home/iris/.local/share/relic-viewer-venv/bin/python -c 'import importlib,subprocess,unittest,sys; m=importlib.import_module("embodiment.dual_media"); exec(compile(subprocess.check_output(["git","show","5c66c95:embodiment/dual_media.py"]),m.__file__,"exec"),m.__dict__); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName("embodiment.tests.test_dual_media.RecordedPhysicalMedia.test_real_replay_media_encodes_decodes_and_preserves_source_indices")); sys.exit(not r.wasSuccessful())'
```

Output: [media-baseline-rejection.log](media-baseline-rejection.log).

## 48. legacy-branding-diff

Exit code: **0**. Passed the stated preparation/check command.

```bash
git diff 94899ed..5c66c95 -- src/main.cpp src/cartesian_demo.cpp
```

Output: [legacy-branding-diff.log](legacy-branding-diff.log).

## 49. final-diff-whitespace

Exit code: **0**. Passed the stated preparation/check command.

```bash
git diff --check
```

Output: [final-diff-whitespace.log](final-diff-whitespace.log).

## 50. nondivisible-cpu-checkpoint

Exit code: **0**. Passed the stated preparation/check command.

```bash
env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 WANDB_MODE=disabled NO_ALBUMENTATIONS_UPDATE=1 CUDA_VISIBLE_DEVICES= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/iris/.local/share/relic-groot-preflight/bin/python /tmp/viper-groot-final-step-save.py
```

Output: [nondivisible-cpu-checkpoint.log](nondivisible-cpu-checkpoint.log).

## 51. cross-smoke-missing-data

Exit code: **2**. Expected negative result: unavailable real dataset recorded BLOCKED, no compute.

```bash
env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /home/iris/.local/share/relic-groot-preflight/bin/python -m embodiment.cross_smoke --source /home/iris/.local/share/viper-cloud-ubuntu/sources/GR00T --dataset-a /tmp/viper-final-audit-absent-data-a --dataset-b /tmp/viper-final-audit-absent-data-b --pretrained /tmp/viper-final-audit-absent-weights --output /tmp/viper-final-audit-blocked-cross
```

Output: [cross-smoke-missing-data.log](cross-smoke-missing-data.log).

## 52. final-preservation

Exit code: **0**. Passed the stated preparation/check command.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python /tmp/viper-audit-snapshot.py
```

Output: [final-preservation.log](final-preservation.log).

## 53. campaign-cli

Exit code: **0**. Passed the stated preparation/check command.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python -m embodiment.training_campaign --help
```

Output: [campaign-cli.log](campaign-cli.log).

## 54. collection-cli

Exit code: **0**. Passed the stated preparation/check command.

```bash
python -m embodiment.collection --help
```

Output: [collection-cli.log](collection-cli.log).

## 55. cross-cli

Exit code: **0**. Passed the stated preparation/check command.

```bash
python -m embodiment.cross_smoke --help
```

Output: [cross-cli.log](cross-cli.log).

## 56. paired-cli

Exit code: **0**. Passed the stated preparation/check command.

```bash
python -m embodiment.paired --help
```

Output: [paired-cli.log](paired-cli.log).

## 57. science-red

Exit code: **1**. Expected RED before provenance fix.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python -m unittest embodiment.tests.test_paired embodiment.tests.test_benchmark_report -v
```

Output: [science-red.log](science-red.log).

## 58. science-green

Exit code: **0**. Passed the stated preparation/check command.

```bash
/home/iris/.local/share/relic-groot-preflight/bin/python -m unittest embodiment.tests.test_paired embodiment.tests.test_benchmark_report embodiment.tests.test_m0 embodiment.tests.test_research_workflows embodiment.tests.test_training_campaign -v
```

Output: [science-green.log](science-green.log).

## 59. robotics-red

Exit code: **1**. Expected RED before endpoint/deadline fix.

```bash
python -m unittest embodiment.tests.test_first_session embodiment.tests.test_simulation_smoke
```

Output: [robotics-red.log](robotics-red.log).

## 60. robotics-green

Exit code: **0**. Passed the stated preparation/check command.

```bash
python -m unittest embodiment.tests.test_first_session embodiment.tests.test_simulation_smoke embodiment.tests.test_qualification_session embodiment.tests.test_safety embodiment.tests.test_execution embodiment.tests.test_contract embodiment.tests.test_panda embodiment.tests.test_collision embodiment.tests.test_kinematics
```

Output: [robotics-green.log](robotics-green.log).

## 61. runbook-shell-syntax

Exit code: **0**. Passed the stated preparation/check command.

```bash
bash -n docs/pre_rental_evidence/rented_host_commands.sh
```

Output: [runbook-shell-syntax.log](runbook-shell-syntax.log).

## 62. staged-raw-whitespace

Exit code: **2**. Raw process output preserves trailing whitespace; diagnostic only, no authored-source error.

```bash
git diff --cached --check
```

Output: [staged-raw-whitespace.log](staged-raw-whitespace.log).

## 63. staged-authored-whitespace

Exit code: **0**. Authored source and documentation pass; raw log output excluded without editing it.

```bash
git diff --cached --check -- . ':!docs/pre_rental_evidence/*.log'
```

Output: [staged-authored-whitespace.log](staged-authored-whitespace.log).
