# VIPER pre-rental verification

Date: 2026-11-03 (Asia/Saigon). Repository: `Iunacy/viper`.

**Decision: GO FOR GPU RENTAL for the initial E2/E3 experiment.** This is engineering readiness to attempt the experiment, not a claim that GPU qualification, learning, or transfer has passed, and not spending authorization.

## Scope and audited revision

The user explicitly accepted the documented E2/E3 study as the initial scope. E4 is conversion infrastructure only; E5 is **NOT IMPLEMENTED** and is required before attributing an improvement specifically to cross-embodiment transfer. Full E0–E5 completion is not a rental prerequisite.

Fetched `origin/main` at audit start: **`5c66c95ec48c101a2d4af55df8d917ff5a72bcac`**, matching local `main`. Audited and repaired on `codex/pre-rental-verification` in `/home/iris/VIPER-pre-rental`, leaving the original `/home/iris/RELIC` worktree and its untracked work untouched. No merge or push was performed.

Verified fix commits:

- `f24e7b5`: bind evaluation reports to raw episode provenance.
- `e8b8e53`: preserve first-session endpoint and stable resume deadlines.
- `e59169f`: isolate GIF export from private reader codec libraries.

The final tests cover the runtime source content in `e59169f`. This report and its evidence are a subsequent documentation commit; resolve that commit with `git log -1 --format=%H -- docs/PRE_RENTAL_VERIFICATION.md`. Qualification must use the final **clean checkout**, a fresh output root, and its actual commit SHA. No historical or audit-time dry-run manifest is a qualification for that checkout.

## Environment and evidence

Arch Linux x86_64, kernel `7.2.11-arch1-1`, GCC 16.2.1, system Python 3.14.8. Prepared CPU reader and viewer environments use Python 3.12.15. Reader: PyTorch `2.9.0+cpu`, Transformers 4.57.3, NumPy 1.26.4, TorchCodec 0.8.0, PyArrow 19.0.1, PyAV 14.2.0. MuJoCo C SDK and Python viewer: 3.16.0. Dependency consistency checks passed in both environments.

Read-only GPU inventory: RTX 3050 Laptop, 4096 MiB total, driver 615.78.08. Snapshot: 16,364,085,248 bytes host RAM, 4,732,575,744 available; 238,730,403,840 free filesystem bytes. These are measured local snapshots, not rental specifications or training measurements. The local GPU is insufficient for the selected experiment. No Kit/Isaac execution, real model loading, paid compute, or large weight download was performed. CPU MuJoCo dynamics and software-requested EGL replay were exercised; replay does not reexecute the recorded PhysX manipulation.

[Command ledger](pre_rental_evidence/COMMANDS.md) records exact argv, directory, exit codes, timing, logs and classification, including unsuccessful attempts. [Machine ledger](pre_rental_evidence/commands.jsonl) preserves machine-readable records. [Environment and preservation snapshot](pre_rental_evidence/final-preservation.log) includes upstream revisions and SHA-256 checks for **82 historical evidence files**, all unchanged. [Git attribution export](pre_rental_evidence/provenance.json) preserves ancestry without inferring eligibility from Git dates.

## Architecture and implementation findings

### Robotics foundation

The native C++ MuJoCo engine (`src/`, `include/`) supplies analytical IK, FK/model checks, path feasibility, trajectory constraints, contact inspection and bounded execution. Its Ruckig and InterpolateCpp experiments remain separate from the Isaac control loop. The full configured CTest suite exercises numerical boundaries, invalid inputs, resets, isolation, contact/execution failures, 100,000-case path fuzzing, adaptive pipelines and the interactive bridge.

`embodiment.contract` preserves native joint order: OpenMANIPULATOR-X has four arm plus two finger channels and a 16-dimensional state; Panda has seven arm plus two finger channels and a 22-dimensional state. State order is joint positions, velocities, world end-effector XYZ, then open-positive gripper aperture. Four-dimensional actions are world-frame XYZ increments in metres and an aperture in [0,1]. The controller integrates once from the measured pose at each 30 Hz control tick. Orientation is a robot-specific admissible grasp orientation, not a learned rotation action. Capacity padding belongs to the upstream processor, not joint remapping.

Python/native action parity, full-chunk validation, bounded joint references, workspace/velocity/tracking/stall guards and fail-stop behavior were exercised. CPU tests compared both official robot assets against MuJoCo, checked OMX analytic versus URDF kinematics, and exercised manufacturer self-collision filtering while retaining the floor-contact probe. They do not establish current Isaac collision response, actuator stability, grasp success, or physical-robot safety.

The two checked-in qualification summaries each report historical 20/20 classical successes, on **different** revisions (`0091cfe...` and `c4b7da5...`). Their raw replay was tested, but neither qualifies current `main` or the fixes. `qualification_pair` requires one clean committed revision, 20 frozen camera-enabled trials per robot, matching source/runtime identity, raw hashes and articulation/sensor checks. Its acceptance threshold remains at least 18/20 per robot with the existing physical evidence requirements.

### GR00T integration

Pinned clean upstream GR00T: `944fe70c4fd54e3fcb80a7d7258a328f9c061176`; clean Isaac Lab: `3c6e67bb5c7ada942a6d1884ab69338f57596f77` (v2.3.0), Isaac Sim 5.1.0. Model and backbone snapshots are pinned in `embodiment/model_sources.json`: GR00T `2fc962b973bccdd5d8ce4f67cc63b264d6886495`, Cosmos `9ce19a195e423419c349abfc86fd07178b230561`. Training uses the upstream frozen `uv.lock`; the reader, simulation and training runtimes are deliberately separate. Current vendor documentation labels Isaac Sim 5.1.0 unsupported; this audit preserves the research pin rather than silently migrating it.

Actual upstream CPU tests verified argument parsing, processor serialization, modality ordering, embodiment-specific normalization/roundtrips, video decoding, 16-action chunk extraction and the public checkpoint's 40-to-16 action decoding. Stored world-frame increments receive no second relative transform. Synthetic safetensor tests exercised index/shard integrity, tensor shape/dtype compatibility, checkpoint isolation and corruption rejection.

For matched E2/E3 target initialization, all target projector slot-10 parameters are restored from the same pretrained donor. E2 shared weights originate from pretrained; E3 shared weights originate from the trained source. Panda statistics are recomputed from B **training** data with the actual upstream reader. Language/visual backbones remain frozen; projector/diffusion training selection and actual trainable names are instrumented.

`training_worker` uses the actual upstream trainer and records trainable parameters, wall time and peak allocated GPU memory. Checkpoint recovery validates model, optimizer, scheduler, RNG archives and latest-checkpoint identity. A real upstream **CPU linear-model fixture** saved/reloaded optimizer state and completed the requested step count; it also confirmed that a nondivisible final step is saved. These are trainer-mechanics tests, not GR00T-weight training.

**Recovery limitation:** pinned upstream sharded-data loading deliberately reseeds to `42 + global_step` on resume and disables skipping. State recovery is supported; uninterrupted-identical sample order and training trajectories are not established. The constant-sample CPU equality test cannot prove that property for real datasets. Preserve interruption/resume metadata, report it for both arms, and do not claim exact uninterrupted reproduction or tune on held-out outcomes.

`policy_service` isolates inference from the simulator, identifies the checkpoint/source/native boundary, validates RGB/native state, and returns bounded chunks. `evaluate` records requested, validated, applied and rejected actions, next-state telemetry, interventions and raw images. `cross_smoke` requires real A/B optimizer/save/reload/inference and a separately validated B closed-loop gate before admitting the full training campaign. Source/data/weight mutation blocks reuse. Missing checkpoint configuration, CUDA packages, GPU capacity or interpreters produce blockers rather than successful receipts.

### Experiment integrity and E0–E5

| Label | Current implementation and evidence | Scope/status |
|---|---|---|
| E0 | Classical control/reference campaigns; historical PhysX evidence and replay | Historical evidence only; current common-revision execution **BLOCKED — EXTERNAL** |
| E1 | Source-policy training (`a`) and M0 evaluation; E1 numbering is a descriptive mapping, not a current CLI label | Implementation verified locally; learned outcome **BLOCKED — EXTERNAL** |
| E2 | B-only adaptation, pretrained shared weights, common target projectors/statistics | Initial study; real execution **BLOCKED — EXTERNAL** |
| E3 | A-to-B initialization followed by matched B adaptation | Initial study; real execution **BLOCKED — EXTERNAL** |
| E4 | `transfer.prepare(..., condition='E4')` checkpoint conversion | Conversion infrastructure only; no validated zero-shot execution or transfer claim |
| E5 | No declared control protocol or execution path | **NOT IMPLEMENTED**; future requirement for exclusive cross-embodiment attribution |

Split-specific seed namespaces, scenario hashes and held-out target/region combinations prevent collection/training from admitting qualification or held-out data. New plans freeze 50 evaluation scenes; legacy 20-scene reports remain readable but cannot meet the primary rule. Camera, native sensor and terminal-stability contracts are checked for new physical demonstrations. Failed collection attempts remain in receipts; only physically successful episodes become demonstrations. A pilot manifest is a plan, never a dataset.

E2/E3 match B data digest, demonstration count, optimizer budget, evaluation scenes, target initialization donor, normalizer, trainable recipe, inference and safety settings. E3 retains its additional source training budget: equal B adaptation does not imply equal total compute or data. Single-seed scene bootstrap does not estimate training-seed variance. Pretraining exposure/possible Panda overlap remains an attribution caveat.

Paired reporting uses 10,000 deterministic scene resamples, all assigned scenes in the denominator, and separately classifies policy failure, infrastructure failure, safety rejection, fallback completion and autonomous success. Primary M1 eligibility is exactly **100 B demonstrations and 50 scenes**; acceptance requires autonomous success improvement **>=20 percentage points** and the paired 95% interval lower bound **>0**. Raw episode hashes and metadata must be verified before publishing. A 12-demo pilot cannot satisfy this rule.

Without E5, the defensible claim is a **related-robot initialization comparison**. Neither a synthetic test, converted checkpoint, successful optimizer step nor an assisted completion proves learned cross-embodiment transfer.

## Repairs and regression evidence

| Defect | Smallest correction | Verification |
|---|---|---|
| Raw OMX episodes could be admitted under a Panda report; runtime/fallback/policy metadata could disagree | Bind raw robot/runtime/scene/scenario/fallback/policy provenance to report and training identity | New regressions fail against audited main; pass after fix |
| Short first-session resumes persisted timing-dependent smoke configurations | Freeze smoke timeout; enforce remaining invocation deadline separately for each worker, without consuming expired attempts | Timing/restart/deadline regressions pass |
| Generated qualification-only execution command lost its endpoint | Preserve `--stop-after` in generated command | Endpoint regression passes |
| GIF export inherited private reader libraries, causing system FFmpeg exit 127 | Reuse existing `system_codec_environment()` for that child | Real replay/GIF fails on baseline with the supported bridge; passes after fix |

No scientific threshold, historical result, model/runtime pin or experiment budget was changed. The malformed-data, recovery and orchestration tests use explicitly synthetic fixtures; their receipts are not experimental evidence.

## Tests executed and limitations

| Verification | Final result |
|---|---|
| Combined Python embodiment suite with real pinned upstream reader, native library, CPU asset/dynamics and replay integrations enabled | **245 passed, 0 failed, 0 skipped**, exit 0 |
| Full Release C++/CTest configuration: foundation, Ruckig, Double-S, adaptive, interactive | **42/42 passed**, exit 0 |
| Native C++ action-boundary CTest | **1/1 passed**, exit 0 |
| Native address/undefined sanitizers | **1/1 passed**, exit 0 |
| Standalone path UBSan: targeted and 100,000 generated cases | Passed; zero oracle mismatches |
| Python compile/import coverage, shell syntax, dependency consistency, pinned Isaac source interfaces, Ruckig upstream hashes | Passed; source-interface presence does not prove Isaac runtime compatibility |
| Cloud/rental orchestration dry runs, pilot manifest and qualification-command generation | Passed preparation checks; outputs explicitly NOT_EXECUTED |
| Missing model/data/runtime, altered hashes, stale receipts, timeouts, failed retries, orphan locks and real nested-process termination | Negative/failure-injection checks behave as recorded; full suite passes |
| Real GR00T model load/optimizer/reload/inference; current Isaac startup/qualification/pilot/closed-loop; M0/M1 | **Not executed — external dependencies** |

Raw logs retain exact process output, including trailing spaces emitted by the test frameworks. The staged whitespace diagnostic flags those logs; the separate authored-source/documentation whitespace check passes. Earlier failed executions remain in the ledger. The first CTest selected the reader interpreter without MuJoCo (41/42 passed); reconfiguration to the existing viewer interpreter produced 42/42. Optional CPU tests initially used that same unsuitable reader interpreter (four missing-MuJoCo errors), then all seven passed in the viewer. A combined-suite attempt incorrectly forced `VIPER_OFFLINE=1` on a test intentionally fetching a local `file://` fixture; that environment mistake was removed. The same attempt exposed the genuine GIF subprocess defect above. The corrected combined run has no skips.

Training import inspection returns exit 2 for absent DeepSpeed/FlashAttention in the CPU environment. A cached container interpreter has a `/workspace/...` symlink unusable on this host and returns 127. Read-only host/cloud/first-session preflights correctly return BLOCKED for this workstation's missing runtime/weights/capacity. None is reported as a real runtime pass.

**Retained historical audit failure:** `python integration/audit.py --output /tmp/viper-final-audit-integration.json` exits 1. Its one-time consolidation guard demands byte equality to commit `94899ed`, predating the repository's VIPER rename. Inspection of `94899ed..5c66c95` shows only three help/error branding replacements in `src/main.cpp` and `src/cartesian_demo.cpp`. This is a historical snapshot-contract mismatch, not an unresolved E2/E3 implementation or current qualification gate. The script and its original acceptance criterion were left unchanged. Its result is **FAIL**, not relabeled PASS; the exact diff is retained. Current CTest and current-revision evidence-preservation checks pass independently.

## Gate status

PASS means reproducible evidence for the stated check; BLOCKED — EXTERNAL means a known missing runtime, hardware, weights or authorization; FAIL means a defect/validation failure; NOT VERIFIED means evidence is insufficient. Component checks do not promote their parent gate.

| Gate | Overall status now | Evidence and outstanding requirements |
|---|---|---|
| G0 | **NOT VERIFIED** | Local contracts/pin checks and dated Git export PASS. Registration, owner license/eligibility and dated attribution review lack owner evidence. Current common-revision qualification is BLOCKED — EXTERNAL. Git timestamps do not establish eligibility. |
| G1 | **BLOCKED — EXTERNAL** | Split/reader/export checks and pilot planning PASS locally. Requires final-revision physical pilot, measured camera/sensors, successful balanced demonstrations and upstream-reader validation of those actual exports. |
| G2 | **BLOCKED — EXTERNAL** | Host constraints, setup commands, model revisions and failure boundaries verified. Requires suitable provider quote, approved spend cap, persistent-storage retention and license/access confirmation. No price or budget has been assumed. |
| G3 | **BLOCKED — EXTERNAL** | Checkpoint/transfer/recovery/inference orchestration locally verified. Requires actual pretrained and backbone weights, GPU training imports, A/B optimizer/save/reload/inference, plus matching real B closed-loop evidence. |
| M0 | **BLOCKED — EXTERNAL** | Admission logic tested; requires source VLA-only success on >=25/50 frozen scenes and all nine separate instruction-flip tasks. Completed failing evaluation is retained, not rerun to select a better result. |
| M1 | **BLOCKED — EXTERNAL** | Matched E2/E3 planning and raw/statistical admission tested. Requires real matched target experiments and primary threshold above. E5 is not required for this initial limited claim. |

No G0–G3 or M0–M1 gate is represented as having passed through synthetic evidence. The repaired local engineering checks are PASS; no demonstrated in-scope implementation blocker remains. External execution may reveal new defects: the first session is qualification, not presumed success.

## Resources: measured versus estimated

- **Measured:** workstation inventory above; test timings/logs; cached metadata file sizes. No GR00T GPU peak, throughput, task success or physical dataset storage was measured in this audit.
- **Enforced capacity floors, not measured requirements:** training >=40 GiB total and >=38 GiB free VRAM; simulation >=16 GiB total and >=12 GiB free. Rental setup requires Ubuntu 22.04 x86_64, eight available CPU cores, NVIDIA driver >=580.65.06 and RTX/Vulkan rendering access. Simulation and training run in separate stages; policy inference and simulator coexist during closed-loop evaluation.
- **Planning estimate:** one 48 GB-class RTX A6000/RTX 6000 Ada/L40S-class device, >=48 GiB available host RAM (prefer 64 GiB-class host), persistent storage. These are an initial host profile, not proof that the pinned full stack fits. A100/H100 alone cannot meet this camera-rendering protocol. See [NVIDIA Isaac requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html).
- **Storage estimate:** locally cached model index metadata advertises 3,144,016,000 parameters and 6,910,361,856 weight bytes (index SHA-256 `407804ea5a62f4f8823f48811ae0edbb82fac101e9cf4d7273e6e2f692bb4d59`). This is metadata, not a measurement of downloaded snapshots. `training_campaign` conservatively reserves `62 * actual_weight_bytes + 12 GiB` for the three-run campaign: approximately **411 GiB** using that metadata; source-only reserve is about **128 GiB**. The doctor's 250 GiB pre-setup floor alone is insufficient assurance for the complete E2/E3 campaign. Plan roughly **600 GiB free persistent storage** (or a 1 TB-class volume) for runtimes, model/backbone caches, checkpoints and raw evidence; actual reserve and free-space checks remain authoritative.
- Raw 640x480 RGB at 30 Hz is about 26.4 MiB/second before compression, about 1.55 GiB/minute/camera. PNG/video size and episode length vary. Successful and failed attempts, both robots and all splits must be retained; measure pilot bytes and budget the 100-demo expansion before committing the full campaign.

Pinned [GR00T model information](https://huggingface.co/nvidia/GR00T-N1.7-3B) and [Cosmos access/license page](https://huggingface.co/nvidia/Cosmos-Reason2-2B) were inspected without acquiring weights. Cosmos requires gated access/license action. Owner license acceptance remains external; this report is not a legal determination.

## First rented-GPU session: exact commands, not executed here

Run from the final clean checkout on an approved Ubuntu host with the persistent mount at `/workspace`. **The first command is:**

```bash
python3 -m embodiment.rental doctor --prefix /workspace/viper --root /workspace/runs/viper
```

A fresh host may report missing runtimes before setup. Inspect its JSON and the dry-run setup plan. Then, only on the approved host and after license acceptance, proceed in bounded stages:

```bash
python3 -m embodiment.rental setup --prefix /workspace/viper --root /workspace/runs/viper
python3 -m embodiment.rental setup --prefix /workspace/viper --root /workspace/runs/viper --execute --accept-isaac-license
python3 -m embodiment.rental qualify --prefix /workspace/viper --root /workspace/runs/viper --execute --allow-gpu --accept-isaac-license
python3 -m embodiment.rental collect --prefix /workspace/viper --root /workspace/runs/viper --execute --allow-gpu --accept-isaac-license
python3 -m embodiment.rental report --prefix /workspace/viper --root /workspace/runs/viper
```

Require startup-smoke PASS, common qualification PASS and pilot `VALIDATED` with `training_ready=true` before training. Do not interpret process exit alone as qualification. Setup is permitted to install packages/assets when explicitly executed; it does not acquire model weights. Training-runtime setup and model acquisition remain separate:

```bash
python3 -m embodiment.rental setup --prefix /workspace/viper --root /workspace/runs/viper --training-runtime --execute --accept-isaac-license
```

Place authorized existing pinned GR00T and backbone snapshots in the configured cache, or separately opt in to `setup --training-runtime --allow-model-downloads --accept-model-license --execute --accept-isaac-license` after gated access is granted. Keep credentials outside logs. The following assumes `/workspace/viper/models/groot` resolves to the pinned snapshot:

```bash
python3 -m embodiment.rental g3 --prefix /workspace/viper --root /workspace/runs/viper --execute --allow-gpu --allow-training --accept-isaac-license
python3 -m embodiment.rental m0 --prefix /workspace/viper --root /workspace/runs/viper --steps 2000 --save-steps 500 --execute --allow-gpu --allow-training --accept-isaac-license
python3 -m embodiment.rental report --prefix /workspace/viper --root /workspace/runs/viper
```

An optimizer/inference receipt alone is not G3. Require `g3_closed_loop_verified=true` and independently valid raw closed-loop evidence. M0 must separately report PASS; a COMPLETE process or failed M0 is not learned control. Stop and investigate any failed physical gate, OOM, corrupt/relabelled evidence, incomplete held-out campaign or unmet resource check. Preserve failed attempts. Resume identical frozen inputs only; never select a new held-out evaluation because the old result was unfavorable.

## E2/E3 execution and statistical reporting

The pilot's 12 demonstrations validate plumbing, not primary M1. For exploratory E2/E3 with those same datasets, reuse the validated pilot G3 and campaign inputs below; `paired.json` must then say `primary_eligible=false`.

For the primary 100-B-demo study, collect separate balanced A/B **training** exports under a new immutable study root, with `embodiment.collection --target 100 --attempt-limit 300 --batch-size 2 --max-jobs 150`, retain failed attempts, validate physical exports and upstream video decoding, and predeclare the dataset hashes. The current training-plan validator requires equal A/B episode counts. Do not expand a hash-verified pilot in place. Run a new G3 against those exact exports; changing datasets invalidates the old G3 receipt and campaign root. No new held-out scenes or acceptance rules are introduced by this procedure.

For an already approved run, set these paths to the chosen immutable datasets/root before executing. The concrete defaults below reuse the pilot (exploratory only):

```bash
export PREFIX=/workspace/viper
export RUN=/workspace/runs/viper
export TRAIN_PY="$PREFIX/sources/GR00T/.venv/bin/python"
export SIM_PY="$PREFIX/simulation/bin/python"
export DATASET_A="$RUN/session/pilot/exports/openmanipulator_x/train"
export DATASET_B="$RUN/session/pilot/exports/franka_panda/train"
export CAMPAIGN="$RUN/campaign"
export G3="$RUN/g3"
export HF_HOME="$PREFIX/cache/huggingface"
export HF_HUB_CACHE="$HF_HOME/hub"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 WANDB_MODE=disabled
export VIPER_ACTION_CONTRACT_LIBRARY="$PREFIX/native/libviper_action_contract.so"
export VIPER_ASSET_CACHE="$PREFIX/robot_cache"
export VIPER_PANDA_USD="$PREFIX/assets/Isaac/IsaacLab/Robots/FrankaEmika/panda_instanceable.usd"
export LD_LIBRARY_PATH="$PREFIX/codec${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export OMNI_KIT_ACCEPT_EULA=YES
```

For a 100-demo study, set `DATASET_A`, `DATASET_B`, `G3` and `CAMPAIGN` to the separately frozen primary paths and execute `embodiment.cross_smoke` with those inputs, `--simulation-python "$SIM_PY" --native-library "$VIPER_ACTION_CONTRACT_LIBRARY" --execute` before the campaign. All GR00T training uses the same pinned source and pretrained snapshot. First complete `train_a` and `evaluate_a --m0` for this campaign using the same arguments as the loop below. Require the matching M0 gate before target stages:

```bash
"$TRAIN_PY" -c 'import sys; from pathlib import Path; from embodiment.m0 import verify; result=verify(Path(sys.argv[1])); print(result); assert result["status"] == "PASS", "M0 failed; preserve results and stop"' \
  "$CAMPAIGN/m0_evaluate_a/attempt-0000/evaluation"
```

Then run target training and evaluation:

```bash
for STAGE in train_b_only train_a_to_b evaluate_b_only evaluate_a_to_b; do
  "$TRAIN_PY" -m embodiment.training_campaign \
    --source "$PREFIX/sources/GR00T" --dataset-a "$DATASET_A" --dataset-b "$DATASET_B" \
    --pretrained "$PREFIX/models/groot" --root "$CAMPAIGN" --smoke-root "$G3" \
    --simulation-python "$SIM_PY" --steps 2000 --save-steps 500 \
    --batch-size 1 --gradient-accumulation 12 --stage "$STAGE" --execute || break
done
```

Source learning/M0 should be assessed before interpreting target transfer; the rental sequence above performs it. For a separate primary campaign, run its `evaluate_a --m0` stage after `train_a` to obtain the same admission evidence on the matching source checkpoint. Do not substitute an unrelated pilot checkpoint for the source donor.

Use the report paths in each verified completion receipt (normally attempt-0000 below); never pick a favorable attempt:

```bash
"$TRAIN_PY" -m embodiment.paired \
  --baseline "$CAMPAIGN/evaluate_b_only/attempt-0000/evaluation/report.json" \
  --transfer "$CAMPAIGN/evaluate_a_to_b/attempt-0000/evaluation/report.json" \
  --output "$CAMPAIGN/paired.json"
```

Expected reporting acceptance: `raw_episode_hashes_verified=true`, matching adaptation signature and protocols, every assigned scene present, correct checkpoint/source/robot/runtime binding, and explicit primary eligibility. The primary scientific outcome can validly **fail**; preserve and report that result. A negative experiment does not retroactively invalidate honest plumbing qualification.

## Artifact locations and acceptance

| Location | Expected artifacts |
|---|---|
| `/workspace/viper/deployment`, `/workspace/viper/setup` | Install plans, process logs, runtime/native/asset receipts |
| `$RUN/session/smoke` | One camera-enabled startup scene per robot; raw evidence and result |
| `$RUN/session/qualification` | Common-revision configuration, both 20-trial raw campaigns, hashes and result |
| `$RUN/session/pilot` | Frozen pilot, failed/accepted attempts, six split exports, upstream-reader receipts |
| `$G3` | A/B attempts, complete trainer checkpoints, conversion metadata, reload/inference metrics, separate closed-loop evidence |
| `$CAMPAIGN/models`, training/evaluation stage directories | Source/E2/E3 models, optimizer/scheduler/RNG state, trainable names, GPU/host/wall telemetry, immutable process/receipt files and raw episodes |
| `$CAMPAIGN/paired.json` | Hash-verified paired interval, eligibility, primary result and attribution caveat |
| `$RUN/pipeline` | Commands, attempt logs, validated completion receipts and reports |

First-session acceptance requires the existing physical, camera, sensor, source-integrity and success gates. Engineering failure includes any silent weight download, synthetic receipt admitted as real evidence, incorrect joint/action mapping, corrupted resume accepted, metadata mismatch, leaked train/evaluation scene, unmatched baseline budget, missing assigned trial or unsupported primary PASS. Those boundaries were locally tested. Real GPU memory, import, training, inference and closed-loop outcomes remain **BLOCKED — EXTERNAL** until executed and recorded.

**GO FOR GPU RENTAL** — for the initial E2/E3 study with the explicit limitations above. Remaining next steps require the selected runtime/hardware, authorized weights/assets, physical simulation execution or owner/provider authorization; they are not claimed as accomplished.
