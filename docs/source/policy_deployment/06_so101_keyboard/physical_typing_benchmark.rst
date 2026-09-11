SO-101 Physical Typing A/B/C Benchmark
======================================

This procedure compares the AnchorBench, original-Workshop, and USD-drive
policies on the fixed ``physical-calibrated-20260718`` keyboard fixture.  All
three policies must use the same six-letter Transit15 recipe; only the actuator
payload may differ.

Benchmark contract
------------------

The scored corpus contains 100 deterministic, unique six-letter A-Z words.
Each word is attempted once by each policy.  The six possible A/B/C orders
rotate across blocks, balancing order position and adjacent-profile carryover.
``NVIDIA`` and ``NEWTON`` are reserved for showcase videos and do not enter the
scored corpus.  The runner pauses for 60 seconds after complete blocks 20, 40,
60, and 80, after all three profiles have completed that tranche.

Strict success requires the exact key-down sequence, matching key releases,
and the sustained 15 mm clearance gate after every letter.  A wrong key,
overlap, early press, phase timeout, or incomplete episode is a failure.  There
is no Backspace correction or retry inside a scored attempt.  Completion time
starts at PPO handoff and ends after the final release and clearance gate.

The native 61-second checkpoint horizon applies by default.  Do not add an
external 20-second cutoff.  Reset, camera, serial, checkpoint, and other
infrastructure failures are invalid attempts and are excluded from all three
denominators.

Prerequisites
-------------

Before collection:

* qualify all three checkpoints with the strict simulator evaluator;
* preserve each checkpoint with its exact ``params/env.yaml``;
* keep the keyboard, 4.44 mm mat, robot base, and fixed typing jaw unchanged;
* connect the Logitech C920 observer; and
* use a Python environment containing LeRobot, evdev, NumPy, and PyTorch.

Define local paths without committing them::

   export SO101_LEROBOT_PYTHON=/path/to/lerobot/bin/python
   export SO101_ROBOT_PORT=/dev/serial/by-id/<robot-controller>
   export SO101_REST_POSE=/absolute/path/to/rest_pose.json
   export SO101_AB_ROOT="$PWD/output/physical_typing_ab"

Prepare and freeze
------------------

Create the protocol once::

   "$SO101_LEROBOT_PYTHON" -m scripts.so101_homing.prepare_typing_ab_benchmark \
       --out "$SO101_AB_ROOT/protocol"

Freeze the matched checkpoint triplet.  Finalization hashes every artifact and
rejects differences outside the actuator profile and resolved actuator block::

   "$SO101_LEROBOT_PYTHON" -m scripts.so101_homing.finalize_typing_ab_benchmark \
       --protocol-dir "$SO101_AB_ROOT/protocol" \
       --anchor-checkpoint /absolute/path/to/anchor/model_19999.pt \
       --anchor-env-config /absolute/path/to/anchor/params/env.yaml \
       --baseline-checkpoint /absolute/path/to/baseline/model_19999.pt \
       --baseline-env-config /absolute/path/to/baseline/params/env.yaml \
       --usd-drive-checkpoint /absolute/path/to/usd_drive/model_19999.pt \
       --usd-drive-env-config /absolute/path/to/usd_drive/params/env.yaml

The output ``benchmark_manifest.json`` is create-once.  It rejects the same
checkpoint in multiple arms, wrong calibration hashes, wrong target length,
different clearance or horizon, and any unmatched training recipe field.

Preflight
---------

Verify the C920 stream before a scored session::

   "$SO101_LEROBOT_PYTHON" -m scripts.so101_homing.preflight_typing_ab_observer \
       --device auto \
       --record-test-dir "$SO101_AB_ROOT/camera_preflight"

Then validate all three policy manifests without connecting to the robot::

   "$SO101_LEROBOT_PYTHON" -m scripts.so101_homing.run_typing_ab_benchmark \
       --manifest "$SO101_AB_ROOT/protocol/benchmark_manifest.json" \
       --session-dir "$SO101_AB_ROOT/software_preflight" \
       --python "$SO101_LEROBOT_PYTHON" \
       --rest-pose "$SO101_REST_POSE" \
       --port "$SO101_ROBOT_PORT" \
       --dry-run

Collect or resume
-----------------

Start the scored session::

   "$SO101_LEROBOT_PYTHON" -m scripts.so101_homing.run_typing_ab_benchmark \
       --manifest "$SO101_AB_ROOT/protocol/benchmark_manifest.json" \
       --session-dir "$SO101_AB_ROOT/session_final" \
       --python "$SO101_LEROBOT_PYTHON" \
       --rest-pose "$SO101_REST_POSE" \
       --port "$SO101_ROBOT_PORT" \
       --enable-robot \
       --observer-device auto

There is one session-level safety confirmation.  Each trial then runs the
fixed-reset gate, exact native PPO contract, evdev scoring, return-to-rest, and
continuous C920 evidence capture.  The camera is evidence only and is never a
policy input.  Each valid result is appended before the next trial.  A stopped
session resumes at the next incomplete trial ID with ``--resume``.

The reset procedure retries up to three times.  If all attempts miss the 0.5
degree encoder or model-frame gate, PPO does not start, the trial is marked
invalid, and collection stops without advancing the schedule.  Correct the
infrastructure issue and rerun the same command with ``--resume``.  Already
scored trial IDs are skipped and observer segments are appended, never
overwritten.

Summarize and package
---------------------

Generate strict matched statistics::

   "$SO101_LEROBOT_PYTHON" -m scripts.so101_homing.summarize_typing_ab_benchmark \
       --session-dir "$SO101_AB_ROOT/session_final"

The report includes per-policy success with Wilson intervals, failure reasons,
complete A/B/C block outcomes, all three pairwise exact McNemar tests,
successful completion-time summaries, and pairwise timing differences.

Build the side-by-side timelapse and stage a review package::

   "$SO101_LEROBOT_PYTHON" -m scripts.so101_homing.build_typing_ab_timelapse \
       --session-dir "$SO101_AB_ROOT/session_final" \
       --out "$SO101_AB_ROOT/session_final/typing_ab_timelapse.mp4" \
       --speed 6

   "$SO101_LEROBOT_PYTHON" -m scripts.so101_homing.package_typing_ab_release \
       --session-dir "$SO101_AB_ROOT/session_final" \
       --timelapse "$SO101_AB_ROOT/session_final/typing_ab_timelapse.mp4" \
       --out "$SO101_AB_ROOT/release_final"

The timelapse builder first materializes every scored attempt under
``episode_videos/`` as a standalone MP4, then creates a three-column comparison.
It changes video playback only; it does not alter policy timing or scoring.
Review the create-once release folder before any external upload.
