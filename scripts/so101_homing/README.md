# SO-101 Physical Keyboard Deployment

The production hardware path is the dated `physical-calibrated-20260718`
fixed-Cartesian policy family. It uses a frozen powered A-Z map and starts from
the exact simulator reset. It does **not** use manual F/Y/N registration,
runtime IK, or per-key correction.

The complete contract is documented in
`docs/source/policy_deployment/06_so101_keyboard/physical_typing_contract.rst`.
The matched AnchorBench, Workshop-baseline, and USD-drive procedure is in
`docs/source/policy_deployment/06_so101_keyboard/physical_typing_benchmark.rst`.

## Required Artifacts

Every deployment requires three explicit, immutable inputs:

1. the RSL-RL `model_N.pt` checkpoint;
2. that checkpoint's archived `params/env.yaml`; and
3. the machine-local LeRobot encoder rest-pose JSON matching the fixed reset.

The runner rejects the wrong keyboard calibration, task contract, actuator
profile, target length, A-Z map hashes, clearance contract, or rest pose before
opening the robot. It converts joints in both directions at the hardware
boundary and uses measured wall time for joint velocity.

## Validate Without Robot Motion

Use absolute artifact paths. `SO101_POLICY_DRY_RUN=1` loads and validates the
entire software contract but never connects to the robot:

```bash
SO101_POLICY_DRY_RUN=1 \
SO101_LEROBOT_PYTHON=/path/to/lerobot/bin/python \
./scripts/so101_homing/run_physical_calibrated_20260718_irl.sh \
  p1d-transit15 NVIDIA \
  /absolute/path/to/model_19999.pt \
  /absolute/path/to/params/env.yaml \
  /absolute/path/to/rest_pose.json
```

Valid recipe names are `p0`, `p1a`, `p1b`, `p1c`, `p1d`,
`p1d-transit15`, `baseline-p1d-transit15`, and
`usd-drive-p1d-transit15`.

## Run On Hardware

Remove `SO101_POLICY_DRY_RUN=1` and set stable hardware paths when automatic
device discovery is not unambiguous:

```bash
SO101_LEROBOT_PYTHON=/path/to/lerobot/bin/python \
SO101_KEYBOARD_DEVICE=/dev/input/by-id/<keyboard-event-device> \
SO101_ROBOT_PORT=/dev/serial/by-id/<robot-controller> \
SO101_ROBOT_ID=my_follower \
./scripts/so101_homing/run_physical_calibrated_20260718_irl.sh \
  p1d-transit15 NVIDIA \
  /absolute/path/to/model_19999.pt \
  /absolute/path/to/params/env.yaml \
  /absolute/path/to/rest_pose.json
```

The operator confirmation remains mandatory. The runner retries the measured
fixed-reset gate up to three times, starts PPO only after both encoder and
model-coordinate errors pass, stops on a wrong or overlapping key, and returns
to rest before releasing evdev.

## Safety And Fixture Validity

- Keep the keyboard, 4.44 mm mat, robot base, and fixed typing jaw unchanged.
- Keep the moving jaw closed; the fixed jaw is the typing contact.
- Stop power if the initial reset path is obstructed or unexpected.
- Moving any fixture component invalidates the frozen map. Recalibrate and
  create a new dated task contract before training or deployment.
- Do not add action holds, slew caps, rate scaling, manual F/Y/N replay, or
  wrapper-side geometry to a scored rollout.

Manual F/Y/N homing and pre-calibration policy adapters are intentionally absent
from this branch. Their history remains available in archival Git branches.
