![OpenMANIPULATOR-X and Franka Panda perform a recorded pick-and-place task](assets/simulation.gif)

# VIPER

VIPER researches robotic manipulation across different bodies through kinematics, bounded control, and GR00T policy integration.

<sub>Historical PhysX execution · MuJoCo state rendering · classical control · 4×</sub>

**In development.** Classical manipulation has historical physical-simulation evidence; learned manipulation and cross-embodiment transfer remain unvalidated. The initial study compares E2/E3 related-robot initialization, with [explicit qualification gates and attribution limits](docs/PRE_RENTAL_VERIFICATION.md).

[CPU checks](https://github.com/Iunacy/viper/actions/workflows/ci.yml) · [Changelog](CHANGELOG.md) · [Apache-2.0](LICENSE)

On Linux with [uv](https://docs.astral.sh/uv/getting-started/installation/), CMake 3.24+, a C++20 compiler and FFmpeg installed, set up the CPU development environment and native tools with one command:

```bash
bash scripts/install.sh
```

This installs development dependencies and builds the native tools. Isaac, GR00T weights and paid compute remain separate. Run offline checks with `.venv/bin/python -m unittest discover -s embodiment/tests -v` and native checks with `ctest --test-dir build-dev --output-on-failure`.

The recorded-evidence viewer runs locally with `VIPER_VIEWER_PYTHON=.venv/bin/python bash interactive/run.sh` at [localhost:8765](http://127.0.0.1:8765). Rendering requires the cached, pinned robot assets described in [the viewer documentation](interactive/README.md). A hosted demo will follow the frontend design and Vercel deployment; there is no live demo yet.

VIPER was formerly named RELIC. Historical commits, run schemas, package namespaces, datasets, and `RELIC_*` settings retain that identity for attribution and compatibility. The current repository is [Iunacy/viper](https://github.com/Iunacy/viper).

The recorded dual-robot evidence viewer displays classical PhysX execution, synchronized playback, applied actions, next-tick tracking error, and intervention provenance. Learned transfer remains unavailable. The C++/Ruckig foundation is separate from Isaac control; `viper_cli` and the compatible `relic_cli` target run the same native implementation.

The shared policy preserves six OpenMANIPULATOR-X and nine Panda joint channels, yielding 16- and 22-dimensional native states. Both predict world-frame Cartesian increments and an open-positive gripper command, with robot-specific admissible grasp orientation. Model-capacity padding happens only in the pinned upstream processor. No joint channel is reinterpreted as another robot's joint.

The transfer preparation restores target projector slot 10 from the same local pretrained checkpoint for E2 and E3, inherits shared weights from the appropriate donor, and recomputes Panda statistics with the pinned upstream training-data reader. Synthetic checkpoint tests verify conversion rules; actual GR00T-weight loading, optimizer steps, and learned closed-loop execution remain unverified.

On an approved GPU host with locally cached model **and backbone** weights, validated physical LeRobot datasets, and the pinned upstream environment:

```bash
python -m embodiment.cloud --source "$GROOT_SOURCE" --pretrained "$PRETRAINED" --volume "$RUN_VOLUME"
python -m embodiment.cross_smoke --source "$GROOT_SOURCE" --dataset-a "$DATASET_A" --dataset-b "$DATASET_B" --pretrained "$PRETRAINED" --output "$RUN_VOLUME/g3"
# Explicit compute opt-in, after the dry run and separate spending approval:
python -m embodiment.cross_smoke --source "$GROOT_SOURCE" --dataset-a "$DATASET_A" --dataset-b "$DATASET_B" --pretrained "$PRETRAINED" --output "$RUN_VOLUME/g3" --execute
```

The dry run launches no training or simulator and downloads no model. Completed training stages are reused only after checkpoint integrity checks; failed attempts remain on disk and retries use new attempt directories. Optimizer recovery checks saved model, optimizer, scheduler and RNG integrity. The instrumented upstream worker records actual trainable parameter names, wall time and peak allocated GPU memory when execution is authorized. An optimizer/inference pass is not a full G3 pass: execute the target policy in the separate `embodiment.policy_service` and `embodiment.evaluate` paths before claiming closed-loop control. Training checkpoint preparation records upstream runtime gates explicitly.

Freeze a bounded pilot with `python -m embodiment.pilot --root "$RUN_VOLUME/pilot" --episodes 12`. Its manifest contains paired scene specifications and explicit collection commands; it is not a dataset. Collection receipts preserve failed attempts and accept only physically successful camera episodes. Existing qualifications remain historical evidence. Generate a common-revision command with `python -m embodiment.qualification_pair --root "$RUN_VOLUME/qualification"`; add `--execute` only in the qualified Isaac runtime on a clean committed revision.

New training plans use 50 frozen held-out scenes. `python -m embodiment.paired --baseline baseline.json --transfer transfer.json --output paired.json` computes deterministic 10,000-resample scene-paired intervals. The primary rule remains +20 percentage points at 100 B demonstrations with a 95% interval excluding zero. Legacy 20-scene reports remain readable and cannot satisfy that primary rule. Report-level validation does not replace auditing raw episode hashes. Without E5, any benefit is attributable to related-robot initialization, not exclusively cross-embodiment transfer.

Offline checks: `python -m unittest discover -s embodiment/tests -v`. Set `RELIC_GROOT_SOURCE` to enable pinned upstream reader, normalization, serialization, and projector checks. TorchCodec may need an isolated FFmpeg 7 library path; keep the system encoder's library environment separate. Export dated attribution evidence with `python -m embodiment.provenance --output /tmp/viper-provenance.json`.

Open gates: G0 registration, license review, dated attribution review and common-revision qualification; G1 physical pilot and upstream-reader qualification on the final revision; G2 rental quote and approved budget; G3 real A-to-B optimizer/save/reload/inference and closed-loop execution. M0 requires learned source control on held-out scenes; M1 requires matched target experiments. No paid compute or large model download is performed by these preparation commands.

Original code is licensed under [Apache-2.0](LICENSE). Vendored code, robot assets, dependencies and model weights retain their separate licenses; see [NOTICE](NOTICE).
