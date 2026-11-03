# VIPER research interface

Explore recorded pick-and-place execution from OpenMANIPULATOR-X and Franka Panda in a static, interactive 3D laboratory.

Requires Node.js 22.12 or newer. From this directory:

```bash
npm ci --ignore-scripts && npm run dev
```

Open the printed local URL. The three included scenarios cover red, green and blue targets. Orbit or zoom the robot, scrub the recording, compare both arms, and open the inspector for joint states, tracking error and source provenance. Camera buttons and the timeline support keyboard input.

The homepage uses the same observed-state playback. Research presents historical classical qualifications, adaptive-control findings and the unverified learned-policy roadmap.

## Production

```bash
npm ci --ignore-scripts && npm run build
```

Serve `dist/` as static files. To preview locally, run `npm run preview`. For Vercel, set the project root to `web`, build command to `npm run build`, and output directory to `dist`. Included rewrites support `/lab` and `/research`. No backend, GPU server, API key or paid service is needed. Production: [VIPER](https://viperlab.vercel.app). The Vercel project `fourward-propagation/viper` is connected to this repository with `main` as its production branch and `web` as its root directory.

## What the recordings show

The bundled pack contains three historical paired seeds from the twenty-trial PhysX qualification campaigns. Geometry comes from the existing pinned MuJoCo reconstruction pipeline. Every original observation is retained at 30 Hz; recorded states are selected without physical interpolation or new dynamics. Both arms share elapsed time, and each holds its own terminal state when it finishes.

The robot campaigns use different source revisions. Playback is not a current-revision qualification, live robot control, or a learned-transfer result. GR00T execution is unverified. E4 provides checkpoint conversion only; E5 is not implemented.

WebGL is needed for 3D. When graphics are unavailable, telemetry and playback remain usable. Mobile panels collapse to preserve the scene. Recorded time pauses when the browser tab is hidden; reduced motion disables automatic hero playback.

See [evidence and implementation notes](../docs/INTERFACE.md) for export reproduction and limitations. Robot and font notices are included in `public/licenses/` and the deployed assets.
