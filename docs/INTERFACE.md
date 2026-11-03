# Cinematic research interface

Implementation lives in `web/`, isolated from all robotics, training, evaluation and protocol code. Routes: `/`, `/lab`, `/research`. The interface can be served as static files without a backend. See `web/README.md` for development and Vercel instructions, and `web/DESIGN.md` for design tokens and interaction decisions.

## Evidence and export

`web/tools/export_replays.py` calls the existing `load_qualified_pair` and `Renderer` from the repository. This verifies original campaign report and per-trial hashes, matches scenarios across embodiments and constructs the existing pinned robot models. It exports seeds 0, 1 and 2 (red, green and blue).

Every original 30 Hz observation is preserved. Joint positions, velocities, end-effector position, phase and one-step tracking error are copied from the existing replay state. Body poses are calculated by MuJoCo forward kinematics from those recorded joints and cube poses, checked against recorded end-effector positions within the existing 0.2 mm tolerance, then rounded to seven decimal places. No dynamics or learned policy is executed. Browser playback uses the preceding recorded observation without interpolation, with the same tick-boundary epsilon as the existing reader. Each embodiment holds its own last observation at the common end time.

GLB geometry is exported from the existing compiled MuJoCo meshes and scene boxes. Official ROBOTIS and Franka source manifests remain the geometry authority. The browser changes lighting, material presentation and camera; it does not change the recorded physical state. Ground and grid are presentation aids. Trajectory and commanded target overlays derive from the selected recording.

The export manifest binds every shipped replay, mesh and metric JSON by SHA-256, and identifies the replay producer source hashes. Replay files also retain all four original per-trial file digests and the campaign's source revision. Public qualification copies omit only the local-machine `raw_artifact_root`; all remaining fields match the repository artifacts exactly. Adaptive metric reports are copied byte-for-byte from `adaptive/revision/`.

To reproduce the pack, use the optional existing replay Python environment, the original raw campaign roots recorded in `embodiment/qualification/*.json`, and the pinned robot asset cache:

```bash
VIPER_ASSET_CACHE=/path/to/pinned/robot_cache /path/to/replay/python web/tools/export_replays.py
```

Original raw campaigns are not required to browse or build the committed static pack. They are required to regenerate it. Export dependencies are those of the existing viewer, plus trimesh already used by its Panda conversion. Source and redistributed-asset notices ship under `web/public/licenses/`.

## Scientific limits

Both classical campaigns recorded 20/20 successful placements and zero wrong-color picks. OMX uses revision `0091cfe`; Panda uses `c4b7da5`. They are historical, separately qualified campaigns, not a current common-revision comparison. Synchronized elapsed time is a replay convenience, not experimental matching across source revisions.

Research metrics load from shipped artifacts, including Wilson intervals and native adaptive study cluster-bootstrap intervals. The exploratory analytical PI baseline has lower tracking RMSE than shared learned adaptive correction. The failed three-to-four-joint probe is stated explicitly. Native adaptive correction is a separate study from the PhysX manipulation recordings and is not evidence of GR00T transfer.

E2/E3 is the initial learned-policy study scope with limited attribution. Real GPU training, checkpoint recovery, inference and learned closed-loop evaluation have no successful execution evidence here. E4 is checkpoint conversion infrastructure only; E5 is not implemented and is required for future transfer-specific attribution claims.

## Interaction and accessibility

The lab supports deterministic play/pause, scrubbing, restart, 0.25–4× speeds, three recording selections, either robot, synchronized comparison, orbit/zoom/reset, trajectory/target overlays and a collapsible telemetry/provenance inspector. Camera buttons complement pointer gestures; the native timeline supports keyboard input. Inspector tabs support arrow keys, Home and End. Recorded time pauses when the tab becomes hidden. Reduced motion leaves the hero initially paused and removes CSS entrance/route animations.

Mobile starts with the inspector closed. Research tables scroll horizontally within their region. The homepage uses a single viewport without page scrolling. Fetch failures provide retry; geometry or WebGL failures leave recorded telemetry available. The interface is a recording browser, with no live commands or unsupported learned-policy selector.

## Validation

Type checking, ESLint, production build, component clock/navigation checks, recording-boundary checks, all six replay integrity checks, export-manifest hashes and qualification-source parity are exercised by the frontend suite. The frontend CI workflow runs the same checks without invoking scientific pipelines. The dependency audit reports zero known vulnerabilities at implementation time; a minimatch 11.0.4 override resolves the development-tool advisory and the configured lint suite passes with it.

The Three.js viewer is lazy-loaded. Vite reports its approximately 643 kB minified / 161 kB gzip chunk as larger than its default warning threshold. Robot geometry totals approximately 7.4 MB, with roughly 6 MB of replay JSON across six recordings; only the chosen scene and selected pair are requested. Static hosts should enable standard compression. The research route does not load Three.js.

Production preview was inspected in the in-app browser at 1280×720, 390×844 and 320×568. The homepage document had no horizontal or vertical overflow at all three sizes. Camera orbit/zoom/reset, speed selection, play/pause, keyboard terminal scrubbing, recording/robot selection, comparison, inspector expansion and arrow-key tab switching were exercised. The production tab recorded no application warnings or errors; earlier development navigation recorded browser-native view-transition opt-in messages, without interrupting navigation.

Screenshots: [desktop home](interface-screenshots/home-desktop.jpg), [mobile home](interface-screenshots/home-mobile.jpg), [compact home](interface-screenshots/home-compact.jpg), [desktop lab](interface-screenshots/lab-desktop.jpg), [mobile lab](interface-screenshots/lab-mobile.jpg), [desktop research](interface-screenshots/research-desktop.jpg), [mobile research](interface-screenshots/research-mobile.jpg).

Local automated validation: 15 checks passed across four test files, type checking passed, lint passed and the production build passed. The design detector returned no findings. This verifies the interface and its exported historical evidence, not new robot or GPU execution. The unavailable-WebGL fallback is covered by a focused component test; it disables all camera actions while leaving the recording workspace independent. Reduced motion and actual GPU/context loss were not exercised through OS/browser emulation in this session. The independent finish review’s sole material finding (enabled camera buttons during graphics failure) was resolved and received a SHIP verdict at that review scope.

## Production deployment

Public site: https://viper-delta-henna.vercel.app. Vercel project: `fourward-propagation/viper`, connected to `Iunacy/viper`, production branch `main`, root `web`, build `npm run build`, output `dist`. The initial ready deployment uses commit `e7023f9`. No application environment variables are required.

Production smoke checks cover `/`, `/lab`, `/research`, the recording catalog and both robot geometry assets. For rollback after a future regression, select a previously verified Ready deployment in the Vercel project and promote it back to production; the historical robotics evidence remains unchanged.
