SO-101 Physical Typing Contract
===============================

This page is the source of truth for the production SO-101 keyboard task.
The retained environment is the fixed-Cartesian, physical-calibrated 2026-07-18
lineage.  It uses Newton MJWarp and a frozen A-Z map derived from powered physical
contacts.

Only task IDs containing ``Physical-Calibrated-20260718`` below are valid for
new training or checkpoint evaluation.  The generic fixed-Cartesian and
anchor-conditioned prototypes are intentionally not registered.

Production task IDs
-------------------

.. list-table::
   :header-rows: 1

   * - Task suffix
     - Length
     - Episode limit
     - Clearance
     - Actuator profile
   * - ``AnchorBench-P0``
     - 1
     - 10 s
     - 4 mm
     - AnchorBench workshop A/B
   * - ``AnchorBench-P1A``
     - 2
     - 21 s
     - 4 mm
     - AnchorBench workshop A/B
   * - ``Baseline-P1A``
     - 2
     - 21 s
     - 4 mm
     - Original Workshop per-joint gains
   * - ``AnchorBench-P1B``
     - 3
     - 31 s
     - 4 mm
     - AnchorBench workshop A/B
   * - ``AnchorBench-P1C``
     - 4
     - 41 s
     - 4 mm
     - AnchorBench workshop A/B
   * - ``AnchorBench-P1D``
     - 6
     - 61 s
     - 4 mm
     - AnchorBench workshop A/B
   * - ``AnchorBench-P1D-Transit15``
     - 6
     - 61 s
     - 15 mm
     - AnchorBench workshop A/B
   * - ``Baseline-P1D-Transit15``
     - 6
     - 61 s
     - 15 mm
     - Original Workshop per-joint gains

Every ID begins with::

   Isaac-Keyboard-SO101-MX-Physical-Calibrated-20260718-FixedCartesian-

The baseline and AnchorBench Transit15 tasks must remain identical except for
``actuator_profile`` and the output experiment name.

Their policy weights remain independent. Baseline P1A starts from random actor
and critic initialization, and baseline Transit15 may resume only from a
qualified baseline P1A checkpoint. An AnchorBench checkpoint is never a valid
baseline warm start.

The Workshop arm explicitly uses the original ``stiffness`` and ``damping``
table from ``Sim-to-Real-SO-101-Workshop``. It does not override armature or
joint-friction fields; the shared USD leaves those fields unauthored, so Newton
resolves them to zero.

Actuator profile provenance
---------------------------

The comparison below freezes the three relevant parameter sources.  Each
slash-separated cell is ordered as ``Workshop baseline / AnchorBench / loaded
SO-101 USD``.  The Coulomb column is applied as both static and dynamic
friction for AnchorBench.

.. list-table:: Effective per-joint Newton parameters
   :header-rows: 1

   * - Joint
     - Kp
     - Kd
     - Armature
     - Coulomb friction
     - Viscous friction
   * - ``shoulder_pan``
     - 55 / 48.419899 / 100
     - 0.7 / 3.334595 / 1
     - 0 / 0.067620 / 0
     - 0 / 0.347432 / 0
     - 0 / 1.590709 / 0
   * - ``shoulder_lift``
     - 30 / 47.782635 / 100
     - 0.8 / 2.563165 / 1
     - 0 / 0.027645 / 0
     - 0 / 0.344793 / 0
     - 0 / 0.561425 / 0
   * - ``elbow_flex``
     - 25 / 14.715496 / 100
     - 0.7 / 0.343250 / 1
     - 0 / 0.037720 / 0
     - 0 / 0.411190 / 0
     - 0 / 0.796639 / 0
   * - ``wrist_flex``
     - 12 / 43.607166 / 100
     - 0.5 / 4.139243 / 1
     - 0 / 0.050714 / 0
     - 0 / 0.248233 / 0
     - 0 / 1.071871 / 0
   * - ``wrist_roll``
     - 7 / 54.873917 / 100
     - 0.5 / 2.968392 / 1
     - 0 / 0.054898 / 0
     - 0 / 0.221761 / 0
     - 0 / 1.637671 / 0
   * - ``gripper``
     - 4 / 68.250793 / 100
     - 0.3 / 2.818730 / 1
     - 0 / 0.077625 / 0
     - 0 / 0.083458 / 0
     - 0 / 0.958565 / 0

The loaded asset is
``https://huggingface.co/datasets/nvidia/Anchor-Lab/resolve/main/robot_assets/so101_no_camera_new_calib.usd``
with SHA-256
``c6c82840925ace388b0ff0acb7d8538c2b419d92fbe01dc70fe833b974d6d462``.
Its authored angular-drive values are ``1.7453292608261108`` stiffness and
``0.01745329238474369`` damping; after the USD angular-unit conversion these
are the effective ``Kp=100`` and ``Kd=1`` values shown above.  The asset does
not author a Newton-recognized armature or joint-friction field.  Its separate
``physics:JointEquivalentInertia`` metadata is not mapped to Newton armature by
the current importer.

.. warning::

   The generated community-upstream converter artifact at
   ``SO101/so101_new_calib.usd/config.yaml`` contains uniform ``Kp=17.8`` and
   ``Kd=0`` settings.  It is not the USD loaded by this task, not the original
   Workshop baseline, and not AnchorBench.  Never use that parameter pair for
   production training, evaluation, deployment, or the matched A/B/C benchmark.
Experimental loaded-USD arm
---------------------------

The isolated ``USDDrive`` tasks run the same calibrated scene, actor,
observation, reward, reset, and curriculum contracts as their corresponding
AnchorBench tasks.  Their only behavioral difference is the actuator profile
authored by the robot asset actually loaded by the task: uniform ``Kp=100``,
``Kd=1``, 10 N effort limit, 10 rad/s velocity limit, and zero effective Newton
armature and joint friction.  The source asset SHA-256 is
``c6c82840925ace388b0ff0acb7d8538c2b419d92fbe01dc70fe833b974d6d462``.

``USDDrive-P1A`` must start from random actor and critic weights.  A later
``USDDrive-P1D-Transit15`` continuation may resume only from a qualified
checkpoint produced by that same USD-drive P1A lineage.  AnchorBench and
Workshop baseline checkpoints are invalid warm starts for this experiment.

The generated community converter values ``Kp=17.8`` and ``Kd=0`` do not come
from the asset loaded by this task and are explicitly excluded from this
profile.

Actor contract
--------------

The actor receives exactly 22 values in this order:

1. Five measured arm positions relative to the fixed reset pose.
2. Five measured arm velocities in radians per second.
3. Five persistent commanded positions relative to the fixed reset pose.
4. The current target key XYZ, normalized by the frozen A-Z map statistics.
5. A three-way ``seek_press``, ``release_key``, or ``clearance`` phase one-hot.
6. Seconds elapsed in the current phase.

There is no letter identity, one-hot alphabet input, all-key geometry input,
contact state, or privileged simulator signal in the actor observation.  Key
identity is encoded only by the current target XYZ.

The policy emits five actions from a native bounded Beta distribution with
support ``[-1, 1]``.  At each 25 Hz control tick, one action is integrated once
using these joint-rate limits in radians per second::

   shoulder_pan  shoulder_lift  elbow_flex  wrist_flex  wrist_roll
       0.30           1.10          0.75         0.20        0.10

The resulting absolute joint command persists until the next actor action.
There is no wrapper action clip, action hold, extra slew cap, or repeated
integration.  The moving jaw remains closed and the fixed jaw is the typing
contact.

Typing state machine
--------------------

Success requires this sequence for every target:

``key down -> matching key up -> sustained clearance``

The switch thresholds are 50 percent travel for key down and 25 percent for key
up, each stabilized for two samples.  Clearance must hold for two consecutive
control ticks.  The target does not advance on key down or key up alone.

The environment terminates on a wrong or overlapping key, invalid frozen map,
out-of-contract action, phase timeout, excessive contact above 10 N, abnormal
robot state, or sustained low-clearance lateral scraping.  Transit15 applies
the same 15 mm value to advancement, scrape termination, and low-clearance
lateral-motion shaping.

Physical calibration
--------------------

The simulator consumes model-space joints.  LeRobot encoder values must be
converted at the physical deployment boundary as::

   q_model = q_lerobot + joint_zero_offset
   q_lerobot_command = q_model_command - joint_zero_offset

The frozen offsets in degrees are:

.. list-table::
   :header-rows: 1

   * - Joint
     - Offset
   * - shoulder pan
     - 0.000000
   * - shoulder lift
     - 1.933627
   * - elbow flex
     - -10.773579
   * - wrist flex
     - 1.364765
   * - wrist roll
     - 0.000000

Do not add these offsets to simulated model-space joints.  The keyboard pose,
model reset pose, A-Z goals, and conversion constants are frozen in
``physical_calibrated_20260718_env_cfg.py``.

Provenance locks
----------------

The production contract includes these SHA-256 identifiers:

.. list-table::
   :header-rows: 1

   * - Artifact
     - SHA-256
   * - Powered repeated A-Z dataset
     - ``dca2c7c51d4fabf5512cbeac59e617e289ab6deb0bf0855be5cd21c8c616b2d7``
   * - Powered contact trace archive
     - ``e1bb5b645fddfddca6e02e54c4e0e9c447d3acdaaea406f22b37d51e1d7ea01c``
   * - Physical calibrated A-Z target map
     - ``cd77d70242f5cac8f3dff8378be559c3d8b26cc816d014cfe9dc16dbb522d301``
   * - Physical joint-rate source
     - ``15dc8fcf17dfafd274f84de53d75e085240d5e44c5aab2f5b741ee170896fb04``

Absolute paths inside the checked-in A-Z JSON are immutable historical
provenance strings.  Runtime code does not open those paths.  Do not scrub the
JSON without intentionally creating a new calibration ID and checkpoint
contract.

Validation gates
----------------

Run the SO-101 unit and contract tests::

   ./isaaclab.sh -p -m pytest -q source/isaaclab_tasks/test/core/test_so101*.py

Run a real Newton contract probe::

   ./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/probe_so101_fixed_cartesian.py \
       --num-envs 1 --headless physics=newton_mjwarp

The probe must report a 22-D observation, 5-D action, frozen-map validity, a
bounded persistent command, and a physical press-release-clearance sequence
without a wrong or overlapping key.

Train only with an explicit production task ID and Newton::

   ./isaaclab.sh train --rl_library rsl_rl \
       --task Isaac-Keyboard-SO101-MX-Physical-Calibrated-20260718-FixedCartesian-AnchorBench-P1D-Transit15 \
       --headless physics=newton_mjwarp

Operational sequence
--------------------

Use this order for every candidate checkpoint:

1. Preserve the checkpoint with its exact ``params/env.yaml``.
2. Run the 1,024-environment strict simulator evaluator.
3. Inspect a one-environment MP4 and Newton Viewer rollout.
4. Run the physical launcher in software-only mode.
5. Run the physical fixed-reset handoff without wrapper action changes.
6. Freeze the final matched pair before collecting A/B results.

Public training and evaluation are documented in
``docs/release/QUICKSTART.md``. Physical deployment is documented in
``scripts/so101_homing/README.md``.  The final paired protocol is
:doc:`physical_typing_benchmark`.

Retained source boundary
------------------------

The production implementation is intentionally narrow:

* ``config/so101/__init__.py`` registers only the dated physical-calibrated
  task IDs.
* ``physical_calibrated_20260718_env_cfg.py`` owns the frozen scene pose,
  model reset, joint-zero conversion, A-Z goals, and production task variants.
* ``fixed_cartesian_env_cfg.py``, ``fixed_cartesian_targets.py``,
  ``registered_mx_env_cfg.py``, and ``so101_env_cfg.py`` are unregistered
  internal superclass and scene machinery.  Their generic defaults are not a
  deployable calibration and must not be exposed as task IDs.
* ``mdp/commands/fixed_cartesian_typing_commands*.py``,
  ``mdp/joint_rate_actions.py``, and the fixed-Cartesian terms in the remaining
  ``mdp`` modules implement the 22-D observation, bounded persistent action,
  press-release-clearance state machine, rewards, and termination gates.
* ``agents/rsl_rl_ppo_cfg.py`` contains only the native bounded-Beta policy
  configurations used by the dated task family.
* ``scripts/so101_homing/fixed_cartesian_policy.py``,
  ``run_fixed_cartesian_policy_handoff.py``, and
  ``run_physical_calibrated_20260718_irl.sh`` are the production checkpoint and
  hardware boundary.  ``policy_runtime.py`` contains only their shared evdev,
  rest-pose, hashing, and JSONL primitives.
* ``evaluate_so101_fixed_cartesian.py`` and
  ``probe_so101_fixed_cartesian.py`` are the production simulator gates.
* ``so101`` provides public container training, evaluation, and deployment
  preparation. Generated experiment outputs stay outside repository source.

Manual F/Y/N registration, runtime IK deployment, anchor-conditioned actors,
legacy shared encoders, pre-calibration task registrations, and failed reward
experiments are deliberately outside this boundary.  They are not included in this public release.

Change control
--------------

Do not silently alter task IDs, observation ordering, action timing, action
support, joint-rate limits, reset pose, A-Z map, calibration hashes, switch
thresholds, clearance semantics, or actuator manifests.  Any incompatible
change requires a new task ID, experiment namespace, tests, and documented
checkpoint contract.

Historical anchor-conditioned tasks, legacy shared-encoder policies, failed
reward variants, logs, checkpoints, and local experiment ledgers are not part
of this production task module.  Keep them in archival branches or external
artifact storage rather than re-registering them here.
