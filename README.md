# SO-101 keyboard typing: training and deployment

Train an SO-101 typing policy in Newton, compare actuator/physics configurations,
and export the trained policy for a LeRobot-calibrated follower. Released
checkpoints and the published fixed-fixture benchmark are included as a starting
point. Users can change the nominal keyboard pose, randomize placement during
training, and deploy using the nominal geometry saved with their own policy.

The new six-letter policy passed 2,027/2,048 simulation episodes (98.97%) after
32 min 14 s of training-loop time on an RTX 5090. Training, evaluation, placement
tests and CPU deployment checks are measured; second-robot physical validation is pending.
See [results and timing](docs/release/RESULTS.md).
See [validation status](docs/release/STATUS.md) for evidence and limitations.

## Try a released policy

Requirements: Linux x86-64, an NVIDIA GPU, Docker with NVIDIA Container Toolkit,
and host Python 3. The pinned container supplies Isaac Lab, Newton and RSL-RL;
no private checkout or cluster account is needed. Allow space for the Isaac Lab image
and build layers. The verified workstation uses an RTX 5090 with 32 GB VRAM;
minimum GPU/driver requirements and other GPU models remain to be qualified.

```bash
git clone https://github.com/VigneshBhavan/so101-keyboard-task-public.git
cd so101-keyboard-task-public
./so101 build
./so101 download
./so101 probe

./so101 video --actuator anchorbench \
  --checkpoint .artifacts/so101-keyboard-typing-benchmark/checkpoints/public-transit15-seed1307/model_549.pt \
  --env-config .artifacts/so101-keyboard-typing-benchmark/checkpoints/public-transit15-seed1307/params/env.yaml
```

`video` writes an MP4 and evaluation report under `output/public/`. Use `play`
instead for an interactive Newton viewer (X11 DISPLAY/XAUTHORITY required), or
`evaluate` for headless seeded episodes. Supply `--num-envs` to set evaluation size.

## Train and choose physics

```bash
# Short startup training; increase iterations for a learned policy.
./so101 train --actuator anchorbench --stage p1a --iterations 10
./so101 train --actuator usd --stage p1a --iterations 10
./so101 train --actuator workshop --stage p1a --iterations 10

# Custom solver settings / actuator parameters, and keyboard placement or DR.
./so101 train --actuator usd --stage p1a \
  --physics-config configs/physics/mjwarp-soft-drives.json \
  --task-config configs/tasks/keyboard-domain-randomization.json --iterations 10
```

Actuator choices are AnchorBench-fitted parameters, the loaded USD drives, and the
Workshop baseline. Newton MJWarp is the supported solver in this interface; Sparse
VBD is not yet qualified. JSON can vary solver substeps/iterations/tolerance and
actuator stiffness, damping, armature, friction, and limits. Keyboard position,
yaw, planar pose randomization and reset-joint noise have a separate task JSON.

Training writes checkpoints, resolved `params/env.yaml`, and the optional
`public_physics.json` / `public_task.json` beside it. Evaluation and resume restore
those JSONs automatically. Evaluation rejects configurations that differ from the
saved environment contract.
Every run records source/image identity, requested settings, inputs and console logs.

Read [task configuration](docs/release/TASK_CONFIGURATION.md),
[the detailed quickstart](docs/release/QUICKSTART.md), and
[training stages and budgets](docs/release/TRAINING.md).

## Calibrate and deploy

Robot calibration uses the standard Hugging Face LeRobot SO-101 follower procedure.
The deployment environment is CPU-only and separate from the simulator.

```bash
./so101 setup-hardware
source .venv-hardware/bin/activate
lerobot-calibrate --robot.type=so101_follower \
  --robot.port=/dev/serial/by-id/YOUR_CONTROLLER --robot.id=my_typing_robot

./so101 prepare-deployment --checkpoint /absolute/path/to/model_N.pt \
  --env-config /absolute/path/to/params/env.yaml --robot-id my_typing_robot \
  --encoder-convention lerobot --out-dir output/my_typing_robot

# No hardware connection: validate the exported inputs first.
./so101 deploy output/my_typing_robot NVIDIA
```

Use `HE` for a two-letter P1A policy and six letters for Transit15. The bundle
exports the trained nominal map, joint reference and normalization. `lerobot`
uses calibrated degrees without the benchmark robot's additional fitted offsets;
`benchmark` explicitly selects those historical corrections. Check physical/model
alignment before enabling motion. The operator-run `--execute` command, device
setup, and full calibration procedure are in [the hardware guide](docs/release/HARDWARE_PREPARATION.md).

## Reference setup and results

[FIXTURE_SETUP.md](FIXTURE_SETUP.md) describes the published Logitech MX keyboard,
fixed typing jaw, closed moving jaw and 4.44 mm mat. It is a reference fixture for
reproducing the released checkpoints, not a restriction on new training. Changed
poses and DR require training/evaluation for the intended setup. The actor receives
nominal targets and proprioception; it receives no camera input or hidden sampled
keyboard pose. Hardware key-down/key-up events provide typing feedback.

Matched checkpoints, configuration files, evaluation reports and checksums:
[Hugging Face benchmark dataset](https://huggingface.co/datasets/VigneshBhavan/so101-keyboard-typing-benchmark).
The historical source snapshot is `1b8cb7e8176021685325724b62c41b1fe394c25a`.
[Runtime provenance](runtime/README.md) records the public base and required patch.

The retained source is also usable as an overlay through
`scripts/overlay_into_isaaclab.sh`; the supported fresh-user installation uses the
pinned container. Training, evaluation, and hardware preparation use the public
commands documented above.
