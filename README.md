# SO-101 keyboard typing: train and deploy

Train an SO-101 typing policy in Newton for your keyboard placement, evaluate it,
and deploy using the geometry saved during training and your robot's LeRobot
calibration. An established AnchorBench ~19k checkpoint is available as an
**optional shortcut for the documented reference fixture**.

## Install

Requirements: Linux x86-64, an NVIDIA GPU, Docker with NVIDIA Container Toolkit,
and host Python 3. The pinned container supplies Isaac Lab, Newton and RSL-RL.
The tested GPU is an RTX 5090 with 32 GB; other GPUs and minimum requirements
remain to be qualified. No private checkout or cluster account is required.

```bash
git clone https://github.com/VigneshBhavan/so101-keyboard-task-public.git
cd so101-keyboard-task-public
./so101 build
```

## Workflow 1: train for your setup

Choose the nominal keyboard position/orientation relative to the robot in
simulation. Your physical fixture must match that trained geometry at deployment.
The task JSON supports nominal XYZ/yaw and optional XY/yaw placement randomization.
See [task configuration](docs/release/TASK_CONFIGURATION.md) for coordinates and units.

```bash
cp configs/tasks/keyboard-pose.json configs/tasks/my-keyboard.json
# Edit my-keyboard.json for your intended physical layout before training.
./so101 probe --task-config configs/tasks/my-keyboard.json

# Startup check; this budget is not intended to produce a deployable policy.
./so101 train --actuator anchorbench --stage p1a \
  --task-config configs/tasks/my-keyboard.json --num-envs 64 --iterations 10
```

Continue with the [P1A-to-six-letter training recipe](docs/release/TRAINING.md).
Choose `anchorbench`, `usd` or `workshop` actuators. Optional `--physics-config`
JSON configures Newton MJWarp and actuator parameters. Sparse VBD is not exposed
by this interface. No pretrained download is needed to train from scratch.

Evaluate your selected checkpoint with its matching stage and configuration:

```bash
./so101 evaluate --actuator anchorbench --stage transit15 \
  --checkpoint /absolute/path/to/model_N.pt \
  --env-config /absolute/path/to/params/env.yaml --num-envs 1024
./so101 video --actuator anchorbench --stage transit15 \
  --checkpoint /absolute/path/to/model_N.pt \
  --env-config /absolute/path/to/params/env.yaml --target NVIDIA
```

Keep the full `params/` folder. Resume and evaluation restore saved task/physics
JSONs; export uses the trained nominal key map and joint reference. Use `p1a` and
a two-letter target for P1A checkpoints. Runs and videos are saved under `output/`.

## Workflow 2: optionally try the established ~19k checkpoint

This AnchorBench checkpoint was trained for a specific keyboard pose and fixed
jaw. Simulation playback needs no physical robot. **Physical use requires matching
its trained fixture geometry**, not placing the keyboard wherever convenient.

| Reference-fixture requirement | Trained value |
| --- | --- |
| Keyboard CAD origin relative to robot model base | `(262.565, 12.135, 1.781) mm` |
| CAD roll, pitch, yaw | `(-5.000, 0.051, -88.606) degrees` |
| Near case edge beyond robot-base housing | `125.28 mm` |
| Keyboard and jaw | Reference Logitech MX geometry; fixed typing jaw, moving jaw closed |
| Mat under keyboard | `4.44 mm` |

CAD angles are not physical top-down yaw. Follow [FIXTURE_SETUP.md](FIXTURE_SETUP.md)
for the authoritative quaternion, placement convention and manual alignment checks.
The matching environment YAML is the checkpoint's source of truth. If your setup
cannot match it, use workflow 1 to train for your intended placement.

```bash
./so101 download
./so101 video --actuator anchorbench --stage transit15 \
  --checkpoint .artifacts/so101-keyboard-typing-benchmark/checkpoints/mjwarp-anchorbench-19k/model_19000.pt \
  --env-config .artifacts/so101-keyboard-typing-benchmark/configs/mjwarp-anchorbench-19k.env.yaml
```

The default download contains only these weights, their environment and evaluation
report, verified against pinned hashes. `./so101 download --all` explicitly fetches
the complete benchmark/development archive. Existing downloaded files are retained.

## Both workflows: calibrate your robot and deploy

**You perform standard LeRobot calibration on your own robot.** Calibration
establishes encoder coordinates; it does not measure the keyboard pose. Do not
copy another robot's calibration or assume its additional fitted offsets apply.

```bash
./so101 setup-hardware
source .venv-hardware/bin/activate
lerobot-calibrate --robot.type=so101_follower \
  --robot.port=/dev/serial/by-id/YOUR_CONTROLLER --robot.id=my_typing_robot

./so101 prepare-deployment --checkpoint /absolute/path/to/model_N.pt \
  --env-config /absolute/path/to/matching/env.yaml --robot-id my_typing_robot \
  --encoder-convention lerobot --out-dir output/my_typing_robot
./so101 deploy output/my_typing_robot NVIDIA
```

For workflow 2, supply the downloaded `model_19000.pt` and
`configs/mjwarp-anchorbench-19k.env.yaml` paths above. For workflow 1, supply your
own selected checkpoint and its `params/env.yaml`.

The last command is a software dry run. Match the physical fixture to the saved
simulation geometry and check model/encoder alignment before enabling motion.
[The hardware guide](docs/release/HARDWARE_PREPARATION.md) provides the explicit
operator-run execution command. `benchmark` encoder offsets are only for
reproducing the historical robot's separately fitted convention.

## Documentation and validation

- [Detailed quickstart](docs/release/QUICKSTART.md)
- [Training](docs/release/TRAINING.md) and [task/physics configuration](docs/release/TASK_CONFIGURATION.md)
- [Hardware preparation](docs/release/HARDWARE_PREPARATION.md) and [reference fixture](FIXTURE_SETUP.md)
- [Software validation status](docs/release/STATUS.md) and [independent reproduction record](docs/release/REPRODUCTION.md)
- [Benchmark artifacts](https://huggingface.co/datasets/VigneshBhavan/so101-keyboard-typing-benchmark) and [runtime provenance](runtime/README.md)

Software execution and deployment dry runs have been tested locally. Physical
reproduction on another user's SO-101 remains unverified. Development-training
measurements are retained separately in the validation archive.
