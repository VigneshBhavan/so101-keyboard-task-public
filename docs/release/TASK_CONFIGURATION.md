# Change keyboard placement and randomization

The published fixture is the default, not a restriction on new training.
Choose independent task and physics configuration files:

```bash
./so101 train --actuator usd --task-config configs/tasks/keyboard-pose.json \
  --physics-config configs/physics/mjwarp-soft-drives.json --iterations 10
./so101 train --actuator anchorbench \
  --task-config configs/tasks/keyboard-domain-randomization.json --iterations 10
```

These short runs test setup. Increase the training budget for a learned policy.
Use `./so101 probe --task-config FILE` to check reset stability, commanded action
limits, and key-map alignment over several resets before training.

## Nominal pose

`keyboard.position_m` is the keyboard CAD origin's XYZ position in the robot-base
frame, in metres. `keyboard.yaw_offset_deg` rotates around robot-base Z relative
to the benchmark's orientation, about the keyboard CAD origin. It is not an
absolute CAD yaw. The keyboard mesh and nominal 26-key target map are transformed
together. A nominal height change also translates the support plane by that height.

`configs/tasks/keyboard-pose.json` demonstrates a 10 mm X shift and 2 degree yaw
offset. The policy keeps the existing 22-element observation and five arm actions.
Its nominal target coordinates change; normalization and the joint reset reference
stay fixed. Arbitrary nominal roll/pitch and vertical pose randomization are not
exposed in this first interface.

## Domain randomization

The reset distribution accepts uniform bounds for `keyboard_x_m`, `keyboard_y_m`,
and `keyboard_yaw_deg`, plus a nonnegative `reset_joint_noise_rad`. XY translations
and yaw are expressed in the robot-base/world axes about the nominal fixture.
The reference example uses +/-3 mm, +/-1 degree, and 0.005 radian reset noise.
These are example ranges, not a claim of achieved physical robustness.

The actor sees the nominal key coordinates throughout an episode. It does not
receive the sampled keyboard perturbation or live simulated key coordinates.
Rewards/contact judging can use live geometry, as in the original task. A separate
validation map is computed from the sampled reset transform and known key geometry,
then checked against simulated keys at every reset. This preserves the geometry
check without treating deliberate randomization as a map error.

The robot's observation/action reference q_reset remains fixed; the actual reset
arrival is randomized around it. Reset audits verify the actor map remains fixed.
Evaluate on enough seeds and episodes before claiming coverage of a distribution.

## Reproduce and deploy

Training saves `params/public_task.json` with `params/env.yaml`. Evaluation and
resume automatically discover it beside the configuration/checkpoint. Keep it
with `public_physics.json` when both were used. The task JSON hash becomes part of
the checkpoint's environment contract. A changed/missing config is rejected during
evaluation. Evaluation retains the requested DR distribution; benchmark checkpoints
without task JSON retain the original deterministic fixture evaluation.

`prepare-deployment` exports the nominal map and normalization from the trained
environment. Hardware uses that nominal map; no simulator-only sampled pose is
available to it. See [the hardware guide](HARDWARE_PREPARATION.md).
