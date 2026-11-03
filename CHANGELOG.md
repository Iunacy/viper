# Changelog

## 0.1.0-alpha.1 — 2026-11-03

Development snapshot. Learned manipulation and cross-embodiment transfer remain unvalidated.

### Added

- Recorded dual-robot demonstration and evidence viewer for OpenMANIPULATOR-X and Franka Panda.
- Pre-rental qualification report and reproducible command evidence for the initial E2/E3 study.
- One-command Linux CPU development setup, GitHub Actions CPU checks, and Apache-2.0 licensing for original code.

### Fixed

- Evaluation reports now bind robot, runtime, scene, fallback and policy provenance to their raw episodes.
- First-session retries preserve deadlines and qualification-only command scope.
- Replay GIF export isolates system FFmpeg from private reader libraries.

### Limitations

- Actual GR00T training, checkpoint reload/inference, current-revision Isaac qualification and learned closed-loop results require the selected GPU runtime and authorized weights.
- E4 provides checkpoint conversion only. E5 is not implemented; results cannot establish exclusive cross-embodiment attribution.
- This alpha is not a production release or physical-robot safety certification.
