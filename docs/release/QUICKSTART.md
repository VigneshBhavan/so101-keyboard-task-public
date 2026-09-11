# New-user workflow

Use Linux x86-64, an NVIDIA GPU, Docker with NVIDIA Container Toolkit and host
Python 3. Building uses the pinned NVIDIA Isaac Lab image and its applicable
license terms. No private repository or cluster account is required. Simulation does
not receive robot devices. See [STATUS.md](STATUS.md) for measured validation.

## Build and try a released policy

```bash
./so101 build
./so101 download
./so101 probe
./so101 video --actuator anchorbench --stage transit15 \
  --checkpoint .artifacts/so101-keyboard-typing-benchmark/checkpoints/mjwarp-anchorbench-19k/model_19000.pt \
  --env-config .artifacts/so101-keyboard-typing-benchmark/configs/mjwarp-anchorbench-19k.env.yaml
```

`video` records an MP4 and evaluation report. Replace it with `evaluate` for
headless episodes, or `play` for the interactive Newton viewer. `play` requires an
accessible X11 `DISPLAY` and, where needed, `XAUTHORITY`. Its interactive window
has not yet been qualified; recorded playback has been tested.

The probe checks zero-action stability and bounded joint actions. It skips the
historical one-letter logical/contact probes, which do not apply unchanged to the
multi-letter task. It is not a contact or policy-quality test.

First startup compiles Warp kernels. The launcher retains the cache in a named
Docker volume and disables the optional Omniverse Hub cache with
`OMNICLIENT_HUB_MODE=disabled`, as documented by the
[Omniverse Client Library](https://docs.omniverse.nvidia.com/kit/docs/client_library/latest/index.html).
The source fingerprint check requests a rebuild when runtime code changes.

## Train with a chosen configuration

```bash
./so101 train --actuator anchorbench --stage p1a --num-envs 64 --iterations 10
./so101 train --actuator usd --stage p1a --num-envs 64 --iterations 10
./so101 train --actuator workshop --stage p1a --num-envs 64 --iterations 10

./so101 train --actuator usd --stage p1a \
  --physics-config configs/physics/mjwarp-soft-drives.json \
  --task-config configs/tasks/keyboard-domain-randomization.json --iterations 10
```

These are short setup checks. Use [TRAINING.md](TRAINING.md) for the staged
P1A-to-Transit15 recipe and training-budget limitations. Add `--plan` to inspect
the command without starting simulation or writing outputs.

Newton MJWarp supports solver substeps, iterations, line-search iterations and
tolerance. Actuator JSON supports stiffness, damping, armature, friction,
dynamic/viscous friction and effort/velocity limits. Values may be scalars or
complete six-joint maps. Unknown fields and invalid values are rejected.
Sparse VBD is not exposed in this qualified interface.

[TASK_CONFIGURATION.md](TASK_CONFIGURATION.md) covers nominal keyboard XYZ/yaw,
XY/yaw randomization and robot reset-joint noise. The benchmark physical fixture
is a reference setup. Sampled pose perturbations are not supplied to the actor.

## Evaluate your training

```bash
./so101 evaluate --actuator usd --stage p1a \
  --checkpoint /absolute/path/to/model_N.pt \
  --env-config /absolute/path/to/params/env.yaml --num-envs 64
```

Select the same actuator and stage used for that checkpoint. Keep the complete
`params/` directory: evaluation automatically restores `public_physics.json` and
`public_task.json` beside `env.yaml`. Their hashes and nominal geometry are checked
against the saved environment. Arbitrary edits to YAML outside the supported JSON
interfaces are not a configuration-restoration mechanism.

Runs live under `output/public/`. Requests record image/source identity, command,
seed and input hashes; training saves the resolved environment and agent YAML.
Each run also saves its console log and exit code. Compare policies with matched
sample budgets, seeds, configurations and sequence banks.

## Calibrate and deploy

Follow [HARDWARE_PREPARATION.md](HARDWARE_PREPARATION.md): install the isolated CPU
LeRobot environment, run the standard SO-101 follower calibration, export a
checkpoint/geometry bundle, and run its software dry run before operator-enabled
hardware execution. The bundle uses the trained nominal map, including changed
keyboard geometry and custom physics contracts. Standard LeRobot coordinates and
the benchmark robot's extra offsets are explicit, separate choices.

This software path has been tested locally. A new-user physical reproduction on
a second SO-101 remains pending.
