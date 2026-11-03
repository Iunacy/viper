![OpenMANIPULATOR-X and Franka Panda perform a recorded pick-and-place task](assets/simulation.gif)

# VIPER

VIPER explores how different robot arms perform the same manipulation task through bounded, feedback-driven control.

<sub>Recorded PhysX execution · MuJoCo state rendering · classical control · 4× playback</sub>

OpenMANIPULATOR-X and Franka Panda pick up the requested colored cube, lift it, carry it to the bin, release it, and retreat. OpenMANIPULATOR-X uses four arm joints; Panda uses seven. Each follows its own joint limits and grasp orientation while working in the same scene.

In their historical simulation qualification runs, **both robots completed 20 of 20 pick-and-place trials**, with no wrong-color picks. These runs used classical controllers on different revisions. They show task execution by both bodies; they do not demonstrate learned transfer between them. Learned manipulation is still in development.

The recording above is the public demo. The research viewer can also play, pause, and scrub through both robots’ motion, alongside their actions and tracking error, when the original local campaign recordings and robot assets are available. Those recordings and assets are not bundled in a fresh checkout.

## Install local tools

On Linux, install [uv](https://docs.astral.sh/uv/getting-started/installation/), CMake 3.24+, a C++20 compiler, and FFmpeg, then run:

```bash
bash scripts/install.sh
```

This sets up the CPU research tools; it does not install Isaac or model weights. The interactive viewer needs separate local recordings and robot assets. There is no hosted demo yet—the Vercel version will follow the frontend design.

[Research details and limitations](docs/PRE_RENTAL_VERIFICATION.md) · [Changelog](CHANGELOG.md) · [Apache-2.0](LICENSE)

VIPER was formerly named RELIC; older package names and recorded data retain that name. Third-party code, robot assets, and model weights keep their own licenses; see [NOTICE](NOTICE).

Explore the interactive 3D laboratory locally: [research interface](web/README.md).
