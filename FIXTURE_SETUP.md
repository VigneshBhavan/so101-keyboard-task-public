# Fixed Keyboard Fixture Setup

This guide describes the specific `physical-calibrated-20260718` fixture used
for the released blind SO-101 typing policies. It is a reproduction target for
the published benchmark. For new training, change the nominal keyboard pose or
its reset distribution through [task configuration](docs/release/TASK_CONFIGURATION.md).

## Required Hardware

- SO-101 mounted to a rigid base
- The same MX-style keyboard geometry used by this task
- A `4.44 mm` mat beneath the keyboard
- The fixed typing jaw and a closed moving jaw

Do not use these policies after changing the robot, keyboard, mat, jaw, or
fixture without revalidating the geometry and joint calibration.

## Coordinate Reference

The authoritative pose is the keyboard asset pose in the SO-101 model's base
frame, not a hand-measured visual estimate:

| Quantity | Value |
| --- | --- |
| Keyboard CAD origin in robot-base frame | `(262.565, 12.135, 1.781) mm` |
| Keyboard CAD roll, pitch, yaw | `(-5.000, 0.051, -88.606) deg` |
| Keyboard near case edge beyond robot-base housing | `125.28 mm` |
| Physical squareness offset | `1.39 deg` from square |
| Mat thickness | `4.44 mm` |

The CAD-origin orientation is not a top-down physical yaw. It follows the
keyboard asset's coordinate convention. The executable source of truth is:

`source/isaaclab_tasks/isaaclab_tasks/core/dexsuite/config/so101/physical_calibrated_20260718_env_cfg.py`

In that file, use `PHYSICAL_CALIBRATED_KEYBOARD_POSITION_B_M` and
`PHYSICAL_CALIBRATED_KEYBOARD_ROTATION_XYZW`; do not replace them with an
independently measured yaw convention.

## Physical Placement Procedure

1. Secure the SO-101 base so it cannot translate or rotate during a run.
2. Put the `4.44 mm` mat under the keyboard.
3. Align the keyboard near case edge `125.28 mm` beyond the robot-base housing
   in the trained forward direction.
4. Apply the small `1.39 deg` non-square offset used by the calibrated fixture.
   The sign and exact CAD alignment are encoded by the authoritative quaternion
   above; use the saved fixture marks or a physical template rather than
   estimating this from a photo.
5. Clamp or mark the keyboard so it cannot move relative to the robot base.
6. Run standard LeRobot calibration for your robot and export the policy's
   deployment bundle. Select the encoder convention explicitly; the historical
   benchmark corrections are separate from standard calibration. See
   [hardware preparation](docs/release/HARDWARE_PREPARATION.md).

## Validation Gate

Before a scored policy rollout:

1. Run `./so101 deploy BUNDLE TARGET` without `--execute` to validate the
   checkpoint, saved environment and generated reset target without hardware.
2. Confirm the fixture, keyboard, mat, and typing jaw have not moved.
3. Bring the robot to the fixed reset through the runner's measured reset gate.
   If it cannot settle within the configured tolerance, do not start PPO.
4. Begin with a supervised validation appropriate to the checkpoint stage.
   Stop on a wrong target, visible displacement, or an unexpected key event;
   inspect the fixture, calibration and policy before attempting a larger corpus.

## Limits Of This Guide

The numerical transform makes the simulator fixture reproducible. Exact
physical reproduction still requires a stable mechanical datum for the
robot-base housing and a robot-specific encoder calibration. A reusable public
deployment fixture would benefit from a dimensioned drawing or printable template.
Those physical aids and an automated policy-free A-Z IK parity probe are not
included in this release; use measured layout and operator alignment checks.
