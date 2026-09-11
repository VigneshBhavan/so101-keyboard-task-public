# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Run or resume a frozen physical SO-101 typing A/B/C benchmark session."""

from __future__ import annotations

import argparse
from pathlib import Path

from .constants import DEFAULT_KEYBOARD_DEVICE, DEFAULT_ROBOT_ID
from .typing_ab_execution import default_python, run_benchmark_session
from .typing_ab_video import OBSERVER_FPS, ObserverCapture, append_observer_segment, resolve_observer_device


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=default_python())
    parser.add_argument("--rest-pose", type=Path, required=True)
    parser.add_argument("--device", default=DEFAULT_KEYBOARD_DEVICE)
    parser.add_argument("--port", required=True)
    parser.add_argument("--id", default=DEFAULT_ROBOT_ID)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--enable-robot", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Skip the one-time session confirmation.")
    parser.add_argument("--max-trials", type=int, default=None)
    parser.add_argument("--inter-trial-s", type=float, default=1.0)
    parser.add_argument(
        "--observer-device",
        default=None,
        help="Logitech C920 video-index0 node or 'auto'. Required for scored robot runs by default.",
    )
    parser.add_argument("--observer-fps", type=int, default=OBSERVER_FPS)
    parser.add_argument("--observer-warmup-s", type=float, default=4.0)
    parser.add_argument(
        "--allow-no-observer",
        action="store_true",
        help="Run a non-final diagnostic without observer video.",
    )
    args = parser.parse_args()

    if args.enable_robot and args.observer_device is None and not args.allow_no_observer:
        parser.error("scored robot sessions require --observer-device auto (or an explicit node)")

    if args.enable_robot and not args.yes:
        print("Confirm safety: fixture fixed, camera recording, and operator ready to stop power.")
        answer = input("Start or resume the scored physical A/B/C session? [y/N] ")
        if answer.strip().casefold() != "y":
            return 1

    session_dir = args.session_dir.resolve()
    capture = None
    try:
        if args.enable_robot and args.observer_device is not None:
            observer = resolve_observer_device(args.observer_device)
            observer_dir = session_dir.parent / f"{session_dir.name}_observer"
            capture = ObserverCapture(
                device=observer,
                output_dir=observer_dir,
                fps=args.observer_fps,
                warmup_s=args.observer_warmup_s,
            ).start()
        result = run_benchmark_session(
            manifest_path=args.manifest.resolve(),
            session_dir=session_dir,
            python=args.python.resolve(),
            rest_pose=args.rest_pose.resolve(),
            device=args.device,
            port=args.port,
            robot_id=args.id,
            enable_robot=args.enable_robot,
            resume=args.resume,
            max_trials=args.max_trials,
            inter_trial_s=args.inter_trial_s,
        )
        if capture is not None:
            capture.assert_running()
        return result
    finally:
        if capture is not None:
            metadata = capture.stop()
            if session_dir.is_dir():
                append_observer_segment(session_dir, metadata)


if __name__ == "__main__":
    raise SystemExit(main())
