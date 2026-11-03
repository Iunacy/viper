![OpenMANIPULATOR-X and Franka Panda perform a recorded pick-and-place task](assets/simulation.gif)

# VIPER

VIPER explores how different robot arms perform the same manipulation task through bounded, feedback-driven control.

<sub>Recorded PhysX execution · MuJoCo state rendering · classical control · 4× playback</sub>

OpenMANIPULATOR-X and Franka Panda pick up the requested colored cube, lift it, carry it to the bin, release it, and retreat. OpenMANIPULATOR-X uses four arm joints; Panda uses seven. Each follows its own joint limits and grasp orientation while working in the same scene.

In their historical simulation qualification runs, **both robots completed 20 of 20 pick-and-place trials**, with no wrong-color picks. These runs used classical controllers on different revisions. They show task execution by both bodies; they do not demonstrate learned transfer between them. Learned manipulation is still in development.

**[Enter the live laboratory](https://viperlab.vercel.app/lab)** · [Research](https://viperlab.vercel.app/research)

Explore three recorded pick-and-place scenarios in 3D. Orbit either arm, scrub its motion, compare both robots, and inspect joint states and tracking error. The browser demo includes the recordings and needs no GPU server.

## Install local tools

On Linux, install [uv](https://docs.astral.sh/uv/getting-started/installation/), CMake 3.24+, a C++20 compiler, and FFmpeg, then run:

```bash
bash scripts/install.sh
```

This sets up the CPU research tools; it does not install Isaac or model weights. To run the browser laboratory locally, see the [research interface setup](web/README.md).

[Research details and limitations](docs/PRE_RENTAL_VERIFICATION.md) · [Changelog](CHANGELOG.md) · [Apache-2.0](LICENSE)

VIPER was formerly named RELIC; older package names and recorded data retain that name. Third-party code, robot assets, and model weights keep their own licenses; see [NOTICE](NOTICE).
