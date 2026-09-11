# New-user release acceptance ledger

The configurable software pipeline is implemented and locally qualified through
six-letter simulation, placement evaluation, export and CPU inference parity.
See [measured results](RESULTS.md) and the [recipient record](REPRODUCTION.md).
Independent installation and second-robot hardware reproduction remain pending.
All new simulation runs use Newton MJWarp; no hardware motion was executed.

| Requirement | Implemented and measured evidence | Remaining qualification |
| --- | --- | --- |
| Public runtime | Public image digest, source ancestor and runtime patch build successfully; GPU reset/action probe passes | Independent recipient installation and GPU/driver coverage |
| Training | AnchorBench, USD and Workshop save checkpoints and environment YAML; custom task/physics training and resume smoke tests pass; 64-environment, 10-update baseline and DR runs pass | 501 P1A plus 50 Transit15 updates measured; wider seed/GPU coverage remains |
| Released policy playback | 4/4 strict evaluation episodes passed; recorded NVIDIA typing passed and frames were inspected | Larger sequence corpus; interactive X11 viewer |
| Physics choices | JSON solver settings and actuator parameters saved/restored with contract hashes | Sparse VBD is not supported by this interface |
| Keyboard placement and DR | Nominal XYZ/yaw transform updates mesh and map; per-reset XY/yaw and joint noise; 3-reset probe preserved actor nominal map | Fixed-policy XY/yaw tolerance measured; physical and cross-physics robustness pending |
| Staged recipe | Public P1A-to-Transit15 commands, output conventions and budget caveats documented | Short learned recipe qualified; optional 20,000-update budget not reproduced |
| Standard robot calibration | Pinned CPU-only LeRobot environment installs; official follower calibration command documented | Operator performs calibration on their own robot |
| Deployment bundle | Saved nominal geometry, q_reset, normalization, IDs and artifact hashes exported; standard and moved-keyboard/custom-physics dry runs pass | Operator-run physical/model alignment and typing validation |
| Reference fixture | Published Logitech MX keyboard, fixed typing jaw, closed moving jaw and 4.44 mm mat documented | Users measure their actual layout; benchmark reproduction requires matching its geometry |
| Repository | Canonical public repository: [VigneshBhavan/so101-keyboard-task-public](https://github.com/VigneshBhavan/so101-keyboard-task-public) | Code publication does not establish physical qualification |

Acceptance: a recipient can install, try a released checkpoint, train with the
supported physics/task configuration, evaluate, calibrate their own robot using
LeRobot, and deploy using the saved nominal geometry. Software tests alone do not
establish successful typing on another physical robot.

The benchmark fixture is the default reference, not a restriction on training.
Changed nominal placement and bounded pose randomization are supported. See
[TASK_CONFIGURATION.md](TASK_CONFIGURATION.md) and
[HARDWARE_PREPARATION.md](HARDWARE_PREPARATION.md).

## Evidence and limits

`validation_runs.json` records successful local run IDs, image identities and
selected results. Host checks passed: 85 tests, 2 skipped, and 7 subtests. They cover
CLI/configuration validation, geometry
transforms, deployment identity/hash checks, and the existing homing contracts.
The Newton container contract suite passes 37 tests.
Randomly initialized smoke checkpoints are not expected to type successfully;
their evaluation checks configuration restoration and execution only.

These tests use an isolated public-derived container on the existing RTX 5090
workstation. A 4096-environment, 10-update capacity test completed in 36.72 seconds of
training time after initialization; one GPU sample showed 17,560 MiB total usage.
This establishes capacity for startup, not a full training result or peak memory.
The hardware dependency environment was installed separately with
CPU-only PyTorch. Bundle dry runs do not open serial devices. The standard LeRobot
encoder convention is implemented; the additional historical benchmark joint
corrections are not assumed to apply to other robots.

## New policy evidence

The new six-letter checkpoint passes 2027/2048 strict episodes, with 3 wrong-key
and 18 scrape failures. NVIDIA video passes; CPU inference matches 261 recorded
actions within 1.32e-6. Training is stopped. Metadata cleanup preserves historical
weights and numerical results, with relative checksums and pinned downloads.
Independent installation and physical typing remain pending.
Contact qualification is also incomplete: peak simulated key travel is 1.579
times the nominal range for the new six-letter policy. Strict success preserves
the existing event contract and does not reject that overtravel.

A fresh Git clone and new Python environments passed all 10 software validation
steps: public download/audit, cached image build, GPU probe, one-update training,
64/64 released-policy episodes, hardware setup, export, dry run and CPU parity.
Docker/package caches were reused on the same workstation; this does not count
as independent-machine or physical reproduction.
